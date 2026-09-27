"""Задание 1: реестр партнеров и переходы в карточку, историю продаж и расчет.

Автор: Danis Arslanov
"""

import psycopg
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QPushButton

import main
from db import PartnerListItem
from main_window import WINDOW_TITLE, MainWindow, PartnerCard
from material_calculator_window import MaterialCalculatorWindow
from partner_edit_window import ADD_TITLE, EDIT_TITLE, PartnerEditWindow
from partner_history_window import PartnerHistoryWindow
from ui_common import format_phone, format_quantity


def open_registry(store) -> MainWindow:
    window = MainWindow(store)
    window.refresh()
    return window


def status_text(window: MainWindow) -> str:
    return window.findChild(QLabel, "statusLabel").text()


def test_registry_title(qt_app, fake_store):
    assert open_registry(fake_store).windowTitle() == WINDOW_TITLE


def test_add_button_opens_empty_card(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    window.findChild(QPushButton, "addButton").click()
    card = window.findChild(PartnerEditWindow)
    assert card.isVisible()
    assert card.windowTitle() == ADD_TITLE
    assert card.name_edit.text() == ""


def test_double_click_opens_card_with_data(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    QTest.mouseDClick(window.findChild(PartnerCard), Qt.MouseButton.LeftButton)
    card = window.findChild(PartnerEditWindow)
    assert card.windowTitle() == EDIT_TITLE
    assert card.name_edit.text() == "Альфа"


def test_back_returns_to_registry(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    window.open_add_window()
    card = window.findChild(PartnerEditWindow)
    card.findChild(QPushButton, "backButton").click()
    assert not card.isVisible()
    assert shown_dialogs.warnings == 0


def test_saved_card_refreshes_registry(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    calls_before = fake_store.partners_calls
    window.open_add_window()
    card = window.findChild(PartnerEditWindow)
    card.name_edit.setText("Бета")
    card.rating_edit.setText("3")
    card.email_edit.setText("beta@example.ru")
    card.findChild(QPushButton, "saveButton").click()
    assert fake_store.created[0].company_name == "Бета"
    assert fake_store.partners_calls == calls_before + 1
    assert not card.isVisible()


def test_missing_partner_is_reported(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    fake_store.records.clear()
    window.open_edit_window(1)
    assert "не найден" in shown_dialogs.errors[0]
    assert window.findChild(PartnerEditWindow) is None


def test_database_error_on_open(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    fake_store.errors["load"] = psycopg.OperationalError("сервер не отвечает")
    window.open_edit_window(1)
    assert "PGPASSWORD" in shown_dialogs.errors[0]
    assert window.findChild(PartnerEditWindow) is None


def test_database_error_on_types(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    fake_store.errors["partner_types"] = psycopg.OperationalError("сервер не отвечает")
    window.open_add_window()
    assert "справочник" in shown_dialogs.errors[0]
    assert window.findChild(PartnerEditWindow) is None


def test_database_error_on_registry(qt_app, fake_store, shown_dialogs):
    fake_store.errors["partners"] = psycopg.OperationalError("сервер не отвечает")
    window = open_registry(fake_store)
    assert status_text(window) == "Не удалось загрузить партнеров"
    assert window.findChildren(PartnerCard) == []
    assert "список партнеров" in shown_dialogs.errors[0]


def test_empty_registry(qt_app, fake_store):
    fake_store.items = []
    assert status_text(open_registry(fake_store)) == "Партнеров пока нет"


def test_refresh_replaces_cards(qt_app, fake_store):
    window = open_registry(fake_store)
    window.refresh()
    assert len(window.findChildren(PartnerCard)) == 1


def test_card_without_director_and_phone(qt_app, fake_store):
    fake_store.items = [PartnerListItem(2, "ИП", "Гамма", None, None, 0, 0)]
    window = open_registry(fake_store)
    texts = [label.text() for label in window.findChildren(QLabel)]
    assert "Директор не указан" in texts
    assert "Телефон не указан" in texts


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


def test_main_starts_registry(qt_app, fake_store, monkeypatch):
    class FakeApplication:
        def __init__(self, argv):
            self.argv = argv

        def exec(self):
            return 0

    log_paths = []
    monkeypatch.setattr(main, "QApplication", FakeApplication)
    monkeypatch.setattr(main, "setup_logging", log_paths.append)
    monkeypatch.setattr(main.db, "PartnerStore", lambda: fake_store)
    monkeypatch.setattr(main.MainWindow, "show", lambda self: None)
    assert main.main() == 0
    assert fake_store.partners_calls == 1
    assert log_paths == [main.LOG_PATH]


def test_format_quantity():
    assert format_quantity(150000) == "150 000"


def select_first_partner(window: MainWindow) -> PartnerCard:
    card = window.findChild(PartnerCard)
    QTest.mouseClick(card, Qt.MouseButton.LeftButton)
    return card


def history_button(window: MainWindow) -> QPushButton:
    return window.findChild(QPushButton, "historyButton")


def test_history_needs_selected_partner(qt_app, fake_store):
    window = open_registry(fake_store)
    assert not history_button(window).isEnabled()
    card = select_first_partner(window)
    assert history_button(window).isEnabled()
    assert card.property("selected") is True


def test_history_opens_for_selected_partner(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    select_first_partner(window)
    history_button(window).click()
    history = window.findChild(PartnerHistoryWindow)
    assert history.windowTitle() == "CRM: История реализации продукции - Альфа"
    assert history.table.rowCount() == 2


def test_history_of_missing_partner(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    select_first_partner(window)
    fake_store.records.clear()
    history_button(window).click()
    assert "не найден" in shown_dialogs.errors[0]
    assert window.findChild(PartnerHistoryWindow) is None


def test_history_database_error(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    select_first_partner(window)
    fake_store.errors["sales"] = psycopg.OperationalError("сервер не отвечает")
    history_button(window).click()
    assert "историю продаж" in shown_dialogs.errors[0]
    assert window.findChild(PartnerHistoryWindow) is None


def test_selection_kept_after_refresh(qt_app, fake_store):
    window = open_registry(fake_store)
    select_first_partner(window)
    window.refresh()
    assert history_button(window).isEnabled()
    assert window.findChild(PartnerCard).property("selected") is True


def test_selection_dropped_when_partner_gone(qt_app, fake_store):
    window = open_registry(fake_store)
    select_first_partner(window)
    fake_store.items = []
    window.refresh()
    assert not history_button(window).isEnabled()


def test_calculator_opens(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    window.findChild(QPushButton, "calculatorButton").click()
    calculator = window.findChild(MaterialCalculatorWindow)
    assert calculator.windowTitle() == "CRM: Расчет материалов"
    assert calculator.product_type_combo.count() == 1


def test_calculator_database_error(qt_app, fake_store, shown_dialogs):
    window = open_registry(fake_store)
    fake_store.errors["material_types"] = psycopg.OperationalError("сервер не отвечает")
    window.findChild(QPushButton, "calculatorButton").click()
    assert "справочники" in shown_dialogs.errors[0]
    assert window.findChild(MaterialCalculatorWindow) is None
