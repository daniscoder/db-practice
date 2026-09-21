"""Задание 3: запросы к базе на тестовых данных из seed.sql.

Автор: Danis Arslanov

Каждый тест работает в своей транзакции, которая откатывается после него,
поэтому добавленные и измененные партнеры в базе не остаются.
"""

from dataclasses import replace

import pytest

import db
from db import DuplicateEmailError, PartnerData, PartnerNotFoundError, UnknownPartnerTypeError

EXPECTED_DISCOUNTS = {
    "Быстрый Путь": 5,
    "Дом и Сад": 15,
    "Логистик-Экспресс": 0,
    "Смирнов А.В.": 0,
    "Строймаркет": 10,
}


def type_id(connection, type_name: str) -> int:
    return next(t.type_id for t in db.fetch_partner_types(connection) if t.type_name == type_name)


def partner_id(connection, company_name: str) -> int:
    return next(p.partner_id for p in db.fetch_partners(connection) if p.company_name == company_name)


def new_partner(connection) -> PartnerData:
    return PartnerData(type_id=type_id(connection, "ООО"), company_name="Новый партнер",
                       director="Орлов Олег Олегович", phone="+79990001122",
                       email="new@partner.ru", address="г. Казань", rating=3)


def test_types_sorted(db_conn):
    names = [t.type_name for t in db.fetch_partner_types(db_conn)]
    assert names == sorted(names)
    assert len(names) == 5


def test_registry_with_discounts(db_conn):
    discounts = {p.company_name: p.discount for p in db.fetch_partners(db_conn)}
    assert discounts == EXPECTED_DISCOUNTS


def test_fetch_partner(db_conn):
    partner = db.fetch_partner(db_conn, partner_id(db_conn, "Строймаркет"))
    assert partner.email == "sales@stroymarket.ru"
    assert partner.type_id == type_id(db_conn, "ПАО")


def test_fetch_missing_partner(db_conn):
    with pytest.raises(PartnerNotFoundError):
        db.fetch_partner(db_conn, -1)


def test_insert_partner(db_conn):
    data = new_partner(db_conn)
    new_id = db.insert_partner(db_conn, data)
    assert db.fetch_partner(db_conn, new_id) == data
    assert "Новый партнер" in [p.company_name for p in db.fetch_partners(db_conn)]


def test_update_partner(db_conn):
    existing_id = partner_id(db_conn, "Быстрый Путь")
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
    existing_id = partner_id(db_conn, "Быстрый Путь")
    with pytest.raises(UnknownPartnerTypeError):
        db.update_partner(db_conn, existing_id, replace(new_partner(db_conn), type_id=-1))


def test_insert_duplicate_email(db_conn):
    with pytest.raises(DuplicateEmailError, match="info@logex.ru"):
        db.insert_partner(db_conn, replace(new_partner(db_conn), email="info@logex.ru"))


def test_update_duplicate_email(db_conn):
    existing_id = partner_id(db_conn, "Строймаркет")
    changed = replace(db.fetch_partner(db_conn, existing_id), email="info@logex.ru")
    with pytest.raises(DuplicateEmailError):
        db.update_partner(db_conn, existing_id, changed)


class NoCommit:
    """Отдает тестовое подключение без фиксации: все откатится после теста."""

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self.connection

    def __exit__(self, *exc_info):
        return False


def test_store_round_trip(db_conn, monkeypatch):
    monkeypatch.setattr(db, "connect", lambda: NoCommit(db_conn))
    store = db.PartnerStore()
    assert len(store.partner_types()) == 5
    data = new_partner(db_conn)
    new_id = store.create(data)
    store.update(new_id, replace(data, rating=7))
    assert store.load(new_id).rating == 7
    assert new_id in [p.partner_id for p in store.partners()]
