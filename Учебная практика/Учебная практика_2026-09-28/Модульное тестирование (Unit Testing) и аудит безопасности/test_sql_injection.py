"""Задание 4: аудит защиты от SQL-инъекций.

Автор: Danis Arslanov

Проверка в два слоя. По коду: запросы к базе есть только в db.py, и текст
каждого - готовая строка-константа, без f-строк, склеек и format. По базе:
строка с попыткой инъекции сохраняется и читается как обычный текст.
"""

import ast
from pathlib import Path

import psycopg
import pytest

import db
from db import PartnerData

PRACTICE_DIR = Path(__file__).resolve().parent.parent
APP_FILES = sorted(
    path for path in PRACTICE_DIR.rglob("*.py")
    if not path.name.startswith("test_") and path.name != "conftest.py"
    and "__pycache__" not in path.parts
)
INJECTION = "Робертс'); DROP TABLE partners; --"


def execute_calls(tree: ast.Module) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "execute"
    ]


def test_queries_only_in_db_module():
    with_queries = [path.name for path in APP_FILES if execute_calls(ast.parse(path.read_text(encoding="utf-8")))]
    assert with_queries == ["db.py"]


def test_query_text_is_constant():
    tree = ast.parse(Path(db.__file__).read_text(encoding="utf-8"))
    string_constants = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for target in node.targets
    }
    calls = execute_calls(tree)
    built_queries = [ast.unparse(call.args[0]) for call in calls
                     if not (isinstance(call.args[0], ast.Name) and call.args[0].id in string_constants)]
    # Без запросов проверка прошла бы впустую: убеждаемся, что она их нашла.
    assert calls
    assert built_queries == []


def test_injection_text_is_stored_as_text(db_conn):
    data = PartnerData(type_id=db.fetch_partner_types(db_conn)[0].type_id, company_name=INJECTION,
                       director=None, phone=None, email="bobby@tables.ru", address="1' OR '1'='1", rating=0)
    new_id = db.insert_partner(db_conn, data)
    assert db.fetch_partner(db_conn, new_id) == data
    assert INJECTION in [partner.company_name for partner in db.fetch_partners(db_conn)]


def test_injection_in_id_is_rejected(db_conn):
    # Строка целиком уходит как значение параметра: СУБД отвергает ее как
    # неверное число, а не выполняет «OR 1=1» и не отдает чужие продажи.
    with pytest.raises(psycopg.Error):
        db.fetch_partner_sales(db_conn, "1 OR 1=1")
