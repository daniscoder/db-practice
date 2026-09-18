"""Задания 3 и 4: окно, карточки и отказоустойчивость без реальной базы.

Автор: Danis Arslanov
"""

import psycopg
import pytest
from PySide6.QtWidgets import QLabel, QMessageBox

from db import Partner, row_to_partner
from main_window import WINDOW_TITLE, MainWindow, PartnerCard, format_phone


def make_partner(company_name: str, discount: int) -> Partner:
    return Partner(
        partner_id=1,
        type_name="ООО",
        company_name=company_name,
        director="Иванов Иван Иванович",
        phone="+72233222232",
        rating=10,
        total_quantity=0,
        discount=discount,
    )


def card_texts(window: MainWindow, object_name: str) -> list[str]:
    return [label.text() for label in window.findChildren(QLabel, object_name)]


def test_title_and_icon(qt_app):
    window = MainWindow(lambda: [])
    assert window.windowTitle() == WINDOW_TITLE
    assert not window.windowIcon().isNull()


def test_cards_show_partners_and_discounts(qt_app):
    partners = [make_partner("Альфа", 10), make_partner("Бета", 15)]
    window = MainWindow(lambda: partners)
    window.refresh()
    assert card_texts(window, "cardTitle") == ["ООО | Альфа", "ООО | Бета"]
    assert card_texts(window, "cardDiscount") == ["10%", "15%"]


def test_partner_without_sales_shows_zero_percent(qt_app):
    row = {
        "partner_id": 5,
        "type_name": "ИП",
        "company_name": "Без продаж",
        "director": "Смирнов Алексей Владимирович",
        "phone": None,
        "rating": 5,
        "total_quantity": None,
    }
    window = MainWindow(lambda: [row_to_partner(row)])
    window.refresh()
    assert card_texts(window, "cardDiscount") == ["0%"]


def test_refresh_replaces_cards(qt_app):
    batches = [[make_partner("Альфа", 5), make_partner("Бета", 5)], [make_partner("Гамма", 0)]]
    window = MainWindow(lambda: batches.pop(0))
    window.refresh()
    window.refresh()
    assert len(window.findChildren(PartnerCard)) == 1


def test_empty_list_message(qt_app):
    window = MainWindow(lambda: [])
    window.refresh()
    assert window.findChild(QLabel, "statusLabel").text() == "Партнеров пока нет"


def test_database_error_does_not_crash(qt_app, monkeypatch):
    shown_errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown_errors.append(args[2]))

    def broken_loader():
        raise psycopg.OperationalError("сервер не отвечает")

    window = MainWindow(broken_loader)
    window.refresh()
    assert window.findChildren(PartnerCard) == []
    assert window.findChild(QLabel, "statusLabel").text() == "Не удалось загрузить партнеров"
    assert "сервер не отвечает" in shown_errors[0]


@pytest.mark.parametrize(
    ("phone", "expected"),
    [
        ("+72233222232", "+7 223 322 22 32"),
        ("+123", "+123"),
        (None, "Телефон не указан"),
    ],
)
def test_format_phone(phone, expected):
    assert format_phone(phone) == expected
