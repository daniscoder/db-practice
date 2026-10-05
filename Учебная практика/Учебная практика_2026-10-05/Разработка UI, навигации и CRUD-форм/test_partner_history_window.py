"""Задание 3: окно истории продаж партнера.

Автор: Danis Arslanov
"""

from datetime import date

from PySide6.QtWidgets import QAbstractItemView, QWidget

from db import SaleRecord
from partner_history_window import COLUMNS, PartnerHistoryWindow, open_history

SALES = [
    SaleRecord("Монитор 27\"", date(2023, 10, 28), 10),
    SaleRecord("Ноутбук Pro", date(2023, 10, 25), 50000),
]


def cell_texts(window: PartnerHistoryWindow) -> list[list[str]]:
    table = window.table
    return [[table.item(row, column).text() for column in range(table.columnCount())]
            for row in range(table.rowCount())]


def test_title_names_partner(qt_app):
    window = PartnerHistoryWindow("Альфа", SALES)
    assert window.windowTitle() == "CRM: История реализации продукции - Альфа"
    assert not window.windowIcon().isNull()


def test_columns_product_date_quantity(qt_app):
    window = PartnerHistoryWindow("Альфа", SALES)
    headers = [window.table.horizontalHeaderItem(i).text() for i in range(window.table.columnCount())]
    assert headers == ["Товар", "Дата продажи", "Количество, шт."]
    assert tuple(headers) == COLUMNS


def test_rows_in_human_format(qt_app):
    assert cell_texts(PartnerHistoryWindow("Альфа", SALES)) == [
        ["Монитор 27\"", "28.10.2023", "10"],
        ["Ноутбук Pro", "25.10.2023", "50 000"],
    ]


def test_table_is_read_only(qt_app):
    window = PartnerHistoryWindow("Альфа", SALES)
    assert window.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_summary(qt_app):
    assert PartnerHistoryWindow("Альфа", SALES).summary_label.text() == "Продаж: 2, всего 50 010 шт."


def test_empty_history(qt_app):
    window = PartnerHistoryWindow("Бета", [])
    assert window.table.rowCount() == 0
    assert window.summary_label.text() == "У партнера пока нет продаж"


def test_open_history_of_missing_partner(qt_app, fake_store, shown_dialogs):
    parent = QWidget()
    assert open_history(fake_store, 42, parent) is None
    assert "не найден" in shown_dialogs.errors[0]
    assert parent.findChild(PartnerHistoryWindow) is None
