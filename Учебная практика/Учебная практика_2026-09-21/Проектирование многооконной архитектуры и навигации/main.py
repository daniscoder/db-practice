"""Точка входа: реестр партнеров с переходом в карточку партнера.

Автор: Danis Arslanov
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Папки заданий названы по требованию практики, по-русски и с пробелами, поэтому
# пакетами Python они быть не могут. Модули соседних заданий подключаются через
# пути поиска: каждая папка задания добавляется в sys.path, служебные каталоги
# (.idea, __pycache__ и подобные) пропускаются.
PRACTICE_DIR = Path(__file__).resolve().parent.parent
for task_dir in sorted(PRACTICE_DIR.iterdir()):
    if task_dir.is_dir() and not task_dir.name.startswith((".", "_")):
        sys.path.insert(0, str(task_dir))

import db
from main_window import MainWindow


def main() -> int:
    """Показать реестр и загрузить в него партнеров."""
    app = QApplication(sys.argv)
    window = MainWindow(db.PartnerStore())
    window.show()
    window.refresh()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
