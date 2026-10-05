-- ============================================================
-- etl.sql - очистка сырых выгрузок и перенос в чистые таблицы
-- Автор: Danis Arslanov
--
-- Источник - таблицы staging.*_raw, их заполняет etl.py. Скрипт можно
-- выполнять повторно, например в pgAdmin после правки правил: чистые
-- таблицы перезаливаются целиком, добавленные через приложение партнеры
-- при этом пропадают.
--
-- Каждая строка выгрузки либо переносится, либо получает причину отказа
-- в reject_reason. Отказы видны в staging.rejected_rows.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Разбор значений. Неразборчивое значение дает NULL: строка уходит в
--    отказ с причиной, а не роняет весь импорт ошибкой приведения типа.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION staging.parse_int(source_text TEXT) RETURNS INT
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE WHEN btrim(source_text) ~ '^[0-9]{1,9}$' THEN btrim(source_text)::INT END
$$;

CREATE OR REPLACE FUNCTION staging.parse_decimal(source_text TEXT) RETURNS DECIMAL
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE WHEN btrim(source_text) ~ '^[0-9]{1,12}(\.[0-9]+)?$' THEN btrim(source_text)::DECIMAL END
$$;

-- Даты в выгрузке в пяти написаниях: 25.10.2023, 2023/10/26, 2023-10-27,
-- 28-10-2023, 2023.10.29, плюс пробелы по краям. Результат - тип DATE,
-- то есть стандарт СУБД ГГГГ-ММ-ДД.
CREATE OR REPLACE FUNCTION staging.parse_date(source_text TEXT) RETURNS DATE
LANGUAGE plpgsql IMMUTABLE
AS $$
DECLARE
    -- Точка и косая черта в датах выгрузки значат то же, что дефис.
    normalized TEXT := translate(btrim(source_text), './', '--');
BEGIN
    IF normalized ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN
        RETURN to_date(normalized, 'YYYY-MM-DD');
    END IF;
    -- Год в конце - российский порядок «день, месяц, год».
    IF normalized ~ '^[0-9]{2}-[0-9]{2}-[0-9]{4}$' THEN
        RETURN to_date(normalized, 'DD-MM-YYYY');
    END IF;
    RETURN NULL;
EXCEPTION
    -- Написание верное, а такого дня нет: 31.02.2023, месяц 13.
    WHEN datetime_field_overflow OR invalid_datetime_format THEN
        RETURN NULL;
END;
$$;

-- ------------------------------------------------------------
-- 2. Очищенные строки с причиной отказа
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW staging.partners_clean AS
WITH normalized AS (
    SELECT
        line_no,
        staging.parse_int(partner_id) AS partner_id,
        -- Многоточие - мусор выгрузки («ИП ...Петров»), серии пробелов
        -- внутри названия сжимаются до одного, по краям срезаются.
        btrim(regexp_replace(replace(partner_name, '...', ''), '\s+', ' ', 'g')) AS full_name,
        btrim(inn) AS inn,
        lower(btrim(email)) AS email
    FROM staging.partners_raw
),
split AS (
    SELECT
        n.line_no,
        n.partner_id,
        t.type_id,
        t.type_name,
        -- Первое слово - форма из справочника, остаток - само название без
        -- обрамляющих кавычек: ООО "Вектор" -> тип ООО, название Вектор.
        regexp_replace(btrim(substr(n.full_name, length(split_part(n.full_name, ' ', 1)) + 1)),
                       '^"(.*)"$', '\1') AS partner_name,
        n.inn,
        n.email
    FROM normalized AS n
    LEFT JOIN partner_types AS t ON t.type_name = split_part(n.full_name, ' ', 1)
),
named AS (
    SELECT
        line_no,
        partner_id,
        type_id,
        type_name,
        -- ФИО предпринимателя пишется кириллицей, а в выгрузке инициалы
        -- набраны латинскими двойниками: A.B. вместо А.В. На вид не
        -- отличить, но поиск по «А.В.» такую строку не найдет.
        CASE WHEN type_name = 'ИП'
            THEN translate(partner_name, 'ABCEHKMOPTXaceopxy', 'АВСЕНКМОРТХасеорху')
            ELSE partner_name
        END AS partner_name,
        inn,
        email,
        row_number() OVER (PARTITION BY partner_id ORDER BY line_no) AS id_copy,
        row_number() OVER (PARTITION BY inn ORDER BY line_no) AS inn_copy,
        row_number() OVER (PARTITION BY email ORDER BY line_no) AS email_copy
    FROM split
)
SELECT
    line_no,
    partner_id,
    type_id,
    type_name,
    partner_name,
    inn,
    email,
    CASE
        WHEN partner_id IS NULL THEN 'id партнера - не целое число'
        WHEN type_id IS NULL THEN 'в начале названия нет формы из справочника partner_types'
        WHEN COALESCE(partner_name, '') = '' THEN 'пустое наименование'
        WHEN COALESCE(inn, '') !~ '^[0-9]{10}([0-9]{2})?$' THEN 'ИНН не из 10 или 12 цифр'
        WHEN COALESCE(email, '') !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' THEN 'email в неверном формате'
        WHEN id_copy > 1 THEN 'повтор id партнера'
        WHEN inn_copy > 1 THEN 'повтор ИНН'
        WHEN email_copy > 1 THEN 'повтор email'
    END AS reject_reason
