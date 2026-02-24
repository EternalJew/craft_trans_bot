# Аналіз проекту craft_trans_bot

## Що робить цей проект

**craft_trans_bot** — це Telegram-бот для транспортної компанії, яка перевозить пасажирів та посилки між Україною та Чехією (напрямок UA ↔ CZ).

### Технічний стек

| Компонент | Технологія |
|-----------|-----------|
| Мова | Python 3 |
| Telegram бот | aiogram 3.x (asyncio) |
| ORM | SQLAlchemy 2.0 |
| База даних | SQLite (`data.db`) |
| Конфіг | python-dotenv |

### Структура проекту

```
craft_trans_bot/
├── bot.py          # Основна логіка бота (FSM, команди, хендлери)
├── models.py       # SQLAlchemy моделі (Ride, Booking, Parcel)
├── database.py     # Підключення до БД
├── seed_db.py      # Початкове заповнення БД
├── requirements.txt
└── media/
    └── skoda.jpg   # Фото автопарку
```

### Моделі бази даних

```
Ride        — рейс (дата, напрямок, кількість місць)
Booking     — бронювання пасажира (прив'язане до рейсу)
Parcel      — посилка (відправник, отримувач, НП офіс)
```

### Функціонал

**Для пасажирів:**
- `/rides` — перегляд доступних рейсів
- `/book` — бронювання місця (FSM: рейс → звідки → куди → телефон → ПІБ → місця → коментар)
- `/my_bookings` — перегляд своїх бронювань за телефоном
- `/cancel_booking` — скасування бронювання
- `/change_booking` — зміна кількості місць / коментаря
- `/parcel` — реєстрація посилки (**не реалізовано, заглушка**)
- `/автопарк` — перегляд фото транспортних засобів

**Для менеджерів** (вхід через `/manager_login` + ключ):
- `/add_ride` — додавання нового рейсу
- `/ride_stats` — деталі рейсу + список броней

---

## Поточні проблеми

### Критичні

| # | Проблема | Де |
|---|---------|-----|
| 1 | **Стан менеджерів у пам'яті** — при перезапуску бота всі менеджери виходять із системи | `bot.py:38` `MANAGERS = set()` |
| 2 | **Відсутнє поле `created_at` у моделі Booking** — код намагається його читати, але в моделі немає | `models.py:17`, `bot.py:100` |
| 3 | **Дублювання імпортів** у `bot.py` (рядки 1–11 і 6–11 ідентичні) | `bot.py:1-12` |
| 4 | **`echo=True` у БД** — виводить кожен SQL-запит у консоль, не підходить для продакшну | `database.py:10` |

### Архітектурні

- Немає API — бот і база даних зв'язані безпосередньо
- SQLite не підходить для багатопотокового середовища / продакшну
- Немає логування (тільки print/stdout)
- Немає валідації телефону (приймається будь-який рядок)
- Немає функції маршрутів (зупинки по дорозі)
- Функція посилок повністю відсутня

---

## Запропоновані покращення

### 1. Розбити на бекенд + фронтенд + бот

```
craft_trans/
├── backend/         # FastAPI REST API
├── frontend/        # React/Vue дашборд для менеджерів
├── bot/             # Telegram бот (викликає API)
└── docker-compose.yml
```

---

### 2. Бекенд (FastAPI)

**Чому FastAPI:**
- Async-native (добре поєднується з aiogram)
- Автоматична документація (Swagger/OpenAPI)
- Pydantic для валідації
- Легко тестується

**Нові ендпоінти:**
```
GET    /routes              — список маршрутів (міста зі зупинками)
POST   /routes              — створити маршрут
GET    /rides               — список рейсів
POST   /rides               — створити рейс
DELETE /rides/{id}          — видалити рейс
GET    /rides/{id}/bookings — бронювання рейсу
POST   /bookings            — нове бронювання
PATCH  /bookings/{id}       — змінити бронювання
DELETE /bookings/{id}       — скасувати бронювання
POST   /parcels             — зареєструвати посилку
GET    /stats/rides         — статистика
POST   /auth/login          — вхід менеджера (JWT)
```

---

### 3. Нова модель: Маршрути зі зупинками

Ключова ідея — відокремити **маршрут** (постійний) від **рейсу** (конкретна дата + транспорт).

