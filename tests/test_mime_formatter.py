"""Tests for custom MIME formatter behavior."""

from IPython.core.formatters import BaseFormatter, JSONFormatter
from IPython.core.interactiveshell import InteractiveShell

from refua_notebook.extension import _get_mime_formatter
from refua_notebook.mime import REFUA_MIME_TYPE


def test_get_mime_formatter_replaces_string_only_formatter():
    """Ensure the Refua MIME formatter accepts dict/list payloads."""
    ip = InteractiveShell.instance()
    original = ip.display_formatter.formatters.get(REFUA_MIME_TYPE)

    try:
        # Simulate the previous broken state: string-only formatter.
        ip.display_formatter.formatters[REFUA_MIME_TYPE] = BaseFormatter(
            parent=ip.display_formatter
        )

        mime_formatter = _get_mime_formatter(ip)

        assert isinstance(mime_formatter, JSONFormatter)
        assert mime_formatter is ip.display_formatter.formatters[REFUA_MIME_TYPE]

        class DummyRefuaType:
            pass

        mime_formatter.for_type(DummyRefuaType, lambda _obj: {"html": "<div>ok</div>"})
        data, _meta = ip.display_formatter.format(DummyRefuaType())

        assert REFUA_MIME_TYPE in data
        assert data[REFUA_MIME_TYPE] == {"html": "<div>ok</div>"}
    finally:
        if original is None:
            ip.display_formatter.formatters.pop(REFUA_MIME_TYPE, None)
        else:
            ip.display_formatter.formatters[REFUA_MIME_TYPE] = original
