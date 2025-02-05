from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters.state import StateFilter
from aiogram.types import BufferedInputFile
from db import SessionLocal
from models import User, WaterLog, FoodLog, WorkoutLog
from utils import (
    get_current_temperature,
    get_food_calories,
    calculate_calorie_goal,
    calculate_water_goal
)
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import func
from datetime import datetime


router = Router()


class ProfileStates(StatesGroup):
    waiting_for_weight = State()
    waiting_for_height = State()
    waiting_for_age = State()
    waiting_for_activity = State()
    waiting_for_city = State()
    waiting_for_sex = State()
    waiting_for_calorie_goal = State()


class FoodStates(StatesGroup):
    waiting_for_food_amount = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать! Я ваш бот для расчёта норм воды и калорий.\n"
        "Используйте /set_profile для настройки профиля."
    )


@router.message(Command("help"), flags={"ignore_state": True})
async def cmd_help(message: types.Message):
    help_text = (
        "Я могу помочь вам рассчитать дневные нормы воды и калорий, "
        "а также отслеживать тренировки и питание.\n\n"
        "Доступные команды:\n"
        "/start - Начать работу с ботом\n"
        "/help - Получить справку\n"
        "/set_profile - Настроить ваш профиль\n"
        "/log_water &lt;количество&gt; - Записать количество выпитой воды (в мл)\n"
        "/log_food &lt;название продукта (на англ. языке)&gt; - Записать потреблённую еду\n"
        "/log_workout &lt;тип тренировки&gt; &lt;время (мин)&gt; - Записать тренировку\n"
        "/check_progress - Проверить прогресс по воде и калориям\n"
        "/plot_progress - Получить графики прогресса по воде и калориям\n"
        "/recommendations - Получить персональные рекомендации по питанию и тренировкам"
    )
    await message.answer(help_text)


@router.message(Command("set_profile"))
async def cmd_set_profile(message: types.Message, state: FSMContext):
    await message.answer("Введите ваш вес в кг:")
    await state.set_state(ProfileStates.waiting_for_weight)


@router.message(ProfileStates.waiting_for_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text)
        if weight <= 0 or weight > 500:
            raise ValueError
        await state.update_data(weight=weight)
        await message.answer("Введите ваш рост в см:")
        await state.set_state(ProfileStates.waiting_for_height)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение для веса.")


