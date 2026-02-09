"""Tests for SMView widget."""

import pytest
from refua_notebook.widgets.sm import SMGridView, SMView


class TestSMView:
    """Tests for SMView widget."""

    def test_basic_creation(self):
        """Test basic widget creation."""
        view = SMView("CCO", name="Ethanol")
        assert view.smiles == "CCO"
        assert view.name == "Ethanol"

    def test_smiles_stripping(self):
        """Test that SMILES is stripped of whitespace."""
        view = SMView("  CCO  \n")
        assert view.smiles == "CCO"

    def test_custom_dimensions(self):
        """Test custom width and height."""
        view = SMView("CCO", width=500, height=400)
        assert view.width == 500
        assert view.height == 400

    def test_minimum_dimensions(self):
        """Test minimum dimensions are enforced."""
        view = SMView("CCO", width=50, height=50)
        assert view.width >= 200
        assert view.height >= 150

    def test_theme(self):
        """Test theme setting."""
        view_light = SMView("CCO", theme="light")
        view_dark = SMView("CCO", theme="dark")
        view_invalid = SMView("CCO", theme="invalid")

        assert view_light.theme == "light"
        assert view_dark.theme == "dark"
        assert view_invalid.theme == "light"  # Default for invalid

    def test_layout(self):
        """Test layout setting."""
        view_h = SMView("CCO", layout="horizontal")
        view_v = SMView("CCO", layout="vertical")
        view_invalid = SMView("CCO", layout="invalid")

        assert view_h.layout == "horizontal"
        assert view_v.layout == "vertical"
        assert view_invalid.layout == "horizontal"  # Default

    def test_with_properties(self):
        """Test creation with properties."""
        props = {"logP": 2.5, "solubility": -3.2}
        view = SMView("CCO", name="Test", properties=props)
        assert view.properties == props

    def test_html_generation(self):
        """Test HTML generation."""
        view = SMView("CCO", name="Ethanol")
        html = view.to_html()

        assert "CCO" in html
        assert "Ethanol" in html

    def test_html_with_properties(self):
        """Test HTML generation with properties."""
        props = {"logP": 2.5, "herg": 0.1}
        view = SMView("CCO", name="Test", properties=props)
        html = view.to_html()

        # Should include ADMET view
        assert "admet" in html.lower() or "logp" in html.lower() or "LogP" in html

    def test_repr_html(self):
        """Test _repr_html_ method."""
        view = SMView("CCO")
        html1 = view._repr_html_()
        html2 = view.to_html()
        # Both calls should produce HTML with the same molecule
        assert "CCO" in html1
        assert "CCO" in html2
        # Element IDs will differ but structure should be similar
        assert "smview" in html1 or "smiles" in html1

    def test_unique_element_ids(self):
        """Test that each view gets a unique element ID."""
        view1 = SMView("CCO")
        view2 = SMView("CCO")
        assert view1._element_id != view2._element_id

    def test_show_structure_false(self):
        """Test show_structure=False hides 2D structure."""
        view = SMView("CCO", show_structure=False)
        html = view.to_html()
        # Should not have smiles drawer
        assert "SmilesDrawer" not in html

    def test_show_properties_false(self):
        """Test show_properties=False hides properties."""
        props = {"logP": 2.5}
        view = SMView("CCO", properties=props, show_properties=False)
        html = view.to_html()
        # Should not have admet view
        assert "admet-view" not in html


class TestSMViewClassMethods:
    """Tests for SMView class methods."""

    def test_from_smiles(self):
        """Test from_smiles class method."""
        view = SMView.from_smiles("CCO", name="Ethanol")
        assert view.smiles == "CCO"
        assert view.name == "Ethanol"

    def test_from_refua_sm_mock(self):
        """Test from_refua_sm with mock object."""

        class MockSM:
            smiles = "CCO"
            name = "Ethanol"

        view = SMView.from_refua_sm(MockSM())
        assert view.smiles == "CCO"
        assert view.name == "Ethanol"

    def test_from_refua_sm_with_properties(self):
        """Test from_refua_sm with properties."""

        class MockSM:
            smiles = "CCO"
            name = "Test"

            def to_dict(self):
                return {"logP": 2.5}

        view = SMView.from_refua_sm(MockSM())
        assert view.properties == {"logP": 2.5}

    def test_from_refua_sm_no_smiles_raises(self):
        """Test from_refua_sm raises without SMILES."""

        class MockSM:
            name = "NoSmiles"

            def __str__(self):
                return ""

        with pytest.raises(ValueError):
            SMView.from_refua_sm(MockSM())


class TestSMGridView:
    """Tests for SMGridView."""

    def test_basic_creation(self):
        """Test basic grid creation."""
        molecules = ["CCO", "CC", "C"]
        grid = SMGridView(molecules)

        assert len(grid.molecules) == 3
        assert grid.columns == 3

    def test_with_dict_molecules(self):
        """Test grid with dict molecules."""
        molecules = [
            {"smiles": "CCO", "name": "Ethanol"},
            {"smiles": "CC", "name": "Ethane"},
        ]
        grid = SMGridView(molecules)

        html = grid.to_html()
        assert "Ethanol" in html
        assert "Ethane" in html

    def test_custom_columns(self):
        """Test custom column count."""
        molecules = ["CCO", "CC", "C", "CO"]
        grid = SMGridView(molecules, columns=2)

        html = grid.to_html()
        assert "grid-template-columns: repeat(2" in html

    def test_minimum_columns(self):
        """Test minimum columns is 1."""
        grid = SMGridView(["CCO"], columns=0)
        assert grid.columns == 1

    def test_html_generation(self):
        """Test HTML generation."""
        molecules = ["CCO", "CC"]
        grid = SMGridView(molecules)
        html = grid.to_html()

        assert "sm-grid" in html
        assert "CCO" in html
        assert "CC" in html

    def test_repr_html(self):
        """Test _repr_html_ method."""
        grid = SMGridView(["CCO", "CC"])
        html = grid._repr_html_()
        assert "sm-grid" in html

    def test_unique_grid_ids(self):
        """Test that each grid gets a unique ID."""
        grid1 = SMGridView(["CCO"])
        grid2 = SMGridView(["CCO"])
        assert grid1._grid_id != grid2._grid_id

    def test_show_properties_in_grid(self):
        """Test show_properties option in grid."""
        molecules = [{"smiles": "CCO", "properties": {"logP": 2.5}}]
        grid = SMGridView(molecules, show_properties=True)
        html = grid.to_html()
        # Should have ADMET display
        assert "admet" in html.lower() or "logP" in html or "LogP" in html

    def test_parse_molecule_string(self):
        """Test _parse_molecule with string."""
        grid = SMGridView([])
        parsed = grid._parse_molecule("CCO")
        assert parsed["smiles"] == "CCO"
        assert parsed["name"] is None

    def test_parse_molecule_dict(self):
        """Test _parse_molecule with dict."""
        grid = SMGridView([])
        parsed = grid._parse_molecule({"smiles": "CCO", "name": "Ethanol"})
        assert parsed["smiles"] == "CCO"
        assert parsed["name"] == "Ethanol"

    def test_parse_molecule_object(self):
        """Test _parse_molecule with object."""

        class MockSM:
            smiles = "CCO"
            name = "Ethanol"

        grid = SMGridView([])
        parsed = grid._parse_molecule(MockSM())
        assert parsed["smiles"] == "CCO"
        assert parsed["name"] == "Ethanol"
