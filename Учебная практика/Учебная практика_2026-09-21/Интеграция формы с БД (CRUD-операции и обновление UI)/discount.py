"""Расчет индивидуальной скидки партнера по суммарному объему продаж.

Автор: Danis Arslanov
"""

# Нижняя граница объема (включительно) и скидка, которая с нее начинается.
# Границы идут по убыванию: первая, до которой объем дотянулся, и дает ответ.
DISCOUNT_TIERS = (
    (300_000, 15),
    (50_000, 10),
    (10_000, 5),
)


def calculate_partner_discount(total_quantity: int | None) -> int:
    """Вернуть скидку партнера в процентах.

    None означает, что продаж у партнера нет совсем: SUM по пустому набору
    строк в SQL дает NULL. Такой партнер получает 0%, как при нулевом объеме.
    """
    if total_quantity is None:
        return 0
    if total_quantity < 0:
        raise ValueError(f"Объем продаж не может быть отрицательным: {total_quantity}")
    for threshold, discount in DISCOUNT_TIERS:
        if total_quantity >= threshold:
            return discount
    return 0
