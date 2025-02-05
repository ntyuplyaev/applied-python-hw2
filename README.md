# Функционал бота (@Hw2CaloryBot)

Картинки:
![p1](images/p1.png)
![p1](images/p2.png)
![p1](images/p3.png)
![p1](images/p4.png)
![p1](images/p5.png)

## 1. Работа телеграм-бота 

- **Описание:**  
  Бот запущен с использованием библиотеки aiogram.  
- **Функционал:**  
  - Обрабатывает входящие сообщения и команды от пользователей.  
  - Запускается через функцию в `main.py`, где создаётся экземпляр бота

---

## 2. Настройка профиля пользователя 

- **Описание:**  
  Пользователь настраивает свой профиль с помощью команды `/set_profile`.  
- **Функционал:**  
  - Используется FSM для последовательного запроса информации (вес, рост, возраст, активность, город, пол, целевая норма калорий).  
  - Данные сохраняются в базе данных (модель `User`).

---

## 3. Корректный расчёт воды и калорий 

- **Описание:**  
  Вычисление целевой нормы потребления воды и калорий происходит с учётом индивидуальных параметров пользователя.  
- **Функционал:**  
  - Функция `calculate_calorie_goal(...)` рассчитывает базовую норму калорий с добавлением активности.  
  - Функция `calculate_water_goal(...)` вычисляет норму воды исходя из веса, активности и текущей температуры.

---

## 4. Использование API для погоды и расчёта калорийности 

- **Описание:**  
  Бот интегрирован с OpenWeatherMap API для получения дополнительных данных.  
- **Функционал:**  
  - **OpenWeatherMap:**  
    Функция `get_current_temperature(city: str)` получает текущую температуру по городу, что влияет на норму воды.
  - **OpenFoodFacts:**  
    Функция `get_food_calories(product_name: str)` обращается к API OpenFoodFacts для определения калорийности продуктов.

---

## 5. Логирование воды, еды и тренировок

- **Описание:**  
  Бот позволяет фиксировать данные по типам активности, обновляя состояния и сохраняя данные в базе.  
- **Функционал:**  
  - **Вода:**  
    Команда `/log_water <количество>` 
  - **Еда:**  
    Команда `/log_food <название продукта>` запрашивает название продукта, затем количество съеденных граммов, и сохраняет данные в лог (модель `FoodLog`). Здесь применяется продвинутый алгоритм определения калорийности.
  - **Тренировки:**  
    Команда `/log_workout <тип тренировки> <время (мин)>` фиксирует тренировку, рассчитывая сожжённые калории и рекомендуемое дополнительное потребление воды (модель `WorkoutLog`).

---

## 6. Отображение прогресса

- **Описание:**  
  Команда `/check_progress`

---

## Дополнительная функциональность

### A. Графики прогресса 

- **Описание:**  
  Бот генерирует графики для визуализации прогресса по воде и калориям.
- **Функционал:**  
  - **PNG картинки:**  
    `/plot_progress` генерируют два отдельных графика:
      - Один для воды: показывает выпитое количество и целевую норму воды.
      - Один для калорий: отображает баланс калорий и целевую норму калорий.
  - **Интерактивный HTML график:**  
    Генерируется объединённый интерактивный график с двумя подграфиками, который отправляется в виде HTML-файла для дальнейшего анализа в браузере.

### B. Рекомендации 

- **Описание:**  
  Бот предлагает персональные рекомендации по питанию и тренировкам на основе дневного прогресса.
- **Функционал:**  
  - Команда `/recommendations` анализирует:
      - Калорийный баланс 
      - Водный баланс (сравнение выпитого количества и нормы)
  - В зависимости от результатов:
      - Если баланс калорий превышает норму, предлагаются низкокалорийные продукты и кардио-тренировки.
      - Если баланс ниже нормы, даются рекомендации по увеличению потребления питательных перекусов и выполнению силовых упражнений.
      - Анализируется также водный баланс с рекомендациями по увеличению количества выпиваемой воды.

### C. Продвинутое определение калорийности 

- **Описание:**  
  Улучшенный алгоритм расчёта калорийности продукта, обеспечивающий более точную оценку.
- **Функционал:**  
  - Функция `get_food_calories(product_name: str)` сначала ищет информацию о продукте через OpenFoodFacts.  
  - **Основной алгоритм:**  
    Если доступны данные по макронутриентам (жиры, белки, углеводы), калорийность рассчитывается по формуле:  
    ```
    калории = 9 * жиры + 4 * (белки + углеводы)
    ```
    
    Если данные по макронутриентам отсутствуют или равны нулю, используется значение из поля `energy-kcal_100g` или `energy_100g` (с переводом из кДж в ккал).

---

## Итог

Бот успешно реализует все базовые функции, а также имеет дополнительный функционал:
- Визуализация прогресса через статичные и интерактивные графики
- Персонализированные рекомендации для коррекции питания и тренировок
- Более точный расчёт калорийности продуктов