```python
# Маршрут: UA → CZ з зупинками
class Route(Base):
    __tablename__ = "routes"
    id           = Column(Integer, primary_key=True)
    name         = Column(String)          # "Київ → Прага"
    direction    = Column(String)          # "UA->CZ" | "CZ->UA"
    stops        = relationship("Stop", order_by="Stop.order")
    rides        = relationship("Ride", back_populates="route")

# Зупинка маршруту
class Stop(Base):
    __tablename__ = "stops"
    id        = Column(Integer, primary_key=True)
    route_id  = Column(Integer, ForeignKey("routes.id"))
    city      = Column(String)             # "Київ", "Львів", "Краків", "Прага"
    country   = Column(String)             # "UA", "CZ"
    order     = Column(Integer)            # порядок зупинки
    pickup    = Column(Boolean)            # чи можна сісти
    dropoff   = Column(Boolean)            # чи можна вийти

# Рейс тепер прив'язаний до маршруту
class Ride(Base):
    __tablename__ = "rides"
    id           = Column(Integer, primary_key=True)
    route_id     = Column(Integer, ForeignKey("routes.id"))
    date         = Column(Date)
    seats_total  = Column(Integer)
    seats_free   = Column(Integer)
    vehicle      = Column(String)          # "Skoda Superb", "VW Crafter"
    driver       = Column(String)
    price        = Column(Integer)         # ціна в грн/EUR
    route        = relationship("Route", back_populates="rides")
```

**Переваги:**
- Пасажир бачить реальні зупинки і вибирає звідки/куди
- Можна показати часи відправлення по кожній зупинці
- Легко додавати нові маршрути без зміни коду

---

### 4. Фронтенд (React або Vue)

**Дашборд для менеджерів:**
- Таблиця рейсів з фільтрацією по даті/маршруту
- Деталі рейсу: список пасажирів, завантаженість
- Редактор маршрутів і зупинок
- Статистика: бронювання по датах, популярні напрямки
- Управління посилками

**Для пасажирів (опційно — сайт-лендінг):**
- Перевірка доступних рейсів
- Онлайн бронювання без Telegram

---

### 5. Міграція бази даних

Перейти з SQLite на **PostgreSQL** (або залишити SQLite для маленьких обсягів), але додати **Alembic** для міграцій:

```bash
alembic init alembic
alembic revision --autogenerate -m "add routes and stops"
alembic upgrade head
```

---

### 6. Автентифікація менеджерів

Замість `MANAGERS = set()` у пам'яті — зберігати в БД:

```python
class Manager(Base):
    __tablename__ = "managers"
    id         = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    name       = Column(String)
    role       = Column(String, default="manager")  # "manager" | "admin"
    is_active  = Column(Boolean, default=True)
```

Для веб-дашборду — JWT токени.

---

### 7. Реалізувати посилки

Парсел-функція вже є в моделях, але не реалізована в боті:

```python
class Parcel(Base):
    # вже є в models.py, треба лише додати FSM-флоу в боті
    # + ендпоінт POST /parcels на бекенді
```

---

## Пріоритетний план дій

### Фаза 1 — Швидкі виправлення (1-2 дні)
- [ ] Виправити дублювання імпортів у `bot.py`
- [ ] Додати поле `created_at` до моделі `Booking`
- [ ] Прибрати `echo=True` у `database.py`
- [ ] Реалізувати `/parcel` FSM-флоу

### Фаза 2 — Маршрути (3-5 днів)
- [ ] Додати моделі `Route` і `Stop`
- [ ] Оновити `Ride` щоб мав зв'язок з `Route`
- [ ] Оновити `Booking` — вибір конкретних зупинок маршруту
- [ ] Оновити бот-команди (`/book` показує зупинки з маршруту)
- [ ] Зробити seed-дані для типових маршрутів UA↔CZ

### Фаза 3 — Бекенд API (1-2 тижні)
- [ ] Ініціалізувати FastAPI проект у `backend/`
- [ ] Перенести SQLAlchemy моделі туди
- [ ] Реалізувати REST ендпоінти
- [ ] Бот викликає API замість прямого доступу до БД
- [ ] JWT автентифікація для менеджерів

### Фаза 4 — Фронтенд (2-3 тижні)
- [ ] Ініціалізувати React/Vue проект у `frontend/`
- [ ] Сторінка логіну менеджера
- [ ] Дашборд: рейси, бронювання, маршрути
- [ ] Docker Compose для зручного запуску

---

## Приклад нової структури маршруту в боті

```
Пасажир: /book

Бот: Оберіть напрямок:
  🇺🇦 Україна → Чехія
  🇨🇿 Чехія → Україна

Пасажир: 🇺🇦 Україна → Чехія

Бот: Оберіть зупинку посадки:
  📍 Київ (вт, чт, нд)
  📍 Житомир
  📍 Рівне
  📍 Львів

Пасажир: 📍 Львів

Бот: Оберіть зупинку висадки:
  📍 Краків
  📍 Острава
  📍 Прага

Пасажир: 📍 Прага

Бот: Доступні рейси Львів → Прага:
  🗓 2026-03-01 | 5 місць | 1200 грн
  🗓 2026-03-05 | 8 місць | 1200 грн
```

---

*Файл створено Claude Code — аналіз репозиторію craft_trans_bot*
