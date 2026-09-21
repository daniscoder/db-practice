"""Задание 4: проверка данных карточки до отправки в базу.

Автор: Danis Arslanov
"""

import pytest

from validation import (
    ValidationError,
    check_email,
    normalize_phone,
    parse_rating,
    require,
    validate_partner_form,
)

VALID_FORM = {
    "company_name": " Бета ",
    "type_id": 2,
    "rating": "5",
    "address": "",
    "director": "Орлов Олег Олегович",
    "phone": "8 (999) 123-45-67",
    "email": "beta@example.ru",
}


@pytest.mark.parametrize(("text", "expected"), [("5", 5), (" 7 ", 7), ("0", 0)])
def test_rating_accepted(text, expected):
    assert parse_rating(text) == expected


@pytest.mark.parametrize("text", ["abc", "4.5", "1,5", "5!"])
def test_rating_not_integer(text):
    with pytest.raises(ValidationError, match="целым числом от 0"):
        parse_rating(text)


def test_rating_negative():
    with pytest.raises(ValidationError, match="отрицательным"):
        parse_rating("-1")


def test_rating_empty():
    with pytest.raises(ValidationError, match="Укажите рейтинг"):
        parse_rating("  ")


def test_required_field():
    assert require("  Альфа ", "Наименование") == "Альфа"
    with pytest.raises(ValidationError, match="Наименование"):
        require("   ", "Наименование")


def test_email_accepted():
    assert check_email(" info@logex.ru ") == "info@logex.ru"


@pytest.mark.parametrize("text", ["", "info", "info@logex", "in fo@logex.ru"])
def test_email_rejected(text):
    with pytest.raises(ValidationError):
        check_email(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("+7 (999) 123-45-67", "+79991234567"),
        ("8 999 123 45 67", "+79991234567"),
        ("", None),
    ],
)
def test_phone_normalized(text, expected):
    assert normalize_phone(text) == expected


@pytest.mark.parametrize("text", ["12345", "+1 999 123 45 67", "+7 999 123 45 678"])
def test_phone_rejected(text):
    with pytest.raises(ValidationError, match="11 цифр"):
        normalize_phone(text)


def test_valid_form():
    data = validate_partner_form(**VALID_FORM)
    assert data.company_name == "Бета"
    assert data.address is None
    assert data.phone == "+79991234567"
    assert data.rating == 5


def test_first_error_is_reported_first():
    form = dict(VALID_FORM, company_name="", rating="abc")
    with pytest.raises(ValidationError, match="Наименование"):
        validate_partner_form(**form)


def test_type_is_required():
    with pytest.raises(ValidationError, match="тип партнера"):
        validate_partner_form(**dict(VALID_FORM, type_id=None))
