"""Protein property visualization widget for Jupyter notebooks.

This module provides the ProteinPropertiesView class for displaying sequence-
derived protein properties from Refua with filtering, category tabs, and
contextual tooltips.
"""

from __future__ import annotations

import html
import math
import re
import uuid
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Dict, List, Mapping

from refua_notebook.mime import REFUA_MIME_TYPE

_ipython_display_module: ModuleType | None
try:
    import IPython.display as _ipython_display_module
except ImportError:
    _ipython_display_module = None


@dataclass
class ProteinThreshold:
    """Defines soft display thresholds for protein property interpretation."""

    name: str
    label: str
    unit: str
    optimal_range: tuple[float, float]
    warning_range: tuple[float, float]
    description: str = ""


@dataclass(frozen=True)
class ProteinInsight:
    """Domain context used for rich protein tooltip copy."""

    what: str
    why: str
    low_signal: str = ""
    high_signal: str = ""
    design_levers: str = ""


_THREE_TO_ONE = {
    "ala": "A",
    "cys": "C",
    "asp": "D",
    "glu": "E",
    "phe": "F",
    "gly": "G",
    "his": "H",
    "ile": "I",
    "lys": "K",
    "leu": "L",
    "met": "M",
    "asn": "N",
    "pro": "P",
    "gln": "Q",
    "arg": "R",
    "ser": "S",
    "thr": "T",
    "val": "V",
    "trp": "W",
    "tyr": "Y",
}

_ALIASES: Dict[str, str] = {
    "mw": "molecular_weight",
    "molecular_weight_da": "molecular_weight",
    "seq_len": "length",
    "length_aa": "length",
    "pi": "isoelectric_point",
    "p_i": "isoelectric_point",
    "charge": "net_charge_ph_7_4",
    "net_charge": "net_charge_ph_7_4",
    "instability": "instability_index",
    "stable": "is_stable",
    "extinction_reduced": "extinction_coefficient_reduced",
    "extinction_oxidized": "extinction_coefficient_oxidized",
}

for aa_name, aa_code in _THREE_TO_ONE.items():
    aa = aa_code.lower()
    _ALIASES[f"{aa}_count"] = f"count_{aa_name}"
    _ALIASES[f"aa_{aa}_count"] = f"count_{aa_name}"
    _ALIASES[f"{aa}_fraction"] = f"fraction_{aa_name}"
    _ALIASES[f"aa_{aa}_fraction"] = f"fraction_{aa_name}"


CATEGORY_ORDER = (
    "core_metrics",
    "charge_profile",
    "secondary_structure",
    "flexibility_absorbance",
    "composition",
    "antibody_liability",
    "peptide_liability",
    "amino_acids",
    "other",
)

CATEGORY_LABELS = {
    "core_metrics": "Core Metrics",
    "charge_profile": "Charge Profile",
    "secondary_structure": "Secondary Structure",
    "flexibility_absorbance": "Flexibility & Absorbance",
    "composition": "Composition",
    "antibody_liability": "Antibody Liability",
    "peptide_liability": "Peptide Liability",
    "amino_acids": "Amino Acids",
    "other": "Other Properties",
    "all": "All Properties",
}


PROPERTY_LABELS = {
    "length": "Length",
    "molecular_weight": "Molecular Weight",
    "isoelectric_point": "Isoelectric Point (pI)",
    "instability_index": "Instability Index",
    "is_stable": "Predicted Stable",
    "aromaticity": "Aromaticity",
    "gravy": "GRAVY",
    "hydropathy_kyte_doolittle": "Hydropathy (Kyte-Doolittle)",
    "aliphatic_index": "Aliphatic Index",
    "shannon_entropy": "Shannon Entropy",
    "helix_fraction": "Helix Fraction",
    "turn_fraction": "Turn Fraction",
    "sheet_fraction": "Sheet Fraction",
    "extinction_coefficient_reduced": "Extinction Coef. (Reduced)",
    "extinction_coefficient_oxidized": "Extinction Coef. (Oxidized)",
    "flexibility_mean": "Flexibility Mean",
    "flexibility_min": "Flexibility Min",
    "flexibility_max": "Flexibility Max",
    "hydrophobic_residue_fraction": "Hydrophobic Residue Fraction",
    "polar_residue_fraction": "Polar Residue Fraction",
    "nonpolar_residue_fraction": "Nonpolar Residue Fraction",
    "charged_residue_fraction": "Charged Residue Fraction",
    "positive_residue_fraction": "Positive Residue Fraction",
    "negative_residue_fraction": "Negative Residue Fraction",
    "tiny_residue_fraction": "Tiny Residue Fraction",
    "small_residue_fraction": "Small Residue Fraction",
    "sulfur_residue_fraction": "Sulfur Residue Fraction",
    "glycine_fraction": "Glycine Fraction",
    "proline_fraction": "Proline Fraction",
    "cysteine_fraction": "Cysteine Fraction",
    "deamidation_high_risk_motif_count": "Deamidation Motifs (High Risk)",
    "deamidation_medium_risk_motif_count": "Deamidation Motifs (Medium Risk)",
    "deamidation_low_risk_motif_count": "Deamidation Motifs (Low Risk)",
    "n_glycosylation_motif_count": "N-Glycosylation Motifs",
    "aspartate_isomerization_motif_count": "Aspartate Isomerization Motifs",
    "aspartate_fragmentation_high_risk_motif_count": "Aspartate Fragmentation (High Risk)",
    "aspartate_fragmentation_medium_risk_motif_count": "Aspartate Fragmentation (Medium Risk)",
    "methionine_oxidation_motif_count": "Methionine Oxidation Sites",
    "tryptophan_oxidation_motif_count": "Tryptophan Oxidation Sites",
    "integrin_binding_motif_count": "Integrin-Binding Motifs",
    "polyreactive_motif_count": "Polyreactive Motifs",
    "aggregation_patch_motif_count": "Aggregation Patch Motifs",
    "viscosity_patch_motif_count": "Viscosity Patch Motifs",
    "unpaired_cysteine_count": "Unpaired Cysteines",
    "antibody_liability_motif_count": "Antibody Liability Motif Count",
    "antibody_liability_score": "Antibody Liability Score",
    "peptide_deamidation_hotspot_count": "Peptide Deamidation Hotspots",
    "peptide_aspartate_cleavage_motif_count": "Peptide Aspartate Cleavage Motifs",
    "peptide_n_terminal_cyclization_risk": "Peptide N-Terminal Cyclization Risk",
    "peptide_trypsin_cleavage_site_count": "Peptide Trypsin Cleavage Sites",
    "peptide_dpp4_cleavage_motif_present": "Peptide DPP4 Cleavage Motif",
    "peptide_hydrophobic_patch_count": "Peptide Hydrophobic Patches",
    "peptide_hydrophilic_residue_fraction": "Peptide Hydrophilic Residue Fraction",
    "peptide_max_consecutive_identical_residues": "Peptide Max Consecutive Identical Residues",
    "peptide_max_consecutive_hydrophobic_residues": "Peptide Max Consecutive Hydrophobic Residues",
    "peptide_linear_unpaired_cysteine_count": "Peptide Linear Unpaired Cysteines",
    "peptide_cyclic_internal_unpaired_cysteine_count": "Peptide Cyclic Internal Unpaired Cysteines",
    "peptide_low_hydrophilic_flag": "Peptide Low Hydrophilic Flag",
    "peptide_consecutive_identical_flag": "Peptide Consecutive Identical Flag",
    "peptide_long_hydrophobic_run_flag": "Peptide Long Hydrophobic Run Flag",
    "peptide_linear_liability_score": "Peptide Linear Liability Score",
    "peptide_cyclic_liability_score": "Peptide Cyclic Liability Score",
}


