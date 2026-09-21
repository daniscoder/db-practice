"""Проверка данных карточки партнера до отправки в базу.

Автор: Danis Arslanov

Каждая ошибка несет готовый текст для пользователя: что не так и как это
исправить. Окно показывает его как есть.
"""

import re

from db import PartnerData

# Та же проверка, что chk_partners_email в базе: что-то, @, что-то, точка, что-то.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(ValueError):
    """Данные формы не прошли проверку. Текст ошибки предназначен пользователю."""


def require(text: str, field_label: str) -> str:
    """Обязательное поле без пробелов по краям."""
    value = text.strip()
    if not value:
        raise ValidationError(
            f"Поле «{field_label}» обязательно для заполнения. Заполните его и повторите сохранение."
        )
    return value


def optional(text: str) -> str | None:
    """Необязательное поле: пустая строка превращается в NULL."""
    return text.strip() or None


def parse_rating(text: str) -> int:
    """Рейтинг: целое число от 0."""
    value = text.strip()
    if not value:
        raise ValidationError("Укажите рейтинг: целое число от 0, например 5.")
    try:
        rating = int(value)
    except ValueError:
        raise ValidationError(
            "Рейтинг должен быть целым числом от 0. Пожалуйста, удалите знаки препинания, "
            "пробелы и буквы и повторите попытку."
        ) from None
    if rating < 0:
        raise ValidationError(
            "Рейтинг не может быть отрицательным. Введите целое число от 0 и повторите попытку."
        )
    return rating


def check_email(text: str) -> str:
    """Email: обязателен и похож на адрес."""
    email = require(text, "Email")
    if not EMAIL_PATTERN.match(email):
        raise ValidationError(
            "Email указан в неверном формате. Введите адрес вида name@company.ru и повторите сохранение."
        )
    return email


def normalize_phone(text: str) -> str | None:
    """Привести телефон к канону +7XXXXXXXXXX. Пустое поле - NULL.

    Скобки, пробелы и дефисы отбрасываются, первая цифра 8 заменяется на 7:
    так один и тот же номер в любом написании хранится одинаково.
    """
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if len(digits) != 11 or digits[0] not in "78":
        raise ValidationError(
            "Телефон должен содержать 11 цифр и начинаться с +7 или 8, например "
            "+7 (999) 123-45-67. Проверьте номер и повторите сохранение."
        )
    return "+7" + digits[1:]


def validate_partner_form(*, company_name: str, type_id: int | None, rating: str, address: str,
                          director: str, phone: str, email: str) -> PartnerData:
    """Проверить поля в порядке формы и собрать данные для записи.

    Проверки идут сверху вниз, как поля на экране: пользователь видит первую
    ошибку, исправляет ее и сохраняет снова.
    """
    checked_name = require(company_name, "Наименование")
    if type_id is None:
        raise ValidationError("Выберите тип партнера из списка и повторите сохранение.")
    checked_rating = parse_rating(rating)
    checked_address = optional(address)
    checked_director = optional(director)
    checked_phone = normalize_phone(phone)
    checked_email = check_email(email)
    return PartnerData(
        type_id=type_id,
        company_name=checked_name,
        director=checked_director,
        phone=checked_phone,
        email=checked_email,
        address=checked_address,
        rating=checked_rating,
    )
