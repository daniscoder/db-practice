"""Задание 1: импорт и очистка выгрузок.

Автор: Danis Arslanov

Импорт в базу идет в транзакции теста и откатывается после него: данные в
базе после прогона остаются прежними.
"""

from datetime import date
from decimal import Decimal

import psycopg
import pytest

import db
import etl
from etl import RAW_DIR, RAW_FILES, RawFileError, decode, read_rows, run_etl

PARTNER_COLUMNS = RAW_FILES[0].columns
PRODUCT_COLUMNS = RAW_FILES[1].columns

CLEAN_PARTNERS = [
    (1, "ООО", "Вектор", "7701234567", "vector@mail.ru"),
    (2, "ИП", "Петров А.В.", "7802345678", "petrov@yandex.ru"),
    (3, "АО", "Технолоджис", "5003456789", "info@techno.ru"),
    (4, "ООО", "Альфа", "7704567890", "alpha@gmail.com"),
    (5, "ИП", "Сидоров И.И.", "7805678901", "sidorov@llc.ru"),
]
CLEAN_PRODUCTS = [
    (101, "Ноутбук Pro", Decimal("75000.00")),
    (102, "Смартфон X", Decimal("45000.50")),
    (103, 'Монитор 27"', Decimal("18200.00")),
]
CLEAN_SALES = [
    (1001, 1, 101, date(2023, 10, 25), 2, Decimal("150000.00")),
    (1002, 2, 102, date(2023, 10, 26), 1, Decimal("45000.50")),
    (1004, 4, 103, date(2023, 10, 28), 10, Decimal("182000.00")),
    (1005, 3, 102, date(2023, 10, 29), 3, Decimal("135001.50")),
    (1006, 5, 103, date(2023, 10, 30), 1, Decimal("18200.00")),
]

PARTNERS_QUERY = """
SELECT p.partner_id, t.type_name, p.partner_name, p.inn, p.email
FROM partners AS p
JOIN partner_types AS t ON t.type_id = p.type_id
ORDER BY p.partner_id
"""
PRODUCTS_QUERY = "SELECT product_id, product_name, price FROM products ORDER BY product_id"
SALES_QUERY = """
SELECT sale_id, partner_id, product_id, sale_date, quantity, amount
FROM sales_history
ORDER BY sale_id
"""


SYNC_SEQUENCES_SQL = """
SELECT setval(pg_get_serial_sequence('partners', 'partner_id'), COALESCE(MAX(partner_id), 0) + 1, false) FROM partners;
SELECT setval(pg_get_serial_sequence('products', 'product_id'), COALESCE(MAX(product_id), 0) + 1, false) FROM products;
SELECT setval(pg_get_serial_sequence('sales_history', 'sale_id'), COALESCE(MAX(sale_id), 0) + 1, false) FROM sales_history;
"""


def table_rows(connection, query: str) -> list[tuple]:
    return [tuple(row.values()) for row in connection.execute(query).fetchall()]


def write_raw_files(directory, partners: str, products: str, sales: str) -> None:
    (directory / "partners_raw.csv").write_text(partners, encoding="utf-8")
    (directory / "products_raw.csv").write_text(products, encoding="utf-8")
    (directory / "sales_history_raw.csv").write_text(sales, encoding="utf-8")


def test_cp1251_file_detected():
    text, encoding = decode((RAW_DIR / "products_raw.csv").read_bytes())
    assert encoding == "cp1251"
    assert "Ноутбук Pro" in text


def test_utf8_file_detected():
    assert decode((RAW_DIR / "partners_raw.csv").read_bytes())[1] == "utf-8"


def test_values_loaded_as_is():
    rows = read_rows(RAW_DIR / "partners_raw.csv", PARTNER_COLUMNS)[1]
    assert rows[0] == (2, ["1", ' ООО "Вектор" ', "7701234567", " vector@mail.ru"])
    assert rows[1][1][1] == "ИП ...Петров  A.B."


