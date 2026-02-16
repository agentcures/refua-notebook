"""Tests for Refua custom MIME bundle rendering."""

from refua_notebook.mime import REFUA_MIME_TYPE
from refua_notebook.widgets.admet import ADMETView
from refua_notebook.widgets.complex import ComplexView
from refua_notebook.widgets.molstar import MOLSTAR_CSS_CDN, MOLSTAR_JS_CDN, MolstarView
from refua_notebook.widgets.protein import ProteinView
from refua_notebook.widgets.protein_properties import ProteinPropertiesView
from refua_notebook.widgets.sm import SMView
from refua_notebook.widgets.smiles import SMILESDRAWER_CDN, SmilesView


class TestMimeBundle:
    """Validate custom MIME bundles are script-free and data-driven."""

    def test_smiles_mimebundle(self):
        view = SmilesView("CCO")
        bundle = view._repr_mimebundle_()

        assert REFUA_MIME_TYPE in bundle
        html = bundle[REFUA_MIME_TYPE]["html"]
        assert 'data-refua-smiles="1"' in html
        assert SMILESDRAWER_CDN not in html
        assert "<script>" not in html

    def test_molstar_mimebundle(self):
        view = MolstarView(url="https://files.rcsb.org/download/1TIM.cif")
        bundle = view._repr_mimebundle_()

        assert REFUA_MIME_TYPE in bundle
        html = bundle[REFUA_MIME_TYPE]["html"]
        assert 'data-refua-molstar="1"' in html
        assert "1TIM.cif" in html
        assert MOLSTAR_JS_CDN not in html
        assert MOLSTAR_CSS_CDN not in html
        assert "<script>" not in html

    def test_complex_mimebundle(self):
        components = [
            {"type": "protein", "name": "Target", "sequence": "MKTAYIAK"},
            {"type": "ligand", "name": "Drug", "smiles": "CCO"},
        ]
        view = ComplexView(name="Test", components=components)
        bundle = view._repr_mimebundle_()

        assert REFUA_MIME_TYPE in bundle
        html = bundle[REFUA_MIME_TYPE]["html"]
        assert 'data-refua-widget="complex"' in html
        assert "<script>" not in html

    def test_protein_mimebundle(self):
        view = ProteinView(sequence="MKTAYIAK", name="Protein", bcif_data=b"data")
        bundle = view._repr_mimebundle_()

        assert REFUA_MIME_TYPE in bundle
        html = bundle[REFUA_MIME_TYPE]["html"]
        assert "<script>" not in html

    def test_sm_view_mimebundle(self):
        view = SMView(smiles="CCO", name="Ligand", properties={"logP": 2.1})
        bundle = view._repr_mimebundle_()

        assert REFUA_MIME_TYPE in bundle
        html = bundle[REFUA_MIME_TYPE]["html"]
        assert "<script>" not in html

    def test_admet_mimebundle(self):
        view = ADMETView({"logP": 2.1, "tpsa": 45.0}, title="Props")
        bundle = view._repr_mimebundle_()

        assert REFUA_MIME_TYPE in bundle
        html = bundle[REFUA_MIME_TYPE]["html"]
        assert "Props" in html

    def test_protein_properties_mimebundle(self):
        view = ProteinPropertiesView(
            {"length": 128, "instability_index": 31.2},
            title="Protein Props",
        )
        bundle = view._repr_mimebundle_()

        assert REFUA_MIME_TYPE in bundle
        html = bundle[REFUA_MIME_TYPE]["html"]
        assert "Protein Props" in html
        assert 'data-refua-widget="protein-properties"' in html
