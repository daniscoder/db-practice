"""Задание 4: журнал ошибок в файл app.log.

Автор: Danis Arslanov
"""

import logging
import re

import psycopg

from app_logging import setup_logging
from main_window import MainWindow

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
    MainWindow(fake_store).refresh()
    assert "Не удалось загрузить список партнеров: сервер не отвечает" in caplog.text
