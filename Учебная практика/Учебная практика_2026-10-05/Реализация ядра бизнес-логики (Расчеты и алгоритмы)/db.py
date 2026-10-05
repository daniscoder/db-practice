"""Работа с базой: реестр и карточка партнера, история продаж, справочники
для расчета материалов.

Автор: Danis Arslanov

Параметры подключения берутся из переменных окружения PGHOST, PGPORT,
PGUSER и PGDATABASE, пароль из PGPASSWORD. Незаданные значения заменяются
значениями из CONNECTION_DEFAULTS.

Все запросы параметризованы: текст SQL - готовая константа, значения
уходят на сервер отдельно от него через %(имя)s. Пользовательский ввод в
текст запроса не попадает никогда.
"""

import os
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal

import psycopg
from psycopg import errors
from psycopg.rows import dict_row

from discount import calculate_discount
from user_messages import SAVE_AGAIN, guide_text

CONNECTION_DEFAULTS = {
    "host": ("PGHOST", "localhost"),
    "port": ("PGPORT", "5432"),
    "user": ("PGUSER", "postgres"),
    "dbname": ("PGDATABASE", "partners_final"),
}

TYPES_QUERY = "SELECT type_id, type_name FROM partner_types ORDER BY type_name"

# Количество для скидки суммирует сама СУБД; партнер без продаж получает 0.
PARTNERS_QUERY = """
SELECT
    p.partner_id,
    t.type_name,
    p.partner_name,
    p.inn,
    p.director,
    p.phone,
    p.rating,
    COALESCE(SUM(s.quantity), 0) AS total_quantity
FROM partners AS p
JOIN partner_types AS t ON t.type_id = p.type_id
LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
WHERE p.partner_name ILIKE %(pattern)s
   OR p.inn LIKE %(pattern)s
   OR p.email ILIKE %(pattern)s
   OR p.director ILIKE %(pattern)s
GROUP BY p.partner_id, t.type_name
ORDER BY p.partner_name
"""

PARTNER_QUERY = """
SELECT type_id, partner_name, inn, email, rating, address, director, phone
FROM partners
WHERE partner_id = %(partner_id)s
"""

TYPE_EXISTS_QUERY = "SELECT 1 FROM partner_types WHERE type_id = %(type_id)s"

INSERT_QUERY = """
INSERT INTO partners (type_id, partner_name, inn, email, rating, address, director, phone)
VALUES (%(type_id)s, %(partner_name)s, %(inn)s, %(email)s, %(rating)s, %(address)s, %(director)s, %(phone)s)
RETURNING partner_id
"""

UPDATE_QUERY = """
UPDATE partners
SET type_id = %(type_id)s,
    partner_name = %(partner_name)s,
    inn = %(inn)s,
    email = %(email)s,
    rating = %(rating)s,
    address = %(address)s,
    director = %(director)s,
    phone = %(phone)s
WHERE partner_id = %(partner_id)s
"""

SALES_QUERY = """
SELECT pr.product_name, s.sale_date, s.quantity
FROM sales_history AS s
JOIN products AS pr ON pr.product_id = s.product_id
WHERE s.partner_id = %(partner_id)s
ORDER BY s.sale_date DESC, s.sale_id DESC
"""

PRODUCT_TYPES_QUERY = """
SELECT product_type_id, type_name, coefficient
FROM product_types
ORDER BY type_name
"""

MATERIAL_TYPES_QUERY = """
SELECT material_type_id, type_name, defect_percent
FROM material_types
ORDER BY type_name
"""

PRODUCT_COEFFICIENT_QUERY = """
SELECT coefficient
FROM product_types
WHERE product_type_id = %(product_type_id)s
"""