@router.message(ProfileStates.waiting_for_height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        height = float(message.text)
        if height <= 0 or height > 300:
            raise ValueError
        await state.update_data(height=height)
        await message.answer("Введите ваш возраст:")
        await state.set_state(ProfileStates.waiting_for_age)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение для роста.")


@router.message(ProfileStates.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        age = int(message.text)
        if age <= 0 or age > 150:
            raise ValueError
        await state.update_data(age=age)
        await message.answer("Сколько минут активности у вас в день?")
        await state.set_state(ProfileStates.waiting_for_activity)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное целое число для возраста.")


@router.message(ProfileStates.waiting_for_activity)
async def process_activity(message: types.Message, state: FSMContext):
    try:
        activity = int(message.text)
        if activity < 0 or activity > 1440:
            raise ValueError
        await state.update_data(activity=activity)
        await message.answer("В каком городе вы находитесь?")
        await state.set_state(ProfileStates.waiting_for_city)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное целое число для активности (в минутах).")


@router.message(ProfileStates.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    city = message.text.strip()
    if not city:
        await message.answer("Город не может быть пустым. Пожалуйста, введите ваш город:")
        return
    await state.update_data(city=city)
    await message.answer("Введите ваш пол (male/female):")
    await state.set_state(ProfileStates.waiting_for_sex)


@router.message(ProfileStates.waiting_for_sex)
async def process_sex(message: types.Message, state: FSMContext):
    sex = message.text.strip().lower()
    if sex not in ['male', 'female']:
        await message.answer("Пожалуйста, введите 'male' или 'female' для пола.")
        return
    await state.update_data(sex=sex)
    await message.answer("Введите вашу целевую норму калорий (или отправьте 'по умолчанию'):")
    await state.set_state(ProfileStates.waiting_for_calorie_goal)


@router.message(ProfileStates.waiting_for_calorie_goal)
async def process_calorie_goal(message: types.Message, state: FSMContext):
    data = await state.get_data()
    calorie_goal_input = message.text.strip().lower()
    if calorie_goal_input == "по умолчанию":
        calorie_goal = calculate_calorie_goal(
            weight=data.get("weight"),
            height=data.get("height"),
            age=data.get("age"),
            activity_minutes=data.get("activity"),
            sex=data.get("sex")
        )
    else:
        try:
            calorie_goal = float(message.text)
            if calorie_goal <= 0 or calorie_goal > 10000:
                raise ValueError
        except ValueError:
            await message.answer("Пожалуйста, введите корректное числовое значение для цели калорий или 'по умолчанию'.")
            return

    # Получаем температуру по API и рассчитываем норму воды
    temperature = await get_current_temperature(data.get("city"))
    if temperature is None:
        await message.answer("Не удалось получить данные о погоде. Убедитесь, что город указан правильно.")
        return

    water_goal = calculate_water_goal(
        weight=data.get("weight"),
        activity_minutes=data.get("activity"),
        temperature=temperature
    )

    user_id = message.from_user.id
    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(user_id=user_id)
        user.weight = data.get("weight")
        user.height = data.get("height")
        user.age = data.get("age")
        user.activity = data.get("activity")
        user.city = data.get("city")
        user.sex = data.get("sex")
        user.calorie_goal = calorie_goal
        session.add(user)
        session.commit()

    await message.answer(
        f"Ваш профиль успешно настроен!\n"
        f"Норма калорий: {calorie_goal:.2f} ккал.\n"
        f"Норма воды (на сегодня): {water_goal:.0f} мл."
    )
    await state.clear()


@router.message(Command("log_water"))
async def cmd_log_water(message: types.Message):
    text = message.text
    parts = text.split(maxsplit=1)  #

    # Если не передан аргумент
    if len(parts) < 2:
        await message.answer("Пожалуйста, укажите количество воды в мл. Пример: /log_water 500")
        return

    args = parts[1].strip()
    try:
        amount = float(args)
        if amount <= 0 or amount > 10000:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение для количества воды в мл.")
        return

    user_id = message.from_user.id
    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            await message.answer("Пожалуйста, сначала настройте ваш профиль с помощью /set_profile.")
            return

        water_log = WaterLog(user_id=user_id, amount=amount)
        session.add(water_log)
        session.commit()

        # Рассчитываем общую выпитую воду за сегодня
        from datetime import datetime
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        total_water = session.query(func.sum(WaterLog.amount)).filter(
            WaterLog.user_id == user_id,
            WaterLog.timestamp >= start_of_day
        ).scalar() or 0

        # Рассчитываем норму воды (заново, с учётом погоды)
        temperature = await get_current_temperature(user.city)
        water_goal = calculate_water_goal(
            weight=user.weight,
            activity_minutes=user.activity,
            temperature=temperature
        )
        remaining = water_goal - total_water
        if remaining < 0:
            remaining = 0

        await message.answer(
            f"Записано: {amount} мл.\n"
            f"Всего сегодня выпито: {total_water:.0f} мл.\n"
            f"Осталось до нормы: {remaining:.0f} мл."
        )


@router.message(Command("log_food"))
async def cmd_log_food(message: types.Message, state: FSMContext):
    text = message.text
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer("Пожалуйста, укажите название продукта. Пример: /log_food apple")
        return

    product_name = parts[1].strip().lower()
    food_info = await get_food_calories(product_name)
    if not food_info:
        await message.answer("Не удалось найти информацию о продукте. Попробуйте другой запрос.")
        return

    await state.update_data(food_info=food_info)
    await message.answer(
        f"🍎 {food_info['name']} — {food_info['calories_per_100g']} ккал на 100 г.\n"
        f"Сколько граммов вы съели?"
    )
    await state.set_state(FoodStates.waiting_for_food_amount)


@router.message(StateFilter(FoodStates.waiting_for_food_amount))
async def process_food_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0 or amount > 10000:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное числовое значение для количества в граммах.")
        return

    data = await state.get_data()
    food_info = data.get("food_info")
    if not food_info:
        await message.answer("Произошла ошибка при получении данных о продукте. Попробуйте снова.")
        await state.clear()
        return

    calories = (food_info['calories_per_100g'] * amount) / 100.0

    user_id = message.from_user.id
    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            await message.answer("Пожалуйста, сначала настройте ваш профиль с помощью /set_profile.")
            await state.clear()
            return

        # Сохраняем лог в базе
        food_log = FoodLog(
            user_id=user_id,
            product_name=food_info['name'],
            amount=amount,
            calories=calories
        )
        session.add(food_log)
        session.commit()

    await message.answer(f"Записано: {calories:.1f} ккал ({amount:.0f} г).")
    await state.clear()


@router.message(Command("log_workout"))
async def cmd_log_workout(message: types.Message):
    text = message.text
    parts = text.split(maxsplit=2)

    if len(parts) < 3:
        await message.answer("Пожалуйста, укажите тип тренировки и время в минутах. Пример: /log_workout бег 30")
        return

    workout_type = parts[1].capitalize()
    try:
        duration = int(parts[2])
        if duration <= 0 or duration > 1440:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число (в минутах) для длительности тренировки.")
        return

    user_id = message.from_user.id
    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            await message.answer("Пожалуйста, сначала настройте ваш профиль с помощью /set_profile.")
            return

        calories_per_minute = {
            'Бег': 10,
            'Йога': 8,
            'Плавание': 9,
            'Велоспорт': 11
        }
        calories_burned = calories_per_minute.get(workout_type, 7) * duration
        water_consumed = (duration // 30) * 200

        workout_log = WorkoutLog(
            user_id=user_id,
            workout_type=workout_type,
            duration=duration,
            calories_burned=calories_burned,
            water_consumed=water_consumed
        )
        session.add(workout_log)
        session.commit()

    await message.answer(
        f"🏃‍♂️ {workout_type} {duration} мин — {calories_burned} ккал.\n"
        f"Дополнительно: выпейте {water_consumed} мл воды."
    )


@router.message(Command("check_progress"))
async def cmd_check_progress(message: types.Message):
    user_id = message.from_user.id
    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            await message.answer("Пожалуйста, сначала настройте ваш профиль с помощью /set_profile.")
            return

        # Рассчитываем норму воды с учётом погоды
        temperature = await get_current_temperature(user.city)
        water_goal = calculate_water_goal(
            weight=user.weight,
            activity_minutes=user.activity,
            temperature=temperature
        )

        from datetime import datetime
        start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Сумма воды за сегодня
        total_water = session.query(func.sum(WaterLog.amount)).filter(
            WaterLog.user_id == user_id,
            WaterLog.timestamp >= start_of_day
        ).scalar() or 0

        # Сумма полученных калорий
        total_calories_consumed = session.query(func.sum(FoodLog.calories)).filter(
            FoodLog.user_id == user_id,
            FoodLog.timestamp >= start_of_day
        ).scalar() or 0

        # Сумма сожженных калорий
        total_calories_burned = session.query(func.sum(WorkoutLog.calories_burned)).filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.timestamp >= start_of_day
        ).scalar() or 0

        # Баланс калорий (получено - сожжено)
        calorie_balance = total_calories_consumed - total_calories_burned

        remaining_water = water_goal - total_water
        if remaining_water < 0:
            remaining_water = 0

        # Сколько калорий осталось до заданной цели
        if user.calorie_goal:
            remaining_calories = user.calorie_goal - calorie_balance
            if remaining_calories < 0:
                remaining_calories = 0
        else:
            remaining_calories = "—"

        progress_text = (
            "📊 Прогресс за сегодня:\n\n"
            f"💧 Вода:\n"
            f" • Выпито: {int(total_water)} мл из {int(water_goal)} мл\n"
            f" • Осталось: {int(remaining_water)} мл\n\n"
            f"🔥 Калории:\n"
            f" • Потреблено: {total_calories_consumed:.1f} ккал\n"
            f" • Сожжено: {total_calories_burned:.1f} ккал\n"
            f" • Баланс: {calorie_balance:.1f} ккал\n"
            f" • Целевая норма: {user.calorie_goal if user.calorie_goal else '—'} ккал\n"
            f" • Осталось до цели: {remaining_calories if isinstance(remaining_calories, str) else f'{remaining_calories:.1f}'} ккал"
        )
        await message.answer(progress_text)


@router.message(Command("plot_progress"))
async def cmd_progress_full(message: types.Message):
    user_id = message.from_user.id
    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            await message.answer("Сначала настройте профиль через /set_profile.")
            return

        water_data = session.query(
            func.strftime("%Y-%m-%d", WaterLog.timestamp).label("day"),
            func.sum(WaterLog.amount)
        ).filter(WaterLog.user_id == user_id).group_by("day").order_by("day").all()

        food_data = session.query(
            func.strftime("%Y-%m-%d", FoodLog.timestamp).label("day"),
            func.sum(FoodLog.calories)
        ).filter(FoodLog.user_id == user_id).group_by("day").order_by("day").all()

        workout_data = session.query(
            func.strftime("%Y-%m-%d", WorkoutLog.timestamp).label("day"),
            func.sum(WorkoutLog.calories_burned)
        ).filter(WorkoutLog.user_id == user_id).group_by("day").order_by("day").all()

    if not (water_data or food_data or workout_data):
        await message.answer("Нет данных для построения графиков. Введите логи и попробуйте снова.")
        return

    water_dict = {day: total for day, total in water_data}
    food_dict = {day: total for day, total in food_data}
    workout_dict = {day: total for day, total in workout_data}

    all_days = sorted(set(water_dict.keys()) | set(food_dict.keys()) | set(workout_dict.keys()))

    water_values = [water_dict.get(day, 0) for day in all_days]
    net_calories = [food_dict.get(day, 0) - workout_dict.get(day, 0) for day in all_days]

    temperature = await get_current_temperature(user.city)
    water_goal = calculate_water_goal(user.weight, user.activity, temperature)
    calorie_goal = user.calorie_goal if user.calorie_goal else 0

    # График по воде (PNG)
    water_fig = go.Figure()
    water_fig.add_trace(go.Scatter(x=all_days, y=water_values,
                                   mode="lines+markers", name="Выпито воды (мл)"))
    water_fig.add_trace(go.Scatter(x=all_days, y=[water_goal] * len(all_days),
                                   mode="lines", name="Норма воды (мл)",
                                   line=dict(dash='dash')))
    water_fig.update_layout(title="Прогресс по воде",
                            xaxis_title="Дата",
                            yaxis_title="Вода (мл)",
                            template="plotly_white")

    water_png = water_fig.to_image(format="png")

    # График по калориям (PNG)
    calorie_fig = go.Figure()
    calorie_fig.add_trace(go.Scatter(x=all_days, y=net_calories,
                                     mode="lines+markers", name="Баланс калорий (ккал)"))
    calorie_fig.add_trace(go.Scatter(x=all_days, y=[calorie_goal] * len(all_days),
                                     mode="lines", name="Целевая норма калорий (ккал)",
                                     line=dict(dash='dash')))
    calorie_fig.update_layout(title="Прогресс по калориям",
                              xaxis_title="Дата",
                              yaxis_title="Калории (ккал)",
                              template="plotly_white")

    calorie_png = calorie_fig.to_image(format="png")

    # Интерактивный график (HTML)
    # Объединённый график с двумя подграфиками
    html_fig = make_subplots(rows=2, cols=1,
                             subplot_titles=("Прогресс по воде", "Прогресс по калориям"),
                             vertical_spacing=0.4)
    html_fig.add_trace(
        go.Scatter(x=all_days, y=water_values, mode="lines+markers", name="Выпито воды (мл)"),
        row=1, col=1
    )
    html_fig.add_trace(
        go.Scatter(x=all_days, y=[water_goal] * len(all_days), mode="lines", name="Норма воды (мл)",
                   line=dict(dash='dash')),
        row=1, col=1
    )
    html_fig.add_trace(
        go.Scatter(x=all_days, y=net_calories, mode="lines+markers", name="Баланс калорий (ккал)"),
        row=2, col=1
    )
    html_fig.add_trace(
        go.Scatter(x=all_days, y=[calorie_goal] * len(all_days), mode="lines", name="Целевая норма калорий (ккал)",
                   line=dict(dash='dash')),
        row=2, col=1
    )
    html_fig.update_layout(title="Интерактивный график прогресса",
                           template="plotly_white",
                           height=700)
    html_fig.update_xaxes(title_text="Дата", row=1, col=1)
    html_fig.update_yaxes(title_text="Вода (мл)", row=1, col=1)
    html_fig.update_xaxes(title_text="Дата", row=2, col=1)
    html_fig.update_yaxes(title_text="Калории (ккал)", row=2, col=1)

    html_str = html_fig.to_html(full_html=True)
    html_bytes = html_str.encode("utf-8")

    water_file = BufferedInputFile(water_png, filename="progress_water.png")
    calorie_file = BufferedInputFile(calorie_png, filename="progress_calories.png")
    html_file = BufferedInputFile(html_bytes, filename="progress_interactive.html")

    await message.answer_photo(photo=water_file, caption="График прогресса по воде")
    await message.answer_photo(photo=calorie_file, caption="График прогресса по калориям")
    await message.answer_document(document=html_file, caption="Интерактивный график прогресса (откройте в браузере)")


@router.message(Command("recommendations"))
async def cmd_recommendations(message: types.Message):
    user_id = message.from_user.id
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    with SessionLocal() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            await message.answer("Сначала настройте профиль с помощью /set_profile.")
            return

        total_food = session.query(func.sum(FoodLog.calories)).filter(
            FoodLog.user_id == user_id,
            FoodLog.timestamp >= start_of_day
        ).scalar() or 0

        total_workout = session.query(func.sum(WorkoutLog.calories_burned)).filter(
            WorkoutLog.user_id == user_id,
            WorkoutLog.timestamp >= start_of_day
        ).scalar() or 0

        total_water = session.query(func.sum(WaterLog.amount)).filter(
            WaterLog.user_id == user_id,
            WaterLog.timestamp >= start_of_day
        ).scalar() or 0

    net_calories = total_food - total_workout
    calorie_goal = user.calorie_goal if user.calorie_goal else 0

    temperature = await get_current_temperature(user.city)
    water_goal = calculate_water_goal(user.weight, user.activity, temperature)
    water_diff = water_goal - total_water

    if calorie_goal > 0:
        diff_percent = ((net_calories - calorie_goal) / calorie_goal) * 100
    else:
        diff_percent = 0

    # Формируем рекомендации по калориям
    if net_calories > calorie_goal * 1.1:
        calorie_recommendation = (
            f"• <b>Калории:</b> Ваш баланс превышает целевую норму на {net_calories - calorie_goal:.0f} ккал "
            f"({diff_percent:.1f}% выше цели).\n"
            "  Рекомендуем снизить потребление высококалорийных продуктов. Попробуйте добавить в рацион:\n"
            "  – свежие овощные салаты (огурцы, брокколи, помидоры),\n"
            "  – легкие белковые блюда (куриная грудка, рыба, тофу),\n"
            "  – избегайте жареной и сильно обработанной пищи.\n"
            "  Также выполните кардио-тренировку (например, бег, плавание или велоспорт) для сжигания лишних калорий."
        )
    elif net_calories < calorie_goal * 0.9:
        calorie_recommendation = (
            f"• <b>Калории:</b> Ваш баланс ниже целевой нормы на {calorie_goal - net_calories:.0f} ккал "
            f"({abs(diff_percent):.1f}% ниже цели).\n"
            "  Возможно, вам не хватает энергии для активного дня. Рекомендуем добавить в рацион:\n"
            "  – питательные перекусы: орехи, авокадо, цельнозерновой хлеб, натуральный йогурт,\n"
            "  – продукты с полезными жирами и белком.\n"
            "  Также можно рассмотреть силовые тренировки для набора мышечной массы."
        )
    else:
        calorie_recommendation = (
            "• <b>Калории:</b> Ваш баланс в пределах нормы. Продолжайте поддерживать сбалансированное питание "
            "и умеренную физическую активность."
        )

    # Формируем рекомендации по воде
    if water_diff > 0:
        water_recommendation = (
            f"• <b>Вода:</b> Вы выпили {total_water:.0f} мл, а ваша норма составляет {water_goal:.0f} мл.\n"
            "  Рекомендуем увеличить потребление воды:\n"
            "  – пейте стакан воды каждые 30-60 минут,\n"
            "  – держите рядом бутылку с водой и устанавливайте напоминания."
        )
    else:
        water_recommendation = (
            "• <b>Вода:</b> Отлично, вы достигли или превысили норму потребления воды!"
        )

    recommendation_text = (
        "🔍 <b>Рекомендации для вас на сегодня:</b>\n\n"
        f"{calorie_recommendation}\n\n"
        f"{water_recommendation}"
    )

    await message.answer(recommendation_text, parse_mode="HTML")
