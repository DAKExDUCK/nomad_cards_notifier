import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from modules.database import DatabaseService
from modules.fuel_cards.collector import NomadCardsCollector
from modules.logger import Logger
from tests.fake_nomad_server import fake_nomad_server


FIXTURE = Path(__file__).parent / "fixtures" / "nomad_site.json"


def test_fake_nomad_server_exposes_parser_compatible_pages():
    with fake_nomad_server(FIXTURE) as (base_url, requests):
        opener = build_opener(_NoRedirectHandler)

        try:
            opener.open(Request(f"{base_url}/login", method="POST", data=b"Username=user"))
        except HTTPError as error:
            assert error.code == 302
        with urlopen(f"{base_url}/cards") as response:
            cards_html = response.read().decode()
        with urlopen(f"{base_url}/card/1/CARD-42") as response:
            card_html = response.read().decode()
        with urlopen(Request(f"{base_url}/sales1", method="POST", data=b"clid=test")) as response:
            sales_html = response.read().decode()

    assert "CARD-42" in cards_html
    assert "Пополнение баланса: 3000.00" in card_html
    assert "Station A" in sales_html
    assert [request[0:2] for request in requests] == [
        ("POST", "/login"),
        ("GET", "/cards"),
        ("GET", "/card/1/CARD-42"),
        ("POST", "/sales1"),
    ]


def test_fake_nomad_server_accepts_new_sales_and_top_ups():
    with fake_nomad_server(FIXTURE) as (base_url, _requests):
        for payload in (
            {
                "type": "top_up",
                "card_external_id": "CARD-42",
                "occurred_at": "23.09.2026 14:00:00",
                "fuel": "DT",
                "quantity": "500.00",
            },
            {
                "type": "sale",
                "card_external_id": "CARD-42",
                "occurred_at": "23.09.2026 15:00:00",
                "station": "Station B",
                "transaction_number": "TX-2",
                "fuel": "DT",
                "quantity": "100.00",
            },
        ):
            request = Request(
                f"{base_url}/__test__/transactions",
                method="POST",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request) as response:
                assert response.status == 201

        with urlopen(Request(f"{base_url}/sales1", method="POST", data=b"clid=test")) as response:
            sales_html = response.read().decode()
        with urlopen(f"{base_url}/card/1/CARD-42") as response:
            card_html = response.read().decode()

    assert "TX-2" in sales_html
    assert "Station B" in sales_html
    assert "Пополнение баланса: 500.00" in card_html


