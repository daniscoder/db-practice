"""Общие фикстуры тестов.

Автор: Danis Arslanov
"""

import os
import sys
from pathlib import Path

import psycopg
import pytest

# Окно в тестах строится без экрана. Задается до создания QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Модули лежат в папках заданий с русскими именами и пробелами, пакетами Python
# эти папки быть не могут. Каждая папка «Задание ...» добавляется в sys.path.
PRACTICE_DIR = Path(__file__).resolve().parent
for task_dir in sorted(PRACTICE_DIR.glob("Задание *")):
    sys.path.insert(0, str(task_dir))

from PySide6.QtWidgets import QApplication

import db


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
