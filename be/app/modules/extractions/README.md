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
- Celery enqueue after upload is a separate integration step.
