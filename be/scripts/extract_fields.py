"""Step 4.3 dry run; reads source segments, writes local JSON/text, no DB writes."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.modules.extractions.field_extractor import extract_fields


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--version-id", type=int, help="Read a parsed version from PostgreSQL")
    source.add_argument("--segments-json", type=Path, help="Step 4.2 result JSON, or a list of segment rows")
    source.add_argument("--pdf", type=Path)
    source.add_argument("--r2-key", help="Exact object key; not Unicode-normalized")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--text-output", type=Path)
    args = parser.parse_args()

    if args.version_id is not None:
        import app.models  # noqa: F401 — register ORM relationships
        from app.core.database import SessionLocal
        from app.modules.extractions.field_service import extract_fields_for_version

        with SessionLocal() as db:
            result = extract_fields_for_version(db, args.version_id)
    else:
        if args.segments_json:
            data = json.loads(args.segments_json.read_text(encoding="utf-8"))
            rows = data["segments"] if isinstance(data, dict) else data
        else:
            from app.modules.extractions.services import parse_pdf
            from app.modules.extractions.structure_extractor import extract_structure
            from app.modules.extractions.text_normalizer import normalize_pages

            if args.r2_key:
                from app.core.storage import download_bytes

                try:
                    pdf = download_bytes(args.r2_key)
                except Exception as error:
                    parser.exit(1, f"R2 download failed ({type(error).__name__}); check connectivity and object access.\n")
            else:
                pdf = args.pdf.read_bytes()
            rows = extract_structure(normalize_pages(parse_pdf(pdf))).to_rows()
        result = extract_fields(rows)
        by_index = {row["segment_index"]: row["content"] for row in rows}
        for candidate in result.candidates:
            for evidence in candidate.evidences:
                if by_index[evidence.segment_index][evidence.start_offset:evidence.end_offset] != evidence.quote:
                    raise ValueError("Evidence does not match source segment")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.text_output:
        entries = []
        for item in result.candidates:
            lines = [f"[{item.field_key} #{item.item_index} | {item.rule_id} | pending]", item.raw_value,
                     "Normalized: " + json.dumps(item.normalized_value, ensure_ascii=False)]
            for evidence in item.evidences:
                lines.append(f"  {evidence.role} / occurrence {evidence.occurrence_index} / "
                             f"segment {evidence.segment_index} (DB id {evidence.document_segment_id}) / "
                             f"page {evidence.page_number} / chars {evidence.start_offset}:{evidence.end_offset}: {evidence.quote}")
            entries.append("\n".join(lines))
        args.text_output.parent.mkdir(parents=True, exist_ok=True)
        args.text_output.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "segments": result.segment_count,
                      "candidates": dict(Counter(c.field_key for c in result.candidates)),
                      "warnings": result.warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
