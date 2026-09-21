-- ============================================================
-- seed.sql - тестовые данные
-- Автор: Danis Arslanov
--
-- Скрипт перезаливает данные целиком, поэтому переживает повторный запуск.
-- Объемы продаж подобраны на границы скидок, у «Смирнов А.В.» продаж нет.
-- ============================================================

TRUNCATE sales_history, products, partners, partner_types RESTART IDENTITY;

INSERT INTO partner_types (type_name)
VALUES ('ЗАО'), ('ООО'), ('ОАО'), ('ПАО'), ('ИП');

INSERT INTO partners (type_id, company_name, director, phone, email, address, rating)
SELECT t.type_id, v.company_name, v.director, v.phone, v.email, v.address, v.rating
FROM (VALUES
    ('ООО', 'Логистик-Экспресс', 'Иванов Иван Иванович',         '+79991112233', 'info@logex.ru',        'г. Москва, ул. Тверская, д. 1',          8),
    ('ЗАО', 'Быстрый Путь',      'Петров Петр Петрович',         '+78125554433', 'office@bystryput.ru',  'г. Санкт-Петербург, Невский пр., д. 20', 7),
    ('ПАО', 'Строймаркет',       'Сидорова Анна Сергеевна',      '+74957778899', 'sales@stroymarket.ru', 'г. Москва, ул. Строителей, д. 5',        10),
    ('ОАО', 'Дом и Сад',         'Кузнецов Олег Викторович',     '+73432223344', 'dom-sad@mail.ru',      'г. Екатеринбург, ул. Мира, д. 12',       9),
    ('ИП',  'Смирнов А.В.',      'Смирнов Алексей Владимирович', NULL,           'smirnov.av@yandex.ru', NULL,                                     5)
) AS v (type_name, company_name, director, phone, email, address, rating)
JOIN partner_types AS t ON t.type_name = v.type_name;

INSERT INTO products (product_name)
VALUES
    ('Стиральный порошок "Альфа"'),
    ('Мыло жидкое "Стандарт"'),
    ('Кондиционер для белья');

INSERT INTO sales_history (partner_id, product_id, sale_date, quantity)
SELECT p.partner_id, pr.product_id, v.sale_date, v.quantity
FROM (VALUES
    ('info@logex.ru',        'Стиральный порошок "Альфа"', DATE '2026-03-01',   5000),
    ('info@logex.ru',        'Кондиционер для белья',      DATE '2026-05-14',   4999),
    ('office@bystryput.ru',  'Мыло жидкое "Стандарт"',     DATE '2026-02-10',   6000),
    ('office@bystryput.ru',  'Стиральный порошок "Альфа"', DATE '2026-06-20',   4000),
    ('sales@stroymarket.ru', 'Мыло жидкое "Стандарт"',     DATE '2026-01-15',  20000),
    ('sales@stroymarket.ru', 'Кондиционер для белья',      DATE '2026-04-02',  20000),
    ('sales@stroymarket.ru', 'Стиральный порошок "Альфа"', DATE '2026-07-30',  10000),
    ('dom-sad@mail.ru',      'Стиральный порошок "Альфа"', DATE '2026-02-01', 150000),
    ('dom-sad@mail.ru',      'Мыло жидкое "Стандарт"',     DATE '2026-05-05', 100000),
    ('dom-sad@mail.ru',      'Кондиционер для белья',      DATE '2026-08-08',  50000)
) AS v (email, product_name, sale_date, quantity)
JOIN partners AS p  ON p.email = v.email
JOIN products AS pr ON pr.product_name = v.product_name;
