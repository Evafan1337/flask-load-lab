"""Демонстрационный каталог. Цены указаны в целых рублях."""

PRODUCTS = {
    "notebook": {
        "name": "Тетрадь в клетку, 48 листов",
        "category": "Бумага",
        "price": 79,
        "description": "Тетрадь формата A5 с полями и бумажной обложкой.",
    },
    "pen": {
        "name": "Синяя шариковая ручка",
        "category": "Письмо",
        "price": 49,
        "description": "Синие чернила и пишущий узел 0,7 мм.",
    },
    "pencils": {
        "name": "Набор карандашей HB, 3 шт.",
        "category": "Письмо",
        "price": 119,
        "description": "Три графитовых карандаша твёрдости HB.",
    },
    "notepad": {
        "name": "Блокнот A5, 80 листов",
        "category": "Бумага",
        "price": 249,
        "description": "Блокнот в линейку с переплётом на пружине.",
    },
    "eraser": {
        "name": "Ластик",
        "category": "Аксессуары",
        "price": 39,
        "description": "Мягкий ластик для графитового карандаша.",
    },
    "ruler": {
        "name": "Линейка, 20 см",
        "category": "Аксессуары",
        "price": 59,
        "description": "Прозрачная пластиковая линейка с миллиметровой шкалой.",
    },
    "folder": {
        "name": "Папка на кнопке, A4",
        "category": "Аксессуары",
        "price": 89,
        "description": "Полупрозрачная папка для документов формата A4.",
    },
    "paper": {
        "name": "Бумага A4, 100 листов",
        "category": "Бумага",
        "price": 199,
        "description": "Офисная бумага плотностью 80 г/м².",
    },
}

CATEGORIES = tuple(dict.fromkeys(product["category"] for product in PRODUCTS.values()))
MAX_QUANTITY = 99
