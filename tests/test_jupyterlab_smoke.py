"""Smoke test for JupyterLab integration."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not os.environ.get("REFUA_JLAB_SMOKE"),
    reason="Set REFUA_JLAB_SMOKE=1 to run the JupyterLab smoke test.",
)
def test_jupyterlab_smoke(tmp_path: Path) -> None:
    """Ensure the prebuilt extension is discovered and JupyterLab starts."""
    if shutil.which("jupyter") is None:
        pytest.skip("jupyter is not available in PATH")

    repo_root = Path(__file__).resolve().parents[1]
    ext_dir = repo_root / "refua_notebook" / "labextension"
    assert ext_dir.exists(), "prebuilt labextension is missing"

    app_dir = tmp_path / "lab"
    env = os.environ.copy()
    env["JUPYTERLAB_DIR"] = str(app_dir)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    env["JUPYTER_RUNTIME_DIR"] = str(runtime_dir)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    list_out = subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "labextension",
            "list",
            "--app-dir",
            str(app_dir),
        ],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
    combined = (list_out.stdout or "") + (list_out.stderr or "")
    assert "refua-notebook" in combined

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "jupyter",
            "lab",
            "--no-browser",
            "--ServerApp.token=",
            "--ServerApp.password=",
            "--ServerApp.open_browser=False",
            "--app-dir",
            str(app_dir),
            "--ServerApp.runtime_dir",
            str(runtime_dir),
            "--port=0",
        ],
        env=env,
    )

    url = None
    start = time.time()
    try:
        while time.time() - start < 45:
            for path in runtime_dir.glob("jpserver-*.json"):
                try:
                    data = path.read_text()
                except OSError:
                    continue
                if data:
                    url = "ready"
                    break
            if url:
                break
            time.sleep(0.2)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    assert url is not None, "JupyterLab did not start successfully"
