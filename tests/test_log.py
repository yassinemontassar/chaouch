import json
import logging
import sys

from chaouch.log import JsonFormatter


def make_record(msg, args=(), exc_info=None):
    return logging.LogRecord("chaouch.x", logging.INFO, __file__, 1, msg, args, exc_info)


def test_json_formatter_includes_fields_and_unicode() -> None:
    record = make_record("salam %s", ("عسلامة",))
    record.fields = {"latency_ms": 12}
    line = JsonFormatter().format(record)
    data = json.loads(line)
    assert data["msg"] == "salam عسلامة"
    assert data["latency_ms"] == 12
    assert data["level"] == "INFO"
    assert "عسلامة" in line  # not \u-escaped


def test_json_formatter_includes_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = make_record("failed", exc_info=sys.exc_info())
    data = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in data["exc"]
