"""Расчет количества материала для производства партии продукции.

Автор: Danis Arslanov

Порядок расчета по ТЗ:
1. базовый расход на единицу = param_1 * param_2 * коэффициент типа продукции;
2. чистый расход = базовый расход на единицу * quantity;
3. расход с учетом брака = чистый расход * (1 + процент брака материала / 100);
4. результат округляется до целого вверх.
"""

import logging
from collections.abc import Mapping
from decimal import ROUND_CEILING, Decimal

INVALID_RESULT = -1

log = logging.getLogger(__name__)


class MaterialCalculator:
    """Расчет материала по справочникам коэффициентов типов продукции и
    процентов брака материалов.

    Справочники передаются снаружи: в приложении они прочитаны из базы, в
    тестах это готовые словари-заглушки. Сам расчет к базе не привязан.
    """

    def __init__(self, product_coefficients: Mapping[int, Decimal],
                 defect_percents: Mapping[int, Decimal]) -> None:
        self._product_coefficients = product_coefficients
        self._defect_percents = defect_percents

    def calculate(self, product_type_id: int, material_type_id: int, quantity: int,
                  param_1: float, param_2: float) -> int:
        """Материал на партию с учетом брака, целым числом вверх.

        При несуществующих типах, количестве не больше нуля или параметрах не
        больше нуля возвращает -1, а не бросает исключение.
        """
        coefficient = lookup(self._product_coefficients, product_type_id)
        defect_percent = lookup(self._defect_percents, material_type_id)
        if coefficient is None or defect_percent is None:
            log.warning("Расчет материалов: нет типа продукции %r или типа материала %r",
                        product_type_id, material_type_id)
            return INVALID_RESULT
        # bool в Python - тоже int, но «True штук» продукции - ошибка данных.
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            log.warning("Расчет материалов: неверное количество продукции %r", quantity)
            return INVALID_RESULT
        size_1 = to_positive_decimal(param_1)
        size_2 = to_positive_decimal(param_2)
        if size_1 is None or size_2 is None:
            log.warning("Расчет материалов: неверные параметры продукции %r и %r", param_1, param_2)
            return INVALID_RESULT
        # Расчет в Decimal, а не во float: во float 0.1 + 0.2 != 0.3, и
        # округление вверх от 12.000000000000002 дало бы лишнюю единицу материала.
        base_per_unit = size_1 * size_2 * coefficient
        net_total = base_per_unit * quantity
        total_with_defect = net_total * (1 + defect_percent / 100)
        return int(total_with_defect.to_integral_value(rounding=ROUND_CEILING))


def lookup(table: Mapping[int, Decimal], type_id: object) -> Decimal | None:
    """Значение справочника по id типа; None, если такого типа нет."""
    if isinstance(type_id, bool) or not isinstance(type_id, int):
        return None
    value = table.get(type_id)
    if value is None:
        return None
    return Decimal(str(value))


def to_positive_decimal(value: object) -> Decimal | None:
    """Параметр изделия как Decimal; None, если это не конечное положительное число."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    # Через str: Decimal(0.1) дал бы 0.1000000000000000055..., а Decimal("0.1") ровно 0.1.
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        return None
    return number
