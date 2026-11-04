# PDF structure extraction

The existing `parse_pdf()` returns page dictionaries. The structure pipeline is
pure Python and does not connect to PostgreSQL, Redis, or R2:

```python
from app.modules.extractions.services import parse_pdf
from app.modules.extractions.text_normalizer import normalize_pages
from app.modules.extractions.structure_extractor import extract_structure

pages = parse_pdf(pdf_bytes)
result = extract_structure(normalize_pages(pages))
rows = result.to_rows()
# Later, the persistence layer adds document_version_id to each row.
```

## Contracts

- Input dictionaries use `content` and positive, strictly increasing
  `page_number` values, as returned by `parse_pdf`. Blank pages and page-number
  gaps are retained. Source content is never rewritten to guess OCR corrections.
- `segment_index` is zero-based across the document; `paragraph_index` is
  zero-based row order within the source page. It is an extraction index, not a
  guarantee of the PDF's typographic paragraph numbering.
- Each row belongs to exactly one page. Legal context survives a page break, but
  content spanning pages becomes separate rows. Page counters are preserved.
- `full_text` is canonical normalized text: wrapped lines within each segment
  join with spaces, segments are separated by two newlines, pages by `\n\f\n`.
  `page_spans` also includes blank pages. Offsets are half-open Unicode character
  ranges in this final text, not PDF bytes or the original OCR output. JavaScript
  callers must account for UTF-16 when slicing text with non-BMP characters.
- Every segment satisfies `full_text[char_start:char_end] == content`.
  Every non-whitespace character from normalized input is preserved in order.
- `nodes` contains intermediate `kind`, `number`, title and physical source-line
  ranges. These are not columns of `DocumentSegment`. `to_rows()` emits only the
  seven existing segment fields. No migration is required for this output.
- Chương / Mục / Điều establish legal context. Numeric clauses and lettered
  points become legal nodes only within an article. Descendants reset when a
  new parent begins. Header rows contain only the heading, never a duplicate
  copy of all their child content.
- Non-legal text falls back to Roman/dotted outline headings, uppercase
  headings, lists, blank lines and conservative paragraph boundaries. Bare
  numeric list items require a colon or uppercase title to become outline
  headings. Decimal table values and inline legal references are not headings.
- `section_title` includes hierarchy and is capped at the schema's 500
  characters, retaining both ends of very long titles and issuing a warning.
  Source content and full intermediate heading titles remain intact.
- `parser_version` is `structure-1.0`. Preserve the returned `full_text` together
  with offsets for downstream extraction or regenerate with the same parser.

## Dry run

Run from `be/`, using the existing virtual environment:

```bash
.venv/bin/python -m scripts.extract_document \
  --pdf /path/to/input.pdf \
  --output .cache/extraction/result.json \
  --save-pages .cache/extraction/pages.json \
  --text-output .cache/extraction/segments.txt

.venv/bin/python -m scripts.extract_document \
  --r2-key 'documents/2/exact-object-key.pdf' \
  --output .cache/extraction/result.json

.venv/bin/python -m scripts.extract_document \
  --pages-json .cache/extraction/pages.json \
  --output .cache/extraction/result.json

.venv/bin/python -m pytest -q tests/test_structure_extractor.py tests/test_extraction_ocr.py
```

`--r2-key` uses the existing backend settings and credentials; it does not
normalize the key (R2 object keys may contain decomposed Unicode). Local PDF and
saved-page inputs require no DB/Redis/R2 configuration. Scanned PDFs still need
Tesseract's `vie` and `eng` language data, configured with `TESSDATA_PREFIX`.

## Limits and integration

This is rule-based text segmentation, not reliable reconstruction of tables,
font styles or multi-column reading order. Garbled table text and missing spaces
already produced by OCR remain visible in the output; offsets prove source
coverage, not semantic OCR accuracy. Review real PDFs before extracting facts.

The parser also checks for a full-page scan with a small native text overlay:
digital-signature text alone must not suppress OCR of the scanned body. This is
a conservative heuristic (under 600 native characters, image coverage at least
80%, native text-block coverage under 15%), not a general OCR quality detector.

## Persistence

`segment_service.py` owns version claim / segment replace / fail marking:

```python
from app.core.database import SessionLocal
from app.modules.extractions.segment_service import (
    claim_version_for_parsing,
    mark_parse_failed,
    replace_segments_and_mark_parsed,
)
from app.modules.extractions.services import parse_pdf
from app.modules.extractions.structure_extractor import extract_structure
from app.modules.extractions.text_normalizer import normalize_pages

db = SessionLocal()
try:
    claim_version_for_parsing(db, version_id)
    result = extract_structure(normalize_pages(parse_pdf(pdf_bytes)))
    replace_segments_and_mark_parsed(db, version_id, result)
    # Keep result.full_text for later field extraction (not stored on DocumentVersion yet).
except Exception:
    mark_parse_failed(db, version_id)
    raise
finally:
    db.close()
```

- `claim_version_for_parsing` locks the row (`FOR UPDATE`) and moves
  `pending` / `failed` → `processing`. Concurrent workers get
  `VersionNotClaimableError`. Use `force=True` for intentional re-parse.
- `replace_segments_and_mark_parsed` deletes prior segments for that version,
  inserts `to_rows()`, sets `parsed` + `parser_version` + `parsed_at` in one
  transaction. Failure rolls back so previous segments stay.
- `mark_parse_failed` is a separate short transaction for orchestration after
  download/parse/replace errors.

## Celery

`tasks.process_document(document_version_id)` runs the full pipeline on a worker.
PDF uploads call `enqueue_document_parse` after the version row is committed.
Non-PDF uploads are not enqueued. Broker errors leave `parse_status=pending`.

