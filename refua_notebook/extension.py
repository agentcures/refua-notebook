"""Refua IPython extension for automatic widget rendering.

This module provides an IPython extension that registers HTML representations
for Refua objects (SM/MolProperties, Protein, Complex, FoldResult,
AffinityPrediction) so they automatically display as interactive widgets in
Jupyter notebooks.

Usage:
    In a Jupyter notebook:

    >>> # Option 1: Load as IPython extension
    >>> %load_ext refua_notebook

    >>> # Option 2: Activate programmatically
    >>> import refua_notebook
    >>> refua_notebook.activate()

    >>> # Now Refua objects display automatically
    >>> from refua import SM, Protein, Complex
    >>> SM("CCO")  # Displays 2D structure
    >>>
    >>> complex = Complex([Protein("MKTAYIAK"), SM("CCO")]).request_affinity()
    >>> result = complex.fold()
    >>> complex  # Displays 3D Molstar viewer
"""

from __future__ import annotations

import html
import sys
from typing import TYPE_CHECKING, Any, Optional

from refua_notebook.mime import REFUA_MIME_TYPE

if TYPE_CHECKING:
    from IPython.core.interactiveshell import InteractiveShell

# Track whether extension is activated
_extension_active = False


def _get_sm_repr_html(sm_obj: Any, include_scripts: bool = True) -> str:
    """Generate HTML representation for a Refua SM (small molecule) object.

    Parameters
    ----------
    sm_obj : refua.SM
        A Refua small molecule object.

    Returns
    -------
    str
        HTML representation showing 2D structure and properties.
    """
    from rdkit import Chem
    from refua import MolProperties, SmallMolecule
    from refua_notebook.widgets.admet import ADMETView
    from refua_notebook.widgets.smiles import SmilesView

    if isinstance(sm_obj, SmallMolecule):
        mol = sm_obj.mol
        title = sm_obj.name
        properties = sm_obj.properties().to_dict()
    elif isinstance(sm_obj, MolProperties):
        mol = sm_obj.mol
        title = getattr(sm_obj, "name", None)
        properties = sm_obj.to_dict()
    else:
        raise TypeError(
            "Expected a refua MolProperties or SmallMolecule object for SM display."
        )

    if title is None and mol is not None and mol.HasProp("_Name"):
        title = mol.GetProp("_Name")

    smiles = None
    if hasattr(sm_obj, "smiles"):
        smiles = sm_obj.smiles
    if not smiles and mol is not None:
        smiles = Chem.MolToSmiles(mol, canonical=True)

    html_parts = []

    if smiles:
        view = SmilesView(smiles, title=title, width=400, height=300)
        html_parts.append(view.to_html(include_scripts=include_scripts))

    if properties and isinstance(properties, dict):
        admet_view = ADMETView(
            properties,
            title=f"{title} Properties" if title else "Molecule Properties",
            compact=True,
        )
        html_parts.append(admet_view.to_html())

    if not html_parts:
        info = f"SM({smiles})" if smiles else repr(sm_obj)
        return (
            '<div style="font-family: monospace; padding: 8px; background: #f3f4f6; '
            f'border-radius: 4px;">{html.escape(info)}</div>'
        )

    return "\n".join(html_parts)


def _get_protein_repr_html(protein_obj: Any, include_scripts: bool = True) -> str:
    """Generate HTML representation for a Refua Protein object.

    Parameters
    ----------
    protein_obj : refua.Protein
        A Refua protein object.

    Returns
    -------
    str
        HTML representation showing protein information and optionally 3D structure.
    """
    from refua import Protein as RefuaProtein
    from refua_notebook.widgets.protein import ProteinView

    if not isinstance(protein_obj, RefuaProtein):
        raise TypeError("Expected a refua Protein object for Protein display.")

    return ProteinView.from_refua_protein(protein_obj).to_html(
        include_scripts=include_scripts
    )


