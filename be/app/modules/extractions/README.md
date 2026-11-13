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

## Step 4.3 — Gemini field extraction

Production uses `gemini_extractor.extract_fields` through the existing Celery
field task. PDF/OCR, structure extraction, stored segments and review APIs stay
unchanged. There is no automatic fallback to regex when Gemini fails.

### Configuration

Install `requirements.txt`, set these variables in `be/.env` (see `.env.example`)
and restart **both the API and Celery worker**:

```dotenv
GEMINI_API_KEY=your-key-from-google-ai-studio
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_TIMEOUT_SECONDS=60
GEMINI_BATCH_CHARS=24000
GEMINI_MAX_BATCHES=8
```

The key is backend-only and is masked in settings representations. API/OCR can
start without it; a field run fails explicitly with `gemini_configuration` when
it is missing. API and workers must use identical model/batch settings. Changing
model, prompt, output schema or batch configuration requires a **new run** via
**Trích xuất lại**. Old completed runs/reviews remain readable and immutable.
The existing `extraction_method` is set to `gemini`; `rule_version` stores the
Gemini prompt/model/configuration fingerprint within its existing 50-character
column. No new migration is required for this switch.

### Provider and evidence contract

- Google Gen AI SDK `models.generate_content` uses JSON structured output via
  `response_json_schema`. Pydantic validates four typed arrays: deadlines,
  obligations, applicable subjects and legal bases. Results remain pending review.
- Prompts treat document text as untrusted data. No tools, browsing or external
  grounding are enabled. Only saved segment text and page/section metadata are
  sent to Gemini; R2 credentials, URLs, PDF bytes and user credentials are not.
- Gemini returns segment indices plus **verbatim quotes**, not character offsets.
  The backend resolves each quote against the exact segment content, including
  repeated-quote occurrence numbers, then computes Python Unicode offsets. A
  quote spanning segments has one evidence per segment. Context evidence can
  retain headings, conditions and actors. `raw_value` is rebuilt from value quotes.
  Whitespace-only OCR differences can be aligned back to the original substring;
  stored quotes always come from the source and a run warning records alignment.
  Letters, accents, numbers and punctuation are never altered to force a match.
- Unknown segments, quotes with changed characters, impossible dates, malformed
  JSON and incomplete schemas trigger one repair request per batch, with the
  original source and a validation hint. The repaired output is fully validated
  again. Unresolved errors or blocked/truncated responses fail the entire run;
  no partial fields are saved. Exact quote validation establishes source
  attribution; semantic interpretation still requires ADMIN/STAFF review.
- Long sources are batched with neighbouring segments as context. Every source
  row is assigned to a target batch; oversized input fails explicitly rather
  than being truncated. Exact duplicate source spans are collapsed. Default
  limits allow eight source batches and one repair per batch, with a 60-second
  per-call timeout and a shared 520-second provider budget below the worker lease.
- Empty results are valid and include a readable warning. Activities, results,
  assessments and proposed solutions are not separate field types. An issue
  date or academic year is not automatically a deadline.

SDK retries are disabled to keep each call bounded. Celery retries temporary
connection/timeouts, HTTP 429 and transient server errors up to three times with
backoff. Configuration errors and unverifiable output need user correction or
manual retry. Public errors/logs exclude provider response bodies and API keys.

Implementation follows the official [Google Gen AI SDK documentation](https://googleapis.github.io/python-genai/)
and [Gemini structured output documentation](https://ai.google.dev/gemini-api/docs/structured-output).

### Run and test

From `be/`, the following calls Gemini and writes **local reports only**:

```bash
.venv/bin/python -m scripts.extract_fields \
  --segments-json .cache/extraction/result.json \
  --output .cache/gemini/fields.json --text-output .cache/gemini/fields.txt

.venv/bin/python -m scripts.extract_fields \
  --version-id 12 --output .cache/gemini/version-12.json

.venv/bin/python -m scripts.extract_fields \
  --pdf /path/to/input.pdf --output .cache/gemini/fields.json

.venv/bin/python -m pytest -q tests --ignore=tests/postgres
```

`--r2-key` is also supported and first runs PDF/OCR/structure extraction. Live
Gemini calls consume the configured account's quota. Offline tests mock the
provider and never send document text to Google. The old `field_extractor.py`
and `rules/` are retained only for regression comparison: pass `--engine rules`
with a local/PDF dry run. The CLI defaults to Gemini; production always uses it.

`field_service.extract_fields_for_version` is a synchronous read-only helper for
scripts and owns no commits. Persisted/API work uses `result_service` and Celery,
which perform the snapshot/fencing checks described below.

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
database automatically. Gemini requires the `google-genai` dependency.

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
runs are immutable to retry. DB connectivity and transient Gemini errors retry up
to three times with backoff. The worker releases DB locks before calling Gemini,
then reacquires them and rechecks source fingerprints and lease ownership before
saving results. Field tasks use late acknowledgement; see the official
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
