"""SMILES structure drawing widget for Jupyter notebooks.

This module provides the SmilesView class for displaying 2D chemical
structure diagrams from SMILES strings inline in Jupyter notebooks.
"""

from __future__ import annotations

import html
import json
import uuid
from types import ModuleType
from typing import Optional

from refua_notebook.mime import REFUA_MIME_TYPE

_ipython_display_module: ModuleType | None
try:
    import IPython.display as _ipython_display_module
except ImportError:
    _ipython_display_module = None


# CDN URL for SmilesDrawer
SMILESDRAWER_CDN = (
    "https://cdn.jsdelivr.net/npm/smiles-drawer@2.1.5/dist/smiles-drawer.min.js"
)


def _safe_json_for_html(value: str) -> str:
    """Encode value as JSON that's safe to embed in HTML script tags.

    This escapes <, >, and & characters to prevent breaking out of
    script tags or causing HTML parsing issues.
    """
    encoded = json.dumps(value)
    # Escape characters that could break out of script context
    encoded = encoded.replace("<", "\\u003c")
    encoded = encoded.replace(">", "\\u003e")
    encoded = encoded.replace("&", "\\u0026")
    return encoded


class SmilesView:
    """Jupyter widget for displaying 2D chemical structures from SMILES.

    This class generates a 2D structure diagram from a SMILES string that
    can be displayed inline in Jupyter notebooks using the SmilesDrawer
    library.

    Parameters
    ----------
    smiles : str
        SMILES string representing the molecular structure.
    width : int, optional
        Width of the canvas in pixels. Default 400.
    height : int, optional
        Height of the canvas in pixels. Default 300.
    title : str, optional
        Title to display above the structure.
    theme : str, optional
        Color theme: "light" or "dark". Default "light".
    show_hydrogens : bool, optional
        Whether to show explicit hydrogens. Default False.
    use_svg : bool, optional
        If True, render as SVG instead of canvas. Default True (better quality).

    Notes
    -----
    Internal helper used by the Refua notebook extension.
    """

    def __init__(
        self,
        smiles: str,
        width: int = 400,
        height: int = 300,
        title: Optional[str] = None,
        theme: str = "light",
        show_hydrogens: bool = False,
        use_svg: bool = True,
    ):
        self.smiles = smiles.strip()
        self.width = max(width, 200)
        self.height = max(height, 150)
        self.title = title
        self.theme = theme if theme in ("light", "dark") else "light"
        self.show_hydrogens = show_hydrogens
        self.use_svg = use_svg
        self._element_id = f"smiles-{uuid.uuid4().hex[:8]}"

    def _render_html(self, include_scripts: bool = True) -> str:
        """Render the SMILES viewer as HTML."""
        element_id = html.escape(self._element_id)
        escaped_smiles = html.escape(self.smiles)
        escaped_title = html.escape(self.title or "")

        # Use JSON encoding for safe JavaScript string (prevents XSS)
        # _safe_json_for_html escapes <, >, & to prevent script injection
        smiles_json = _safe_json_for_html(self.smiles)
        theme_json = _safe_json_for_html(self.theme)

        title_html = ""
        if self.title:
            title_html = f"""
    <div class="smiles-title">{escaped_title}</div>
"""

        element_tag = "svg" if self.use_svg else "canvas"
        drawer_class = "SvgDrawer" if self.use_svg else "Drawer"

        # Additional attributes for SVG
        if self.use_svg:
            element_attrs = f'viewBox="0 0 {self.width} {self.height}" preserveAspectRatio="xMidYMid meet"'
        else:
            element_attrs = ""

        explicit_hydrogens_js = "true" if self.show_hydrogens else "false"

        script_block = ""
        if include_scripts:
            script_block = f"""
<script>
(function() {{
    function loadSmilesDrawer(callback) {{
        if (typeof SmilesDrawer !== 'undefined') {{
            callback();
            return;
        }}
        var script = document.createElement('script');
        script.src = '{SMILESDRAWER_CDN}';
        script.onload = callback;
        script.onerror = function() {{
            document.getElementById('{element_id}-error').textContent = 'Failed to load SmilesDrawer';
            document.getElementById('{element_id}-error').style.display = 'block';
        }};
        document.head.appendChild(script);
    }}

    function renderSmiles() {{
        var element = document.getElementById('{element_id}');
        var errorEl = document.getElementById('{element_id}-error');
        var smiles = {smiles_json};
        var theme = {theme_json};

        var options = {{
            width: {self.width},
            height: {self.height},
            padding: 12,
            explicitHydrogens: {explicit_hydrogens_js},
            compactDrawing: false
        }};

        try {{
            SmilesDrawer.parse(
                smiles,
                function(tree) {{
                    try {{
                        var drawer = new SmilesDrawer.{drawer_class}(options);
                        drawer.draw(tree, element, theme);
                    }} catch (drawErr) {{
                        console.error('Failed to draw SMILES:', drawErr);
                        errorEl.textContent = 'Failed to render structure';
                        errorEl.style.display = 'block';
                    }}
                }},
                function(parseErr) {{
                    console.error('Failed to parse SMILES:', parseErr);
                    errorEl.textContent = 'Invalid SMILES: ' + parseErr;
                    errorEl.style.display = 'block';
                }}
            );
        }} catch (err) {{
            console.error('SmilesDrawer error:', err);
            errorEl.textContent = 'Error rendering structure';
            errorEl.style.display = 'block';
        }}
    }}

    loadSmilesDrawer(renderSmiles);
}})();
</script>
"""

        data_attrs = (
            f'data-refua-smiles="1" '
            f'data-theme="{html.escape(self.theme)}" '
            f'data-explicit-hydrogens="{str(self.show_hydrogens).lower()}" '
            f'data-width="{self.width}" '
            f'data-height="{self.height}"'
        )

        return f"""
<style>
#{element_id}-container {{
    display: inline-block;
    background: {"#1e293b" if self.theme == "dark" else "#ffffff"};
    border: 1px solid {"#374151" if self.theme == "dark" else "#e5e7eb"};
    border-radius: 8px;
    padding: 12px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}}
#{element_id}-container .smiles-title {{
    font-size: 14px;
    font-weight: 600;
    color: {"#f8fafc" if self.theme == "dark" else "#374151"};
    margin-bottom: 8px;
    text-align: center;
}}
#{element_id} {{
    display: block;
    width: {self.width}px;
    height: {self.height}px;
}}
#{element_id}-error {{
    display: none;
    color: #ef4444;
    font-size: 12px;
    text-align: center;
    padding: 8px;
}}
#{element_id}-smiles {{
    font-size: 11px;
    color: {"#94a3b8" if self.theme == "dark" else "#6b7280"};
    font-family: 'Consolas', 'Monaco', monospace;
    margin-top: 8px;
    text-align: center;
    word-break: break-all;
    max-width: {self.width}px;
}}
</style>

<div id="{element_id}-container">
{title_html}
    <{element_tag} id="{element_id}" {element_attrs}
        width="{self.width}" height="{self.height}"
        data-smiles="{escaped_smiles}" {data_attrs}></{element_tag}>
    <div id="{element_id}-error"></div>
    <div id="{element_id}-smiles">{escaped_smiles}</div>
</div>
{script_block}
"""

    def _repr_html_(self) -> str:
        """IPython HTML representation for inline display."""
        return self._render_html()

    def _repr_mimebundle_(self, include=None, exclude=None):
        """Provide a custom MIME bundle for JupyterLab rendering."""
        return {
            "text/html": self._render_html(),
            REFUA_MIME_TYPE: {"html": self._render_html(include_scripts=False)},
        }

    def display(self) -> None:
        """Display the SMILES structure in the notebook."""
        if _ipython_display_module is not None:
            _ipython_display_module.display(
                _ipython_display_module.HTML(self._render_html())
            )
        else:
            print(self._render_html())

    def to_html(self, include_scripts: bool = True) -> str:
        """Return the HTML representation as a string."""
        return self._render_html(include_scripts=include_scripts)

    @classmethod
    def from_smiles_list(
        cls,
        smiles_list: list[str],
        titles: Optional[list[Optional[str]]] = None,
        columns: int = 3,
        **kwargs,
    ) -> "SmilesGridView":
        """Create a grid view of multiple SMILES structures.

        Parameters
        ----------
        smiles_list : list[str]
            List of SMILES strings.
        titles : list[str], optional
            Titles for each structure.
        columns : int, optional
            Number of columns in the grid. Default 3.
        **kwargs
            Additional arguments passed to each SmilesView.

        Returns
        -------
        SmilesGridView
            A grid view containing multiple structures.
        """
        return SmilesGridView(smiles_list, titles=titles, columns=columns, **kwargs)


