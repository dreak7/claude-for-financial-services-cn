"""Validation helpers for structured MCP tool arguments."""

from datetime import datetime
import re


def is_stock_code(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9]{6}", value))


def is_windcode(value: str) -> bool:
    return bool(re.fullmatch(r"[\w.\-\u4e00-\u9fff]+", value))


def is_date(value: str, fmt: str) -> bool:
    patterns = {"%Y%m%d": r"[0-9]{8}", "%Y-%m-%d": r"[0-9]{4}-[0-9]{2}-[0-9]{2}"}
    if not re.fullmatch(patterns[fmt], value):
        return False
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False
