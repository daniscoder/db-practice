"""Задание 4: сквозная проверка, база -> скидки -> окно.

Автор: Danis Arslanov
"""

from task_4_app import main


def test_load_partners_reads_database(connection):
    partners = main.load_partners()
    discounts = {p.company_name: p.discount for p in partners}
    assert discounts["Смирнов А.В."] == 0
    assert discounts["Дом и Сад"] == 15


def test_main_builds_window_from_database(qt_app, connection, monkeypatch):
    class FakeApplication:
        def __init__(self, argv):
            self.argv = argv

        def exec(self):
            return 0

    monkeypatch.setattr(main, "QApplication", FakeApplication)
    monkeypatch.setattr(main.MainWindow, "show", lambda self: None)
    assert main.main() == 0
