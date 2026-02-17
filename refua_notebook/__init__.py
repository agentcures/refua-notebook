"""Refua Notebook: IPython extension for Refua object rendering.

This package provides an IPython extension that registers automatic HTML
representations for Refua objects (SM, Protein, Complex, FoldResult) so they
display as interactive widgets automatically.

Example usage:
    >>> # Activate extension for automatic widget display
    >>> import refua_notebook
    >>> refua_notebook.activate()
    >>>
    >>> # Now Refua objects display automatically
    >>> from refua import SM, Protein, Complex
    >>> SM("CCO")  # Shows 2D structure + properties
    >>>
    >>> complex = Complex([Protein("MKTAYIAK"), SM("CCO")]).request_affinity()
    >>> result = complex.fold()
    >>> complex  # Shows 3D Mol* viewer with affinity when available
    >>>
    >>> # Or use %load_ext magic
    >>> %load_ext refua_notebook
"""

from importlib.metadata import version as _distribution_version
from pathlib import Path
import tomllib


def _read_version_from_pyproject() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    version = project.get("version")
    if not version:
        return None
    return str(version)


def _resolve_version() -> str:
    local_version = _read_version_from_pyproject()
    if local_version is not None:
        return local_version
    return _distribution_version("refua-notebook")


__version__ = _resolve_version()

# Extension functions
from refua_notebook.extension import (
    activate,
    deactivate,
    is_active,
    load_ipython_extension,
    unload_ipython_extension,
)


def _jupyter_labextension_paths():
    """Expose the prebuilt JupyterLab extension for federated discovery."""
    return [
        {
            "src": "labextension",
            "dest": "refua-notebook",
        }
    ]


__all__ = [
    # Extension
    "activate",
    "deactivate",
    "is_active",
    "load_ipython_extension",
    "unload_ipython_extension",
    "_jupyter_labextension_paths",
]