def test_quote_inside_unquoted_field_is_kept():
    rows = read_rows(RAW_DIR / "products_raw.csv", PRODUCT_COLUMNS)[1]
    assert rows[2] == (4, ["103", 'Монитор 27"', "18200.0"])


def test_wrong_header_stops_import(tmp_path):
    path = tmp_path / "partners_raw.csv"
    path.write_text("id,name\n1,ООО Вектор\n", encoding="utf-8")
    with pytest.raises(RawFileError, match="ожидались колонки"):
        read_rows(path, PARTNER_COLUMNS)


def test_wrong_field_count_stops_import(tmp_path):
    path = tmp_path / "products_raw.csv"
    path.write_text("product_id,product_name,price\n101,Ноутбук,75000,лишнее\n", encoding="utf-8")
    with pytest.raises(RawFileError, match="строка 2: полей 4"):
        read_rows(path, PRODUCT_COLUMNS)


def test_blank_lines_skipped(tmp_path):
    path = tmp_path / "products_raw.csv"
    path.write_text("product_id,product_name,price\n\n101,Ноутбук,75000\n", encoding="utf-8")
    assert read_rows(path, PRODUCT_COLUMNS)[1] == [(3, ["101", "Ноутбук", "75000"])]


@pytest.fixture
def etl_conn(db_conn):
    """Подключение для импорта. Данные откатываются, а счетчики id - нет:
    setval в etl.sql транзакцией не откатывается. Без выравнивания после
    теста счетчик партнеров встал бы на 6, и приложение, где уже есть
    партнер 6, упало бы на дубле ключа."""
    yield db_conn
    db_conn.rollback()
    db_conn.execute(SYNC_SEQUENCES_SQL)
    db_conn.commit()


@pytest.fixture
def report(etl_conn):
    return run_etl(etl_conn)


def test_loaded_counts(report):
    assert report.loaded == {"partners": 5, "products": 3, "sales_history": 5}
    assert report.encodings == {
        "partners_raw.csv": "utf-8",
        "products_raw.csv": "cp1251",
        "sales_history_raw.csv": "utf-8",
    }


def test_orphan_sale_rejected(report):
    assert report.rejected == [("sales_history_raw.csv", 4, "партнер с id 999 не найден")]


def test_partners_cleaned(db_conn, report):
    assert table_rows(db_conn, PARTNERS_QUERY) == CLEAN_PARTNERS


def test_products_cleaned(db_conn, report):
    assert table_rows(db_conn, PRODUCTS_QUERY) == CLEAN_PRODUCTS


def test_dates_normalized(db_conn, report):
    assert table_rows(db_conn, SALES_QUERY) == CLEAN_SALES


def test_rerun_gives_same_result(db_conn, report):
    run_etl(db_conn)
    assert table_rows(db_conn, PARTNERS_QUERY) == CLEAN_PARTNERS
    assert table_rows(db_conn, SALES_QUERY) == CLEAN_SALES


def test_new_partner_gets_next_id(db_conn, report):
    data = db.PartnerData(type_id=db.fetch_partner_types(db_conn)[0].type_id, partner_name="Новый",
                          inn="1234567890", email="new@partner.ru", rating=0,
                          address=None, director=None, phone=None)
    assert db.insert_partner(db_conn, data) == 6


def test_checks_sql_passes(db_conn, report):
    checks_sql = (etl.TASK_DIR / "checks.sql").read_text(encoding="utf-8")
    failed = [row for row in db_conn.execute(checks_sql).fetchall() if not row["passed"]]
    assert failed == []


