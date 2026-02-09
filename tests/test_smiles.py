"""Tests for SmilesView widget."""

from refua_notebook.widgets.smiles import SMILESDRAWER_CDN, SmilesGridView, SmilesView


class TestSmilesView:
    """Tests for SmilesView widget."""

    def test_basic_creation(self):
        """Test basic widget creation."""
        view = SmilesView("CCO")
        assert view.smiles == "CCO"
        assert view.width == 400
        assert view.height == 300

    def test_smiles_stripping(self):
        """Test that SMILES is stripped of whitespace."""
        view = SmilesView("  CCO  \n")
        assert view.smiles == "CCO"

    def test_custom_dimensions(self):
        """Test custom width and height."""
        view = SmilesView("CCO", width=500, height=400)
        assert view.width == 500
        assert view.height == 400

    def test_minimum_dimensions(self):
        """Test minimum dimensions are enforced."""
        view = SmilesView("CCO", width=50, height=50)
        assert view.width >= 200
        assert view.height >= 150

    def test_title(self):
        """Test title setting."""
        view = SmilesView("CCO", title="Ethanol")
        assert view.title == "Ethanol"

    def test_theme(self):
        """Test theme setting."""
        view_light = SmilesView("CCO", theme="light")
        view_dark = SmilesView("CCO", theme="dark")
        view_invalid = SmilesView("CCO", theme="invalid")

        assert view_light.theme == "light"
        assert view_dark.theme == "dark"
        assert view_invalid.theme == "light"  # Default for invalid

    def test_html_generation(self):
        """Test HTML generation."""
        view = SmilesView("CCO", title="Ethanol")
        html = view.to_html()

        assert "CCO" in html
        assert "Ethanol" in html
        assert SMILESDRAWER_CDN in html
        assert "SmilesDrawer" in html
        assert 'data-refua-smiles="1"' in html

    def test_repr_html(self):
        """Test _repr_html_ method."""
        view = SmilesView("CCO")
        assert view._repr_html_() == view.to_html()

    def test_svg_mode(self):
        """Test SVG rendering mode."""
        view = SmilesView("CCO", use_svg=True)
        html = view.to_html()

        assert "<svg" in html
        assert "SvgDrawer" in html

    def test_canvas_mode(self):
        """Test canvas rendering mode."""
        view = SmilesView("CCO", use_svg=False)
        html = view.to_html()

        assert "<canvas" in html
        assert "new SmilesDrawer.Drawer" in html

    def test_show_hydrogens(self):
        """Test explicit hydrogens option."""
        view_with = SmilesView("CCO", show_hydrogens=True)
        view_without = SmilesView("CCO", show_hydrogens=False)

        html_with = view_with.to_html()
        html_without = view_without.to_html()

        assert "explicitHydrogens: true" in html_with
        assert "explicitHydrogens: false" in html_without

    def test_unique_element_ids(self):
        """Test that each view gets a unique element ID."""
        view1 = SmilesView("CCO")
        view2 = SmilesView("CCO")

        assert view1._element_id != view2._element_id

    def test_dark_theme_styling(self):
        """Test dark theme styling in HTML."""
        view = SmilesView("CCO", theme="dark")
        html = view.to_html()

        # Dark theme should have dark background
        assert "#1e293b" in html

    def test_light_theme_styling(self):
        """Test light theme styling in HTML."""
        view = SmilesView("CCO", theme="light")
        html = view.to_html()

        # Light theme should have light background
        assert "#ffffff" in html

    def test_html_escaping(self):
        """Test that HTML is properly escaped."""
        view = SmilesView("CCO", title="<script>alert('xss')</script>")
        html = view.to_html()

        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_smiles_escaping(self):
        """Test that SMILES is properly escaped."""
        # SMILES with special characters
        view = SmilesView("C&C")  # & needs escaping
        html = view.to_html()

        # The SMILES should be escaped in data-smiles attribute
        assert 'data-smiles="C&amp;C"' in html

    def test_smiles_displayed(self):
        """Test that SMILES is displayed below structure."""
        view = SmilesView("CCO")
        html = view.to_html()

        # Should have a div for showing the SMILES (the id contains -smiles suffix)
        assert '-smiles">' in html or "-smiles'>" in html
        assert ">CCO<" in html


