"""Скидка в реестре: границы из практики 14.09 и отказ на отрицательном объеме.

Автор: Danis Arslanov
"""

import pytest

from discount import calculate_partner_discount


@pytest.mark.parametrize(
    ("total_quantity", "expected_discount"),
    [(None, 0), (9_999, 0), (10_000, 5), (50_000, 10), (300_000, 15)],
)
def test_discount_boundaries(total_quantity, expected_discount):
    assert calculate_partner_discount(total_quantity) == expected_discount


def test_negative_quantity_is_rejected():
    with pytest.raises(ValueError):
        calculate_partner_discount(-1)
