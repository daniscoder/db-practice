"""Задание 4: аудит защиты от SQL-инъекций.

Автор: Danis Arslanov

Проверка в два слоя. По коду: запросы к базе выполняются только в db.py и
etl.py, ни один текст запроса не собирается склейкой, f-строкой, format или
join, а каждая строка SQL в модулях - готовая константа. По базе: строки с
попыткой инъекции в поиске и в полях карточки сохраняются и ищутся как
обычный текст.
"""

import ast
import re
from dataclasses import replace
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
SQL_START = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|COPY|WITH)\b", re.IGNORECASE)
QUERY_METHODS = {"execute", "copy"}
INJECTION = "Робертс'); DROP TABLE partners; --"


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def query_calls(tree: ast.Module) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in QUERY_METHODS and node.args
    ]


def is_built_string(node: ast.expr) -> bool:
    """Текст, собранный в момент выполнения: f-строка, склейка, % или .format/.join."""
    if isinstance(node, (ast.JoinedStr, ast.BinOp)):
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"format", "join"}


def test_queries_only_in_data_modules():
    with_queries = sorted(path.name for path in APP_FILES if query_calls(parse(path)))
    assert with_queries == ["db.py", "etl.py"]


@pytest.mark.parametrize("path", [path for path in APP_FILES if path.name in {"db.py", "etl.py"}], ids=lambda p: p.name)
def test_query_text_is_never_built(path):
    calls = query_calls(parse(path))
    built = [ast.unparse(call) for call in calls if is_built_string(call.args[0])]
    # Без запросов проверка прошла бы впустую: убеждаемся, что она их нашла.
    assert calls
    assert built == []


@pytest.mark.parametrize("path", APP_FILES, ids=lambda p: p.name)
def test_sql_constants_are_plain_strings(path):
    # f-строка с SQL внутри - это готовая к инъекции склейка, даже если до
    # execute она доходит через переменную.
    formatted_sql = [
        ast.unparse(node) for node in ast.walk(parse(path))
        if isinstance(node, ast.JoinedStr)
        and any(isinstance(part, ast.Constant) and SQL_START.match(str(part.value)) for part in node.values)
    ]
    assert formatted_sql == []


def test_injection_in_search_is_plain_text(db_conn):
    found = db.fetch_partners(db_conn, "' OR '1'='1")
    assert found == []
    assert db.fetch_partners(db_conn, "%'; DROP TABLE partners; --") == []
    assert db.fetch_partners(db_conn, "")


def test_injection_in_card_fields_is_stored_as_text(db_conn):
    data = PartnerData(type_id=db.fetch_partner_types(db_conn)[0].type_id, partner_name=INJECTION,
                       inn="1234567890", email="bobby@tables.ru", rating=0,
                       address="1' OR '1'='1", director="'; DELETE FROM partners; --", phone=None)
    new_id = db.insert_partner(db_conn, data)
    assert db.fetch_partner(db_conn, new_id) == data
    db.update_partner(db_conn, new_id, replace(data, address="'); TRUNCATE sales_history; --"))
    assert db.fetch_partner(db_conn, new_id).address == "'); TRUNCATE sales_history; --"
    assert [partner.partner_name for partner in db.fetch_partners(db_conn, "DROP TABLE")] == [INJECTION]


def test_injection_in_id_is_rejected(db_conn):
    # Строка целиком уходит как значение параметра: СУБД отвергает ее как
    # неверное число, а не выполняет «OR 1=1» и не отдает чужие продажи.
    with pytest.raises(psycopg.Error):
        db.fetch_partner_sales(db_conn, "1 OR 1=1")
