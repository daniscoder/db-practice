"""Окно истории реализации продукции одного партнера.

Автор: Danis Arslanov
"""

import logging

import psycopg
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import dialogs
from db import CrmStore, PartnerStoreError, SaleRecord
from ui_common import APP_ICON, LOGO, STYLE_SHEET, format_quantity
from user_messages import database_error_text

TITLE_TEMPLATE = "CRM: История реализации продукции - {partner_name}"
COLUMNS = ("Товар", "Дата продажи", "Количество, шт.")
DATE_FORMAT = "%d.%m.%Y"
LOGO_HEIGHT = 40

log = logging.getLogger(__name__)


class PartnerHistoryWindow(QDialog):
    """Таблица продаж партнера: товар, дата и количество."""

    def __init__(self, partner_name: str, sales: list[SaleRecord], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE_TEMPLATE.format(partner_name=partner_name))
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setStyleSheet(STYLE_SHEET)
        self.resize(640, 460)

        logo_label = QLabel()
        logo_label.setPixmap(QPixmap(str(LOGO)).scaledToHeight(LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation))
        title_label = QLabel("История реализации продукции")
        title_label.setObjectName("pageTitle")
        partner_label = QLabel(partner_name)
        partner_label.setObjectName("partnerName")
        title_layout = QVBoxLayout()
        title_layout.addWidget(title_label)
        title_layout.addWidget(partner_label)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        header_layout.addWidget(logo_label)
        header_layout.addLayout(title_layout)
        header_layout.addStretch(1)

        self.table = QTableWidget(len(sales), len(COLUMNS))
        self.table.setObjectName("salesTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        # Дата и количество подстраиваются под содержимое заново при показе окна,
        # когда стиль уже сделал заголовки жирными; разовый расчет ширины до
        # применения стиля обрезал бы их. Товар занимает остальное место.
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for row, sale in enumerate(sales):
            self._set_cell(row, 0, sale.product_name, Qt.AlignmentFlag.AlignLeft)
            self._set_cell(row, 1, sale.sale_date.strftime(DATE_FORMAT), Qt.AlignmentFlag.AlignCenter)
            self._set_cell(row, 2, format_quantity(sale.quantity), Qt.AlignmentFlag.AlignRight)

        total_quantity = sum(sale.quantity for sale in sales)
        summary = f"Продаж: {len(sales)}, всего {format_quantity(total_quantity)} шт." if sales else "У партнера пока нет продаж"
        self.summary_label = QLabel(summary)
        self.summary_label.setObjectName("summaryLabel")

        buttons = QDialogButtonBox()
        back_button = buttons.addButton("Назад", QDialogButtonBox.ButtonRole.RejectRole)
        back_button.setObjectName("backButton")
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary_label)
        layout.addWidget(buttons)

    def _set_cell(self, row: int, column: int, text: str, alignment: Qt.AlignmentFlag) -> None:
        item = QTableWidgetItem(text)
        item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, column, item)


def open_history(store: CrmStore, partner_id: int, parent: QWidget) -> PartnerHistoryWindow | None:
    """Прочитать партнера и его продажи и открыть историю поверх parent.

    Так историю открывают и реестр, и карточка партнера. Возвращает окно,
    чтобы вызывающий хранил на него ссылку, или None, если загрузить не удалось.
    """
    try:
        partner = store.load(partner_id)
        sales = store.sales(partner_id)
    except PartnerStoreError as error:
        log.error("Не удалось открыть историю продаж партнера %s: %s", partner_id, error)
        dialogs.show_error(parent, str(error))
        return None
    except psycopg.Error as error:
        log.error("Не удалось открыть историю продаж партнера %s: %s", partner_id, error)
        dialogs.show_error(parent, database_error_text("загрузить историю продаж", error))
        return None
    window = PartnerHistoryWindow(partner.partner_name, sales, parent=parent)
    # open() показывает окно модально поверх parent: тот ждет закрытия, а
    # его содержимое, в том числе несохраненный ввод, остается как было.
    # Кнопка «Назад» просто закрывает историю и возвращает к нему.
    window.open()
    return window
