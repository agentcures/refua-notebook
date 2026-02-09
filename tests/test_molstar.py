"""Tests for MolstarView widget."""

import base64
import html
import json
import re

from refua_notebook.widgets.molstar import MOLSTAR_CSS_CDN, MOLSTAR_JS_CDN, MolstarView


class TestMolstarView:
    """Tests for MolstarView widget."""

    def test_basic_creation_with_url(self):
        """Test basic widget creation with URL."""
        view = MolstarView(url="https://files.rcsb.org/download/1TIM.cif")
        assert view.url == "https://files.rcsb.org/download/1TIM.cif"
        assert view.width == 600
        assert view.height == 400

    def test_creation_with_bcif_data(self):
        """Test creation with BCIF data."""
        bcif_data = b"\x00\x01\x02\x03"
        view = MolstarView(bcif_data=bcif_data)
        assert view.bcif_data == bcif_data

    def test_creation_with_pdb_data(self):
        """Test creation with PDB data."""
        pdb_data = "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N"
        view = MolstarView(pdb_data=pdb_data)
        assert view.pdb_data == pdb_data

    def test_custom_dimensions(self):
        """Test custom width and height."""
        view = MolstarView(
            url="https://example.com/structure.cif", width=800, height=600
        )
        assert view.width == 800
        assert view.height == 600

    def test_ligand_name(self):
        """Test ligand name setting."""
        view = MolstarView(
            url="https://example.com/structure.cif", ligand_name="Drug-01"
        )
        assert view.ligand_name == "Drug-01"

    def test_html_generation_with_url(self):
        """Test HTML generation with URL source."""
        view = MolstarView(url="https://files.rcsb.org/download/1TIM.cif")
        html = view.to_html()

        assert "molstar" in html.lower()
        assert MOLSTAR_JS_CDN in html
        assert MOLSTAR_CSS_CDN in html
        assert "1TIM.cif" in html
        assert 'data-refua-molstar="1"' in html
        assert "loadStructureFromUrl" in html

    def test_html_generation_with_bcif_data(self):
        """Test HTML generation with BCIF data."""
        bcif_data = b"\x00\x01\x02\x03"
        view = MolstarView(bcif_data=bcif_data)
        html = view.to_html()

        # Should contain base64 encoded data
        expected_b64 = base64.b64encode(bcif_data).decode("ascii")
        assert expected_b64 in html
        assert "data:application/octet-stream;base64" in html

    def test_html_generation_with_pdb_data(self):
        """Test HTML generation with PDB data."""
        pdb_data = "ATOM      1  N   ALA A   1       0.000   0.000   0.000"
        view = MolstarView(pdb_data=pdb_data)
        html = view.to_html()

        # Should contain base64 encoded data
        assert "data:text/plain;base64" in html

    def test_html_with_no_data(self):
        """Test HTML generation with no data."""
        view = MolstarView()
        html = view.to_html()

        assert "No structure data provided" in html

    def test_repr_html(self):
        """Test _repr_html_ method."""
        view = MolstarView(url="https://example.com/structure.cif")
        assert view._repr_html_() == view.to_html()

    def test_ligand_in_html(self):
        """Test ligand name appears in HTML."""
        view = MolstarView(
            url="https://example.com/structure.cif", ligand_name="Aspirin"
        )
        html = view.to_html()

        assert "Aspirin" in html

    def test_controls_toggle(self):
        """Test show_controls option."""
        view_with = MolstarView(
            url="https://example.com/structure.cif", show_controls=True
        )
        view_without = MolstarView(
            url="https://example.com/structure.cif", show_controls=False
        )

        html_with = view_with.to_html()
        html_without = view_without.to_html()

        # Controls setting should be reflected
        assert "layoutShowControls: true" in html_with
        assert "layoutShowControls: false" in html_without

    def test_unique_viewer_ids(self):
        """Test that each viewer gets a unique ID."""
        view1 = MolstarView(url="https://example.com/structure.cif")
        view2 = MolstarView(url="https://example.com/structure.cif")

        assert view1._viewer_id != view2._viewer_id

    def test_from_pdb_id(self):
        """Test from_pdb_id class method."""
        view = MolstarView.from_pdb_id("1TIM")
        assert view.url == "https://files.rcsb.org/download/1TIM.cif"

    def test_from_pdb_id_lowercase(self):
        """Test from_pdb_id with lowercase input."""
        view = MolstarView.from_pdb_id("1tim")
        assert view.url == "https://files.rcsb.org/download/1TIM.cif"

    def test_format_detection_from_url(self):
        """Test format detection from URL."""
        view_cif = MolstarView(url="https://example.com/structure.cif")
        html_cif = view_cif.to_html()
        assert "mmcif" in html_cif

        view_pdb = MolstarView(url="https://example.com/structure.pdb")
        html_pdb = view_pdb.to_html()
        # Format is used as variable in JS, check both possible quoting styles
        assert "pdb" in html_pdb and "formatType" in html_pdb

        view_bcif = MolstarView(url="https://example.com/structure.bcif")
        html_bcif = view_bcif.to_html()
        assert "bcif" in html_bcif

    def test_html_escaping(self):
        """Test that HTML/JS is properly escaped."""
        view = MolstarView(
            url="https://example.com/structure.cif",
            ligand_name="<script>alert('xss')</script>",
        )
        html_output = view.to_html()

        # The script tag should be escaped - characters are escaped as unicode
        # e.g., < becomes \u003c, > becomes \u003e
        assert "<script>alert" not in html_output
        # Check for unicode-escaped version
        assert "\\u003cscript\\u003e" in html_output

    def test_background_color(self):
        """Test custom background color."""
        view = MolstarView(
            url="https://example.com/structure.cif", background="#f0f0f0"
        )
        html = view.to_html()

        assert "#f0f0f0" in html

    def test_color_plan_metadata_in_html(self):
        """Test color plan metadata is embedded for renderer use."""
        view = MolstarView(
            url="https://example.com/structure.cif",
            components=[
                {"type": "protein", "name": "Heavy chain", "chain_ids": ["A"]},
                {"type": "protein", "name": "Light chain", "chain_ids": ["B"]},
                {
                    "type": "ligand",
                    "name": "Ligand X",
                    "smiles": "CCO",
                    "chain_ids": ["X"],
                },
            ],
        )
        html_output = view.to_html(include_scripts=False)
        match = re.search(r'data-color-plan="([^"]+)"', html_output)
        assert match is not None

        color_plan = json.loads(html.unescape(match.group(1)))
        assert ["A", "B"] in color_plan["protein_chain_groups"]
        assert color_plan["ligand_chain_groups"] == [["X"]]
        assert color_plan["antibody_pair_detected"] is True

    def test_color_plan_default_palette_script_present(self):
        """Test script contains role-based default colors."""
        view = MolstarView(url="https://example.com/structure.cif")
        html_output = view.to_html()
        assert "applyColorPlan" in html_output
        assert "#2563eb" in html_output
        assert "#db2777" in html_output

    def test_antibody_chain_pairing_heuristic(self):
        """Heavy/light components should be grouped to the same color bucket."""
        view = MolstarView(
            url="https://example.com/structure.cif",
            components=[
                {"type": "protein", "id": "H", "chain_ids": ["H1"]},
                {"type": "protein", "id": "L", "chain_ids": ["L1"]},
                {"type": "protein", "name": "Enzyme", "chain_ids": ["A"]},
            ],
        )
        color_plan = view._build_molecule_color_plan()
        assert color_plan["antibody_pair_detected"] is True
        assert color_plan["protein_chain_groups"][0] == ["H1", "L1"]
        assert ["A"] in color_plan["protein_chain_groups"]

    def test_ligand_like_chain_id_heuristic(self):
        """L-prefixed ids without sequence should be treated as ligand-like."""
        view = MolstarView(
            url="https://example.com/structure.cif",
            components=[
                {"type": "unknown", "id": "L1", "chain_ids": ["L1"]},
                {"type": "protein", "id": "A", "sequence": "MKT", "chain_ids": ["A"]},
            ],
        )
        color_plan = view._build_molecule_color_plan()
        assert color_plan["ligand_chain_groups"] == [["L1"]]
        assert color_plan["other_chain_groups"] == []

    def test_structure_inferred_color_plan_without_components(self):
        """Fallback should infer roles/chains directly from mmCIF records."""
        mmcif_data = """data_model
ATOM 1 N N . ALA 1 1 ? A 0 0 0 1 1 A ALA 10 1
ATOM 2 N N . GLY 1 1 ? H 1 0 0 1 1 H GLY 10 1
ATOM 3 N N . GLY 1 1 ? L 2 0 0 1 1 L GLY 10 1
HETATM 4 C C1 . LIG1 . 1 ? L1 3 0 0 1 2 L1 LIG1 10 1
"""
        view = MolstarView(bcif_data=mmcif_data.encode("utf-8"))
        color_plan = view._build_molecule_color_plan()

        assert color_plan["antibody_pair_detected"] is True
        assert ["H", "L"] in color_plan["protein_chain_groups"]
        assert ["A"] in color_plan["protein_chain_groups"]
        assert color_plan["ligand_chain_groups"] == [["L1"]]


