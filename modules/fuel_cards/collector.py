from __future__ import annotations

import asyncio
import hashlib
from html import escape
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin

import aiohttp

from modules.database import DatabaseService
from modules.logger import Logger


@dataclass(frozen=True)
class FuelCardRecord:
    external_id: str
    name: str
    url: str


@dataclass(frozen=True)
class FuelOperationRecord:
    external_id: str
    card_external_id: str
    occurred_at: str | None
    operation_type: str
    amount: str | None
    quantity: str | None
    station: str | None
    transaction_number: str | None
    dispenser: str | None
    fuel: str | None
    unit_price: str | None
    issuer: str | None
    card_number: str | None
    holder: str | None
    contract: str | None
    fuel_balance: str | None = None


class _CardsPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.cards: list[FuelCardRecord] = []
        self._in_cards_table = False
        self._in_card_link = False
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self._row_href: str | None = None
        self._row_link_text: str = ""
        self._row_card_name: str = ""
        self._cell_text: list[str] = []
        self._table_depth = 0
        self._td_index = 0
        self._in_second_cell = False
        self._card_link_index = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and attributes.get("id") == "cards":
            self._in_cards_table = True
            self._table_depth = 1
        elif self._in_cards_table and tag == "table":
            self._table_depth += 1

        if self._in_cards_table and tag == "tr":
            self._td_index = 0
            self._card_link_index = 0
            self._row_href = None
            self._row_link_text = ""
            self._row_card_name = ""
        elif self._in_cards_table and tag == "td":
            self._td_index += 1
            self._in_second_cell = self._td_index == 2
            self._cell_text = []

        if self._in_second_cell and tag == "a" and self._current_href is None:
            self._card_link_index += 1
            href = attributes.get("href")
            if href and self._card_link_index == 2:
                self._in_card_link = True
                self._current_href = href
                self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_card_link and self._current_href:
            self._row_href = self._current_href
            self._row_link_text = " ".join("".join(self._current_text).split())
            self._in_card_link = False
            self._current_href = None
            self._current_text = []
        elif tag == "td" and self._in_cards_table:
            if self._td_index == 3:
                self._row_card_name = " ".join("".join(self._cell_text).split())
            self._in_second_cell = False
            self._cell_text = []
        elif tag == "tr" and self._in_cards_table:
            if self._row_href:
                card_id = self._card_id(self._row_href, self._row_card_name)
                name = self._row_card_name or card_id
                self.cards.append(FuelCardRecord(card_id, name or card_id, self._row_href))
            self._td_index = 0
        elif tag == "table" and self._in_cards_table:
            self._table_depth -= 1
            if self._table_depth == 0:
                self._in_cards_table = False

    def handle_data(self, data: str) -> None:
        if self._in_card_link:
            self._current_text.append(data)
        if self._in_cards_table and self._td_index == 3:
            self._cell_text.append(data)

    @staticmethod
    def _card_id(href: str, name: str) -> str:
        match = re.search(r"/card/[^/]+/([^/?#]+)", href, re.IGNORECASE)
        return match.group(1) if match else name or href


class _TablesParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "table" and self._table is None:
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag == "tr" and self._table is None:
            self._table = []
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None

    def close(self) -> None:
        super().close()
        if self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        if self._row is not None and self._table is not None:
            if self._row:
                self._table.append(self._row)
            self._row = None
        if self._table is not None:
            self.tables.append(self._table)
            self._table = None


