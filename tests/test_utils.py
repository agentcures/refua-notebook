"""Tests for refua_notebook utility functions."""

from refua_notebook.utils import (
    chunk_list,
    clamp,
    format_scientific,
    merge_dicts,
    normalize_property_name,
    safe_float,
)


class TestSafeFloat:
    """Tests for safe_float function."""

    def test_valid_float(self):
        """Test conversion of valid float."""
        assert safe_float(3.14) == 3.14

    def test_valid_int(self):
        """Test conversion of valid int."""
        assert safe_float(42) == 42.0

    def test_string_number(self):
        """Test conversion of string number."""
        assert safe_float("2.5") == 2.5

    def test_none_default(self):
        """Test None returns default."""
        assert safe_float(None) is None
        assert safe_float(None, 0.0) == 0.0

    def test_invalid_string(self):
        """Test invalid string returns default."""
        assert safe_float("not a number") is None
        assert safe_float("invalid", 0.0) == 0.0

    def test_nan_returns_default(self):
        """Test NaN returns default."""
        assert safe_float(float("nan")) is None
        assert safe_float(float("nan"), 0.0) == 0.0

    def test_inf_returns_default(self):
        """Test infinity returns default."""
        assert safe_float(float("inf")) is None
        assert safe_float(float("-inf"), -1.0) == -1.0


class TestNormalizePropertyName:
    """Tests for normalize_property_name function."""

    def test_lowercase(self):
        """Test lowercase conversion."""
        assert normalize_property_name("LogP") == "logp"

    def test_strip_whitespace(self):
        """Test whitespace stripping."""
        assert normalize_property_name("  solubility  ") == "solubility"

    def test_replace_hyphen(self):
        """Test hyphen replacement."""
        assert normalize_property_name("half-life") == "half_life"

    def test_replace_space(self):
        """Test space replacement."""
        assert normalize_property_name("half life") == "half_life"


class TestFormatScientific:
    """Tests for format_scientific function."""

    def test_normal_value(self):
        """Test normal value formatting."""
        result = format_scientific(2.5)
        assert "2.5" in result

    def test_small_value(self):
        """Test small value uses scientific notation."""
        result = format_scientific(0.0001)
        assert "e" in result.lower()

    def test_large_value(self):
        """Test large value uses scientific notation."""
        result = format_scientific(100000.0)
        assert "e" in result.lower()

    def test_nan(self):
        """Test NaN returns N/A."""
        assert format_scientific(float("nan")) == "N/A"

    def test_inf(self):
        """Test infinity returns N/A."""
        assert format_scientific(float("inf")) == "N/A"

    def test_precision(self):
        """Test precision parameter."""
        result = format_scientific(0.00001234, precision=3)
        assert "e" in result.lower()


class TestClamp:
    """Tests for clamp function."""

    def test_within_range(self):
        """Test value within range is unchanged."""
        assert clamp(5, 0, 10) == 5

    def test_below_lower(self):
        """Test value below lower bound is clamped."""
        assert clamp(-5, 0, 10) == 0

    def test_above_upper(self):
        """Test value above upper bound is clamped."""
        assert clamp(15, 0, 10) == 10

    def test_at_bounds(self):
        """Test values at bounds."""
        assert clamp(0, 0, 10) == 0
        assert clamp(10, 0, 10) == 10

    def test_float_values(self):
        """Test with float values."""
        assert clamp(0.5, 0.0, 1.0) == 0.5
        assert clamp(-0.1, 0.0, 1.0) == 0.0


class TestChunkList:
    """Tests for chunk_list function."""

    def test_exact_division(self):
        """Test list that divides evenly."""
        result = chunk_list([1, 2, 3, 4], 2)
        assert result == [[1, 2], [3, 4]]

    def test_uneven_division(self):
        """Test list that doesn't divide evenly."""
        result = chunk_list([1, 2, 3, 4, 5], 2)
        assert result == [[1, 2], [3, 4], [5]]

    def test_empty_list(self):
        """Test empty list."""
        result = chunk_list([], 3)
        assert result == []

    def test_chunk_size_larger_than_list(self):
        """Test chunk size larger than list."""
        result = chunk_list([1, 2], 5)
        assert result == [[1, 2]]

    def test_minimum_chunk_size(self):
        """Test minimum chunk size is 1."""
        result = chunk_list([1, 2, 3], 0)
        assert len(result) == 3  # Should be treated as size 1

    def test_single_element_chunks(self):
        """Test single element chunks."""
        result = chunk_list([1, 2, 3], 1)
        assert result == [[1], [2], [3]]


class TestMergeDicts:
    """Tests for merge_dicts function."""

    def test_basic_merge(self):
        """Test basic dictionary merge."""
        result = merge_dicts({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_override(self):
        """Test later values override earlier."""
        result = merge_dicts({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_multiple_dicts(self):
        """Test merging multiple dictionaries."""
        result = merge_dicts({"a": 1}, {"b": 2}, {"c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_empty_dicts(self):
        """Test with empty dictionaries."""
        result = merge_dicts({}, {"a": 1}, {})
        assert result == {"a": 1}

    def test_no_dicts(self):
        """Test with no dictionaries."""
        result = merge_dicts()
        assert result == {}
