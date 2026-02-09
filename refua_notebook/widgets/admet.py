"""ADMET property visualization widget for Jupyter notebooks.

This module provides the ADMETView class for displaying ADMET (Absorption,
Distribution, Metabolism, Excretion, and Toxicity) property predictions
inline in Jupyter notebooks.
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
class PropertyThreshold:
    """Defines thresholds for ADMET property scoring."""

    name: str
    label: str
    unit: str
    optimal_range: tuple[float, float]
    warning_range: tuple[float, float]
    category: str = "general"
    description: str = ""


@dataclass(frozen=True)
class PropertyInsight:
    """Domain context used for rich tooltip copy."""

    what: str
    why: str
    low_signal: str = ""
    high_signal: str = ""
    design_levers: str = ""


# Standard ADMET property thresholds based on drug-likeness guidelines
ADMET_THRESHOLDS: Dict[str, PropertyThreshold] = {
    # Absorption
    "logP": PropertyThreshold(
        "logP",
        "LogP",
        "",
        (0.0, 3.0),
        (-0.5, 5.0),
        "absorption",
        "Partition coefficient - optimal for oral absorption",
    ),
    "caco2": PropertyThreshold(
        "caco2",
        "Caco-2 Permeability",
        "nm/s",
        (20.0, float("inf")),
        (10.0, float("inf")),
        "absorption",
        "Intestinal permeability",
    ),
    "solubility": PropertyThreshold(
        "solubility",
        "Solubility",
        "log mol/L",
        (-4.0, 0.0),
        (-5.0, 0.0),
        "absorption",
        "Aqueous solubility",
    ),
    "hia": PropertyThreshold(
        "hia",
        "HIA",
        "%",
        (80.0, 100.0),
        (50.0, 100.0),
        "absorption",
        "Human Intestinal Absorption",
    ),
    "bioavailability": PropertyThreshold(
        "bioavailability",
        "Bioavailability",
        "%",
        (30.0, 100.0),
        (20.0, 100.0),
        "absorption",
        "Oral bioavailability",
    ),
    "pampa": PropertyThreshold(
        "pampa",
        "PAMPA",
        "cm/s",
        (1e-6, float("inf")),
        (1e-7, float("inf")),
        "absorption",
        "Parallel artificial membrane permeability",
    ),
    # Distribution
    "ppbr": PropertyThreshold(
        "ppbr",
        "Plasma Protein Binding",
        "%",
        (0.0, 90.0),
        (0.0, 95.0),
        "distribution",
        "Plasma protein binding rate",
    ),
    "vdss": PropertyThreshold(
        "vdss",
        "VDss",
        "L/kg",
        (0.1, 10.0),
        (0.04, 20.0),
        "distribution",
        "Volume of distribution at steady state",
    ),
    "bbb": PropertyThreshold(
        "bbb",
        "BBB Penetration",
        "",
        (0.0, 1.0),
        (0.0, 1.0),
        "distribution",
        "Blood-brain barrier penetration probability",
    ),
    # Metabolism
    "clearance_microsome": PropertyThreshold(
        "clearance_microsome",
        "Microsomal Clearance",
        "mL/min/g",
        (0.0, 30.0),
        (0.0, 50.0),
        "metabolism",
        "Microsomal clearance rate",
    ),
    "clearance_hepatocyte": PropertyThreshold(
        "clearance_hepatocyte",
        "Hepatocyte Clearance",
        "mL/min/kg",
        (0.0, 10.0),
        (0.0, 20.0),
        "metabolism",
        "Hepatocyte clearance rate",
    ),
    "half_life": PropertyThreshold(
        "half_life",
        "Half-life",
        "hr",
        (2.0, 12.0),
        (1.0, 24.0),
        "metabolism",
        "Elimination half-life",
    ),
    # Excretion
    "pgp": PropertyThreshold(
        "pgp",
        "P-gp Substrate",
        "",
        (0.0, 0.3),
        (0.0, 0.5),
        "excretion",
        "P-glycoprotein substrate probability",
    ),
    # Toxicity
    "herg": PropertyThreshold(
        "herg",
        "hERG Inhibition",
        "",
        (0.0, 0.3),
        (0.0, 0.5),
        "toxicity",
        "hERG channel inhibition probability",
    ),
    "ames": PropertyThreshold(
        "ames",
        "AMES Mutagenicity",
        "",
        (0.0, 0.3),
        (0.0, 0.5),
        "toxicity",
        "AMES mutagenicity probability",
    ),
    "dili": PropertyThreshold(
        "dili",
        "DILI",
        "",
        (0.0, 0.3),
        (0.0, 0.5),
        "toxicity",
        "Drug-induced liver injury probability",
    ),
    "ld50": PropertyThreshold(
        "ld50",
        "LD50",
        "log mol/kg",
        (-2.0, float("inf")),
        (-3.0, float("inf")),
        "toxicity",
        "Acute oral toxicity",
    ),
    "clintox": PropertyThreshold(
        "clintox",
        "ClinTox",
        "",
        (0.0, 0.3),
        (0.0, 0.5),
        "toxicity",
        "Clinical toxicity probability",
    ),
    "carcinogen": PropertyThreshold(
        "carcinogen",
        "Carcinogen",
        "",
        (0.0, 0.3),
        (0.0, 0.5),
        "toxicity",
        "Carcinogenicity probability",
    ),
    "skin_reaction": PropertyThreshold(
        "skin_reaction",
        "Skin Reaction",
        "",
        (0.0, 0.3),
        (0.0, 0.5),
        "toxicity",
        "Skin sensitization probability",
    ),
}

PROPERTY_INSIGHTS: Dict[str, PropertyInsight] = {
    "logP": PropertyInsight(
        what="Lipophilicity estimate (octanol/water partition).",
        why="Balances permeability against solubility, clearance, and off-target risk.",
        low_signal="Very low values can reduce membrane diffusion.",
        high_signal="High values often increase hERG, CYP liability, and poor developability.",
        design_levers="Tune aromatic load, heteroatom count, and basicity to rebalance polarity.",
    ),
    "caco2": PropertyInsight(
        what="Caco-2 monolayer permeability surrogate for gut absorption.",
        why="Higher permeability generally supports oral exposure when solubility is adequate.",
        low_signal="Low values suggest passive uptake is limiting.",
        high_signal="Very high values are good, but check efflux and first-pass metabolism.",
        design_levers="Reduce PSA and H-bonding burden; control ionization state.",
    ),
    "solubility": PropertyInsight(
        what="Aqueous solubility estimate.",
        why="Insufficient solubility can cap oral absorption and increase PK variability.",
        low_signal="Low solubility drives precipitation and formulation complexity.",
        high_signal="Very high solubility is favorable unless permeability drops too far.",
        design_levers="Introduce polarity strategically, break crystal packing, explore salts/co-crystals.",
    ),
    "hia": PropertyInsight(
        what="Predicted human intestinal absorption percentage.",
        why="Links early ADME profile to probability of oral success.",
        low_signal="Low HIA indicates absorption is a major risk to exposure.",
        high_signal="High HIA is positive, but still validate with clearance and efflux.",
        design_levers="Optimize permeability-solubility balance and minimize P-gp efflux risk.",
    ),
    "bioavailability": PropertyInsight(
        what="Predicted oral bioavailability.",
        why="Integrates absorption plus first-pass loss into a practical developability metric.",
        low_signal="Low values often reflect poor absorption or high first-pass metabolism.",
        high_signal="High values support oral dosing flexibility.",
        design_levers="Lower clearance hot spots, reduce efflux, and protect metabolic soft spots.",
    ),
    "pampa": PropertyInsight(
        what="Passive membrane permeability estimate (PAMPA).",
        why="Useful early indicator of transcellular uptake potential.",
        low_signal="Low PAMPA implies limited passive diffusion.",
        high_signal="Higher PAMPA generally supports oral uptake.",
        design_levers="Adjust lipophilicity and polar surface area without overdriving toxicity.",
    ),
    "ppbr": PropertyInsight(
        what="Plasma protein binding rate.",
        why="Binding affects free drug exposure, distribution, and PK interpretation.",
        low_signal="Low binding can increase free fraction and clearance.",
        high_signal="Very high binding can reduce free concentration at target.",
        design_levers="Modify lipophilicity/acidity to tune albumin and alpha-1-acid glycoprotein affinity.",
    ),
    "vdss": PropertyInsight(
        what="Volume of distribution at steady state.",
        why="Indicates extent of tissue partitioning relative to plasma.",
        low_signal="Very low Vd can limit tissue exposure for intracellular targets.",
        high_signal="Very high Vd can prolong terminal phase and complicate dose control.",
        design_levers="Tune basicity, lipophilicity, and transporter interactions.",
    ),
    "bbb": PropertyInsight(
        what="Blood-brain barrier penetration probability.",
        why="Critical for CNS projects and often a liability for peripheral programs.",
        low_signal="Low probability is typically desirable for non-CNS drugs.",
        high_signal="High values may be needed for CNS efficacy but increase CNS side-effect risk.",
        design_levers="Control PSA, pKa, and P-gp susceptibility to bias CNS exposure.",
    ),
    "clearance_microsome": PropertyInsight(
        what="Predicted microsomal clearance.",
        why="Proxy for hepatic metabolic turnover and half-life pressure.",
        low_signal="Lower clearance usually supports longer exposure.",
        high_signal="High clearance can require higher dose or more frequent dosing.",
        design_levers="Block oxidative soft spots, reduce lipophilicity, and avoid metabolic alerts.",
    ),
    "clearance_hepatocyte": PropertyInsight(
        what="Predicted hepatocyte clearance.",
        why="Captures broader hepatic elimination processes than microsomes alone.",
        low_signal="Low values generally support improved systemic exposure.",
        high_signal="High values can suppress oral and systemic exposure.",
        design_levers="Stabilize labile motifs and tune uptake transporter liabilities.",
    ),
    "half_life": PropertyInsight(
        what="Predicted elimination half-life.",
        why="Directly informs dosing interval and concentration fluctuation.",
        low_signal="Short half-life may require frequent dosing.",
        high_signal="Very long half-life can create accumulation risk.",
        design_levers="Balance metabolic stability with clearance and target residence time.",
    ),
    "pgp": PropertyInsight(
        what="Probability of being a P-glycoprotein substrate.",
        why="Efflux can reduce gut absorption and CNS penetration.",
        low_signal="Low substrate probability reduces efflux risk.",
        high_signal="High substrate probability may lower exposure in key tissues.",
        design_levers="Reduce polarity/shape motifs associated with P-gp recognition.",
    ),
    "herg": PropertyInsight(
        what="Probability of hERG channel inhibition.",
        why="hERG liability is a major cardiotoxicity de-risking gate.",
        low_signal="Low probability is favorable for cardiac safety margin.",
        high_signal="Higher probability raises QT risk concern and triage priority.",
        design_levers="Lower lipophilicity/basicity and reduce aromatic cationic motifs.",
    ),
    "ames": PropertyInsight(
        what="Probability of AMES mutagenicity.",
        why="Mutagenicity risk can terminate otherwise potent chemical series.",
        low_signal="Low probability is preferred.",
        high_signal="High probability suggests structural alert remediation is needed.",
        design_levers="Remove electrophilic/reactive substructures and known mutagenic motifs.",
    ),
    "dili": PropertyInsight(
        what="Probability of drug-induced liver injury.",
        why="DILI is a common reason for clinical attrition.",
        low_signal="Low probability supports safer chronic dosing assumptions.",
        high_signal="Higher probability warrants aggressive mitigation and in vitro confirmation.",
        design_levers="Reduce reactive metabolite potential and minimize lipophilic burden.",
    ),
    "ld50": PropertyInsight(
        what="Predicted acute oral toxicity index (LD50-like scale).",
        why="Useful coarse indicator for safety margin prioritization.",
        low_signal="Lower values indicate higher acute toxicity concern.",
        high_signal="Higher values indicate lower acute toxicity concern.",
        design_levers="Remove toxicophores and optimize exposure-driving properties.",
    ),
    "clintox": PropertyInsight(
        what="Probability of clinical toxicity signal.",
        why="Broad safety prior that complements mechanism-specific assays.",
        low_signal="Low probability is favorable for progression.",
        high_signal="High probability indicates elevated attrition risk.",
        design_levers="De-risk promiscuity and reactive chemistry across the scaffold.",
    ),
    "carcinogen": PropertyInsight(
        what="Probability of carcinogenicity signal.",
        why="Long-term safety risk relevant for chronic indications.",
        low_signal="Low probability is preferred.",
        high_signal="Higher probability requires structural alert review and assay follow-up.",
        design_levers="Eliminate known carcinogenic motifs and reduce genotoxic liabilities.",
    ),
    "skin_reaction": PropertyInsight(
        what="Probability of skin sensitization reaction.",
        why="Important for occupational handling and topical/oral safety profile.",
        low_signal="Low probability is favorable.",
        high_signal="High probability indicates sensitization mitigation is needed.",
        design_levers="Reduce electrophilic/reactive motifs linked to protein adduct formation.",
    ),
}


CATEGORY_ORDER = (
    "druglikeness",
    "surface_electronics",
    "topology_shape",
    "composition_counts",
    "fragments_alerts",
    "admet_profile",
    "other",
)
CORE_CATEGORY_KEYS = CATEGORY_ORDER[:5]

CATEGORY_LABELS = {
    "druglikeness": "Drug-Likeness",
    "surface_electronics": "Surface & Electronics",
    "topology_shape": "Topology & Shape",
    "composition_counts": "Composition & Counts",
    "fragments_alerts": "Fragments & Alerts",
    "admet_profile": "ADMET Profile",
    "other": "Other Properties",
    "all": "All Properties",
}


def _get_status_class(value: float, threshold: PropertyThreshold) -> str:
    """Determine status class (optimal/warning/danger) for a property value."""
    opt_low, opt_high = threshold.optimal_range
    warn_low, warn_high = threshold.warning_range

    if opt_low <= value <= opt_high:
        return "optimal"
    elif warn_low <= value <= warn_high:
        return "warning"
    else:
        return "danger"


def _is_finite_number(value: Any) -> bool:
    """Return True when value is an int/float and finite (bool excluded)."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    return not math.isnan(numeric) and not math.isinf(numeric)


