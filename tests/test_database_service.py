from datetime import datetime
from types import SimpleNamespace

from modules.bot.handlers.default import _parse_balance_value
from modules.database.service import DatabaseService


def test_operation_datetime_parses_supported_formats():
    assert DatabaseService._operation_datetime("21.09.2026 12:30:45") == datetime(2026, 9, 21, 12, 30, 45)
    assert DatabaseService._operation_datetime("2026-09-21 12:30:45") == datetime(2026, 9, 21, 12, 30, 45)


def test_operation_datetime_returns_none_for_invalid_value():
    assert DatabaseService._operation_datetime("not-a-date") is None


def test_parse_balance_value_accepts_decimal_comma_and_rejects_invalid_values():
    assert str(_parse_balance_value("1250,50")) == "1250.50"
    assert _parse_balance_value("-1") is None
    assert _parse_balance_value("not-a-number") is None


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


def test_recalculate_operation_balances_chains_multiple_top_ups():
    operations = [
        SimpleNamespace(
            occurred_at="21.09.2026 10:00:00",
            occurred_at_datetime=datetime(2026, 9, 21, 10),
            created_at=datetime(2026, 9, 21, 10),
            id=1,
            operation_type="1",
            quantity="300",
            amount=None,
            fuel_balance="1000",
        ),
        SimpleNamespace(
            occurred_at="21.09.2026 11:00:00",
            occurred_at_datetime=datetime(2026, 9, 21, 11),
            created_at=datetime(2026, 9, 21, 11),
            id=2,
            operation_type="1",
            quantity="500",
            amount=None,
            fuel_balance=None,
        ),
        SimpleNamespace(
            occurred_at="21.09.2026 12:00:00",
            occurred_at_datetime=datetime(2026, 9, 21, 12),
            created_at=datetime(2026, 9, 21, 12),
            id=3,
            operation_type="1",
            quantity="200",
            amount=None,
            fuel_balance=None,
        ),
        SimpleNamespace(
            occurred_at="21.09.2026 13:00:00",
            occurred_at_datetime=datetime(2026, 9, 21, 13),
            created_at=datetime(2026, 9, 21, 13),
            id=4,
            operation_type="0",
            quantity="200",
            amount=None,
            fuel_balance=None,
        ),
    ]

    assert DatabaseService._recalculate_operation_balances(operations) == 3
    assert [operation.fuel_balance for operation in operations] == ["1000", "1500.00", "1700.00", "1500.00"]


def test_recalculate_operation_balances_places_late_operation_by_occurred_at():
    late_loaded = SimpleNamespace(
        occurred_at="21.09.2026 11:00:00",
        occurred_at_datetime=datetime(2026, 9, 21, 11),
        created_at=datetime(2026, 9, 21, 23),
        id=3,
        operation_type="1",
        quantity="500",
        amount=None,
        fuel_balance=None,
    )
    operations = [
        SimpleNamespace(
            occurred_at="21.09.2026 10:00:00",
            occurred_at_datetime=datetime(2026, 9, 21, 10),
            created_at=datetime(2026, 9, 21, 10),
            id=1,
            operation_type="1",
            quantity="300",
            amount=None,
            fuel_balance="1000",
        ),
        SimpleNamespace(
            occurred_at="21.09.2026 12:00:00",
            occurred_at_datetime=datetime(2026, 9, 21, 12),
            created_at=datetime(2026, 9, 21, 12),
            id=2,
            operation_type="0",
            quantity="200",
            amount=None,
            fuel_balance="800",
        ),
        late_loaded,
    ]

    assert DatabaseService._recalculate_operation_balances(operations) == 2
    assert [operation.id for operation in operations] == [1, 3, 2]
    assert [operation.fuel_balance for operation in operations] == ["500.00", "1000.00", "800"]
