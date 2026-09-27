"""Диалоговые окна трех типов: ошибка, предупреждение, информация.

Автор: Danis Arslanov

У каждого типа свой заголовок и своя пиктограмма: крестик у ошибки,
восклицательный знак у предупреждения, «i» у информации.
"""

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

ERROR_TITLE = "CRM: Ошибка"
WARNING_TITLE = "CRM: Предупреждение"
INFO_TITLE = "CRM: Информация"

DISCARD_TEXT = (
    "В карточке есть несохраненные изменения. Если закрыть ее сейчас, они будут "
    "потеряны без возможности восстановления.\n\nЗакрыть карточку без сохранения?"
)


def database_error_text(action: str, error: Exception) -> str:
    """Текст ошибки СУБД: что не получилось и что проверить."""
    return (
        f"Не удалось {action}: база данных недоступна или отклонила запрос.\n\n"
        "Проверьте, что сервер PostgreSQL запущен и пароль в переменной PGPASSWORD "
        "верный, затем повторите попытку.\n\n"
        f"Подробности: {error}"
    )


def error_box(parent: QWidget | None, text: str) -> QMessageBox:
    return QMessageBox(QMessageBox.Icon.Critical, ERROR_TITLE, text, QMessageBox.StandardButton.Ok, parent)


def info_box(parent: QWidget | None, text: str) -> QMessageBox:
    return QMessageBox(QMessageBox.Icon.Information, INFO_TITLE, text, QMessageBox.StandardButton.Ok, parent)


def discard_box(parent: QWidget | None) -> tuple[QMessageBox, QPushButton]:
    """Предупреждение о потере изменений и кнопка, которая соглашается на потерю."""
    box = QMessageBox(QMessageBox.Icon.Warning, WARNING_TITLE, DISCARD_TEXT, QMessageBox.StandardButton.NoButton, parent)
    discard_button = box.addButton("Закрыть без сохранения", QMessageBox.ButtonRole.DestructiveRole)
    stay_button = box.addButton("Вернуться к карточке", QMessageBox.ButtonRole.RejectRole)
    # Безопасный ответ по умолчанию: случайный Enter не уничтожит введенное.
    box.setDefaultButton(stay_button)
    return box, discard_button


def show_error(parent: QWidget | None, text: str) -> None:
    error_box(parent, text).exec()


def show_info(parent: QWidget | None, text: str) -> None:
    info_box(parent, text).exec()


def confirm_discard(parent: QWidget | None) -> bool:
    """Спросить, закрывать ли карточку с несохраненными изменениями."""
    box, discard_button = discard_box(parent)
    box.exec()
    return box.clickedButton() is discard_button
