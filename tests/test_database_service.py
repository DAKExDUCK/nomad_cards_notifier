from datetime import datetime
from types import SimpleNamespace

from modules.database.service import DatabaseService


def test_operation_datetime_parses_supported_formats():
    assert DatabaseService._operation_datetime("21.09.2026 12:30:45") == datetime(2026, 9, 21, 12, 30, 45)
    assert DatabaseService._operation_datetime("2026-09-21 12:30:45") == datetime(2026, 9, 21, 12, 30, 45)


def test_operation_datetime_returns_none_for_invalid_value():
    assert DatabaseService._operation_datetime("not-a-date") is None


def test_operation_sort_key_uses_occurred_at_before_created_at():
    late_loaded = SimpleNamespace(
        occurred_at="21.09.2026 12:00:00",
        occurred_at_datetime=datetime(2026, 9, 21, 12),
        created_at=datetime(2026, 9, 21, 23),
        id=2,
    )
    early_loaded = SimpleNamespace(
        occurred_at="21.09.2026 13:00:00",
        occurred_at_datetime=datetime(2026, 9, 21, 13),
        created_at=datetime(2026, 9, 21, 12),
        id=1,
    )

    assert sorted([late_loaded, early_loaded], key=DatabaseService._operation_sort_key) == [late_loaded, early_loaded]
