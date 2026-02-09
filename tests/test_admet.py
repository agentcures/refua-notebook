"""Tests for ADMETView widget."""

from refua_notebook.widgets.admet import (
    ADMET_THRESHOLDS,
    ADMETView,
    _format_value,
    _get_status_class,
    _normalize_key,
)


class TestADMETThresholds:
    """Tests for ADMET threshold definitions."""

    def test_all_categories_defined(self):
        """Verify all expected categories are present."""
        categories = {t.category for t in ADMET_THRESHOLDS.values()}
        expected = {"absorption", "distribution", "metabolism", "excretion", "toxicity"}
        assert expected.issubset(categories)

    def test_thresholds_have_valid_ranges(self):
        """Verify threshold ranges are valid."""
        for key, threshold in ADMET_THRESHOLDS.items():
            opt_low, opt_high = threshold.optimal_range
            warn_low, warn_high = threshold.warning_range
            # Warning range should be equal to or wider than optimal
            assert warn_low <= opt_low, f"{key}: warning low should be <= optimal low"
            assert (
                warn_high >= opt_high
            ), f"{key}: warning high should be >= optimal high"


class TestStatusClassification:
    """Tests for property status classification."""

    def test_optimal_status(self):
        """Test optimal status for logP."""
        threshold = ADMET_THRESHOLDS["logP"]
        assert _get_status_class(2.0, threshold) == "optimal"
        assert _get_status_class(0.5, threshold) == "optimal"

    def test_warning_status(self):
        """Test warning status for logP."""
        threshold = ADMET_THRESHOLDS["logP"]
        # Value in warning range but not optimal
        assert _get_status_class(4.0, threshold) == "warning"
        assert _get_status_class(-0.3, threshold) == "warning"

    def test_danger_status(self):
        """Test danger status for logP."""
        threshold = ADMET_THRESHOLDS["logP"]
        assert _get_status_class(6.0, threshold) == "danger"
        assert _get_status_class(-1.0, threshold) == "danger"

    def test_herg_status(self):
        """Test hERG inhibition status."""
        threshold = ADMET_THRESHOLDS["herg"]
        assert _get_status_class(0.1, threshold) == "optimal"  # Low inhibition = good
        assert _get_status_class(0.4, threshold) == "warning"
        assert _get_status_class(0.8, threshold) == "danger"


class TestFormatValue:
    """Tests for value formatting."""

    def test_format_float(self):
        """Test formatting float values."""
        assert _format_value(2.5) == "2.5"
        assert _format_value(0.123456789) == "0.123"

    def test_format_bool(self):
        """Test formatting boolean values."""
        assert _format_value(True) == "Yes"
        assert _format_value(False) == "No"

    def test_format_none(self):
        """Test formatting None."""
        assert _format_value(None) == "N/A"

    def test_format_scientific(self):
        """Test scientific notation for small/large values."""
        result = _format_value(0.0001)
        assert "e" in result.lower()

        result = _format_value(100000.0)
        assert "e" in result.lower()

    def test_format_nan(self):
        """Test formatting NaN."""
        assert _format_value(float("nan")) == "N/A"

    def test_format_inf(self):
        """Test formatting infinity."""
        assert _format_value(float("inf")) == "N/A"


class TestNormalizeKey:
    """Tests for key normalization."""

    def test_basic_normalization(self):
        """Test basic key normalization."""
        assert _normalize_key("logP") == "logP"
        assert _normalize_key("LogP") == "logP"
        assert _normalize_key("LOGP") == "logP"
        assert _normalize_key("log_p") == "logP"

    def test_alias_mapping(self):
        """Test alias mapping."""
        assert _normalize_key("caco_2") == "caco2"
        assert _normalize_key("blood_brain_barrier") == "bbb"
        assert _normalize_key("herg_inhibition") == "herg"
        assert _normalize_key("ames_mutagenicity") == "ames"

    def test_dataset_specific_aliases(self):
        """Test dataset-specific name aliases."""
        assert _normalize_key("lipophilicity_astrazeneca") == "logP"
        assert _normalize_key("solubility_aqsoldb") == "solubility"
        assert _normalize_key("bbb_martins") == "bbb"