class SmilesGridView:
    """Grid view for displaying multiple SMILES structures.

    Parameters
    ----------
    smiles_list : list[str]
        List of SMILES strings.
    titles : list[str], optional
        Titles for each structure.
    columns : int, optional
        Number of columns in the grid. Default 3.
    width : int, optional
        Width of each structure. Default 280.
    height : int, optional
        Height of each structure. Default 210.
    **kwargs
        Additional arguments passed to each SmilesView.
    """

    def __init__(
        self,
        smiles_list: list[str],
        titles: Optional[list[Optional[str]]] = None,
        columns: int = 3,
        width: int = 280,
        height: int = 210,
        **kwargs,
    ):
        self.smiles_list = smiles_list
        self.titles = titles or [None] * len(smiles_list)
        self.columns = max(columns, 1)
        self.width = width
        self.height = height
        self.kwargs = kwargs
        self._grid_id = f"smiles-grid-{uuid.uuid4().hex[:8]}"

    def _render_html(self) -> str:
        """Render the grid as HTML."""
        grid_id = html.escape(self._grid_id)

        items_html = []
        for smiles, title in zip(self.smiles_list, self.titles):
            view = SmilesView(
                smiles,
                title=title,
                width=self.width,
                height=self.height,
                **self.kwargs,
            )
            items_html.append(
                f'<div class="smiles-grid-item">{view._render_html()}</div>'
            )

        return f"""
<style>
#{grid_id} {{
    display: grid;
    grid-template-columns: repeat({self.columns}, 1fr);
    gap: 16px;
    margin: 16px 0;
}}
#{grid_id} .smiles-grid-item {{
    display: flex;
    justify-content: center;
}}
@media (max-width: 768px) {{
    #{grid_id} {{
        grid-template-columns: repeat(auto-fit, minmax({self.width + 24}px, 1fr));
    }}
}}
</style>

<div id="{grid_id}">
    {"".join(items_html)}
</div>
"""

    def _repr_html_(self) -> str:
        """IPython HTML representation for inline display."""
        return self._render_html()

    def display(self) -> None:
        """Display the grid in the notebook."""
        if _ipython_display_module is not None:
            _ipython_display_module.display(
                _ipython_display_module.HTML(self._render_html())
            )
        else:
            print(self._render_html())

    def to_html(self) -> str:
        """Return the HTML representation as a string."""
        return self._render_html()
