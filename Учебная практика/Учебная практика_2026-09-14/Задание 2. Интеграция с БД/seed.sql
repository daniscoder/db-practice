-- ============================================================
-- seed.sql - тестовые данные
-- Автор: Danis Arslanov
--
-- Скрипт перезаливает данные целиком, поэтому переживает повторный запуск.
-- Объемы продаж подобраны точно на границы скидок из ТЗ, а у партнера
-- «Смирнов А.В.» продаж нет совсем: SUM(quantity) для него дает NULL.
-- ============================================================

TRUNCATE sales_history, products, partners, partner_types RESTART IDENTITY;

INSERT INTO partner_types (type_name)
VALUES ('ЗАО'), ('ООО'), ('ОАО'), ('ПАО'), ('ИП');

INSERT INTO partners (type_id, company_name, director, inn, phone, rating)
SELECT t.type_id, v.company_name, v.director, v.inn, v.phone, v.rating
FROM (VALUES
    ('ООО', 'Логистик-Экспресс', 'Иванов Иван Иванович',         '7701234567',   '+79991112233', 8),
    ('ЗАО', 'Быстрый Путь',      'Петров Петр Петрович',         '7812345678',   '+78125554433', 7),
    ('ПАО', 'Строймаркет',       'Сидорова Анна Сергеевна',      '5001098765',   '+74957778899', 10),
    ('ОАО', 'Дом и Сад',         'Кузнецов Олег Викторович',     '6601234567',   '+73432223344', 9),
    ('ИП',  'Смирнов А.В.',      'Смирнов Алексей Владимирович', '770112345678', NULL,           5)
) AS v (type_name, company_name, director, inn, phone, rating)
JOIN partner_types AS t ON t.type_name = v.type_name;

INSERT INTO products (product_name)
VALUES
    ('Стиральный порошок "Альфа"'),
    ('Мыло жидкое "Стандарт"'),
    ('Кондиционер для белья');

INSERT INTO sales_history (partner_id, product_id, sale_date, quantity)
SELECT p.partner_id, pr.product_id, v.sale_date, v.quantity
FROM (VALUES
    ('7701234567', 'Стиральный порошок "Альфа"', DATE '2026-03-01',   5000),
    ('7701234567', 'Кондиционер для белья',      DATE '2026-05-14',   4999),
    ('7812345678', 'Мыло жидкое "Стандарт"',     DATE '2026-02-10',   6000),
    ('7812345678', 'Стиральный порошок "Альфа"', DATE '2026-06-20',   4000),
    ('5001098765', 'Мыло жидкое "Стандарт"',     DATE '2026-01-15',  20000),
    ('5001098765', 'Кондиционер для белья',      DATE '2026-04-02',  20000),
    ('5001098765', 'Стиральный порошок "Альфа"', DATE '2026-07-30',  10000),
    ('6601234567', 'Стиральный порошок "Альфа"', DATE '2026-02-01', 150000),
    ('6601234567', 'Мыло жидкое "Стандарт"',     DATE '2026-05-05', 100000),
    ('6601234567', 'Кондиционер для белья',      DATE '2026-08-08',  50000)
) AS v (inn, product_name, sale_date, quantity)
JOIN partners AS p  ON p.inn = v.inn
JOIN products AS pr ON pr.product_name = v.product_name;

-- Проверка: суммарный объем и ожидаемая скидка по каждому партнеру
SELECT
    p.company_name,
    SUM(s.quantity) AS total_quantity
FROM partners AS p
LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
GROUP BY p.partner_id
ORDER BY p.company_name;
