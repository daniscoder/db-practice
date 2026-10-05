"""Задание 2: запросы к базе на данных, загруженных etl.py.

Автор: Danis Arslanov

Каждый тест работает в своей транзакции, которая откатывается после него,
поэтому добавленные и измененные партнеры в базе не остаются.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from psycopg import errors

import db
from db import DuplicateValueError, PartnerData, PartnerNotFoundError, UnknownPartnerTypeError
from material_calculator import INVALID_RESULT, MaterialCalculator

IMPORTED_PARTNERS = {"Альфа", "Вектор", "Петров А.В.", "Сидоров И.И.", "Технолоджис"}


def type_id(connection, type_name: str) -> int:
    return next(t.type_id for t in db.fetch_partner_types(connection) if t.type_name == type_name)


def partner_id(connection, partner_name: str) -> int:
    return next(p.partner_id for p in db.fetch_partners(connection) if p.partner_name == partner_name)


def found_names(connection, search: str) -> set[str]:
    return {p.partner_name for p in db.fetch_partners(connection, search)}


def new_partner(connection) -> PartnerData:
    return PartnerData(type_id=type_id(connection, "ООО"), partner_name="Новый партнер", inn="1234567890",
                       email="new@partner.ru", rating=3, address="г. Казань",
                       director="Орлов Олег Олегович", phone="+79990001122")


def test_types_sorted(db_conn):
    names = [t.type_name for t in db.fetch_partner_types(db_conn)]
    assert names == ["АО", "ЗАО", "ИП", "ОАО", "ООО", "ПАО"]


def test_registry_has_imported_partners(db_conn):
    partners = {p.partner_name: p for p in db.fetch_partners(db_conn)}
    # Сверяются только импортированные: добавленные через приложение законно
    # лежат в базе и проверке мешать не должны.
    assert IMPORTED_PARTNERS <= set(partners)
    assert partners["Вектор"].type_name == "ООО"
    assert partners["Вектор"].inn == "7701234567"


def test_discount_from_sales_in_database(db_conn):
    # В выгрузке у каждого партнера не больше 10 шт., скидка у всех 0%.
    assert {p.discount for p in db.fetch_partners(db_conn) if p.partner_name in IMPORTED_PARTNERS} == {0}
    alpha_id = partner_id(db_conn, "Альфа")
    product_id = db_conn.execute("SELECT MIN(product_id) AS id FROM products").fetchone()["id"]
    db_conn.execute(
        "INSERT INTO sales_history (partner_id, product_id, sale_date, quantity, amount) "
        "VALUES (%(partner_id)s, %(product_id)s, DATE '2023-11-01', 49990, 1)",
        {"partner_id": alpha_id, "product_id": product_id},
    )
    discounts = {p.partner_name: p.discount for p in db.fetch_partners(db_conn)}
    # 10 из выгрузки + 49 990 = 50 000: ровно граница 10%.
    assert discounts["Альфа"] == 10


@pytest.mark.parametrize(
    ("search", "expected"),
    [
        ("вектор", {"Вектор"}),
        ("7802345678", {"Петров А.В."}),
        ("@llc.ru", {"Сидоров И.И."}),
        ("И.И.", {"Сидоров И.И."}),
        ("нет такого", set()),
        ("%", set()),
        ("_", set()),
    ],
)
def test_search(db_conn, search, expected):
    assert found_names(db_conn, search) & IMPORTED_PARTNERS == expected


def test_search_by_director(db_conn):
    db.update_partner(db_conn, partner_id(db_conn, "Альфа"),
                      replace(db.fetch_partner(db_conn, partner_id(db_conn, "Альфа")), director="Орлова Анна"))
    assert found_names(db_conn, "орлова") == {"Альфа"}


def test_like_pattern_escapes_wildcards():
    assert db.like_pattern("100%_\\") == "%100\\%\\_\\\\%"


def test_fetch_partner(db_conn):
    partner = db.fetch_partner(db_conn, partner_id(db_conn, "Технолоджис"))
    assert partner.email == "info@techno.ru"
    assert partner.type_id == type_id(db_conn, "АО")
    assert partner.rating == 0
    assert partner.director is None


def test_fetch_missing_partner(db_conn):
    with pytest.raises(PartnerNotFoundError, match="Как исправить"):
        db.fetch_partner(db_conn, -1)


def test_insert_partner(db_conn):
    data = new_partner(db_conn)
    new_id = db.insert_partner(db_conn, data)
    assert db.fetch_partner(db_conn, new_id) == data
    assert "Новый партнер" in found_names(db_conn, "")


def test_update_partner(db_conn):
    existing_id = partner_id(db_conn, "Вектор")
    changed = replace(db.fetch_partner(db_conn, existing_id), rating=9, address="г. Тверь")
    db.update_partner(db_conn, existing_id, changed)
    assert db.fetch_partner(db_conn, existing_id) == changed


def test_update_missing_partner(db_conn):
    with pytest.raises(PartnerNotFoundError):
        db.update_partner(db_conn, -1, new_partner(db_conn))


def test_insert_unknown_type(db_conn):
    with pytest.raises(UnknownPartnerTypeError):
        db.insert_partner(db_conn, replace(new_partner(db_conn), type_id=-1))


def test_update_unknown_type(db_conn):
    with pytest.raises(UnknownPartnerTypeError):
        db.update_partner(db_conn, partner_id(db_conn, "Вектор"), replace(new_partner(db_conn), type_id=-1))


def test_insert_duplicate_inn(db_conn):
    with pytest.raises(DuplicateValueError, match="ИНН 7701234567"):
        db.insert_partner(db_conn, replace(new_partner(db_conn), inn="7701234567"))


def test_insert_duplicate_email(db_conn):
    with pytest.raises(DuplicateValueError, match="vector@mail.ru"):
        db.insert_partner(db_conn, replace(new_partner(db_conn), email="vector@mail.ru"))


def test_update_duplicate_email(db_conn):
    existing_id = partner_id(db_conn, "Альфа")
    changed = replace(db.fetch_partner(db_conn, existing_id), email="vector@mail.ru")
    with pytest.raises(DuplicateValueError):
        db.update_partner(db_conn, existing_id, changed)


class FailingConnection:
    """Подключение, у которого справочник типов на месте, а запись падает
    на уникальности, не связанной с ИНН и email."""

    def execute(self, query, params=None):
        if query == db.TYPE_EXISTS_QUERY:
            return self
        raise errors.UniqueViolation("duplicate key value violates unique constraint")

    def fetchone(self):
        return {"exists": 1}


def test_other_unique_violation_is_not_disguised():
    with pytest.raises(errors.UniqueViolation):
        db.insert_partner(FailingConnection(), PartnerData(1, "Бета", "1234567890", "b@b.ru", 0, None, None, None))


def test_store_round_trip(db_store):
    assert len(db_store.partner_types()) == 6
    data = PartnerData(type_id=db_store.partner_types()[0].type_id, partner_name="Новый партнер",
                       inn="1234567890", email="new@partner.ru", rating=1,
                       address=None, director=None, phone=None)
    new_id = db_store.create(data)
    db_store.update(new_id, replace(data, rating=7))
    assert db_store.load(new_id).rating == 7
    assert new_id in [p.partner_id for p in db_store.partners("Новый")]
    assert db_store.sales(new_id) == []
    assert len(db_store.product_types()) == 3
    assert len(db_store.material_types()) == 3


def test_partner_sales_joined_with_products(db_conn):
    sales = db.fetch_partner_sales(db_conn, partner_id(db_conn, "Альфа"))
    assert [(s.product_name, s.sale_date, s.quantity) for s in sales] == [('Монитор 27"', date(2023, 10, 28), 10)]


def test_product_types(db_conn):
    types = {t.type_name: t.coefficient for t in db.fetch_product_types(db_conn)}
    assert types == {"Мониторы": Decimal("4.34"), "Ноутбуки": Decimal("2.35"), "Смартфоны": Decimal("1.50")}


def test_material_types(db_conn):
    types = {t.type_name: t.defect_percent for t in db.fetch_material_types(db_conn)}
    assert types == {"Алюминий": Decimal("0.28"), "Пластик": Decimal("0.95"), "Стекло": Decimal("0.10")}


def reference_ids(connection) -> tuple[int, int]:
    product_type = next(t for t in db.fetch_product_types(connection) if t.type_name == "Ноутбуки")
    material_type = next(t for t in db.fetch_material_types(connection) if t.type_name == "Стекло")
    return product_type.product_type_id, material_type.material_type_id


def test_reference_lookups(db_conn):
    product_type_id, material_type_id = reference_ids(db_conn)
    assert db.fetch_product_coefficient(db_conn, product_type_id) == Decimal("2.35")
    assert db.fetch_defect_percent(db_conn, material_type_id) == Decimal("0.10")
    assert db.fetch_product_coefficient(db_conn, -1) is None
    assert db.fetch_defect_percent(db_conn, -1) is None


def test_calculator_reads_references_from_database(db_conn, db_store):
    product_type_id, material_type_id = reference_ids(db_conn)
    calculator = MaterialCalculator(db_store)
    # 10 * 2 * 3 * 2.35 = 141, * 1.001 = 141.141, вверх - 142.
    assert calculator.calculate(product_type_id, material_type_id, 10, 2.0, 3.0) == 142
    assert calculator.calculate(999_999, material_type_id, 10, 2.0, 3.0) == INVALID_RESULT
    assert calculator.calculate(product_type_id, 999_999, 10, 2.0, 3.0) == INVALID_RESULT
