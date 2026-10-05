-- ============================================================
-- staging.sql - промежуточные таблицы для сырых выгрузок
-- Автор: Danis Arslanov
--
-- Строки файлов ложатся сюда как есть, все поля текстом: пробелы, даты в
-- разных форматах и битые ссылки сохраняются, чтобы их разобрал etl.sql.
-- line_no - номер строки в исходном файле, по нему видно, какая строка
-- отброшена. Выполняет etl.py перед загрузкой файлов.
-- ============================================================

DROP SCHEMA IF EXISTS staging CASCADE;
CREATE SCHEMA staging;

CREATE TABLE staging.partners_raw (
    line_no      INT  PRIMARY KEY,
    partner_id   TEXT,
    partner_name TEXT,
    inn          TEXT,
    email        TEXT
);

CREATE TABLE staging.products_raw (
    line_no      INT  PRIMARY KEY,
    product_id   TEXT,
    product_name TEXT,
    price        TEXT
);

CREATE TABLE staging.sales_history_raw (
    line_no    INT  PRIMARY KEY,
    sale_id    TEXT,
    partner_id TEXT,
    product_id TEXT,
    sale_date  TEXT,
    quantity   TEXT,
    amount     TEXT
);
