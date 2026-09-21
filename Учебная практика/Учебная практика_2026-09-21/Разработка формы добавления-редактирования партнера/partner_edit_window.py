"""Карточка партнера: форма добавления и редактирования.

Автор: Danis Arslanov
"""

import psycopg
from PySide6.QtCore import Signal
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
from db import PartnerData, PartnerStore, PartnerStoreError, PartnerType
from ui_common import APP_ICON, STYLE_SHEET, format_phone
from validation import ValidationError, validate_partner_form

ADD_TITLE = "CRM: Карточка партнера [Добавление]"
EDIT_TITLE = "CRM: Карточка партнера [Редактирование]"


class PartnerEditWindow(QDialog):
    """Карточка партнера. Без partner_id - добавление, с ним - редактирование."""

    saved = Signal()

    def __init__(self, store: PartnerStore, partner_types: list[PartnerType],
                 partner_id: int | None = None, partner: PartnerData | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        # id приходит из главной формы. None - новый партнер, и сохранение
        # пойдет в INSERT; число - существующий, и сохранение пойдет в UPDATE.
        self._partner_id = partner_id
        self.setWindowTitle(ADD_TITLE if partner_id is None else EDIT_TITLE)
        self.setWindowIcon(QIcon(str(APP_ICON)))
        self.setStyleSheet(STYLE_SHEET)
        self.setMinimumWidth(480)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("nameEdit")
        self.type_combo = QComboBox()
        self.type_combo.setObjectName("typeCombo")
        # Список только для выбора, свой тип ввести нельзя. Рядом с названием
        # в данных пункта лежит type_id: в базу уходит он, а не текст.
        self.type_combo.setEditable(False)
        for partner_type in partner_types:
            self.type_combo.addItem(partner_type.type_name, partner_type.type_id)
        self.rating_edit = QLineEdit()
        self.rating_edit.setObjectName("ratingEdit")
        self.rating_edit.setPlaceholderText("Целое число от 0")
        self.address_edit = QLineEdit()
        self.address_edit.setObjectName("addressEdit")
        self.director_edit = QLineEdit()
        self.director_edit.setObjectName("directorEdit")
        self.phone_edit = QLineEdit()
        self.phone_edit.setObjectName("phoneEdit")
        self.phone_edit.setPlaceholderText("+7 (999) 123-45-67")
        self.phone_edit.setToolTip("Телефон компании: 11 цифр. Скобки, пробелы и дефисы можно не ставить.")
        self.email_edit = QLineEdit()
        self.email_edit.setObjectName("emailEdit")
        self.email_edit.setPlaceholderText("name@company.ru")
        self.email_edit.setToolTip("Email компании в формате name@company.ru. Обязательное поле.")

        form = QFormLayout()
        form.addRow("Наименование *", self.name_edit)
        form.addRow("Тип партнера", self.type_combo)
        form.addRow("Рейтинг", self.rating_edit)
        form.addRow("Адрес", self.address_edit)
        form.addRow("ФИО директора", self.director_edit)
        form.addRow("Телефон", self.phone_edit)
        form.addRow("Email *", self.email_edit)

        buttons = QDialogButtonBox()
        save_button = buttons.addButton("Сохранить", QDialogButtonBox.ButtonRole.AcceptRole)
        save_button.setObjectName("saveButton")
        back_button = buttons.addButton("Назад", QDialogButtonBox.ButtonRole.RejectRole)
        back_button.setObjectName("backButton")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("* - обязательные поля"))
        layout.addWidget(buttons)

        if partner is not None:
            self._fill(partner)
        # Снимок полей после заполнения: с ним сравнивается форма, чтобы понять,
        # есть ли несохраненные изменения.
        self._initial_state = self._state()

    def _fill(self, partner: PartnerData) -> None:
        self.name_edit.setText(partner.company_name)
        # Ищем пункт по type_id, а не по тексту: если типа уже нет в справочнике,
        # список останется пустым, и сохранение попросит выбрать тип.
        self.type_combo.setCurrentIndex(self.type_combo.findData(partner.type_id))
        self.rating_edit.setText(str(partner.rating))
        self.address_edit.setText(partner.address or "")
        self.director_edit.setText(partner.director or "")
        self.phone_edit.setText(format_phone(partner.phone) if partner.phone else "")
        self.email_edit.setText(partner.email)

    def _state(self) -> tuple:
        return (
            self.name_edit.text(),
            self.type_combo.currentData(),
            self.rating_edit.text(),
            self.address_edit.text(),
            self.director_edit.text(),
            self.phone_edit.text(),
            self.email_edit.text(),
        )

    def is_modified(self) -> bool:
        """Изменил ли пользователь что-нибудь с момента открытия карточки."""
        return self._state() != self._initial_state

    def save(self) -> None:
        """Проверить поля и записать партнера в базу."""
        try:
            data = validate_partner_form(
                company_name=self.name_edit.text(),
                type_id=self.type_combo.currentData(),
                rating=self.rating_edit.text(),
                address=self.address_edit.text(),
                director=self.director_edit.text(),
                phone=self.phone_edit.text(),
                email=self.email_edit.text(),
            )
            if self._partner_id is None:
                self._store.create(data)
                message = f"Партнер «{data.company_name}» добавлен в базу."
            else:
                self._store.update(self._partner_id, data)
                message = f"Изменения партнера «{data.company_name}» сохранены."
        except (ValidationError, PartnerStoreError) as error:
            dialogs.show_error(self, str(error))
            return
        except psycopg.Error as error:
            dialogs.show_error(self, dialogs.database_error_text("сохранить партнера", error))
            return
        dialogs.show_info(self, message)
        self.saved.emit()
        self.accept()

    def reject(self) -> None:
        # Сюда ведут кнопка «Назад», клавиша Esc и крестик окна.
        if self.is_modified() and not dialogs.confirm_discard(self):
            return
        super().reject()