def _get_complex_repr_html(complex_obj: Any, include_scripts: bool = True) -> str:
    """Generate HTML representation for a Refua Complex object.

    Parameters
    ----------
    complex_obj : refua.Complex
        A Refua complex object (folded or unfolded).

    Returns
    -------
    str
        HTML representation using the ComplexView widget.
    """
    import refua
    from refua import Complex as RefuaComplex
    from refua.unified import FoldResult
    from refua_notebook.widgets.complex import ComplexView

    allowed = (RefuaComplex, FoldResult)
    if hasattr(refua, "FoldedComplex"):
        allowed = (*allowed, refua.FoldedComplex)  # type: ignore[assignment]

    if not isinstance(complex_obj, allowed):
        raise TypeError(
            "Expected a refua Complex or FoldResult object for Complex display."
        )

    try:
        return ComplexView.from_refua_complex(complex_obj).to_html(
            include_scripts=include_scripts
        )
    except Exception:
        return (
            '<div style="font-family: monospace; padding: 8px; background: #f3f4f6; '
            f'border-radius: 4px;">{html.escape(repr(complex_obj))}</div>'
        )


def _get_affinity_repr_html(affinity_obj: Any, include_scripts: bool = True) -> str:
    """Generate HTML representation for a Refua AffinityPrediction object."""
    from refua_notebook.widgets.affinity import AffinityView

    return AffinityView(affinity_obj).to_html(include_scripts=include_scripts)


_REFUA_TYPE_REGISTRY = (
    ("refua.chem", "MolProperties", _get_sm_repr_html),
    ("refua.chem", "SmallMolecule", _get_sm_repr_html),
    ("refua.unified", "Protein", _get_protein_repr_html),
    ("refua.unified", "Complex", _get_complex_repr_html),
    ("refua.unified", "FoldResult", _get_complex_repr_html),
    ("refua.boltz.api", "AffinityPrediction", _get_affinity_repr_html),
    ("refua.unified", "AffinityPrediction", _get_affinity_repr_html),
    ("refua", "AffinityPrediction", _get_affinity_repr_html),
)


def _get_sm_repr_mime(sm_obj: Any) -> dict[str, Any]:
    return {"html": _get_sm_repr_html(sm_obj, include_scripts=False)}


def _get_protein_repr_mime(protein_obj: Any) -> dict[str, Any]:
    return {"html": _get_protein_repr_html(protein_obj, include_scripts=False)}


def _get_complex_repr_mime(complex_obj: Any) -> dict[str, Any]:
    return {"html": _get_complex_repr_html(complex_obj, include_scripts=False)}


def _get_affinity_repr_mime(affinity_obj: Any) -> dict[str, Any]:
    return {"html": _get_affinity_repr_html(affinity_obj, include_scripts=False)}


_REFUA_MIME_REGISTRY = (
    ("refua.chem", "MolProperties", _get_sm_repr_mime),
    ("refua.chem", "SmallMolecule", _get_sm_repr_mime),
    ("refua.unified", "Protein", _get_protein_repr_mime),
    ("refua.unified", "Complex", _get_complex_repr_mime),
    ("refua.unified", "FoldResult", _get_complex_repr_mime),
    ("refua.boltz.api", "AffinityPrediction", _get_affinity_repr_mime),
    ("refua.unified", "AffinityPrediction", _get_affinity_repr_mime),
    ("refua", "AffinityPrediction", _get_affinity_repr_mime),
)


def _register_formatters_by_name(formatter: Any, registry: tuple) -> bool:
    if formatter is None or not hasattr(formatter, "for_type_by_name"):
        return False
    for module_name, type_name, handler in registry:
        formatter.for_type_by_name(module_name, type_name, handler)
    return True


def _unregister_formatters_by_name(formatter: Any, registry: tuple) -> bool:
    if formatter is None:
        return False
    deferred = getattr(formatter, "deferred_printers", None)
    if not isinstance(deferred, dict):
        return False
    removed = False
    for module_name, type_name, _ in registry:
        if deferred.pop((module_name, type_name), None) is not None:
            removed = True
    return removed