PROPERTY_DESCRIPTIONS = {
    "length": "Sequence length in residues.",
    "molecular_weight": "Estimated molecular weight in Daltons.",
    "isoelectric_point": "Estimated isoelectric point (pI).",
    "instability_index": "Instability index; values below 40 are usually more stable.",
    "is_stable": "Binary stability flag derived from instability index.",
    "aromaticity": "Fraction of aromatic residues.",
    "gravy": "Grand average of hydropathy.",
    "hydropathy_kyte_doolittle": "Average Kyte-Doolittle hydropathy score.",
    "aliphatic_index": "Relative contribution of aliphatic side chains.",
    "shannon_entropy": "Shannon entropy of amino-acid composition.",
    "helix_fraction": "Predicted alpha-helical fraction.",
    "turn_fraction": "Predicted beta-turn fraction.",
    "sheet_fraction": "Predicted beta-sheet fraction.",
    "extinction_coefficient_reduced": "Extinction coefficient with reduced cysteines.",
    "extinction_coefficient_oxidized": "Extinction coefficient with cystines/disulfides.",
    "flexibility_mean": "Mean local flexibility from sliding-window estimation.",
    "flexibility_min": "Minimum local flexibility score.",
    "flexibility_max": "Maximum local flexibility score.",
    "deamidation_high_risk_motif_count": "Count of high-risk deamidation motifs matching N[GS].",
    "deamidation_medium_risk_motif_count": "Count of medium-risk deamidation motifs matching N[AHNT].",
    "deamidation_low_risk_motif_count": "Count of low-risk deamidation motifs matching [STK]N.",
    "n_glycosylation_motif_count": "Count of canonical N-glycosylation sequons matching N[^P][ST].",
    "aspartate_isomerization_motif_count": "Count of aspartate isomerization-prone motifs matching D[DGHST].",
    "aspartate_fragmentation_high_risk_motif_count": "Count of high-risk fragmentation motifs matching DP.",
    "aspartate_fragmentation_medium_risk_motif_count": "Count of medium-risk fragmentation motifs matching TS.",
    "methionine_oxidation_motif_count": "Count of methionine oxidation-prone sites (M).",
    "tryptophan_oxidation_motif_count": "Count of tryptophan oxidation-prone sites (W).",
    "integrin_binding_motif_count": "Count of integrin-binding motif hits (e.g., RGD, LDV, NGR).",
    "polyreactive_motif_count": "Count of sequence patterns associated with polyreactivity risk.",
    "aggregation_patch_motif_count": "Count of motif matches associated with aggregation patch risk (FHW).",
    "viscosity_patch_motif_count": "Count of motif matches associated with viscosity patch risk (HYF/HWH).",
    "unpaired_cysteine_count": "Approximate count of cysteines lacking a nearby putative pair.",
    "antibody_liability_motif_count": "Total count across antibody liability motifs and unpaired cysteines.",
    "antibody_liability_score": "Weighted antibody liability score from sequence motif counts.",
    "peptide_deamidation_hotspot_count": "Count of peptide deamidation hotspots matching N[GSQA].",
    "peptide_aspartate_cleavage_motif_count": "Count of peptide acidic cleavage motifs matching D[PGS].",
    "peptide_n_terminal_cyclization_risk": "1 when the sequence starts with Q or N, indicating N-terminal cyclization risk.",
    "peptide_trypsin_cleavage_site_count": "Count of internal trypsin cleavage sites (K/R not at C-terminus).",
    "peptide_dpp4_cleavage_motif_present": "1 when an N-terminal DPP4 cleavage motif (^[PX]?[AP]) is present.",
    "peptide_hydrophobic_patch_count": "Count of hydrophobic patches with 3+ consecutive FILVWY residues.",
    "peptide_hydrophilic_residue_fraction": "Fraction of hydrophilic residues (D,E,K,R,H,N,Q,S,T).",
    "peptide_max_consecutive_identical_residues": "Longest run of consecutive identical residues.",
    "peptide_max_consecutive_hydrophobic_residues": "Longest run of consecutive hydrophobic residues in FILVWY.",
    "peptide_linear_unpaired_cysteine_count": "For linear peptides with odd cysteine count, flags all cysteines as potentially unpaired.",
    "peptide_cyclic_internal_unpaired_cysteine_count": "For cyclic peptides, potential unpaired cysteine count among internal cysteines only.",
    "peptide_low_hydrophilic_flag": "1 when hydrophilic residue fraction is below 0.40.",
    "peptide_consecutive_identical_flag": "1 when any consecutive identical run is longer than one residue.",
    "peptide_long_hydrophobic_run_flag": "1 when the longest FILVWY run exceeds four residues.",
    "peptide_linear_liability_score": "Weighted linear-peptide liability score from motif and composition flags.",
    "peptide_cyclic_liability_score": "Weighted cyclic-peptide liability score with cyclic-specific penalties.",
}


ANTIBODY_LIABILITY_KEYS = {
    "deamidation_high_risk_motif_count",
    "deamidation_medium_risk_motif_count",
    "deamidation_low_risk_motif_count",
    "n_glycosylation_motif_count",
    "aspartate_isomerization_motif_count",
    "aspartate_fragmentation_high_risk_motif_count",
    "aspartate_fragmentation_medium_risk_motif_count",
    "methionine_oxidation_motif_count",
    "tryptophan_oxidation_motif_count",
    "integrin_binding_motif_count",
    "polyreactive_motif_count",
    "aggregation_patch_motif_count",
    "viscosity_patch_motif_count",
    "unpaired_cysteine_count",
    "antibody_liability_motif_count",
    "antibody_liability_score",
}

PEPTIDE_LIABILITY_KEYS = {
    "peptide_deamidation_hotspot_count",
    "peptide_aspartate_cleavage_motif_count",
    "peptide_n_terminal_cyclization_risk",
    "peptide_trypsin_cleavage_site_count",
    "peptide_dpp4_cleavage_motif_present",
    "peptide_hydrophobic_patch_count",
    "peptide_hydrophilic_residue_fraction",
    "peptide_max_consecutive_identical_residues",
    "peptide_max_consecutive_hydrophobic_residues",
    "peptide_linear_unpaired_cysteine_count",
    "peptide_cyclic_internal_unpaired_cysteine_count",
    "peptide_low_hydrophilic_flag",
    "peptide_consecutive_identical_flag",
    "peptide_long_hydrophobic_run_flag",
    "peptide_linear_liability_score",
    "peptide_cyclic_liability_score",
}

