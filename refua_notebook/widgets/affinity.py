"""Affinity prediction visualization widget for Jupyter notebooks.

This module provides the AffinityView class for displaying affinity prediction
objects inline in Jupyter notebooks.
"""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import asdict, is_dataclass
from types import ModuleType
from typing import Any, Mapping, Optional

from refua_notebook.mime import REFUA_MIME_TYPE

_ipython_display_module: ModuleType | None
try:
    import IPython.display as _ipython_display_module
except ImportError:
    _ipython_display_module = None


class AffinityView:
    """Jupyter widget for displaying affinity prediction values."""

    _FALLBACK_FIELDS = (
        "ic50",
        "binding_probability",
        "value",
        "probability",
        "ic50_1",
        "binding_probability_1",
        "value1",
        "probability1",
        "ic50_2",
        "binding_probability_2",
        "value2",
        "probability2",
    )

    _PRIORITY_FIELDS = (
        "ic50",
        "binding_probability",
        "value",
        "probability",
        "ic50_1",
        "binding_probability_1",
        "value1",
        "probability1",
        "ic50_2",
        "binding_probability_2",
        "value2",
        "probability2",
    )
    _TAB_SECTIONS = (
        ("overall", "Overall", "No aggregate affinity metrics available."),
        ("model1", "Model #1", "No Model #1 metrics available."),
        ("model2", "Model #2", "No Model #2 metrics available."),
    )
    _MODEL_INDEX_TOKEN_RE = re.compile(r"(?:^|_)(?:model|head|ensemble)_?([12])(?:_|$)")
    _COMPACT_MODEL_KEY_RE = re.compile(
        r"^(?:ic50|binding_probability|value|probability|confidence)([12])$"
    )

    def __init__(self, affinity: Any, title: str = "Binding Affinity"):
        self.affinity = self._coerce_affinity(affinity)
        self.title = title or "Binding Affinity"
        self._element_id = f"affinity-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _coerce_properties(properties: Any) -> Optional[dict[str, Any]]:
        if properties is None:
            return None
        if isinstance(properties, Mapping):
            return dict(properties)
        if is_dataclass(properties) and not isinstance(properties, type):
            try:
                return {
                    str(k): v
                    for k, v in asdict(properties).items()
                    if not str(k).startswith("_")
                }
            except Exception:
                pass
        if hasattr(properties, "__dict__") and properties.__dict__:
            return {
                str(k): v
                for k, v in properties.__dict__.items()
                if not str(k).startswith("_")
            }
        if hasattr(properties, "__slots__"):
            slots = properties.__slots__
            if isinstance(slots, str):
                slots = (slots,)
            result: dict[str, Any] = {}
            for key in slots:
                key_str = str(key)
                if key_str.startswith("_"):
                    continue
                if hasattr(properties, key):
                    result[key_str] = getattr(properties, key)
            if result:
                return result
        return None

    @classmethod
    def _coerce_affinity(cls, affinity: Any) -> dict[str, Any]:
        raw = cls._coerce_properties(affinity) or {}
        if not raw:
            for attr in cls._FALLBACK_FIELDS:
                if not hasattr(affinity, attr):
                    continue
                try:
                    value = getattr(affinity, attr)
                except Exception:
                    continue
                if value is not None:
                    raw[attr] = value

        return {
            str(key): value
            for key, value in raw.items()
            if not str(key).startswith("_")
            and value is not None
            and not (isinstance(value, str) and not value.strip())
        }

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _format_label(cls, key: str) -> str:
        parts = [part for part in key.split("_") if part]
        if not parts:
            return "Metric"
        normalized: list[str] = []
        for part in parts:
            part_lower = part.lower()
            if part_lower == "ic50":
                normalized.append("IC50")
            elif part_lower in {"kd", "ki"}:
                normalized.append(part.upper())
            elif part.isdigit():
                normalized.append(f"#{part}")
            else:
                normalized.append(part.capitalize())
        return " ".join(normalized)

    @classmethod
    def _format_value(cls, key: str, value: Any) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        number = cls._to_float(value)
        if number is None:
            return str(value)

        key_lower = key.lower()
        if (
            "probability" in key_lower
            or key_lower.startswith("prob")
            or "confidence" in key_lower
        ):
            if 0.0 <= number <= 1.0:
                return f"{number:.1%}"
            return f"{number:.2f}"
        if "ic50" in key_lower or key_lower == "value":
            return f"{number:.3f}"
        if number != 0.0 and abs(number) < 0.01:
            return f"{number:.2e}"
        if abs(number) >= 100.0:
            return f"{number:,.2f}"
        return f"{number:.3f}"

    @classmethod
    def _tone_for_metric(cls, key: str, value: Any) -> str:
        number = cls._to_float(value)
        if number is None:
            return "neutral"

        key_lower = key.lower()
        if (
            "probability" in key_lower
            or key_lower.startswith("prob")
            or "confidence" in key_lower
        ):
            if number >= 0.8:
                return "good"
            if number >= 0.5:
                return "warn"
            return "risk"
        if "ic50" in key_lower or key_lower == "value":
            if number <= -3.0:
                return "good"
            if number <= -1.0:
                return "warn"
            return "risk"
        return "neutral"

    @classmethod
    def _sort_keys(cls, keys: list[str]) -> list[str]:
        priority = {key: idx for idx, key in enumerate(cls._PRIORITY_FIELDS)}

        return sorted(
            keys,
            key=lambda key: (
                priority.get(key, len(priority)),
                key.lower(),
            ),
        )

    @classmethod
    def _tab_for_key(cls, key: str) -> str:
        normalized = key.strip().lower()
        if normalized.endswith("_1"):
            return "model1"
        if normalized.endswith("_2"):
            return "model2"

        compact_match = cls._COMPACT_MODEL_KEY_RE.match(normalized)
        if compact_match:
            return f"model{compact_match.group(1)}"

        token_match = cls._MODEL_INDEX_TOKEN_RE.search(normalized)
        if token_match:
            return f"model{token_match.group(1)}"

        return "overall"

    def _partition_keys(self) -> dict[str, list[str]]:
        tab_map: dict[str, list[str]] = {
            section_key: [] for section_key, _, _ in self._TAB_SECTIONS
        }
        for key in self.affinity.keys():
            tab_key = self._tab_for_key(key)
            if tab_key not in tab_map:
                tab_key = "overall"
            tab_map[tab_key].append(key)
        return tab_map

    def _render_rows_html(self, keys: list[str], empty_message: str) -> str:
        if not keys:
            safe_message = html.escape(empty_message)
            return f'<div class="affinity-empty">{safe_message}</div>'

        rows = []
        for key in self._sort_keys(keys):
            value = self.affinity[key]
            label = html.escape(self._format_label(key))
            formatted = html.escape(self._format_value(key, value))
            tone = self._tone_for_metric(key, value)
            rows.append(f"""
<div class="affinity-row">
    <span class="affinity-label">{label}</span>
    <span class="affinity-value tone-{tone}">{formatted}</span>
</div>
""")
        return "".join(rows)

    def _render_tabbed_rows_html(self, tab_ids: Mapping[str, str]) -> str:
        sections = self._partition_keys()
        radio_name = html.escape(f"{self._element_id}-tabs")

        inputs = []
        labels = []
        panels = []
        for index, (section_key, section_label, empty_message) in enumerate(
            self._TAB_SECTIONS
        ):
            tab_id = tab_ids[section_key]
            safe_tab_id = html.escape(tab_id)
            safe_label = html.escape(section_label)
            checked = ' checked="checked"' if index == 0 else ""
            inputs.append(
                f'<input type="radio" class="affinity-tab-input" id="{safe_tab_id}" name="{radio_name}"{checked}>'
            )
            labels.append(
                f'<label class="affinity-tab" for="{safe_tab_id}" role="tab">{safe_label}</label>'
            )

            panel_rows_html = self._render_rows_html(
                sections.get(section_key, []), empty_message
            )
            panels.append(
                f'<section class="affinity-panel panel-{section_key}" role="tabpanel">{panel_rows_html}</section>'
            )

        return (
            "".join(inputs)
            + f'<div class="affinity-tabs" role="tablist">{"".join(labels)}</div>'
            + f'<div class="affinity-panels">{"".join(panels)}</div>'
        )

    def _render_html(self) -> str:
        root_id = html.escape(self._element_id)
        title = html.escape(self.title)
        tab_ids = {
            section_key: f"{self._element_id}-tab-{section_key}"
            for section_key, _, _ in self._TAB_SECTIONS
        }
        rows_html = self._render_tabbed_rows_html(tab_ids)
        overall_tab = tab_ids["overall"]
        model1_tab = tab_ids["model1"]
        model2_tab = tab_ids["model2"]
        return f"""
<div id="{root_id}" class="affinity-view" data-refua-widget="affinity">
<style>
#{root_id} {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    border: 1px solid #dbe4f0;
    border-radius: 14px;
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    box-shadow: 0 16px 30px rgba(15, 23, 42, 0.08);
    overflow: hidden;
    max-width: 560px;
}}
#{root_id} .affinity-header {{
    background: linear-gradient(120deg, #0f172a 0%, #1e293b 100%);
    color: #f8fafc;
    padding: 12px 14px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
#{root_id} .affinity-tab-input {{
    position: absolute;
    opacity: 0;
    pointer-events: none;
}}
#{root_id} .affinity-tabs {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 12px;
    border-bottom: 1px solid #dbe4f0;
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}}
#{root_id} .affinity-tab {{
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.01em;
    color: #334155;
    border: 1px solid #cbd5e1;
    background: #ffffff;
    cursor: pointer;
    user-select: none;
}}
#{root_id} .affinity-tab:hover {{
    background: #eff6ff;
    border-color: #93c5fd;
}}
#{root_id} .affinity-panels {{
    background: #ffffff;
}}
#{root_id} .affinity-panel {{
    display: none;
}}
#{root_id} #{overall_tab}:checked ~ .affinity-tabs label[for="{overall_tab}"] {{
    color: #1d4ed8;
    border-color: #93c5fd;
    background: #dbeafe;
}}
#{root_id} #{model1_tab}:checked ~ .affinity-tabs label[for="{model1_tab}"] {{
    color: #1d4ed8;
    border-color: #93c5fd;
    background: #dbeafe;
}}
#{root_id} #{model2_tab}:checked ~ .affinity-tabs label[for="{model2_tab}"] {{
    color: #1d4ed8;
    border-color: #93c5fd;
    background: #dbeafe;
}}
#{root_id} #{overall_tab}:checked ~ .affinity-panels .panel-overall {{
    display: block;
}}
#{root_id} #{model1_tab}:checked ~ .affinity-panels .panel-model1 {{
    display: block;
}}
#{root_id} #{model2_tab}:checked ~ .affinity-panels .panel-model2 {{
    display: block;
}}
#{root_id} .affinity-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 11px 14px;
    border-bottom: 1px solid #e2e8f0;
}}
#{root_id} .affinity-row:last-child {{
    border-bottom: 0;
}}
#{root_id} .affinity-label {{
    color: #334155;
    font-size: 13px;
    font-weight: 600;
}}
#{root_id} .affinity-value {{
    font-family: "SFMono-Regular", Menlo, Consolas, monospace;
    font-size: 12px;
    font-weight: 700;
    border-radius: 999px;
    padding: 3px 10px;
    white-space: nowrap;
}}
#{root_id} .affinity-value.tone-good {{
    color: #166534;
    background: #dcfce7;
}}
#{root_id} .affinity-value.tone-warn {{
    color: #92400e;
    background: #fef3c7;
}}
#{root_id} .affinity-value.tone-risk {{
    color: #991b1b;
    background: #fee2e2;
}}
#{root_id} .affinity-value.tone-neutral {{
    color: #1e3a8a;
    background: #dbeafe;
}}
#{root_id} .affinity-empty {{
    padding: 16px 14px;
    color: #64748b;
    font-size: 12px;
}}
@media (max-width: 620px) {{
    #{root_id} {{
        max-width: 100%;
    }}
    #{root_id} .affinity-tabs {{
        gap: 6px;
    }}
    #{root_id} .affinity-tab {{
        font-size: 10px;
        padding: 5px 9px;
    }}
}}
</style>
<div class="affinity-header">{title}</div>
{rows_html}
</div>
"""

    def _repr_html_(self) -> str:
        """IPython HTML representation for inline display."""
        return self._render_html()

    def _repr_mimebundle_(self, include=None, exclude=None):
        """Provide a custom MIME bundle for JupyterLab rendering."""
        html_output = self._render_html()
        return {
            "text/html": html_output,
            REFUA_MIME_TYPE: {"html": html_output},
        }

    def display(self) -> None:
        """Display the affinity view in the notebook."""
        if _ipython_display_module is not None:
            _ipython_display_module.display(
                _ipython_display_module.HTML(self._render_html())
            )
        else:
            print(self._render_html())

    def to_html(self, include_scripts: bool = True) -> str:
        """Return the HTML representation as a string."""
        del include_scripts
        return self._render_html()
