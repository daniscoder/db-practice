"""Общее для окон приложения: оформление, ресурсы, вывод чисел и телефона.

Автор: Danis Arslanov
"""

from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
APP_ICON = RESOURCES_DIR / "icon.png"
LOGO = RESOURCES_DIR / "logo.png"

# Оформление по руководству по стилю: белый фон, черный текст, тонкие серые
# рамки, шрифт Segoe UI. Выбранный партнер выделяется рамкой толще и темнее.
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
QScrollArea#partnerList, QTableWidget {
    border: 1px solid #7F7F7F;
}
QFrame#partnerCard {
    border: 1px solid #7F7F7F;
}
QFrame#partnerCard[selected="true"] {
    border: 2px solid #000000;
}
QFrame#partnerCard QLabel {
    border: none;
}
QLabel#cardTitle, QLabel#cardDiscount {
    font-size: 14pt;
}
QHeaderView::section {
    background-color: #FFFFFF;
    border: none;
    border-bottom: 1px solid #7F7F7F;
    padding: 4px 6px;
    font-weight: bold;
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
QPushButton:disabled {
    color: #7F7F7F;
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


def format_quantity(quantity: int) -> str:
    """Число с разрядами через пробел: 150 000."""
    return f"{quantity:,}".replace(",", " ")
