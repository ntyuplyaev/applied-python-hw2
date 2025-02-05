import aiohttp
from config import OPENWEATHERMAP_API_KEY, OPENFOODFACTS_API_URL
import difflib
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta


async def get_current_temperature(city: str) -> float:
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHERMAP_API_KEY}&units=metric"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data['main']['temp']


async def get_food_calories(product_name: str) -> dict:
    """
    Запрашивает информацию о продуктах из OpenFoodFacts,
    ищет среди них наиболее подходящий по названию продукт и возвращает словарь с названием
    и калорийностью на 100 г. Для определения калорийности сначала пытается вычислить её
    по макронутриентам (жиры, белки, углеводы). Если этих данных нет – использует energy-kcal_100g.
    Если ничего подходящего не найдено, возвращает None.
    """
    search_url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": product_name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 10  # Запрашиваем 10 продуктов
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    if data.get("count", 0) == 0:
        return None

    # Ищем продукт с наилучшим «совпадением» по названию
    products = data.get("products", [])
    best_product = None
    best_ratio = 0.0

    for prod in products:
        # Пробуем взять название из 'product_name' или 'generic_name'
        name = prod.get("product_name", "") or prod.get("generic_name", "")
        if not name:
            continue

        # Считаем коэффициент похожести
        ratio = difflib.SequenceMatcher(None, product_name.lower(), name.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_product = prod

    if not best_product:
        return None

    chosen_name = best_product.get("product_name", "").capitalize()
    nutriments = best_product.get("nutriments", {})

    # Пробуем рассчитать калорийность по макронутриентам
    try:
        fat = float(nutriments.get("fat_100g", 0))
        proteins = float(nutriments.get("proteins_100g", 0))
        carbs = float(nutriments.get("carbohydrates_100g", 0))
        # Если хотя бы одно значение не равно нулю, проводим расчёт
        if fat or proteins or carbs:
            calculated_calories = 9 * fat + 4 * (proteins + carbs)
        else:
            calculated_calories = None
    except (ValueError, TypeError):
        calculated_calories = None

    if calculated_calories is not None and calculated_calories > 0:
        calories = calculated_calories
    else:
        # Если не удалось вычислить калорийность по макроэлементам, пробуем взять energy-kcal_100g
        calories = nutriments.get("energy-kcal_100g")
        if calories is None:
            energy_kj = nutriments.get("energy_100g")
            if energy_kj:
                try:
                    calories = float(energy_kj) / 4.184  # перевод из кДж в ккал
                except (ValueError, TypeError):
                    calories = None

    if not chosen_name or calories is None:
        return None

    return {
        "name": chosen_name,
        "calories_per_100g": calories
    }


def calculate_calorie_goal(weight: float, height: float, age: int, activity_minutes: int, sex: str = 'male') -> float:
    """
    Рассчитывает дневную норму калорий по формуле:
    Калории = 10 × Вес (кг) + 6.25 × Рост (см) − 5 × Возраст + C
    Где C зависит от пола и уровня активности.
    """
    # Базовая формула BMR для мужчин: 10W + 6.25H - 5A + 5
    # Для женщин: 10W + 6.25H - 5A - 161
    if sex.lower() == 'male':
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Добавим калории за активность
    # Предположим, что 45 минут активности = 300 калорий (примерно)
    # Калории = 300 / 45 * activity_minutes
    activity_calories = (300 / 45) * activity_minutes

    total_calories = bmr + activity_calories
    return total_calories


def calculate_water_goal(weight: float, activity_minutes: int, temperature: float = None) -> float:
    """
    Рассчитывает дневную норму воды по формуле:
    Базовая норма = Вес × 30 мл/кг
    +500 мл за каждые 30 минут активности.
    +500 мл за жаркую погоду (> 25°C).
    """
    water = weight * 30  # мл
    water += (activity_minutes // 30) * 500
    if temperature and temperature > 25:
        water += 500
    return water


def get_daily_water_stats(session: Session, user_id: int, days: int = 7):
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days-1)

    results = (
        session.query(
            func.date(func.datetime("water_logs.timestamp")),
            func.sum("water_logs.amount")
        )
        .filter("water_logs.user_id == user_id")
        .filter(func.date(func.datetime("water_logs.timestamp")) >= str(start_date))
        .group_by(func.date(func.datetime("water_logs.timestamp")))
        .order_by(func.date(func.datetime("water_logs.timestamp")))
        .all()
    )

    data_dict = {}
    for r in results:
        date_str = r[0]
        total_water = r[1] or 0
        data_dict[date_str] = float(total_water)

    dates = []
    water_values = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()  # 'YYYY-MM-DD'
        dates.append(day_str)
        water_values.append(data_dict.get(day_str, 0.0))

    return dates, water_values


def get_daily_calorie_stats(session: Session, user_id: int, days: int = 7):
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days-1)

    food_results = (
        session.query(
            func.date(func.datetime("food_logs.timestamp")),
            func.sum("food_logs.calories")
        )
        .filter("food_logs.user_id == user_id")
        .filter(func.date(func.datetime("food_logs.timestamp")) >= str(start_date))
        .group_by(func.date(func.datetime("food_logs.timestamp")))
        .order_by(func.date(func.datetime("food_logs.timestamp")))
        .all()
    )

    workout_results = (
        session.query(
            func.date(func.datetime("workout_logs.timestamp")),
            func.sum("workout_logs.calories_burned")
        )
        .filter("workout_logs.user_id == user_id")
        .filter(func.date(func.datetime("workout_logs.timestamp")) >= str(start_date))
        .group_by(func.date(func.datetime("workout_logs.timestamp")))
        .order_by(func.date(func.datetime("workout_logs.timestamp")))
        .all()
    )

    food_data = {}
    for r in food_results:
        date_str = r[0]
        total_calories = r[1] or 0
        food_data[date_str] = float(total_calories)

    workout_data = {}
    for r in workout_results:
        date_str = r[0]
        total_burned = r[1] or 0
        workout_data[date_str] = float(total_burned)

    dates = []
    net_calories = []
    for i in range(days):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()
        c_in = food_data.get(day_str, 0.0)
        c_out = workout_data.get(day_str, 0.0)
        net = c_in - c_out
        dates.append(day_str)
        net_calories.append(net)

    return dates, net_calories