def _get_mime_formatter(ip: "InteractiveShell") -> Optional[Any]:
    """Return a formatter for the custom Refua MIME type.

    The formatter must accept JSON-serializable mappings because Refua widget
    MIME handlers return payloads shaped like ``{"html": "<div>..."}``.
    """

    def _supports_mapping_payloads(formatter: Any) -> bool:
        return_type = getattr(formatter, "_return_type", None)
        if isinstance(return_type, tuple):
            return dict in return_type or list in return_type
        return return_type in (dict, list)

    display_formatter = getattr(ip, "display_formatter", None)
    if display_formatter is None:
        return None

    try:
        mime_formatter = display_formatter.formatters.get(REFUA_MIME_TYPE)
    except Exception:
        mime_formatter = None

    # BaseFormatter defaults to string return values, which causes dict MIME
    # payloads to be rejected. Ensure the formatter supports mapping payloads.
    if mime_formatter is None or not _supports_mapping_payloads(mime_formatter):
        try:
            from IPython.core.formatters import JSONFormatter

            mime_formatter = JSONFormatter(parent=display_formatter)
            display_formatter.formatters[REFUA_MIME_TYPE] = mime_formatter
        except Exception:
            return None
    return mime_formatter


def _register_formatters(ip: Optional["InteractiveShell"] = None) -> bool:
    """Register HTML formatters for Refua types with IPython.

    Parameters
    ----------
    ip : InteractiveShell, optional
        IPython shell instance. If None, attempts to get current instance.

    Returns
    -------
    bool
        True if registration was successful, False otherwise.
    """
    # Get IPython instance
    if ip is None:
        try:
            from IPython import get_ipython

            ip = get_ipython()
        except ImportError:
            return False

    if ip is None:
        return False

    # Get the HTML formatter
    display_formatter = getattr(ip, "display_formatter", None)
    if display_formatter is None:
        return False

    try:
        html_formatter = display_formatter.formatters["text/html"]
    except KeyError:
        return False
    mime_formatter = _get_mime_formatter(ip)

    # Avoid importing refua on activation when possible. This keeps activation
    # lightweight and prevents any model download side-effects during import.
    registered_html = _register_formatters_by_name(html_formatter, _REFUA_TYPE_REGISTRY)
    registered_mime = False
    if mime_formatter is not None:
        registered_mime = _register_formatters_by_name(
            mime_formatter, _REFUA_MIME_REGISTRY
        )
    if "refua" not in sys.modules and (registered_html or registered_mime):
        return True

    try:
        import refua
        import refua.unified as refua_unified
        from refua import Complex, MolProperties, Protein, SmallMolecule
        from refua.unified import FoldResult
    except ImportError as exc:
        raise ImportError(
            "refua-notebook requires the refua package. Install it with: pip install refua"
        ) from exc

    # Register formatters for each type
    html_formatter.for_type(MolProperties, _get_sm_repr_html)
    html_formatter.for_type(SmallMolecule, _get_sm_repr_html)
    html_formatter.for_type(Protein, _get_protein_repr_html)
    html_formatter.for_type(Complex, _get_complex_repr_html)
    html_formatter.for_type(FoldResult, _get_complex_repr_html)
    if mime_formatter is not None:
        mime_formatter.for_type(MolProperties, _get_sm_repr_mime)
        mime_formatter.for_type(SmallMolecule, _get_sm_repr_mime)
        mime_formatter.for_type(Protein, _get_protein_repr_mime)
        mime_formatter.for_type(Complex, _get_complex_repr_mime)
        mime_formatter.for_type(FoldResult, _get_complex_repr_mime)

    affinity_prediction_type = getattr(refua_unified, "AffinityPrediction", None)
    if affinity_prediction_type is None:
        affinity_prediction_type = getattr(refua, "AffinityPrediction", None)
    if affinity_prediction_type is not None:
        html_formatter.for_type(affinity_prediction_type, _get_affinity_repr_html)
        if mime_formatter is not None:
            mime_formatter.for_type(affinity_prediction_type, _get_affinity_repr_mime)

    # Also register for FoldedComplex if it exists
    if hasattr(refua, "FoldedComplex"):
        html_formatter.for_type(refua.FoldedComplex, _get_complex_repr_html)
        if mime_formatter is not None:
            mime_formatter.for_type(refua.FoldedComplex, _get_complex_repr_mime)

    return True


