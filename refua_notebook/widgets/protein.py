"""Protein visualization widget for Jupyter notebooks.

This module provides the ProteinView class for displaying protein information
and 3D structures inline in Jupyter notebooks.
"""

from __future__ import annotations

import html
import uuid
from types import ModuleType
from typing import Any, Optional

from refua_notebook.mime import REFUA_MIME_TYPE

_ipython_display_module: ModuleType | None
try:
    import IPython.display as _ipython_display_module
except ImportError:
    _ipython_display_module = None


class ProteinView:
    """Jupyter widget for displaying protein information and 3D structures.

    This class generates an HTML representation of a protein that can be
    displayed inline in Jupyter notebooks. If structure data is available,
    it shows an interactive 3D viewer.

    Parameters
    ----------
    sequence : str, optional
        Amino acid sequence of the protein.
    name : str, optional
        Name or identifier of the protein.
    bcif_data : bytes, optional
        Binary CIF structure data.
    pdb_data : str, optional
        PDB format structure data.
    width : int, optional
        Width of the viewer in pixels. Default 600.
    height : int, optional
        Height of the viewer in pixels. Default 400.
    show_structure : bool, optional
        Whether to show 3D structure if available. Default True.
    show_sequence : bool, optional
        Whether to show the sequence. Default True.
    sequence_display_length : int, optional
        Maximum length of sequence to display. Default 60.

    Notes
    -----
    Internal helper used by the Refua notebook extension.
    """

    def __init__(
        self,
        sequence: Optional[str] = None,
        name: Optional[str] = None,
        bcif_data: Optional[bytes] = None,
        pdb_data: Optional[str] = None,
        width: int = 600,
        height: int = 400,
        show_structure: bool = True,
        show_sequence: bool = True,
        sequence_display_length: int = 60,
    ):
        self.sequence = sequence.strip() if sequence else None
        self.name = name
        self.bcif_data = bcif_data
        self.pdb_data = pdb_data
        self.width = max(width, 300)
        self.height = max(height, 200)
        self.show_structure = show_structure
        self.show_sequence = show_sequence
        self.sequence_display_length = sequence_display_length
        self._element_id = f"protein-{uuid.uuid4().hex[:8]}"

    @property
    def has_structure(self) -> bool:
        """Check if structure data is available."""
        return self.bcif_data is not None or self.pdb_data is not None

    @property
    def sequence_length(self) -> int:
        """Get the length of the protein sequence."""
        return len(self.sequence) if self.sequence else 0

    def _format_sequence(self) -> str:
        """Format sequence for display with truncation if needed."""
        if not self.sequence:
            return ""

        if len(self.sequence) <= self.sequence_display_length:
            return self.sequence

        half = self.sequence_display_length // 2
        return f"{self.sequence[:half]}...{self.sequence[-half:]}"

    def _render_html(self, include_scripts: bool = True) -> str:
        """Render the protein view as HTML."""
        element_id = html.escape(self._element_id)
        escaped_name = html.escape(self.name or "Protein")

        html_parts = []

        # Show 3D structure if available
        if self.show_structure and self.has_structure:
            from refua_notebook.widgets.molstar import MolstarView

            viewer = MolstarView(
                bcif_data=self.bcif_data,
                pdb_data=self.pdb_data,
                width=self.width,
                height=self.height,
                show_controls=True,
            )
            html_parts.append(viewer.to_html(include_scripts=include_scripts))

        # Show protein info card
        seq_display = html.escape(self._format_sequence()) if self.show_sequence else ""
        seq_len = self.sequence_length

        has_structure_badge = ""
        if self.has_structure:
            has_structure_badge = '<span style="background: #dcfce7; color: #166534; font-size: 10px; padding: 2px 6px; border-radius: 4px; margin-left: 8px;">3D Structure</span>'

        info_html = f"""
<div id="{element_id}" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 8px 0; padding: 12px; background: linear-gradient(135deg, #f8fafc, #f1f5f9);
            border: 1px solid #e2e8f0; border-radius: 8px; max-width: {self.width}px;">
    <div style="font-size: 14px; font-weight: 600; margin-bottom: 8px; color: #1e293b;">
        {escaped_name}{has_structure_badge}
    </div>
    {f'<div style="font-size: 12px; color: #64748b; margin-bottom: 8px;"><strong>Length:</strong> {seq_len} amino acids</div>' if seq_len > 0 else ''}
    {f'<div style="font-family: monospace; font-size: 11px; color: #475569; word-break: break-all; background: #fff; padding: 8px; border-radius: 4px; border: 1px solid #e2e8f0;">{seq_display}</div>' if seq_display else ''}
</div>
"""
        html_parts.append(info_html)

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
        """Display the protein view in the notebook."""
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
    def from_refua_protein(
        cls,
        protein: Any,
        **kwargs,
    ) -> "ProteinView":
        """Create a ProteinView from a Refua Protein object.

        Parameters
        ----------
        protein : refua.Protein
            A Refua Protein object.
        **kwargs
            Additional arguments passed to ProteinView constructor.

        Returns
        -------
        ProteinView
            A view instance configured with the protein data.
        """
        sequence = None
        if hasattr(protein, "sequence"):
            sequence = protein.sequence
        elif hasattr(protein, "seq"):
            sequence = protein.seq

        name = None
        if hasattr(protein, "name"):
            name = protein.name
        elif hasattr(protein, "ids"):
            ids = protein.ids
            if isinstance(ids, str):
                name = ids
            elif isinstance(ids, (list, tuple)) and ids:
                name = str(ids[0])
        elif hasattr(protein, "id"):
            name = protein.id

        bcif_data = None
        pdb_data = None

        if hasattr(protein, "to_bcif"):
            try:
                bcif_data = protein.to_bcif()
            except Exception:
                pass

        if bcif_data is None and hasattr(protein, "to_pdb"):
            try:
                pdb_data = protein.to_pdb()
            except Exception:
                pass

        return cls(
            sequence=sequence,
            name=name,
            bcif_data=bcif_data,
            pdb_data=pdb_data,
            **kwargs,
        )

    @classmethod
    def from_sequence(
        cls,
        sequence: str,
        name: Optional[str] = None,
        **kwargs,
    ) -> "ProteinView":
        """Create a ProteinView from an amino acid sequence.

        Parameters
        ----------
        sequence : str
            Amino acid sequence.
        name : str, optional
            Name for the protein.
        **kwargs
            Additional arguments passed to ProteinView constructor.

        Returns
        -------
        ProteinView
            A view instance with the sequence.
        """
        return cls(sequence=sequence, name=name, **kwargs)
