"""Tests for ComplexView widget."""

from refua_notebook.widgets.complex import ComplexView


class TestComplexView:
    """Tests for ComplexView widget."""

    def test_basic_creation(self):
        """Test basic widget creation."""
        view = ComplexView(name="Test Complex")
        assert view.name == "Test Complex"
        assert not view.is_folded

    def test_folded_with_bcif(self):
        """Test is_folded with BCIF data."""
        view = ComplexView(bcif_data=b"test data")
        assert view.is_folded

    def test_folded_with_pdb(self):
        """Test is_folded with PDB data."""
        view = ComplexView(pdb_data="ATOM...")
        assert view.is_folded

    def test_custom_dimensions(self):
        """Test custom width and height."""
        view = ComplexView(width=800, height=600)
        assert view.width == 800
        assert view.height == 600

    def test_minimum_dimensions(self):
        """Test minimum dimensions are enforced."""
        view = ComplexView(width=200, height=100)
        assert view.width >= 400
        assert view.height >= 300

    def test_with_affinity(self):
        """Test creation with affinity."""
        affinity = {"ic50": -7.5, "probability": 0.85}
        view = ComplexView(bcif_data=b"data", affinity=affinity)
        assert view.affinity == affinity

    def test_with_components(self):
        """Test creation with components."""
        components = [
            {"type": "protein", "name": "Target", "sequence": "MKTAYIAK"},
            {"type": "ligand", "name": "Drug", "smiles": "CCO"},
        ]
        view = ComplexView(components=components)
        assert len(view.components) == 2

    def test_html_folded(self):
        """Test HTML generation for folded complex."""
        view = ComplexView(
            bcif_data=b"\x00\x01\x02\x03",
            name="Folded Complex",
            ligand_name="Drug",
        )
        html = view.to_html()

        assert "Folded Complex" in html
        assert "molstar" in html.lower() or "data:application" in html
        assert 'data-format="bcif"' in html

    def test_html_text_cif_bytes_are_labeled_mmcif(self):
        """Text payloads provided via bcif_data should be treated as mmCIF."""
        view = ComplexView(
            bcif_data=b"data_model\nloop_\n_atom_site.id\n",
            name="Text CIF Complex",
        )
        html = view.to_html()
        assert 'data-format="mmcif"' in html

    def test_html_unfolded(self):
        """Test HTML generation for unfolded complex."""
        components = [
            {"type": "protein", "name": "Target", "sequence": "MKTAYIAK"},
            {"type": "ligand", "smiles": "CCO"},
        ]
        view = ComplexView(name="Pending", components=components)
        html = view.to_html()

        assert "No 3D structure available" in html
        assert "fold()" in html
        assert "complex-view-minimal" in html

    def test_html_with_affinity(self):
        """Test minimal UI omits affinity panel details."""
        view = ComplexView(
            bcif_data=b"data",
            affinity={"ic50": -7.5, "probability": 0.85},
        )
        html = view.to_html()

        assert "Binding Affinity" not in html
        assert 'data-refua-molstar="1"' in html

    def test_minimal_html_omits_admet_panels(self):
        """Test minimal UI does not render ADMET tables in complex view."""
        components = [
            {
                "type": "ligand",
                "name": "Drug",
                "smiles": "CCO",
                "properties": {"logP": 2.5, "solubility": -1.2},
            }
        ]
        view = ComplexView(components=components)
        html = view.to_html()

        assert "ADMET" not in html
        assert "logP" not in html and "LogP" not in html

    def test_repr_html(self):
        """Test _repr_html_ method."""
        view = ComplexView(name="Test")
        assert view._repr_html_() == view.to_html()

    def test_unique_element_ids(self):
        """Test that each view gets a unique element ID."""
        view1 = ComplexView(name="Test1")
        view2 = ComplexView(name="Test2")
        assert view1._element_id != view2._element_id

    def test_format_affinity_probability(self):
        """Test affinity probability formatting."""
        view = ComplexView()
        formatted = view._format_affinity_value("probability", 0.85)
        assert "85" in formatted or "0.85" in formatted

    def test_format_affinity_ic50(self):
        """Test affinity ic50 formatting."""
        view = ComplexView()
        formatted = view._format_affinity_value("ic50", -7.5)
        assert "7.5" in formatted

    def test_show_affinity_false(self):
        """Test show_affinity=False hides affinity."""
        view = ComplexView(
            bcif_data=b"data",
            affinity={"ic50": -7.5},
            show_affinity=False,
        )
        html = view.to_html()
        # Affinity should not be shown
        assert "Binding Affinity" not in html


