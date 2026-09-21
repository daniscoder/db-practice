-- ============================================================
-- queries.sql - запросы для будущего приложения
-- ============================================================


-- ------------------------------------------------------------
-- ЗАПРОС 1. Список партнеров с числом доставок,
--           отсортированный по названию.
--           LEFT JOIN - чтобы партнеры без единой отгрузки
--           тоже попали в выдачу со значением 0.
-- ------------------------------------------------------------
SELECT
    p.partner_id,
    p.company_name,
    p.inn,
    p.contact_email,
    COALESCE(p.phone, '-')          AS phone,
    p.rating,
    COUNT(d.sale_id)                AS deliveries_count,
    COALESCE(SUM(d.total_amount), 0) AS total_revenue
FROM partners p
LEFT JOIN deliveries d ON d.partner_id = p.partner_id
GROUP BY
    p.partner_id, p.company_name, p.inn,
    p.contact_email, p.phone, p.rating
ORDER BY p.company_name;


-- ------------------------------------------------------------
-- ЗАПРОС 2. Транзакция: новый партнер + его первая отгрузка.
--           Оба INSERT либо применяются вместе, либо
--           откатываются вместе - отгрузка не может
--           остаться без партнера.
-- ------------------------------------------------------------
BEGIN;

-- Товар может уже существовать - ON CONFLICT защищает от ошибки
-- по уникальному имени. После этого товар точно есть в справочнике.
INSERT INTO products (product_name)
VALUES ('Стиральный порошок "Альфа"')
ON CONFLICT (product_name) DO NOTHING;

-- Партнер и его первая отгрузка одним выражением:
-- CTE с INSERT ... RETURNING отдает partner_id сразу во вставку
-- в deliveries, без хардкода идентификатора.
--
-- ON CONFLICT (inn) DO UPDATE, а не DO NOTHING: ИНН уникален, и при
-- повторном прогоне простой INSERT падал бы на uq_partners_inn, унося
-- в откат всю транзакцию вместе с UPDATE ниже. DO NOTHING тоже не
-- годится - при конфликте RETURNING не вернул бы ни строки, отгрузка
-- молча не вставилась бы, и ошибки никто бы не заметил. DO UPDATE
-- отдает partner_id в любом случае и заодно обновляет карточку -
-- это и есть «добавление/обновление» из задания.
WITH upserted_partner AS (
    INSERT INTO partners (company_name, inn, contact_email, phone, rating)
    VALUES ('ООО "Тест-Логистика"', '7799001122', 'test@testlogistic.ru', '+74950001122', 5.00)
    ON CONFLICT (inn) DO UPDATE
        SET company_name  = EXCLUDED.company_name,
            contact_email = EXCLUDED.contact_email,
            phone         = EXCLUDED.phone,
            rating        = EXCLUDED.rating
    RETURNING partner_id
)
INSERT INTO deliveries (partner_id, product_id, sale_date, quantity, total_amount)
SELECT
    up.partner_id,
    pr.product_id,
    CURRENT_DATE,
    5,
    2500.00
FROM upserted_partner up
CROSS JOIN products pr
WHERE pr.product_name = 'Стиральный порошок "Альфа"'
  -- «Первая» отгрузка - значит только если у партнера еще нет ни одной.
  -- Без этого условия каждый повторный прогон плодил бы копии: у
  -- deliveries нет естественного уникального ключа, и ON CONFLICT
  -- здесь опереться не на что.
  AND NOT EXISTS (
      SELECT 1 FROM deliveries d
      WHERE d.partner_id = up.partner_id
  );

-- Обновление данных существующего партнера в той же транзакции
UPDATE partners
SET phone  = '+79991112299',
    rating = 4.90
WHERE inn = '7701234567';

COMMIT;
-- При любой ошибке выше вместо COMMIT выполняется ROLLBACK,
-- и база остается в исходном состоянии.


-- ------------------------------------------------------------
-- ЗАПРОС 3. Детальная история отгрузок одного партнера
--           за указанный период.
--           :partner_id, :date_from, :date_to - параметры,
--           которые подставит приложение.
-- ------------------------------------------------------------
SELECT
    d.sale_id,
    p.company_name,
    pr.product_name,
    d.sale_date,
    d.quantity                                  AS quantity_pcs,
    d.total_amount,
    ROUND(d.total_amount / d.quantity, 2)       AS price_per_unit
FROM deliveries d
JOIN partners p  ON p.partner_id = d.partner_id
JOIN products pr ON pr.product_id = d.product_id
WHERE d.partner_id = 1                      -- :partner_id
  AND d.sale_date BETWEEN DATE '2026-03-01' -- :date_from
                      AND DATE '2026-03-31' -- :date_to
ORDER BY d.sale_date;


-- Итоговая строка по тому же партнеру и периоду
SELECT
    p.company_name,
    COUNT(*)             AS deliveries_count,
    SUM(d.quantity)      AS total_quantity_pcs,
    SUM(d.total_amount)  AS total_sum
FROM deliveries d
JOIN partners p ON p.partner_id = d.partner_id
WHERE d.partner_id = 1
  AND d.sale_date BETWEEN DATE '2026-03-01' AND DATE '2026-03-31'
GROUP BY p.company_name;