def test_collector_runs_full_collection_and_notification_pipeline(monkeypatch):
    Logger.load_config()

    class Store:
        cards = {}
        operations = {}
        sent_ids = {}
        next_card_id = 1
        next_operation_id = 1

    async def save_card_snapshot(card_record, operation_records, inserted_records=None):
        card = Store.cards.setdefault(
            card_record.external_id,
            SimpleNamespace(
                id=Store.next_card_id,
                external_id=card_record.external_id,
                name=card_record.name,
                detail_url=card_record.url,
            ),
        )
        Store.next_card_id += 1
        inserted = 0
        for record in operation_records:
            if record.external_id in Store.operations:
                continue
            operation = SimpleNamespace(
                id=Store.next_operation_id,
                card_id=card.id,
                card_external_id=record.card_external_id,
                external_id=record.external_id,
                occurred_at=record.occurred_at,
                occurred_at_datetime=DatabaseService._operation_datetime(record.occurred_at),
                operation_type=record.operation_type,
                amount=record.amount,
                quantity=record.quantity,
                station=record.station,
                transaction_number=record.transaction_number,
                dispenser=record.dispenser,
                fuel=record.fuel,
                unit_price=record.unit_price,
                issuer=record.issuer,
                card_number=record.card_number,
                holder=record.holder,
                contract=record.contract,
                fuel_balance=record.fuel_balance,
                fuel_balance_is_anchor=False,
                notification_sent_at=None,
                notification_chat_id=None,
                notification_message_id=None,
                created_at=datetime(2026, 9, 26, 12, Store.next_operation_id),
            )
            if operation.operation_type == "1" and not any(
                existing.fuel_balance is not None for existing in Store.operations.values()
            ):
                operation.fuel_balance = operation.quantity
                operation.fuel_balance_is_anchor = True
            Store.next_operation_id += 1
            Store.operations[record.external_id] = operation
            if inserted_records is not None:
                inserted_records.append(record)
            inserted += 1
        return inserted

    async def recalculate_fuel_balances(*, days=60, operation_records=None):
        del days, operation_records
        operations_by_card = {}
        for operation in Store.operations.values():
            operations_by_card.setdefault(operation.card_id, []).append(operation)
        for operations in operations_by_card.values():
            DatabaseService._recalculate_operation_balances(operations)
        return 0

    async def get_card_by_external_id(external_id):
        return Store.cards.get(external_id)

    async def get_sent_notification_operations():
        return [operation for operation in Store.operations.values() if operation.notification_message_id]

    async def get_pending_notification_operations():
        return sorted(
            [operation for operation in Store.operations.values() if not operation.notification_sent_at],
            key=DatabaseService._operation_sort_key,
        )

    async def mark_notification_sent(operation_id, chat_id, message_id):
        operation = next(operation for operation in Store.operations.values() if operation.id == operation_id)
        operation.notification_sent_at = datetime(2026, 9, 26, 12)
        operation.notification_chat_id = str(chat_id)
        operation.notification_message_id = message_id
        Store.sent_ids[operation_id] = message_id

    monkeypatch.setattr(DatabaseService, "save_card_snapshot", staticmethod(save_card_snapshot))
    monkeypatch.setattr(DatabaseService, "recalculate_fuel_balances", staticmethod(recalculate_fuel_balances))
    monkeypatch.setattr(DatabaseService, "get_card_by_external_id", staticmethod(get_card_by_external_id))
    monkeypatch.setattr(
        DatabaseService,
        "get_sent_notification_operations",
        staticmethod(get_sent_notification_operations),
    )
    monkeypatch.setattr(
        DatabaseService,
        "get_pending_notification_operations",
        staticmethod(get_pending_notification_operations),
    )
    monkeypatch.setattr(DatabaseService, "mark_notification_sent", staticmethod(mark_notification_sent))

    sent = []
    edited = []

    async def notify(text):
        message_id = len(sent) + 100
        sent.append((message_id, text))
        return 777, message_id

    async def edit_notify(chat_id, message_id, text):
        edited.append((chat_id, message_id, text))

    with fake_nomad_server(FIXTURE) as (base_url, _requests):
        collector = NomadCardsCollector(base_url, "user", "password", "client", notify, edit_notify)
        assert asyncio.run(collector.run_once()) == 2
        assert len(sent) == 2
        assert "3000.00 л" in sent[0][1]
        assert "2900.00 л" in sent[1][1]

        payload = {
            "type": "top_up",
            "card_external_id": "CARD-42",
            "occurred_at": "23.09.2026 11:00:00",
            "fuel": "DT",
            "quantity": "500.00",
        }
        request = Request(
            f"{base_url}/__test__/transactions",
            method="POST",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request) as response:
            assert response.status == 201

        assert asyncio.run(collector.run_once()) == 1

    assert len(edited) == 2
    assert {message_id for _, message_id, _ in edited} == {100, 101}
    assert "3000.00 л" in next(text for _, message_id, text in edited if message_id == 100)
    assert "3400.00 л" in next(text for _, message_id, text in edited if message_id == 101)
    assert len(sent) == 3
    assert "3500.00 л" in sent[2][1]


class _NoRedirectHandler(HTTPRedirectHandler):
    def http_error_302(self, request, response, code, message, headers):
        return response
