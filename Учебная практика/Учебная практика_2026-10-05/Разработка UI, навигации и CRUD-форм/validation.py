"""Проверка данных карточки партнера до отправки в базу.

Автор: Danis Arslanov

Каждая ошибка несет готовый текст для пользователя: что не так и по шагам,
как это исправить. Окно показывает его как есть.
"""

import re

from db import PartnerData
from user_messages import SAVE_AGAIN, guide_text

# Та же проверка, что chk_partners_email в базе: что-то, @, что-то, точка, что-то.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# 10 цифр у организации, 12 у индивидуального предпринимателя.
INN_PATTERN = re.compile(r"^\d{10}(\d{2})?$")


class ValidationError(ValueError):
    """Данные формы не прошли проверку. Текст ошибки предназначен пользователю."""


def require(text: str, field_label: str) -> str:
    """Обязательное поле без пробелов по краям."""
    value = text.strip()
    if not value:
        raise ValidationError(guide_text(
            f"Поле «{field_label}» не заполнено, а без него партнера не сохранить.",
            [f"Заполните поле «{field_label}».", SAVE_AGAIN],
        ))
    return value


def optional(text: str) -> str | None:
    """Необязательное поле: пустая строка превращается в NULL."""
    return text.strip() or None


def check_type(type_id: int | None) -> int:
    if type_id is None:
        raise ValidationError(guide_text(
            "Не выбран тип партнера.",
            ["Откройте список «Тип».", "Выберите тип, например ООО.", SAVE_AGAIN],
        ))
    return type_id


def check_inn(text: str) -> str:
    inn = require(text, "ИНН")
    if not INN_PATTERN.match(inn):
        raise ValidationError(guide_text(
            "ИНН должен состоять из 10 цифр у организации или 12 цифр у предпринимателя.",
            ["Сверьте ИНН с документами партнера.", "Введите его без пробелов и других знаков.", SAVE_AGAIN],
        ))
    return inn


def parse_rating(text: str) -> int:
    """Рейтинг: целое неотрицательное число."""
    value = require(text, "Рейтинг")
    try:
        rating = int(value)
    except ValueError:
        raise ValidationError(guide_text(
            "Рейтинг должен быть целым неотрицательным числом.",
            ["Удалите из поля «Рейтинг» буквы, пробелы и знаки препинания.",
             "Введите целое число, например 5.", SAVE_AGAIN],
        )) from None
    if rating < 0:
        raise ValidationError(guide_text(
            "Рейтинг не может быть отрицательным.",
            ["Уберите знак минус из поля «Рейтинг».", "Введите целое число от 0, например 5.", SAVE_AGAIN],
        ))
    return rating


def normalize_phone(text: str) -> str | None:
    """Привести телефон к канону +7XXXXXXXXXX. Пустое поле - NULL.

    Скобки, пробелы и дефисы отбрасываются, первая цифра 8 заменяется на 7:
    так один и тот же номер в любом написании хранится одинаково.
    """
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    if len(digits) != 11 or digits[0] not in "78":
        raise ValidationError(guide_text(
            "Телефон должен содержать 11 цифр и начинаться с +7 или 8.",
            ["Проверьте номер по образцу +7 (999) 123-45-67.",
             "Если телефона нет, очистите поле.", SAVE_AGAIN],
        ))
    return "+7" + digits[1:]


def check_email(text: str) -> str:
    """Email: обязателен и похож на адрес."""
    email = require(text, "Email")
    if not EMAIL_PATTERN.match(email):
        raise ValidationError(guide_text(
            "Email указан в неверном формате.",
            ["Введите адрес вида name@company.ru, без пробелов.", SAVE_AGAIN],
        ))
    return email.lower()


def validate_partner_form(*, partner_name: str, type_id: int | None, inn: str, rating: str, address: str,
                          director: str, phone: str, email: str) -> PartnerData:
    """Проверить поля в порядке формы и собрать данные для записи.

    Проверки идут сверху вниз, как поля на экране: пользователь видит первую
    ошибку, исправляет ее и сохраняет снова.
    """
    checked_name = require(partner_name, "Наименование")
    checked_type = check_type(type_id)
    checked_inn = check_inn(inn)
    checked_rating = parse_rating(rating)
    checked_address = optional(address)
    checked_director = optional(director)
    checked_phone = normalize_phone(phone)
    checked_email = check_email(email)
    return PartnerData(
        type_id=checked_type,
        partner_name=checked_name,
        inn=checked_inn,
        email=checked_email,
        rating=checked_rating,
        address=checked_address,
        director=checked_director,
        phone=checked_phone,
    )
