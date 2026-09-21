from datetime import datetime

from modules.database.service import DatabaseService


def test_operation_datetime_parses_supported_formats():
    assert DatabaseService._operation_datetime("21.09.2026 12:30:45") == datetime(2026, 9, 21, 12, 30, 45)
    assert DatabaseService._operation_datetime("2026-09-21 12:30:45") == datetime(2026, 9, 21, 12, 30, 45)


def test_operation_datetime_returns_none_for_invalid_value():
    assert DatabaseService._operation_datetime("not-a-date") is None