def _format_range_bound(value: float) -> str:
    """Format one side of a numeric range."""
    if math.isinf(value):
        return "infinity" if value > 0 else "-infinity"
    if value == 0:
        return "0"
    if abs(value) < 0.001 or abs(value) >= 10000:
        return f"{value:.1e}"
    return f"{value:.3g}"


def _format_range(low: float, high: float, unit: str) -> str:
    """Format a low/high range with optional units."""
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


def _compact_key(key: str) -> str:
    """Compact a key for robust descriptor-family matching."""
    return key.lower().replace("_", "").replace("-", "").replace(" ", "")


def _extract_family_index(key: str, prefix: str) -> tuple[int, str]:
    """Extract numeric suffix for prefix-based descriptor sorting."""
    compact = _compact_key(key)
    if not compact.startswith(prefix):
        return (999, compact)
    suffix = compact[len(prefix) :]
    match = re.match(r"(\d+)(.*)$", suffix)
    if match:
        return (int(match.group(1)), match.group(2))
    return (999, suffix)


def _infer_property_category(
    norm_key: str,
    raw_key: str,
    threshold: PropertyThreshold | None,
) -> str:
    """Assign a property to a display category."""
    compact = _compact_key(norm_key)
    raw_compact = _compact_key(raw_key)

    if threshold is not None and norm_key in ADMET_THRESHOLDS:
        return "admet_profile"

    if norm_key.startswith("fr_") or raw_compact.startswith("fr"):
        return "fragments_alerts"

    count_like_compacts = {
        "heavyatomcount",
        "nhohcount",
        "nocount",
        "numvalenceelectrons",
        "numradicalelectrons",
        "ringcount",
        "formalcharge",
    }
    if (
        norm_key.startswith("num_")
        or compact.endswith("count")
        or compact in count_like_compacts
    ):
        return "composition_counts"

    if (
        compact.startswith("peoevsa")
        or compact.startswith("smrvsa")
        or compact.startswith("slogpvsa")
        or compact.startswith("estatevsa")
        or compact.startswith("vsaestate")
        or compact.startswith("bcut2d")
        or "partialcharge" in compact
        or compact
        in {
            "labuteasa",
            "tpsa",
            "maxestateindex",
            "minestateindex",
            "maxabsestateindex",
            "minabsestateindex",
        }
    ):
        return "surface_electronics"

    if (
        compact.startswith("chi")
        or compact.startswith("kappa")
        or compact.startswith("fpdensitymorgan")
        or compact in {"avgipc", "ipc", "balabanj", "bertzct", "hallkieralpha", "phi"}
    ):
        return "topology_shape"

    druglike_compacts = {
        "qed",
        "sps",
        "molwt",
        "exactmolwt",
        "heavyatommolwt",
        "mollogp",
        "molmr",
        "fractioncsp3",
        "maxabsestateindex",
        "minabsestateindex",
    }
    if compact in druglike_compacts:
        return "druglikeness"

    return "other"


