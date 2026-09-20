"""Общие фикстуры тестов.

Автор: Danis Arslanov
"""

import os

import psycopg
import pytest

# Окно в тестах строится без экрана. Задается до создания QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from task_2_database import db


@pytest.fixture(scope="session")
def connection():
    """Подключение к базе практики. Без базы интеграционные тесты пропускаются."""
    try:
        conn = db.connect()
    except psycopg.OperationalError as error:
        pytest.skip(f"База недоступна: {error}")
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def qt_app():
    """Один QApplication на весь прогон: второй Qt создать не даст."""
    app = QApplication.instance() or QApplication([])
    yield app
