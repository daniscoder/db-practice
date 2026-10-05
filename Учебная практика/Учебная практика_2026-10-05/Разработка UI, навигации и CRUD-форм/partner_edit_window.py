"""Карточка партнера: форма добавления и редактирования.

Автор: Danis Arslanov
"""

import logging

import psycopg
from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QIcon, QRegularExpressionValidator
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
from db import CrmStore, PartnerData, PartnerStoreError, PartnerType
from partner_history_window import PartnerHistoryWindow, open_history
from ui_common import APP_ICON, STYLE_SHEET, format_phone
from user_messages import database_error_text
from validation import ValidationError, validate_partner_form

ADD_TITLE = "CRM: Карточка партнера [Добавление]"
EDIT_TITLE = "CRM: Карточка партнера [Редактирование]"

log = logging.getLogger(__name__)


def input_filter(pattern: str, parent: QWidget) -> QRegularExpressionValidator:
    """Фильтр ввода: символы, которые не подходят под шаблон, в поле не попадут."""
    return QRegularExpressionValidator(QRegularExpression(pattern), parent)


class PartnerEditWindow(QDialog):
    """Карточка партнера. Без partner_id - добавление, с ним - редактирование."""

    saved = Signal()

    def __init__(self, store: CrmStore, partner_types: list[PartnerType],
                 partner_id: int | None = None, partner: PartnerData | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        # Между окнами передается только id партнера, а не объект с данными:
        # None - новый партнер, сохранение пойдет в INSERT; число - существующий,
        # сохранение пойдет в UPDATE, а история продаж загрузится по нему из базы.
        self._partner_id = partner_id
        self._history_window: PartnerHistoryWindow | None = None
        self.setWindowTitle(ADD_TITLE if partner_id is None else EDIT_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setStyleSheet(STYLE_SHEET)
        self.setMinimumWidth(500)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.name_edit.setPlaceholderText("Название без формы, например Вектор")
        self.type_combo = QComboBox()
        self.type_combo.setObjectName("typeCombo")
        # В данных пункта лежит type_id: в базу уходит он, а не текст.
        for partner_type in partner_types:
            self.type_combo.addItem(partner_type.type_name, partner_type.type_id)
        self.inn_edit = QLineEdit()
        self.inn_edit.setObjectName("innEdit")
        self.inn_edit.setPlaceholderText("10 или 12 цифр")
        self.inn_edit.setValidator(input_filter(r"\d{0,12}", self.inn_edit))
        self.rating_edit = QLineEdit()
        self.rating_edit.setObjectName("ratingEdit")
        self.rating_edit.setPlaceholderText("Целое число от 0")
        self.rating_edit.setValidator(input_filter(r"\d{0,6}", self.rating_edit))
        self.address_edit = QLineEdit()
        self.address_edit.setObjectName("addressEdit")
        self.address_edit.setPlaceholderText("Индекс, город, улица, дом")
        self.director_edit = QLineEdit()
        self.director_edit.setObjectName("directorEdit")
        self.director_edit.setPlaceholderText("Фамилия Имя Отчество")
        self.phone_edit = QLineEdit()
        self.phone_edit.setObjectName("phoneEdit")
        self.phone_edit.setPlaceholderText("+7 (999) 123-45-67")
        self.phone_edit.setToolTip("11 цифр. Скобки, пробелы и дефисы можно не ставить.")
        self.phone_edit.setValidator(input_filter(r"[0-9+()\s-]{0,20}", self.phone_edit))
        self.email_edit = QLineEdit()
        self.email_edit.setObjectName("emailEdit")
        self.email_edit.setPlaceholderText("name@company.ru")

        form = QFormLayout()
        form.addRow("Наименование *", self.name_edit)
        form.addRow("Тип *", self.type_combo)
        form.addRow("ИНН *", self.inn_edit)
        form.addRow("Рейтинг *", self.rating_edit)
        form.addRow("Адрес", self.address_edit)
        form.addRow("Директор", self.director_edit)
        form.addRow("Телефон", self.phone_edit)
        form.addRow("Email *", self.email_edit)

        buttons = QDialogButtonBox()
        save_button = buttons.addButton("Сохранить", QDialogButtonBox.ButtonRole.AcceptRole)
        save_button.setObjectName("saveButton")
        if partner_id is not None:
            history_button = buttons.addButton("История продаж", QDialogButtonBox.ButtonRole.ActionRole)
            history_button.setObjectName("historyButton")
            history_button.clicked.connect(self.open_history_window)
        back_button = buttons.addButton("Назад", QDialogButtonBox.ButtonRole.RejectRole)
        back_button.setObjectName("backButton")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("* - обязательные поля"))
        layout.addWidget(buttons)

        if partner is None:
            self.rating_edit.setText("0")
        else:
            self._fill(partner)
        # Снимок полей после заполнения: с ним сравнивается форма, чтобы понять,
        # есть ли несохраненные изменения.
        self._initial_state = self._state()

    def _fill(self, partner: PartnerData) -> None:
        self.name_edit.setText(partner.partner_name)
        # Пункт ищется по type_id: если типа уже нет в справочнике, список
        # останется пустым, и сохранение попросит выбрать тип.
        self.type_combo.setCurrentIndex(self.type_combo.findData(partner.type_id))
        self.inn_edit.setText(partner.inn)
        self.rating_edit.setText(str(partner.rating))
        self.address_edit.setText(partner.address or "")
        self.director_edit.setText(partner.director or "")
        self.phone_edit.setText(format_phone(partner.phone) if partner.phone else "")
        self.email_edit.setText(partner.email)

    def _state(self) -> tuple:
        return (
            self.name_edit.text(),
            self.type_combo.currentData(),
            self.inn_edit.text(),
            self.rating_edit.text(),
            self.address_edit.text(),
            self.director_edit.text(),
            self.phone_edit.text(),
            self.email_edit.text(),
        )

    def is_modified(self) -> bool:
        """Изменил ли пользователь что-нибудь с момента открытия карточки."""
        return self._state() != self._initial_state

    def open_history_window(self) -> None:
        """История продаж этого партнера поверх карточки; ввод в карточке сохраняется."""
        self._history_window = open_history(self._store, self._partner_id, self)

    def save(self) -> None:
        """Проверить поля и записать партнера в базу."""
        try:
            data = validate_partner_form(
                partner_name=self.name_edit.text(),
                type_id=self.type_combo.currentData(),
                inn=self.inn_edit.text(),
                rating=self.rating_edit.text(),
                address=self.address_edit.text(),
                director=self.director_edit.text(),
                phone=self.phone_edit.text(),
                email=self.email_edit.text(),
            )
            if self._partner_id is None:
                self._store.create(data)
                message = f"Партнер «{data.partner_name}» добавлен в базу."
            else:
                self._store.update(self._partner_id, data)
                message = f"Изменения партнера «{data.partner_name}» сохранены."
        except (ValidationError, PartnerStoreError) as error:
            log.warning("Карточка партнера не сохранена: %s", error)
            dialogs.show_error(self, str(error))
            return
        except psycopg.Error as error:
            log.error("Не удалось сохранить партнера: %s", error)
            dialogs.show_error(self, database_error_text("сохранить партнера", error))
            return
        dialogs.show_info(self, message)
        self.saved.emit()
        self.accept()

    def reject(self) -> None:
        # Сюда ведут кнопка «Назад», клавиша Esc и крестик окна.
        if self.is_modified() and not dialogs.confirm_discard(self):
            return
        super().reject()
