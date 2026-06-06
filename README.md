# Face Actress Search — сбор датасета

Система поиска похожих порноактрис по фотографии (Face Recognition).

**Текущий этап:** сбор и подготовка датасета фотографий для обучения / fine-tuning FaceNet.

## Структура проекта

```
face-actress-search/
├── config.yaml              # настройки парсера и фильтров
├── scrapers/
│   ├── babepedia.py         # основной источник (~17k актрис)
│   └── tpdb.py              # ThePornDB API (опционально)
├── scripts/
│   ├── scrape_actresses.py  # сбор фото и метаданных
│   └── prepare_dataset.py   # подготовка для FaceNet (следующий этап)
└── data/
    ├── raw/                 # скачанные фото (по папке на актрису)
    ├── metadata/            # JSON с метаданными
    └── processed/           # кропы лиц 160x160
```

## Источники данных

| Источник | Тип | Фото | Метаданные | Примечание |
|----------|-----|------|------------|------------|
| **[Babepedia](https://www.babepedia.com/pornstartop100)** | HTML | ✅ галереи | ✅ карьера, этничность | **Основной источник**, ~17 159 актрис |
| **[ThePornDB](https://theporndb.net)** | REST API | ✅ 1 фото | ✅ полные | Нужен API-токен, `metadataapi.net` |
| **[IAFD](https://www.iafd.com)** | HTML | ⚠️ редко | ✅ фильмография | ToS запрещает скрапинг, мало headshots |
| **Freeones** | HTML | ✅ | ✅ | Есть в Stash, нет публичного API |
| **StashDB** | GraphQL | ✅ | ✅ | Нужна регистрация, community-driven |

### Рекомендация

Для датасета face recognition лучше всего подходит **Babepedia**:
- много профильных фото (галерея + user uploads);
- поле «Years active» для фильтрации по периоду 2006–2026;
- ajax-поиск по имени.

ThePornDB — хорошее дополнение для метаданных и перекрёстной проверки имён.

## Быстрый старт

```bash
cd face-actress-search
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # опционально, для ThePornDB
```

### Тестовый прогон (1 страница, без скачивания)

```bash
python scripts/scrape_actresses.py --dry-run --max-pages 1
```

### Полный сбор с Babepedia

```bash
# Фильтр: карьера с 2006 года (настраивается в config.yaml)
python scripts/scrape_actresses.py --source babepedia

# Продолжить после остановки
python scripts/scrape_actresses.py --source babepedia --resume

# Докачать +5 фото к уже скачанным (без перекачки существующих)
python scripts/scrape_actresses.py --enrich --extra 5

# Ограничить для теста
python scripts/scrape_actresses.py --limit 50
```

### ThePornDB (опционально)

1. Получите токен: https://theporndb.net/user/api-tokens
2. Добавьте в `.env`: `TPDB_API_TOKEN=your_token`
3. В `config.yaml` установите `theporndb.enabled: true`
4. Запустите: `python scripts/scrape_actresses.py --source theporndb`

## Настройка фильтров

В `config.yaml`:

```yaml
filters:
  min_career_start: 2006   # актрисы, начавшие карьеру с 2006 (≈20 лет назад)
  max_career_end: null     # без верхней границы
```

Для диапазона «последние 5 лет» установите `min_career_start: 2021`.

## Face Recognition пайплайн

Модели (~120 МБ) скачиваются автоматически при первом запуске:
- **MTCNN** — детекция лиц (~2 МБ)
- **InceptionResnetV1** (VGGFace2) — embeddings (~107 МБ)

### 1. Установка ML-зависимостей

```bash
pip install -r requirements.txt
```

### 2. Детекция лиц и кроп 160×160

```bash
# Сэмпл на 10 актрисах (рекомендуется для первого прогона)
python scripts/prepare_dataset.py --limit 10

# Весь датасет
python scripts/prepare_dataset.py
```

Вход: `data/raw/` → Выход: `data/processed/{slug}/face_000.jpg`

### 3. Каталог лиц (mapping, без ML)

```bash
python scripts/build_mapping.py
```

Создаёт `data/index/mapping.json` — связь лиц с актрисами.

### 4. Embeddings (FaceNet, тяжёлый шаг)

```bash
python scripts/generate_embeddings.py
python scripts/generate_embeddings.py --limit 100   # сэмпл
```

Создаёт `data/index/embeddings.npy`.

### 5. FAISS-индекс

```bash
python scripts/build_index.py
```

Создаёт `data/index/faiss.index` из готовых embeddings.

### 6. Поиск top-5 (CLI)

```bash
python scripts/search.py --image path/to/photo.jpg
python scripts/search.py --image photo.jpg --json
```

### 7. NSFW-разметка (для бота)

```bash
pip install nudenet
python scripts/label_nsfw.py
```

Помечает фото как `safe` (одежда/белье) или `explicit` (нюдс).  
Бот отправляет **не-нюдс** фото той же актрисы; если все explicit — только текст top-5.

После докачки новых фото запустите снова (добавит только новые).

### 8. Telegram-бот

```bash
pip install aiogram
# В .env:
#   TELEGRAM_BOT_TOKEN=...   (@BotFather)
#   CRYPTO_PAY_TOKEN=...     (@CryptoBot → Crypto Pay → Create App)
#   CRYPTO_PAY_TESTNET=true  (тест: @CryptoTestnetBot, без реальных денег)
python -m bot.main
```

Отправьте боту фото — вернёт top-5 с процентом схожести и фото лучшего совпадения.

**Тарифы:** 3 бесплатных поиска/день, 15 поисков за $3, безлимит 30 дней за $5.  
Оплата: Telegram Stars и USDT через CryptoBot (`/buy`, `/balance`).

Для теста без лимитов: `telegram.limits.enabled: false` в `config.yaml`.

**Актриса дня:** рассылка похожих на случайную актрису (`telegram.digest` в `config.yaml`).
Кнопка **⭐** — посмотреть саму актрису дня.

**Аналитика:** события пишутся в `logs/events.jsonl` (фото, кнопки, поиски, оплаты).
Сводка: `python scripts/analytics_report.py --days 7`

### Полный прогон одной командой

```bash
python scripts/prepare_dataset.py
python scripts/build_mapping.py
python scripts/generate_embeddings.py
python scripts/build_index.py
```

## Возможные проблемы

**403 / Age Verification / Access Restricted** — Babepedia может показывать страницу верификации возраста или геоблок (UK/EU). Решения:
- VPN в разрешённый регион (US/DE и т.д.)
- Увеличить `request_delay` до 3–5 сек
- Повторить запуск через несколько минут

Скрипт явно сообщит, если получил страницу блокировки вместо списка актрис.

## Ограничения и этика

- Соблюдайте `request_delay` в конфиге — не перегружайте серверы.
- IAFD явно запрещает скрапинг в ToS — не используйте как основной источник.
- Датасет предназначен для исследования / личного проекта распознавания публичных профилей.
- Не используйте для идентификации людей без их согласия.
