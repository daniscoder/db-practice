"""Главное окно: шапка с логотипом и список карточек партнеров со скидками.

Автор: Danis Arslanov
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from db import Partner

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
WINDOW_TITLE = "CRM: Список партнеров и скидок"
LOGO_HEIGHT = 48

# Оформление по макету Screenshot_2: белый фон, черный текст, тонкие серые
# рамки у списка и у каждой карточки, шрифт Segoe UI.
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
QPushButton {
    border: 1px solid #7F7F7F;
    padding: 6px 18px;
}
QPushButton:hover {
    background-color: #F0F0F0;
}
"""


def format_phone(phone: str | None) -> str:
    """Показать телефон как в макете: +7 223 322 22 32.

    В базе номер хранится каноном, плюс и цифры, а разбивка на группы - дело
    отображения. Номер другой длины выводится как есть.
    """
    if phone is None:
        return "Телефон не указан"
    digits = phone.removeprefix("+")
    if len(digits) != 11:
        return phone
    return f"+{digits[0]} {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:]}"


class PartnerCard(QFrame):
    """Карточка одного партнера по макету Screenshot_2."""

    def __init__(self, partner: Partner, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("partnerCard")
        title_label = QLabel(f"{partner.type_name} | {partner.company_name}")
        title_label.setObjectName("cardTitle")
        discount_label = QLabel(f"{partner.discount}%")
        discount_label.setObjectName("cardDiscount")
        discount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        layout = QGridLayout(self)
        layout.setContentsMargins(24, 12, 70, 14)
        layout.setVerticalSpacing(0)
        layout.setColumnStretch(0, 1)
        layout.addWidget(title_label, 0, 0)
        layout.addWidget(discount_label, 0, 1)
        layout.addWidget(QLabel(partner.director), 1, 0)
        layout.addWidget(QLabel(format_phone(partner.phone)), 2, 0)
        layout.addWidget(QLabel(f"Рейтинг: {partner.rating}"), 3, 0)


class MainWindow(QMainWindow):
    """Окно со списком партнеров. Источник данных передается снаружи."""

    def __init__(self, load_partners: Callable[[], list[Partner]]) -> None:
        super().__init__()
        self._load_partners = load_partners
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(RESOURCES_DIR / "icon.png")))
        self.setStyleSheet(STYLE_SHEET)
        self.resize(720, 560)

        logo = QPixmap(str(RESOURCES_DIR / "logo.png"))
        logo_label = QLabel()
        logo_label.setPixmap(logo.scaledToHeight(LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation))
        title_label = QLabel("Партнеры и скидки")
        title_label.setObjectName("pageTitle")
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(refresh_button)

        self._status_label = QLabel()
        self._status_label.setObjectName("statusLabel")

        cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(cards_widget)
        self._cards_layout.setContentsMargins(20, 16, 20, 16)
        self._cards_layout.setSpacing(16)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("partnerList")
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(cards_widget)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.addLayout(header_layout)
        layout.addWidget(self._status_label)
        layout.addWidget(scroll_area, 1)
        self.setCentralWidget(central_widget)

    def refresh(self) -> None:
        """Перечитать партнеров. Ошибка источника данных не роняет окно."""
        try:
            partners = self._load_partners()
        except Exception as error:
            self._show_partners([])
            self._status_label.setText("Не удалось загрузить партнеров")
            QMessageBox.critical(self, WINDOW_TITLE, f"Не удалось загрузить данные:\n{error}")
            return
        self._show_partners(partners)
        self._status_label.setText(f"Партнеров: {len(partners)}" if partners else "Партнеров пока нет")

    def _show_partners(self, partners: list[Partner]) -> None:
        """Заменить карточки в списке на новые."""
        while self._cards_layout.count():
            widget = self._cards_layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for partner in partners:
            self._cards_layout.addWidget(PartnerCard(partner))
        self._cards_layout.addStretch(1)
