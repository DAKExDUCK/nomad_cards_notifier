from modules.fuel_cards.collector import FuelCardRecord, NomadCardsCollector


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