class TestADMETView:
    """Tests for ADMETView widget."""

    def test_basic_creation(self):
        """Test basic widget creation."""
        props = {"logP": 2.5, "solubility": -3.2}
        view = ADMETView(props)
        assert view.properties == props
        assert view.title == "ADMET Properties"

    def test_custom_title(self):
        """Test custom title."""
        view = ADMETView({}, title="Custom Title")
        assert view.title == "Custom Title"

    def test_html_generation(self):
        """Test HTML generation."""
        props = {"logP": 2.5, "herg": 0.1}
        view = ADMETView(props)
        html = view.to_html()

        assert "admet-view" in html
        assert "LogP" in html
        assert "2.5" in html
        assert "hERG" in html
        assert "0.1" in html

    def test_repr_html(self):
        """Test _repr_html_ method."""
        props = {"logP": 2.5}
        view = ADMETView(props)
        assert view._repr_html_() == view.to_html()

    def test_category_grouping(self):
        """Test category grouping."""
        props = {
            "qed": 0.66,  # drug-likeness
            "peoe_vsa1": 12.4,  # surface/electronic
            "chi0": 28.0,  # topology
            "num_h_donors": 1,  # composition/count
            "fr_halogen": 1,  # fragment
            "herg": 0.1,  # admet profile
        }
        view = ADMETView(props, show_categories=True)
        html = view.to_html()

        assert "Drug-Likeness" in html
        assert "Surface &amp; Electronics" in html
        assert "Topology &amp; Shape" in html
        assert "Composition &amp; Counts" in html
        assert "Fragments &amp; Alerts" in html
        assert "ADMET Profile" in html
        assert 'data-admet-tab="all"' not in html
        assert 'data-admet-tab="druglikeness"' in html
        assert 'data-admet-tab="surface_electronics"' in html
        assert 'data-admet-tab="topology_shape"' in html
        assert 'data-admet-tab="composition_counts"' in html
        assert 'data-admet-tab="fragments_alerts"' in html
        assert 'data-admet-tab="admet_profile"' in html

    def test_category_tabs_show_core_five_types(self):
        """Always show the five core property-type tabs when grouping is enabled."""
        view = ADMETView({"logP": 2.5}, show_categories=True)
        html = view.to_html()

        assert 'data-admet-tab="druglikeness"' in html
        assert 'data-admet-tab="surface_electronics"' in html
        assert 'data-admet-tab="topology_shape"' in html
        assert 'data-admet-tab="composition_counts"' in html
        assert 'data-admet-tab="fragments_alerts"' in html
        assert 'data-admet-panel="druglikeness"' in html
        assert 'data-admet-panel="surface_electronics"' in html
        assert 'data-admet-panel="topology_shape"' in html
        assert 'data-admet-panel="composition_counts"' in html
        assert 'data-admet-panel="fragments_alerts"' in html

    def test_other_tab_shown_only_for_unknown_properties(self):
        """Unknown properties should appear under an explicit Other tab."""
        known_html = ADMETView({"logP": 2.5}, show_categories=True).to_html()
        unknown_html = ADMETView(
            {"custom_property": 42}, show_categories=True
        ).to_html()

        assert 'data-admet-tab="other"' not in known_html
        assert 'data-admet-tab="other"' in unknown_html
        assert 'data-admet-panel="other"' in unknown_html

    def test_no_category_grouping(self):
        """Test without category grouping."""
        props = {"logP": 2.5}
        view = ADMETView(props, show_categories=False)
        html = view.to_html()

        assert 'data-admet-tab="' not in html
        assert "Drug-Likeness" not in html

    def test_compact_mode(self):
        """Test compact display mode."""
        props = {"logP": 2.5}
        view = ADMETView(props, compact=True)
        html = view.to_html()

        assert "admet-compact" in html

    def test_status_colors_in_html(self):
        """Test that status classes appear in HTML."""
        props = {
            "logP": 2.0,  # optimal
            "herg": 0.7,  # danger
        }
        view = ADMETView(props)
        html = view.to_html()

        assert "admet-status-optimal" in html
        assert "admet-status-danger" in html

    def test_unknown_property(self):
        """Test handling of unknown properties."""
        props = {"custom_property": 42}
        view = ADMETView(props)
        html = view.to_html()

        assert "Custom Property" in html
        assert "42" in html
        assert "admet-status-unknown" in html

    def test_html_escaping(self):
        """Test that HTML is properly escaped."""
        props = {"logP": 2.5}
        view = ADMETView(props, title="<script>alert('xss')</script>")
        html = view.to_html()

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_empty_properties(self):
        """Test widget with no properties."""
        view = ADMETView({})
        html = view.to_html()

        assert "admet-view" in html
        # Should still have header
        assert "ADMET Properties" in html

    def test_filter_input_present(self):
        """Test property name filter input is rendered."""
        view = ADMETView({"logP": 2.5})
        html = view.to_html()

        assert 'data-refua-widget="admet"' in html
        assert 'data-admet-filter="1"' in html

    def test_row_filter_metadata_present(self):
        """Test rows include metadata for client-side filtering."""
        view = ADMETView({"logP": 2.5})
        html = view.to_html()

        assert 'data-admet-row="1"' in html
        assert 'data-admet-search="logp logp"' in html

    def test_rich_tooltip_content_present(self):
        """Test richer medicinal-chem tooltip markup is rendered."""
        view = ADMETView({"logP": 2.5})
        html = view.to_html()

        assert 'data-admet-tooltip="1"' in html
        assert "Why It Matters" in html
        assert "Target Window" in html
        assert "Medicinal-Chem Levers" in html

    def test_unknown_property_tooltip_fallback(self):
        """Test unknown properties still render helpful tooltip content."""
        view = ADMETView({"custom_property": 42})
        html = view.to_html()

        assert "No calibrated threshold" in html
        assert "computed molecular descriptor" in html

    def test_descriptor_tooltip_has_family_specific_context(self):
        """Known descriptor families should emit non-generic semantic guidance."""
        html = ADMETView({"peoe_vsa1": 12.4}).to_html()
        assert "partial-charge bin" in html
        assert "charge-surface distribution" in html


