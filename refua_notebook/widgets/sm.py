"""Small molecule (SM) visualization widget for Jupyter notebooks.

This module provides the SMView class for displaying small molecule information
including 2D structure drawings and ADMET properties inline in Jupyter notebooks.
"""

from __future__ import annotations

import html
import uuid
from types import ModuleType
from typing import Any, Dict, Mapping, Optional, Sequence

from refua_notebook.mime import REFUA_MIME_TYPE

_ipython_display_module: ModuleType | None
try:
    import IPython.display as _ipython_display_module
except ImportError:
    _ipython_display_module = None


class SMView:
    """Jupyter widget for displaying small molecule (ligand) information.

    This class generates an HTML representation of a small molecule that can be
    displayed inline in Jupyter notebooks. It shows the 2D structure from SMILES
    and optionally displays ADMET or other molecular properties.

    Parameters
    ----------
    smiles : str
        SMILES string representing the molecular structure.
    name : str, optional
        Name or identifier of the molecule.
    properties : dict, optional
        Dictionary of molecular properties (e.g., ADMET predictions).
    width : int, optional
        Width of the structure drawing in pixels. Default 400.
    height : int, optional
        Height of the structure drawing in pixels. Default 300.
    theme : str, optional
        Color theme: "light" or "dark". Default "light".
    show_structure : bool, optional
        Whether to show 2D structure. Default True.
    show_properties : bool, optional
        Whether to show properties table. Default True.
    show_smiles : bool, optional
        Whether to show SMILES string. Default True.
    layout : str, optional
        Layout of structure and properties: "horizontal" or "vertical". Default "horizontal".

    Notes
    -----
    Internal helper used by the Refua notebook extension.
    """

    def __init__(
        self,
        smiles: str,
        name: Optional[str] = None,
        properties: Optional[Mapping[str, Any]] = None,
        width: int = 400,
        height: int = 300,
        theme: str = "light",
        show_structure: bool = True,
        show_properties: bool = True,
        show_smiles: bool = True,
        layout: str = "horizontal",
    ):
        self.smiles = smiles.strip()
        self.name = name
        self.properties = dict(properties) if properties else {}
        self.width = max(width, 200)
        self.height = max(height, 150)
        self.theme = theme if theme in ("light", "dark") else "light"
        self.show_structure = show_structure
        self.show_properties = show_properties
        self.show_smiles = show_smiles
        self.layout = layout if layout in ("horizontal", "vertical") else "horizontal"
        self._element_id = f"smview-{uuid.uuid4().hex[:8]}"

    def _render_html(self, include_scripts: bool = True) -> str:
        """Render the small molecule view as HTML."""
        element_id = html.escape(self._element_id)
        escaped_smiles = html.escape(self.smiles)

        html_parts = []

        # Start container
        flex_direction = "column" if self.layout == "vertical" else "row"
        html_parts.append(f"""
<div id="{element_id}" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex; flex-direction: {flex_direction}; gap: 16px; margin: 8px 0;
            flex-wrap: wrap; align-items: flex-start;">
""")

        # Show 2D structure
        if self.show_structure:
            from refua_notebook.widgets.smiles import SmilesView

            structure_view = SmilesView(
                self.smiles,
                title=self.name,
                width=self.width,
                height=self.height,
                theme=self.theme,
            )
            html_parts.append(
                f'<div style="flex-shrink: 0;">{structure_view.to_html(include_scripts=include_scripts)}</div>'
            )

        # Show properties if available
        if self.show_properties and self.properties:
            from refua_notebook.widgets.admet import ADMETView

            props_view = ADMETView(
                self.properties,
                title=f"{self.name} Properties" if self.name else "Molecule Properties",
                compact=True,
                show_categories=True,
            )
            html_parts.append(
                f'<div style="flex-grow: 1; min-width: 300px;">{props_view.to_html()}</div>'
            )

        # Close container
        html_parts.append("</div>")

        # Show SMILES string below
        if self.show_smiles and not self.show_structure:
            # Only show SMILES separately if structure is not shown (structure already shows it)
            smiles_bg = "#374151" if self.theme == "dark" else "#f3f4f6"
            smiles_color = "#d1d5db" if self.theme == "dark" else "#4b5563"
            html_parts.append(f"""
<div style="font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; color: {smiles_color};
            background: {smiles_bg}; padding: 8px 12px; border-radius: 4px; margin-top: 8px;
            word-break: break-all; max-width: {self.width + 300}px;">
    <strong>SMILES:</strong> {escaped_smiles}
</div>
""")

        return "\n".join(html_parts)

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
        """Display the small molecule view in the notebook."""
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
    def from_refua_sm(
        cls,
        sm: Any,
        **kwargs,
    ) -> "SMView":
        """Create an SMView from a Refua SM object.

        Parameters
        ----------
        sm : refua.SM
            A Refua small molecule object.
        **kwargs
            Additional arguments passed to SMView constructor.

        Returns
        -------
        SMView
            A view instance configured with the molecule data.
        """
        # Get SMILES
        smiles = None
        if hasattr(sm, "smiles"):
            smiles = sm.smiles
        elif hasattr(sm, "to_smiles"):
            smiles = sm.to_smiles()
        elif hasattr(sm, "__str__"):
            smiles = str(sm)

        if not smiles:
            raise ValueError("Could not extract SMILES from SM object")

        # Get name
        name = None
        if hasattr(sm, "name"):
            name = sm.name
        elif hasattr(sm, "id"):
            name = sm.id

        # Get properties
        properties = None
        if hasattr(sm, "to_dict"):
            try:
                properties = sm.to_dict()
            except Exception:
                pass
        elif hasattr(sm, "properties"):
            properties = sm.properties
        elif hasattr(sm, "admet"):
            properties = sm.admet

        return cls(
            smiles=smiles,
            name=name,
            properties=properties,
            **kwargs,
        )

    @classmethod
    def from_smiles(
        cls,
        smiles: str,
        name: Optional[str] = None,
        **kwargs,
    ) -> "SMView":
        """Create an SMView from a SMILES string.

        Parameters
        ----------
        smiles : str
            SMILES string.
        name : str, optional
            Name for the molecule.
        **kwargs
            Additional arguments passed to SMView constructor.

        Returns
        -------
        SMView
            A view instance with the SMILES.
        """
        return cls(smiles=smiles, name=name, **kwargs)