ANTIBODY_LIABILITY_ORDER = {
    "deamidation_high_risk_motif_count": 0,
    "deamidation_medium_risk_motif_count": 1,
    "deamidation_low_risk_motif_count": 2,
    "n_glycosylation_motif_count": 3,
    "aspartate_isomerization_motif_count": 4,
    "aspartate_fragmentation_high_risk_motif_count": 5,
    "aspartate_fragmentation_medium_risk_motif_count": 6,
    "methionine_oxidation_motif_count": 7,
    "tryptophan_oxidation_motif_count": 8,
    "integrin_binding_motif_count": 9,
    "polyreactive_motif_count": 10,
    "aggregation_patch_motif_count": 11,
    "viscosity_patch_motif_count": 12,
    "unpaired_cysteine_count": 13,
    "antibody_liability_motif_count": 14,
    "antibody_liability_score": 15,
}

PEPTIDE_LIABILITY_ORDER = {
    "peptide_deamidation_hotspot_count": 0,
    "peptide_aspartate_cleavage_motif_count": 1,
    "peptide_n_terminal_cyclization_risk": 2,
    "peptide_trypsin_cleavage_site_count": 3,
    "peptide_dpp4_cleavage_motif_present": 4,
    "peptide_hydrophobic_patch_count": 5,
    "peptide_hydrophilic_residue_fraction": 6,
    "peptide_max_consecutive_identical_residues": 7,
    "peptide_max_consecutive_hydrophobic_residues": 8,
    "peptide_linear_unpaired_cysteine_count": 9,
    "peptide_cyclic_internal_unpaired_cysteine_count": 10,
    "peptide_low_hydrophilic_flag": 11,
    "peptide_consecutive_identical_flag": 12,
    "peptide_long_hydrophobic_run_flag": 13,
    "peptide_linear_liability_score": 14,
    "peptide_cyclic_liability_score": 15,
}


PROTEIN_THRESHOLDS: Dict[str, ProteinThreshold] = {
    "length": ProteinThreshold(
        "length",
        "Length",
        "aa",
        (50.0, 1200.0),
        (20.0, 2000.0),
        PROPERTY_DESCRIPTIONS["length"],
    ),
    "molecular_weight": ProteinThreshold(
        "molecular_weight",
        "Molecular Weight",
        "Da",
        (5_000.0, 150_000.0),
        (2_000.0, 250_000.0),
        PROPERTY_DESCRIPTIONS["molecular_weight"],
    ),
    "isoelectric_point": ProteinThreshold(
        "isoelectric_point",
        "Isoelectric Point (pI)",
        "",
        (5.0, 9.0),
        (4.0, 10.5),
        PROPERTY_DESCRIPTIONS["isoelectric_point"],
    ),
    "instability_index": ProteinThreshold(
        "instability_index",
        "Instability Index",
        "",
        (-float("inf"), 40.0),
        (-float("inf"), 60.0),
        PROPERTY_DESCRIPTIONS["instability_index"],
    ),
    "is_stable": ProteinThreshold(
        "is_stable",
        "Predicted Stable",
        "",
        (1.0, 1.0),
        (1.0, 1.0),
        PROPERTY_DESCRIPTIONS["is_stable"],
    ),
    "aromaticity": ProteinThreshold(
        "aromaticity",
        "Aromaticity",
        "",
        (0.03, 0.20),
        (0.01, 0.30),
        PROPERTY_DESCRIPTIONS["aromaticity"],
    ),
    "gravy": ProteinThreshold(
        "gravy",
        "GRAVY",
        "",
        (-0.8, 0.8),
        (-1.5, 1.5),
        PROPERTY_DESCRIPTIONS["gravy"],
    ),
    "hydropathy_kyte_doolittle": ProteinThreshold(
        "hydropathy_kyte_doolittle",
        "Hydropathy (Kyte-Doolittle)",
        "",
        (-0.8, 0.8),
        (-1.5, 1.5),
        PROPERTY_DESCRIPTIONS["hydropathy_kyte_doolittle"],
    ),
    "aliphatic_index": ProteinThreshold(
        "aliphatic_index",
        "Aliphatic Index",
        "",
        (60.0, 120.0),
        (40.0, 140.0),
        PROPERTY_DESCRIPTIONS["aliphatic_index"],
    ),
    "shannon_entropy": ProteinThreshold(
        "shannon_entropy",
        "Shannon Entropy",
        "",
        (2.2, 4.3),
        (1.8, 4.35),
        PROPERTY_DESCRIPTIONS["shannon_entropy"],
    ),
    "flexibility_mean": ProteinThreshold(
        "flexibility_mean",
        "Flexibility Mean",
        "",
        (0.30, 0.65),
        (0.20, 0.85),
        PROPERTY_DESCRIPTIONS["flexibility_mean"],
    ),
}