def _property_sort_key(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
    """Sort rows within each category in an interpretable descriptor order."""
    category = str(row.get("category", "other"))
    norm_key = str(row.get("normalized_key", row.get("key", "")))
    label = str(row.get("label", ""))
    compact = _compact_key(norm_key)
    label_key = label.lower()

    if category == "admet_profile":
        order = {
            "logp": 0,
            "caco2": 1,
            "solubility": 2,
            "hia": 3,
            "bioavailability": 4,
            "pampa": 5,
            "ppbr": 6,
            "vdss": 7,
            "bbb": 8,
            "clearancemicrosome": 9,
            "clearancehepatocyte": 10,
            "halflife": 11,
            "pgp": 12,
            "herg": 13,
            "ames": 14,
            "dili": 15,
            "ld50": 16,
            "clintox": 17,
            "carcinogen": 18,
            "skinreaction": 19,
        }
        return (0, order.get(compact, 999), 0, label_key)

    if category == "druglikeness":
        order = {
            "qed": 0,
            "sps": 1,
            "molwt": 2,
            "exactmolwt": 3,
            "heavyatommolwt": 4,
            "mollogp": 5,
            "molmr": 6,
            "tpsa": 7,
            "fractioncsp3": 8,
        }
        return (0, order.get(compact, 999), 0, label_key)

    if category == "surface_electronics":
        family_order = {
            "maxabsestateindex": 0,
            "maxestateindex": 1,
            "minabsestateindex": 2,
            "minestateindex": 3,
            "maxpartialcharge": 4,
            "minpartialcharge": 5,
            "maxabspartialcharge": 6,
            "minabspartialcharge": 7,
            "labuteasa": 8,
            "tpsa": 9,
            "bcut2d": 10,
            "peoevsa": 11,
            "smrvsa": 12,
            "slogpvsa": 13,
            "estatevsa": 14,
            "vsaestate": 15,
        }
        for prefix, family_idx in (
            ("bcut2d", family_order["bcut2d"]),
            ("peoevsa", family_order["peoevsa"]),
            ("smrvsa", family_order["smrvsa"]),
            ("slogpvsa", family_order["slogpvsa"]),
            ("estatevsa", family_order["estatevsa"]),
            ("vsaestate", family_order["vsaestate"]),
        ):
            idx, suffix = _extract_family_index(compact, prefix)
            if idx != 999:
                return (0, family_idx, idx, suffix)

        return (0, family_order.get(compact, 999), 0, label_key)

    if category == "topology_shape":
        for prefix, family_rank in (
            ("fpdensitymorgan", 0),
            ("chi", 1),
            ("kappa", 2),
        ):
            idx, suffix = _extract_family_index(compact, prefix)
            if idx != 999:
                return (0, family_rank, idx, suffix)
        order = {
            "balabanj": 3,
            "bertzct": 4,
            "avgipc": 5,
            "ipc": 6,
            "hallkieralpha": 7,
            "phi": 8,
        }
        return (0, order.get(compact, 999), 0, label_key)

    if category == "composition_counts":
        if compact.startswith("num"):
            return (0, 0, 0, label_key)
        if compact.endswith("count"):
            return (0, 1, 0, label_key)
        return (0, 2, 0, label_key)

    if category == "fragments_alerts":
        if compact.startswith("fr"):
            return (0, 0, 0, label_key)
        return (0, 1, 0, label_key)

    return (0, 999, 0, label_key)


def _auto_property_insight(
    norm_key: str,
    raw_key: str,
    label: str,
    category: str,
) -> PropertyInsight:
    """Generate custom semantic tooltip copy for descriptor-like properties."""
    compact = _compact_key(norm_key)
    label_clean = label.strip() or raw_key

    if category == "fragments_alerts":
        fragment = raw_key[3:] if raw_key.lower().startswith("fr_") else raw_key
        fragment_name = fragment.replace("_", " ").replace("-", " ").strip()
        if not fragment_name:
            fragment_name = label_clean
        return PropertyInsight(
            what=f"Substructure flag/count for the '{fragment_name}' motif.",
            why="Fragment alerts connect scaffold chemistry to reactivity, metabolism, and safety liabilities.",
            low_signal="Low/zero means the motif is absent or rare.",
            high_signal="Higher values indicate repeated presence of this motif in the scaffold.",
            design_levers="Swap or cap flagged motifs to tune risk while preserving potency drivers.",
        )

    if category == "composition_counts":
        return PropertyInsight(
            what=f"Counts molecular composition features represented by '{label_clean}'.",
            why="Atom/bond counts influence size, polarity balance, synthetic complexity, and developability.",
            low_signal="Lower counts usually indicate smaller, less feature-dense scaffolds.",
            high_signal="Higher counts often increase complexity and may shift ADMET behavior.",
            design_levers="Prune non-essential substituents or simplify ring systems to reduce feature burden.",
        )

    if category == "surface_electronics":
        if compact in {
            "maxabsestateindex",
            "maxestateindex",
            "minabsestateindex",
            "minestateindex",
        }:
            return PropertyInsight(
                what=f"{label_clean} summarizes atom-level electrotopological state intensity.",
                why="E-state indices connect local electronic environment and topology, useful for SAR and ADMET modeling.",
                low_signal="Lower values indicate weaker contribution from high-intensity E-state environments.",
                high_signal="Higher values indicate stronger concentration of electronically activated topological environments.",
                design_levers="Adjust heteroatom placement and substituent electronics near key ring/linker positions.",
            )
        if "partialcharge" in compact:
            return PropertyInsight(
                what=f"{label_clean} tracks the extreme partial-charge distribution in the molecule.",
                why="Charge extrema influence ionic interactions, solvation, permeability, and off-target liabilities.",
                low_signal="Lower magnitude implies a less polarized extreme in the corresponding direction.",
                high_signal="Higher magnitude implies stronger charge localization that can shift ADMET behavior.",
                design_levers="Rebalance electron-withdrawing/donating groups to tune charge localization.",
            )
        if compact == "labuteasa":
            return PropertyInsight(
                what="Labute ASA estimates solvent-accessible surface area.",
                why="Accessible surface is linked to desolvation cost, permeability, and binding-interface exposure.",
                low_signal="Lower values indicate a more compact exposed surface footprint.",
                high_signal="Higher values indicate broader exposed surface, often with higher solvation demand.",
                design_levers="Compact substituent topology or reduce bulky appendages to tune exposed area.",
            )
        if compact == "tpsa":
            return PropertyInsight(
                what="Topological polar surface area (TPSA) estimates exposed polar functionality.",
                why="TPSA is a key permeability and oral/CNS exposure discriminator.",
                low_signal="Too low can reduce aqueous compatibility for some programs.",
                high_signal="High TPSA often limits passive permeability and CNS penetration.",
                design_levers="Tune heteroatom count and hydrogen-bonding motifs to move TPSA intentionally.",
            )
        if compact.startswith("peoevsa"):
            return PropertyInsight(
                what=f"{label_clean} quantifies surface area in a partial-charge bin.",
                why="Charge-distribution surface terms often correlate with permeability, binding mode, and solubility.",
                low_signal="Low contribution means limited surface in that charge bin.",
                high_signal="High contribution indicates that charge pattern dominates exposed surface.",
                design_levers="Tune local substituent polarity and ionization to rebalance charge-surface distribution.",
            )
        if compact.startswith("smrvsa"):
            return PropertyInsight(
                what=f"{label_clean} captures surface area in a molar-refractivity bin.",
                why="Refractivity-linked surface terms track polarizability and packing-related behavior.",
                low_signal="Low values mean little surface in this refractivity regime.",
                high_signal="High values suggest this refractivity regime is structurally prominent.",
                design_levers="Adjust aromatic/heteroatom content to shift refractivity and exposed surface balance.",
            )
        if compact.startswith("slogpvsa"):
            return PropertyInsight(
                what=f"{label_clean} captures surface area in a fragment lipophilicity bin.",
                why="Lipophilic surface partitioning is informative for permeability-solubility and off-target tradeoffs.",
                low_signal="Low values indicate limited surface in this lipophilicity range.",
                high_signal="High values indicate strong contribution from that lipophilicity class.",
                design_levers="Redistribute lipophilicity by editing hydrophobic substituents and heteroatom placement.",
            )
        if compact.startswith("estatevsa") or compact.startswith("vsaestate"):
            return PropertyInsight(
                what=f"{label_clean} is an E-state/surface hybrid descriptor.",
                why="It links atom electronic state with exposed area, useful for SAR pattern mining.",
                low_signal="Lower values imply weaker contribution from that electronic-surface regime.",
                high_signal="Higher values suggest a dominant electronic-surface signature.",
                design_levers="Modify local electronics or steric exposure to tune this signature.",
            )
        if compact.startswith("bcut2d"):
            return PropertyInsight(
                what=f"{label_clean} is a BCUT eigenvalue descriptor over weighted molecular graph properties.",
                why="BCUT features summarize global mass/charge/lipophilicity dispersion relevant to ADMET modeling.",
                low_signal="Lower values indicate reduced contribution from the associated weighted mode.",
                high_signal="Higher values indicate stronger expression of that weighted structural mode.",
                design_levers="Reshape scaffold topology and substituent electronics to shift global eigenvalue profile.",
            )
        return PropertyInsight(
            what=f"{label_clean} reflects electronic or surface-area distribution of the molecule.",
            why="These descriptors are often predictive for permeability, binding orientation, and PK behavior.",
            low_signal="Low values suggest limited contribution from this electronic/surface pattern.",
            high_signal="High values indicate this pattern is strongly represented.",
            design_levers="Tune charge placement, polar groups, and exposed hydrophobic surface.",
        )

    if category == "topology_shape":
        if compact.startswith("chi"):
            return PropertyInsight(
                what=f"{label_clean} is a connectivity (Chi) index derived from molecular graph branching.",
                why="Connectivity indices capture topology complexity and can shift potency/ADMET trends.",
                low_signal="Lower values indicate simpler or less-branched topology.",
                high_signal="Higher values indicate richer branching/connectivity complexity.",
                design_levers="Adjust branching pattern and ring fusion to tune topological complexity.",
            )
        if compact.startswith("kappa"):
            return PropertyInsight(
                what=f"{label_clean} is a Kier shape index describing molecular shape profile.",
                why="Shape descriptors influence recognition, fit, and conformational behavior.",
                low_signal="Lower values may reflect compact or less-elongated shape regimes.",
                high_signal="Higher values indicate more elongated or shape-complex scaffolds.",
                design_levers="Alter ring architecture and linker geometry to reshape 3D topology.",
            )
        if compact == "balabanj":
            return PropertyInsight(
                what="Balaban J is a distance-connectivity topological index.",
                why="It captures graph branching and cyclicity patterns that influence chemotype behavior.",
                low_signal="Lower values indicate simpler distance-connectivity structure.",
                high_signal="Higher values indicate richer branching/cycle complexity.",
                design_levers="Alter branching and ring connectivity to tune topological compactness.",
            )
        if compact == "bertzct":
            return PropertyInsight(
                what="Bertz CT estimates structural complexity from graph information content.",
                why="Complexity impacts synthetic tractability and can correlate with ADMET unpredictability.",
                low_signal="Lower values indicate simpler molecular graph complexity.",
                high_signal="Higher values indicate highly complex graph architecture.",
                design_levers="Simplify fused motifs and redundant branching to reduce complexity load.",
            )
        if compact in {"ipc", "avgipc"}:
            return PropertyInsight(
                what=f"{label_clean} is an information-content descriptor of molecular topology.",
                why="Information-theoretic descriptors summarize graph diversity and feature distribution.",
                low_signal="Lower values indicate lower topological information diversity.",
                high_signal="Higher values indicate richer graph information content.",
                design_levers="Adjust heterogeneity of branching and ring substitution patterns.",
            )
        if compact == "hallkieralpha":
            return PropertyInsight(
                what="Hall-Kier alpha captures valence and atom-type correction to connectivity.",
                why="It refines topology descriptors toward chemical realism for QSAR tasks.",
                low_signal="Lower values indicate reduced valence-corrected topological complexity.",
                high_signal="Higher values indicate stronger valence/topology correction impact.",
                design_levers="Modify heteroatom valence environments to tune valence-corrected topology.",
            )
        if compact == "phi":
            return PropertyInsight(
                what="Phi is a flexibility/topology index related to molecular shape freedom.",
                why="Flexibility proxies inform conformational entropy and binding-mode adaptability.",
                low_signal="Lower values suggest a more rigid topological profile.",
                high_signal="Higher values suggest increased topological flexibility.",
                design_levers="Constrain or release rotatable segments and ring junctions.",
            )
        return PropertyInsight(
            what=f"{label_clean} is a topology/shape descriptor from the molecular graph.",
            why="Topology metrics are useful for clustering chemotypes and understanding SAR transferability.",
            low_signal="Lower values indicate reduced topological complexity for this descriptor family.",
            high_signal="Higher values indicate increased graph-level complexity.",
            design_levers="Modify branching, ring systems, and linker patterns to tune topological signature.",
        )

    if category == "druglikeness":
        if compact == "qed":
            return PropertyInsight(
                what="QED (quantitative estimate of drug-likeness) is a composite desirability score.",
                why="It summarizes key property balance into a quick medicinal-chem triage signal.",
                low_signal="Lower scores indicate property patterns less aligned with oral drug-like priors.",
                high_signal="Higher scores indicate stronger agreement with classical drug-like balance.",
                design_levers="Co-optimize MW, lipophilicity, H-bonding, and aromaticity balance.",
            )
        if compact == "sps":
            return PropertyInsight(
                what="SPS reflects scaffold 3D character and stereochemical/shape complexity.",
                why="3D-rich chemistry can improve selectivity and reduce flat aromatic liabilities.",
                low_signal="Lower values suggest flatter, less stereochemically rich scaffolds.",
                high_signal="Higher values indicate stronger 3D character and spatial complexity.",
                design_levers="Increase sp3 content or introduce stereodefined saturated motifs.",
            )
        if compact in {"molwt", "exactmolwt", "heavyatommolwt"}:
            return PropertyInsight(
                what=f"{label_clean} measures molecular mass (variant-specific).",
                why="Molecular weight strongly influences permeability, clearance, and formulation burden.",
                low_signal="Lower mass usually favors permeability but may reduce binding surface.",
                high_signal="Higher mass can increase potency opportunities but stresses ADMET balance.",
                design_levers="Trim non-essential substituents while preserving pharmacophore interactions.",
            )
        if compact in {"mollogp", "logp"}:
            return PropertyInsight(
                what=f"{label_clean} estimates global lipophilicity.",
                why="Lipophilicity is central to permeability-solubility-clearance tradeoffs.",
                low_signal="Too low can undercut passive permeability and intracellular exposure.",
                high_signal="Too high can elevate hERG/CYP/off-target risk and reduce solubility.",
                design_levers="Redistribute hydrophobes and heteroatoms to target project-appropriate lipophilicity.",
            )
        if compact == "molmr":
            return PropertyInsight(
                what="Molar refractivity approximates polarizability and steric volume contribution.",
                why="It links electronic responsiveness and size, relevant for binding and PK behavior.",
                low_signal="Lower values indicate lower polarizability/volume contribution.",
                high_signal="Higher values indicate more polarizable and sterically larger chemistry.",
                design_levers="Tune aromatic and heteroatom-rich motifs to rebalance polarizability.",
            )
        if compact == "fractioncsp3":
            return PropertyInsight(
                what="Fraction Csp3 measures the proportion of sp3-hybridized carbons.",
                why="Higher sp3 fraction is often associated with improved 3D character and developability.",
                low_signal="Low values indicate flatter, aromatic-heavy chemistry.",
                high_signal="High values indicate more saturated 3D-enriched scaffolds.",
                design_levers="Replace flat aromatic motifs with saturated bioisosteric alternatives where possible.",
            )
        return PropertyInsight(
            what=f"{label_clean} is a core physicochemical descriptor used in lead-quality triage.",
            why="Physicochemical balance governs the permeability-solubility-clearance trade space.",
            low_signal="Low values can indicate underpowered permeability or insufficient scaffold richness.",
            high_signal="High values can increase developability risk depending on the metric context.",
            design_levers="Adjust lipophilicity, polarity, and scaffold size to keep property balance in range.",
        )

    if category == "admet_profile":
        return PropertyInsight(
            what=f"{label_clean} is an ADMET endpoint prediction.",
            why="Endpoint-level predictions support early risk triage before targeted experiments.",
            low_signal="Lower values can be favorable or unfavorable depending on endpoint directionality.",
            high_signal="Higher values should be interpreted against endpoint-specific safety/PK intent.",
            design_levers="Tune exposure drivers and structural alerts based on endpoint-specific liabilities.",
        )

    return PropertyInsight(
        what=f"{label_clean} is a computed molecular descriptor.",
        why="Descriptor-level signals help connect scaffold changes to chemical and biological behavior.",
        low_signal="Lower values indicate reduced expression of this descriptor signal.",
        high_signal="Higher values indicate stronger expression of this descriptor signal.",
        design_levers="Use local substituent and scaffold edits to move the descriptor with related properties.",
    )


def _format_value(value: Any, precision: int = 3) -> str:
    """Format a value for display."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    elif isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return "N/A"
        if abs(value) < 0.001 or abs(value) >= 10000:
            return f"{value:.2e}"
        return f"{value:.{precision}g}"
    elif value is None:
        return "N/A"
    return str(value)


def _normalize_key(key: str) -> str:
    """Normalize property key for threshold lookup."""
    # Common key variations
    normalized = key.strip()
    # Split acronym boundaries before lowering, e.g. NumHDonors -> Num_H_Donors.
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", normalized)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    normalized = normalized.lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    # Handle common aliases
    aliases = {
        "logp": "logP",
        "log_p": "logP",
        "caco_2": "caco2",
        "caco2_permeability": "caco2",
        "human_intestinal_absorption": "hia",
        "plasma_protein_binding": "ppbr",
        "blood_brain_barrier": "bbb",
        "bbb_penetration": "bbb",
        "herg_inhibition": "herg",
        "ames_mutagenicity": "ames",
        "oral_bioavailability": "bioavailability",
        "half_life_obach": "half_life",
        "clearance_microsome_az": "clearance_microsome",
        "clearance_hepatocyte_az": "clearance_hepatocyte",
        "vdss_lombardo": "vdss",
        "ppbr_az": "ppbr",
        "caco2_wang": "caco2",
        "bioavailability_ma": "bioavailability",
        "hia_hou": "hia",
        "pampa_ncats": "pampa",
        "solubility_aqsoldb": "solubility",
        "lipophilicity_astrazeneca": "logP",
        "bbb_martins": "bbb",
        "pgp_broccatelli": "pgp",
        "ld50_zhu": "ld50",
        "clintox_ct_tox": "clintox",
        "carcinogens_lagunin": "carcinogen",
    }

    if normalized in aliases:
        return aliases[normalized]
    return normalized


class ADMETView:
    """Jupyter widget for displaying ADMET properties with visual indicators.

    This class generates an HTML representation of ADMET properties that can
    be displayed inline in Jupyter notebooks. Properties are color-coded based
    on their values relative to standard drug-likeness thresholds.

    Parameters
    ----------
    properties : dict
        Dictionary of ADMET property names to values. Keys can be in various
        formats (e.g., "logP", "log_p", "LogP") and will be normalized.
    title : str, optional
        Title to display above the properties table.
    show_categories : bool, optional
        If True, group properties by ADMET category. Default True.
    compact : bool, optional
        If True, use a more compact display format. Default False.

    Notes
    -----
    Internal helper used by the Refua notebook extension.
    """

    def __init__(
        self,
        properties: Mapping[str, Any],
        title: str = "ADMET Properties",
        show_categories: bool = True,
        compact: bool = False,
    ):
        self.properties = dict(properties)
        self.title = title
        self.show_categories = show_categories
        self.compact = compact
        self._element_id = f"admetview-{uuid.uuid4().hex[:8]}"

    def _build_property_rows(self) -> List[Dict[str, Any]]:
        """Build list of property row data for rendering."""
        rows = []
        for key, value in self.properties.items():
            norm_key = _normalize_key(key)
            threshold = ADMET_THRESHOLDS.get(norm_key)

            row: Dict[str, Any] = {
                "key": key,
                "value": value,
                "formatted_value": _format_value(value),
                "normalized_key": norm_key,
            }

            row["category"] = _infer_property_category(norm_key, str(key), threshold)

            if threshold is not None:
                row["label"] = threshold.label
                row["unit"] = threshold.unit
                row["admet_category"] = threshold.category
                row["description"] = threshold.description
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
                # Unknown property - display as-is
                row["label"] = key.replace("_", " ").title()
                row["unit"] = ""
                row["admet_category"] = "other"
                row["description"] = ""
                row["status"] = "unknown"
                row["optimal_range"] = ""
                row["warning_range"] = ""

            insight = PROPERTY_INSIGHTS.get(norm_key)
            if insight is None:
                insight = _auto_property_insight(
                    norm_key=norm_key,
                    raw_key=str(key),
                    label=str(row.get("label", key)),
                    category=str(row.get("category", "other")),
                )
            row["insight"] = insight

            rows.append(row)

        return rows

    def _group_rows(
        self, rows: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group rows by property-type category."""
        if not self.show_categories:
            return {"all": rows}

        categories: Dict[str, List[Dict[str, Any]]] = {
            key: [] for key in CATEGORY_ORDER
        }
        for row in rows:
            cat = row.get("category", "other")
            if cat in categories:
                categories[cat].append(row)
            else:
                categories["other"].append(row)

        for key in categories:
            categories[key] = sorted(categories[key], key=_property_sort_key)
        return categories

    def _render_tooltip(self, row: Mapping[str, Any]) -> str:
        """Render rich medicinal-chem tooltip content for one property row."""
        label = html.escape(str(row.get("label", "Property")))
        current_value = html.escape(str(row.get("formatted_value", "N/A")))
        unit = html.escape(str(row.get("unit", "")))
        current_text = f"{current_value} {unit}".strip()
        description = str(row.get("description", "")).strip()
        insight = row.get("insight")
        if not isinstance(insight, PropertyInsight):
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
            else (description if description else "Predicted property value.")
        )
        why_text = (
            insight.why
            if insight and insight.why
            else "Use with the full ADMET panel to guide prioritization."
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
                    '        <span class="admet-tooltip-key">Target Window</span>',
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
                    '        <span class="admet-tooltip-key">Medicinal-Chem Levers</span>',
                    f'        <span class="admet-tooltip-text">{html.escape(levers_text)}</span>',
                ]
            )
        html_parts.extend(["    </span>", "</span>"])
        return "\n".join(html_parts)

    def _render_rows(self, rows: List[Dict[str, Any]]) -> List[str]:
        """Render property rows for a tab panel."""
        html_parts: List[str] = []
        for row in rows:
            escaped_label = html.escape(row["label"])
            escaped_value = html.escape(row["formatted_value"])
            escaped_unit = html.escape(row.get("unit", ""))
            status_class = f"admet-status-{row['status']}"
            search_blob = html.escape(
                f"{row.get('label', '')} {row.get('key', '')}".lower(),
                quote=True,
            )
            category = html.escape(str(row.get("category", "other")), quote=True)

            tooltip_html = self._render_tooltip(row)
            tooltip_label = html.escape(
                f"More ADMET context for {row.get('label', 'property')}",
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
        """Render the ADMET view as HTML."""
        rows = self._build_property_rows()
        categories = self._group_rows(rows)
        category_keys: List[str] = []
        if self.show_categories:
            # Always expose five core property-type tabs.
            category_keys = list(CORE_CATEGORY_KEYS)
            # Optional extra tabs when data exists.
            if categories.get("admet_profile"):
                category_keys.append("admet_profile")
            if categories.get("other"):
                category_keys.append("other")
        show_tabs = self.show_categories and len(category_keys) > 0

        # Build HTML
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
    background: linear-gradient(90deg, #0ea5e9 0%, #4f46e5 50%, #0891b2 100%);
}}
.admet-view.admet-compact {{ max-width: 520px; }}
.admet-header {{
    background: linear-gradient(130deg, #0f172a 0%, #1e293b 58%, #0b3a53 100%);
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
<div id="{element_id}" class="admet-view{compact_class}" data-refua-widget="admet">
    <div class="admet-header">{escaped_title}</div>
    <div class="admet-toolbar">
        <input id="{filter_id}" class="admet-filter-input" data-admet-filter="1" type="text" placeholder="Filter properties..." aria-label="Filter properties by name" />
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
        """IPython HTML representation for inline display."""
        return self._render_html()

    def _repr_mimebundle_(self, include=None, exclude=None):
        """Provide a custom MIME bundle for JupyterLab rendering."""
        return {
            "text/html": self._render_html(),
            REFUA_MIME_TYPE: {"html": self._render_html()},
        }

    def display(self) -> None:
        """Display the ADMET view in the notebook."""
        if _ipython_display_module is not None:
            _ipython_display_module.display(
                _ipython_display_module.HTML(self._render_html())
            )
        else:
            print(self._render_html())

    def to_html(self) -> str:
        """Return the HTML representation as a string."""
        return self._render_html()
