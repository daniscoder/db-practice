"""Журнал ошибок приложения в файл app.log.

Автор: Danis Arslanov

Каждая запись: дата и время, уровень, модуль-источник и текст ошибки.
"""

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_path: Path) -> logging.Handler:
    """Писать предупреждения и ошибки всех модулей в файл log_path.

    Возвращает обработчик, чтобы его можно было снять, например в тестах.
    """
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.WARNING)
    return handler
