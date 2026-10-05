"""Задание 3: проверка данных карточки до отправки в базу.

Автор: Danis Arslanov
"""

import pytest

from validation import (
    ValidationError,
    check_email,
    check_inn,
    normalize_phone,
    parse_rating,
    require,
    validate_partner_form,
)

VALID_FORM = {
    "partner_name": " Бета ",
    "type_id": 2,
    "inn": "123456789012",
    "rating": "5",
    "address": "",
    "director": "Орлов Олег Олегович",
    "phone": "8 (999) 123-45-67",
    "email": " Beta@Example.ru ",
}


@pytest.mark.parametrize(("text", "expected"), [("5", 5), (" 7 ", 7), ("0", 0)])
def test_rating_accepted(text, expected):
    assert parse_rating(text) == expected


@pytest.mark.parametrize("text", ["abc", "4.5", "1,5", "5!"])
def test_rating_not_integer(text):
    with pytest.raises(ValidationError, match="целым неотрицательным числом"):
        parse_rating(text)


def test_rating_negative():
    with pytest.raises(ValidationError, match="отрицательным"):
        parse_rating("-1")


def test_rating_empty():
    with pytest.raises(ValidationError, match="«Рейтинг» не заполнено"):
        parse_rating("  ")


def test_error_has_numbered_steps():
    with pytest.raises(ValidationError) as error:
        parse_rating("abc")
    assert "Как исправить:\n1. " in str(error.value)
    assert "2. Введите целое число" in str(error.value)


def test_required_field():
    assert require("  Вектор ", "Наименование") == "Вектор"
    with pytest.raises(ValidationError, match="Наименование"):
        require("   ", "Наименование")


@pytest.mark.parametrize("text", ["7701234567", "123456789012"])
def test_inn_accepted(text):
    assert check_inn(text) == text


@pytest.mark.parametrize("text", ["12345", "77012345678", "77012345ab"])
def test_inn_rejected(text):
    with pytest.raises(ValidationError, match="10 цифр"):
        check_inn(text)


def test_email_lowercased():
    assert check_email(" Info@Techno.ru ") == "info@techno.ru"


@pytest.mark.parametrize("text", ["", "info", "info@techno", "in fo@techno.ru"])
def test_email_rejected(text):
    with pytest.raises(ValidationError):
        check_email(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("+7 (999) 123-45-67", "+79991234567"), ("8 999 123 45 67", "+79991234567"), ("", None)],
)
def test_phone_normalized(text, expected):
    assert normalize_phone(text) == expected


@pytest.mark.parametrize("text", ["12345", "+1 999 123 45 67", "+7 999 123 45 678"])
def test_phone_rejected(text):
    with pytest.raises(ValidationError, match="11 цифр"):
        normalize_phone(text)


def test_valid_form():
    data = validate_partner_form(**VALID_FORM)
    assert data.partner_name == "Бета"
    assert data.inn == "123456789012"
    assert data.address is None
    assert data.phone == "+79991234567"
    assert data.email == "beta@example.ru"
    assert data.rating == 5


def test_first_error_is_reported_first():
    with pytest.raises(ValidationError, match="Наименование"):
        validate_partner_form(**dict(VALID_FORM, partner_name="", rating="abc"))


def test_type_is_required():
    with pytest.raises(ValidationError, match="тип партнера"):
        validate_partner_form(**dict(VALID_FORM, type_id=None))
