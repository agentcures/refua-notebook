"""Browser-level JupyterLab widget rendering checks via Playwright."""

from __future__ import annotations

import json
import os
import socket
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import nbformat
import pytest

from refua_notebook.mime import REFUA_MIME_TYPE
from refua_notebook.widgets.admet import ADMETView
from refua_notebook.widgets.complex import ComplexView
from refua_notebook.widgets.sm import SMView


def _display_data_output(widget: object) -> nbformat.NotebookNode:
    """Convert widget MIME bundle to a notebook display_data output.

    Keep only the custom Refua MIME payload so JupyterLab exercises the
    extension renderer path rather than the plain HTML fallback.
    """
    bundle = widget._repr_mimebundle_()  # type: ignore[attr-defined]
    data = {}
    refua_payload = bundle.get(REFUA_MIME_TYPE)
    if refua_payload is not None:
        data[REFUA_MIME_TYPE] = refua_payload
    elif "application/vnd.refua+json" in bundle:
        data["application/vnd.refua+json"] = bundle["application/vnd.refua+json"]
    data.setdefault("text/plain", repr(widget))
    return nbformat.v4.new_output("display_data", data=data, metadata={})


def _wait_for_server_url(runtime_dir: Path, timeout_s: float = 45.0) -> str | None:
    """Wait for a Jupyter server runtime json and return the base URL."""
    start = time.time()
    while time.time() - start < timeout_s:
        for path in runtime_dir.glob("jpserver-*.json"):
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            url = payload.get("url")
            if isinstance(url, str) and url:
                parsed = urlparse(url)
                if parsed.port and parsed.port > 0:
                    return url
        time.sleep(0.2)
    return None