class SMGridView:
    """Grid view for displaying multiple small molecules.

    Parameters
    ----------
    molecules : list
        List of molecules. Each can be:
        - A SMILES string
        - A dict with 'smiles' and optional 'name', 'properties' keys
        - A refua.SM object
    columns : int, optional
        Number of columns in the grid. Default 3.
    width : int, optional
        Width of each structure. Default 280.
    height : int, optional
        Height of each structure. Default 210.
    show_properties : bool, optional
        Whether to show properties. Default False (for compact grid).
    **kwargs
        Additional arguments passed to each SMView.
    """

    def __init__(
        self,
        molecules: Sequence[Any],
        columns: int = 3,
        width: int = 280,
        height: int = 210,
        show_properties: bool = False,
        **kwargs,
    ):
        self.molecules = list(molecules)
        self.columns = max(columns, 1)
        self.width = width
        self.height = height
        self.show_properties = show_properties
        self.kwargs = kwargs
        self._grid_id = f"smgrid-{uuid.uuid4().hex[:8]}"

    def _parse_molecule(self, mol: Any) -> Dict[str, Any]:
        """Parse a molecule into smiles, name, and properties."""
        if isinstance(mol, str):
            return {"smiles": mol, "name": None, "properties": None}

        if isinstance(mol, dict):
            return {
                "smiles": mol.get("smiles", ""),
                "name": mol.get("name") or mol.get("title"),
                "properties": mol.get("properties") or mol.get("admet"),
            }

        # Assume it's a refua.SM-like object
        smiles = getattr(mol, "smiles", None) or str(mol)
        name = getattr(mol, "name", None) or getattr(mol, "id", None)
        properties = None
        if hasattr(mol, "to_dict"):
            try:
                properties = mol.to_dict()
            except Exception:
                pass
        elif hasattr(mol, "properties"):
            properties = mol.properties

        return {"smiles": smiles, "name": name, "properties": properties}

    def _render_html(self) -> str:
        """Render the grid as HTML."""
        grid_id = html.escape(self._grid_id)

        items_html = []
        for mol in self.molecules:
            parsed = self._parse_molecule(mol)
            if not parsed["smiles"]:
                continue

            view = SMView(
                smiles=parsed["smiles"],
                name=parsed["name"],
                properties=parsed["properties"] if self.show_properties else None,
                width=self.width,
                height=self.height,
                show_properties=self.show_properties,
                layout="vertical",
                **self.kwargs,
            )
            items_html.append(f'<div class="sm-grid-item">{view.to_html()}</div>')

        return f"""
<style>
#{grid_id} {{
    display: grid;
    grid-template-columns: repeat({self.columns}, 1fr);
    gap: 16px;
    margin: 16px 0;
}}
#{grid_id} .sm-grid-item {{
    display: flex;
    justify-content: center;
}}
@media (max-width: 768px) {{
    #{grid_id} {{
        grid-template-columns: repeat(auto-fit, minmax({self.width + 40}px, 1fr));
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
