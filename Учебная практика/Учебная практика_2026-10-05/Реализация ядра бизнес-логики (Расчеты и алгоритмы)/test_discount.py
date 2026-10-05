"""Задание 2: границы накопительной скидки.

Автор: Danis Arslanov
"""

import pytest

from discount import calculate_discount


@pytest.mark.parametrize(
    ("total_quantity", "expected_discount"),
    [
        (0, 0),
        (9_999, 0),
        (10_000, 5),
        (49_999, 5),
        (50_000, 10),
        (299_999, 10),
        (300_000, 15),
        (1_000_000, 15),
    ],
)
def test_discount_boundaries(total_quantity, expected_discount):
    assert calculate_discount(total_quantity) == expected_discount


def test_negative_quantity_is_rejected():
    with pytest.raises(ValueError, match="отрицательным"):
        calculate_discount(-1)
