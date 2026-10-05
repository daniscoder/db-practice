"""Общие фикстуры тестов.

Автор: Danis Arslanov
"""

import os
import sys
from datetime import date
from decimal import Decimal
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
from db import (
    MaterialType,
    PartnerData,
    PartnerListItem,
    PartnerType,
    ProductType,
    SaleRecord,
    partner_not_found,
)


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


class NoCommit:
    """Отдает тестовое подключение вместо нового и ничего не фиксирует:
    все изменения откатятся после теста."""

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *exc_info):
        return False


@pytest.fixture
def db_store(db_conn, monkeypatch):
    """Настоящий CrmStore, который работает в откатываемой транзакции теста."""
    monkeypatch.setattr(db, "connect", lambda: NoCommit(db_conn))
    return db.CrmStore()


class FakeStore:
    """Хранилище в памяти вместо базы. errors задает, какой метод и каким
    исключением откажет."""

    def __init__(self) -> None:
        self.types = [PartnerType(1, "ИП"), PartnerType(2, "ООО")]
        self.items = [PartnerListItem(1, "ООО", "Вектор", "7701234567", "Иванов Иван Иванович",
                                      "+79991112233", 5, 10)]
        self.records = {
            1: PartnerData(type_id=2, partner_name="Вектор", inn="7701234567", email="vector@mail.ru",
                           rating=5, address="г. Москва", director="Иванов Иван Иванович",
                           phone="+79991112233"),
        }
        self.sales_by_partner = {
            1: [
                SaleRecord("Ноутбук Pro", date(2023, 10, 25), 2),
                SaleRecord("Монитор 27\"", date(2023, 10, 20), 10),
            ],
        }
        self.product_type_list = [ProductType(1, "Ноутбуки", Decimal("2.35"))]
        self.material_type_list = [MaterialType(1, "Стекло", Decimal("0.10"))]
        self.created: list[PartnerData] = []
        self.updated: list[tuple[int, PartnerData]] = []
        self.searches: list[str] = []
        self.errors: dict[str, Exception] = {}

    def _fail(self, method: str) -> None:
        if method in self.errors:
            raise self.errors[method]

    def partner_types(self) -> list[PartnerType]:
        self._fail("partner_types")
        return self.types

    def partners(self, search: str = "") -> list[PartnerListItem]:
        self._fail("partners")
        self.searches.append(search)
        return [item for item in self.items if search.lower() in item.partner_name.lower()]

    def load(self, partner_id: int) -> PartnerData:
        self._fail("load")
        if partner_id not in self.records:
            raise partner_not_found()
        return self.records[partner_id]

    def sales(self, partner_id: int) -> list[SaleRecord]:
        self._fail("sales")
        return self.sales_by_partner.get(partner_id, [])

    def product_types(self) -> list[ProductType]:
        self._fail("product_types")
        return self.product_type_list

    def material_types(self) -> list[MaterialType]:
        self._fail("material_types")
        return self.material_type_list

    def product_coefficient(self, product_type_id: int) -> Decimal | None:
        self._fail("product_coefficient")
        return {item.product_type_id: item.coefficient for item in self.product_type_list}.get(product_type_id)

    def defect_percent(self, material_type_id: int) -> Decimal | None:
        self._fail("defect_percent")
        return {item.material_type_id: item.defect_percent for item in self.material_type_list}.get(material_type_id)

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
