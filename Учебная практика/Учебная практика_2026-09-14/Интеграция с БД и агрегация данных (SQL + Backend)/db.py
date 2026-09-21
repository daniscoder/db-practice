"""Работа с базой: суммарный объем продаж партнера и его скидка.

Автор: Danis Arslanov

Параметры подключения берутся из переменных окружения PGHOST, PGPORT,
PGUSER и PGDATABASE, пароль из PGPASSWORD (его libpq читает сама).
Незаданные значения заменяются значениями из CONNECTION_DEFAULTS.
"""

import os
from dataclasses import dataclass

import psycopg
from psycopg.rows import dict_row

from discount import calculate_partner_discount

CONNECTION_DEFAULTS = {
    "host": ("PGHOST", "localhost"),
    "port": ("PGPORT", "5432"),
    "user": ("PGUSER", "postgres"),
    "dbname": ("PGDATABASE", "partner_discounts"),
}

# LEFT JOIN идет от partners, а не от sales_history: у партнера без продаж
# строка все равно вернется, только SUM даст NULL. Так «партнера нет»
# (строк нет) отличается от «продаж нет» (строка с NULL).
TOTAL_QUANTITY_QUERY = """
SELECT SUM(s.quantity) AS total_quantity
FROM partners AS p
LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
WHERE p.partner_id = %(partner_id)s
GROUP BY p.partner_id
"""

PARTNER_SELECT = """
SELECT
    p.partner_id,
    t.type_name,
    p.company_name,
    p.director,
    p.phone,
    p.rating,
    SUM(s.quantity) AS total_quantity
FROM partners AS p
JOIN partner_types AS t ON t.type_id = p.type_id
LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
"""

PARTNER_GROUP_BY = "GROUP BY p.partner_id, t.type_name\n"

ALL_PARTNERS_QUERY = PARTNER_SELECT + PARTNER_GROUP_BY + "ORDER BY p.company_name\n"

ONE_PARTNER_QUERY = PARTNER_SELECT + "WHERE p.partner_id = %(partner_id)s\n" + PARTNER_GROUP_BY


@dataclass(frozen=True)
class Partner:
    """Данные партнера для карточки вместе с рассчитанной скидкой."""

    partner_id: int
    type_name: str
    company_name: str
    director: str
    phone: str | None
    rating: int
    total_quantity: int
    discount: int


def connect() -> psycopg.Connection:
    """Открыть подключение к базе практики."""
    settings = {
        key: os.environ.get(env_name, default)
        for key, (env_name, default) in CONNECTION_DEFAULTS.items()
    }
    return psycopg.connect(**settings, row_factory=dict_row)


def row_to_partner(row: dict) -> Partner:
    """Собрать партнера из строки запроса и досчитать скидку.

    total_quantity равен None, если продаж нет. Скидку для этого случая
    определяет функция расчета, а объем показывается нулем.
    """
    total_quantity = row["total_quantity"]
    return Partner(
        partner_id=row["partner_id"],
        type_name=row["type_name"],
        company_name=row["company_name"],
        director=row["director"],
        phone=row["phone"],
        rating=row["rating"],
        total_quantity=total_quantity or 0,
        discount=calculate_partner_discount(total_quantity),
    )


def fetch_partner_total_quantity(connection: psycopg.Connection, partner_id: int) -> int | None:
    """Суммарный объем продаж партнера; None, если продаж не было.

    Несуществующий партнер дает LookupError, а не молчаливый ноль.
    """
    row = connection.execute(TOTAL_QUANTITY_QUERY, {"partner_id": partner_id}).fetchone()
    if row is None:
        raise LookupError(f"Партнер {partner_id} не найден")
    return row["total_quantity"]


def fetch_partner_with_discount(connection: psycopg.Connection, partner_id: int) -> Partner:
    """Данные одного партнера вместе с его текущей скидкой."""
    row = connection.execute(ONE_PARTNER_QUERY, {"partner_id": partner_id}).fetchone()
    if row is None:
        raise LookupError(f"Партнер {partner_id} не найден")
    return row_to_partner(row)


def fetch_partners_with_discounts(connection: psycopg.Connection) -> list[Partner]:
    """Все партнеры по алфавиту, каждый со своей скидкой. Один запрос на всех."""
    rows = connection.execute(ALL_PARTNERS_QUERY).fetchall()
    return [row_to_partner(row) for row in rows]
