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
`field_types.py`. Current `rule_version` is `fields-1.1`.

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
  surrounding conditions/actions or the actual subject/legal-basis heading. A match can
  span adjacent unfinished segments/pages; each piece cites its own source.
  A synthetic newline joins such segments only in the in-memory matching view.
- Repeated values in identical textual and section context share one candidate,
  with all source occurrences retained (`occurrence_index`). Same dates with
  different actions/conditions remain separate. No numeric confidence score is
  invented. Source IDs are `null` only for dry runs before segment persistence.
- Local offsets do not require a stored full-document `full_text`. They refer
  directly to the saved segment content. Step 4.4 copies that content into an
  evidence snapshot, preserving its meaning after re-parsing replaces the rows.

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
  decisions, regulations and plans. References starting a paragraph/list item
  under an actual `Căn cứ`, `Căn cứ pháp lý`, `Căn cứ đánh giá` or `Cơ sở pháp lý`
  heading also qualify; evidence retains that heading. Context stops at the next
  heading, unrelated section or missing source chunk. Generic `căn cứ xét tuyển`,
  `theo quy định`, unnumbered plans and standalone mentions in reported activities
  are excluded. Reference numbers are copied as OCR produced them, not corrected
  or checked against a legal database. Issue dates are not deadline candidates.

A report can parse successfully into many segments while yielding no candidates
for these four fields. Activities, results, assessments and proposed solutions
are not additional field types. Updating rules requires a new extraction run
(restart API/worker and use **Trích xuất lại**); completed runs and reviews keep
their original rule version and evidence.

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

The Step 4.3 CLI still writes only local JSON/text reports. For persisted runs,
use the Step 4.4 services, task, or authenticated endpoints below.

## Step 4.4 — persisted runs, proposals and evidence

Migration `b8f31d2c9a60` adds `extraction_runs`, `extracted_fields` and
`field_evidences`. Existing documents, versions and segments are not modified.
Apply the migration before restarting the API and Celery worker with this code:

```bash
# From be/, using the database configured for your intended environment:
.venv/bin/alembic upgrade head
.venv/bin/celery -A app.core.celery_app.celery_app worker -l info
```

The worker must register both `extractions.process_document` and
`extractions.extract_document_fields`. This change does not migrate your live
database automatically and does not need a new Python dependency.

### Lifecycle and recovery

1. The upload API commits a version and queues the existing parse task.
2. The parse worker saves segments, marks the version `parsed`, and creates a
   pending automatic extraction run **in the same transaction**.
3. After commit it publishes the field task using the run ID. Automatic requests
   deduplicate by version, source generation and rule version.
4. The field worker claims `pending`/`failed` work (or an expired lease), increments
   the attempt count and runs Step 4.3 over persisted segments. It atomically
   saves fields/evidence and marks the run `completed`, including zero-candidate
   results. All new fields have `review_status=pending`.
5. On failure, the transaction rolls back and the run is marked `failed` in a
   separate transaction. Its public error is sanitized. `parse_status` and the
   already-saved segments are unaffected.

