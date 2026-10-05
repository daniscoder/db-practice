"""Расчет сырья на партию продукции с учетом брака.

Автор: Danis Arslanov

Расход = ⌈Количество * Параметр1 * Параметр2 * Коэффициент типа продукции
          * (1 + Процент брака / 100)⌉
"""

import logging
from decimal import ROUND_CEILING, Decimal

INVALID_RESULT = -1

log = logging.getLogger(__name__)


class MaterialCalculator:
    """Расчет по справочникам типов продукции и материалов.

    references - источник справочников с методами product_coefficient(id) и
    defect_percent(id), которые возвращают значение или None, если такого
    типа нет. В приложении это CrmStore из db.py, и каждый расчет делает
    запросы к таблицам product_types и material_types. В модульных тестах -
    заглушка на словарях.
    """

    def __init__(self, references) -> None:
        self._references = references

    def calculate(self, product_type_id: int, material_type_id: int, quantity: int,
                  param_1: float, param_2: float) -> int:
        """Количество сырья целым числом, округленным вверх.

        При несуществующих типах, количестве не больше нуля или параметрах не
        больше нуля возвращает -1, а не бросает исключение. Сбой самой базы
        -1 не маскируется: это не ошибка ввода, и окно сообщает о нем отдельно.
        """
        if not is_positive_int(product_type_id) or not is_positive_int(material_type_id):
            log.warning("Расчет материалов: неверный id типа продукции %r или типа материала %r",
                        product_type_id, material_type_id)
            return INVALID_RESULT
        if not is_positive_int(quantity):
            log.warning("Расчет материалов: неверное количество продукции %r", quantity)
            return INVALID_RESULT
        size_1 = to_positive_decimal(param_1)
        size_2 = to_positive_decimal(param_2)
        if size_1 is None or size_2 is None:
            log.warning("Расчет материалов: неверные параметры продукции %r и %r", param_1, param_2)
            return INVALID_RESULT
        # Ввод проверен до запросов: на заведомо неверных данных база не нужна.
        coefficient = self._references.product_coefficient(product_type_id)
        defect_percent = self._references.defect_percent(material_type_id)
        if coefficient is None or defect_percent is None:
            log.warning("Расчет материалов: нет типа продукции %r или типа материала %r",
                        product_type_id, material_type_id)
            return INVALID_RESULT
        # Расчет в Decimal, а не во float: во float 0.1 * 3 дает 0.30000000000000004,
        # и округление вверх добавило бы лишнюю единицу сырья там, где ее нет.
        total = quantity * size_1 * size_2 * to_decimal(coefficient) * (1 + to_decimal(defect_percent) / 100)
        # ROUND_CEILING - строго вверх, даже 6.001 дает 7: сырья на партию
        # должно хватить, недостающая доля единицы - это остановка производства.
        return int(total.to_integral_value(rounding=ROUND_CEILING))


def is_positive_int(value: object) -> bool:
    """Целое число больше нуля. bool в Python - тоже int, но «True штук» - ошибка данных."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def to_decimal(value: object) -> Decimal:
    # Через str: Decimal(0.1) дал бы 0.1000000000000000055..., а Decimal("0.1") ровно 0.1.
    return Decimal(str(value))


def to_positive_decimal(value: object) -> Decimal | None:
    """Параметр продукции как Decimal; None, если это не конечное положительное число."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    number = to_decimal(value)
    if not number.is_finite() or number <= 0:
        return None
    return number
