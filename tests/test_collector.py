import asyncio

from modules.database import DatabaseService
from modules.fuel_cards.collector import FuelCardRecord, FuelOperationRecord, NomadCardsCollector


def test_parse_cards_extracts_card_identity_and_absolute_url():
    html = """
    <table id="cards"><tr>
      <td></td><td><a href="/ignore">ignore</a><a href="/card/1/CARD-42">card</a></td>
      <td> Main card </td>
    </tr></table>
    """

    cards = NomadCardsCollector("https://example.test", "user", "password", "client")._parse_cards(html)

    assert cards == [FuelCardRecord("CARD-42", "Main card", "https://example.test/card/1/CARD-42")]


def test_parse_card_operations_extracts_top_up():
    html = """
    <table class="table table-striped"><tr>
      <th>Дата</th><th>Продукт</th><th>Операция</th><th>Статус</th>
    </tr>
      <tr>
        <td><small>Оформлено: 23.09.2026 10:00:35<br>Выполнено 23.09.2026 10:00:35 <b>Офис</b></small></td>
        <td>ДТ</td>
        <td><small>Пополнение баланса: 3000.00</small></td>
        <td><span class="label label-success">выполнено</span></td>
      </tr>
    </table>
    """

    operations = NomadCardsCollector._parse_card_operations(html, "CARD-42")

    assert len(operations) == 1
    assert operations[0].operation_type == "1"
    assert operations[0].quantity == "3000.00"
    assert operations[0].amount is None
    assert operations[0].fuel == "ДТ"
    assert operations[0].occurred_at == "23.09.2026 10:00:35"


def test_split_notification_respects_maximum_length():
    chunks = NomadCardsCollector._split_notification("one\n\ntwo\n\nthree", max_length=7)

    assert chunks == ["one", "two", "three"]


def _operation_for_notification(**overrides) -> FuelOperationRecord:
    values = {
        "external_id": "operation-1",
        "card_external_id": "CARD-42",
        "occurred_at": "23.09.2026 10:00:35",
        "operation_type": "1",
        "amount": None,
        "quantity": "3000.00",
        "station": None,
        "transaction_number": None,
        "dispenser": None,
        "fuel": "ДТ",
        "unit_price": None,
        "issuer": None,
        "card_number": "CARD-42",
        "holder": None,
        "contract": None,
        "fuel_balance": "3000.00",
    }
    values.update(overrides)
    return FuelOperationRecord(**values)


def test_format_notification_prefers_holder_for_card_label(monkeypatch):
    operation = _operation_for_notification(holder="Main card")

    async def get_card(_external_id):
        return None

    monkeypatch.setattr(DatabaseService, "get_card_by_external_id", get_card)

    message = asyncio.run(
        NomadCardsCollector("https://example.test", "user", "password", "client")._format_notification([operation])
    )

    assert "💳 Карта: <code>Main card</code>" in message
    assert "CARD-42" not in message


def test_format_notification_prefers_database_card_name(monkeypatch):
    operation = _operation_for_notification(holder="Operation holder")

    class Card:
        name = "Stored card"
        external_id = "CARD-42"

    async def get_card(_external_id):
        return Card()

    monkeypatch.setattr(DatabaseService, "get_card_by_external_id", get_card)

    message = asyncio.run(
        NomadCardsCollector("https://example.test", "user", "password", "client")._format_notification([operation])
    )

    assert "💳 Карта: <code>Stored card</code>" in message
    assert "Operation holder" not in message


def test_format_notification_uses_card_number_when_holder_is_missing(monkeypatch):
    operation = _operation_for_notification()

    async def get_card(_external_id):
        return None

    monkeypatch.setattr(DatabaseService, "get_card_by_external_id", get_card)

    message = asyncio.run(
        NomadCardsCollector("https://example.test", "user", "password", "client")._format_notification([operation])
    )

    assert "💳 Карта: <code>CARD-42</code>" in message
    assert "💳 Карта: <code>Не указано</code>" not in message


def test_format_notification_uses_external_id_when_card_number_is_missing(monkeypatch):
    operation = _operation_for_notification(card_number=None, card_external_id="EXTERNAL-42")

    async def get_card(_external_id):
        return None

    monkeypatch.setattr(DatabaseService, "get_card_by_external_id", get_card)

    message = asyncio.run(
        NomadCardsCollector("https://example.test", "user", "password", "client")._format_notification([operation])
    )

    assert "💳 Карта: <code>EXTERNAL-42</code>" in message


def test_format_notification_escapes_card_label(monkeypatch):
    operation = _operation_for_notification(holder="Card <A&B>")

    async def get_card(_external_id):
        return None

    monkeypatch.setattr(DatabaseService, "get_card_by_external_id", get_card)

    message = asyncio.run(
        NomadCardsCollector("https://example.test", "user", "password", "client")._format_notification([operation])
    )

    assert "💳 Карта: <code>Card &lt;A&amp;B&gt;</code>" in message
