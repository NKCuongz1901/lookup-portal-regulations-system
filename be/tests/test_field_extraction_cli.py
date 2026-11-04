"""Offline CLI entry point and review artifact contract."""
import json
from pathlib import Path
import subprocess
import sys


def test_cli_reads_structure_output_and_writes_auditable_reports(tmp_path):
    source = tmp_path / "segments.json"
    output = tmp_path / "results" / "fields.json"
    readable = tmp_path / "results" / "fields.txt"
    content = "Sinh viên phải nộp hồ sơ trước ngày 15/12/2026."
    source.write_text(json.dumps({"segments": [{"segment_index": 0, "page_number": 3, "content": content}]}), encoding="utf-8")
    run = subprocess.run([
        sys.executable, "-m", "scripts.extract_fields", "--segments-json", str(source),
        "--output", str(output), "--text-output", str(readable),
    ], cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=True)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert json.loads(run.stdout)["candidates"] == {"obligation": 1, "deadline": 1}
    assert result["document_version_id"] is None
    assert result["warnings"]
    for candidate in result["candidates"]:
        for evidence in candidate["evidences"]:
            assert evidence["document_segment_id"] is None
            assert evidence["quote"] == content[evidence["start_offset"]:evidence["end_offset"]]
    assert "page 3" in readable.read_text(encoding="utf-8")
