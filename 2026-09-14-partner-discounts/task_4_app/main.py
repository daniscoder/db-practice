"""Точка входа: окно CRM со списком партнеров и их скидками из базы.

Автор: Danis Arslanov
"""

import sys

from PySide6.QtWidgets import QApplication

from task_2_database import db
from task_3_ui.main_window import MainWindow


def load_partners() -> list[db.Partner]:
    """Прочитать партнеров из базы. Подключение живет только на время чтения."""
    with db.connect() as connection:
        return db.fetch_partners_with_discounts(connection)


def main() -> int:
    """Показать окно и загрузить в него партнеров."""
    app = QApplication(sys.argv)
    window = MainWindow(load_partners)
    window.show()
    window.refresh()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
