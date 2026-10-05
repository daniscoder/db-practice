"""Задание 2: оформление кода по правилам ТЗ.

Автор: Danis Arslanov

Правила «строго одна команда на строку» и «идентификаторы в выбранном
стиле» (snake_case для функций и переменных, CamelCase для классов,
UPPER_CASE для констант) проверяются по дереву разбора каждого модуля
практики, а не на глаз.
"""

import ast
import re
from pathlib import Path

import pytest

PRACTICE_DIR = Path(__file__).resolve().parent.parent
SOURCE_FILES = sorted(
    path for path in PRACTICE_DIR.rglob("*.py")
    if not any(part.startswith((".", "_")) for part in path.relative_to(PRACTICE_DIR).parts[:-1])
)

# Методы Qt, которые переопределяются: их имена задает библиотека, а не мы.
QT_OVERRIDES = {"mousePressEvent", "mouseDoubleClickEvent"}
SNAKE_CASE = re.compile(r"^_{0,2}[a-z][a-z0-9_]*$")
UPPER_CASE = re.compile(r"^[A-Z][A-Z0-9_]*$")
CAMEL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")


def module_id(path: Path) -> str:
    return path.relative_to(PRACTICE_DIR).as_posix()


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_all_modules_found():
    names = {path.name for path in SOURCE_FILES}
    assert {"etl.py", "db.py", "discount.py", "material_calculator.py", "main.py", "dialogs.py"} <= names


@pytest.mark.parametrize("path", SOURCE_FILES, ids=module_id)
def test_one_statement_per_line(path):
    # Два оператора с одной строки начала - это «a = 1; b = 2» или «if x: return».
    lines = [node.lineno for node in ast.walk(parse(path)) if isinstance(node, ast.stmt)]
    repeated = sorted({line for line in lines if lines.count(line) > 1})
    assert repeated == []


@pytest.mark.parametrize("path", SOURCE_FILES, ids=module_id)
def test_naming(path):
    wrong = []
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.ClassDef) and not CAMEL_CASE.match(node.name):
            wrong.append(node.name)
        elif isinstance(node, ast.FunctionDef) and node.name not in QT_OVERRIDES and not SNAKE_CASE.match(node.name):
            wrong.append(node.name)
        elif isinstance(node, ast.arg) and not SNAKE_CASE.match(node.arg):
            wrong.append(node.arg)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if not (SNAKE_CASE.match(node.id) or UPPER_CASE.match(node.id)):
                wrong.append(node.id)
    assert wrong == []
