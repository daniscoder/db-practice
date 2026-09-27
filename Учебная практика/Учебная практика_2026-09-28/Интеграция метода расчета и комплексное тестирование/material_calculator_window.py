"""Окно расчета материалов на партию продукции.

Автор: Danis Arslanov
"""

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
from db import MaterialType, ProductType
from material_calculator import INVALID_RESULT, MaterialCalculator
from ui_common import APP_ICON, STYLE_SHEET, format_quantity

WINDOW_TITLE = "CRM: Расчет материалов"
INITIAL_RESULT = "Заполните поля и нажмите «Рассчитать»"
INVALID_INPUT_TEXT = (
    "Расчет невозможен: данные введены неверно.\n\n"
    "Проверьте, что тип продукции и тип материала выбраны из списков, количество "
    "продукции - целое число больше 0, а оба параметра продукции - положительные "
    "числа (дробную часть можно отделять точкой или запятой). Исправьте данные и "
    "повторите расчет."
)


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
    """Калькулятор материала: типы из справочников, количество, параметры изделия."""

    def __init__(self, product_types: list[ProductType], material_types: list[MaterialType],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setStyleSheet(STYLE_SHEET)
        self.setMinimumWidth(460)
        # Справочники читаются из базы один раз при открытии окна и уходят в
        # метод расчета словарями: id типа -> коэффициент или процент брака.
        self._calculator = MaterialCalculator(
            {item.product_type_id: item.coefficient for item in product_types},
            {item.material_type_id: item.defect_percent for item in material_types},
        )

        self.product_type_combo = QComboBox()
        self.product_type_combo.setObjectName("productTypeCombo")
        for item in product_types:
            self.product_type_combo.addItem(f"{item.type_name} (коэффициент {item.coefficient})", item.product_type_id)
        self.material_type_combo = QComboBox()
        self.material_type_combo.setObjectName("materialTypeCombo")
        for item in material_types:
            self.material_type_combo.addItem(f"{item.type_name} (брак {item.defect_percent}%)", item.material_type_id)
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
        close_button = buttons.addButton("Закрыть", QDialogButtonBox.ButtonRole.RejectRole)
        close_button.setObjectName("closeButton")
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.result_label)
        layout.addWidget(buttons)

    def calculate(self) -> None:
        """Посчитать материал и показать результат или объяснить ошибку ввода."""
        # Неразобранное поле уходит в метод как None: решать, годятся ли
        # данные, должен сам метод расчета, а окно лишь читает его -1.
        result = self._calculator.calculate(
            self.product_type_combo.currentData(),
            self.material_type_combo.currentData(),
            parse_integer(self.quantity_edit.text()),
            parse_number(self.param_1_edit.text()),
            parse_number(self.param_2_edit.text()),
        )
        if result == INVALID_RESULT:
            self.result_label.setText("Расчет невозможен: проверьте введенные данные")
            dialogs.show_error(self, INVALID_INPUT_TEXT)
            return
        self.result_label.setText(f"Необходимо материала: {format_quantity(result)} ед.")