def test_every_anomaly_has_reason(etl_conn, db_conn, tmp_path):
    write_raw_files(
        tmp_path,
        partners=(
            "partner_id,partner_name,inn,email\n"
            "1,ООО Ромашка,7701111111,a@a.ru\n"
            "x,ООО Без id,7701111112,b@b.ru\n"
            "3,Ромашка без формы,7701111113,c@c.ru\n"
            "4,ООО Короткий ИНН,12345,d@d.ru\n"
            "5,ООО Плохой email,7701111115,not-an-email\n"
            "1,ООО Повтор id,7701111116,f@f.ru\n"
            "7,ООО Повтор ИНН,7701111111,g@g.ru\n"
            "8,ООО Повтор email,7701111118, A@A.RU\n"
            "9,ООО,7701111119,i@i.ru\n"
        ),
        products=(
            "product_id,product_name,price\n"
            "10,Товар,100\n"
            "11,Без цены,abc\n"
            "12,Ноль,0\n"
            "10,Повтор id,5\n"
            "13,Товар,7\n"
            "y,Нет id,5\n"
            "14,   ,5\n"
        ),
        sales=(
            "sale_id,partner_id,product_id,sale_date,quantity,amount\n"
            "1,1,10,31.02.2023,1,100\n"
            "2,1,10,2023-13-01,1,100\n"
            "3,1,10,вчера,1,100\n"
            "4,1,10,2023-10-01,0,0\n"
            "5,1,10,2023-10-01,1,abc\n"
            "6,1,99,2023-10-01,1,100\n"
            "7,3,10,2023-10-01,1,100\n"
            "7,1,10,2023-10-01,1,100\n"
            "z,1,10,2023-10-01,1,100\n"
            "8,1,10,01/10/2023,2,200\n"
        ),
    )
    result = run_etl(db_conn, tmp_path)
    assert result.loaded == {"partners": 1, "products": 1, "sales_history": 1}
    assert result.rejected == [
        ("partners_raw.csv", 3, "id партнера - не целое число"),
        ("partners_raw.csv", 4, "в начале названия нет формы из справочника partner_types"),
        ("partners_raw.csv", 5, "ИНН не из 10 или 12 цифр"),
        ("partners_raw.csv", 6, "email в неверном формате"),
        ("partners_raw.csv", 7, "повтор id партнера"),
        ("partners_raw.csv", 8, "повтор ИНН"),
        ("partners_raw.csv", 9, "повтор email"),
        ("partners_raw.csv", 10, "пустое наименование"),
        ("products_raw.csv", 3, "цена - не положительное число"),
        ("products_raw.csv", 4, "цена - не положительное число"),
        ("products_raw.csv", 5, "повтор id товара"),
        ("products_raw.csv", 6, "повтор наименования"),
        ("products_raw.csv", 7, "id товара - не целое число"),
        ("products_raw.csv", 8, "пустое наименование"),
        ("sales_history_raw.csv", 2, "дата не распознана"),
        ("sales_history_raw.csv", 3, "дата не распознана"),
        ("sales_history_raw.csv", 4, "дата не распознана"),
        ("sales_history_raw.csv", 5, "количество - не целое положительное число"),
        ("sales_history_raw.csv", 6, "сумма - не число"),
        ("sales_history_raw.csv", 7, "товар с id 99 не найден"),
        ("sales_history_raw.csv", 8, "партнер с id 3 не найден"),
        ("sales_history_raw.csv", 9, "повтор id продажи"),
        ("sales_history_raw.csv", 10, "id продажи - не целое число"),
    ]
    assert table_rows(db_conn, SALES_QUERY) == [(8, 1, 10, date(2023, 10, 1), 2, Decimal("200.00"))]


def test_main_prints_report(etl_conn, db_store, capsys):
    assert etl.main() == 0
    output = capsys.readouterr().out
    assert "products_raw.csv: cp1251" in output
    assert "sales_history: 5" in output
    assert "sales_history_raw.csv, строка 4: партнер с id 999 не найден" in output


def test_main_reports_failure(monkeypatch, capsys):
    def refuse():
        raise psycopg.OperationalError("сервер не отвечает")

    monkeypatch.setattr(db, "connect", refuse)
    assert etl.main() == 1
    assert "Импорт не выполнен: сервер не отвечает" in capsys.readouterr().err
