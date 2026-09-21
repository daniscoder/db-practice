"""Работа с базой: справочник типов, реестр партнеров, добавление и изменение.

Автор: Danis Arslanov

Параметры подключения берутся из переменных окружения PGHOST, PGPORT,
PGUSER и PGDATABASE, пароль из PGPASSWORD. Незаданные значения заменяются
значениями из CONNECTION_DEFAULTS.
"""

import os
from dataclasses import asdict, dataclass

import psycopg
from psycopg import errors
from psycopg.rows import dict_row

from discount import calculate_partner_discount

CONNECTION_DEFAULTS = {
    "host": ("PGHOST", "localhost"),
    "port": ("PGPORT", "5432"),
    "user": ("PGUSER", "postgres"),
    "dbname": ("PGDATABASE", "partners_crm"),
}

TYPES_QUERY = "SELECT type_id, type_name FROM partner_types ORDER BY type_name"

PARTNERS_QUERY = """
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
GROUP BY p.partner_id, t.type_name
ORDER BY p.company_name
"""

PARTNER_QUERY = """
SELECT type_id, company_name, director, phone, email, address, rating
FROM partners
WHERE partner_id = %(partner_id)s
"""

TYPE_EXISTS_QUERY = "SELECT 1 FROM partner_types WHERE type_id = %(type_id)s"

INSERT_QUERY = """
INSERT INTO partners (type_id, company_name, director, phone, email, address, rating)
VALUES (%(type_id)s, %(company_name)s, %(director)s, %(phone)s, %(email)s, %(address)s, %(rating)s)
RETURNING partner_id
"""

UPDATE_QUERY = """
UPDATE partners
SET type_id = %(type_id)s,
    company_name = %(company_name)s,
    director = %(director)s,
    phone = %(phone)s,
    email = %(email)s,
    address = %(address)s,
    rating = %(rating)s
WHERE partner_id = %(partner_id)s
"""


@dataclass(frozen=True)
class PartnerType:
    """Строка справочника типов партнеров."""

    type_id: int
    type_name: str


@dataclass(frozen=True)
class PartnerListItem:
    """Партнер в реестре на главной форме, вместе с рассчитанной скидкой."""

    partner_id: int
    type_name: str
    company_name: str
    director: str | None
    phone: str | None
    rating: int
    discount: int


@dataclass(frozen=True)
class PartnerData:
    """Поля карточки партнера: то, что вводится в форме и пишется в базу."""

    type_id: int
    company_name: str
    director: str | None
    phone: str | None
    email: str
    address: str | None
    rating: int


class PartnerStoreError(Exception):
    """Отказ с готовым текстом для пользователя: что случилось и что делать."""


class PartnerNotFoundError(PartnerStoreError, LookupError):
    """Партнера нет в базе: например, его удалили, пока карточка была открыта."""


class UnknownPartnerTypeError(PartnerStoreError, LookupError):
    """Выбранного типа нет в справочнике."""


class DuplicateEmailError(PartnerStoreError, ValueError):
    """Партнер с таким email уже есть."""


def connect() -> psycopg.Connection:
    """Открыть подключение к базе практики."""
    settings = {
        key: os.environ.get(env_name, default)
        for key, (env_name, default) in CONNECTION_DEFAULTS.items()
    }
    return psycopg.connect(**settings, row_factory=dict_row)


def fetch_partner_types(connection: psycopg.Connection) -> list[PartnerType]:
    """Справочник типов для выпадающего списка, по алфавиту."""
    rows = connection.execute(TYPES_QUERY).fetchall()
    return [PartnerType(row["type_id"], row["type_name"]) for row in rows]


def fetch_partners(connection: psycopg.Connection) -> list[PartnerListItem]:
    """Реестр партнеров по алфавиту, у каждого своя скидка."""
    rows = connection.execute(PARTNERS_QUERY).fetchall()
    return [
        PartnerListItem(
            partner_id=row["partner_id"],
            type_name=row["type_name"],
            company_name=row["company_name"],
            director=row["director"],
            phone=row["phone"],
            rating=row["rating"],
            discount=calculate_partner_discount(row["total_quantity"]),
        )
        for row in rows
    ]


def fetch_partner(connection: psycopg.Connection, partner_id: int) -> PartnerData:
    """Все поля одного партнера для карточки."""
    row = connection.execute(PARTNER_QUERY, {"partner_id": partner_id}).fetchone()
    if row is None:
        raise PartnerNotFoundError(
            "Партнер не найден в базе: возможно, его удалили. Закройте карточку и обновите список."
        )
    return PartnerData(**row)


def check_type_exists(connection: psycopg.Connection, type_id: int) -> None:
    """Ссылочная целостность на уровне приложения.

    Тип проверяется до записи, чтобы пользователь получил понятное объяснение,
    а не голый отказ внешнего ключа fk_partners_type от СУБД.
    """
    if connection.execute(TYPE_EXISTS_QUERY, {"type_id": type_id}).fetchone() is None:
        raise UnknownPartnerTypeError(
            "Выбранного типа партнера нет в справочнике. Закройте карточку, откройте ее "
            "снова и выберите тип из списка."
        )


def duplicate_email_error(email: str) -> DuplicateEmailError:
    return DuplicateEmailError(
        f"Партнер с email {email} уже есть в базе. Укажите другой email и повторите сохранение."
    )


def insert_partner(connection: psycopg.Connection, data: PartnerData) -> int:
    """Добавить партнера и вернуть его id."""
    check_type_exists(connection, data.type_id)
    try:
        row = connection.execute(INSERT_QUERY, asdict(data)).fetchone()
    except errors.UniqueViolation as error:
        # Единственное уникальное поле партнера - email, другой причины у этой ошибки нет.
        raise duplicate_email_error(data.email) from error
    return row["partner_id"]


def update_partner(connection: psycopg.Connection, partner_id: int, data: PartnerData) -> None:
    """Сохранить изменения партнера."""
    check_type_exists(connection, data.type_id)
    try:
        cursor = connection.execute(UPDATE_QUERY, {**asdict(data), "partner_id": partner_id})
    except errors.UniqueViolation as error:
        raise duplicate_email_error(data.email) from error
    # UPDATE без совпавших строк ошибки не дает: партнера удалили, пока карточка была открыта.
    if cursor.rowcount == 0:
        raise PartnerNotFoundError(
            "Партнер не найден в базе: возможно, его удалили. Закройте карточку и обновите список."
        )


class PartnerStore:
    """Операции для окон. Каждая открывает свое подключение и при успехе
    фиксирует изменения, при ошибке откатывает. Окна работают через этот
    объект, а не с psycopg напрямую, поэтому в тестах его легко подменить."""

    def partner_types(self) -> list[PartnerType]:
        with connect() as connection:
            return fetch_partner_types(connection)

    def partners(self) -> list[PartnerListItem]:
        with connect() as connection:
            return fetch_partners(connection)

    def load(self, partner_id: int) -> PartnerData:
        with connect() as connection:
            return fetch_partner(connection, partner_id)

    def create(self, data: PartnerData) -> int:
        with connect() as connection:
            return insert_partner(connection, data)

    def update(self, partner_id: int, data: PartnerData) -> None:
        with connect() as connection:
            update_partner(connection, partner_id, data)
