import logging

import pandas as pd

from parser import parse_city, preprocessing, save_to_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("parser.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


# Cities can be passed either as a single city string or a list of cities
cities = [
    "Краснодар",
    "Екатеринбург",
    "Казань",
    "Новосибирск",
    "Нижний Новгород",
    "Тюмень",
    "Ростов-на-Дону",
    "Самара",
    "Уфа",
    "Воронеж",
    "Челябинск",
    "Сочи",
]

# Each query is a dict with the query text and filter criteria.
# Any criterion can be omitted or set to None — in that case
# no restriction is applied for it.
queries = [
    {
        "query": "Ремонт квартир под ключ",
        "min_reviews": 20,
        "max_reviews": 80,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "Дизайн интерьера",
        "min_reviews": 20,
        "max_reviews": 80,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "Строительство загородных домов",
        "min_reviews": 20,
        "max_reviews": 80,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "Строительство бань",
        "min_reviews": 20,
        "max_reviews": 80,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "Стоматологическая клиника",
        "min_reviews": 50,
        "max_reviews": 200,
        "min_rating": 4.3,
        "max_rating": 4.8,
    },
    {
        "query": "Центр косметологии",
        "min_reviews": 50,
        "max_reviews": 200,
        "min_rating": 4.3,
        "max_rating": 4.8,
    },
    {
        "query": "Пластическая хирургия",
        "min_reviews": 50,
        "max_reviews": 200,
        "min_rating": 4.3,
        "max_rating": 4.8,
    },
    {
        "query": "Медицинский центр",
        "min_reviews": 50,
        "max_reviews": 200,
        "min_rating": 4.3,
        "max_rating": 4.8,
    },
    {
        "query": "Детейлинг",
        "min_reviews": 30,
        "max_reviews": 100,
        "min_rating": 4.4,
        "max_rating": 4.8,
    },
    {
        "query": "Тюнинг ателье",
        "min_reviews": 30,
        "max_reviews": 100,
        "min_rating": 4.4,
        "max_rating": 4.8,
    },
    {
        "query": "Автостудия",
        "min_reviews": 30,
        "max_reviews": 100,
        "min_rating": 4.4,
        "max_rating": 4.8,
    },
    {
        "query": "Автоподбор",
        "min_reviews": 30,
        "max_reviews": 100,
        "min_rating": 4.4,
        "max_rating": 4.8,
    },
    {
        "query": "Салон красоты премиум",
        "min_reviews": 40,
        "max_reviews": 150,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "СПА салон",
        "min_reviews": 40,
        "max_reviews": 150,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "Массажный салон",
        "min_reviews": 40,
        "max_reviews": 150,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "Студия перманентного макияжа",
        "min_reviews": 40,
        "max_reviews": 150,
        "min_rating": 4.2,
        "max_rating": 4.7,
    },
    {
        "query": "Банкетный зал",
        "min_reviews": 15,
        "max_reviews": 60,
        "min_rating": 4.1,
        "max_rating": 4.6,
    },
    {
        "query": "Кейтеринг",
        "min_reviews": 15,
        "max_reviews": 60,
        "min_rating": 4.1,
        "max_rating": 4.6,
    },
    {
        "query": "Фотостудия",
        "min_reviews": 15,
        "max_reviews": 60,
        "min_rating": 4.1,
        "max_rating": 4.6,
    },
    {
        "query": "Аренда коттеджей посуточно",
        "min_reviews": 15,
        "max_reviews": 60,
        "min_rating": 4.1,
        "max_rating": 4.6,
    },
]


def run(cities_input, queries_input) -> None:
    city_list = [cities_input] if isinstance(cities_input, str) else list(cities_input)

    item = queries[4]
    
    query = item["query"]
    city_dfs = []

    for city in city_list:
        try:
            df = parse_city(city, query)
        except Exception:
            logger.exception("Не удалось получить данные для %s / %s", city, query)
            continue

        if df.empty:
            logger.warning("Нет данных для %s / %s", city, query)
            continue

        df.insert(0, "Город", city)
        city_dfs.append(df)


    combined_df = pd.concat(city_dfs, ignore_index=True)

    combined_filtered = preprocessing(
        combined_df,
        min_reviews=item.get("min_reviews"),
        max_reviews=item.get("max_reviews"),
        min_rating=item.get("min_rating"),
        max_rating=item.get("max_rating"),
    )

    try:
        save_to_excel(combined_filtered, query)
    except Exception:
        logger.exception("Не удалось сохранить результат для запроса %s", query)


def main() -> None:
    run(cities, queries)


if __name__ == "__main__":
    main()
