"""Тексты сообщений об ошибках: что случилось и по шагам, как исправить.

Автор: Danis Arslanov

Модуль без Qt: тексты собирают и окна, и проверка данных, и работа с
базой, а показывает их dialogs.py.
"""

from collections.abc import Sequence

SAVE_AGAIN = "Нажмите «Сохранить» еще раз."


def guide_text(problem: str, steps: Sequence[str]) -> str:
    """Описание проблемы и нумерованные шаги исправления."""
    numbered = "\n".join(f"{number}. {step}" for number, step in enumerate(steps, start=1))
    return f"{problem}\n\nКак исправить:\n{numbered}"


def database_error_text(action: str, error: Exception) -> str:
    """Ошибка СУБД: что не получилось, что проверить и подробности от сервера."""
    guide = guide_text(
        f"Не удалось {action}: база данных недоступна или отклонила запрос.",
        [
            "Убедитесь, что сервер PostgreSQL запущен.",
            "Проверьте пароль к базе в переменной PGPASSWORD или в файле pgpass.conf.",
            "Проверьте, что база partners_final создана и заполнена: schema.sql, reference.sql, etl.py.",
            "Повторите действие.",
        ],
    )
    return f"{guide}\n\nПодробности: {error}"


def unexpected_error_text(error: BaseException) -> str:
    """Ошибка, которую программа не предусмотрела."""
    guide = guide_text(
        "Произошла непредвиденная ошибка, действие не выполнено.",
        [
            "Закройте это сообщение и повторите действие.",
            "Если ошибка повторяется, перезапустите приложение.",
            "Если и это не помогло, передайте разработчику файл app.log из папки практики.",
        ],
    )
    return f"{guide}\n\nПодробности: {error}"
