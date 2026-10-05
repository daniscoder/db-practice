"""Окно расчета сырья на партию продукции.

Автор: Danis Arslanov
"""

import logging

import psycopg
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

import dialogs
from db import CrmStore, MaterialType, ProductType
from material_calculator import INVALID_RESULT, MaterialCalculator
from ui_common import APP_ICON, STYLE_SHEET, format_quantity
from user_messages import database_error_text, guide_text

WINDOW_TITLE = "CRM: Расчет материалов"
INITIAL_RESULT = "Заполните поля и нажмите «Рассчитать»"
INVALID_RESULT_TEXT = "Расчет невозможен: проверьте введенные данные"
DATABASE_FAILED_TEXT = "Расчет не выполнен: нет связи с базой данных"
INVALID_INPUT_TEXT = guide_text(
    "Расчет невозможен: данные введены неверно.",
    [
        "Выберите тип продукции и тип материала из списков.",
        "Укажите количество продукции целым числом больше 0.",
        "Укажите оба параметра продукции положительными числами, дробную часть можно отделить запятой.",
        "Нажмите «Рассчитать» еще раз.",
    ],
)

log = logging.getLogger(__name__)


def parse_integer(text: str) -> int | None:
    """Целое число из поля ввода; None, если это не целое."""
    try:
        return int(text.strip())
    except ValueError:
        return None


def parse_number(text: str) -> float | None:
    """Число из поля ввода; десятичная запятая тоже годится. None, если не число."""
    try:
        return float(text.strip().replace(",", "."))
    except ValueError:
        return None


class MaterialCalculatorWindow(QDialog):
    """Калькулятор сырья: типы из справочников, количество, параметры продукции."""

    def __init__(self, store: CrmStore, product_types: list[ProductType], material_types: list[MaterialType],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setStyleSheet(STYLE_SHEET)
        self.setMinimumWidth(460)
        self._calculator = MaterialCalculator(store)

        self.product_type_combo = QComboBox()
        self.product_type_combo.setObjectName("productTypeCombo")
        for item in product_types:
            self.product_type_combo.addItem(item.type_name, item.product_type_id)
        self.material_type_combo = QComboBox()
        self.material_type_combo.setObjectName("materialTypeCombo")
        for item in material_types:
            self.material_type_combo.addItem(item.type_name, item.material_type_id)
        self.quantity_edit = QLineEdit()
        self.quantity_edit.setObjectName("quantityEdit")
        self.quantity_edit.setPlaceholderText("Целое число больше 0")
        self.param_1_edit = QLineEdit()
        self.param_1_edit.setObjectName("param1Edit")
        self.param_1_edit.setPlaceholderText("Положительное число, например 2,5")
        self.param_2_edit = QLineEdit()
        self.param_2_edit.setObjectName("param2Edit")
        self.param_2_edit.setPlaceholderText("Положительное число, например 1,2")
        self.result_label = QLabel(INITIAL_RESULT)
        self.result_label.setObjectName("resultLabel")

        form = QFormLayout()
        form.addRow("Тип продукции", self.product_type_combo)
        form.addRow("Тип материала", self.material_type_combo)
        form.addRow("Количество продукции, шт.", self.quantity_edit)
        form.addRow("Параметр продукции 1", self.param_1_edit)
        form.addRow("Параметр продукции 2", self.param_2_edit)

        buttons = QDialogButtonBox()
        calculate_button = buttons.addButton("Рассчитать", QDialogButtonBox.ButtonRole.ActionRole)
        calculate_button.setObjectName("calculateButton")
        calculate_button.clicked.connect(self.calculate)
        back_button = buttons.addButton("Назад", QDialogButtonBox.ButtonRole.RejectRole)
        back_button.setObjectName("backButton")
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.result_label)
        layout.addWidget(buttons)

    def calculate(self) -> None:
        """Посчитать сырье и показать результат или объяснить ошибку."""
        # В списках лежат id типов, их и получает метод: коэффициент и процент
        # брака он сам читает из справочников в базе. Неразобранное поле уходит
        # как None, решать, годятся ли данные, должен метод, окно читает его -1.
        try:
            result = self._calculator.calculate(
                self.product_type_combo.currentData(),
                self.material_type_combo.currentData(),
                parse_integer(self.quantity_edit.text()),
                parse_number(self.param_1_edit.text()),
                parse_number(self.param_2_edit.text()),
            )
        except psycopg.Error as error:
            log.error("Не удалось рассчитать материалы: %s", error)
            self.result_label.setText(DATABASE_FAILED_TEXT)
            dialogs.show_error(self, database_error_text("прочитать справочники для расчета", error))
            return
        if result == INVALID_RESULT:
            self.result_label.setText(INVALID_RESULT_TEXT)
            dialogs.show_error(self, INVALID_INPUT_TEXT)
            return
        self.result_label.setText(f"Необходимо сырья: {format_quantity(result)} ед.")
