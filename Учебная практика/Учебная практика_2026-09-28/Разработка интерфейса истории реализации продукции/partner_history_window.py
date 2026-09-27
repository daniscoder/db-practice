"""Окно истории реализации продукции одного партнера.

Автор: Danis Arslanov
"""

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

from db import SaleRecord
from ui_common import APP_ICON, LOGO, STYLE_SHEET, format_quantity

TITLE_TEMPLATE = "CRM: История реализации продукции - {partner_name}"
COLUMNS = ("Наименование продукции", "Количество (шт.)", "Дата продажи")
DATE_FORMAT = "%d.%m.%Y"
LOGO_HEIGHT = 40


class PartnerHistoryWindow(QDialog):
    """Таблица продаж партнера: продукция, количество и дата."""

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
        # Количество и дата подстраиваются под содержимое заново при показе окна,
        # когда стиль уже сделал заголовки жирными; разовый расчет ширины до
        # применения стиля обрезал бы их. Наименование занимает остальное место.
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for row, sale in enumerate(sales):
            self._set_cell(row, 0, sale.product_name, Qt.AlignmentFlag.AlignLeft)
            self._set_cell(row, 1, format_quantity(sale.quantity), Qt.AlignmentFlag.AlignRight)
            self._set_cell(row, 2, sale.sale_date.strftime(DATE_FORMAT), Qt.AlignmentFlag.AlignCenter)

        total_quantity = sum(sale.quantity for sale in sales)
        summary = f"Продаж: {len(sales)}, всего {format_quantity(total_quantity)} шт." if sales else "У партнера пока нет продаж"
        self.summary_label = QLabel(summary)
        self.summary_label.setObjectName("summaryLabel")

        buttons = QDialogButtonBox()
        close_button = buttons.addButton("Закрыть", QDialogButtonBox.ButtonRole.RejectRole)
        close_button.setObjectName("closeButton")
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
