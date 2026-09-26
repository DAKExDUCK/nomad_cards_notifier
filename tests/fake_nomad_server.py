import json
import threading
from argparse import ArgumentParser
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _html_table(headers: list[str], rows: list[list[str]]) -> str:
    header_html = "".join(f"<th>{escape(value)}</th>" for value in headers)
    rows_html = "".join("<tr>" + "".join(f"<td>{escape(value)}</td>" for value in row) + "</tr>" for row in rows)
    return f"<table><tr>{header_html}</tr>{rows_html}</table>"


def _cards_page(cards: list[dict]) -> str:
    rows = []
    for card in cards:
        rows.append(
            f'<tr><td></td><td><a href="/ignore">ignore</a>'
            f'<a href="/card/1/{card["external_id"]}">card</a></td><td>{card["name"]}</td></tr>'
        )
    return '<table id="cards">' + "".join(rows) + "</table>"


def _sales_page(rows: list[list[str]]) -> str:
    headers = [
        "Дата/время",
        "АЗС",
        "№ трнз.",
        "Колонка",
        "Топливо",
        "Цена",
        "Объём",
        "Сумма",
        "Эмитент",
        "Карта",
        "Держатель",
        "Договор",
    ]
    return _html_table(headers, rows)


def _card_page(operations: list[dict]) -> str:
    rows = []
    for operation in operations:
        rows.append(
            [
                f"Оформлено: {operation['occurred_at']}<br>Выполнено {operation['occurred_at']}",
                operation.get("fuel", ""),
                f"Пополнение баланса: {operation['quantity']}",
                "выполнено",
            ]
        )
    return _html_table(["Дата", "Продукт", "Операция", "Статус"], rows)


class _FakeNomadHandler(BaseHTTPRequestHandler):
    server_version = "FakeNomad/1.0"

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode()
        self.server.requests.append(("POST", self.path, parse_qs(body)))
        if self.path == "/login":
            self.send_response(302)
            self.send_header("Location", "/cards")
            self.end_headers()
            return
        if self.path == "/sales1":
            self._write_html(_sales_page(self.server.fixture.get("sales", [])))
            return
        if self.path == "/__test__/transactions":
            self._add_transaction(body)
            return
        self.send_error(404)

    def do_GET(self) -> None:
        self.server.requests.append(("GET", self.path, {}))
        if self.path == "/cards":
            self._write_html(_cards_page(self.server.fixture.get("cards", [])))
            return
        card_id = urlparse(self.path).path.removeprefix("/card/1/")
        for card in self.server.fixture.get("cards", []):
            if card["external_id"] == card_id:
                self._write_html(_card_page(card.get("top_ups", [])))
                return
        self.send_error(404)

    def _write_html(self, content: str) -> None:
        encoded = content.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _add_transaction(self, body: str) -> None:
        try:
            transaction = json.loads(body)
            transaction_type = transaction["type"]
            card_id = transaction["card_external_id"]
            occurred_at = transaction["occurred_at"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._write_json({"error": "Expected type, card_external_id and occurred_at"}, status=400)
            return

        if transaction_type == "top_up":
            card = next((card for card in self.server.fixture.get("cards", []) if card["external_id"] == card_id), None)
            if card is None:
                self._write_json({"error": f"Unknown card: {card_id}"}, status=404)
                return
            card.setdefault("top_ups", []).append(
                {
                    "occurred_at": occurred_at,
                    "fuel": transaction.get("fuel", ""),
                    "quantity": transaction.get("quantity", ""),
                }
            )
        elif transaction_type == "sale":
            self.server.fixture.setdefault("sales", []).append(
                [
                    occurred_at,
                    transaction.get("station", ""),
                    transaction.get("transaction_number", ""),
                    transaction.get("dispenser", ""),
                    transaction.get("fuel", ""),
                    transaction.get("unit_price", ""),
                    transaction.get("quantity", ""),
                    transaction.get("amount", ""),
                    transaction.get("issuer", ""),
                    card_id,
                    transaction.get("holder", ""),
                    transaction.get("contract", ""),
                ]
            )
        else:
            self._write_json({"error": "type must be sale or top_up"}, status=400)
            return
        self._write_json({"status": "added", "type": transaction_type, "card_external_id": card_id}, status=201)

    def _write_json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        del format, args


@contextmanager
def fake_nomad_server(fixture_path: str | Path) -> Iterator[tuple[str, list[tuple[str, str, dict]]]]:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeNomadHandler)
    server.fixture = fixture
    server.requests = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server.requests
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()


def main() -> None:
    parser = ArgumentParser(description="Run a local Nomad-compatible test server")
    parser.add_argument("--fixture", type=Path, default=Path(__file__).parent / "fixtures" / "nomad_site.json")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), _FakeNomadHandler)
    server.fixture = fixture
    server.requests = []
    print(f"Fake Nomad server: http://127.0.0.1:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