PROTEIN_INSIGHTS: Dict[str, ProteinInsight] = {
    "length": ProteinInsight(
        what="Total amino-acid count of the sequence.",
        why="Length drives expression burden, fold complexity, and manufacturing scope.",
        low_signal="Very short chains may lack autonomous fold stability.",
        high_signal="Very long chains can increase design, folding, and purification risk.",
        design_levers="Trim flexible tails or split domains when architecture allows.",
    ),
    "molecular_weight": ProteinInsight(
        what="Estimated molecular mass from sequence composition.",
        why="Mass influences delivery strategy, diffusion, and process constraints.",
        low_signal="Lower mass can improve penetration but may reduce interface area.",
        high_signal="Higher mass can improve avidity but increase production complexity.",
        design_levers="Optimize domain architecture and linker length to balance size and function.",
    ),
    "isoelectric_point": ProteinInsight(
        what="Predicted pH where net charge is near zero.",
        why="pI informs solubility behavior and formulation pH selection.",
        low_signal="Low pI skews sequence toward acidic character.",
        high_signal="High pI skews sequence toward basic character.",
        design_levers="Swap charged residues away from critical motifs to tune global charge balance.",
    ),
    "instability_index": ProteinInsight(
        what="Empirical instability score derived from dipeptide composition.",
        why="Useful early proxy for sequence robustness in expression contexts.",
        low_signal="Lower values indicate a more stable composition profile.",
        high_signal="Higher values can flag susceptibility to degradation.",
        design_levers="Reduce destabilizing motifs and rebalance residue composition in flexible regions.",
    ),
    "is_stable": ProteinInsight(
        what="Binary stability flag based on instability index threshold.",
        why="Offers a quick triage signal before deeper structural validation.",
        low_signal="`No` indicates additional sequence hardening may be needed.",
        high_signal="`Yes` indicates composition is consistent with baseline stability priors.",
        design_levers="Use conservative residue swaps in loops/linkers to improve the stability score.",
    ),
    "gravy": ProteinInsight(
        what="Average hydropathy across residues (GRAVY).",
        why="Hydropathy balance affects solubility, aggregation risk, and membrane affinity.",
        low_signal="Very negative values indicate strong overall hydrophilicity.",
        high_signal="Very positive values indicate strong hydrophobicity.",
        design_levers="Tune solvent-exposed hydrophobic patches while preserving core packing.",
    ),
    "hydropathy_kyte_doolittle": ProteinInsight(
        what="Kyte-Doolittle mean hydropathy index.",
        why="Complements GRAVY when comparing sequence-level hydrophobic trends.",
        low_signal="Low values indicate polar/charged enrichment.",
        high_signal="High values indicate hydrophobic enrichment.",
        design_levers="Redistribute hydrophobic residues between surface and core-compatible regions.",
    ),
    "aliphatic_index": ProteinInsight(
        what="Relative abundance of aliphatic side chains (A, V, I, L).",
        why="Often associated with thermostability tendencies in globular proteins.",
        low_signal="Low values can indicate reduced aliphatic packing contribution.",
        high_signal="High values suggest stronger aliphatic side-chain contribution.",
        design_levers="Adjust aliphatic substitutions in structurally tolerant regions.",
    ),
    "shannon_entropy": ProteinInsight(
        what="Entropy of amino-acid composition.",
        why="Captures compositional diversity versus residue bias in the sequence.",
        low_signal="Low entropy indicates strong residue bias.",
        high_signal="High entropy indicates more even residue usage.",
        design_levers="Reduce extreme motif repetition where it is not functionally required.",
    ),
    "helix_fraction": ProteinInsight(
        what="Predicted alpha-helical content fraction.",
        why="Helical propensity helps assess secondary-structure balance.",
        low_signal="Lower values indicate less helical tendency.",
        high_signal="Higher values indicate stronger helical tendency.",
        design_levers="Adjust helix-breaking/promoting residues in target regions.",
    ),
    "turn_fraction": ProteinInsight(
        what="Predicted beta-turn content fraction.",
        why="Turn propensity can affect flexibility and loop geometry.",
        low_signal="Lower values indicate fewer turn-prone motifs.",
        high_signal="Higher values indicate more turn-prone composition.",
        design_levers="Tune glycine/proline placement to reshape local turn behavior.",
    ),
    "sheet_fraction": ProteinInsight(
        what="Predicted beta-sheet content fraction.",
        why="Sheet propensity contributes to fold architecture and aggregation profile.",
        low_signal="Lower values indicate weaker sheet tendency.",
        high_signal="Higher values indicate stronger sheet tendency.",
        design_levers="Rebalance sheet-forming residues in beta-rich segments.",
    ),
    "extinction_coefficient_reduced": ProteinInsight(
        what="Predicted UV absorbance coefficient assuming reduced cysteines.",
        why="Useful for concentration estimation in purified protein workflows.",
        low_signal="Lower values reduce UV absorbance signal at 280 nm.",
        high_signal="Higher values improve UV detectability but reflect aromatic/cystine composition.",
        design_levers="Consider aromatic residue placement and disulfide strategy when optimizing readout.",
    ),
    "extinction_coefficient_oxidized": ProteinInsight(
        what="Predicted UV absorbance coefficient assuming oxidized cystines.",
        why="Supports concentration planning when disulfides are expected.",
        low_signal="Lower values indicate weaker UV signal under oxidized assumptions.",
        high_signal="Higher values indicate stronger UV signal under oxidized assumptions.",
        design_levers="Tune aromatic/disulfide-rich regions with structural constraints in mind.",
    ),
    "flexibility_mean": ProteinInsight(
        what="Average local flexibility estimate across the sequence.",
        why="Highlights overall tendency toward rigid versus mobile behavior.",
        low_signal="Lower values indicate a generally more rigid sequence profile.",
        high_signal="Higher values indicate broader local mobility.",
        design_levers="Stabilize high-flexibility segments with helix-promoting or packing-friendly substitutions.",
    ),
}


def _compact_key(key: str) -> str:
    return key.lower().replace("_", "").replace("-", "").replace(" ", "")


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    return not math.isnan(numeric) and not math.isinf(numeric)


def _format_value(value: Any, precision: int = 3) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "N/A"
        if abs(value) < 0.001 or abs(value) >= 10000:
            return f"{value:.2e}"
        return f"{value:.{precision}g}"
    if value is None:
        return "N/A"
    return str(value)


def _format_range_bound(value: float) -> str:
    if math.isinf(value):
        return "infinity" if value > 0 else "-infinity"
    if value == 0:
        return "0"
    if abs(value) < 0.001 or abs(value) >= 10000:
        return f"{value:.1e}"
    return f"{value:.3g}"


def _format_range(low: float, high: float, unit: str) -> str:
    if math.isinf(low) and math.isinf(high):
        body = "any value"
    elif math.isinf(low):
        body = f"<= {_format_range_bound(high)}"
    elif math.isinf(high):
        body = f">= {_format_range_bound(low)}"
    else:
        body = f"{_format_range_bound(low)} to {_format_range_bound(high)}"

    if unit:
        return f"{body} {unit}"
    return body


def _get_status_class(value: float, threshold: ProteinThreshold) -> str:
    opt_low, opt_high = threshold.optimal_range
    warn_low, warn_high = threshold.warning_range

    if opt_low <= value <= opt_high:
        return "optimal"
    if warn_low <= value <= warn_high:
        return "warning"
    return "danger"


def _normalize_key(key: str) -> str:
    normalized = key.strip()
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    normalized = normalized.lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return _ALIASES.get(normalized, normalized)


def _key_to_ph_label(norm_key: str) -> str:
    if not norm_key.startswith("net_charge_ph_"):
        return ""
    ph_token = norm_key.removeprefix("net_charge_ph_")
    return ph_token.replace("_", ".")


def _label_for_key(norm_key: str, raw_key: str) -> str:
    if norm_key in PROPERTY_LABELS:
        return PROPERTY_LABELS[norm_key]

    ph_label = _key_to_ph_label(norm_key)
    if ph_label:
        return f"Net Charge @ pH {ph_label}"

    if norm_key.startswith("count_"):
        aa_name = norm_key.removeprefix("count_").replace("_", " ").title()
        return f"{aa_name} Count"

    if norm_key.startswith("fraction_"):
        aa_name = norm_key.removeprefix("fraction_").replace("_", " ").title()
        return f"{aa_name} Fraction"

    return raw_key.replace("_", " ").title()


def _description_for_key(norm_key: str, label: str) -> str:
    if norm_key in PROPERTY_DESCRIPTIONS:
        return PROPERTY_DESCRIPTIONS[norm_key]

    ph_label = _key_to_ph_label(norm_key)
    if ph_label:
        return f"Estimated net charge at pH {ph_label}."

    if norm_key.startswith("count_"):
        token = norm_key.removeprefix("count_")
        aa_code = _THREE_TO_ONE.get(token, "?")
        return f"Residue count for {aa_code} ({token.upper()})."

    if norm_key.startswith("fraction_"):
        token = norm_key.removeprefix("fraction_")
        aa_code = _THREE_TO_ONE.get(token, "?")
        return f"Residue fraction for {aa_code} ({token.upper()})."

    if norm_key.endswith("_fraction"):
        return f"Fractional composition metric for {label}."

    return "Predicted protein property value."


