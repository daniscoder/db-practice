"""Задания 2 и 4: запросы к базе на тестовых данных из sql/seed.sql.

Автор: Danis Arslanov

Объемы в seed.sql подобраны точно на границы скидок, а один партнер
заведен вовсе без продаж, чтобы проверить случай SUM(quantity) IS NULL.
"""

import pytest

import db

EXPECTED_TOTALS = {
    "Быстрый Путь": (10_000, 5),
    "Дом и Сад": (300_000, 15),
    "Логистик-Экспресс": (9_999, 0),
    "Смирнов А.В.": (0, 0),
    "Строймаркет": (50_000, 10),
}


def partner_id_by_name(connection, company_name: str) -> int:
    partners = db.fetch_partners_with_discounts(connection)
    return next(p.partner_id for p in partners if p.company_name == company_name)


def test_all_partners_with_discounts(connection):
    partners = db.fetch_partners_with_discounts(connection)
    actual = {p.company_name: (p.total_quantity, p.discount) for p in partners}
    assert actual == EXPECTED_TOTALS


def test_partners_sorted_by_name(connection):
    names = [p.company_name for p in db.fetch_partners_with_discounts(connection)]
    assert names == sorted(names)


def test_total_quantity_of_partner(connection):
    partner_id = partner_id_by_name(connection, "Дом и Сад")
    assert db.fetch_partner_total_quantity(connection, partner_id) == 300_000


def test_total_quantity_is_none_without_sales(connection):
    partner_id = partner_id_by_name(connection, "Смирнов А.В.")
    assert db.fetch_partner_total_quantity(connection, partner_id) is None


def test_partner_with_discount(connection):
    partner_id = partner_id_by_name(connection, "Строймаркет")
    partner = db.fetch_partner_with_discount(connection, partner_id)
    assert partner.type_name == "ПАО"
    assert partner.total_quantity == 50_000
    assert partner.discount == 10


def test_partner_without_sales_gets_zero(connection):
    partner_id = partner_id_by_name(connection, "Смирнов А.В.")
    partner = db.fetch_partner_with_discount(connection, partner_id)
    assert partner.total_quantity == 0
    assert partner.discount == 0
    assert partner.phone is None


def test_missing_partner_total_raises(connection):
    with pytest.raises(LookupError):
        db.fetch_partner_total_quantity(connection, -1)


def test_missing_partner_raises(connection):
    with pytest.raises(LookupError):
        db.fetch_partner_with_discount(connection, -1)
