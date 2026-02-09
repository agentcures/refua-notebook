"""Mol* 3D molecular viewer widget for Jupyter notebooks.

This module provides the MolstarView class for displaying 3D molecular
structures inline in Jupyter notebooks using the Mol* (molstar) viewer.
"""

from __future__ import annotations

import base64
import html
import json
import re
import uuid
from types import ModuleType
from typing import Any, Mapping, Optional, Sequence

from refua_notebook.mime import REFUA_MIME_TYPE

_ipython_display_module: ModuleType | None
try:
    import IPython.display as _ipython_display_module
except ImportError:
    _ipython_display_module = None


# CDN URLs for Mol* resources
MOLSTAR_JS_CDN = (
    "https://cdn.jsdelivr.net/npm/molstar@4.18.0/build/viewer/molstar.min.js"
)
MOLSTAR_CSS_CDN = (
    "https://cdn.jsdelivr.net/npm/molstar@4.18.0/build/viewer/molstar.min.css"
)

# Valid CSS color pattern (hex, rgb, rgba, hsl, hsla, named colors)
_CSS_COLOR_PATTERN = re.compile(
    r"^(?:#[0-9a-fA-F]{3,8}|"  # hex colors
    r"rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)|"  # rgb
    r"rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[\d.]+\s*\)|"  # rgba
    r"[a-zA-Z]+)$"  # named colors
)

_CHAIN_ID_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9]{1,4}$")
_HEAVY_CHAIN_HINT_PATTERN = re.compile(
    r"\b(?:heavy|igh|vh|h[\s_-]?chain|chain[\s_-]?h|hc)\b", re.IGNORECASE
)
_LIGHT_CHAIN_HINT_PATTERN = re.compile(
    r"\b(?:light|igl|vl|kappa|lambda|l[\s_-]?chain|chain[\s_-]?l|lc)\b",
    re.IGNORECASE,
)

_NUCLEIC_COMP_IDS = {
    "A",
    "C",
    "G",
    "U",
    "I",
    "DA",
    "DC",
    "DG",
    "DT",
    "DU",
    "DI",
    "ADE",
    "CYT",
    "GUA",
    "URA",
    "THY",
}
_ION_COMP_IDS = {
    "LI",
    "NA",
    "K",
    "RB",
    "CS",
    "BE",
    "MG",
    "CA",
    "SR",
    "BA",
    "MN",
    "FE",
    "CO",
    "NI",
    "CU",
    "ZN",
    "CD",
    "HG",
    "AL",
    "GA",
    "IN",
    "TL",
    "PB",
    "AG",
    "AU",
    "PT",
    "CR",
    "MO",
    "W",
    "V",
    "YB",
    "SM",
    "EU",
    "LA",
    "CL",
    "BR",
    "IOD",
    "F",
}


def _validate_css_color(color: str, default: str = "white") -> str:
    """Validate and sanitize a CSS color value."""
    if _CSS_COLOR_PATTERN.match(color):
        return color
    return default


def _validate_dimension(value: Any, default: int = 400) -> int:
    """Validate and sanitize a dimension value (width/height)."""
    try:
        val = int(value)
        return max(val, 100)  # Minimum dimension of 100px
    except (TypeError, ValueError):
        return default


def _safe_json_for_html(value: Any) -> str:
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


