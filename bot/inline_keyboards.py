"""
Inline-клавиатуры для Telegram-бота Паникёр 3000.
"""

from telebot import types


def get_main_menu_keyboard():
    """Клавиатура главного меню"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    buttons = [
        types.InlineKeyboardButton("📊 КАРТА ПАНИКИ", callback_data="panic_map"),
        types.InlineKeyboardButton("🌡️ ИНДЕКС ПЕРЕГРЕВА", callback_data="overheat_menu"),
        types.InlineKeyboardButton("📈 СЕГОДНЯШНИЕ ИСТЕРИКИ", callback_data="today"),
        types.InlineKeyboardButton("📊 СТАТИСТИКА ЗА НЕДЕЛЮ", callback_data="stats"),
    ]

    # Распределяем по 2 кнопки в ряд
    for i in range(0, len(buttons), 2):
        row_buttons = buttons[i:i + 2]
        if len(row_buttons) == 2:
            keyboard.row(row_buttons[0], row_buttons[1])
        else:
            keyboard.add(row_buttons[0])

    return keyboard


def get_overheat_keyboard(ticker):
    """Клавиатура для индекса перегрева акции"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    buttons = [
        types.InlineKeyboardButton("📊 ГРАФИК АКЦИИ", callback_data=f"graph_{ticker}"),
        types.InlineKeyboardButton("📈 СРАВНИТЬ С IMOEX", callback_data=f"compare_{ticker}"),
        types.InlineKeyboardButton("📋 ИСТОРИЯ СИГНАЛОВ", callback_data=f"history_{ticker}"),
        types.InlineKeyboardButton("🤔 ОБЪЯСНИТЬ СИГНАЛ", callback_data=f"explain_{ticker}"),
        types.InlineKeyboardButton("🚫 ИГНОРИРОВАТЬ 2 ЧАСА", callback_data=f"ignore_{ticker}"),
    ]

    # Первые 4 кнопки по 2 в ряд, последняя отдельно
    keyboard.row(buttons[0], buttons[1])
    keyboard.row(buttons[2], buttons[3])
    keyboard.add(buttons[4])

    return keyboard


def get_today_keyboard():
    """Клавиатура для сегодняшних сигналов"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    buttons = [
        types.InlineKeyboardButton("📊 КАРТА ПАНИКИ", callback_data="panic_map"),
        types.InlineKeyboardButton("📈 СТАТИСТИКА", callback_data="stats"),
    ]

    keyboard.row(buttons[0], buttons[1])

    return keyboard