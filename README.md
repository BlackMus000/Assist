# 🤖 Личный Telegram-ассистент

## Что умеет
- 💬 Чат с ИИ (Claude)
- ✅ Управление задачами
- 📝 Заметки
- 📅 Планирование дня

---

## Деплой на Railway (бесплатно)

### 1. Получи токены

**Telegram токен:**
1. Открой @BotFather в Telegram
2. Напиши `/newbot`
3. Следуй инструкциям, получи токен

**Anthropic API ключ:**
1. Зайди на https://console.anthropic.com
2. API Keys → Create Key
3. Скопируй ключ

---

### 2. Загрузи код на GitHub

1. Создай аккаунт на https://github.com (если нет)
2. Создай новый репозиторий (New repository)
3. Загрузи все файлы проекта:
   - `bot.py`
   - `requirements.txt`
   - `Procfile`

---

### 3. Деплой на Railway

1. Зайди на https://railway.app
2. Войди через GitHub
3. New Project → Deploy from GitHub repo
4. Выбери свой репозиторий
5. Перейди в Settings → Variables и добавь:
   ```
   TELEGRAM_TOKEN = токен_от_botfather
   ANTHROPIC_API_KEY = ключ_от_anthropic
   ```
6. Railway автоматически запустит бота

---

### 4. Проверь

Открой своего бота в Telegram и напиши `/start`

---

## Локальный запуск (для теста)

```bash
pip install -r requirements.txt
export TELEGRAM_TOKEN="твой_токен"
export ANTHROPIC_API_KEY="твой_ключ"
python bot.py
```
