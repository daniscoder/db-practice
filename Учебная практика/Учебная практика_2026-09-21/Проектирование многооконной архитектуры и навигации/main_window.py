"""Главная форма: реестр партнеров и переход в карточку партнера.

Автор: Danis Arslanov
"""

import psycopg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import dialogs
from db import PartnerData, PartnerListItem, PartnerStore, PartnerStoreError
from partner_edit_window import PartnerEditWindow
from ui_common import APP_ICON, LOGO, STYLE_SHEET, format_phone

WINDOW_TITLE = "CRM: Реестр партнеров"
LOGO_HEIGHT = 48


class PartnerCard(QFrame):
    """Карточка партнера в реестре. Двойной щелчок открывает ее на редактирование."""

    # Сигнал, а не ссылка на метод главной формы: иначе карточка и форма держали
    # бы друг друга, и сборщик мусора разбирал бы их в произвольном порядке,
    # что в PySide6 кончается падением.
    open_requested = Signal(int)

    def __init__(self, partner: PartnerListItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("partnerCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Двойной щелчок - открыть карточку партнера")
        # Карточка помнит только id партнера: по нему главная форма заново
        # читает из базы актуальные данные, а не показывает устаревшую копию.
        self._partner_id = partner.partner_id

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
        layout.addWidget(QLabel(partner.director or "Директор не указан"), 1, 0)
        layout.addWidget(QLabel(format_phone(partner.phone)), 2, 0)
        layout.addWidget(QLabel(f"Рейтинг: {partner.rating}"), 3, 0)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.open_requested.emit(self._partner_id)
        event.accept()


class MainWindow(QMainWindow):
    """Реестр партнеров. Из него открывается карточка на добавление или изменение."""

    def __init__(self, store: PartnerStore) -> None:
        super().__init__()
        self._store = store
        # Ссылка на открытую карточку: без нее окно удалил бы сборщик мусора.
        self._edit_window: PartnerEditWindow | None = None
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setStyleSheet(STYLE_SHEET)
        self.resize(720, 560)

        logo_label = QLabel()
        logo_label.setPixmap(QPixmap(str(LOGO)).scaledToHeight(LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation))
        title_label = QLabel("Реестр партнеров")
        title_label.setObjectName("pageTitle")
        add_button = QPushButton("Добавить партнера")
        add_button.setObjectName("addButton")
        add_button.clicked.connect(self.open_add_window)
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(add_button)
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
        """Перечитать реестр из базы."""
        try:
            partners = self._store.partners()
        except psycopg.Error as error:
            self._show_partners([])
            self._status_label.setText("Не удалось загрузить партнеров")
            dialogs.show_error(self, dialogs.database_error_text("загрузить список партнеров", error))
            return
        self._show_partners(partners)
        self._status_label.setText(f"Партнеров: {len(partners)}" if partners else "Партнеров пока нет")

    def open_add_window(self) -> None:
        """Открыть пустую карточку для нового партнера."""
        self._open_card(None, None)

    def open_edit_window(self, partner_id: int) -> None:
        """Открыть карточку партнера с данными, свежими из базы."""
        try:
            partner = self._store.load(partner_id)
        except PartnerStoreError as error:
            dialogs.show_error(self, str(error))
            return
        except psycopg.Error as error:
            dialogs.show_error(self, dialogs.database_error_text("открыть карточку партнера", error))
            return
        self._open_card(partner_id, partner)

    def _open_card(self, partner_id: int | None, partner: PartnerData | None) -> None:
        try:
            partner_types = self._store.partner_types()
        except psycopg.Error as error:
            dialogs.show_error(self, dialogs.database_error_text("загрузить справочник типов партнеров", error))
            return
        window = PartnerEditWindow(self._store, partner_types, partner_id, partner, parent=self)
        window.saved.connect(self.refresh)
        self._edit_window = window
        # open() показывает карточку модально поверх главной формы: форма ждет
        # закрытия карточки, а ее список и прокрутка остаются как были.
        window.open()

    def _show_partners(self, partners: list[PartnerListItem]) -> None:
        """Заменить карточки в списке на новые."""
        while self._cards_layout.count():
            widget = self._cards_layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for partner in partners:
            card = PartnerCard(partner)
            card.open_requested.connect(self.open_edit_window)
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch(1)
