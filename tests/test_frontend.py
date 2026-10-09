"""Run the real frontend scripts with Node's isolated DOM/network harness."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_frontend_behavior():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for the frontend behavioral harness")
    script = Path(__file__).with_suffix(".js")
    result = subprocess.run(
        [node, "--test", str(script)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
