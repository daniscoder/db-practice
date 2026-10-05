"""Задание 3: окно расчета материалов.

Автор: Danis Arslanov
"""

import psycopg
import pytest
from PySide6.QtWidgets import QPushButton

from material_calculator_window import (
    DATABASE_FAILED_TEXT,
    INVALID_INPUT_TEXT,
    INVALID_RESULT_TEXT,
    WINDOW_TITLE,
    MaterialCalculatorWindow,
    parse_integer,
    parse_number,
)


def make_window(store) -> MaterialCalculatorWindow:
    return MaterialCalculatorWindow(store, store.product_type_list, store.material_type_list)


def run_calculation(window: MaterialCalculatorWindow, quantity: str, param_1: str, param_2: str) -> str:
    window.quantity_edit.setText(quantity)
    window.param_1_edit.setText(param_1)
    window.param_2_edit.setText(param_2)
    window.findChild(QPushButton, "calculateButton").click()
    return window.result_label.text()


def test_title_and_lists(qt_app, fake_store):
    window = make_window(fake_store)
    assert window.windowTitle() == WINDOW_TITLE
    assert window.product_type_combo.currentText() == "Ноутбуки"
    assert window.material_type_combo.currentText() == "Стекло"


def test_result_is_shown(qt_app, fake_store, shown_dialogs):
    # 10 * 2 * 3 * 2.35 = 141, * 1.001 = 141.141, вверх - 142
    assert run_calculation(make_window(fake_store), "10", "2", "3") == "Необходимо сырья: 142 ед."
    assert shown_dialogs.errors == []


def test_decimal_comma_accepted(qt_app, fake_store, shown_dialogs):
    assert run_calculation(make_window(fake_store), "10", "2,0", "3") == "Необходимо сырья: 142 ед."


def test_large_result_has_digit_groups(qt_app, fake_store, shown_dialogs):
    # 14.1 * 1000 = 14100, * 1.001 = 14114.1, вверх - 14115
    assert run_calculation(make_window(fake_store), "1000", "2", "3") == "Необходимо сырья: 14 115 ед."


@pytest.mark.parametrize(
    ("quantity", "param_1", "param_2"),
    [("10", "-2", "3"), ("10", "2", "-3"), ("0", "2", "3"), ("десять", "2", "3"), ("10", "", "3")],
)
def test_invalid_input_shows_guide(qt_app, fake_store, shown_dialogs, quantity, param_1, param_2):
    assert run_calculation(make_window(fake_store), quantity, param_1, param_2) == INVALID_RESULT_TEXT
    assert shown_dialogs.errors == [INVALID_INPUT_TEXT]
    assert "Как исправить" in INVALID_INPUT_TEXT


def test_empty_references_show_guide(qt_app, fake_store, shown_dialogs):
    fake_store.product_type_list = []
    run_calculation(make_window(fake_store), "10", "2", "3")
    assert shown_dialogs.errors == [INVALID_INPUT_TEXT]


def test_database_error_during_calculation(qt_app, fake_store, shown_dialogs):
    window = make_window(fake_store)
    fake_store.errors["product_coefficient"] = psycopg.OperationalError("сервер не отвечает")
    assert run_calculation(window, "10", "2", "3") == DATABASE_FAILED_TEXT
    assert "прочитать справочники для расчета" in shown_dialogs.errors[0]


@pytest.mark.parametrize(("text", "expected"), [("12", 12), (" 7 ", 7), ("2.5", None), ("", None)])
def test_parse_integer(text, expected):
    assert parse_integer(text) == expected


@pytest.mark.parametrize(("text", "expected"), [("2,5", 2.5), ("3", 3.0), ("abc", None)])
def test_parse_number(text, expected):
    assert parse_number(text) == expected