class TestSmilesViewComplexMolecules:
    """Tests for SmilesView with complex molecules."""

    def test_aspirin(self):
        """Test with aspirin SMILES."""
        aspirin = "CC(=O)OC1=CC=CC=C1C(=O)O"
        view = SmilesView(aspirin, title="Aspirin")
        html = view.to_html()

        assert aspirin in html
        assert "Aspirin" in html

    def test_caffeine(self):
        """Test with caffeine SMILES."""
        caffeine = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
        view = SmilesView(caffeine, title="Caffeine")
        html = view.to_html()

        assert caffeine in html

    def test_ring_systems(self):
        """Test with complex ring systems."""
        benzene = "c1ccccc1"
        view = SmilesView(benzene, title="Benzene")
        html = view.to_html()

        assert benzene in html


class TestSmilesGridView:
    """Tests for SmilesGridView."""

    def test_basic_creation(self):
        """Test basic grid creation."""
        smiles_list = ["CCO", "CC", "C"]
        grid = SmilesGridView(smiles_list)

        assert len(grid.smiles_list) == 3
        assert grid.columns == 3

    def test_with_titles(self):
        """Test grid with titles."""
        smiles_list = ["CCO", "CC"]
        titles = ["Ethanol", "Ethane"]
        grid = SmilesGridView(smiles_list, titles=titles)

        html = grid.to_html()
        assert "Ethanol" in html
        assert "Ethane" in html

    def test_custom_columns(self):
        """Test custom column count."""
        smiles_list = ["CCO", "CC", "C", "CO"]
        grid = SmilesGridView(smiles_list, columns=2)

        html = grid.to_html()
        assert "grid-template-columns: repeat(2" in html

    def test_minimum_columns(self):
        """Test minimum columns is 1."""
        grid = SmilesGridView(["CCO"], columns=0)
        assert grid.columns == 1

    def test_html_generation(self):
        """Test HTML generation."""
        smiles_list = ["CCO", "CC"]
        grid = SmilesGridView(smiles_list)
        html = grid.to_html()

        assert "smiles-grid" in html
        assert "CCO" in html
        assert "CC" in html

    def test_repr_html(self):
        """Test _repr_html_ method returns HTML."""
        grid = SmilesGridView(["CCO", "CC"])
        html = grid._repr_html_()
        # Check that it returns valid HTML with the grid structure
        assert "smiles-grid" in html
        assert "CCO" in html
        assert "CC" in html

    def test_kwargs_passed_to_children(self):
        """Test that kwargs are passed to child SmilesView instances."""
        smiles_list = ["CCO"]
        grid = SmilesGridView(smiles_list, theme="dark")

        html = grid.to_html()
        # Dark theme background color should be present
        assert "#1e293b" in html

    def test_unique_grid_ids(self):
        """Test that each grid gets a unique ID."""
        grid1 = SmilesGridView(["CCO"])
        grid2 = SmilesGridView(["CCO"])

        assert grid1._grid_id != grid2._grid_id


class TestSmilesViewFromSmilesList:
    """Tests for SmilesView.from_smiles_list class method."""

    def test_from_smiles_list(self):
        """Test creating grid from SmilesView class method."""
        smiles_list = ["CCO", "CC", "C"]
        grid = SmilesView.from_smiles_list(smiles_list, columns=2)

        assert isinstance(grid, SmilesGridView)
        assert len(grid.smiles_list) == 3
        assert grid.columns == 2

    def test_from_smiles_list_with_titles(self):
        """Test creating grid with titles from class method."""
        smiles_list = ["CCO", "CC"]
        titles = ["Ethanol", "Ethane"]
        grid = SmilesView.from_smiles_list(smiles_list, titles=titles)

        html = grid.to_html()
        assert "Ethanol" in html
        assert "Ethane" in html
