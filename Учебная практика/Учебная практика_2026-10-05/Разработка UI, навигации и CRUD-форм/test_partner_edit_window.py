"""Задание 3: форма редактирования партнера, подсказки, переход в историю.

Автор: Danis Arslanov
"""

from dataclasses import replace

import psycopg
import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton

from partner_edit_window import ADD_TITLE, EDIT_TITLE, PartnerEditWindow
from partner_history_window import PartnerHistoryWindow

FIELD_NAMES = ["nameEdit", "innEdit", "ratingEdit", "addressEdit", "directorEdit", "phoneEdit", "emailEdit"]


def make_card(store, partner_id=None) -> PartnerEditWindow:
    card = PartnerEditWindow(store, store.types, partner_id, store.records.get(partner_id))
    card.open()
    return card


def save(card: PartnerEditWindow) -> None:
    card.findChild(QPushButton, "saveButton").click()


def fill_valid(card: PartnerEditWindow) -> None:
    card.name_edit.setText("Бета")
    card.inn_edit.setText("1234567890")
    card.email_edit.setText("beta@example.ru")


def test_add_mode(qt_app, fake_store):
    card = make_card(fake_store)
    assert card.windowTitle() == ADD_TITLE
    assert card.rating_edit.text() == "0"
    assert card.findChild(QPushButton, "historyButton") is None


def test_edit_mode_shows_data(qt_app, fake_store):
    card = make_card(fake_store, 1)
    assert card.windowTitle() == EDIT_TITLE
    assert card.name_edit.text() == "Вектор"
    assert card.type_combo.currentText() == "ООО"
    assert card.inn_edit.text() == "7701234567"
    assert card.rating_edit.text() == "5"
    assert card.address_edit.text() == "г. Москва"
    assert card.director_edit.text() == "Иванов Иван Иванович"
    assert card.phone_edit.text() == "+7 999 111 22 33"
    assert card.email_edit.text() == "vector@mail.ru"
    assert not card.windowIcon().isNull()


def test_all_fields_with_hints(qt_app, fake_store):
    card = make_card(fake_store)
    fields = [card.findChild(QLineEdit, name) for name in FIELD_NAMES]
    assert all(field.placeholderText() for field in fields)
    assert card.findChild(QComboBox, "typeCombo") is not None


def test_type_is_strict_list(qt_app, fake_store):
    card = make_card(fake_store)
    combo = card.type_combo
    assert not combo.isEditable()
    assert [combo.itemText(i) for i in range(combo.count())] == ["ИП", "ООО"]
    assert [combo.itemData(i) for i in range(combo.count())] == [1, 2]


@pytest.mark.parametrize(
    ("field_name", "typed", "expected"),
    [
        ("ratingEdit", "-5a,7", "57"),
        ("innEdit", "77-01 23x", "770123"),
        ("phoneEdit", "+7 (999) abc", "+7 (999) "),
    ],
)
def test_input_filters(qt_app, fake_store, field_name, typed, expected):
    card = make_card(fake_store)
    field = card.findChild(QLineEdit, field_name)
    field.clear()
    QTest.keyClicks(field, typed)
    assert field.text() == expected


def test_empty_optional_fields(qt_app, fake_store):
    fake_store.records[1] = replace(fake_store.records[1], director=None, phone=None, address=None)
    card = make_card(fake_store, 1)
    assert card.director_edit.text() == ""
    assert card.phone_edit.text() == ""
    assert card.address_edit.text() == ""


def test_unknown_type_leaves_list_empty(qt_app, fake_store):
    fake_store.records[1] = replace(fake_store.records[1], type_id=42)
    card = make_card(fake_store, 1)
    assert card.type_combo.currentData() is None


def test_modification_is_tracked(qt_app, fake_store):
    card = make_card(fake_store, 1)
    assert not card.is_modified()
    card.rating_edit.setText("6")
    assert card.is_modified()


def test_add_saves_to_store(qt_app, fake_store, shown_dialogs):
    card = make_card(fake_store)
    saved_signals = []
    card.saved.connect(lambda: saved_signals.append(True))
    fill_valid(card)
    card.phone_edit.setText("8 999 123-45-67")
    save(card)
    created = fake_store.created[0]
    assert (created.partner_name, created.inn, created.phone, created.rating) == ("Бета", "1234567890", "+79991234567", 0)
    assert "добавлен" in shown_dialogs.infos[0]
    assert saved_signals == [True]
    assert not card.isVisible()


def test_edit_saves_to_store(qt_app, fake_store, shown_dialogs):
    card = make_card(fake_store, 1)
    card.rating_edit.setText("8")
    save(card)
    assert fake_store.updated[0][0] == 1
    assert fake_store.updated[0][1].rating == 8
    assert "сохранены" in shown_dialogs.infos[0]


def test_history_from_card_keeps_input(qt_app, fake_store, shown_dialogs):
    card = make_card(fake_store, 1)
    card.address_edit.setText("г. Тверь, несохраненный адрес")
    card.findChild(QPushButton, "historyButton").click()
    history = card.findChild(PartnerHistoryWindow)
    assert history.isVisible()
    assert history.table.rowCount() == 2
    history.findChild(QPushButton, "backButton").click()
    assert not history.isVisible()
    assert card.isVisible()
    assert card.address_edit.text() == "г. Тверь, несохраненный адрес"


def test_history_from_card_database_error(qt_app, fake_store, shown_dialogs):
    card = make_card(fake_store, 1)
    fake_store.errors["sales"] = psycopg.OperationalError("сервер не отвечает")
    card.findChild(QPushButton, "historyButton").click()
    assert "историю продаж" in shown_dialogs.errors[0]
    assert card.findChild(PartnerHistoryWindow) is None