def _unregister_formatters(ip: Optional["InteractiveShell"] = None) -> bool:
    """Unregister HTML formatters for Refua types.

    Parameters
    ----------
    ip : InteractiveShell, optional
        IPython shell instance.

    Returns
    -------
    bool
        True if unregistration was successful.
    """
    if ip is None:
        try:
            from IPython import get_ipython

            ip = get_ipython()
        except ImportError:
            return False

    if ip is None:
        return False

    display_formatter = getattr(ip, "display_formatter", None)
    if display_formatter is None:
        return False

    try:
        html_formatter = display_formatter.formatters["text/html"]
    except KeyError:
        return False
    mime_formatter = _get_mime_formatter(ip)

    removed_by_name = _unregister_formatters_by_name(
        html_formatter, _REFUA_TYPE_REGISTRY
    )
    _unregister_formatters_by_name(mime_formatter, _REFUA_MIME_REGISTRY)

    try:
        import refua
        import refua.unified as refua_unified
        from refua import Complex, MolProperties, Protein, SmallMolecule
        from refua.unified import FoldResult
    except ImportError as exc:
        if removed_by_name:
            return True
        raise ImportError(
            "refua-notebook requires the refua package. Install it with: pip install refua"
        ) from exc

    # Remove formatters
    for type_class in [MolProperties, SmallMolecule, Protein, Complex, FoldResult]:
        try:
            html_formatter.pop(type_class, None)
        except Exception:
            pass
        if mime_formatter is not None:
            try:
                mime_formatter.pop(type_class, None)
            except Exception:
                pass

    affinity_prediction_type = getattr(refua_unified, "AffinityPrediction", None)
    if affinity_prediction_type is None:
        affinity_prediction_type = getattr(refua, "AffinityPrediction", None)
    if affinity_prediction_type is not None:
        try:
            html_formatter.pop(affinity_prediction_type, None)
        except Exception:
            pass
        if mime_formatter is not None:
            try:
                mime_formatter.pop(affinity_prediction_type, None)
            except Exception:
                pass

    if hasattr(refua, "FoldedComplex"):
        try:
            html_formatter.pop(refua.FoldedComplex, None)
        except Exception:
            pass
        if mime_formatter is not None:
            try:
                mime_formatter.pop(refua.FoldedComplex, None)
            except Exception:
                pass

    return True


def activate(ip: Optional["InteractiveShell"] = None) -> bool:
    """Activate Refua notebook extension.

    This registers HTML representations for Refua objects so they display
    automatically as interactive widgets in Jupyter notebooks.

    Parameters
    ----------
    ip : InteractiveShell, optional
        IPython shell instance. If None, uses current instance.

    Returns
    -------
    bool
        True if activation was successful.

    Examples
    --------
    >>> import refua_notebook
    >>> refua_notebook.activate()
    True
    >>>
    >>> from refua import SM
    >>> SM("CCO")  # Now displays as 2D structure widget
    """
    global _extension_active

    if _extension_active:
        return True

    success = _register_formatters(ip)
    if success:
        _extension_active = True

    return success


def deactivate(ip: Optional["InteractiveShell"] = None) -> bool:
    """Deactivate Refua notebook extension.

    This removes the HTML representations for Refua objects.

    Parameters
    ----------
    ip : InteractiveShell, optional
        IPython shell instance.

    Returns
    -------
    bool
        True if deactivation was successful.
    """
    global _extension_active

    success = _unregister_formatters(ip)
    _extension_active = False

    return success


def is_active() -> bool:
    """Check if the Refua notebook extension is active.

    Returns
    -------
    bool
        True if extension is currently active.
    """
    return _extension_active


def load_ipython_extension(ip: "InteractiveShell") -> None:
    """Load the Refua notebook extension.

    This is called by IPython when using %load_ext refua_notebook.

    Parameters
    ----------
    ip : InteractiveShell
        The IPython shell instance.
    """
    success = activate(ip)
    if not success:
        raise RuntimeError(
            "Refua notebook extension could not register HTML formatters. "
            "Ensure IPython is available and try again."
        )
    print(
        "Refua notebook extension loaded. Refua objects will now display as interactive widgets."
    )


def unload_ipython_extension(ip: "InteractiveShell") -> None:
    """Unload the Refua notebook extension.

    This is called by IPython when the extension is unloaded.

    Parameters
    ----------
    ip : InteractiveShell
        The IPython shell instance.
    """
    deactivate(ip)
    print("Refua notebook extension unloaded.")
