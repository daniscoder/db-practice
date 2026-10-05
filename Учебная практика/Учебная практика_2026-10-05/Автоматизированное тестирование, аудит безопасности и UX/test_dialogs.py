"""Задание 4: MessageBox с пошаговыми подсказками, предупреждение на
«Назад» и защита от падений.

Автор: Danis Arslanov
"""

import logging
import sys

import psycopg
from PySide6.QtWidgets import QMessageBox, QPushButton

import dialogs
from db import DuplicateValueError, PartnerType
from partner_edit_window import PartnerEditWindow
from user_messages import database_error_text, guide_text, unexpected_error_text


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
    assert "потеряны безвозвратно" in box.text()
    assert discard_button.text() == dialogs.DISCARD_BUTTON_TEXT
    assert box.defaultButton().text() == dialogs.STAY_BUTTON_TEXT


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
    monkeypatch.setattr(QMessageBox, "exec", click_button(dialogs.DISCARD_BUTTON_TEXT))
    assert dialogs.confirm_discard(None) is True


def test_confirm_discard_declined(qt_app, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", click_button(dialogs.STAY_BUTTON_TEXT))
    assert dialogs.confirm_discard(None) is False


def test_guide_text_numbers_steps():
    assert guide_text("Беда.", ["Шаг первый.", "Шаг второй."]) == (
        "Беда.\n\nКак исправить:\n1. Шаг первый.\n2. Шаг второй."
    )


def test_database_error_text():
    text = database_error_text("сохранить партнера", RuntimeError("нет связи"))
    assert text.startswith("Не удалось сохранить партнера")
    assert "1. Убедитесь, что сервер PostgreSQL запущен." in text
    assert "PGPASSWORD" in text
    assert text.endswith("Подробности: нет связи")


def test_unexpected_error_text():
    text = unexpected_error_text(ZeroDivisionError("division by zero"))
    assert "app.log" in text
    assert text.endswith("Подробности: division by zero")


def test_unexpected_error_is_shown_and_logged(shown_dialogs, caplog):
    try:
        raise ZeroDivisionError("division by zero")
    except ZeroDivisionError as error:
        dialogs.handle_unexpected_error(type(error), error, error.__traceback__)
    assert "непредвиденная ошибка" in shown_dialogs.errors[0]
    assert caplog.records[-1].levelno == logging.CRITICAL
    assert "ZeroDivisionError" in caplog.text


def test_ctrl_c_still_stops_program(shown_dialogs, monkeypatch):
    passed = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *args: passed.append(args[0]))
    dialogs.handle_unexpected_error(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert passed == [KeyboardInterrupt]
    assert shown_dialogs.errors == []


TYPES = [PartnerType(1, "ИП"), PartnerType(2, "ООО")]


def open_card(store, partner_id=None) -> PartnerEditWindow:
    card = PartnerEditWindow(store, TYPES, partner_id, store.records.get(partner_id))
    card.open()
    return card


def fill_valid(card: PartnerEditWindow) -> None:
    card.name_edit.setText("Бета")
    card.inn_edit.setText("1234567890")
    card.email_edit.setText("beta@example.ru")


def save(card: PartnerEditWindow) -> None:
    card.findChild(QPushButton, "saveButton").click()


def test_input_error_shows_steps(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store)
    fill_valid(card)
    card.inn_edit.setText("123")
    save(card)
    assert "ИНН должен состоять из 10 цифр" in shown_dialogs.errors[0]
    assert "Как исправить:\n1. " in shown_dialogs.errors[0]
    assert fake_store.created == []
    assert card.isVisible()


def test_database_unavailable_on_save(qt_app, fake_store, shown_dialogs):
    fake_store.errors["create"] = psycopg.OperationalError("сервер не отвечает")
    card = open_card(fake_store)
    fill_valid(card)
    save(card)
    assert "Не удалось сохранить партнера" in shown_dialogs.errors[0]
    assert "Подробности: сервер не отвечает" in shown_dialogs.errors[0]
    assert card.isVisible()


def test_duplicate_on_save(qt_app, fake_store, shown_dialogs):
    fake_store.errors["create"] = DuplicateValueError("Партнер с ИНН 1234567890 уже есть в базе.")
    card = open_card(fake_store)
    fill_valid(card)
    save(card)
    assert shown_dialogs.errors == ["Партнер с ИНН 1234567890 уже есть в базе."]


def test_back_without_changes_closes_silently(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store, 1)
    card.findChild(QPushButton, "backButton").click()
    assert shown_dialogs.warnings == 0
    assert not card.isVisible()


def test_back_with_changes_can_stay(qt_app, fake_store, shown_dialogs):
    shown_dialogs.discard_answer = False
    card = open_card(fake_store, 1)
    card.name_edit.setText("Черновик")
    card.findChild(QPushButton, "backButton").click()
    assert shown_dialogs.warnings == 1
    assert card.isVisible()
    assert card.name_edit.text() == "Черновик"


def test_back_with_changes_can_discard(qt_app, fake_store, shown_dialogs):
    card = open_card(fake_store)
    card.name_edit.setText("Черновик")
    card.findChild(QPushButton, "backButton").click()
    assert shown_dialogs.warnings == 1
    assert not card.isVisible()
