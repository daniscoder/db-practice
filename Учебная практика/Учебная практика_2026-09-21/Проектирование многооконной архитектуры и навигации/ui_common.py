"""Общее для обоих окон: оформление, ресурсы, вывод телефона.

Автор: Danis Arslanov
"""

from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
APP_ICON = RESOURCES_DIR / "icon.png"
LOGO = RESOURCES_DIR / "logo.png"

# Оформление по руководству по стилю прошлой практики: белый фон, черный
# текст, тонкие серые рамки, шрифт Segoe UI.
STYLE_SHEET = """
QWidget {
    font-family: "Segoe UI";
    font-size: 10pt;
    color: #000000;
    background-color: #FFFFFF;
}
QLabel#pageTitle {
    font-size: 16pt;
}
QScrollArea#partnerList {
    border: 1px solid #7F7F7F;
}
QFrame#partnerCard {
    border: 1px solid #7F7F7F;
}
QFrame#partnerCard QLabel {
    border: none;
}
QLabel#cardTitle, QLabel#cardDiscount {
    font-size: 14pt;
}
QLineEdit {
    border: 1px solid #7F7F7F;
    padding: 4px 6px;
}
QPushButton {
    border: 1px solid #7F7F7F;
    padding: 6px 18px;
}
QPushButton:hover {
    background-color: #F0F0F0;
}
"""


def format_phone(phone: str | None) -> str:
    """Показать телефон группами: +7 223 322 22 32.

    В базе номер хранится каноном, плюс и цифры. Номер другой длины
    выводится как есть.
    """
    if phone is None:
        return "Телефон не указан"
    digits = phone.removeprefix("+")
    if len(digits) != 11:
        return phone
    return f"+{digits[0]} {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:]}"
