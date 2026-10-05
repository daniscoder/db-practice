"""Задание 4: модульные тесты метода расчета материалов.

Автор: Danis Arslanov

Справочники здесь - заглушка на словарях вместо базы: модульный тест
проверяет сам расчет и не зависит от сервера. С настоящей базой метод
проверяет test_db.py задания 2.
"""

import logging
import math
from decimal import Decimal

import pytest

from material_calculator import INVALID_RESULT, MaterialCalculator


class FakeReferences:
    """Справочники типов продукции и материалов; считает обращения к ним."""

    def __init__(self) -> None:
        self.coefficients = {1: Decimal("2.35"), 2: Decimal("1.50")}
        self.defect_percents = {1: Decimal("0.10"), 2: Decimal("0.95"), 3: Decimal("0")}
        self.queries = 0

    def product_coefficient(self, product_type_id: int) -> Decimal | None:
        self.queries += 1
        return self.coefficients.get(product_type_id)

    def defect_percent(self, material_type_id: int) -> Decimal | None:
        self.queries += 1
        return self.defect_percents.get(material_type_id)


@pytest.fixture
def references() -> FakeReferences:
    return FakeReferences()


@pytest.fixture
def calculator(references) -> MaterialCalculator:
    return MaterialCalculator(references)


def test_standard_calculation(calculator):
    """Тест 1. Базовый расчет: 10 * 2 * 3 * 2.35 = 141, * 1.001 = 141.141, вверх - 142."""
    assert calculator.calculate(1, 1, 10, 2.0, 3.0) == 142


def test_fraction_rounds_up(calculator):
    """Тест 2. Округление строго вверх: 1 * 2 * 2 * 1.5 * 1.0095 = 6.057 дает 7, а не 6."""
    assert calculator.calculate(2, 2, 1, 2.0, 2.0) == 7


@pytest.mark.parametrize(
    ("product_type_id", "material_type_id"),
    [(99, 1), (1, 99), (99, 99), (0, 1), (-1, 1), (None, 1), ("1", 1), (True, 1)],
)
def test_unknown_type_id(calculator, product_type_id, material_type_id):
    """Тест 3. Несуществующий или не числовой id типа продукции или материала."""
    assert calculator.calculate(product_type_id, material_type_id, 10, 2.0, 3.0) == INVALID_RESULT


@pytest.mark.parametrize(("param_1", "param_2"), [(-2.0, 3.0), (2.0, -3.0), (-2.0, -3.0)])
def test_negative_params(calculator, param_1, param_2):
    """Тест 4. Отрицательные параметры продукции."""
    assert calculator.calculate(1, 1, 10, param_1, param_2) == INVALID_RESULT


@pytest.mark.parametrize("quantity", [0, -1, -100])
def test_zero_or_negative_quantity(calculator, quantity):
    """Тест 5. Количество продукции ноль или меньше."""
    assert calculator.calculate(1, 1, quantity, 2.0, 3.0) == INVALID_RESULT


def test_whole_result_is_not_raised(calculator):
    """Тест 6. Ровно 6 при браке 0% остается 6: округление вверх не добавляет лишнюю единицу."""
    assert calculator.calculate(2, 3, 1, 2.0, 2.0) == 6


def test_float_noise_does_not_add_unit(calculator):
    """Тест 7. Во float 20 * 0.1 * 3 * 1.5 = 9.000000000000002, и округление вверх дало бы 10."""
    assert calculator.calculate(2, 3, 20, 0.1, 3.0) == 9


@pytest.mark.parametrize(
    ("param_1", "param_2"),
    [(0, 3.0), (2.0, 0), (math.nan, 3.0), (math.inf, 3.0), (None, 3.0), ("2", 3.0), (True, 3.0)],
)
def test_other_invalid_params(calculator, param_1, param_2):
    """Тест 8. Ноль, NaN, бесконечность и не числа - тоже не положительные размеры."""
    assert calculator.calculate(1, 1, 10, param_1, param_2) == INVALID_RESULT


@pytest.mark.parametrize("quantity", [2.5, None, "10", True])
def test_non_integer_quantity(calculator, quantity):
    """Тест 9. Дробное, пустое, строковое и логическое количество."""
    assert calculator.calculate(1, 1, quantity, 2.0, 3.0) == INVALID_RESULT


def test_invalid_input_does_not_query_references(calculator, references):
    """Тест 10. На заведомо неверном вводе к справочникам не обращаются."""
    calculator.calculate(1, 1, 0, 2.0, 3.0)
    calculator.calculate(1, 1, 10, -2.0, 3.0)
    assert references.queries == 0


def test_reference_values_may_be_float(references):
    """Тест 11. Справочник со значениями float считается так же точно."""
    references.coefficients = {1: 2.35}
    references.defect_percents = {1: 0.1}
    assert MaterialCalculator(references).calculate(1, 1, 10, 2.0, 3.0) == 142


def test_decimal_and_int_params(calculator):
    """Тест 12. Параметры Decimal и int."""
    assert calculator.calculate(1, 1, 10, Decimal("2"), 3) == 142


def test_rejection_is_logged(calculator, caplog):
    """Тест 13. Отказ записывается в журнал."""
    caplog.set_level(logging.WARNING)
    calculator.calculate(99, 1, 10, 2.0, 3.0)
    assert "нет типа продукции 99" in caplog.text
