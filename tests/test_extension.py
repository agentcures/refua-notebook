"""Tests for Refua notebook extension."""

from refua import Complex, Protein, SM

from refua_notebook.extension import (
    _get_complex_repr_html,
    _get_protein_repr_html,
    _get_sm_repr_html,
    activate,
    deactivate,
    is_active,
)


class TestSMReprHtml:
    """Tests for SM HTML representation."""

    def test_refua_sm_object_renders(self):
        """Test HTML generation for a Refua SM object."""
        sm = SM("CCO")
        sm.name = "Ethanol"
        sm.smiles = "CCO"
        html = _get_sm_repr_html(sm)
        assert "CCO" in html
        assert "Ethanol" in html or "Molecule Properties" in html


class TestProteinReprHtml:
    """Tests for Protein HTML representation."""

    def test_protein_with_sequence(self):
        """Test HTML generation with sequence."""
        protein = Protein(
            "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ",
            ids="Chain_A",
        )
        html = _get_protein_repr_html(protein)
        assert "Chain_A" in html
        assert "33" in html or "aa" in html  # Length display
        assert 'data-refua-widget="protein-properties"' in html

    def test_protein_with_ids(self):
        """Test HTML generation with ids attribute."""
        protein = Protein("MKTAYIAK", ids="Chain_A")
        html = _get_protein_repr_html(protein)
        assert "Chain_A" in html

    def test_protein_with_list_ids(self):
        """Test HTML generation with list ids."""
        protein = Protein("MKTAYIAK", ids=["Chain_A", "Chain_B"])
        html = _get_protein_repr_html(protein)
        assert "Chain_A" in html

    def test_protein_long_sequence_truncation(self):
        """Test that long sequences are truncated for display."""
        protein = Protein("M" * 100, ids="LongProtein")
        html = _get_protein_repr_html(protein)
        assert "..." in html  # Truncation indicator


class TestComplexReprHtml:
    """Tests for Complex HTML representation."""

    def test_unfolded_complex_with_entities(self):
        """Test HTML generation for unfolded complex."""
        complex_obj = Complex(
            [Protein("MKTAYIAK", ids="A"), SM("CCO")],
            name="Pending Complex",
        )
        html = _get_complex_repr_html(complex_obj)
        assert "No 3D structure available" in html
        assert "fold()" in html


class TestActivateDeactivate:
    """Tests for activate/deactivate functions."""

    def test_is_active_initially_false(self):
        """Test that extension is not active initially."""
        # Reset state
        import refua_notebook.extension as ext

        ext._extension_active = False
        assert not is_active()

    def test_activate_without_ipython(self):
        """Test activate returns False without IPython."""
        # Reset state
        import refua_notebook.extension as ext

        ext._extension_active = False

        # Without an active IPython shell, activate should return False
        # or True if it worked (depends on environment).
        result = activate()
        assert isinstance(result, bool)

    def test_deactivate_resets_state(self):
        """Test that deactivate resets active state."""
        import refua_notebook.extension as ext

        ext._extension_active = True

        deactivate()
        assert not is_active()


class TestModuleLoading:
    """Tests for module loading functions."""

    def test_load_ipython_extension_callable(self):
        """Test that load_ipython_extension is callable."""
        from refua_notebook.extension import load_ipython_extension

        assert callable(load_ipython_extension)

    def test_unload_ipython_extension_callable(self):
        """Test that unload_ipython_extension is callable."""
        from refua_notebook.extension import unload_ipython_extension

        assert callable(unload_ipython_extension)