class TestADMETViewPropertyRows:
    """Tests for property row building."""

    def test_property_rows_structure(self):
        """Test that property rows have expected structure."""
        props = {"logP": 2.5, "herg": 0.1}
        view = ADMETView(props)
        rows = view._build_property_rows()

        assert len(rows) == 2
        for row in rows:
            assert "key" in row
            assert "value" in row
            assert "formatted_value" in row
            assert "label" in row
            assert "status" in row
            assert "category" in row

    def test_known_property_metadata(self):
        """Test that known properties get proper metadata."""
        props = {"logP": 2.5}
        view = ADMETView(props)
        rows = view._build_property_rows()

        row = rows[0]
        assert row["label"] == "LogP"
        assert row["category"] == "admet_profile"
        assert row["status"] == "optimal"
        assert "Partition coefficient" in row["description"]

    def test_surface_descriptor_rows_are_sorted_by_family_index(self):
        """Surface descriptors should sort numerically within a descriptor family."""
        props = {"peoe_vsa10": 1.0, "peoe_vsa2": 1.0, "peoe_vsa1": 1.0}
        view = ADMETView(props)
        rows = view._build_property_rows()
        categories = view._group_rows(rows)
        ordered = [row["normalized_key"] for row in categories["surface_electronics"]]
        assert ordered == ["peoe_vsa1", "peoe_vsa2", "peoe_vsa10"]