class TestMolstarViewDataUrl:
    """Tests for data URL generation."""

    def test_bcif_data_url(self):
        """Test BCIF data URL generation."""
        bcif_data = b"\x00\x01bcif\x02content"
        view = MolstarView(bcif_data=bcif_data)

        data_url = view._get_data_url()
        assert data_url is not None
        assert data_url.startswith("data:application/octet-stream;base64,")

        # Verify the encoded data can be decoded
        b64_part = data_url.split(",")[1]
        decoded = base64.b64decode(b64_part)
        assert decoded == bcif_data

    def test_pdb_data_url(self):
        """Test PDB data URL generation."""
        pdb_data = "ATOM      1  N   ALA A   1       0.000   0.000   0.000"
        view = MolstarView(pdb_data=pdb_data)

        data_url = view._get_data_url()
        assert data_url is not None
        assert data_url.startswith("data:text/plain;base64,")

    def test_no_data_url(self):
        """Test no data URL when only URL provided."""
        view = MolstarView(url="https://example.com/structure.cif")
        data_url = view._get_data_url()
        assert data_url is None

    def test_bcif_takes_precedence(self):
        """Test that BCIF data takes precedence over PDB data."""
        bcif_data = b"\x00\x01bcif\x02content"
        pdb_data = "pdb content"
        view = MolstarView(bcif_data=bcif_data, pdb_data=pdb_data)

        data_url = view._get_data_url()
        assert "application/octet-stream" in data_url

    def test_text_cif_bytes_infer_mmcif(self):
        """Text payloads in bcif_data are treated as mmCIF for loading."""
        view = MolstarView(bcif_data=b"data_model\\nloop_\\n_atom_site.id\\n")
        html = view.to_html()
        assert 'data-format="mmcif"' in html
        data_url = view._get_data_url()
        assert data_url is not None
        assert data_url.startswith("data:text/plain;base64,")