def _pick_free_port() -> int:
    """Reserve and return an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http_ready(url: str, timeout_s: float = 45.0) -> bool:
    """Poll an HTTP endpoint until it responds."""
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            with urlopen(url, timeout=3) as response:
                if int(getattr(response, "status", 200)) >= 200:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


@pytest.mark.skipif(
    not os.environ.get("REFUA_JLAB_PLAYWRIGHT"),
    reason="Set REFUA_JLAB_PLAYWRIGHT=1 to run the Playwright JupyterLab test.",
)
def test_jupyterlab_widgets_render_with_playwright(tmp_path: Path) -> None:
    """Open JupyterLab and verify widget content is rendered and loaded."""
    if shutil.which("jupyter") is None:
        pytest.skip("jupyter is not available in PATH")

    playwright = pytest.importorskip("playwright.sync_api")
    sync_playwright = playwright.sync_playwright
    PlaywrightError = playwright.Error

    repo_root = Path(__file__).resolve().parents[1]
    ext_dir = repo_root / "refua_notebook" / "labextension"
    assert ext_dir.exists(), "prebuilt labextension is missing"

    pdb_data = (
        "ATOM      1  N   GLY A   1      11.104  13.207   9.447  1.00 10.00           N\n"
        "ATOM      2  CA  GLY A   1      12.467  13.601   9.789  1.00 10.00           C\n"
        "ATOM      3  C   GLY A   1      13.084  12.622  10.799  1.00 10.00           C\n"
        "ATOM      4  O   GLY A   1      12.554  11.516  10.876  1.00 10.00           O\n"
        "TER\nEND\n"
    )

    notebook_path = tmp_path / "widgets_playwright.ipynb"
    admet = ADMETView({"logP": 2.5, "herg": 0.1}, title="Playwright ADMET")
    sm = SMView("CCO", name="Playwright SM", properties={"logP": 2.5, "herg": 0.1})
    complex_view = ComplexView(
        name="Playwright Complex",
        pdb_data=pdb_data,
        components=[
            {"type": "protein", "name": "Target", "sequence": "MKTAYIAK"},
            {"type": "ligand", "name": "Ligand", "smiles": "CCO"},
        ],
        affinity={"probability": 0.85},
    )

    nb = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                source="# pre-rendered widget outputs",
                execution_count=1,
                outputs=[
                    _display_data_output(admet),
                    _display_data_output(sm),
                    _display_data_output(complex_view),
                ],
            )
        ]
    )
    nbformat.write(nb, notebook_path)

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["JUPYTER_RUNTIME_DIR"] = str(runtime_dir)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    port = _pick_free_port()
    server_url = f"http://127.0.0.1:{port}/"

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
            "--ServerApp.root_dir",
            str(tmp_path),
            "--ip=127.0.0.1",
            f"--port={port}",
            "--ServerApp.port_retries=50",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        runtime_server_url = _wait_for_server_url(runtime_dir, timeout_s=60.0)
        if runtime_server_url is not None:
            server_url = runtime_server_url

        if not _wait_for_http_ready(urljoin(server_url, "lab"), timeout_s=60.0):
            log_output = ""
            if proc.stdout is not None:
                try:
                    log_output = proc.stdout.read()
                except Exception:
                    log_output = ""
            pytest.fail(
                "JupyterLab did not start successfully.\n"
                f"Process return code: {proc.poll()}\n"
                f"Expected URL: {server_url}\n"
                f"Server log:\n{log_output}"
            )

        with sync_playwright() as p:
            browser = None
            launch_error = None
            try:
                browser = p.chromium.launch(headless=True)
            except PlaywrightError as exc:
                launch_error = exc
                try:
                    # Fallback for offline environments with system Chrome installed.
                    browser = p.chromium.launch(channel="chrome", headless=True)
                except PlaywrightError as channel_exc:
                    pytest.skip(
                        "Playwright Chromium is unavailable; run "
                        "`poetry run playwright install chromium` or ensure "
                        "system Chrome is installed. "
                        f"(bundle error: {launch_error}; channel error: {channel_exc})"
                    )

            page = browser.new_page()
            notebook_url = urljoin(server_url, f"lab/tree/{notebook_path.name}")
            page.goto(notebook_url, wait_until="domcontentloaded", timeout=60_000)

            page.wait_for_selector(".jp-Notebook", timeout=60_000)
            page.wait_for_selector(".admet-view", timeout=60_000)
            page.wait_for_selector('[data-refua-smiles="1"]', timeout=60_000)
            page.wait_for_selector(
                '.complex-view[data-refua-widget="complex"]', timeout=60_000
            )
            page.wait_for_selector('[data-refua-molstar="1"]', timeout=60_000)

            page.wait_for_selector("text=Playwright ADMET", timeout=60_000)
            page.wait_for_selector("text=Playwright SM", timeout=60_000)
            page.wait_for_selector("text=Playwright Complex", timeout=60_000)

            admet_root = page.locator(
                '.admet-view[data-refua-widget="admet"]',
                has_text="Playwright ADMET",
            ).first
            assert admet_root.count() == 1
            assert admet_root.locator('input[data-admet-filter="1"]').count() == 1
            admet_tab_labels = admet_root.locator(
                "[data-admet-tab]"
            ).all_text_contents()
            assert any("All" in label for label in admet_tab_labels)
            assert any("Absorption" in label for label in admet_tab_labels)
            assert any("Toxicity" in label for label in admet_tab_labels)
            admet_rows_text = " ".join(
                admet_root.locator('[data-admet-row="1"]').all_text_contents()
            ).lower()
            assert "logp" in admet_rows_text
            assert "herg" in admet_rows_text

            complex_root = page.locator(
                '.complex-view[data-refua-widget="complex"]',
                has_text="Playwright Complex",
            ).first
            assert complex_root.count() == 1
            assert complex_root.locator("button[data-complex-tab]").count() == 0
            complex_text = complex_root.text_content() or ""
            assert "Playwright Complex" in complex_text
            assert "Binding Affinity" not in complex_text

            page.wait_for_selector(
                '.complex-view [data-refua-molstar="1"][data-refua-rendered="true"]',
                timeout=60_000,
            )

            loading_locator = complex_root.locator(
                '[data-refua-molstar-loading="1"]'
            ).first
            assert loading_locator.count() == 1
            assert (loading_locator.text_content() or "").strip()

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
