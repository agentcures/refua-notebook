"""Tests for ProteinView widget."""

from refua_notebook.widgets.protein import ProteinView


class TestProteinView:
    """Tests for ProteinView widget."""

    def test_basic_creation(self):
        """Test basic widget creation."""
        view = ProteinView(sequence="MKTAYIAK", name="Test Protein")
        assert view.sequence == "MKTAYIAK"
        assert view.name == "Test Protein"
        assert view.sequence_length == 8

    def test_sequence_stripping(self):
        """Test that sequence is stripped of whitespace."""
        view = ProteinView(sequence="  MKTAYIAK  \n")
        assert view.sequence == "MKTAYIAK"

    def test_custom_dimensions(self):
        """Test custom width and height."""
        view = ProteinView(sequence="MKTAYIAK", width=800, height=600)
        assert view.width == 800
        assert view.height == 600

    def test_minimum_dimensions(self):
        """Test minimum dimensions are enforced."""
        view = ProteinView(sequence="MKTAYIAK", width=100, height=100)
        assert view.width >= 300
        assert view.height >= 200

    def test_has_structure_false_by_default(self):
        """Test has_structure is False without structure data."""
        view = ProteinView(sequence="MKTAYIAK")
        assert not view.has_structure

    def test_has_structure_with_bcif(self):
        """Test has_structure is True with BCIF data."""
        view = ProteinView(sequence="MKTAYIAK", bcif_data=b"test data")
        assert view.has_structure

    def test_has_structure_with_pdb(self):
        """Test has_structure is True with PDB data."""
        view = ProteinView(sequence="MKTAYIAK", pdb_data="ATOM...")
        assert view.has_structure

    def test_html_generation(self):
        """Test HTML generation."""
        view = ProteinView(sequence="MKTAYIAK", name="Test Protein")
        html = view.to_html()

        assert "Test Protein" in html
        assert "8" in html  # Length
        assert "amino acids" in html

    def test_repr_html(self):
        """Test _repr_html_ method."""
        view = ProteinView(sequence="MKTAYIAK")
        assert view._repr_html_() == view.to_html()

    def test_sequence_truncation(self):
        """Test long sequence is truncated for display."""
        long_seq = "M" * 100
        view = ProteinView(sequence=long_seq, sequence_display_length=40)
        html = view.to_html()

        assert "..." in html
        assert "100" in html  # Full length shown

    def test_sequence_not_truncated_when_short(self):
        """Test short sequence is not truncated."""
        view = ProteinView(sequence="MKTAYIAK")
        formatted = view._format_sequence()
        assert "..." not in formatted

    def test_unique_element_ids(self):
        """Test that each view gets a unique element ID."""
        view1 = ProteinView(sequence="MKTAYIAK")
        view2 = ProteinView(sequence="MKTAYIAK")
        assert view1._element_id != view2._element_id

    def test_show_sequence_false(self):
        """Test show_sequence=False hides sequence."""
        view = ProteinView(sequence="MKTAYIAK", show_sequence=False)
        html = view.to_html()
        # The formatted sequence should not appear when show_sequence is False
        formatted_seq = view._format_sequence()
        assert formatted_seq not in html or formatted_seq == ""

    def test_structure_badge_shown(self):
        """Test 3D Structure badge appears with structure data."""
        view = ProteinView(sequence="MKTAYIAK", bcif_data=b"data")
        html = view.to_html()
        assert "3D Structure" in html

    def test_no_structure_badge_without_data(self):
        """Test no 3D Structure badge without structure data."""
        view = ProteinView(sequence="MKTAYIAK")
        html = view.to_html()
        # Badge should not appear when there's no structure data
        assert not view.has_structure
        assert "3D Structure" not in html


class TestProteinViewClassMethods:
    """Tests for ProteinView class methods."""

    def test_from_sequence(self):
        """Test from_sequence class method."""
        view = ProteinView.from_sequence("MKTAYIAK", name="Test")
        assert view.sequence == "MKTAYIAK"
        assert view.name == "Test"

    def test_from_refua_protein_mock(self):
        """Test from_refua_protein with mock object."""

        class MockProtein:
            sequence = "MKTAYIAK"
            name = "Mock Protein"

        view = ProteinView.from_refua_protein(MockProtein())
        assert view.sequence == "MKTAYIAK"
        assert view.name == "Mock Protein"

    def test_from_refua_protein_with_ids(self):
        """Test from_refua_protein with ids attribute."""

        class MockProtein:
            sequence = "MKTAYIAK"
            ids = "Chain_A"

        view = ProteinView.from_refua_protein(MockProtein())
        assert view.name == "Chain_A"

    def test_from_refua_protein_with_list_ids(self):
        """Test from_refua_protein with list ids."""

        class MockProtein:
            sequence = "MKTAYIAK"
            ids = ["A", "B"]

        view = ProteinView.from_refua_protein(MockProtein())
        assert view.name == "A"

    def test_from_refua_protein_with_structure(self):
        """Test from_refua_protein with structure data."""

        class MockProtein:
            sequence = "MKTAYIAK"
            name = "Folded"

            def to_bcif(self):
                return b"bcif data"

        view = ProteinView.from_refua_protein(MockProtein())
        assert view.has_structure
        assert view.bcif_data == b"bcif data"