class NomadCardsCollector:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        clid: str,
        notify: Callable[[str], Awaitable[None]] | None = None,
        interval_seconds: int = 300,
        sales_from: str | None = None,
        sales_to: str | None = None,
        station_urls: Mapping[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.clid = clid
        self.notify = notify
        self.interval_seconds = interval_seconds
        self.sales_from = sales_from
        self.sales_to = sales_to
        self.station_urls = {
            self._normalize_station_name(name): url
            for name, url in (station_urls or {}).items()
            if url
        }

    async def run_once(self) -> int:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            Logger.info("Starting login process...")
            await self._login(session)
            Logger.info("Logged in successfully")
            cards_html = await self._get_text(session, "/cards")
            Logger.info("Fetched fuel cards page")
            cards = self._parse_cards(cards_html)
            Logger.info(f"Found {len(cards)} fuel cards")
            for card in cards:
                await DatabaseService.save_card_snapshot(card, [])
            sales_html = await self._get_sales(session)
            Logger.info("Fetched sales page" if sales_html else "Failed to fetch sales page")
            operations = self._parse_operations(sales_html)
            Logger.info(f"Found {len(operations)} operations")
            cards_by_number = {card.external_id: card for card in cards}
            operation_count = 0
            for operation in operations:
                card_number = operation.card_number or operation.card_external_id
                card = cards_by_number.get(card_number) or FuelCardRecord(
                    external_id=card_number,
                    name=operation.holder or card_number,
                    url=urljoin(f"{self.base_url}/", f"card/1/{card_number}"),
                )
                operation_count += await DatabaseService.save_card_snapshot(
                    card, [operation]
                )

            for card in cards:
                detail_html = await self._get_text(session, card.url)
                top_ups = self._parse_card_operations(detail_html, card.external_id)
                operation_count += await DatabaseService.save_card_snapshot(
                    card, top_ups
                )
            await DatabaseService.recalculate_fuel_balances(
                days=60,
            )

        pending_operations = await DatabaseService.get_pending_notification_operations()
        if pending_operations and self.notify:
            notification = self._format_notification(pending_operations)
            for chunk in self._split_notification(notification):
                await self.notify(chunk)
            await DatabaseService.mark_notifications_sent(
                [operation.id for operation in pending_operations]
            )
        return operation_count

    def _format_notification(self, operations: list[FuelOperationRecord]) -> str:
        messages = []
        for operation in operations:
            card = escape(operation.card_number or operation.card_external_id)
            date_text = escape(operation.occurred_at or "Не указано")
            if operation.occurred_at:
                date_text = f"{date_text}"
            amount = escape(operation.amount or "Не указано")
            fuel = escape(operation.fuel or "Не указано")
            holder = escape(operation.holder or "Не указано")
            balance = escape(operation.fuel_balance or "Не указано")

            if operation.operation_type == "1":
                quantity = escape(operation.quantity or "Не указано")
                messages.append(
                    "💰 <b>Пополнение карты</b>\n"
                    f"💳 Карта: <code>{holder or card}</code>\n"
                    f"🛢️ Топливо: <b>{fuel}</b>\n"
                    f"💵 Сумма: <b>{amount} ₸</b>\n"
                    f"⛽ Обьем: <b>{quantity} л</b>\n"
                    f"📊 Остаток: <b>{balance}</b>\n"
                    f"🕒 <i>{date_text}</i>\n"
                )
                continue

            quantity = escape(operation.quantity or "Не указано")
            station_name = operation.station or "Не указано"
            station = escape(station_name)
            station_url = self.station_urls.get(NomadCardsCollector._normalize_station_name(station_name))
            if station_url:
                station = f'<a href="{escape(station_url, quote=True)}">{station}</a>'
            messages.append(
                "⛽ <b>Расход топлива</b>\n"
                f"💳 Карта: <code>{holder or card}</code>\n"
                f"📍 АЗС: <b>{station}</b>\n"
                f"🛢️ Топливо: <b>{fuel}</b>\n"
                f"📏 Объём: <b>{quantity} л</b>\n"
                f"🕒 <i>{date_text}</i>\n"
                f"📊 Остаток: <b>{balance} л</b>\n"
            )
        return "\n\n".join(messages)

    @staticmethod
    def _split_notification(text: str, max_length: int = 4000) -> list[str]:
        blocks = text.split("\n\n")
        chunks: list[str] = []
        current: list[str] = []
        current_length = 0
        for block in blocks:
            block_length = len(block) + (2 if current else 0)
            if current and current_length + block_length > max_length:
                chunks.append("\n\n".join(current))
                current = []
                current_length = 0
            current.append(block)
            current_length += len(block) + (2 if len(current) > 1 else 0)
        if current:
            chunks.append("\n\n".join(current))
        return chunks

    @staticmethod
    def _normalize_station_name(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip()).casefold()

    async def run_forever(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                Logger.error("Fuel cards collection failed", exc_info=True)
            await asyncio.sleep(self.interval_seconds)

    async def _login(self, session: aiohttp.ClientSession) -> None:
        login_url = urljoin(f"{self.base_url}/", "login")
        async with session.post(
            login_url,
            data={"Username": self.username, "Password": self.password, "Login": "Login"},
            allow_redirects=False,
            ssl=False
        ) as response:
            if response.status != 302:
                raise RuntimeError(f"Nomad login failed with status {response.status}")

    async def _get_text(self, session: aiohttp.ClientSession, path: str) -> str:
        url = urljoin(f"{self.base_url}/", path)
        async with session.get(url, ssl=False) as response:
            response.raise_for_status()
            return await response.text()

    async def _get_sales(self, session: aiohttp.ClientSession) -> str:
        start = self.sales_from or (date.today() - timedelta(days=30)).strftime("%d.%m.%Y")
        end = self.sales_to or date.today().strftime("%d.%m.%Y 23:59:59")
        url = urljoin(f"{self.base_url}/", "sales1")
        data = {
            "clid": self.clid,
            "from": start,
            "to": end,
            "product": "-1",
            "azs": "-1",
            "issuer": "-1",
            "card": "-1",
            "contract": "-1",
        }
        async with session.post(url, data=data, headers={"X-Requested-With": "XMLHttpRequest"}, ssl=False) as response:
            response.raise_for_status()
            return await response.text()

    def _parse_cards(self, html: str) -> list[FuelCardRecord]:
        parser = _CardsPageParser()
        parser.feed(html)
        return [
            FuelCardRecord(card.external_id, card.name, urljoin(f"{self.base_url}/", card.url))
            for card in parser.cards
        ]

    @staticmethod
    def _parse_operations(html: str) -> list[FuelOperationRecord]:
        parser = _TablesParser()
        parser.feed(html)
        parser.close()
        operations: list[FuelOperationRecord] = []
        for table in parser.tables:
            if len(table) < 2:
                continue
            headers = [NomadCardsCollector._normalize_header(value) for value in table[0]]
            if headers[:3] != ["дата/время", "азс", "№ трнз."]:
                continue
            for row in table[1:]:
                if len(row) < 12 or not row[0] or row[1].upper() == "ИТОГО":
                    continue
                values = row[:12]
                external_id = hashlib.sha256(f"{values[9]}|{values[2]}|{values[0]}".encode()).hexdigest()
                operations.append(
                    FuelOperationRecord(
                        external_id=external_id,
                        card_external_id=values[9],
                        occurred_at=values[0],
                        operation_type="0",
                        amount=values[7] or None,
                        quantity=values[6] or None,
                        station=values[1] or None,
                        transaction_number=values[2] or None,
                        dispenser=values[3] or None,
                        fuel=values[4] or None,
                        unit_price=values[5] or None,
                        issuer=values[8] or None,
                        card_number=values[9] or None,
                        holder=values[10] or None,
                        contract=values[11] or None,
                    )
                )
        return operations

    @staticmethod
    def _parse_card_operations(html: str, card_external_id: str) -> list[FuelOperationRecord]:
        parser = _TablesParser()
        parser.feed(html)
        parser.close()
        operations: list[FuelOperationRecord] = []
        for table in parser.tables:
            if len(table) < 2:
                continue
            headers = [NomadCardsCollector._normalize_header(value) for value in table[0]]
            date_index = NomadCardsCollector._header_index(headers, "дат", "date", "время")
            amount_index = NomadCardsCollector._header_index(headers, "сумм", "amount", "пополн", "зачисл")
            quantity_index = NomadCardsCollector._header_index(
                headers, "объем", "объём", "колич", "литр", "quantity", "volume"
            )
            operation_index = NomadCardsCollector._header_index(headers, "операц", "тип", "вид")
            product_index = NomadCardsCollector._header_index(headers, "продукт", "топливо", "product", "fuel")
            if date_index is None or operation_index is None:
                continue

            for row in table[1:]:
                if not row or len(row) <= max(date_index, operation_index) or not row[date_index]:
                    continue
                if any(value.upper() == "ИТОГО" for value in row):
                    continue
                operation_text = row[operation_index] if operation_index is not None and len(row) > operation_index else ""
                amount = row[amount_index] if amount_index is not None and len(row) > amount_index else None
                quantity = row[quantity_index] if quantity_index is not None and len(row) > quantity_index else None
                if amount is None:
                    amount_match = re.search(r"[-+]?\d[\d\s]*[.,]\d{2}", operation_text)
                    amount = amount_match.group(0).replace(" ", "") if amount_match else None
                dates = re.findall(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}", row[date_index])
                occurred_at = dates[-1] if dates else row[date_index]
                raw = "|".join(row)
                external_id = hashlib.sha256(f"{card_external_id}|card-page|{raw}".encode()).hexdigest()
                operations.append(
                    FuelOperationRecord(
                        external_id=external_id,
                        card_external_id=card_external_id,
                        occurred_at=occurred_at,
                        operation_type="1",
                        amount=amount,
                        quantity=quantity,
                        station=None,
                        transaction_number=None,
                        dispenser=None,
                        fuel=row[product_index] if product_index is not None and len(row) > product_index else None,
                        unit_price=None,
                        issuer=None,
                        card_number=card_external_id,
                        holder=None,
                        contract=None,
                    )
                )
        return operations

    @staticmethod
    def _normalize_header(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip().lower())

    @staticmethod
    def _header_index(headers: list[str], *needles: str) -> int | None:
        for index, header in enumerate(headers):
            if any(needle in header for needle in needles):
                return index
        return None

    @staticmethod
    def _field(fields: dict[str, str], *needles: str) -> str | None:
        for header, value in fields.items():
            if any(needle in header for needle in needles):
                return value or None
        return None