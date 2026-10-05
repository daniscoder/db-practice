"""Главная форма: реестр партнеров с поиском и переходы в карточку
партнера, историю продаж и расчет материалов.

Автор: Danis Arslanov
"""

import logging

import psycopg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import dialogs
from db import CrmStore, PartnerData, PartnerListItem, PartnerStoreError
from material_calculator_window import MaterialCalculatorWindow
from partner_edit_window import PartnerEditWindow
from partner_history_window import open_history
from ui_common import APP_ICON, LOGO, STYLE_SHEET, format_phone
from user_messages import database_error_text

WINDOW_TITLE = "CRM: Реестр партнеров"
LOGO_HEIGHT = 48
SEARCH_DELAY_MS = 300

log = logging.getLogger(__name__)


class PartnerCard(QFrame):
    """Партнер в реестре. Щелчок выбирает его, двойной щелчок открывает карточку."""

    # Сигналы, а не ссылки на методы главной формы: иначе партнер и форма держали
    # бы друг друга, и сборщик мусора разбирал бы их в произвольном порядке,
    # что в PySide6 кончается падением.
    selected = Signal(int)
    open_requested = Signal(int)

    def __init__(self, partner: PartnerListItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("partnerCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Щелчок - выбрать партнера, двойной щелчок - открыть карточку")
        # Партнер помнит только свой id: по нему соседние окна заново читают из
        # базы актуальные данные, а не показывают устаревшую копию.
        self._partner_id = partner.partner_id

        title_label = QLabel(f"{partner.type_name} | {partner.partner_name}")
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
        layout.addWidget(QLabel(f"ИНН {partner.inn}"), 1, 0)
        layout.addWidget(QLabel(partner.director or "Директор не указан"), 2, 0)
        layout.addWidget(QLabel(format_phone(partner.phone)), 3, 0)
        layout.addWidget(QLabel(f"Рейтинг: {partner.rating}"), 4, 0)

    def set_selected(self, is_selected: bool) -> None:
        self.setProperty("selected", is_selected)
        # Оформление по свойству Qt применяет только после повторной полировки.
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.selected.emit(self._partner_id)
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.open_requested.emit(self._partner_id)
        event.accept()


class MainWindow(QMainWindow):
    """Реестр партнеров и переходы в соседние окна.

    Соседние окна открываются модально поверх реестра, сам он не закрывается:
    после «Назад» поиск, выбранный партнер и прокрутка остаются прежними.
    """

    def __init__(self, store: CrmStore) -> None:
        super().__init__()
        self._store = store
        # Ссылка на открытое окно: без нее его удалил бы сборщик мусора.
        self._child_window: QDialog | None = None
        self._selected_partner_id: int | None = None
        self._cards: dict[int, PartnerCard] = {}
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setStyleSheet(STYLE_SHEET)
        self.resize(860, 600)

        logo_label = QLabel()
        logo_label.setPixmap(QPixmap(str(LOGO)).scaledToHeight(LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation))
        title_label = QLabel("Реестр партнеров")
        title_label.setObjectName("pageTitle")
        add_button = QPushButton("Добавить партнера")
        add_button.setObjectName("addButton")
        add_button.clicked.connect(self.open_add_window)
        self._history_button = QPushButton("История продаж")
        self._history_button.setObjectName("historyButton")
        self._history_button.setToolTip("Сначала выберите партнера в списке щелчком")
        self._history_button.setEnabled(False)
        self._history_button.clicked.connect(self.open_history_window)
        calculator_button = QPushButton("Расчет материалов")
        calculator_button.setObjectName("calculatorButton")
        calculator_button.clicked.connect(self.open_calculator_window)
        refresh_button = QPushButton("Обновить")
        refresh_button.setObjectName("refreshButton")
        refresh_button.clicked.connect(self.refresh)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        header_layout.addWidget(logo_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(add_button)
        header_layout.addWidget(self._history_button)
        header_layout.addWidget(calculator_button)
        header_layout.addWidget(refresh_button)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchEdit")
        self.search_edit.setPlaceholderText("Поиск по наименованию, ИНН, email или директору")
        self.search_edit.setClearButtonEnabled(True)
        # Запрос к базе уходит после паузы в наборе, а не на каждую букву.
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(SEARCH_DELAY_MS)
        self.search_timer.timeout.connect(self.refresh)
        self.search_edit.textChanged.connect(self.schedule_search)

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
        layout.addWidget(self.search_edit)
        layout.addWidget(self._status_label)
        layout.addWidget(scroll_area, 1)
        self.setCentralWidget(central_widget)

    def schedule_search(self, _text: str) -> None:
        self.search_timer.start()

    def refresh(self) -> None:
        """Перечитать реестр из базы с учетом строки поиска."""
        search = self.search_edit.text().strip()
        try:
            partners = self._store.partners(search)
        except psycopg.Error as error:
            log.error("Не удалось загрузить список партнеров: %s", error)
            self._show_partners([])
            self._status_label.setText("Не удалось загрузить партнеров")
            dialogs.show_error(self, database_error_text("загрузить список партнеров", error))
            return
        self._show_partners(partners)
        if partners:
            self._status_label.setText(f"Партнеров: {len(partners)}")
        elif search:
            self._status_label.setText(f"По запросу «{search}» партнеров не найдено")
        else:
            self._status_label.setText("Партнеров пока нет")

    def select_partner(self, partner_id: int) -> None:
        """Выделить партнера в списке и разрешить открыть его историю продаж."""
        for card_partner_id, card in self._cards.items():
            card.set_selected(card_partner_id == partner_id)
        self._selected_partner_id = partner_id
        self._history_button.setEnabled(True)

    def open_add_window(self) -> None:
        """Открыть пустую карточку для нового партнера."""
        self._open_card(None, None)

    def open_edit_window(self, partner_id: int) -> None:
        """Открыть карточку партнера с данными, свежими из базы."""
        try:
            partner = self._store.load(partner_id)
        except PartnerStoreError as error:
            log.error("Не удалось открыть карточку партнера %s: %s", partner_id, error)
            dialogs.show_error(self, str(error))
            return
        except psycopg.Error as error:
            log.error("Не удалось открыть карточку партнера %s: %s", partner_id, error)
            dialogs.show_error(self, database_error_text("открыть карточку партнера", error))
            return
        self._open_card(partner_id, partner)

    def open_history_window(self) -> None:
        """Открыть историю продаж выбранного партнера."""
        self._child_window = open_history(self._store, self._selected_partner_id, self)

    def open_calculator_window(self) -> None:
        """Открыть расчет материалов со списками типов из базы."""
        try:
            product_types = self._store.product_types()
            material_types = self._store.material_types()
        except psycopg.Error as error:
            log.error("Не удалось загрузить справочники для расчета материалов: %s", error)
            dialogs.show_error(self, database_error_text("загрузить справочники типов продукции и материалов", error))
            return
        self._show_window(MaterialCalculatorWindow(self._store, product_types, material_types, parent=self))

    def _open_card(self, partner_id: int | None, partner: PartnerData | None) -> None:
        try:
            partner_types = self._store.partner_types()
        except psycopg.Error as error:
            log.error("Не удалось загрузить справочник типов партнеров: %s", error)
            dialogs.show_error(self, database_error_text("загрузить справочник типов партнеров", error))
            return
        window = PartnerEditWindow(self._store, partner_types, partner_id, partner, parent=self)
        # После записи в базу карточка шлет saved, и реестр перечитывается сам.
        window.saved.connect(self.refresh)
        self._show_window(window)

    def _show_window(self, window: QDialog) -> None:
        self._child_window = window
        window.open()

    def _show_partners(self, partners: list[PartnerListItem]) -> None:
        """Заменить партнеров в списке на новых, сохранив выбор, если партнер остался."""
        while self._cards_layout.count():
            widget = self._cards_layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._cards = {}
        for partner in partners:
            card = PartnerCard(partner)
            card.selected.connect(self.select_partner)
            card.open_requested.connect(self.open_edit_window)
            self._cards[partner.partner_id] = card
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch(1)
        if self._selected_partner_id in self._cards:
            self.select_partner(self._selected_partner_id)
        else:
            self._selected_partner_id = None
            self._history_button.setEnabled(False)
