"""Диалоговые окна: ошибка, предупреждение, информация и перехват
непредвиденных исключений.

Автор: Danis Arslanov
"""

import logging
import sys
from types import TracebackType

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from user_messages import unexpected_error_text

ERROR_TITLE = "CRM: Ошибка"
WARNING_TITLE = "CRM: Предупреждение"
INFO_TITLE = "CRM: Информация"

DISCARD_TEXT = (
    "В карточке есть несохраненные изменения. Если вернуться сейчас, они будут "
    "потеряны безвозвратно.\n\nВернуться без сохранения?"
)
DISCARD_BUTTON_TEXT = "Вернуться без сохранения"
STAY_BUTTON_TEXT = "Остаться в карточке"

log = logging.getLogger(__name__)


def error_box(parent: QWidget | None, text: str) -> QMessageBox:
    return QMessageBox(QMessageBox.Icon.Critical, ERROR_TITLE, text, QMessageBox.StandardButton.Ok, parent)


def info_box(parent: QWidget | None, text: str) -> QMessageBox:
    return QMessageBox(QMessageBox.Icon.Information, INFO_TITLE, text, QMessageBox.StandardButton.Ok, parent)


def discard_box(parent: QWidget | None) -> tuple[QMessageBox, QPushButton]:
    """Предупреждение о потере изменений и кнопка, которая соглашается на потерю."""
    box = QMessageBox(QMessageBox.Icon.Warning, WARNING_TITLE, DISCARD_TEXT, QMessageBox.StandardButton.NoButton, parent)
    discard_button = box.addButton(DISCARD_BUTTON_TEXT, QMessageBox.ButtonRole.DestructiveRole)
    stay_button = box.addButton(STAY_BUTTON_TEXT, QMessageBox.ButtonRole.RejectRole)
    # Безопасный ответ по умолчанию: случайный Enter не уничтожит введенное.
    box.setDefaultButton(stay_button)
    return box, discard_button


def show_error(parent: QWidget | None, text: str) -> None:
    error_box(parent, text).exec()


def show_info(parent: QWidget | None, text: str) -> None:
    info_box(parent, text).exec()


def confirm_discard(parent: QWidget | None) -> bool:
    """Спросить, уходить ли из карточки с несохраненными изменениями."""
    box, discard_button = discard_box(parent)
    box.exec()
    return box.clickedButton() is discard_button


def handle_unexpected_error(error_type: type[BaseException], error: BaseException,
                            traceback: TracebackType | None) -> None:
    """Замена sys.excepthook: исключение, не пойманное в обработчике окна,
    записывается в журнал и показывается сообщением, а приложение работает дальше.

    Ctrl+C в консоли по-прежнему завершает программу.
    """
    if issubclass(error_type, KeyboardInterrupt):
        sys.__excepthook__(error_type, error, traceback)
        return
    log.critical("Непредвиденная ошибка", exc_info=(error_type, error, traceback))
    show_error(None, unexpected_error_text(error))