```bash
# from be/
celery -A app.core.celery_app.celery_app worker -l info
```

Worker must list `extractions.process_document` under `[tasks]`.

## Step 4.3 — rule-based field extraction

`field_extractor.extract_fields(segments)` is pure Python. It returns pending
review candidates for `deadline`, `obligation`, `applicable_subject`, and
`legal_basis`. It does not call an LLM, PDF parser, R2, Redis, or PostgreSQL.
Four independent rule modules live in `rules/`; contracts live in
`field_types.py`. Current `rule_version` is `fields-1.0`.

For stored data, use the read service:

```python
import app.models  # Register all ORM relationships.
from app.core.database import SessionLocal
from app.modules.extractions.field_service import extract_fields_for_version

with SessionLocal() as db:
    result = extract_fields_for_version(db, document_version_id=12)
    payload = result.to_dict()
```

The service accepts only a non-deleted document's `parsed` version with segments.
It sorts by `segment_index` and reads the requested version only. A shared lock
on the version prevents the existing parser from replacing its segments during
the read transaction. The caller owns authorization and session lifetime; the
service does not commit, enqueue, change statuses, or persist fields. Missing
versions, unparsed versions, and missing segments produce distinct exceptions.

### Candidates and evidence

- Each candidate has `field_key`, per-field `item_index`, `raw_value`, a typed
  `normalized_value` object, `rule_id`, `rule_version`, `review_status=pending`,
  and an `evidences` list. Pending is a proposal marker, not a saved review record
  or a claim that the extracted information has been verified.
- Each evidence has the actual `document_segment_id`, `segment_index`, source
  page/section, `quote`, and local `start_offset` / `end_offset`. The invariant is
  `segment.content[start_offset:end_offset] == quote`. Offsets use Python Unicode
  characters, not bytes or JavaScript UTF-16 code units. No second normalization
  of segment text is performed before matching.
- `role=value` identifies the literal matched text. `role=context` retains
  surrounding conditions/actions or the actual subject heading. A match can
  span adjacent unfinished segments/pages; each piece cites its own source.
  A synthetic newline joins such segments only in the in-memory matching view.
- Repeated values in identical textual and section context share one candidate,
  with all source occurrences retained (`occurrence_index`). Same dates with
  different actions/conditions remain separate. No numeric confidence score is
  invented. Source IDs are `null` only for dry runs before segment persistence.
- Local offsets do not require a stored full-document `full_text`. They refer
  directly to the saved segment content. Re-parsing currently replaces those
  rows, so Step 4.4 must define immutable parse history or an evidence snapshot
  policy before keeping long-lived reviews that reference segment IDs.

### Supported rules and limits

- Deadlines: explicit before/on-or-before dates (`DD/MM/YYYY`, `DD-MM-YYYY`,
  `ngày D tháng M năm YYYY`), application date ranges including shared month/year
  notation, numeric relative durations and beginning/end-of-period recurrence.
  Calendar dates are validated. Relative deadlines preserve the anchor text;
  no due date is calculated and missing years are not guessed. Opening dates,
  bare publication dates, exam schedules and exam durations are not deadlines.
- Obligations: explicit `phải`, `có trách nhiệm`, `bắt buộc`, including a trailing
  `(bắt buộc)` marker. Common negation, optional wording and questions are
  excluded. Positive requirements after `nhưng` remain discoverable. Implicit
  instructions without these markers are not comprehensively detected.
- Subjects: explicit application/subject markers, and subject lists under an
  actual applicable-subject heading. Heading evidence is retained. Eligibility
  conditions stay verbatim; they are not converted into a decision about a user.
- Legal bases: explicitly introduced laws/codes or numbered decrees, circulars,
  decisions and regulations. Generic `căn cứ xét tuyển` / `theo quy định` is
  excluded. Reference numbers are copied as OCR produced them, not corrected or
  checked against a legal database. Issue dates are not deadline candidates.

These are conservative text heuristics, not a complete Vietnamese semantic
parser. Lists introduced by `sau:` may need multiple candidates read together.
Some common OCR joins are accepted by regex, but garbled table cells, lost
words, complex exclusions, spelled-out durations and ambiguous cross-section
references need manual review or later rules. Cross-segment joining is bounded
to unfinished adjacent paragraphs in the same section, at most 8,000 characters;
it does not reconstruct tables. Counts of candidates are not precision/recall.

### Run and test

Run from `be/`. PDF/R2 inputs are optional dry-run conveniences which run Step
4.2 first. Production Step 4.3 reads saved segments via `--version-id`.

```bash
.venv/bin/python -m scripts.extract_fields \
  --version-id 12 --output .cache/fields/version-12.json

.venv/bin/python -m scripts.extract_fields \
  --segments-json .cache/extraction/result.json \
  --output .cache/fields/result.json --text-output .cache/fields/result.txt

.venv/bin/python -m scripts.extract_fields \
  --pdf /path/to/input.pdf --output .cache/fields/result.json

.venv/bin/python -m scripts.extract_fields \
  --r2-key 'documents/2/exact-object-key.pdf' --output .cache/fields/result.json

.venv/bin/python -m pytest -q tests/test_field_extractor.py tests/test_field_service.py
# With TEST_DATABASE_URL pointing to a test PostgreSQL instance:
.venv/bin/python -m pytest -q tests/postgres/test_field_extraction.py
```

The CLI writes only local JSON/text reports. Step 4.4 (extraction-run/field/
evidence/review tables and migrations) is not implemented here. The upload parse
task remains focused on saving segments; it does not discard field proposals
by running Step 4.3 before there is a persistence destination for them.
