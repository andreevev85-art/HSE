"""
Обработчики ошибок для Telegram-бота Паникёр 3000.
Адаптировано для telebot.
"""

import logging

logger = logging.getLogger(__name__)

def error_handler(bot, update, error):
    """Глобальный обработчик ошибок для telebot"""
    try:
        logger.error(f"Ошибка в боте: {error}")
    except:
        logger.error("Ошибка в обработчике ошибок")

def send_error_message(bot, message, command: str):
    """Отправка сообщения об ошибке пользователю"""
    try:
        bot.reply_to(
            message,
            f"❌ Ошибка при выполнении команды /{command}\n"
            "Попробуйте позже или обратитесь к администратору."
        )
    except:
        logger.error(f"Не удалось отправить сообщение об ошибке для команды /{command}")

def send_callback_error(bot, call, error):
    """Обработка ошибок в callback-запросах"""
    try:
        bot.answer_callback_query(
            call.id,
            f"Ошибка: {str(error)[:50]}...",
            show_alert=True
        )
    except:
        logger.error(f"Не удалось отправить ошибку callback: {error}")