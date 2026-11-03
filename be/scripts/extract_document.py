"""Dry-run PDF structure extraction without connecting to PostgreSQL.

Examples (run from be/):
  .venv/bin/python -m scripts.extract_document --pdf input.pdf --output result.json
  .venv/bin/python -m scripts.extract_document --r2-key documents/...pdf --output result.json
  .venv/bin/python -m scripts.extract_document --pages-json pages.json --output result.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.modules.extractions.structure_extractor import extract_structure
from app.modules.extractions.text_normalizer import normalize_pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pdf", type=Path)
    source.add_argument("--r2-key")
    source.add_argument("--pages-json", type=Path, help="Previously saved parse_pdf output")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--save-pages", type=Path, help="Save parse_pdf output for repeatable offline checks")
    parser.add_argument("--text-output", type=Path, help="Optional readable per-segment audit file")
    args = parser.parse_args()

    if args.pages_json:
        pages = json.loads(args.pages_json.read_text(encoding="utf-8"))
    else:
        from app.modules.extractions.services import parse_pdf

        if args.r2_key:
            # Lazy import: local PDF / text tests need no DB, Redis or R2 config.
            from app.core.storage import download_bytes

            try:
                content = download_bytes(args.r2_key)
            except Exception as error:
                parser.exit(1, f"R2 download failed ({type(error).__name__}); check connectivity and object access.\n")
        else:
            content = args.pdf.read_bytes()
        pages = parse_pdf(content)

    normalized = normalize_pages(pages)
    result = extract_structure(normalized)
    # Audit the two guarantees needed by downstream field extraction.
    for segment in result.segments:
        assert result.full_text[segment.char_start:segment.char_end] == segment.content
        page = next(span for span in result.page_spans if span.page_number == segment.page_number)
        assert page.char_start <= segment.char_start < segment.char_end <= page.char_end
    source_text = "".join(line.text for page in normalized.pages for line in page.lines)
    assert "".join(source_text.split()) == "".join(result.full_text.split())

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.save_pages:
        args.save_pages.parent.mkdir(parents=True, exist_ok=True)
        args.save_pages.write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.text_output:
        args.text_output.parent.mkdir(parents=True, exist_ok=True)
        entries = []
        for segment, node in zip(result.segments, result.nodes):
            entries.append(
                f"[Page {segment.page_number} | segment {segment.segment_index} | {node.kind} | "
                f"chars {segment.char_start}:{segment.char_end}]\n"
                f"Section: {segment.section_title or '(none)'}\n{segment.content}"
            )
        args.text_output.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "pages": len(result.page_spans),
        "segments": len(result.segments), "characters": len(result.full_text),
        "kinds": dict(Counter(node.kind for node in result.nodes)),
        "warnings": result.warnings,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
