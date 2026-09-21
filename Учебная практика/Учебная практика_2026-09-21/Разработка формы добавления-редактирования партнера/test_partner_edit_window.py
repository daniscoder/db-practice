"""Задание 2: поля карточки партнера, выпадающий список и подсказки.

Автор: Danis Arslanov
"""

from dataclasses import replace

from PySide6.QtWidgets import QComboBox, QLineEdit

from partner_edit_window import ADD_TITLE, EDIT_TITLE, PartnerEditWindow

FIELD_NAMES = ["nameEdit", "ratingEdit", "addressEdit", "directorEdit", "phoneEdit", "emailEdit"]


def make_card(store, partner_id=None, partner=None) -> PartnerEditWindow:
    return PartnerEditWindow(store, store.types, partner_id, partner)


def test_add_mode_title(qt_app, fake_store):
    assert make_card(fake_store).windowTitle() == ADD_TITLE


def test_edit_mode_title_and_data(qt_app, fake_store):
    card = make_card(fake_store, 1, fake_store.records[1])
    assert card.windowTitle() == EDIT_TITLE
    assert card.name_edit.text() == "Альфа"
    assert card.type_combo.currentText() == "ООО"
    assert card.rating_edit.text() == "5"
    assert card.address_edit.text() == "г. Москва"
    assert card.director_edit.text() == "Иванов Иван Иванович"
    assert card.phone_edit.text() == "+7 999 111 22 33"
    assert card.email_edit.text() == "alpha@example.ru"


def test_all_fields_present(qt_app, fake_store):
    card = make_card(fake_store)
    assert all(card.findChild(QLineEdit, name) is not None for name in FIELD_NAMES)
    assert card.findChild(QComboBox, "typeCombo") is not None


def test_type_is_strict_list(qt_app, fake_store):
    card = make_card(fake_store)
    combo = card.type_combo
    assert not combo.isEditable()
    assert [combo.itemText(i) for i in range(combo.count())] == ["ЗАО", "ООО"]
    assert [combo.itemData(i) for i in range(combo.count())] == [1, 2]


def test_phone_and_email_hints(qt_app, fake_store):
    card = make_card(fake_store)
    for field in (card.phone_edit, card.email_edit):
        assert field.placeholderText()
        assert field.toolTip()


def test_empty_optional_fields(qt_app, fake_store):
    partner = replace(fake_store.records[1], director=None, phone=None, address=None)
    card = make_card(fake_store, 1, partner)
    assert card.director_edit.text() == ""
    assert card.phone_edit.text() == ""
    assert card.address_edit.text() == ""


def test_unknown_type_leaves_list_empty(qt_app, fake_store):
    partner = replace(fake_store.records[1], type_id=42)
    card = make_card(fake_store, 1, partner)
    assert card.type_combo.currentData() is None


def test_modification_is_tracked(qt_app, fake_store):
    card = make_card(fake_store, 1, fake_store.records[1])
    assert not card.is_modified()
    card.rating_edit.setText("6")
    assert card.is_modified()
