# panicker3000/tests/simple_bot.py (исправленная версия)
import os
import sys
import telebot
from dotenv import load_dotenv

# ============================================================================
# 1. НАСТРОЙКА ПУТЕЙ
# ============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
panicker3000_dir = os.path.dirname(current_dir)  # Папка panicker3000/
project_root = os.path.dirname(panicker3000_dir)  # Корень проекта

# Файл .env находится ВНУТРИ panicker3000/
env_path = os.path.join(panicker3000_dir, '.env')

print(f"[INFO] Ищу .env по пути: {env_path}")

# ============================================================================
# 2. ПРОВЕРКА ФАЙЛА .env
# ============================================================================
if not os.path.exists(env_path):
    print(f"❌ ОШИБКА: Файл .env не найден по пути: {env_path}")
    print("   Файл должен быть в папке panicker3000/")
    sys.exit(1)

load_dotenv(dotenv_path=env_path)
print(f"✅ .env загружен из: {env_path}")

# ============================================================================
# 3. ПОЛУЧЕНИЕ ТОКЕНА (используем TELEGRAM_BOT_TOKEN)
# ============================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TELEGRAM_TOKEN:
    print("❌ ОШИБКА: TELEGRAM_BOT_TOKEN не найден в .env")
    print("   Проверьте, что в файле есть строка:")
    print("   TELEGRAM_BOT_TOKEN=ваш_токен_здесь")
    sys.exit(1)

print(f"✅ Токен загружен. Длина: {len(TELEGRAM_TOKEN)} символов")

# ============================================================================
# 4. СОЗДАНИЕ БОТА И ОБРАБОТЧИКИ
# ============================================================================
bot = telebot.TeleBot(TELEGRAM_TOKEN)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, f"🤖 Бот запущен! .env найден в: {env_path}")


@bot.message_handler(commands=['health'])
def health_check(message):
    status = f"""
    ✅ Система в порядке!
    📁 .env: {env_path}
    🔑 Токен: {'Есть' if TELEGRAM_TOKEN else 'Нет'}
    """
    bot.reply_to(message, status)


# ============================================================================
# 5. ЗАПУСК
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Запуск бота...")
    print(f"Путь к .env: {env_path}")
    print(f"Токен: {TELEGRAM_TOKEN[:10]}...")
    print("=" * 60)

    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Ошибка: {e}")