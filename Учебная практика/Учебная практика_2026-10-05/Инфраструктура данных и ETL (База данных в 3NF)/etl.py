"""Импорт сырых выгрузок заказчика: файлы raw/ -> staging -> чистые таблицы.

Автор: Danis Arslanov

Запуск из папки практики, после schema.sql и reference.sql:

    python "Инфраструктура данных и ETL (База данных в 3NF)/etl.py"

Файлы читает Python, а не COPY ... CSV самой СУБД. В выгрузках кавычки
стоят посреди полей без кавычек: Монитор 27", АО "Технолоджис". Разбор CSV
в PostgreSQL открывает на такой кавычке кавычки: на products_raw.csv COPY
падает с «unterminated CSV quoted field», а из партнера молча делает
«АО Технолоджис». Модуль csv считает такую кавычку обычным символом.
Очистка данных - в etl.sql.
"""

import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

TASK_DIR = Path(__file__).resolve().parent
PRACTICE_DIR = TASK_DIR.parent
# Подключение к базе берется из db.py соседнего задания: папки заданий с
# пробелами в именах пакетами Python быть не могут, поэтому все они
# добавляются в пути поиска модулей.
for task_dir in sorted(PRACTICE_DIR.iterdir()):
    if task_dir.is_dir() and not task_dir.name.startswith((".", "_")):
        sys.path.insert(0, str(task_dir))

import db

RAW_DIR = TASK_DIR / "raw"
STAGING_SQL = (TASK_DIR / "staging.sql").read_text(encoding="utf-8")
ETL_SQL = (TASK_DIR / "etl.sql").read_text(encoding="utf-8")

PARTNERS_COPY = "COPY staging.partners_raw (line_no, partner_id, partner_name, inn, email) FROM STDIN"
PRODUCTS_COPY = "COPY staging.products_raw (line_no, product_id, product_name, price) FROM STDIN"
SALES_COPY = (
    "COPY staging.sales_history_raw (line_no, sale_id, partner_id, product_id, sale_date, quantity, amount) "
    "FROM STDIN"
)

COUNTS_QUERY = """
SELECT
    (SELECT COUNT(*) FROM partners) AS partners,
    (SELECT COUNT(*) FROM products) AS products,
    (SELECT COUNT(*) FROM sales_history) AS sales_history
"""

REJECTED_QUERY = """
SELECT file_name, line_no, reject_reason
FROM staging.rejected_rows
ORDER BY file_name, line_no
"""


@dataclass(frozen=True)
class RawFile:
    """Файл выгрузки: имя, ожидаемые колонки и команда загрузки в staging."""

    file_name: str
    columns: tuple[str, ...]
    copy_query: str


RAW_FILES = (
    RawFile("partners_raw.csv", ("partner_id", "partner_name", "inn", "email"), PARTNERS_COPY),
    RawFile("products_raw.csv", ("product_id", "product_name", "price"), PRODUCTS_COPY),
    RawFile("sales_history_raw.csv",
            ("sale_id", "partner_id", "product_id", "sale_date", "quantity", "amount"), SALES_COPY),
)


@dataclass(frozen=True)
class EtlReport:
    """Итог импорта: в какой кодировке прочитан каждый файл, сколько строк
    легло в чистые таблицы и какие строки отброшены."""

    encodings: dict[str, str]
    loaded: dict[str, int]
    rejected: list[tuple[str, int, str]]


class RawFileError(ValueError):
    """Файл выгрузки не той структуры: импорт не начинается."""


def decode(data: bytes) -> tuple[str, str]:
    """Текст файла и кодировка, в которой он прочитан."""
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        # Сохраненные из Excel под Windows выгрузки приходят в cp1251, как
        # products_raw.csv. В UTF-8 такие байты кириллицы недопустимы, так
        # что ошибка декодирования однозначно указывает на cp1251.
        return data.decode("cp1251"), "cp1251"


def read_rows(path: Path, columns: tuple[str, ...]) -> tuple[str, list[tuple[int, list[str]]]]:
    """Кодировка файла и его строки с номерами, без заголовка и пустых строк."""
    text, encoding = decode(path.read_bytes())
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, None)
    if header != list(columns):
        raise RawFileError(f"{path.name}: ожидались колонки {', '.join(columns)}, в файле {header}")
    rows = []
    for row in reader:
        if not row:
            continue
        if len(row) != len(columns):
            raise RawFileError(
                f"{path.name}, строка {reader.line_num}: полей {len(row)}, а должно быть {len(columns)}"
            )
        rows.append((reader.line_num, row))
    return encoding, rows


def load_raw(connection: psycopg.Connection, raw_dir: Path = RAW_DIR) -> dict[str, str]:
    """Пересоздать staging и загрузить в него файлы как есть.

    Возвращает кодировку каждого файла.
    """
    connection.execute(STAGING_SQL)
    encodings = {}
    for raw_file in RAW_FILES:
        encoding, rows = read_rows(raw_dir / raw_file.file_name, raw_file.columns)
        encodings[raw_file.file_name] = encoding
        with connection.cursor() as cursor, cursor.copy(raw_file.copy_query) as copy:
            for line_no, row in rows:
                copy.write_row([line_no, *row])
    return encodings


def run_etl(connection: psycopg.Connection, raw_dir: Path = RAW_DIR) -> EtlReport:
    """Загрузить файлы в staging, очистить и перезалить чистые таблицы.

    Все идет в одной транзакции подключения: при ошибке в базе не остается
    половины импорта.
    """
    encodings = load_raw(connection, raw_dir)
    connection.execute(ETL_SQL)
    loaded = connection.execute(COUNTS_QUERY).fetchone()
    rejected = [
        (row["file_name"], row["line_no"], row["reject_reason"])
        for row in connection.execute(REJECTED_QUERY).fetchall()
    ]
    return EtlReport(encodings, dict(loaded), rejected)


def format_report(report: EtlReport) -> str:
    lines = ["Кодировки файлов:"]
    lines += [f"  {file_name}: {encoding}" for file_name, encoding in report.encodings.items()]
    lines.append("Загружено строк:")
    lines += [f"  {table}: {count}" for table, count in report.loaded.items()]
    lines.append(f"Отброшено строк: {len(report.rejected)}")
    lines += [f"  {file_name}, строка {line_no}: {reason}" for file_name, line_no, reason in report.rejected]
    return "\n".join(lines)


def main() -> int:
    try:
        with db.connect() as connection:
            report = run_etl(connection)
    except (RawFileError, psycopg.Error) as error:
        print(f"Импорт не выполнен: {error}", file=sys.stderr)
        return 1
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
