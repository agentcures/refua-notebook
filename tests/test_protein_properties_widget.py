"""Tests for ProteinPropertiesView widget."""

from refua_notebook.widgets.protein_properties import (
    ProteinPropertiesView,
    _normalize_key,
)


class TestNormalizeKey:
    """Tests for protein property key normalization."""

    def test_alias_mapping(self):
        assert _normalize_key("pi") == "isoelectric_point"
        assert _normalize_key("mw") == "molecular_weight"
        assert _normalize_key("charge") == "net_charge_ph_7_4"

    def test_amino_acid_alias_mapping(self):
        assert _normalize_key("aa_a_count") == "count_ala"
        assert _normalize_key("a_fraction") == "fraction_ala"


class TestProteinPropertiesView:
    """Tests for ProteinPropertiesView."""

    def test_basic_creation(self):
        props = {"length": 128, "instability_index": 31.2}
        view = ProteinPropertiesView(props)

        assert view.properties == props
        assert view.title == "Protein Properties"

    def test_html_generation(self):
        props = {"length": 128, "instability_index": 31.2, "is_stable": 1}
        view = ProteinPropertiesView(props)
        html = view.to_html()

        assert 'data-refua-widget="protein-properties"' in html
        assert "Length" in html
        assert "Instability Index" in html
        assert "Predicted Stable" in html
        assert "128" in html

    def test_category_grouping(self):
        props = {
            "length": 128,
            "net_charge_ph_7_4": -4.1,
            "helix_fraction": 0.42,
            "flexibility_mean": 0.55,
            "hydrophobic_residue_fraction": 0.38,
            "count_ala": 11,
        }
        view = ProteinPropertiesView(props, show_categories=True)
        html = view.to_html()

        assert 'data-admet-tab="core_metrics"' in html
        assert 'data-admet-tab="charge_profile"' in html
        assert 'data-admet-tab="secondary_structure"' in html
        assert 'data-admet-tab="flexibility_absorbance"' in html
        assert 'data-admet-tab="composition"' in html
        assert 'data-admet-tab="amino_acids"' in html

    def test_other_tab_for_unknown_properties(self):
        known_html = ProteinPropertiesView(
            {"length": 128}, show_categories=True
        ).to_html()
        unknown_html = ProteinPropertiesView(
            {"custom_metric": 42}, show_categories=True
        ).to_html()

        assert 'data-admet-tab="other"' not in known_html
        assert 'data-admet-tab="other"' in unknown_html

    def test_rich_tooltip_content_present(self):
        view = ProteinPropertiesView({"instability_index": 31.2})
        html = view.to_html()

        assert 'data-admet-tooltip="1"' in html
        assert "What" in html
        assert "Why It Matters" in html
        assert "Protein-Engineering Levers" in html

    def test_status_classes_in_html(self):
        view = ProteinPropertiesView(
            {
                "instability_index": 28.0,
                "is_stable": 0,
            }
        )
        html = view.to_html()

        assert "admet-status-optimal" in html
        assert "admet-status-danger" in html

    def test_developability_categories_and_tooltips(self):
        view = ProteinPropertiesView(
            {
                "deamidation_high_risk_motif_count": 2,
                "antibody_liability_score": 22,
                "peptide_low_hydrophilic_flag": 1,
                "peptide_linear_liability_score": 18,
            }
        )
        html = view.to_html()

        assert 'data-admet-tab="antibody_liability"' in html
        assert 'data-admet-tab="peptide_liability"' in html
        assert "Deamidation Motifs (High Risk)" in html
        assert "Antibody Liability Score" in html
        assert "Peptide Linear Liability Score" in html
        assert "Weighted antibody liability score from sequence motif counts." in html
        assert (
            "Peptide liability scores summarize multiple instability and cleavage liabilities"
            in html
        )
        assert "admet-status-danger" in html
