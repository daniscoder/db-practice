"""Общие фикстуры тестов.

Автор: Danis Arslanov
"""

import os
import sys
from pathlib import Path

import psycopg
import pytest

# Окна в тестах строятся без экрана. Задается до создания QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Модули лежат в папках заданий с русскими именами и пробелами, пакетами Python
# эти папки быть не могут. Каждая папка задания добавляется в sys.path,
# служебные каталоги (.idea, __pycache__ и подобные) пропускаются.
PRACTICE_DIR = Path(__file__).resolve().parent
for task_dir in sorted(PRACTICE_DIR.iterdir()):
    if task_dir.is_dir() and not task_dir.name.startswith((".", "_")):
        sys.path.insert(0, str(task_dir))

from PySide6.QtWidgets import QApplication

import db
import dialogs
from db import PartnerData, PartnerListItem, PartnerNotFoundError, PartnerType


@pytest.fixture(scope="session")
def qt_app():
    """Один QApplication на весь прогон: второй Qt создать не даст."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(scope="session")
def connection():
    """Подключение к базе практики. Без базы тесты с базой пропускаются."""
    try:
        conn = db.connect()
    except psycopg.OperationalError as error:
        pytest.skip(f"База недоступна: {error}")
    yield conn
    conn.close()


@pytest.fixture
def db_conn(connection):
    """Подключение, все изменения которого откатываются после теста."""
    yield connection
    connection.rollback()


class FakeStore:
    """Хранилище партнеров в памяти вместо базы. errors задает, какой метод
    и каким исключением откажет."""

    def __init__(self) -> None:
        self.types = [PartnerType(1, "ЗАО"), PartnerType(2, "ООО")]
        self.items = [PartnerListItem(1, "ООО", "Альфа", "Иванов Иван Иванович", "+79991112233", 5, 10)]
        self.records = {
            1: PartnerData(type_id=2, company_name="Альфа", director="Иванов Иван Иванович",
                           phone="+79991112233", email="alpha@example.ru", address="г. Москва", rating=5),
        }
        self.created: list[PartnerData] = []
        self.updated: list[tuple[int, PartnerData]] = []
        self.errors: dict[str, Exception] = {}
        self.partners_calls = 0

    def _fail(self, method: str) -> None:
        if method in self.errors:
            raise self.errors[method]

    def partner_types(self) -> list[PartnerType]:
        self._fail("partner_types")
        return self.types

    def partners(self) -> list[PartnerListItem]:
        self._fail("partners")
        self.partners_calls += 1
        return self.items

    def load(self, partner_id: int) -> PartnerData:
        self._fail("load")
        if partner_id not in self.records:
            raise PartnerNotFoundError("Партнер не найден в базе.")
        return self.records[partner_id]

    def create(self, data: PartnerData) -> int:
        self._fail("create")
        self.created.append(data)
        return 99

    def update(self, partner_id: int, data: PartnerData) -> None:
        self._fail("update")
        self.updated.append((partner_id, data))


@pytest.fixture
def fake_store():
    return FakeStore()


class DialogRecorder:
    """Вместо настоящих диалогов запоминает, что было бы показано."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.infos: list[str] = []
        self.warnings = 0
        self.discard_answer = True

    def show_error(self, parent, text: str) -> None:
        self.errors.append(text)

    def show_info(self, parent, text: str) -> None:
        self.infos.append(text)

    def confirm_discard(self, parent) -> bool:
        self.warnings += 1
        return self.discard_answer


@pytest.fixture
def shown_dialogs(monkeypatch):
    recorder = DialogRecorder()
    monkeypatch.setattr(dialogs, "show_error", recorder.show_error)
    monkeypatch.setattr(dialogs, "show_info", recorder.show_info)
    monkeypatch.setattr(dialogs, "confirm_discard", recorder.confirm_discard)
    return recorder