Version/run locks use a consistent order. A 10-minute lease and execution token
exclude active duplicate attempts and fence off a superseded worker. Completed
runs are immutable to retry. DB connectivity errors retry up to three times with
backoff. Field tasks use late acknowledgement; see the official
[Celery task documentation](https://docs.celeryq.dev/en/stable/userguide/tasks.html#acks-late).
Hard-killed workers can still require manual retry after lease expiry; there is
no periodic recovery scheduler in this change.

A failed broker publish leaves a durable pending run with
`error_code=queue_unavailable`; the API returns 503 with that run's ID. Retry the
same run when Redis is available. A crash after the parse commit but before
publish can likewise leave a pending run; the retry endpoint handles it without
re-downloading or re-parsing the PDF. Old unparsed uploads are not backfilled.

Each run records a hash of the exact source segment IDs/content/metadata,
parser version and source parse timestamp. If those change while work is queued,
the run fails with `source_changed`; create a new run. If the installed rules no
longer match the requested version, the error is `rule_version_changed`. A retry
never silently substitutes new input/rules for an old run.

### Historical evidence

Every evidence saves the complete `segment_content_snapshot`, page, section,
original `source_segment_id`, quote and local offsets. PostgreSQL constraints
also enforce that the quote equals the indicated snapshot slice. Its optional
live `document_segment_id` FK uses `ON DELETE SET NULL`; when re-parsing deletes
old segments, historical quotes and snapshots remain intact. Old completed runs
stay readable and each intentional re-run creates a separate history entry.

These remain proposals until an ADMIN/STAFF member reviews them through the
review endpoints and FE screen described below.

### API (ADMIN / STAFF)

All paths below are prefixed with `/api/v1`; they use the existing `ApiResponse`
envelope. Deleted documents are hidden from every endpoint.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/document-versions/{version_id}/extraction-runs` | Run history, newest first |
| GET | `/extraction-runs/{run_id}` | Status, counts, parser/rule versions, errors and timing |
| GET | `/extraction-runs/{run_id}/fields` | Fields with evidence snapshots |
| POST | `/document-versions/{version_id}/extraction-runs` | Create/queue an intentional run |
| POST | `/extraction-runs/{run_id}/retry` | Retry the same run without duplicating fields |

Lists support `page` and `itemsPerPage` (1–100). The fields endpoint additionally
accepts `field_key` and `review_status` filters. Run detail is metadata; fields
are retrieved separately so large evidence snapshots are paginated.

Create body: `{"idempotency_key": "<client-generated UUID>"}`. Reuse the UUID
for HTTP retries; generate a new one to intentionally create a new run. Keys
are scoped to the document version. Queue acceptance returns 202, an already
completed request returns 200, stale/unparsed sources or an active explicit
retry return 409. The field task does not run inside the HTTP request.

For internal scripts/workers, `result_service.create_run(db, version_id, ...)`
and `result_service.execute_run(db, run_id)` provide the same lifecycle. These
functions own commits/rollbacks and require a dedicated session, unlike the
read-only Step 4.3 service. Callers remain responsible for authorization.

### Validation

```bash
.venv/bin/python -m pytest -q tests --ignore=tests/postgres
# PostgreSQL test account must be allowed to create isolated schemas:
.venv/bin/python -m pytest -q tests/postgres/test_extraction_results.py
```

PostgreSQL tests cover migration round trips, atomic rollback, retry/idempotency,
lease fencing, source changes, snapshot survival, API permissions, pagination
and queue failure. They use the existing rollback-only test schema fixture.

With the two previously downloaded R2 PDFs' page text available under
`.cache/extraction-smoke/`, enable the optional persistence smoke tests:

```bash
# TEST_DATABASE_URL must point to an isolated test PostgreSQL instance.
RUN_EXTRACTION_PDF_SMOKE=1 .venv/bin/python -m pytest -q tests --tb=short
```

Verified on 2026-11-04 against a temporary PostgreSQL 16 instance with ICU
collation: **260 tests passed**. The admissions PDF produced 13 stored candidates
and 33 evidence rows; the tuition notice produced 3 candidates and 6 evidence
rows. Every quote matched its saved segment slice and page. Reports are written
to `.cache/extraction-persistence/{admissions,tuition}.persisted.json`; test data
is rolled back and the project database is not migrated by these checks.
Broker publication is mocked in tests; this does not verify a deployed Redis /
Celery worker setup.

## Human review and FE comparison

Migration `c9a42e7d0b13` adds `field_reviews` and the fields `review_revision`,
`reviewed_value`, `reviewed_at` on each extracted field. Run `alembic upgrade head`
before deploying the new API/FE. Existing proposals start at revision 0.

- `POST /api/v1/extracted-fields/{field_id}/reviews` saves a review atomically.
- `GET /api/v1/extracted-fields/{field_id}/reviews?page=1&itemsPerPage=5` returns
  audit history, newest revision first. Both endpoints require ADMIN/STAFF and
  hide fields belonging to deleted documents.

Example correction request:

```json
{
  "action": "correct",
  "expected_revision": 0,
  "idempotency_key": "a0f00d12-a0e4-49a5-af60-2852aef94522",
  "corrected_value": "20/12/2026",
  "note": "Đã đối chiếu thời hạn trên văn bản gốc."
}
```

`approve` and `reject` do not accept `corrected_value`. Correction and rejection
require a nonblank note. Correction means **correct and approve**. `expected_revision`
must match the field revision; a stale write returns 409. Retrying an identical
request with the same key and reviewer is idempotent; reusing that key for a
different request returns 409. Review is allowed only on completed runs.

Corrections are human-authored text in `reviewed_value`. The original `raw_value`,
machine `normalized_value`, and evidence are never overwritten. Consumers must
use `reviewed_value` when present and check `review_status`; original normalized
JSON must not be mistaken for a corrected machine-readable value. Rejecting a
previously corrected field retains its value for audit purposes. Review history
records actor identity/name, time, action, previous/new values and status, and note.
The API does not offer editing/deleting audit entries or publishing a document.

In FE, open **Văn bản → Chi tiết → Phiên bản → Đối chiếu trích xuất**. The screen
loads the actual PDF and run/field APIs, supports run history, polling, filters,
pagination, retry, approve/correct/reject, and review history. Selecting evidence
jumps to its source page. Highlighting applies to the saved source text using
Unicode code-point offsets. The current schema has no PDF bounding boxes, so
there is no claim of pixel-accurate highlights over scanned PDF pages.
