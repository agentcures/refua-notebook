"""Utility functions for refua-notebook.

This module provides shared utilities for data processing and
helper functions used across the widget implementations.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

Number = Union[int, float]


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float.

    Parameters
    ----------
    value : Any
        Value to convert.
    default : float, optional
        Default value if conversion fails.

    Returns
    -------
    float or None
        Converted value or default.
    """
    if value is None:
        return default
    try:
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def normalize_property_name(name: str) -> str:
    """Normalize a property name for consistent lookup.

    Parameters
    ----------
    name : str
        Property name to normalize.

    Returns
    -------
    str
        Normalized property name.
    """
    normalized = name.lower().strip()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return normalized


def format_scientific(value: Number, precision: int = 2) -> str:
    """Format a number in scientific notation if needed.

    Parameters
    ----------
    value : Number
        Value to format.
    precision : int
        Number of decimal places.

    Returns
    -------
    str
        Formatted value.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "N/A"

    if abs(value) < 0.001 or abs(value) >= 10000:
        return f"{value:.{precision}e}"
    return f"{value:.{precision}g}"


def clamp(value: Number, lower: Number, upper: Number) -> Number:
    """Clamp a value between lower and upper bounds.

    Parameters
    ----------
    value : Number
        Value to clamp.
    lower : Number
        Lower bound.
    upper : Number
        Upper bound.

    Returns
    -------
    Number
        Clamped value.
    """
    return max(lower, min(upper, value))


def chunk_list(items: Sequence[Any], size: int) -> List[List[Any]]:
    """Split a sequence into chunks of a given size.

    Parameters
    ----------
    items : Sequence
        Items to chunk.
    size : int
        Chunk size.

    Returns
    -------
    List[List]
        List of chunks.
    """
    size = max(size, 1)
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def merge_dicts(*dicts: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries, later values override earlier.

    Parameters
    ----------
    *dicts : Mapping
        Dictionaries to merge.

    Returns
    -------
    Dict
        Merged dictionary.
    """
    result: Dict[str, Any] = {}
    for d in dicts:
        result.update(d)
    return result
