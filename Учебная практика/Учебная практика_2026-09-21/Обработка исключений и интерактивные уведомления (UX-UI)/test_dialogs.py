"""Задание 4: диалоги трех типов и реакция карточки на ошибки.

Автор: Danis Arslanov
"""

import psycopg
from PySide6.QtWidgets import QMessageBox, QPushButton

import dialogs
from db import DuplicateEmailError
from partner_edit_window import PartnerEditWindow


def test_error_box(qt_app):
    box = dialogs.error_box(None, "Текст ошибки")
    assert box.icon() == QMessageBox.Icon.Critical
    assert box.windowTitle() == dialogs.ERROR_TITLE
    assert box.text() == "Текст ошибки"


def test_info_box(qt_app):
    box = dialogs.info_box(None, "Готово")
    assert box.icon() == QMessageBox.Icon.Information
    assert box.windowTitle() == dialogs.INFO_TITLE


def test_discard_box(qt_app):
    box, discard_button = dialogs.discard_box(None)
    assert box.icon() == QMessageBox.Icon.Warning
    assert box.windowTitle() == dialogs.WARNING_TITLE
    assert "потеряны" in box.text()
    assert discard_button.text() == "Закрыть без сохранения"
    assert box.defaultButton().text() == "Вернуться к карточке"


def test_show_error_and_info(qt_app, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append((self.icon(), self.windowTitle())))
    dialogs.show_error(None, "ошибка")
    dialogs.show_info(None, "готово")
    assert shown == [
        (QMessageBox.Icon.Critical, dialogs.ERROR_TITLE),
        (QMessageBox.Icon.Information, dialogs.INFO_TITLE),
    ]


def click_button(text: str):
    def fake_exec(box: QMessageBox):
        next(button for button in box.buttons() if button.text() == text).click()
    return fake_exec


def test_confirm_discard_agreed(qt_app, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", click_button("Закрыть без сохранения"))
    assert dialogs.confirm_discard(None) is True


def test_confirm_discard_declined(qt_app, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", click_button("Вернуться к карточке"))
    assert dialogs.confirm_discard(None) is False


def test_database_error_text():
    text = dialogs.database_error_text("сохранить партнера", RuntimeError("нет связи"))
    assert "сохранить партнера" in text
    assert "PGPASSWORD" in text
    assert "нет связи" in text


def open_card(store, partner_id=None) -> PartnerEditWindow:
    partner = store.records.get(partner_id)
    card = PartnerEditWindow(store, store.types, partner_id, partner)
    card.open()
    return card


def fill_valid(card: PartnerEditWindow) -> None:
    card.name_edit.setText("Бета")
    card.rating_edit.setText("5")
    card.email_edit.setText("beta@example.ru")


def save(card: PartnerEditWindow) -> None:
    card.findChild(QPushButton, "saveButton").click()


def test_bad_rating_blocks_save(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store)
    fill_valid(card)
    card.rating_edit.setText("4.5")
    save(card)
    assert "целым числом от 0" in shown_dialogs.errors[0]
    assert fake_store.created == []
    assert card.isVisible()


def test_empty_email_blocks_save(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store)
    fill_valid(card)
    card.email_edit.setText("")
    save(card)
    assert "Email" in shown_dialogs.errors[0]
    assert fake_store.created == []


def test_database_unavailable_on_save(qt_app, fake_store, shown_dialogs):
    fake_store.errors["create"] = psycopg.OperationalError("сервер не отвечает")
    card = open_card(fake_store)
    fill_valid(card)
    save(card)
    assert "PGPASSWORD" in shown_dialogs.errors[0]
    assert card.isVisible()


def test_duplicate_email_on_save(qt_app, fake_store, shown_dialogs):
    fake_store.errors["create"] = DuplicateEmailError("Партнер с email beta@example.ru уже есть в базе.")
    card = open_card(fake_store)
    fill_valid(card)
    save(card)
    assert shown_dialogs.errors == ["Партнер с email beta@example.ru уже есть в базе."]


def test_successful_add_informs(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store)
    saved_signals = []
    card.saved.connect(lambda: saved_signals.append(True))
    fill_valid(card)
    save(card)
    assert "добавлен" in shown_dialogs.infos[0]
    assert saved_signals == [True]
    assert not card.isVisible()


def test_successful_edit_informs(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store, 1)
    card.rating_edit.setText("8")
    save(card)
    assert fake_store.updated[0][1].rating == 8
    assert "сохранены" in shown_dialogs.infos[0]


def test_back_with_changes_can_stay(qt_app, fake_store, shown_dialogs):
    shown_dialogs.discard_answer = False
    card = open_card(fake_store)
    card.name_edit.setText("Черновик")
    card.findChild(QPushButton, "backButton").click()
    assert shown_dialogs.warnings == 1
    assert card.isVisible()


def test_back_with_changes_can_discard(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store)
    card.name_edit.setText("Черновик")
    card.findChild(QPushButton, "backButton").click()
    assert shown_dialogs.warnings == 1
    assert not card.isVisible()
