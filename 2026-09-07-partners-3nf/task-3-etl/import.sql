-- ============================================================
-- import.sql - загрузка очищенных данных + проверка
-- ============================================================

-- ------------------------------------------------------------
-- ВАРИАНТ А. Серверный COPY (файлы лежат на машине с сервером БД)
--            Требует прав суперпользователя / pg_read_server_files.
--            Замените /путь/к/ на реальный каталог с CSV.
-- ------------------------------------------------------------
-- COPY partners (partner_id, company_name, inn, contact_email, phone, rating)
--     FROM '/путь/к/partners_clean.csv'
--     WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

-- COPY products (product_id, product_name)
--     FROM '/путь/к/products_clean.csv'
--     WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

-- COPY deliveries (sale_id, partner_id, product_id, sale_date, quantity, total_amount)
--     FROM '/путь/к/deliveries_clean.csv'
--     WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

-- ------------------------------------------------------------
-- ВАРИАНТ Б. Клиентский \copy (работает из psql без прав суперпользователя)
-- ------------------------------------------------------------
-- CSV лежат рядом с этим файлом, поэтому путь - просто имя: psql
-- запускается из task-3-etl/. Порядок обязателен - сначала справочники,
-- иначе FK у deliveries не на что ссылаться.
-- \copy partners   (partner_id, company_name, inn, contact_email, phone, rating)         FROM 'partners_clean.csv'   WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
-- \copy products   (product_id, product_name)                                            FROM 'products_clean.csv'   WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')
-- \copy deliveries (sale_id, partner_id, product_id, sale_date, quantity, total_amount)  FROM 'deliveries_clean.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8')

-- ------------------------------------------------------------
-- ВАРИАНТ В. Прямые INSERT - если COPY недоступен
--            или если импорт делается через мастер DBeaver,
--            этот блок можно не выполнять.
-- ------------------------------------------------------------
INSERT INTO partners (company_name, inn, contact_email, phone, rating)
VALUES
    ('ООО "Логистик-Экспресс"', '7701234567', 'info@logex.ru',           '+79991112233',       4.8),
    ('ИП Петров А.В.',          '5001098765', 'petrov_delivery@mail.ru', NULL,                 4.2),
    ('ТК "Быстрый Путь"',       '7812345678', 'speedway@yandex.ru',      '+78125554433',       NULL);

INSERT INTO products (product_name)
VALUES
    ('Стиральный порошок "Альфа"'),
    ('Мыло жидкое "Стандарт"'),
    ('Кондиционер для белья');

INSERT INTO deliveries (partner_id, product_id, sale_date, quantity, total_amount)
VALUES
    (1, 1, DATE '2026-03-01',  50, 25000.00),
    (2, 2, DATE '2026-03-15', 200, 18000.50),
    (1, 3, DATE '2026-03-20',  30, 10500.00),
    (3, 2, DATE '2026-03-25', 150, 13500.00);

-- ------------------------------------------------------------
-- Если данные грузились через COPY с явными id - синхронизируем
-- счетчики IDENTITY, иначе следующий INSERT упадет на дубле ключа.
-- ------------------------------------------------------------
SELECT setval(pg_get_serial_sequence('partners',   'partner_id'), COALESCE(MAX(partner_id), 1)) FROM partners;
SELECT setval(pg_get_serial_sequence('products',   'product_id'), COALESCE(MAX(product_id), 1)) FROM products;
SELECT setval(pg_get_serial_sequence('deliveries', 'sale_id'),    COALESCE(MAX(sale_id),    1)) FROM deliveries;

-- ============================================================
-- ПРОВЕРОЧНЫЕ ЗАПРОСЫ (Задание 3)
-- ============================================================

-- Построчно по каждой таблице
SELECT COUNT(*) AS partners_count   FROM partners;    -- ожидается 3
SELECT COUNT(*) AS products_count   FROM products;    -- ожидается 3
SELECT COUNT(*) AS deliveries_count FROM deliveries;  -- ожидается 4

-- Сводная проверка одним запросом
SELECT 'partners'   AS table_name, COUNT(*) AS rows_loaded, 3 AS rows_expected FROM partners
UNION ALL
SELECT 'products',   COUNT(*), 3 FROM products
UNION ALL
SELECT 'deliveries', COUNT(*), 4 FROM deliveries
ORDER BY table_name;

-- Контроль ссылочной целостности: обе выборки должны вернуть 0 строк
SELECT d.* FROM deliveries d
LEFT JOIN partners p ON p.partner_id = d.partner_id
WHERE p.partner_id IS NULL;

SELECT d.* FROM deliveries d
LEFT JOIN products pr ON pr.product_id = d.product_id
WHERE pr.product_id IS NULL;
