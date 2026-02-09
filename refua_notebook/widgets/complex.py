"""Complex visualization widget for Jupyter notebooks.

This module provides the ComplexView class for displaying molecular complexes
(protein-ligand, protein-protein, etc.) inline in Jupyter notebooks.
"""

from __future__ import annotations

import html
import uuid
from dataclasses import asdict, is_dataclass
from types import ModuleType
from typing import Any, Mapping, Optional, Sequence

from refua_notebook.mime import REFUA_MIME_TYPE

_ipython_display_module: ModuleType | None
try:
    import IPython.display as _ipython_display_module
except ImportError:
    _ipython_display_module = None


class ComplexView:
    """Jupyter widget for displaying molecular complexes.

    This class generates an HTML representation of a molecular complex that can be
    displayed inline in Jupyter notebooks. The visual layout is intentionally
    minimal and viewer-first.

    Parameters
    ----------
    bcif_data : bytes, optional
        Binary CIF structure data from folding.
    pdb_data : str, optional
        PDB format structure data.
    name : str, optional
        Name of the complex.
    ligand_name : str, optional
        Name of the ligand for highlighting in 3D viewer.
    affinity : dict, optional
        Binding affinity predictions.
    components : list, optional
        List of component descriptions for unfolded complexes.
        Each component can be a dict with 'type', 'sequence', 'smiles', 'name',
        and optional 'properties' or 'admet' keys.
    width : int, optional
        Width of the viewer in pixels. Default 700.
    height : int, optional
        Height of the viewer in pixels. Default 500.
    show_controls : bool, optional
        Whether to show Mol* viewer controls. Default False.
    show_affinity : bool, optional
        Retained for API compatibility.

    Notes
    -----
    Internal helper used by the Refua notebook extension.
    """

    def __init__(
        self,
        bcif_data: Optional[bytes] = None,
        pdb_data: Optional[str] = None,
        name: Optional[str] = None,
        ligand_name: Optional[str] = None,
        affinity: Optional[Mapping[str, Any]] = None,
        components: Optional[Sequence[Mapping[str, Any]]] = None,
        width: int = 700,
        height: int = 500,
        show_controls: bool = False,
        show_affinity: bool = True,
    ):
        self.bcif_data = bcif_data
        self.pdb_data = pdb_data
        self.name = name
        self.ligand_name = ligand_name
        self.affinity = dict(affinity) if affinity else {}
        self.components = list(components) if components else []
        self.width = max(width, 400)
        self.height = max(height, 300)
        self.show_controls = show_controls
        self.show_affinity = show_affinity
        self._element_id = f"complex-{uuid.uuid4().hex[:8]}"

    @property
    def is_folded(self) -> bool:
        """Check if the complex has structure data (is folded)."""
        return self.bcif_data is not None or self.pdb_data is not None

    @staticmethod
    def _coerce_properties(properties: Any) -> Optional[Mapping[str, Any]]:
        if properties is None:
            return None
        if isinstance(properties, Mapping):
            return dict(properties)
        if is_dataclass(properties) and not isinstance(properties, type):
            try:
                return {
                    k: v
                    for k, v in asdict(properties).items()
                    if not str(k).startswith("_")
                }
            except Exception:
                pass
        if hasattr(properties, "__dict__") and properties.__dict__:
            return {
                k: v for k, v in properties.__dict__.items() if not k.startswith("_")
            }
        if hasattr(properties, "__slots__"):
            slots = properties.__slots__
            if isinstance(slots, str):
                slots = (slots,)
            data = {}
            for key in slots:
                if str(key).startswith("_"):
                    continue
                if hasattr(properties, key):
                    data[key] = getattr(properties, key)
            if data:
                return data
        return None

    @staticmethod
    def _extract_admet_properties(properties: Any) -> Optional[Mapping[str, Any]]:
        props = ComplexView._coerce_properties(properties)
        if not props:
            return None
        predictions = props.get("predictions")
        if isinstance(predictions, Mapping):
            merged = dict(predictions)
            for key in ("admet_score", "safety_score", "adme_score", "rdkit_score"):
                if key in props:
                    merged[key] = props[key]
            return merged
        return props

    def _format_affinity_value(self, key: str, value: Any) -> str:
        """Format an affinity value for display."""
        if isinstance(value, float):
            if "probability" in key.lower() or "prob" in key.lower():
                return f"{value:.1%}"
            if "ic50" in key.lower() or "value" in key.lower():
                return f"{value:.2f}"
            return f"{value:.3f}"
        return str(value)

    def _split_components(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        ligands: list[dict[str, Any]] = []
        proteins: list[dict[str, Any]] = []
        others: list[dict[str, Any]] = []

        for comp in self.components:
            if isinstance(comp, Mapping):
                comp_type = str(comp.get("type", "unknown")).lower()
                name = comp.get("name") or comp.get("id") or comp_type.title()
                smiles = comp.get("smiles") or comp.get("smile")
                if smiles is not None and not isinstance(smiles, str):
                    smiles = str(smiles)
                sequence = comp.get("sequence") or comp.get("seq")
                if sequence is not None and not isinstance(sequence, str):
                    sequence = str(sequence)
                properties = self._extract_admet_properties(
                    comp.get("properties") or comp.get("admet")
                )
            else:
                comp_type = type(comp).__name__.lower()
                name = str(comp)
                smiles = None
                sequence = None
                properties = None

            is_ligand = comp_type in (
                "ligand",
                "sm",
                "small_molecule",
                "small molecule",
            ) or bool(smiles)
            is_protein = comp_type == "protein" or bool(sequence)

            if is_ligand and not is_protein:
                ligands.append(
                    {
                        "type": "ligand",
                        "name": name,
                        "smiles": smiles,
                        "properties": properties,
                    }
                )
            elif is_protein:
                proteins.append(
                    {
                        "type": "protein",
                        "name": name,
                        "sequence": sequence or "",
                    }
                )
            else:
                others.append(
                    {
                        "type": comp_type or "other",
                        "name": name,
                    }
                )

        return ligands, proteins, others

    def _collect_admet_items(
        self, ligands: Sequence[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for ligand in ligands:
            properties = self._coerce_properties(ligand.get("properties"))
            if properties:
                items.append(
                    {
                        "name": ligand.get("name") or "Ligand",
                        "smiles": ligand.get("smiles"),
                        "properties": properties,
                    }
                )
        return items

    def _render_header_html(
        self,
        ligands: Sequence[Mapping[str, Any]],
        proteins: Sequence[Mapping[str, Any]],
        others: Sequence[Mapping[str, Any]],
        admet_items: Sequence[Mapping[str, Any]],
    ) -> str:
        escaped_name = html.escape(self.name or "Complex")
        status_label = "Folded" if self.is_folded else "Not Folded"
        status_class = "status-ready" if self.is_folded else "status-pending"

        summary_bits = []
        if proteins:
            summary_bits.append(
                f"{len(proteins)} protein{'s' if len(proteins) != 1 else ''}"
            )
        if ligands:
            summary_bits.append(
                f"{len(ligands)} ligand{'s' if len(ligands) != 1 else ''}"
            )
        if others:
            summary_bits.append(
                f"{len(others)} component{'s' if len(others) != 1 else ''}"
            )
        if self.show_affinity and self.affinity:
            summary_bits.append("affinity computed")
        if admet_items:
            summary_bits.append(
                f"ADMET for {len(admet_items)} ligand{'s' if len(admet_items) != 1 else ''}"
            )
        if self.is_folded:
            summary_bits.append("structure ready")

        summary_text = (
            " | ".join(summary_bits) if summary_bits else "No components detected"
        )
        escaped_summary = html.escape(summary_text)

        hint_html = ""
        if not self.is_folded:
            hint_html = (
                '<div class="complex-hint">'
                "Call <code>.fold()</code> to generate 3D structure and binding affinity."
                "</div>"
            )

        return f"""
<div class="complex-header">
    <div class="complex-title-row">
        <div class="complex-title">{escaped_name}</div>
        <span class="complex-status {status_class}">{status_label}</span>
    </div>
    <div class="complex-summary">{escaped_summary}</div>
    {hint_html}
</div>
"""

    def _render_structure_html(self, include_scripts: bool) -> str:
        """Render HTML for a folded complex with 3D structure."""
        from refua_notebook.widgets.molstar import MolstarView

        if not self.is_folded:
            return ""

        viewer = MolstarView(
            bcif_data=self.bcif_data,
            pdb_data=self.pdb_data,
            ligand_name=self.ligand_name,
            components=self.components,
            width=self.width,
            height=self.height,
            show_controls=self.show_controls,
        )
        return viewer.to_html(include_scripts=include_scripts)

    def _render_affinity_html(self) -> str:
        """Render HTML for binding affinity information."""
        if not self.affinity:
            return ""

        affinity_items = []
        for key, value in self.affinity.items():
            if value is None or (isinstance(value, str) and not value):
                continue
            formatted = self._format_affinity_value(key, value)
            display_key = key.replace("_", " ").title()

            if "probability" in key.lower() or "prob" in key.lower():
                val_float = float(value) if isinstance(value, (int, float)) else 0
                if val_float >= 0.7:
                    color = "#166534"
                    bg = "#dcfce7"
                elif val_float >= 0.5:
                    color = "#a16207"
                    bg = "#fef3c7"
                else:
                    color = "#991b1b"
                    bg = "#fee2e2"
            else:
                color = "#166534"
                bg = "#dcfce7"

            affinity_items.append(f"""
<div class="complex-affinity-row">
    <span class="complex-affinity-label">{html.escape(display_key)}</span>
    <span class="complex-affinity-value" style="color: {color}; background: {bg};">{html.escape(formatted)}</span>
</div>
""")

        if not affinity_items:
            return ""

        return f"""
<div class="complex-affinity">
    <div class="complex-affinity-title">Binding Affinity</div>
    {"".join(affinity_items)}
</div>
"""

    def _render_components_html(
        self,
        ligands: Sequence[Mapping[str, Any]],
        proteins: Sequence[Mapping[str, Any]],
        others: Sequence[Mapping[str, Any]],
        include_scripts: bool,
    ) -> str:
        html_parts = []

        if ligands:
            ligand_cards = []
            for ligand in ligands:
                smiles = ligand.get("smiles")
                name = ligand.get("name") or "Ligand"

                if smiles:
                    from refua_notebook.widgets.smiles import SmilesView

                    sm_view = SmilesView(smiles, title=name, width=240, height=180)
                    ligand_cards.append(
                        f'<div class="complex-grid-item">{sm_view.to_html(include_scripts=include_scripts)}</div>'
                    )
                else:
                    ligand_cards.append(f"""
<div class="complex-card">
    <div class="complex-card-label">Ligand</div>
    <div class="complex-card-title">{html.escape(str(name))}</div>
</div>
""")

            html_parts.append(f"""
<div class="complex-section">
    <div class="complex-section-title">Ligands ({len(ligands)})</div>
    <div class="complex-grid">{''.join(ligand_cards)}</div>
</div>
""")

        if proteins:
            protein_cards = []
            for protein in proteins:
                name = protein.get("name") or "Protein"
                sequence = protein.get("sequence") or ""
                seq_len = len(sequence)
                seq_display = sequence[:20] + "..." if len(sequence) > 20 else sequence
                protein_cards.append(f"""
<div class="complex-card">
    <div class="complex-card-label">Protein</div>
    <div class="complex-card-title">{html.escape(str(name))}</div>
    {f'<div class="complex-card-meta">{seq_len} amino acids</div>' if seq_len else ''}
    {f'<div class="complex-card-seq">{html.escape(seq_display)}</div>' if seq_display else ''}
</div>
""")

            html_parts.append(f"""
<div class="complex-section">
    <div class="complex-section-title">Proteins ({len(proteins)})</div>
    <div class="complex-grid">{''.join(protein_cards)}</div>
</div>
""")

        if others:
            other_cards = []
            for comp in others:
                comp_type = comp.get("type", "other")
                name = comp.get("name") or comp_type.title()
                other_cards.append(f"""
<div class="complex-card">
    <div class="complex-card-label">{html.escape(str(comp_type).title())}</div>
    <div class="complex-card-title">{html.escape(str(name))}</div>
</div>
""")

            html_parts.append(f"""
<div class="complex-section">
    <div class="complex-section-title">Other Components ({len(others)})</div>
    <div class="complex-grid">{''.join(other_cards)}</div>
</div>
""")

        if not html_parts:
            return '<div class="complex-empty">No components available.</div>'

        return "\n".join(html_parts)

    def _render_admet_html(
        self,
        admet_items: Sequence[Mapping[str, Any]],
        include_scripts: bool,
    ) -> str:
        if not admet_items:
            return ""

        html_parts = []
        from refua_notebook.widgets.admet import ADMETView

        for item in admet_items:
            name = item.get("name") or "Ligand"
            properties = item.get("properties") or {}
            smiles = item.get("smiles")

            structure_html = ""
            if smiles:
                from refua_notebook.widgets.smiles import SmilesView

                structure_view = SmilesView(smiles, title=name, width=220, height=160)
                structure_html = f'<div class="complex-admet-structure">{structure_view.to_html(include_scripts=include_scripts)}</div>'

            admet_view = ADMETView(
                properties,
                title=f"{name} ADMET" if name else "ADMET",
                compact=True,
                show_categories=True,
            )
            html_parts.append(f"""
<div class="complex-admet-item">
    {structure_html}
    <div class="complex-admet-table">{admet_view.to_html()}</div>
</div>
""")

        return "\n".join(html_parts)

    def _render_tabs_html(
        self,
        header_html: str,
        tabs: Sequence[Mapping[str, str]],
        include_scripts: bool,
    ) -> str:
        root_id = self._element_id
        root_id_escaped = html.escape(root_id)

        tab_buttons = []
        tab_panels = []
        for idx, tab in enumerate(tabs):
            tab_id = f"{root_id}-tab-{idx}"
            label = tab.get("label", f"Tab {idx + 1}")
            content = tab.get("content", "")
            active_class = " active" if idx == 0 else ""
            aria_selected = "true" if idx == 0 else "false"
            tab_buttons.append(
                f'<button type="button" class="complex-tab-btn{active_class}" data-complex-tab="{html.escape(tab_id)}" aria-selected="{aria_selected}">{html.escape(label)}</button>'
            )
            tab_panels.append(
                f'<div class="complex-tab-panel{active_class}" data-complex-panel="{html.escape(tab_id)}">{content}</div>'
            )

        tab_bar_html = f'<div class="complex-tab-bar">{"".join(tab_buttons)}</div>'

        template = """
<div id="__ROOT_ID__" class="complex-view" data-refua-widget="complex">
<style>
#__ROOT_ID_JS__ {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #0f172a;
}
#__ROOT_ID_JS__ .complex-header {
    background: linear-gradient(135deg, #f8fafc, #eef2ff);
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0 16px 0;
}
#__ROOT_ID_JS__ .complex-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}
#__ROOT_ID_JS__ .complex-title {
    font-size: 16px;
    font-weight: 600;
    color: #0f172a;
}
#__ROOT_ID_JS__ .complex-status {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
}
#__ROOT_ID_JS__ .complex-status.status-ready {
    background: #dcfce7;
    color: #166534;
}
#__ROOT_ID_JS__ .complex-status.status-pending {
    background: #fef3c7;
    color: #92400e;
}
#__ROOT_ID_JS__ .complex-summary {
    font-size: 12px;
    color: #475569;
    margin-top: 6px;
}
#__ROOT_ID_JS__ .complex-hint {
    margin-top: 8px;
    font-size: 12px;
    color: #a16207;
}
#__ROOT_ID_JS__ .complex-hint code {
    background: rgba(255, 255, 255, 0.7);
    padding: 1px 4px;
    border-radius: 4px;
}
#__ROOT_ID_JS__ .complex-tab-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 12px;
}
#__ROOT_ID_JS__ .complex-tab-btn {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 6px 12px;
    font-size: 12px;
    color: #475569;
    cursor: pointer;
}
#__ROOT_ID_JS__ .complex-tab-btn.active {
    background: #ffffff;
    color: #0f172a;
    border-color: #cbd5f5;
    box-shadow: 0 -1px 0 #cbd5f5 inset;
}
#__ROOT_ID_JS__ .complex-tab-panel {
    display: none;
    padding: 12px 0 4px 0;
}
#__ROOT_ID_JS__ .complex-tab-panel.active {
    display: block;
}
#__ROOT_ID_JS__ .complex-section {
    margin-bottom: 16px;
}
#__ROOT_ID_JS__ .complex-section-title {
    font-size: 13px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 8px;
}
#__ROOT_ID_JS__ .complex-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
}
#__ROOT_ID_JS__ .complex-grid-item {
    display: flex;
    justify-content: center;
}
#__ROOT_ID_JS__ .complex-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 12px;
    min-height: 90px;
}
#__ROOT_ID_JS__ .complex-card-label {
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
#__ROOT_ID_JS__ .complex-card-title {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
    margin-top: 6px;
}
#__ROOT_ID_JS__ .complex-card-meta {
    font-size: 11px;
    color: #64748b;
    margin-top: 6px;
}
#__ROOT_ID_JS__ .complex-card-seq {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 10px;
    color: #94a3b8;
    margin-top: 6px;
    word-break: break-all;
}
#__ROOT_ID_JS__ .complex-empty {
    font-size: 12px;
    color: #64748b;
    padding: 8px 0;
}
#__ROOT_ID_JS__ .complex-affinity {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 10px;
    padding: 12px 16px;
    max-width: 380px;
}
#__ROOT_ID_JS__ .complex-affinity-title {
    font-size: 14px;
    font-weight: 600;
    color: #166534;
    margin-bottom: 8px;
}
#__ROOT_ID_JS__ .complex-affinity-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid #dcfce7;
}
#__ROOT_ID_JS__ .complex-affinity-row:last-child {
    border-bottom: none;
}
#__ROOT_ID_JS__ .complex-affinity-label {
    font-size: 12px;
    color: #475569;
}
#__ROOT_ID_JS__ .complex-affinity-value {
    font-size: 12px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 4px;
}
#__ROOT_ID_JS__ .complex-admet-item {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 16px;
}
#__ROOT_ID_JS__ .complex-admet-structure {
    flex-shrink: 0;
}
#__ROOT_ID_JS__ .complex-admet-table {
    flex-grow: 1;
    min-width: 280px;
}
@media (max-width: 700px) {
    #__ROOT_ID_JS__ .complex-tab-bar {
        border-bottom: none;
    }
    #__ROOT_ID_JS__ .complex-tab-btn {
        border-radius: 8px;
        border-bottom: 1px solid #e2e8f0;
    }
}
</style>
__HEADER_HTML__
__TAB_BAR__
<div class="complex-tab-panels">__TAB_PANELS__</div>
__TABS_SCRIPT__
</div>
"""
        script_block = ""
        if include_scripts:
            script_block = f"""
<script>
(function() {{
    var root = document.getElementById('{root_id}');
    if (!root) return;
    var buttons = root.querySelectorAll('[data-complex-tab]');
    var panels = root.querySelectorAll('[data-complex-panel]');
    function activate(tabId) {{
        buttons.forEach(function(btn) {{
            var active = btn.getAttribute('data-complex-tab') === tabId;
            btn.classList.toggle('active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
        }});
        panels.forEach(function(panel) {{
            var active = panel.getAttribute('data-complex-panel') === tabId;
            panel.classList.toggle('active', active);
        }});
    }}
    if (buttons.length) {{
        buttons.forEach(function(btn) {{
            btn.addEventListener('click', function() {{
                activate(btn.getAttribute('data-complex-tab'));
            }});
        }});
        activate(buttons[0].getAttribute('data-complex-tab'));
    }} else if (panels.length) {{
        panels[0].classList.add('active');
    }}
}})();
</script>
"""

        return (
            template.replace("__ROOT_ID__", root_id_escaped)
            .replace("__ROOT_ID_JS__", root_id)
            .replace("__HEADER_HTML__", header_html)
            .replace("__TAB_BAR__", tab_bar_html)
            .replace("__TAB_PANELS__", "".join(tab_panels))
            .replace("__TABS_SCRIPT__", script_block)
        )

    def _render_html(self, include_scripts: bool = True) -> str:
        """Render a minimal viewer-first complex display."""
        root_id = self._element_id
        root_id_escaped = html.escape(root_id)
        title = html.escape(self.name or "Complex")
        status_label = "3D Ready" if self.is_folded else "Not Folded"
        status_class = "ready" if self.is_folded else "pending"

        if self.is_folded:
            stage_html = self._render_structure_html(include_scripts)
        else:
            stage_html = (
                '<div class="complex-empty-state">'
                '<div class="complex-empty-title">No 3D structure available</div>'
                '<div class="complex-empty-subtitle">'
                "Call <code>.fold()</code> to generate a structure."
                "</div>"
                "</div>"
            )

        return f"""
<div id="{root_id_escaped}" class="complex-view complex-view-minimal" data-refua-widget="complex">
<style>
#{root_id} {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #0f172a;
}}
#{root_id} .complex-meta {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin: 0 0 8px 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
#{root_id} .complex-name {{
    color: #334155;
    font-weight: 600;
}}
#{root_id} .complex-status {{
    border-radius: 999px;
    padding: 2px 8px;
    font-weight: 600;
}}
#{root_id} .complex-status.ready {{
    background: #dcfce7;
    color: #166534;
}}
#{root_id} .complex-status.pending {{
    background: #fef3c7;
    color: #92400e;
}}
#{root_id} .complex-stage {{
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.12);
}}
#{root_id} .complex-stage [data-refua-molstar="1"] {{
    border: 0 !important;
    border-radius: 14px !important;
}}
#{root_id} .complex-empty-state {{
    min-height: 240px;
    border: 1px dashed #cbd5e1;
    border-radius: 14px;
    background: linear-gradient(160deg, #f8fafc 0%, #f1f5f9 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 8px;
    padding: 24px;
    text-align: center;
}}
#{root_id} .complex-empty-title {{
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
}}
#{root_id} .complex-empty-subtitle {{
    font-size: 12px;
    color: #64748b;
}}
#{root_id} .complex-empty-subtitle code {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 1px 5px;
}}
</style>
<div class="complex-meta">
    <span class="complex-name">{title}</span>
    <span class="complex-status {status_class}">{status_label}</span>
</div>
<div class="complex-stage">{stage_html}</div>
</div>
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
        """Display the complex view in the notebook."""
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
    def from_refua_complex(
        cls,
        complex_obj: Any,
        **kwargs,
    ) -> "ComplexView":
        """Create a ComplexView from a Refua Complex object.

        Parameters
        ----------
        complex_obj : refua.Complex or refua.FoldedComplex
            A Refua complex object.
        **kwargs
            Additional arguments passed to ComplexView constructor.

        Returns
        -------
        ComplexView
            A view instance configured with the complex data.
        """
        # Get name
        name = getattr(complex_obj, "name", None)

        last_fold = getattr(complex_obj, "last_fold", None)
        last_structure = getattr(complex_obj, "last_structure", None)
        last_affinity = getattr(complex_obj, "last_affinity", None)

        # Check for structure data (folded)
        bcif_data = None
        pdb_data = None

        def _try_method(obj: Any, method: str) -> Optional[Any]:
            if obj is None or not hasattr(obj, method):
                return None
            try:
                return getattr(obj, method)()
            except Exception:
                return None

        for candidate in (last_fold, last_structure, complex_obj):
            if bcif_data is None:
                bcif_data = _try_method(candidate, "to_bcif")
            if pdb_data is None:
                pdb_data = _try_method(candidate, "to_pdb")
            if bcif_data is not None or pdb_data is not None:
                break

        # Get affinity if available
        affinity = None
        affinity_source = None
        if last_fold is not None:
            affinity_source = getattr(last_fold, "affinity", None)
        if affinity_source is None and last_affinity is not None:
            affinity_source = last_affinity
        if affinity_source is None and hasattr(complex_obj, "affinity"):
            affinity_source = getattr(complex_obj, "affinity", None)

        if affinity_source is not None:
            affinity = cls._coerce_properties(affinity_source)
            if affinity:
                affinity = {
                    k: v
                    for k, v in affinity.items()
                    if v is not None and not (isinstance(v, str) and not v)
                }
            if not affinity:
                affinity = {}
                for attr in (
                    "value",
                    "probability",
                    "ic50",
                    "binding_probability",
                    "value1",
                    "value2",
                    "probability1",
                    "probability2",
                ):
                    if hasattr(affinity_source, attr):
                        val = getattr(affinity_source, attr)
                        if val is not None:
                            affinity[attr] = val

        # Get ligand name
        ligand_name = None
        components = []

        entities = getattr(complex_obj, "entities", None) or getattr(
            complex_obj, "components", []
        )
        chain_ids = None
        if last_fold is not None:
            chain_ids = getattr(last_fold, "chain_ids", None)
        if chain_ids is None:
            chain_ids = getattr(complex_obj, "chain_ids", None)
        chain_ids = list(chain_ids or [])
        chain_idx = 0

        ligand_admet = None
        if last_fold is not None:
            ligand_admet = getattr(last_fold, "ligand_admet", None)
        if ligand_admet is None:
            ligand_admet = getattr(complex_obj, "ligand_admet", None)
        ligand_admet_map = (
            dict(ligand_admet) if isinstance(ligand_admet, Mapping) else {}
        )
        used_admet: set[str] = set()

        ligand_rdkit = None
        if last_fold is not None:
            ligand_rdkit = getattr(last_fold, "ligand_rdkit", None)
        if ligand_rdkit is None:
            ligand_rdkit = getattr(complex_obj, "ligand_rdkit", None)
        ligand_rdkit_map = (
            dict(ligand_rdkit) if isinstance(ligand_rdkit, Mapping) else {}
        )
        used_rdkit: set[str] = set()

        def _is_design_file(entity: Any) -> bool:
            if isinstance(entity, Mapping):
                if str(entity.get("type", "")).lower() == "file":
                    return True
                if "path" in entity and not any(
                    key in entity for key in ("sequence", "seq", "smiles")
                ):
                    return True
            entity_type = type(entity).__name__.lower()
            if "designfile" in entity_type:
                return True
            if hasattr(entity, "path") and not (
                hasattr(entity, "sequence")
                or hasattr(entity, "seq")
                or hasattr(entity, "smiles")
            ):
                return True
            return False

        def _next_chain_ids(entity: Any) -> Optional[Sequence[str]]:
            nonlocal chain_idx
            if not chain_ids or _is_design_file(entity):
                return None
            if chain_idx >= len(chain_ids):
                return None
            ids = chain_ids[chain_idx]
            chain_idx += 1
            return ids

        def _collect_ids(entity: Any, fallback: Optional[Sequence[str]]) -> list[str]:
            ids: list[str] = []
            raw_ids = None
            if isinstance(entity, Mapping):
                raw_ids = entity.get("ids") or entity.get("id")
            else:
                if hasattr(entity, "ids"):
                    raw_ids = getattr(entity, "ids")
                elif hasattr(entity, "id"):
                    raw_ids = getattr(entity, "id")
            if raw_ids is not None:
                if isinstance(raw_ids, str):
                    ids.append(raw_ids)
                elif isinstance(raw_ids, (list, tuple)):
                    ids.extend([str(item) for item in raw_ids if item])
                else:
                    ids.append(str(raw_ids))
            if fallback:
                if isinstance(fallback, str):
                    ids.append(fallback)
                else:
                    ids.extend([str(item) for item in fallback if item])
            # de-duplicate while preserving order
            seen: set[str] = set()
            deduped: list[str] = []
            for item in ids:
                if item in seen:
                    continue
                seen.add(item)
                deduped.append(item)
            return deduped

        def _pick_payload(
            candidate_ids: Sequence[str],
            payload_map: Mapping[str, Any],
            used: set[str],
        ) -> Any:
            for candidate in candidate_ids:
                if candidate in payload_map:
                    used.add(candidate)
                    return payload_map[candidate]
            for key, value in payload_map.items():
                if key not in used:
                    used.add(key)
                    return value
            return None

        def _normalize_chain_ids(raw: Any) -> list[str]:
            normalized: list[str] = []
            if raw is None:
                return normalized
            if isinstance(raw, str):
                values = [raw]
            elif isinstance(raw, (list, tuple, set)):
                values = list(raw)
            else:
                values = [raw]
            for value in values:
                token = str(value).strip()
                if token and token not in normalized:
                    normalized.append(token)
            return normalized

        for entity in entities:
            entity_chain_ids = _next_chain_ids(entity)
            entity_chain_id_list = _normalize_chain_ids(entity_chain_ids)
            entity_ids = _collect_ids(entity, entity_chain_ids)
            entity_type = type(entity).__name__
            entity_type_lower = entity_type.lower()

            is_ligand = (
                entity_type == "SM"
                or "ligand" in entity_type_lower
                or "small" in entity_type_lower
                or hasattr(entity, "smiles")
                or hasattr(entity, "to_smiles")
            )
            is_protein = (
                entity_type == "Protein"
                or "protein" in entity_type_lower
                or hasattr(entity, "sequence")
                or hasattr(entity, "seq")
            )

            if is_ligand and not is_protein:
                smiles = getattr(entity, "smiles", None)
                if smiles is None and hasattr(entity, "to_smiles"):
                    try:
                        smiles = entity.to_smiles()
                    except Exception:
                        smiles = None
                if smiles is None:
                    smiles = str(entity)

                ent_name = getattr(entity, "name", None) or getattr(entity, "id", None)
                if ent_name is None and entity_ids:
                    ent_name = entity_ids[0]
                if not ligand_name and smiles:
                    ligand_name = ent_name or (
                        smiles[:20] + "..." if len(smiles) > 20 else smiles
                    )

                properties = None
                if ligand_admet_map:
                    payload = _pick_payload(entity_ids, ligand_admet_map, used_admet)
                    properties = cls._extract_admet_properties(payload)
                if properties is None and ligand_rdkit_map:
                    payload = _pick_payload(entity_ids, ligand_rdkit_map, used_rdkit)
                    properties = cls._coerce_properties(payload)
                if properties is None and hasattr(entity, "to_dict"):
                    try:
                        properties = entity.to_dict()
                    except Exception:
                        properties = None
                if properties is None and hasattr(entity, "properties"):
                    properties = entity.properties
                if properties is None and hasattr(entity, "admet"):
                    properties = entity.admet
                properties = cls._extract_admet_properties(properties)

                components.append(
                    {
                        "type": "ligand",
                        "name": ent_name,
                        "id": entity_ids[0] if entity_ids else None,
                        "smiles": smiles,
                        "chain_ids": entity_chain_id_list,
                        "properties": properties,
                    }
                )
            elif is_protein:
                seq = getattr(entity, "sequence", None) or getattr(entity, "seq", "")
                prot_name = getattr(entity, "name", None) or getattr(
                    entity, "ids", None
                )
                if isinstance(prot_name, (list, tuple)):
                    prot_name = prot_name[0] if prot_name else None
                components.append(
                    {
                        "type": "protein",
                        "name": prot_name,
                        "id": entity_ids[0] if entity_ids else None,
                        "sequence": seq,
                        "chain_ids": entity_chain_id_list,
                    }
                )
            else:
                components.append(
                    {
                        "type": entity_type.lower(),
                        "name": getattr(entity, "name", None),
                        "id": entity_ids[0] if entity_ids else None,
                        "chain_ids": entity_chain_id_list,
                    }
                )

        return cls(
            bcif_data=bcif_data,
            pdb_data=pdb_data,
            name=name,
            ligand_name=ligand_name,
            affinity=affinity,
            components=components,
            **kwargs,
        )

    @classmethod
    def from_structure_data(
        cls,
        bcif_data: Optional[bytes] = None,
        pdb_data: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs,
    ) -> "ComplexView":
        """Create a ComplexView from structure data.

        Parameters
        ----------
        bcif_data : bytes, optional
            Binary CIF structure data.
        pdb_data : str, optional
            PDB format structure data.
        name : str, optional
            Name for the complex.
        **kwargs
            Additional arguments passed to ComplexView constructor.

        Returns
        -------
        ComplexView
            A view instance with the structure data.
        """
        return cls(bcif_data=bcif_data, pdb_data=pdb_data, name=name, **kwargs)