class TestComplexViewComponents:
    """Tests for ComplexView component parsing."""

    def test_protein_component_split(self):
        """Test protein component is split into proteins bucket."""
        components = [{"type": "protein", "name": "Target", "sequence": "MKTAYIAK"}]
        view = ComplexView(components=components)
        ligands, proteins, others = view._split_components()
        assert not ligands
        assert len(proteins) == 1
        assert proteins[0]["name"] == "Target"
        assert proteins[0]["sequence"] == "MKTAYIAK"
        assert not others

    def test_ligand_component_with_smiles_split(self):
        """Test ligand component with SMILES is split into ligands bucket."""
        components = [{"type": "ligand", "name": "Drug", "smiles": "CCO"}]
        view = ComplexView(components=components)
        ligands, proteins, others = view._split_components()
        assert len(ligands) == 1
        assert ligands[0]["name"] == "Drug"
        assert ligands[0]["smiles"] == "CCO"
        assert not proteins
        assert not others

    def test_ligand_component_without_smiles_split(self):
        """Test ligand component without SMILES still goes to ligands bucket."""
        components = [{"type": "ligand", "name": "Unknown Drug"}]
        view = ComplexView(components=components)
        ligands, proteins, others = view._split_components()
        assert len(ligands) == 1
        assert ligands[0]["name"] == "Unknown Drug"
        assert ligands[0]["smiles"] is None
        assert not proteins
        assert not others

    def test_unknown_component_type_split(self):
        """Test unknown component type is split into others bucket."""
        components = [{"type": "ion", "name": "Calcium"}]
        view = ComplexView(components=components)
        ligands, proteins, others = view._split_components()
        assert not ligands
        assert not proteins
        assert len(others) == 1
        assert others[0]["name"] == "Calcium"
        assert others[0]["type"] == "ion"


class TestComplexViewClassMethods:
    """Tests for ComplexView class methods."""

    def test_from_structure_data_bcif(self):
        """Test from_structure_data with BCIF."""
        view = ComplexView.from_structure_data(
            bcif_data=b"test data",
            name="Test Complex",
        )
        assert view.is_folded
        assert view.name == "Test Complex"

    def test_from_structure_data_pdb(self):
        """Test from_structure_data with PDB."""
        view = ComplexView.from_structure_data(
            pdb_data="ATOM...",
            name="PDB Complex",
        )
        assert view.is_folded
        assert view.name == "PDB Complex"

    def test_from_refua_complex_folded(self):
        """Test from_refua_complex with folded complex."""

        class MockComplex:
            name = "Folded Complex"
            entities = []

            def to_bcif(self):
                return b"bcif data"

        view = ComplexView.from_refua_complex(MockComplex())
        assert view.is_folded
        assert view.name == "Folded Complex"

    def test_from_refua_complex_with_affinity(self):
        """Test from_refua_complex with affinity."""

        class MockAffinity:
            value = -7.5
            probability = 0.85

        class MockComplex:
            name = "Test"
            affinity = MockAffinity()
            entities = []

            def to_bcif(self):
                return b"data"

        view = ComplexView.from_refua_complex(MockComplex())
        # Check affinity was extracted
        assert len(view.affinity) >= 1
        assert (
            view.affinity.get("value") == -7.5
            or view.affinity.get("probability") == 0.85
        )

    def test_from_refua_complex_with_entities(self):
        """Test from_refua_complex extracts entities."""

        class MockSM:
            smiles = "CCO"
            name = "Drug"

        class MockProtein:
            sequence = "MKTAYIAK"
            name = "Target"

        class MockComplex:
            name = "Complex"
            entities = [MockProtein(), MockSM()]
            affinity = None

            def to_bcif(self):
                return None

        view = ComplexView.from_refua_complex(MockComplex())
        # Check entities were extracted - names depend on type detection
        assert len(view.components) == 2

    def test_from_refua_complex_sm_type_detection(self):
        """Test SM type is detected from class name."""

        class SM:  # Named exactly SM
            smiles = "CCO"
            name = None

        class MockComplex:
            name = "Test"
            entities = [SM()]
            affinity = None

            def to_bcif(self):
                return None

        view = ComplexView.from_refua_complex(MockComplex())
        assert len(view.components) == 1
        assert view.components[0]["type"] == "ligand"

    def test_from_refua_complex_uses_object_graph_metadata(self):
        """Test that object graph metadata is used for fold/admet."""

        class MockAffinity:
            ic50 = -7.5
            binding_probability = 0.82

        class MockFold:
            affinity = MockAffinity()
            ligand_admet = {"L1": {"predictions": {"logP": 2.1}}}
            chain_ids = (("A",), ("L1",))

            def to_bcif(self):
                return b"bcif data"

        class MockSM:
            smiles = "CCO"
            name = "Drug"

        class MockProtein:
            sequence = "MKTAYIAK"
            name = "Target"

        class MockComplex:
            name = "Graph Complex"
            entities = [MockProtein(), MockSM()]
            last_fold = MockFold()

        view = ComplexView.from_refua_complex(MockComplex())
        assert view.is_folded
        assert (
            view.affinity.get("ic50") == -7.5
            or view.affinity.get("binding_probability") == 0.82
        )
        ligands = [comp for comp in view.components if comp.get("type") == "ligand"]
        assert ligands
        assert ligands[0].get("properties", {}).get("logP") == 2.1