class MolstarView:
    """Jupyter widget for displaying 3D molecular structures with Mol*.

    This class generates an interactive 3D molecular viewer that can be
    displayed inline in Jupyter notebooks. It supports BCIF (Binary CIF)
    data from structure prediction tools like Refua/Boltz.

    Parameters
    ----------
    bcif_data : bytes, optional
        Binary CIF data containing the molecular structure.
    pdb_data : str, optional
        PDB format string containing the molecular structure.
    url : str, optional
        URL to load structure from (supports mmCIF, PDB, BCIF formats).
    ligand_name : str, optional
        Name of the ligand to highlight in the structure.
    components : sequence of mapping, optional
        Component metadata used for role/chain-aware default coloring.
    width : int, optional
        Width of the viewer in pixels. Default 600.
    height : int, optional
        Height of the viewer in pixels. Default 400.
    background : str, optional
        Background color for the viewer. Default "white".
    show_controls : bool, optional
        Whether to show viewer controls. Default True.

    Notes
    -----
    Internal helper used by the Refua notebook extension.
    """

    def __init__(
        self,
        bcif_data: Optional[bytes] = None,
        pdb_data: Optional[str] = None,
        url: Optional[str] = None,
        ligand_name: Optional[str] = None,
        components: Optional[Sequence[Mapping[str, Any]]] = None,
        width: int = 600,
        height: int = 400,
        background: str = "white",
        show_controls: bool = True,
    ):
        self.bcif_data = bcif_data
        self.pdb_data = pdb_data
        self.url = url
        self.ligand_name = ligand_name
        self.components = [
            dict(component)
            for component in (components or [])
            if isinstance(component, Mapping)
        ]
        self.width = width
        self.height = height
        self.background = background
        self.show_controls = show_controls
        self._viewer_id = f"molstar-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _collect_component_hint_text(component: Mapping[str, Any]) -> str:
        """Build a lowercase text blob used for component heuristics."""
        chunks: list[str] = []
        for key in ("type", "name", "id", "label"):
            value = component.get(key)
            if value is None:
                continue
            chunks.append(str(value))
        ids = component.get("ids")
        if isinstance(ids, str):
            chunks.append(ids)
        elif isinstance(ids, (list, tuple, set)):
            chunks.extend(str(item) for item in ids if item)
        return " ".join(chunks).lower()

    @staticmethod
    def _coerce_component_chain_ids(raw: Any) -> list[str]:
        """Normalize possible chain-id fields into a clean string list."""

        tokens: list[str] = []

        def _collect(value: Any) -> None:
            if value is None:
                return
            if isinstance(value, str):
                for piece in re.split(r"[,\s;]+", value.strip()):
                    if piece:
                        tokens.append(piece)
                return
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    _collect(item)
                return
            tokens.append(str(value))

        _collect(raw)
        seen: set[str] = set()
        chain_ids: list[str] = []
        for token in tokens:
            clean = token.strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            chain_ids.append(clean)
        return chain_ids

    @staticmethod
    def _classify_component_role(component: Mapping[str, Any]) -> str:
        """Infer coarse molecule role used for default coloring."""
        comp_type = str(component.get("type", "")).strip().lower()
        has_smiles = bool(component.get("smiles") or component.get("smile"))
        has_sequence = bool(component.get("sequence") or component.get("seq"))
        hint_text = MolstarView._collect_component_hint_text(component)

        if comp_type in ("dna", "rna", "nucleic", "nucleic_acid", "nucleic acid"):
            return "nucleic"
        if "nucleic" in comp_type:
            return "nucleic"
        if comp_type in ("ion", "metal", "metal_ion") or "ion" in comp_type:
            return "ion"
        if comp_type in (
            "ligand",
            "sm",
            "small_molecule",
            "small molecule",
            "molecule",
        ) or has_smiles:
            return "ligand"
        if (
            not has_sequence
            and (
                "ligand" in hint_text
                or "small molecule" in hint_text
                or "small_molecule" in hint_text
                or re.search(r"\bl\d+\b", hint_text)
            )
        ):
            return "ligand"
        if comp_type in ("protein", "peptide", "antibody") or has_sequence:
            return "protein"
        if "protein" in comp_type or "antibody" in comp_type:
            return "protein"
        return "other"

    @staticmethod
    def _detect_antibody_chain_role(component: Mapping[str, Any]) -> Optional[str]:
        """Best-effort heavy/light chain detection from component labels."""
        hint_text = MolstarView._collect_component_hint_text(component)
        if _HEAVY_CHAIN_HINT_PATTERN.search(hint_text):
            return "heavy"
        if _LIGHT_CHAIN_HINT_PATTERN.search(hint_text):
            return "light"

        comp_id = component.get("id")
        if isinstance(comp_id, str):
            token = comp_id.strip().upper()
            if token in {"H", "HC", "VH"}:
                return "heavy"
            if token in {"L", "LC", "VL", "K", "KAPPA", "LAMBDA"}:
                return "light"
        return None

    @staticmethod
    def _empty_color_plan() -> dict[str, Any]:
        return {
            "protein_chain_groups": [],
            "nucleic_chain_groups": [],
            "ligand_chain_groups": [],
            "ion_chain_groups": [],
            "other_chain_groups": [],
            "antibody_pair_detected": False,
        }

    @staticmethod
    def _plan_has_chain_groups(plan: Mapping[str, Any]) -> bool:
        for key in (
            "protein_chain_groups",
            "nucleic_chain_groups",
            "ligand_chain_groups",
            "ion_chain_groups",
            "other_chain_groups",
        ):
            groups = plan.get(key)
            if isinstance(groups, Sequence) and groups:
                return True
        return False

    @staticmethod
    def _is_heavy_chain_id(chain_id: str) -> bool:
        token = str(chain_id).strip().upper()
        if token in {"H", "HC", "VH"}:
            return True
        return bool(re.fullmatch(r"H\d{0,2}", token))

    @staticmethod
    def _is_light_chain_id(chain_id: str) -> bool:
        token = str(chain_id).strip().upper()
        if token in {"L", "LC", "VL", "K", "KAPPA", "LAMBDA"}:
            return True
        return bool(re.fullmatch(r"L\d{0,2}", token))

    @staticmethod
    def _ensure_chain_stats(
        chain_stats: dict[str, dict[str, Any]], chain_id: str
    ) -> dict[str, Any]:
        stats = chain_stats.get(chain_id)
        if stats is not None:
            return stats
        stats = {
            "atom_count": 0,
            "hetatm_count": 0,
            "comp_counts": {},
        }
        chain_stats[chain_id] = stats
        return stats

    @staticmethod
    def _extract_chain_stats_from_mmcif_text(
        mmcif_text: str,
    ) -> dict[str, dict[str, Any]]:
        """Extract chain-level stats from mmCIF ATOM/HETATM rows."""
        chain_stats: dict[str, dict[str, Any]] = {}

        for raw_line in mmcif_text.splitlines():
            line = raw_line.strip()
            if not line.startswith(("ATOM ", "HETATM ")):
                continue

            fields = line.split()
            if len(fields) < 10:
                continue

            group = fields[0].upper()
            comp_id = fields[5].strip().upper()
            chain_id = fields[9].strip()
            if not chain_id or chain_id in {".", "?"}:
                continue

            stats = MolstarView._ensure_chain_stats(chain_stats, chain_id)
            comp_counts = stats["comp_counts"]
            comp_counts[comp_id] = int(comp_counts.get(comp_id, 0)) + 1
            if group == "ATOM":
                stats["atom_count"] = int(stats["atom_count"]) + 1
            elif group == "HETATM":
                stats["hetatm_count"] = int(stats["hetatm_count"]) + 1

        return chain_stats

    @staticmethod
    def _extract_chain_stats_from_pdb_text(
        pdb_text: str,
    ) -> dict[str, dict[str, Any]]:
        """Extract chain-level stats from PDB ATOM/HETATM rows."""
        chain_stats: dict[str, dict[str, Any]] = {}

        for raw_line in pdb_text.splitlines():
            if not (raw_line.startswith("ATOM  ") or raw_line.startswith("HETATM")):
                continue

            group = raw_line[:6].strip().upper()
            chain_id = raw_line[21:22].strip() if len(raw_line) >= 22 else ""
            comp_id = raw_line[17:20].strip().upper() if len(raw_line) >= 20 else ""
            if not chain_id:
                continue

            stats = MolstarView._ensure_chain_stats(chain_stats, chain_id)
            comp_counts = stats["comp_counts"]
            if comp_id:
                comp_counts[comp_id] = int(comp_counts.get(comp_id, 0)) + 1
            if group == "ATOM":
                stats["atom_count"] = int(stats["atom_count"]) + 1
            elif group == "HETATM":
                stats["hetatm_count"] = int(stats["hetatm_count"]) + 1

        return chain_stats

    @staticmethod
    def _classify_chain_role_from_stats(stats: Mapping[str, Any]) -> str:
        atom_count = int(stats.get("atom_count", 0))
        hetatm_count = int(stats.get("hetatm_count", 0))
        comp_counts_raw = stats.get("comp_counts", {})
        comp_counts: dict[str, int] = {}
        if isinstance(comp_counts_raw, Mapping):
            for comp_id, count in comp_counts_raw.items():
                token = str(comp_id).strip().upper()
                if not token:
                    continue
                comp_counts[token] = int(count)

        total_comp_obs = sum(comp_counts.values())
        nucleic_comp_obs = sum(
            count
            for comp_id, count in comp_counts.items()
            if comp_id in _NUCLEIC_COMP_IDS
        )

        if atom_count > 0:
            if total_comp_obs > 0 and nucleic_comp_obs / total_comp_obs >= 0.8:
                return "nucleic"
            return "protein"

        if hetatm_count > 0:
            unique_comps = set(comp_counts)
            if unique_comps and unique_comps.issubset(_ION_COMP_IDS):
                return "ion"
            if len(unique_comps) == 1:
                only = next(iter(unique_comps))
                if only in _ION_COMP_IDS or (len(only) <= 2 and hetatm_count <= 4):
                    return "ion"
            return "ligand"

        return "other"

    def _infer_chain_roles_from_structure(self) -> list[tuple[str, str]]:
        """Infer chain roles directly from structural records."""
        chain_stats: dict[str, dict[str, Any]] = {}

        if self.bcif_data is not None and self._looks_like_text_cif(self.bcif_data):
            try:
                mmcif_text = self.bcif_data.decode("utf-8")
            except UnicodeDecodeError:
                mmcif_text = self.bcif_data.decode("utf-8", errors="ignore")
            chain_stats = self._extract_chain_stats_from_mmcif_text(mmcif_text)
        elif self.pdb_data is not None:
            chain_stats = self._extract_chain_stats_from_pdb_text(self.pdb_data)

        inferred: list[tuple[str, str]] = []
        for chain_id, stats in chain_stats.items():
            role = self._classify_chain_role_from_stats(stats)
            inferred.append((chain_id, role))
        return inferred

    def _build_structure_inferred_color_plan(self) -> Optional[dict[str, Any]]:
        chain_roles = self._infer_chain_roles_from_structure()
        if not chain_roles:
            return None

        plan = self._empty_color_plan()
        assigned_chain_ids: set[str] = set()

        def _add_group(plan_key: str, chain_ids: Sequence[str]) -> None:
            group: list[str] = []
            for chain_id in chain_ids:
                token = str(chain_id).strip()
                if not token or token in assigned_chain_ids or token in group:
                    continue
                group.append(token)
            if group:
                plan[plan_key].append(group)
                assigned_chain_ids.update(group)

        protein_chain_ids = [chain for chain, role in chain_roles if role == "protein"]
        heavy_chain_ids = [
            chain for chain in protein_chain_ids if self._is_heavy_chain_id(chain)
        ]
        light_chain_ids = [
            chain for chain in protein_chain_ids if self._is_light_chain_id(chain)
        ]

        if heavy_chain_ids and light_chain_ids:
            _add_group("protein_chain_groups", [*heavy_chain_ids, *light_chain_ids])
            plan["antibody_pair_detected"] = bool(plan["protein_chain_groups"])

        for chain_id in protein_chain_ids:
            _add_group("protein_chain_groups", [chain_id])

        role_to_plan_key = {
            "nucleic": "nucleic_chain_groups",
            "ligand": "ligand_chain_groups",
            "ion": "ion_chain_groups",
        }
        for chain_id, role in chain_roles:
            if role == "protein":
                continue
            plan_key = role_to_plan_key.get(role, "other_chain_groups")
            _add_group(plan_key, [chain_id])

        return plan

    def _build_molecule_color_plan(self) -> dict[str, Any]:
        """Create chain-group color hints consumed by JS renderers."""
        plan = self._empty_color_plan()
        if not self.components:
            inferred_plan = self._build_structure_inferred_color_plan()
            return inferred_plan if inferred_plan is not None else plan

        rows: list[dict[str, Any]] = []
        for component in self.components:
            if not isinstance(component, Mapping):
                continue

            role = self._classify_component_role(component)
            chain_ids: list[str] = []
            for key in (
                "chain_ids",
                "chains",
                "chain",
                "asym_id",
                "auth_asym_id",
                "label_asym_id",
            ):
                chain_ids.extend(self._coerce_component_chain_ids(component.get(key)))

            if not chain_ids:
                component_id = component.get("id")
                if isinstance(component_id, str):
                    token = component_id.strip()
                    if _CHAIN_ID_TOKEN_PATTERN.fullmatch(token):
                        chain_ids = [token]

            deduped_chain_ids: list[str] = []
            seen_ids: set[str] = set()
            for chain_id in chain_ids:
                if chain_id in seen_ids:
                    continue
                seen_ids.add(chain_id)
                deduped_chain_ids.append(chain_id)

            rows.append(
                {
                    "role": role,
                    "chain_ids": deduped_chain_ids,
                    "antibody_role": (
                        self._detect_antibody_chain_role(component)
                        if role == "protein"
                        else None
                    ),
                }
            )

        assigned_chain_ids: set[str] = set()

        def _add_group(plan_key: str, chain_ids: Sequence[str]) -> None:
            group: list[str] = []
            for chain_id in chain_ids:
                token = str(chain_id).strip()
                if not token or token in assigned_chain_ids or token in group:
                    continue
                group.append(token)
            if group:
                plan[plan_key].append(group)
                assigned_chain_ids.update(group)

        protein_rows = [row for row in rows if row.get("role") == "protein"]
        heavy_chain_ids: list[str] = []
        light_chain_ids: list[str] = []
        for row in protein_rows:
            if row.get("antibody_role") == "heavy":
                heavy_chain_ids.extend(row.get("chain_ids", []))
            elif row.get("antibody_role") == "light":
                light_chain_ids.extend(row.get("chain_ids", []))

        if heavy_chain_ids and light_chain_ids:
            _add_group("protein_chain_groups", [*heavy_chain_ids, *light_chain_ids])
            plan["antibody_pair_detected"] = bool(plan["protein_chain_groups"])

        for row in protein_rows:
            _add_group("protein_chain_groups", row.get("chain_ids", []))

        role_to_plan_key = {
            "nucleic": "nucleic_chain_groups",
            "ligand": "ligand_chain_groups",
            "ion": "ion_chain_groups",
        }
        for row in rows:
            role = str(row.get("role", "other"))
            if role in ("protein",):
                continue
            plan_key = role_to_plan_key.get(role, "other_chain_groups")
            _add_group(plan_key, row.get("chain_ids", []))

        if not self._plan_has_chain_groups(plan):
            inferred_plan = self._build_structure_inferred_color_plan()
            if inferred_plan is not None:
                return inferred_plan

        return plan

    @staticmethod
    def _looks_like_text_cif(data: bytes) -> bool:
        """Heuristically detect text mmCIF bytes mislabeled as BCIF."""
        if not data:
            return False
        sample = data[:2048]
        try:
            text = sample.decode("utf-8")
        except UnicodeDecodeError:
            return False

        stripped = text.lstrip()
        if not stripped:
            return False
        if stripped.startswith(("data_", "loop_", "_")):
            return True

        printable = sum(
            1 for ch in stripped if ch.isprintable() or ch in ("\n", "\r", "\t")
        )
        return printable / max(len(stripped), 1) >= 0.95

    def _infer_bcif_format_and_mime(self) -> tuple[str, str]:
        """Infer format/mime for BCIF payloads (binary BCIF vs text mmCIF)."""
        if self.bcif_data is not None and self._looks_like_text_cif(self.bcif_data):
            return "mmcif", "text/plain"
        return "bcif", "application/octet-stream"

    def _get_data_url(self) -> Optional[str]:
        """Convert BCIF/PDB data to a data URL for loading."""
        if self.bcif_data is not None:
            _, mime_type = self._infer_bcif_format_and_mime()
            b64_data = base64.b64encode(self.bcif_data).decode("ascii")
            return f"data:{mime_type};base64,{b64_data}"
        elif self.pdb_data is not None:
            b64_data = base64.b64encode(self.pdb_data.encode("utf-8")).decode("ascii")
            return f"data:text/plain;base64,{b64_data}"
        return None

    def _render_html(self, include_scripts: bool = True) -> str:
        """Render the Mol* viewer as HTML."""
        viewer_id = html.escape(self._viewer_id)

        # Validate and sanitize inputs
        safe_width = _validate_dimension(self.width, 600)
        safe_height = _validate_dimension(self.height, 400)
        safe_bg = _validate_css_color(self.background, "white")

        # Determine data source
        data_url = self._get_data_url()
        if data_url is not None:
            # Use inline data
            if self.bcif_data is not None:
                format_type, _ = self._infer_bcif_format_and_mime()
            else:
                format_type = "pdb"
            url_value = data_url
        elif self.url is not None:
            # Load from URL
            url_value = self.url
            # Determine format from URL extension
            if self.url.endswith(".bcif"):
                format_type = "bcif"
            elif self.url.endswith(".pdb"):
                format_type = "pdb"
            else:
                format_type = "mmcif"
        else:
            # No data provided
            return f"""
<div style="width: {safe_width}px; height: {safe_height}px; display: flex;
            align-items: center; justify-content: center; background: #f3f4f6;
            border: 1px solid #e5e7eb; border-radius: 8px; color: #6b7280;">
    <p>No structure data provided</p>
</div>
"""

        controls_js = "true" if self.show_controls else "false"
        data_url_escaped = html.escape(url_value, quote=True)
        ligand_attr = html.escape(self.ligand_name or "", quote=True)
        color_plan = self._build_molecule_color_plan()
        color_plan_attr = html.escape(
            json.dumps(color_plan, separators=(",", ":")),
            quote=True,
        )
        data_attrs = (
            f'data-refua-molstar="1" '
            f'data-url="{data_url_escaped}" '
            f'data-format="{html.escape(format_type)}" '
            f'data-ligand="{ligand_attr}" '
            f'data-controls="{str(self.show_controls).lower()}" '
            f'data-color-plan="{color_plan_attr}" '
            f'data-background="{safe_bg}"'
        )

        script_block = ""
        if include_scripts:
            # Use JSON encoding for JavaScript values (prevents XSS)
            # _safe_json_for_html escapes <, >, & to prevent script injection
            ligand_json = (
                _safe_json_for_html(self.ligand_name) if self.ligand_name else "null"
            )
            url_json = _safe_json_for_html(url_value)
            color_plan_json = _safe_json_for_html(color_plan)
            script_block = f"""
<script>
(function() {{
    // Load Mol* script if not already loaded
    function loadMolstar(callback) {{
        if (typeof molstar !== 'undefined') {{
            callback();
            return;
        }}
        var script = document.createElement('script');
        script.src = '{MOLSTAR_JS_CDN}';
        script.onload = callback;
        script.onerror = function() {{
            document.getElementById('{viewer_id}-loading').textContent = 'Failed to load Mol*';
        }};
        document.head.appendChild(script);
    }}

    function initViewer() {{
        var container = document.getElementById('{viewer_id}');
        var loadingEl = document.getElementById('{viewer_id}-loading');
        var ligandName = {ligand_json};
        var dataUrl = {url_json};
        var colorPlan = {color_plan_json};
        var formatType = '{format_type}';
        var isInlineDataUrl =
            typeof dataUrl === 'string' && dataUrl.trim().indexOf('data:') === 0;

        function looksLikeTextCifDataUrl(url) {{
            if (typeof url !== 'string' || url.indexOf('data:') !== 0) {{
                return false;
            }}
            var commaIndex = url.indexOf(',');
            if (commaIndex < 0) {{
                return false;
            }}
            var meta = url.slice(5, commaIndex).toLowerCase();
            var payload = url.slice(commaIndex + 1);
            try {{
                var sample = '';
                if (meta.indexOf(';base64') >= 0) {{
                    var compact = payload.replace(/\\s+/g, '');
                    var chunk = compact.slice(0, 4096);
                    var padded = chunk + '='.repeat((4 - (chunk.length % 4)) % 4);
                    sample = atob(padded).slice(0, 512);
                }} else {{
                    sample = decodeURIComponent(payload.slice(0, 512));
                }}
                var trimmed = sample.replace(/^\\s+/, '');
                if (!trimmed) {{
                    return false;
                }}
                return (
                    trimmed.indexOf('data_') === 0 ||
                    trimmed.indexOf('loop_') === 0 ||
                    trimmed.indexOf('_') === 0
                );
            }} catch (e) {{
                return false;
            }}
        }}

        function normalizeChainGroups(rawGroups) {{
            if (!Array.isArray(rawGroups)) {{
                return [];
            }}
            var seen = Object.create(null);
            var groups = [];
            for (var i = 0; i < rawGroups.length; i += 1) {{
                var rawGroup = rawGroups[i];
                var chainIds = [];
                if (!Array.isArray(rawGroup)) {{
                    continue;
                }}
                for (var j = 0; j < rawGroup.length; j += 1) {{
                    var token = String(rawGroup[j] || '').trim();
                    if (!token || seen[token]) {{
                        continue;
                    }}
                    seen[token] = true;
                    chainIds.push(token);
                }}
                if (chainIds.length > 0) {{
                    groups.push(chainIds);
                }}
            }}
            return groups;
        }}

        function makeChainSelector(chainIds) {{
            if (!Array.isArray(chainIds) || chainIds.length === 0) {{
                return null;
            }}
            var selectors = [];
            var seen = Object.create(null);
            for (var i = 0; i < chainIds.length; i += 1) {{
                var token = String(chainIds[i] || '').trim();
                if (!token) {{
                    continue;
                }}
                var labelKey = 'label:' + token;
                if (!seen[labelKey]) {{
                    seen[labelKey] = true;
                    selectors.push({{ label_asym_id: token }});
                }}
                var authKey = 'auth:' + token;
                if (!seen[authKey]) {{
                    seen[authKey] = true;
                    selectors.push({{ auth_asym_id: token }});
                }}
            }}
            if (selectors.length === 0) {{
                return null;
            }}
            return selectors.length === 1 ? selectors[0] : selectors;
        }}

        function addChainRepresentation(structure, chainIds, type, color, opacity) {{
            var selector = makeChainSelector(chainIds);
            if (!selector) {{
                return null;
            }}
            var component = structure.component({{ selector: selector }});
            var colorProps = {{ color: color }};
            if (typeof opacity === 'number') {{
                colorProps.opacity = opacity;
            }}
            component.representation({{ type: type }}).color(colorProps);
            return component;
        }}

        function applyColorPlan(structure) {{
            var proteinPalette = [
                '#2563eb',
                '#0891b2',
                '#7c3aed',
                '#0f766e',
                '#059669',
                '#f59e0b',
                '#dc2626',
                '#9333ea',
            ];
            var ligandPalette = [
                '#db2777',
                '#c026d3',
                '#e11d48',
                '#be185d',
                '#ec4899',
            ];
            var proteinGroups = normalizeChainGroups(
                colorPlan && colorPlan.protein_chain_groups
            );
            var nucleicGroups = normalizeChainGroups(
                colorPlan && colorPlan.nucleic_chain_groups
            );
            var ligandGroups = normalizeChainGroups(
                colorPlan && colorPlan.ligand_chain_groups
            );
            var ionGroups = normalizeChainGroups(colorPlan && colorPlan.ion_chain_groups);
            var otherGroups = normalizeChainGroups(
                colorPlan && colorPlan.other_chain_groups
            );

            if (proteinGroups.length > 0) {{
                for (var i = 0; i < proteinGroups.length; i += 1) {{
                    addChainRepresentation(
                        structure,
                        proteinGroups[i],
                        'cartoon',
                        proteinPalette[i % proteinPalette.length],
                        1
                    );
                }}
            }} else {{
                structure
                    .component({{ selector: 'protein' }})
                    .representation({{ type: 'cartoon' }})
                    .color({{ color: '#2563eb' }});
            }}

            if (nucleicGroups.length > 0) {{
                for (var j = 0; j < nucleicGroups.length; j += 1) {{
                    addChainRepresentation(
                        structure,
                        nucleicGroups[j],
                        'cartoon',
                        '#f59e0b',
                        1
                    );
                }}
            }} else {{
                structure
                    .component({{ selector: 'nucleic' }})
                    .representation({{ type: 'cartoon' }})
                    .color({{ color: '#f59e0b' }});
            }}

            if (ligandGroups.length > 0) {{
                for (var k = 0; k < ligandGroups.length; k += 1) {{
                    var ligandComponent = addChainRepresentation(
                        structure,
                        ligandGroups[k],
                        'ball_and_stick',
                        ligandPalette[k % ligandPalette.length],
                        1
                    );
                    if (ligandName && k === 0 && ligandComponent) {{
                        ligandComponent.label({{ text: ligandName }});
                    }}
                }}
            }} else {{
                var fallbackLigand = structure.component({{ selector: 'ligand' }});
                if (ligandName) {{
                    fallbackLigand.label({{ text: ligandName }});
                }}
                fallbackLigand
                    .representation({{ type: 'ball_and_stick' }})
                    .color({{ color: '#db2777' }});
            }}

            if (ionGroups.length > 0) {{
                for (var m = 0; m < ionGroups.length; m += 1) {{
                    addChainRepresentation(
                        structure,
                        ionGroups[m],
                        'ball_and_stick',
                        '#14b8a6',
                        1
                    );
                }}
            }} else {{
                structure
                    .component({{ selector: 'ion' }})
                    .representation({{ type: 'ball_and_stick' }})
                    .color({{ color: '#14b8a6' }});
            }}

            structure
                .component({{ selector: 'branched' }})
                .representation({{ type: 'ball_and_stick' }})
                .color({{ color: '#84cc16' }});

            for (var n = 0; n < otherGroups.length; n += 1) {{
                addChainRepresentation(
                    structure,
                    otherGroups[n],
                    'ball_and_stick',
                    '#64748b',
                    1
                );
            }}
        }}

        function loadWithMvs(viewer) {{
            try {{
                var mvs = molstar && molstar.PluginExtensions && molstar.PluginExtensions.mvs;
                if (!mvs || !mvs.MVSData || typeof mvs.loadMVS !== 'function') {{
                    return Promise.resolve(false);
                }}

                var normalizedFormat = String(formatType || 'mmcif').toLowerCase();
                if (
                    normalizedFormat === 'bcif' &&
                    isInlineDataUrl &&
                    looksLikeTextCifDataUrl(dataUrl)
                ) {{
                    normalizedFormat = 'mmcif';
                }}
                var builder = mvs.MVSData.createBuilder();
                var structure = builder
                    .download({{ url: dataUrl }})
                    .parse({{ format: normalizedFormat }})
                    .modelStructure({{}});
                applyColorPlan(structure);

                var mvsData = builder.getState();
                return mvs
                    .loadMVS(
                        viewer.plugin,
                        mvsData,
                        {{ sourceUrl: null, sanityChecks: true, replaceExisting: false }}
                    )
                    .then(function() {{
                        container.setAttribute('data-refua-loaded-format', normalizedFormat);
                        return true;
                    }})
                    .catch(function(err) {{
                        console.warn('MVS load failed; falling back to direct structure load.', err);
                        return false;
                    }});
            }} catch (err) {{
                console.warn('MVS setup failed; falling back to direct structure load.', err);
                return Promise.resolve(false);
            }}
        }}

        function loadDirectly(viewer) {{
            if (typeof viewer.loadStructureFromUrl !== 'function') {{
                return Promise.reject(new Error('Mol* viewer does not support loadStructureFromUrl'));
            }}
            var normalizedFormat = String(formatType || 'mmcif').toLowerCase();
            var isBinary = normalizedFormat === 'bcif';
            var directLoadOptions = {{
                representationParams: {{
                    theme: {{ globalName: 'entity-id' }}
                }}
            }};
            if (
                normalizedFormat === 'bcif' &&
                isInlineDataUrl &&
                looksLikeTextCifDataUrl(dataUrl)
            ) {{
                normalizedFormat = 'mmcif';
                isBinary = false;
            }}
            return viewer
                .loadStructureFromUrl(
                    dataUrl,
                    normalizedFormat,
                    isBinary,
                    directLoadOptions
                )
                .then(function() {{
                    container.setAttribute('data-refua-loaded-format', normalizedFormat);
                    container.setAttribute('data-refua-loaded-path', 'direct');
                }});
        }}

        molstar.Viewer
            .create('{viewer_id}', {{
                layoutIsExpanded: false,
                layoutShowControls: {controls_js},
                layoutShowRemoteState: false,
                layoutShowSequence: true,
                layoutShowLog: false,
                layoutShowLeftPanel: {controls_js},
                viewportShowExpand: {controls_js},
                viewportShowSelectionMode: false,
                viewportShowAnimation: {controls_js},
                viewportShowTrajectoryControls: {controls_js},
                disabledExtensions: ['volumes-and-segmentations'],
            }})
            .then(function(viewer) {{
                return Promise.resolve(loadWithMvs(viewer)).then(function(loadedWithMvs) {{
                    if (loadedWithMvs) {{
                        container.setAttribute('data-refua-loaded-path', 'mvs');
                        return viewer;
                    }}
                    return loadDirectly(viewer).then(function() {{ return viewer; }});
                }});
            }})
            .then(function(viewer) {{
                loadingEl.style.display = 'none';
                viewer.plugin.managers.camera.reset();
            }})
            .catch(function(err) {{
                console.error('Failed to load structure:', err);
                loadingEl.textContent = 'Failed to load structure';
                loadingEl.style.display = 'block';
            }});
    }}

    loadMolstar(initViewer);
}})();
</script>
"""

        return f"""
<style>
#{viewer_id}-container {{
    width: {safe_width}px;
    height: {safe_height}px;
    position: relative;
    border: 1px solid #dbe3ec;
    border-radius: 12px;
    overflow: hidden;
    background: {safe_bg};
}}
#{viewer_id} {{
    width: 100%;
    height: 100%;
}}
.molstar-loading {{
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: #6b7280;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 12px;
    letter-spacing: 0.02em;
}}
</style>

{f'<link rel="stylesheet" href="{MOLSTAR_CSS_CDN}">' if include_scripts else ''}

<div id="{viewer_id}-container" {data_attrs}>
    <div id="{viewer_id}" data-refua-molstar-viewer="1"></div>
    <div class="molstar-loading" id="{viewer_id}-loading" data-refua-molstar-loading="1">Loading structure...</div>
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
        """Display the Mol* viewer in the notebook."""
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
    def from_refua_result(
        cls,
        result: Any,
        ligand_name: Optional[str] = None,
        **kwargs,
    ) -> "MolstarView":
        """Create a MolstarView from a Refua Complex folding result.

        Parameters
        ----------
        result : Any
            A Refua FoldedComplex result object with a to_bcif() method.
        ligand_name : str, optional
            Name of the ligand to highlight.
        **kwargs
            Additional arguments passed to MolstarView constructor.

        Returns
        -------
        MolstarView
            A viewer instance configured with the structure.
        """
        bcif_data = result.to_bcif()
        return cls(bcif_data=bcif_data, ligand_name=ligand_name, **kwargs)

    @classmethod
    def from_pdb_id(cls, pdb_id: str, **kwargs) -> "MolstarView":
        """Create a MolstarView from a PDB ID.

        Parameters
        ----------
        pdb_id : str
            A 4-character PDB ID (e.g., "1TIM", "6LU7").
        **kwargs
            Additional arguments passed to MolstarView constructor.

        Returns
        -------
        MolstarView
            A viewer instance that will load the structure from RCSB.
        """
        url = f"https://files.rcsb.org/download/{pdb_id.upper()}.cif"
        return cls(url=url, **kwargs)
