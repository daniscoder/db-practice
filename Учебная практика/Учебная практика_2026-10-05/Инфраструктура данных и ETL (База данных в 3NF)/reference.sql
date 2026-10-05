-- ============================================================
-- reference.sql - справочники: типы партнеров и данные для расчета
-- материалов. Выполняется после schema.sql и до импорта etl.py.
-- Автор: Danis Arslanov
--
-- Повторный запуск безопасен: существующие строки обновляются.
-- ============================================================

-- По этому списку ETL распознает форму в начале названия партнера.
INSERT INTO partner_types (type_name)
VALUES ('АО'), ('ЗАО'), ('ИП'), ('ОАО'), ('ООО'), ('ПАО')
ON CONFLICT (type_name) DO NOTHING;

-- В выгрузках заказчика этих справочников нет, значения условные.
INSERT INTO product_types (type_name, coefficient)
VALUES
    ('Ноутбуки', 2.35),
    ('Смартфоны', 1.50),
    ('Мониторы', 4.34)
ON CONFLICT (type_name) DO UPDATE SET coefficient = EXCLUDED.coefficient;

INSERT INTO material_types (type_name, defect_percent)
VALUES
    ('Пластик', 0.95),
    ('Алюминий', 0.28),
    ('Стекло', 0.10)
ON CONFLICT (type_name) DO UPDATE SET defect_percent = EXCLUDED.defect_percent;