DEFECT_PERCENT_QUERY = """
SELECT defect_percent
FROM material_types
WHERE material_type_id = %(material_type_id)s
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
    partner_name: str
    inn: str
    director: str | None
    phone: str | None
    rating: int
    discount: int


@dataclass(frozen=True)
class PartnerData:
    """Поля карточки партнера: то, что вводится в форме и пишется в базу."""

    type_id: int
    partner_name: str
    inn: str
    email: str
    rating: int
    address: str | None
    director: str | None
    phone: str | None


@dataclass(frozen=True)
class SaleRecord:
    """Одна продажа партнера для окна истории."""

    product_name: str
    sale_date: date
    quantity: int


@dataclass(frozen=True)
class ProductType:
    """Тип продукции и его коэффициент расхода сырья."""

    product_type_id: int
    type_name: str
    coefficient: Decimal


@dataclass(frozen=True)
class MaterialType:
    """Тип материала и его процент брака."""

    material_type_id: int
    type_name: str
    defect_percent: Decimal


class PartnerStoreError(Exception):
    """Отказ с готовым текстом для пользователя: что случилось и что делать."""


class PartnerNotFoundError(PartnerStoreError, LookupError):
    """Партнера нет в базе: например, его удалили, пока окно было открыто."""


class UnknownPartnerTypeError(PartnerStoreError, LookupError):
    """Выбранного типа нет в справочнике."""


class DuplicateValueError(PartnerStoreError, ValueError):
    """Партнер с таким ИНН или email уже есть."""


def connect() -> psycopg.Connection:
    """Открыть подключение к базе практики."""
    settings = {
        key: os.environ.get(env_name, default)
        for key, (env_name, default) in CONNECTION_DEFAULTS.items()
    }
    return psycopg.connect(**settings, row_factory=dict_row)


def like_pattern(search: str) -> str:
    """Шаблон LIKE «содержит строку». Знаки % и _ из ввода ищутся как
    обычные символы, а не работают подстановкой: поиск «100%» не должен
    находить всех подряд."""
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def partner_not_found() -> PartnerNotFoundError:
    return PartnerNotFoundError(guide_text(
        "Партнер не найден в базе: возможно, его удалили, пока окно было открыто.",
        ["Закройте это окно кнопкой «Назад».", "Нажмите «Обновить» в реестре партнеров.",
         "Выберите партнера в обновленном списке."],
    ))


def fetch_partner_types(connection: psycopg.Connection) -> list[PartnerType]:
    """Справочник типов партнеров для выпадающего списка, по алфавиту."""
    rows = connection.execute(TYPES_QUERY).fetchall()
    return [PartnerType(row["type_id"], row["type_name"]) for row in rows]


def fetch_partners(connection: psycopg.Connection, search: str = "") -> list[PartnerListItem]:
    """Реестр партнеров по алфавиту, у каждого своя скидка.

    search - подстрока наименования, ИНН, email или ФИО директора; пустая
    строка выбирает всех.
    """
    rows = connection.execute(PARTNERS_QUERY, {"pattern": like_pattern(search)}).fetchall()
    return [
        PartnerListItem(
            partner_id=row["partner_id"],
            type_name=row["type_name"],
            partner_name=row["partner_name"],
            inn=row["inn"],
            director=row["director"],
            phone=row["phone"],
            rating=row["rating"],
            discount=calculate_discount(row["total_quantity"]),
        )
        for row in rows
    ]


def fetch_partner(connection: psycopg.Connection, partner_id: int) -> PartnerData:
    """Все поля одного партнера."""
    row = connection.execute(PARTNER_QUERY, {"partner_id": partner_id}).fetchone()
    if row is None:
        raise partner_not_found()
    return PartnerData(**row)


def fetch_partner_sales(connection: psycopg.Connection, partner_id: int) -> list[SaleRecord]:
    """История продаж партнера с названиями товаров, новые сверху."""
    rows = connection.execute(SALES_QUERY, {"partner_id": partner_id}).fetchall()
    return [SaleRecord(row["product_name"], row["sale_date"], row["quantity"]) for row in rows]


def fetch_product_types(connection: psycopg.Connection) -> list[ProductType]:
    """Справочник типов продукции с коэффициентами, по алфавиту."""
    rows = connection.execute(PRODUCT_TYPES_QUERY).fetchall()
    return [ProductType(row["product_type_id"], row["type_name"], row["coefficient"]) for row in rows]


def fetch_material_types(connection: psycopg.Connection) -> list[MaterialType]:
    """Справочник типов материалов с процентом брака, по алфавиту."""
    rows = connection.execute(MATERIAL_TYPES_QUERY).fetchall()
    return [MaterialType(row["material_type_id"], row["type_name"], row["defect_percent"]) for row in rows]


def fetch_product_coefficient(connection: psycopg.Connection, product_type_id: int) -> Decimal | None:
    """Коэффициент типа продукции; None, если такого типа нет."""
    row = connection.execute(PRODUCT_COEFFICIENT_QUERY, {"product_type_id": product_type_id}).fetchone()
    return None if row is None else row["coefficient"]


def fetch_defect_percent(connection: psycopg.Connection, material_type_id: int) -> Decimal | None:
    """Процент брака типа материала; None, если такого типа нет."""
    row = connection.execute(DEFECT_PERCENT_QUERY, {"material_type_id": material_type_id}).fetchone()
    return None if row is None else row["defect_percent"]


def check_type_exists(connection: psycopg.Connection, type_id: int) -> None:
    """Тип проверяется до записи, чтобы пользователь получил объяснение, а не
    голый отказ внешнего ключа fk_partners_type от СУБД."""
    if connection.execute(TYPE_EXISTS_QUERY, {"type_id": type_id}).fetchone() is None:
        raise UnknownPartnerTypeError(guide_text(
            "Выбранного типа партнера нет в справочнике: его удалили, пока карточка была открыта.",
            ["Закройте карточку кнопкой «Назад».", "Откройте ее снова: список типов загрузится заново.",
             "Выберите тип из списка.", SAVE_AGAIN],
        ))


def duplicate_error(constraint_name: str | None, data: PartnerData) -> DuplicateValueError | None:
    """Понятный текст для нарушения уникальности ИНН или email; None для
    других ограничений, их ошибка уходит пользователю как ошибка СУБД."""
    if constraint_name == "uq_partners_inn":
        return DuplicateValueError(guide_text(
            f"Партнер с ИНН {data.inn} уже есть в базе.",
            ["Сверьте ИНН с документами партнера.",
             "Если это тот же партнер, вернитесь в реестр и откройте его карточку из списка.",
             "Если ИНН был введен с ошибкой, исправьте его.", SAVE_AGAIN],
        ))
    if constraint_name == "uq_partners_email":
        return DuplicateValueError(guide_text(
            f"Партнер с email {data.email} уже есть в базе.",
            ["Проверьте адрес: у каждого партнера свой email.", "Укажите другой email.", SAVE_AGAIN],
        ))
    return None


def write_partner(connection: psycopg.Connection, query: str, params: dict, data: PartnerData) -> psycopg.Cursor:
    """Выполнить INSERT или UPDATE партнера, переведя дубль ИНН или email
    в понятную пользователю ошибку."""
    check_type_exists(connection, data.type_id)
    try:
        return connection.execute(query, params)
    except errors.UniqueViolation as error:
        user_error = duplicate_error(error.diag.constraint_name, data)
        if user_error is None:
            raise
        raise user_error from error


def insert_partner(connection: psycopg.Connection, data: PartnerData) -> int:
    """Добавить партнера и вернуть его id."""
    return write_partner(connection, INSERT_QUERY, asdict(data), data).fetchone()["partner_id"]


def update_partner(connection: psycopg.Connection, partner_id: int, data: PartnerData) -> None:
    """Сохранить изменения партнера."""
    cursor = write_partner(connection, UPDATE_QUERY, {**asdict(data), "partner_id": partner_id}, data)
    # UPDATE без совпавших строк ошибки не дает: партнера удалили, пока карточка была открыта.
    if cursor.rowcount == 0:
        raise partner_not_found()


class CrmStore:
    """Операции для окон. Каждая открывает свое подключение и при успехе
    фиксирует изменения, при ошибке откатывает. Окна работают через этот
    объект, а не с psycopg напрямую, поэтому в тестах его легко подменить.

    Методы product_coefficient и defect_percent - справочники для
    MaterialCalculator: метод расчета обращается через них к базе.
    """

    def partner_types(self) -> list[PartnerType]:
        with connect() as connection:
            return fetch_partner_types(connection)

    def partners(self, search: str = "") -> list[PartnerListItem]:
        with connect() as connection:
            return fetch_partners(connection, search)

    def load(self, partner_id: int) -> PartnerData:
        with connect() as connection:
            return fetch_partner(connection, partner_id)

    def sales(self, partner_id: int) -> list[SaleRecord]:
        with connect() as connection:
            return fetch_partner_sales(connection, partner_id)

    def product_types(self) -> list[ProductType]:
        with connect() as connection:
            return fetch_product_types(connection)

    def material_types(self) -> list[MaterialType]:
        with connect() as connection:
            return fetch_material_types(connection)

    def product_coefficient(self, product_type_id: int) -> Decimal | None:
        with connect() as connection:
            return fetch_product_coefficient(connection, product_type_id)

    def defect_percent(self, material_type_id: int) -> Decimal | None:
        with connect() as connection:
            return fetch_defect_percent(connection, material_type_id)

    def create(self, data: PartnerData) -> int:
        with connect() as connection:
            return insert_partner(connection, data)

    def update(self, partner_id: int, data: PartnerData) -> None:
        with connect() as connection:
            update_partner(connection, partner_id, data)