FROM named;

CREATE OR REPLACE VIEW staging.products_clean AS
WITH normalized AS (
    SELECT
        line_no,
        staging.parse_int(product_id) AS product_id,
        btrim(regexp_replace(product_name, '\s+', ' ', 'g')) AS product_name,
        staging.parse_decimal(price) AS price
    FROM staging.products_raw
),
numbered AS (
    SELECT
        normalized.*,
        row_number() OVER (PARTITION BY product_id ORDER BY line_no) AS id_copy,
        row_number() OVER (PARTITION BY product_name ORDER BY line_no) AS name_copy
    FROM normalized
)
SELECT
    line_no,
    product_id,
    product_name,
    price,
    CASE
        WHEN product_id IS NULL THEN 'id товара - не целое число'
        WHEN COALESCE(product_name, '') = '' THEN 'пустое наименование'
        WHEN price IS NULL OR price <= 0 THEN 'цена - не положительное число'
        WHEN id_copy > 1 THEN 'повтор id товара'
        WHEN name_copy > 1 THEN 'повтор наименования'
    END AS reject_reason
FROM numbered;

CREATE OR REPLACE VIEW staging.sales_history_clean AS
WITH normalized AS (
    SELECT
        line_no,
        staging.parse_int(sale_id) AS sale_id,
        btrim(partner_id) AS partner_ref,
        btrim(product_id) AS product_ref,
        staging.parse_int(partner_id) AS partner_id,
        staging.parse_int(product_id) AS product_id,
        staging.parse_date(sale_date) AS sale_date,
        staging.parse_int(quantity) AS quantity,
        staging.parse_decimal(amount) AS amount,
        row_number() OVER (PARTITION BY staging.parse_int(sale_id) ORDER BY line_no) AS id_copy
    FROM staging.sales_history_raw
)
SELECT
    s.line_no,
    s.sale_id,
    s.partner_id,
    s.product_id,
    s.sale_date,
    s.quantity,
    s.amount,
    CASE
        WHEN s.sale_id IS NULL THEN 'id продажи - не целое число'
        WHEN s.id_copy > 1 THEN 'повтор id продажи'
        WHEN s.sale_date IS NULL THEN 'дата не распознана'
        WHEN s.quantity IS NULL OR s.quantity <= 0 THEN 'количество - не целое положительное число'
        WHEN s.amount IS NULL THEN 'сумма - не число'
        -- Ссылка проверяется по принятым строкам, а не по всем: продажа
        -- отброшенного партнера тоже осталась бы без партнера.
        WHEN NOT EXISTS (
            SELECT 1 FROM staging.partners_clean AS p
            WHERE p.partner_id = s.partner_id AND p.reject_reason IS NULL
        ) THEN 'партнер с id ' || COALESCE(s.partner_ref, '') || ' не найден'
        WHEN NOT EXISTS (
            SELECT 1 FROM staging.products_clean AS pr
            WHERE pr.product_id = s.product_id AND pr.reject_reason IS NULL
        ) THEN 'товар с id ' || COALESCE(s.product_ref, '') || ' не найден'
    END AS reject_reason
FROM normalized AS s;

CREATE OR REPLACE VIEW staging.rejected_rows AS
SELECT 'partners_raw.csv' AS file_name, line_no, reject_reason
FROM staging.partners_clean
WHERE reject_reason IS NOT NULL
UNION ALL
SELECT 'products_raw.csv', line_no, reject_reason
FROM staging.products_clean
WHERE reject_reason IS NOT NULL
UNION ALL
SELECT 'sales_history_raw.csv', line_no, reject_reason
FROM staging.sales_history_clean
WHERE reject_reason IS NOT NULL;

-- ------------------------------------------------------------
-- 3. Перезаливка чистых таблиц. Справочники не трогаются.
-- ------------------------------------------------------------

TRUNCATE sales_history, products, partners;

INSERT INTO partners (partner_id, type_id, partner_name, inn, email)
SELECT partner_id, type_id, partner_name, inn, email
FROM staging.partners_clean
WHERE reject_reason IS NULL;

INSERT INTO products (product_id, product_name, price)
SELECT product_id, product_name, price
FROM staging.products_clean
WHERE reject_reason IS NULL;

INSERT INTO sales_history (sale_id, partner_id, product_id, sale_date, quantity, amount)
SELECT sale_id, partner_id, product_id, sale_date, quantity, amount
FROM staging.sales_history_clean
WHERE reject_reason IS NULL;

-- id из выгрузки вставлены явно, и счетчик IDENTITY о них не знает: без
-- сдвига первый же партнер из приложения получил бы id 1 и упал на дубле.
SELECT setval(pg_get_serial_sequence('partners', 'partner_id'), COALESCE(MAX(partner_id), 0) + 1, false) FROM partners;
SELECT setval(pg_get_serial_sequence('products', 'product_id'), COALESCE(MAX(product_id), 0) + 1, false) FROM products;
SELECT setval(pg_get_serial_sequence('sales_history', 'sale_id'), COALESCE(MAX(sale_id), 0) + 1, false) FROM sales_history;

-- Итог: отброшенные строки с причинами.
SELECT file_name, line_no, reject_reason
FROM staging.rejected_rows
ORDER BY file_name, line_no;
