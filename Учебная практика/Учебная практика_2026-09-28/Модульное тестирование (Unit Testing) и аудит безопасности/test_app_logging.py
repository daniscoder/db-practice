"""Задание 4: журнал ошибок в файл app.log.

Автор: Danis Arslanov
"""

import logging
import re
from decimal import Decimal

import psycopg
from PySide6.QtWidgets import QPushButton

from app_logging import setup_logging
from db import MaterialType, ProductType
from main_window import MainWindow
from material_calculator_window import MaterialCalculatorWindow
from partner_edit_window import PartnerEditWindow

LOG_LINE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ERROR проверка: Не удалось подключиться к базе$")


def test_log_file_has_date_time_and_text(tmp_path):
    log_path = tmp_path / "app.log"
    handler = setup_logging(log_path)
    try:
        logging.getLogger("проверка").error("Не удалось подключиться к базе")
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()
    assert LOG_LINE.match(log_path.read_text(encoding="utf-8").strip())


def test_registry_error_is_logged(qt_app, fake_store, shown_dialogs, caplog):
    fake_store.errors["partners"] = psycopg.OperationalError("сервер не отвечает")
    window = MainWindow(fake_store)
    window.refresh()
    assert "Не удалось загрузить список партнеров: сервер не отвечает" in caplog.text


def test_card_save_error_is_logged(qt_app, fake_store, shown_dialogs, caplog):
    card = PartnerEditWindow(fake_store, fake_store.types)
    card.name_edit.setText("Бета")
    card.rating_edit.setText("4.5")
    card.email_edit.setText("beta@example.ru")
    card.findChild(QPushButton, "saveButton").click()
    assert "Карточка партнера не сохранена: Рейтинг должен быть целым числом" in caplog.text


def test_card_database_error_is_logged(qt_app, fake_store, shown_dialogs, caplog):
    fake_store.errors["create"] = psycopg.OperationalError("сервер не отвечает")
    card = PartnerEditWindow(fake_store, fake_store.types)
    card.name_edit.setText("Бета")
    card.rating_edit.setText("4")
    card.email_edit.setText("beta@example.ru")
    card.findChild(QPushButton, "saveButton").click()
    assert "Не удалось сохранить партнера: сервер не отвечает" in caplog.text


def test_calculator_rejection_is_logged(qt_app, shown_dialogs, caplog):
    window = MaterialCalculatorWindow([ProductType(1, "Порошковые средства", Decimal("2.35"))],
                                      [MaterialType(1, "Картон", Decimal("0.10"))])
    window.quantity_edit.setText("0")
    window.param_1_edit.setText("2")
    window.param_2_edit.setText("3")
    window.findChild(QPushButton, "calculateButton").click()
    assert "Расчет материалов: неверное количество продукции 0" in caplog.text
