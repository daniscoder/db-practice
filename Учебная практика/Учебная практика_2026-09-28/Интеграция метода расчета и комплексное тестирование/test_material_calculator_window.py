"""Задание 3: метод расчета в окне и реакция на неверный ввод.

Автор: Danis Arslanov
"""

from decimal import Decimal

import pytest
from PySide6.QtWidgets import QPushButton

from db import MaterialType, ProductType
from material_calculator_window import (
    INVALID_INPUT_TEXT,
    WINDOW_TITLE,
    MaterialCalculatorWindow,
    parse_integer,
    parse_number,
)

PRODUCT_TYPES = [ProductType(1, "Порошковые средства", Decimal("2.35"))]
MATERIAL_TYPES = [MaterialType(1, "Картон", Decimal("0.10"))]


def make_window(product_types=PRODUCT_TYPES, material_types=MATERIAL_TYPES) -> MaterialCalculatorWindow:
    return MaterialCalculatorWindow(product_types, material_types)


def run_calculation(window: MaterialCalculatorWindow, quantity: str, param_1: str, param_2: str) -> str:
    window.quantity_edit.setText(quantity)
    window.param_1_edit.setText(param_1)
    window.param_2_edit.setText(param_2)
    window.findChild(QPushButton, "calculateButton").click()
    return window.result_label.text()


def test_title_and_lists(qt_app):
    window = make_window()
    assert window.windowTitle() == WINDOW_TITLE
    assert window.product_type_combo.currentText() == "Порошковые средства (коэффициент 2.35)"
    assert window.material_type_combo.currentText() == "Картон (брак 0.10%)"


def test_result_is_shown(qt_app, shown_dialogs):
    window = make_window()
    # 2 * 3 * 2.35 = 14.1 на единицу, * 10 = 141, * 1.001 = 141.141, вверх - 142
    assert run_calculation(window, "10", "2", "3") == "Необходимо материала: 142 ед."
    assert shown_dialogs.errors == []


def test_decimal_comma_accepted(qt_app, shown_dialogs):
    window = make_window()
    assert run_calculation(window, "10", "2,0", "3") == "Необходимо материала: 142 ед."


def test_large_result_has_digit_groups(qt_app, shown_dialogs):
    window = make_window()
    # 14.1 * 1000 = 14100, * 1.001 = 14114.1, вверх - 14115
    assert run_calculation(window, "1000", "2", "3") == "Необходимо материала: 14 115 ед."


@pytest.mark.parametrize(
    ("quantity", "param_1", "param_2"),
    [
        ("10", "-2", "3"),
        ("10", "2", "-3"),
        ("0", "2", "3"),
        ("-1", "2", "3"),
        ("десять", "2", "3"),
        ("10", "", "3"),
    ],
)
def test_invalid_input_shows_error(qt_app, shown_dialogs, quantity, param_1, param_2):
    window = make_window()
    result = run_calculation(window, quantity, param_1, param_2)
    assert result == "Расчет невозможен: проверьте введенные данные"
    assert shown_dialogs.errors == [INVALID_INPUT_TEXT]


def test_missing_type_shows_error(qt_app, shown_dialogs):
    window = make_window(product_types=[], material_types=[])
    run_calculation(window, "10", "2", "3")
    assert shown_dialogs.errors == [INVALID_INPUT_TEXT]


@pytest.mark.parametrize(("text", "expected"), [("12", 12), (" 7 ", 7), ("2.5", None), ("", None)])
def test_parse_integer(text, expected):
    assert parse_integer(text) == expected


@pytest.mark.parametrize(("text", "expected"), [("2,5", 2.5), ("3", 3.0), ("abc", None)])
def test_parse_number(text, expected):
    assert parse_number(text) == expected