def _dynamic_threshold(
    norm_key: str, label: str, description: str
) -> ProteinThreshold | None:
    if norm_key.endswith("_liability_score"):
        return ProteinThreshold(
            norm_key,
            label,
            "",
            (0.0, 20.0),
            (0.0, 40.0),
            description,
        )

    if norm_key.endswith("_flag") or norm_key.endswith("_present") or norm_key.endswith(
        "_risk"
    ):
        return ProteinThreshold(
            norm_key,
            label,
            "",
            (0.0, 0.0),
            (0.0, 0.0),
            description,
        )

    if (
        norm_key.endswith("_motif_count")
        or norm_key.endswith("_site_count")
        or norm_key.endswith("_unpaired_cysteine_count")
        or norm_key == "unpaired_cysteine_count"
    ):
        return ProteinThreshold(
            norm_key,
            label,
            "",
            (0.0, 0.0),
            (0.0, 1.0),
            description,
        )

    if norm_key.startswith("count_"):
        return ProteinThreshold(
            norm_key,
            label,
            "",
            (0.0, float("inf")),
            (0.0, float("inf")),
            description,
        )

    if norm_key.startswith("fraction_") or norm_key.endswith("_fraction"):
        return ProteinThreshold(
            norm_key,
            label,
            "",
            (0.0, 1.0),
            (-0.05, 1.05),
            description,
        )

    if norm_key.startswith("extinction_coefficient_"):
        return ProteinThreshold(
            norm_key,
            label,
            "M^-1 cm^-1",
            (0.0, float("inf")),
            (0.0, float("inf")),
            description,
        )

    return None


def _infer_property_category(norm_key: str) -> str:
    if norm_key in {
        "length",
        "molecular_weight",
        "isoelectric_point",
        "instability_index",
        "is_stable",
        "aromaticity",
        "gravy",
        "hydropathy_kyte_doolittle",
        "aliphatic_index",
        "shannon_entropy",
    }:
        return "core_metrics"

    if norm_key in PEPTIDE_LIABILITY_KEYS or norm_key.startswith("peptide_"):
        return "peptide_liability"

    if norm_key in ANTIBODY_LIABILITY_KEYS:
        return "antibody_liability"

    if norm_key.startswith("net_charge_ph_") or norm_key in {
        "charged_residue_fraction",
        "positive_residue_fraction",
        "negative_residue_fraction",
    }:
        return "charge_profile"

    if norm_key in {"helix_fraction", "turn_fraction", "sheet_fraction"}:
        return "secondary_structure"

    if norm_key.startswith("flexibility_") or norm_key.startswith(
        "extinction_coefficient_"
    ):
        return "flexibility_absorbance"

    if norm_key.startswith("count_") or norm_key.startswith("fraction_"):
        return "amino_acids"

    if norm_key.endswith("_fraction"):
        return "composition"

    return "other"


