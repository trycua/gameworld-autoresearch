"""Record immutable build provenance without copying Git credentials/history."""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fps_bench.qwen_baseline import ROOT, source_file_hashes

revision = sys.argv[1]
if not re.fullmatch(r"[0-9a-f]{40}", revision):
    raise SystemExit("SOURCE_REVISION must be the full source Git commit SHA")
(ROOT / "image-source.json").write_text(json.dumps({
    "git_commit": revision,
    "files_sha256": source_file_hashes(),
}, indent=2) + "\n")
