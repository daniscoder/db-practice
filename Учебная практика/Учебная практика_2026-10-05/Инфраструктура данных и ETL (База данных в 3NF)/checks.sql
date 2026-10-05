-- ============================================================
-- checks.sql - проверка результата импорта одним запросом
-- Автор: Danis Arslanov
--
-- Ожидания посчитаны для выгрузок из raw/ и верны сразу после etl.py:
-- партнеры, добавленные потом через приложение, меняют счетчики.
-- В столбце passed все строки должны быть true.
-- ============================================================

SELECT check_name, actual, expected, actual = expected AS passed
FROM (
    SELECT 1 AS check_no, 'партнеров загружено' AS check_name,
           COUNT(*)::TEXT AS actual, '5' AS expected
    FROM partners
    UNION ALL
    SELECT 2, 'товаров загружено', COUNT(*)::TEXT, '3'
    FROM products
    UNION ALL
    SELECT 3, 'продаж загружено', COUNT(*)::TEXT, '5'
    FROM sales_history
    UNION ALL
    SELECT 4, 'отброшено строк', COUNT(*)::TEXT, '1'
    FROM staging.rejected_rows
    UNION ALL
    SELECT 5, 'продаж без партнера или товара', COUNT(*)::TEXT, '0'
    FROM sales_history AS s
    LEFT JOIN partners AS p ON p.partner_id = s.partner_id
    LEFT JOIN products AS pr ON pr.product_id = s.product_id
    WHERE p.partner_id IS NULL OR pr.product_id IS NULL
    UNION ALL
    SELECT 6, 'названий с лишними пробелами', COUNT(*)::TEXT, '0'
    FROM (
        SELECT partner_name AS name FROM partners
        UNION ALL
        SELECT product_name FROM products
    ) AS names
    WHERE name <> btrim(name) OR name LIKE '%  %'
    UNION ALL
    SELECT 7, 'email с пробелами или заглавными', COUNT(*)::TEXT, '0'
    FROM partners
    WHERE email <> lower(btrim(email))
    UNION ALL
    SELECT 8, 'имен с латиницей', COUNT(*)::TEXT, '0'
    FROM partners AS p
    JOIN partner_types AS t ON t.type_id = p.type_id
    WHERE t.type_name = 'ИП' AND p.partner_name ~ '[A-Za-z]'
    UNION ALL
    SELECT 9, 'даты продаж', string_agg(to_char(sale_date, 'YYYY-MM-DD'), ', ' ORDER BY sale_date),
           '2023-10-25, 2023-10-26, 2023-10-28, 2023-10-29, 2023-10-30'
    FROM sales_history
    UNION ALL
    SELECT 10, 'сумм не равных количеству на цену', COUNT(*)::TEXT, '0'
    FROM sales_history AS s
    JOIN products AS pr ON pr.product_id = s.product_id
    WHERE s.amount <> s.quantity * pr.price
) AS checks
ORDER BY check_no;