def _property_sort_key(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    category = str(row.get("category", "other"))
    norm_key = str(row.get("normalized_key", row.get("key", "")))
    label_key = str(row.get("label", "")).lower()

    if category == "core_metrics":
        order = {
            "length": 0,
            "molecular_weight": 1,
            "isoelectric_point": 2,
            "instability_index": 3,
            "is_stable": 4,
            "aromaticity": 5,
            "gravy": 6,
            "hydropathy_kyte_doolittle": 7,
            "aliphatic_index": 8,
            "shannon_entropy": 9,
        }
        return (0, order.get(norm_key, 999), 0, label_key)

    if category == "charge_profile":
        if norm_key.startswith("net_charge_ph_"):
            ph_label = _key_to_ph_label(norm_key)
            try:
                return (0, 0, int(float(ph_label) * 10), label_key)
            except Exception:
                return (0, 0, 999, label_key)
        order = {
            "charged_residue_fraction": 1,
            "positive_residue_fraction": 2,
            "negative_residue_fraction": 3,
        }
        return (0, order.get(norm_key, 999), 0, label_key)

    if category == "secondary_structure":
        order = {"helix_fraction": 0, "turn_fraction": 1, "sheet_fraction": 2}
        return (0, order.get(norm_key, 999), 0, label_key)

    if category == "flexibility_absorbance":
        order = {
            "flexibility_mean": 0,
            "flexibility_min": 1,
            "flexibility_max": 2,
            "extinction_coefficient_reduced": 3,
            "extinction_coefficient_oxidized": 4,
        }
        return (0, order.get(norm_key, 999), 0, label_key)

    if category == "antibody_liability":
        return (0, ANTIBODY_LIABILITY_ORDER.get(norm_key, 999), 0, label_key)

    if category == "peptide_liability":
        return (0, PEPTIDE_LIABILITY_ORDER.get(norm_key, 999), 0, label_key)

    if category == "composition":
        order = {
            "hydrophobic_residue_fraction": 0,
            "polar_residue_fraction": 1,
            "nonpolar_residue_fraction": 2,
            "charged_residue_fraction": 3,
            "positive_residue_fraction": 4,
            "negative_residue_fraction": 5,
            "tiny_residue_fraction": 6,
            "small_residue_fraction": 7,
            "sulfur_residue_fraction": 8,
            "glycine_fraction": 9,
            "proline_fraction": 10,
            "cysteine_fraction": 11,
        }
        return (0, order.get(norm_key, 999), 0, label_key)

    if category == "amino_acids":
        if norm_key.startswith("count_"):
            token = norm_key.removeprefix("count_")
            aa_code = _THREE_TO_ONE.get(token, token)
            return (0, 0, ord(aa_code[0]) if aa_code else 999, label_key)
        if norm_key.startswith("fraction_"):
            token = norm_key.removeprefix("fraction_")
            aa_code = _THREE_TO_ONE.get(token, token)
            return (0, 1, ord(aa_code[0]) if aa_code else 999, label_key)
        return (0, 2, 0, label_key)

    return (0, 999, 0, label_key)


def _auto_property_insight(
    norm_key: str,
    raw_key: str,
    label: str,
    description: str,
    category: str,
) -> ProteinInsight:
    label_clean = label.strip() or raw_key
    description_text = description.strip()
    what_text = (
        description_text
        if description_text
        else f"{label_clean} is a computed protein property."
    )

    ph_label = _key_to_ph_label(norm_key)
    if ph_label:
        return ProteinInsight(
            what=f"Estimated net sequence charge at pH {ph_label}.",
            why="Charge profile affects solubility, colloidal behavior, and purification strategy.",
            low_signal="More negative values indicate acidic residue dominance at this pH.",
            high_signal="More positive values indicate basic residue dominance at this pH.",
            design_levers="Adjust Asp/Glu versus Lys/Arg/His balance away from functional hotspots.",
        )

    if norm_key.startswith("count_"):
        token = norm_key.removeprefix("count_")
        aa_code = _THREE_TO_ONE.get(token, "?")
        return ProteinInsight(
            what=f"Absolute count of residue {aa_code} ({token.upper()}).",
            why="Residue counts shape fold propensity, interface chemistry, and expression behavior.",
            low_signal="Low count means this residue contributes minimally to sequence behavior.",
            high_signal="High count means this residue strongly influences global properties.",
            design_levers="Target substitutions in non-conserved regions to rebalance composition.",
        )

    if norm_key.startswith("fraction_"):
        token = norm_key.removeprefix("fraction_")
        aa_code = _THREE_TO_ONE.get(token, "?")
        return ProteinInsight(
            what=f"Fractional abundance of residue {aa_code} ({token.upper()}).",
            why="Amino-acid fractions reveal composition bias that impacts developability.",
            low_signal="Low fraction indicates limited contribution from this residue type.",
            high_signal="High fraction indicates this residue class dominates sequence composition.",
            design_levers="Introduce conservative alternatives to smooth extreme composition bias.",
        )

    if category == "antibody_liability":
        if norm_key.endswith("_liability_score"):
            return ProteinInsight(
                what=what_text,
                why="Aggregated antibody liability scores provide a fast sequence-level developability risk screen.",
                low_signal="Lower scores generally indicate fewer sequence liability hotspots.",
                high_signal="Higher scores indicate accumulating chemical or biophysical liability patterns.",
                design_levers="Prioritize conservative substitutions that reduce hotspot motifs outside CDR-critical positions.",
            )
        return ProteinInsight(
            what=what_text,
            why="Antibody liability signals flag motifs associated with degradation, heterogeneity, aggregation, or viscosity risk.",
            low_signal="Lower counts indicate fewer sequence motifs associated with liability.",
            high_signal="Higher counts indicate more potential liability hotspots to triage.",
            design_levers="Use sequence hardening passes to remove avoidable hotspots while preserving binding interfaces.",
        )

    if category == "peptide_liability":
        if norm_key.endswith("_flag") or norm_key.endswith("_present") or norm_key.endswith(
            "_risk"
        ):
            return ProteinInsight(
                what=what_text,
                why="Binary peptide liability triggers capture known sequence liabilities in a compact deployability screen.",
                low_signal="`0` means the specific liability trigger is not currently detected.",
                high_signal="`1` means the trigger is present and should be reviewed for sequence hardening.",
                design_levers="Shift local residue patterns near the motif while keeping potency and selectivity motifs intact.",
            )
        if norm_key.endswith("_liability_score"):
            return ProteinInsight(
                what=what_text,
                why="Peptide liability scores summarize multiple instability and cleavage liabilities into a triage metric.",
                low_signal="Lower scores indicate fewer modeled sequence liabilities for this peptide format.",
                high_signal="Higher scores indicate stacked liabilities that can reduce peptide robustness.",
                design_levers="Address high-weight liabilities first, then re-run scoring to confirm risk reduction.",
            )
        return ProteinInsight(
            what=what_text,
            why="Peptide liability counts identify motif-level risks tied to deamidation, cleavage, oxidation, and aggregation behavior.",
            low_signal="Lower values indicate fewer motif-driven liabilities for this sequence.",
            high_signal="Higher values indicate more sequence motifs that may limit peptide stability or PK.",
            design_levers="Apply motif-focused substitutions and re-evaluate cleavage/hydrophobicity patterns iteratively.",
        )

    if category == "composition":
        return ProteinInsight(
            what=f"{label_clean} quantifies sequence composition balance.",
            why="Composition-level signals connect sequence edits to stability and manufacturability.",
            low_signal="Lower values indicate reduced contribution from this residue class.",
            high_signal="Higher values indicate stronger contribution from this residue class.",
            design_levers="Tune residue class balance in loops/linkers while preserving active motifs.",
        )

    if category == "secondary_structure":
        return ProteinInsight(
            what=f"{label_clean} estimates secondary-structure propensity.",
            why="Secondary-structure balance provides quick foldability context.",
            low_signal="Lower values indicate weaker propensity for this structure type.",
            high_signal="Higher values indicate stronger propensity for this structure type.",
            design_levers="Adjust helix/sheet breakers or promoters in candidate segments.",
        )

    if category == "core_metrics":
        return ProteinInsight(
            what=f"{label_clean} is a core sequence-derived protein metric.",
            why="Core metrics provide fast triage before heavier structural workflows.",
            low_signal="Lower values may indicate underrepresentation of this trait.",
            high_signal="Higher values may indicate overrepresentation of this trait.",
            design_levers="Use conservative local substitutions to move the metric without disrupting function.",
        )

    return ProteinInsight(
        what=what_text,
        why="Combined interpretation across properties is most informative for sequence prioritization.",
        low_signal="Lower values indicate reduced expression of this property signal.",
        high_signal="Higher values indicate stronger expression of this property signal.",
        design_levers="Iterate sequence edits with structure/context constraints and re-evaluate as a panel.",
    )


class ProteinPropertiesView:
    """Jupyter widget for displaying protein properties with rich tooltips.

    Parameters
    ----------
    properties : dict
        Dictionary of protein property names to values.
    title : str, optional
        Title to display above the property table.
    show_categories : bool, optional
        If True, show category tabs and grouped rows.
    compact : bool, optional
        If True, use a narrower panel width.
    """

    def __init__(
        self,
        properties: Mapping[str, Any],
        title: str = "Protein Properties",
        show_categories: bool = True,
        compact: bool = False,
    ):
        self.properties = dict(properties)
        self.title = title
        self.show_categories = show_categories
        self.compact = compact
        self._element_id = f"proteinprops-{uuid.uuid4().hex[:8]}"

    def _build_property_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for key, value in self.properties.items():
            raw_key = str(key)
            norm_key = _normalize_key(raw_key)
            label = _label_for_key(norm_key, raw_key)
            description = _description_for_key(norm_key, label)

            threshold = PROTEIN_THRESHOLDS.get(norm_key)
            if threshold is None:
                threshold = _dynamic_threshold(norm_key, label, description)

            row: Dict[str, Any] = {
                "key": raw_key,
                "normalized_key": norm_key,
                "label": label,
                "value": value,
                "formatted_value": _format_value(value),
                "description": description,
                "category": _infer_property_category(norm_key),
            }

            if threshold is not None:
                row["unit"] = threshold.unit
                row["optimal_range"] = _format_range(
                    threshold.optimal_range[0],
                    threshold.optimal_range[1],
                    threshold.unit,
                )
                row["warning_range"] = _format_range(
                    threshold.warning_range[0],
                    threshold.warning_range[1],
                    threshold.unit,
                )
                if _is_finite_number(value):
                    row["status"] = _get_status_class(float(value), threshold)
                else:
                    row["status"] = "unknown"
            else:
                row["unit"] = ""
                row["optimal_range"] = ""
                row["warning_range"] = ""
                row["status"] = "unknown"

            insight = PROTEIN_INSIGHTS.get(norm_key)
            if insight is None:
                insight = _auto_property_insight(
                    norm_key=norm_key,
                    raw_key=raw_key,
                    label=label,
                    description=description,
                    category=str(row.get("category", "other")),
                )
            row["insight"] = insight

            rows.append(row)

        return rows

    def _group_rows(
        self, rows: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not self.show_categories:
            return {"all": rows}

        categories: Dict[str, List[Dict[str, Any]]] = {
            key: [] for key in CATEGORY_ORDER
        }

        for row in rows:
            cat = str(row.get("category", "other"))
            if cat in categories:
                categories[cat].append(row)
            else:
                categories["other"].append(row)

        for key in categories:
            categories[key] = sorted(categories[key], key=_property_sort_key)
        return categories

    def _render_tooltip(self, row: Mapping[str, Any]) -> str:
        label = html.escape(str(row.get("label", "Property")))
        current_value = html.escape(str(row.get("formatted_value", "N/A")))
        unit = html.escape(str(row.get("unit", "")))
        current_text = f"{current_value} {unit}".strip()
        description = str(row.get("description", "")).strip()

        insight = row.get("insight")
        if not isinstance(insight, ProteinInsight):
            insight = None

        status = str(row.get("status", "unknown"))
        status_label_map = {
            "optimal": "In target window",
            "warning": "Borderline",
            "danger": "Outside preferred window",
            "unknown": "No calibrated threshold",
        }
        status_label = html.escape(
            status_label_map.get(status, status_label_map["unknown"])
        )
        status_class = (
            f"tooltip-status-{status if status in status_label_map else 'unknown'}"
        )

        what_text = (
            insight.what
            if insight and insight.what
            else (description if description else "Predicted protein property value.")
        )
        why_text = (
            insight.why
            if insight and insight.why
            else "Interpret against sequence context and neighboring properties."
        )

        low_text = insight.low_signal if insight and insight.low_signal else ""
        high_text = insight.high_signal if insight and insight.high_signal else ""
        levers_text = insight.design_levers if insight and insight.design_levers else ""
        optimal_range = str(row.get("optimal_range", "")).strip()
        warning_range = str(row.get("warning_range", "")).strip()

        html_parts = [
            '<span class="admet-tooltip-card" role="tooltip">',
            f'    <span class="admet-tooltip-title">{label}</span>',
            f'    <span class="admet-tooltip-status {status_class}">{status_label}</span>',
            '    <span class="admet-tooltip-grid">',
            '        <span class="admet-tooltip-key">Current</span>',
            f'        <span class="admet-tooltip-text">{current_text}</span>',
            '        <span class="admet-tooltip-key">What</span>',
            f'        <span class="admet-tooltip-text">{html.escape(what_text)}</span>',
            '        <span class="admet-tooltip-key">Why It Matters</span>',
            f'        <span class="admet-tooltip-text">{html.escape(why_text)}</span>',
        ]

        if optimal_range:
            html_parts.extend(
                [
                    '        <span class="admet-tooltip-key">Typical Window</span>',
                    f'        <span class="admet-tooltip-text">{html.escape(optimal_range)}</span>',
                ]
            )
        if warning_range:
            html_parts.extend(
                [
                    '        <span class="admet-tooltip-key">Watch Zone</span>',
                    f'        <span class="admet-tooltip-text">{html.escape(warning_range)}</span>',
                ]
            )
        if low_text:
            html_parts.extend(
                [
                    '        <span class="admet-tooltip-key">If Too Low</span>',
                    f'        <span class="admet-tooltip-text">{html.escape(low_text)}</span>',
                ]
            )
        if high_text:
            html_parts.extend(
                [
                    '        <span class="admet-tooltip-key">If Too High</span>',
                    f'        <span class="admet-tooltip-text">{html.escape(high_text)}</span>',
                ]
            )
        if levers_text:
            html_parts.extend(
                [
                    '        <span class="admet-tooltip-key">Protein-Engineering Levers</span>',
                    f'        <span class="admet-tooltip-text">{html.escape(levers_text)}</span>',
                ]
            )

        html_parts.extend(["    </span>", "</span>"])
        return "\n".join(html_parts)

    def _render_rows(self, rows: List[Dict[str, Any]]) -> List[str]:
        html_parts: List[str] = []
        for row in rows:
            escaped_label = html.escape(str(row.get("label", "")))
            escaped_value = html.escape(str(row.get("formatted_value", "")))
            escaped_unit = html.escape(str(row.get("unit", "")))
            status_class = f"admet-status-{row.get('status', 'unknown')}"
            search_blob = html.escape(
                f"{row.get('label', '')} {row.get('key', '')}".lower(),
                quote=True,
            )
            category = html.escape(str(row.get("category", "other")), quote=True)

            tooltip_html = self._render_tooltip(row)
            tooltip_label = html.escape(
                f"More protein context for {row.get('label', 'property')}",
                quote=True,
            )
            unit_html = (
                f'<span class="admet-unit">{escaped_unit}</span>'
                if escaped_unit
                else ""
            )

            html_parts.append(
                f"""        <div class="admet-row" data-admet-row="1" data-admet-search="{search_blob}" data-admet-category="{category}">
            <span class="admet-label-wrap">
                <span class="admet-label">{escaped_label}</span>
                <button type="button" class="admet-tooltip-trigger" data-admet-tooltip="1" aria-label="{tooltip_label}">
                    ?
{tooltip_html}
                </button>
            </span>
            <span class="admet-value {status_class}">{escaped_value}{unit_html}</span>
        </div>"""
            )

        return html_parts

    def _render_html(self) -> str:
        rows = self._build_property_rows()
        categories = self._group_rows(rows)

        category_keys: List[str] = []
        if self.show_categories:
            category_keys = [
                key for key in CATEGORY_ORDER if categories.get(key)
            ]

        show_tabs = self.show_categories and len(category_keys) > 0

        escaped_title = html.escape(self.title)
        compact_class = " admet-compact" if self.compact else ""
        element_id = html.escape(self._element_id, quote=True)
        filter_id = f"{element_id}-filter"

        html_parts = [f"""
<style>
.admet-view {{
    --admet-ink: #0f172a;
    --admet-muted: #475569;
    --admet-panel-border: #d6deea;
    --admet-row-border: #e2e8f0;
    --admet-row-hover: linear-gradient(90deg, #f8fafc 0%, #eef2ff 100%);
    font-family: "Avenir Next", "Segoe UI", Roboto, sans-serif;
    max-width: 800px;
    margin: 16px 0;
    background: linear-gradient(145deg, #f8fafc 0%, #ffffff 42%, #f8fafc 100%);
    border: 1px solid var(--admet-panel-border);
    border-radius: 16px;
    overflow: visible;
    box-shadow: 0 18px 36px rgba(15, 23, 42, 0.12), 0 3px 8px rgba(15, 23, 42, 0.08);
    position: relative;
}}
.admet-view::before {{
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
    background: linear-gradient(90deg, #0284c7 0%, #0f766e 50%, #16a34a 100%);
}}
.admet-view.admet-compact {{ max-width: 520px; }}
.admet-header {{
    background: linear-gradient(130deg, #0f172a 0%, #1e293b 58%, #134e4a 100%);
    color: #f8fafc;
    padding: 14px 18px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.02em;
    border-radius: 16px 16px 0 0;
}}
.admet-toolbar {{
    padding: 12px 18px;
    border-bottom: 1px solid var(--admet-row-border);
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
}}
.admet-filter-input {{
    width: 100%;
    max-width: 260px;
    padding: 8px 11px;
    border: 1px solid #bfccdd;
    border-radius: 10px;
    font-size: 12px;
    color: var(--admet-ink);
    background: #ffffff;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}}
.admet-view.admet-compact .admet-filter-input {{
    max-width: 190px;
}}
.admet-filter-input:focus {{
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.16);
}}
.admet-tabs {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px 18px;
    border-bottom: 1px solid var(--admet-row-border);
    background: #f8fafc;
}}
.admet-tab {{
    border: 1px solid #c3cfdf;
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    color: #334155;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 12px;
    cursor: pointer;
    transition: all 140ms ease;
}}
.admet-tab:hover {{
    background: #eef2ff;
    border-color: #93c5fd;
}}
.admet-tab.active {{
    background: linear-gradient(180deg, #dbeafe 0%, #bfdbfe 100%);
    border-color: #60a5fa;
    color: #1e3a8a;
    box-shadow: 0 3px 10px rgba(37, 99, 235, 0.24);
}}
.admet-panels {{
    background: #ffffff;
    border-radius: 0 0 16px 16px;
}}
.admet-panel {{
    display: none;
}}
.admet-panel.active {{
    display: block;
}}
.admet-empty {{
    display: none;
    padding: 12px 18px;
    font-size: 12px;
    color: #64748b;
    font-style: italic;
}}
.admet-section {{
    border-bottom: 1px solid var(--admet-row-border);
}}
.admet-section:last-child {{
    border-bottom: none;
}}
.admet-section-header {{
    background: linear-gradient(90deg, #f8fafc 0%, #eef2ff 100%);
    padding: 9px 18px;
    font-size: 12px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
.admet-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 11px 18px;
    border-bottom: 1px solid #edf2f7;
    transition: background 130ms ease, transform 130ms ease;
    position: relative;
    z-index: 1;
}}
.admet-row:last-child {{ border-bottom: none; }}
.admet-row:hover {{
    background: var(--admet-row-hover);
    transform: translateX(1px);
    z-index: 30;
}}
.admet-row:focus-within {{
    z-index: 30;
}}
.admet-label-wrap {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex: 1;
}}
.admet-label {{
    font-size: 13px;
    color: #1e293b;
    font-weight: 600;
    line-height: 1.3;
}}
.admet-value {{
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    font-family: "SFMono-Regular", Menlo, Consolas, monospace;
    font-size: 12px;
    font-weight: 700;
    padding: 5px 11px;
    border-radius: 999px;
    text-align: right;
    min-width: 96px;
    justify-content: flex-end;
    border: 1px solid transparent;
}}
.admet-unit {{
    font-size: 10px;
    color: #64748b;
    font-weight: 500;
}}
.admet-status-optimal {{
    background: linear-gradient(180deg, #dcfce7 0%, #bbf7d0 100%);
    border-color: #86efac;
    color: #166534;
}}
.admet-status-warning {{
    background: linear-gradient(180deg, #fef3c7 0%, #fde68a 100%);
    border-color: #fcd34d;
    color: #92400e;
}}
.admet-status-danger {{
    background: linear-gradient(180deg, #fee2e2 0%, #fecaca 100%);
    border-color: #fca5a5;
    color: #991b1b;
}}
.admet-status-unknown {{
    background: linear-gradient(180deg, #f1f5f9 0%, #e2e8f0 100%);
    border-color: #cbd5e1;
    color: #4b5563;
}}
.admet-tooltip-trigger {{
    border: 1px solid #bfccdd;
    background: linear-gradient(180deg, #eef2ff 0%, #e0e7ff 100%);
    color: #3730a3;
    border-radius: 999px;
    width: 18px;
    height: 18px;
    padding: 0;
    font-size: 11px;
    font-weight: 800;
    line-height: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    cursor: help;
    position: relative;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}}
.admet-tooltip-trigger:focus {{
    outline: none;
}}
.admet-tooltip-trigger:focus-visible {{
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
}}
.admet-tooltip-card {{
    position: absolute;
    left: calc(100% + 10px);
    top: -10px;
    width: 330px;
    max-width: min(330px, 80vw);
    padding: 10px 12px;
    border-radius: 12px;
    border: 1px solid rgba(148, 163, 184, 0.5);
    background: linear-gradient(180deg, #0f172a 0%, #1f2937 100%);
    color: #f8fafc;
    box-shadow: 0 18px 30px rgba(15, 23, 42, 0.35);
    z-index: 5000;
    opacity: 0;
    visibility: hidden;
    transform: translateY(4px) scale(0.98);
    transition: opacity 140ms ease, visibility 140ms ease, transform 140ms ease;
    pointer-events: none;
    text-align: left;
}}
.admet-tooltip-trigger:hover .admet-tooltip-card,
.admet-tooltip-trigger:focus .admet-tooltip-card,
.admet-tooltip-trigger:focus-visible .admet-tooltip-card {{
    opacity: 1;
    visibility: visible;
    transform: translateY(0) scale(1);
}}
.admet-tooltip-title {{
    display: block;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 6px;
}}
.admet-tooltip-status {{
    display: inline-block;
    margin-bottom: 8px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}}
.admet-tooltip-status.tooltip-status-optimal {{
    background: rgba(74, 222, 128, 0.2);
    color: #86efac;
}}
.admet-tooltip-status.tooltip-status-warning {{
    background: rgba(250, 204, 21, 0.2);
    color: #fcd34d;
}}
.admet-tooltip-status.tooltip-status-danger {{
    background: rgba(248, 113, 113, 0.2);
    color: #fca5a5;
}}
.admet-tooltip-status.tooltip-status-unknown {{
    background: rgba(148, 163, 184, 0.25);
    color: #cbd5e1;
}}
.admet-tooltip-grid {{
    display: grid;
    grid-template-columns: minmax(88px, auto) 1fr;
    gap: 5px 8px;
    align-items: start;
}}
.admet-tooltip-key {{
    color: #93c5fd;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
.admet-tooltip-text {{
    color: #e2e8f0;
    font-size: 11px;
    line-height: 1.35;
}}
@media (max-width: 900px) {{
    .admet-tooltip-card {{
        left: auto;
        right: 0;
        top: calc(100% + 8px);
    }}
}}
.admet-view.admet-compact .admet-tooltip-card {{
    width: 280px;
}}
</style>
<div id="{element_id}" class="admet-view protein-properties-view{compact_class}" data-refua-widget="protein-properties">
    <div class="admet-header">{escaped_title}</div>
    <div class="admet-toolbar">
        <input id="{filter_id}" class="admet-filter-input" data-admet-filter="1" type="text" placeholder="Filter properties..." aria-label="Filter protein properties by name" />
    </div>
"""]

        if show_tabs:
            html_parts.append('    <div class="admet-tabs" role="tablist">')
            for key in category_keys:
                label = html.escape(CATEGORY_LABELS.get(key, key.title()))
                html_parts.append(
                    f'        <button type="button" class="admet-tab" data-admet-tab="{key}" aria-selected="false">{label}</button>'
                )
            html_parts.append("    </div>")

        html_parts.append('    <div class="admet-panels">')
        if show_tabs:
            for idx, key in enumerate(category_keys):
                active_class = " active" if idx == 0 else ""
                html_parts.append(
                    f'        <div class="admet-panel{active_class}" data-admet-panel="{key}">'
                )
                html_parts.extend(self._render_rows(categories[key]))
                html_parts.append(
                    '            <div class="admet-empty" data-admet-empty="1">No properties match this filter.</div>'
                )
                html_parts.append("        </div>")
        else:
            html_parts.append(
                '        <div class="admet-panel active" data-admet-panel="all">'
            )
            html_parts.extend(self._render_rows(rows))
            html_parts.append(
                '            <div class="admet-empty" data-admet-empty="1">No properties match this filter.</div>'
            )
            html_parts.append("        </div>")

        html_parts.append("    </div>")
        html_parts.append("</div>")

        return "\n".join(html_parts)

    def _repr_html_(self) -> str:
        return self._render_html()

    def _repr_mimebundle_(self, include=None, exclude=None):
        return {
            "text/html": self._render_html(),
            REFUA_MIME_TYPE: {"html": self._render_html()},
        }

    def display(self) -> None:
        if _ipython_display_module is not None:
            _ipython_display_module.display(
                _ipython_display_module.HTML(self._render_html())
            )
        else:
            print(self._render_html())

    def to_html(self) -> str:
        return self._render_html()
