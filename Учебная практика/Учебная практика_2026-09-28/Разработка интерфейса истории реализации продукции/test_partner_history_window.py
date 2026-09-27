"""Задание 1: окно истории реализации продукции.

Автор: Danis Arslanov
"""

from datetime import date

from PySide6.QtWidgets import QAbstractItemView

from db import SaleRecord
from partner_history_window import COLUMNS, PartnerHistoryWindow

SALES = [
    SaleRecord("Кондиционер для белья", 50000, date(2026, 8, 8)),
    SaleRecord("Мыло жидкое \"Стандарт\"", 100000, date(2026, 5, 5)),
]


def cell_texts(window: PartnerHistoryWindow) -> list[list[str]]:
    table = window.table
    return [[table.item(row, column).text() for column in range(table.columnCount())]
            for row in range(table.rowCount())]


def test_title_names_partner(qt_app):
    window = PartnerHistoryWindow("Дом и Сад", SALES)
    assert window.windowTitle() == "CRM: История реализации продукции - Дом и Сад"
    assert not window.windowIcon().isNull()


def test_required_columns(qt_app):
    window = PartnerHistoryWindow("Дом и Сад", SALES)
    headers = [window.table.horizontalHeaderItem(i).text() for i in range(window.table.columnCount())]
    assert headers == ["Наименование продукции", "Количество (шт.)", "Дата продажи"]
    assert tuple(headers) == COLUMNS


def test_rows_in_human_format(qt_app):
    window = PartnerHistoryWindow("Дом и Сад", SALES)
    assert cell_texts(window) == [
        ["Кондиционер для белья", "50 000", "08.08.2026"],
        ["Мыло жидкое \"Стандарт\"", "100 000", "05.05.2026"],
    ]


def test_table_is_read_only(qt_app):
    window = PartnerHistoryWindow("Дом и Сад", SALES)
    assert window.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_summary(qt_app):
    window = PartnerHistoryWindow("Дом и Сад", SALES)
    assert window.summary_label.text() == "Продаж: 2, всего 150 000 шт."


def test_empty_history(qt_app):
    window = PartnerHistoryWindow("Смирнов А.В.", [])
    assert window.table.rowCount() == 0
    assert window.summary_label.text() == "У партнера пока нет продаж"
