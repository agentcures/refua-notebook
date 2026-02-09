"""Tests for affinity prediction rendering."""

from dataclasses import dataclass
import re

from refua_notebook.extension import (
    _REFUA_MIME_REGISTRY,
    _REFUA_TYPE_REGISTRY,
    _get_affinity_repr_html,
    _get_affinity_repr_mime,
)
from refua_notebook.mime import REFUA_MIME_TYPE
from refua_notebook.widgets.affinity import AffinityView


@dataclass
class MockAffinity:
    """Simple dataclass used to emulate Refua affinity predictions."""

    ic50: float
    binding_probability: float
    ic50_1: float
    binding_probability_1: float
    ic50_2: float
    binding_probability_2: float


def test_affinity_view_renders_styled_metrics():
    """Render affinity values as a styled card."""
    affinity = MockAffinity(
        ic50=-3.5756607055,
        binding_probability=0.9542990922,
        ic50_1=-1.5654917955,
        binding_probability_1=0.9272315502,
        ic50_2=-3.0112311,
        binding_probability_2=0.9812091,
    )
    html = AffinityView(affinity).to_html()

    assert 'data-refua-widget="affinity"' in html
    assert "Binding Affinity" in html
    assert "Overall" in html
    assert "Model #1" in html
    assert "Model #2" in html
    assert "95.4%" in html
    assert "tone-good" in html

    overall_panel_match = re.search(
        r'<section class="affinity-panel panel-overall" role="tabpanel">(.*?)</section>',
        html,
        flags=re.DOTALL,
    )
    model1_panel_match = re.search(
        r'<section class="affinity-panel panel-model1" role="tabpanel">(.*?)</section>',
        html,
        flags=re.DOTALL,
    )
    model2_panel_match = re.search(
        r'<section class="affinity-panel panel-model2" role="tabpanel">(.*?)</section>',
        html,
        flags=re.DOTALL,
    )

    assert overall_panel_match is not None
    assert model1_panel_match is not None
    assert model2_panel_match is not None

    overall_panel = overall_panel_match.group(1)
    model1_panel = model1_panel_match.group(1)
    model2_panel = model2_panel_match.group(1)

    assert "IC50</span>" in overall_panel
    assert "Binding Probability</span>" in overall_panel
    assert "IC50 #1" not in overall_panel
    assert "IC50 #2" not in overall_panel

    assert "IC50 #1" in model1_panel
    assert "Binding Probability #1" in model1_panel
    assert "IC50 #2" not in model1_panel

    assert "IC50 #2" in model2_panel
    assert "Binding Probability #2" in model2_panel
    assert "IC50 #1" not in model2_panel


def test_affinity_view_mimebundle_includes_refua_payload():
    """Ensure custom MIME bundle is emitted for JupyterLab rendering."""
    view = AffinityView({"ic50": -3.4, "binding_probability": 0.91})
    bundle = view._repr_mimebundle_()

    assert REFUA_MIME_TYPE in bundle
    assert bundle[REFUA_MIME_TYPE]["html"] == bundle["text/html"]
    assert "<script>" not in bundle["text/html"]


def test_affinity_extension_helpers_render_structured_html():
    """Affinity helper functions should produce the widget HTML."""

    class SlotAffinity:
        __slots__ = ("ic50", "binding_probability")

        def __init__(self, ic50: float, binding_probability: float):
            self.ic50 = ic50
            self.binding_probability = binding_probability

    affinity = SlotAffinity(-2.8, 0.88)
    html = _get_affinity_repr_html(affinity)
    mime = _get_affinity_repr_mime(affinity)

    assert 'data-refua-widget="affinity"' in html
    assert "Binding Probability" in html
    assert 'data-refua-widget="affinity"' in mime["html"]


def test_affinity_prediction_registered_for_formatter_dispatch():
    """Deferred formatter registry should include affinity prediction type."""
    assert (
        "refua.boltz.api",
        "AffinityPrediction",
        _get_affinity_repr_html,
    ) in _REFUA_TYPE_REGISTRY
    assert (
        "refua.unified",
        "AffinityPrediction",
        _get_affinity_repr_html,
    ) in _REFUA_TYPE_REGISTRY
    assert (
        "refua",
        "AffinityPrediction",
        _get_affinity_repr_html,
    ) in _REFUA_TYPE_REGISTRY
    assert (
        "refua.boltz.api",
        "AffinityPrediction",
        _get_affinity_repr_mime,
    ) in _REFUA_MIME_REGISTRY
    assert (
        "refua.unified",
        "AffinityPrediction",
        _get_affinity_repr_mime,
    ) in _REFUA_MIME_REGISTRY
    assert (
        "refua",
        "AffinityPrediction",
        _get_affinity_repr_mime,
    ) in _REFUA_MIME_REGISTRY
