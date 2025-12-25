"""
Шаблоны сообщений для Telegram-бота Паникёр 3000.
"""

from datetime import datetime
from typing import List, Optional

# Импорт Pydantic схем
try:
    from utils.schemas import PanicSignal
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    PanicSignal = None

def get_main_menu_template(user_name, bot_status, exchange_status,
                           last_check, alerts_enabled, last_panic_time,
                           last_panic_ticker, signals_today):
    """Шаблон главного меню (полный)"""
    alert_status = "🟢 ВКЛ" if alerts_enabled else "🔴 ВЫКЛ"

    return f"""
🤖 ПАНИКЁР 3000 | v1.0
Отряд контроля рыночной паники

━━━━━━━━━━━━━━━━━━━━━━━━━
Статус: {bot_status}
Биржа: {exchange_status}
Последняя проверка: {last_check}

📋 БЫСТРЫЙ ДОСТУП:

[📊 КАРТА ПАНИКИ] - тепловая карта
[📊 ИНДЕКС ПЕРЕГРЕВА] - HP-бар акции
[📈 СЕГОДНЯШНИЕ ИСТЕРИКИ] - список
[📊 СТАТИСТИКА ЗА НЕДЕЛЮ] - точность
[⚙️ НАСТРОЙКИ ПАНИКИ] - пороги
[❓ КАК РАБОТАЕТ] - инструкция

🔧 СЛУЖЕБНЫЕ КОМАНДЫ:

/overheat [ТИКЕР] -- индекс перегрева
/panicmap - карта активности
/today - все сигналы сегодня
/stats - статистика
/extreme - самые сильные сигналы
/alerts on/off - вкл/выкл уведомления
/startscan - возобновить сканирование (после сбоя)

━━━━━━━━━━━━━━━━━━━━━━━━━
🔔 Автооповещения: {alert_status}
🚨 Последняя паника: {last_panic_time} ({last_panic_ticker})
📅 Сигналов сегодня: {signals_today}
"""


def format_panic_signal_alert(signal: PanicSignal) -> str:
    """Форматирование сигнала паники с использованием PanicSignal модели"""
    if not PYDANTIC_AVAILABLE or signal is None:
        return "⚠️ Система временно недоступна"

    # Определяем эмодзи и уровни
    if signal.final_level == "🔴 СИЛЬНЫЙ":
        emoji = "🚨"
        level_text = "КРАСНЫЙ УРОВЕНЬ"
    elif signal.final_level == "🟡 ХОРОШИЙ":
        emoji = "⚠️"
        level_text = "ЖЁЛТЫЙ УРОВЕНЬ"
    else:
        emoji = "ℹ️"
        level_text = "БЕЛЫЙ УРОВЕНЬ"

    # Определяем тип паники
    panic_type = "ПАНИКА" if signal.signal_type == "panic" else "ЖАДНОСТЬ"

    # Форматируем RSI значения
    rsi_7 = signal.rsi_7 if signal.rsi_7 is not None else "N/A"
    rsi_21 = signal.rsi_21 if signal.rsi_21 is not None else "N/A"
    rsi_periods = f"{signal.rsi_14} (7д={rsi_7}, 14д={signal.rsi_14}, 21д={rsi_21})"

    # Форматируем фильтры - используем поля passed_filters и failed_filters
    passed_filters = []
    filter_emojis = {"time": "⏰", "volatility": "📊", "trend": "📈", "spread": "💰"}
    filter_names = {
        "time": "Время (в активной зоне)",
        "volatility": "Волатильность (ATR > порог)",
        "trend": "Тренд (торгуется по тренду)",
        "spread": "Ликвидность (спред < 0.1%)"
    }

    # Проверяем пройденные фильтры
    for filter_type in signal.passed_filters:
        emoji = filter_emojis.get(filter_type, "✓")
        name = filter_names.get(filter_type, filter_type)
        passed_filters.append(f"{emoji} {name}")

    filters_text = "\n".join(passed_filters) if passed_filters else "✗ Нет пройденных фильтров"

    # Форматируем индекс перегрева
    if signal.risk_metric is not None:
        health_bar = _get_health_bar(signal.risk_metric * 100)
        health_percent = int(signal.risk_metric * 100)
    else:
        health_bar = "[░░░░░░░░░░]"
        health_percent = 0

    return f"""
{emoji} {level_text}! В {signal.ticker} ОБНАРУЖЕНА {panic_type}!

📊 ПАРАМЕТРЫ ПАНИКИ:
• RSI: {rsi_periods}
• Объём: {signal.volume_ratio:.1f}× от нормы
• Время: {signal.timestamp.strftime('%H:%M')}
• Индекс перегрева: {health_bar} {health_percent}%

🎯 ИНТЕРПРЕТАЦИЯ СИГНАЛА:
• Уровень: {signal.final_level}
• Подтверждение: {len(signal.passed_filters)}/4 фильтра
• Контекст: {signal.interpretation}
• Риск: {signal.risk_level}

✅ ПРОЙДЕННЫЕ ФИЛЬТРЫ:
{filters_text}

━━━━━━━━━━━━━━━━━━━━━━━━━
[📊 ГРАФИК АКЦИИ] [📈 СРАВНИТЬ С IMOEX]
[📋 ИСТОРИЯ СИГНАЛОВ] [🤔 ОБЪЯСНИТЬ СИГНАЛ]
[🚫 ИГНОРИРОВАТЬ {signal.ticker} НА 2 ЧАСА]
"""

def get_help_template():
    """Шаблон справки по командам"""
    return """
📚 СПРАВКА ПО КОМАНДАМ ПАНИКЁР 3000

━━━━━━━━━━━━━━━━━━━━━━━━━
📋 ОСНОВНЫЕ КОМАНДЫ:

/start - Главное меню
/help - Эта справка
/status - Статус системы

📊 АНАЛИТИКА:

/overheat [ТИКЕР] - Индекс перегрева акции
/panicmap - Карта паники за сегодня (ASCII)
/today - Все сигналы за сегодня
/stats - Статистика за неделю
/extreme - Самые сильные сигналы

⚙️ НАСТРОЙКИ:

/alerts on - Включить уведомления
/alerts off - Выключить уведомления
/settings - Настройки детектора

🔄 УПРАВЛЕНИЕ:

/startscan - Возобновить сканирование
/ignore [ТИКЕР] [ЧАСЫ] - Игнорировать тикер

━━━━━━━━━━━━━━━━━━━━━━━━━
📱 ИНТЕРАКТИВНЫЕ КНОПКИ:

После каждого сигнала доступны кнопки:
[📊 ГРАФИК АКЦИИ] - Открыть график
[📈 СРАВНИТЬ С IMOEX] - Сравнить с индексом
[📋 ИСТОРИЯ СИГНАЛОВ] - История сигналов
[🤔 ОБЪЯСНИТЬ СИГНАЛ] - Подробное объяснение
[🚫 ИГНОРИРОВАТЬ 2 ЧАСА] - Временно игнорировать

━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️ ПРИМЕЧАНИЯ:

• Бот работает только в часы работы биржи (10:00-18:30 МСК)
• Сигналы приходят только при обнаружении аномалий
• Настройки можно изменить в веб-дашборде
• Для экстренной остановки: /stopscan

💬 Поддержка: @panicker3000_support
"""


def get_health_template(ticker, health_percentage, health_bar,
                        rsi_values, volume_ratio, last_signal):
    """Шаблон индекса перегрева акции"""
    rsi_text = ""
    if isinstance(rsi_values, dict):
        rsi_text = f"RSI: {rsi_values.get('current', 'N/A')}"
        if rsi_values.get('period7'):
            rsi_text += f" (7д={rsi_values.get('period7')}, 21д={rsi_values.get('period21', 'N/A')})"

    return f"""
📊 ИНДЕКС ПЕРЕГРЕВА {ticker}:

Текущее состояние: {health_bar} {health_percentage}%

{rsi_text}
📈 Объём: {volume_ratio}× от нормы
⏰ Последний сигнал: {last_signal}

🎯 ИНТЕРПРЕТАЦИЯ:
{_get_health_interpretation(health_percentage)}
"""


def _get_health_interpretation(percentage):
    """Вспомогательная функция для интерпретации индекса перегрева"""
    if percentage < 30:
        return "🟢 Акция в норме, RSI около 50, объём стандартный"
    elif percentage < 60:
        return "🟡 Умеренное отклонение, требует наблюдения"
    elif percentage < 80:
        return "🟠 Повышенный риск, возможен сигнал"
    else:
        return "🔴 Высокий риск, сильное отклонение от нормы"


def _get_health_bar(percentage: float) -> str:
    """Создание ASCII-шкалы индекса перегрева"""
    if not isinstance(percentage, (int, float)):
        return "[░░░░░░░░░░]"

    percentage = max(0, min(100, percentage))
    filled = int(percentage / 10)
    return "[" + "█" * filled + "░" * (10 - filled) + "]"

def get_today_template(today_signals):
    """Шаблон сегодняшних сигналов"""
    if not today_signals:
        return "📅 СЕГОДНЯШНИХ СИГНАЛОВ ПОКА НЕТ\n\nСледующая проверка в 10:00."

    signal_lines = []
    for signal in today_signals:
        # Поддержка как PanicSignal объектов, так и словарей
        if PYDANTIC_AVAILABLE and isinstance(signal, PanicSignal):
            time_str = signal.signal_time.strftime('%H:%M')
            ticker = signal.ticker
            level = signal.final_level
            rsi = signal.rsi_14
            volume = f"{signal.volume_ratio:.1f}"
        else:
            # Обратная совместимость со словарями
            time_str = signal.get('time', 'N/A')
            ticker = signal.get('ticker', 'N/A')
            level = signal.get('level', 'N/A')
            rsi = signal.get('rsi', 'N/A')
            volume = signal.get('volume_ratio', 'N/A')

        signal_lines.append(f"{time_str} {level} {ticker} - RSI={rsi}, Объём={volume}×")

    total_count = len(today_signals)
    strong_count = sum(1 for s in today_signals if '🔴' in s.get('level', ''))
    moderate_count = sum(1 for s in today_signals if '🟡' in s.get('level', ''))
    urgent_count = sum(1 for s in today_signals if '⚪' in s.get('level', ''))

    return f"""
📅 СИГНАЛЫ ЗА СЕГОДНЯ ({datetime.now().strftime('%d.%m.%Y')}):

{"\n".join(signal_lines)}

━━━━━━━━━━━━━━━━━━━━━━━━━
ИТОГО: {total_count} сигналов
🔴 Сильных: {strong_count}
🟡 Умеренных: {moderate_count}
⚪ Срочных: {urgent_count}
"""

def get_stats_template(stats_data):
    """Шаблон статистики"""
    if not stats_data:
        return "📊 НЕТ ДАННЫХ ДЛЯ СТАТИСТИКИ\n\nСоберите данные за несколько дней."

    return f"""
📊 СТАТИСТИКА ЗА ПОСЛЕДНИЕ 7 ДНЕЙ:

Всего сигналов: {stats_data.get('total_signals', 0)}
🔴 Сильных: {stats_data.get('strong_signals', 0)}
🟡 Умеренных: {stats_data.get('moderate_signals', 0)}
⚪ Срочных: {stats_data.get('urgent_signals', 0)}

🏆 САМАЯ АКТИВНАЯ: {stats_data.get('most_active_ticker', 'НЕТ')} ({stats_data.get('most_active_count', 0)})
😌 САМЫЙ СПОКОЙНЫЙ: {stats_data.get('most_calm_ticker', 'НЕТ')} ({stats_data.get('most_calm_count', 0)})

📊 ОБЩАЯ НАПРЯЖЁННОСТЬ: {stats_data.get('market_tension', 'НЕТ ДАННЫХ')}

(по шкале от 🟢 спокойно до 🔴 паника)
"""


def get_extreme_template(extreme_signals):
    """Шаблон экстремальных сигналов"""
    if not extreme_signals:
        return "📊 СЕГОДНЯ ЕЩЁ НЕТ СИЛЬНЫХ СИГНАЛОВ\n\nПроверьте /today для всех сигналов."

    signal_lines = []
    medals = ["🥇", "🥈", "🥉"]

    for i, signal in enumerate(extreme_signals[:3]):  # Только топ-3
        medal = medals[i] if i < len(medals) else "📊"

        # Поддержка как PanicSignal объектов, так и словарей
        if PYDANTIC_AVAILABLE and isinstance(signal, PanicSignal):
            ticker = signal.ticker
            level = signal.final_level
            rsi = signal.rsi_14
            volume = f"{signal.volume_ratio:.1f}"
            time_str = signal.signal_time.strftime('%H:%M')
        else:
            # Обратная совместимость со словарями
            ticker = signal.get('ticker', 'N/A')
            level = signal.get('level', 'N/A')
            rsi = signal.get('rsi', 'N/A')
            volume = signal.get('volume_ratio', 'N/A')
            time_str = signal.get('time', 'N/A')

        signal_lines.append(f"{medal} {time_str} {level} {ticker}")
        signal_lines.append(f"   RSI: {rsi} | Объём: {volume}×")

    return f"""
📊 САМЫЕ СИЛЬНЫЕ СИГНАЛЫ СЕГОДНЯ (ТОП-{min(3, len(extreme_signals))})

{"\n".join(signal_lines)}

━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Все сигналы: /today
📈 Статистика: /stats
"""


def get_panic_map_template(panic_map_data):
    """Шаблон карты паники"""
    if not panic_map_data:
        return "📊 НЕТ ДАННЫХ ДЛЯ КАРТЫ ПАНИКИ"

    date_str = datetime.now().strftime('%d.%m.%Y')

    # Создаём ASCII карту
    map_lines = [f"📊 КАРТА ПАНИКИ ЗА {date_str}", ""]

    # Заголовок с часами
    hours = ["10", "12", "14", "16", "18"]
    map_lines.append("    " + "  ".join(hours))

    # Данные по тикерам
    for ticker, signals in panic_map_data.items():
        hour_signals = []
        for hour in ["10", "12", "14", "16", "18"]:
            signal = signals.get(hour, '⚪')
            hour_signals.append(signal)

        map_lines.append(f"{ticker:4} " + "  ".join(hour_signals))

    map_lines.append("")
    map_lines.append("⚪ = нет сигналов | 🟡 = хорошо | 🔴 = сильно")
    map_lines.append("Срочные сигналы не показываются на карте")

    return "\n".join(map_lines)

def get_status_template(status_data):
    """Шаблон статуса системы"""
    return f"""
📡 СТАТУС СИСТЕМЫ ПАНИКЁР 3000

━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 БОТ: {status_data.get('bot_status', 'НЕТ ДАННЫХ')}
🏛️ БИРЖА: {status_data.get('exchange_status', 'НЕТ ДАННЫХ')}
🕐 ВРЕМЯ: {datetime.now().strftime('%H:%M')} МСК
📅 ДАТА: {datetime.now().strftime('%d.%m.%Y')}

📊 СКАНИРОВАНИЕ:
• Активных тикеров: {status_data.get('active_tickers', 0)}
• Последняя проверка: {status_data.get('last_scan', 'НЕТ')}
• Следующая проверка: {status_data.get('next_scan', 'НЕТ')}

💾 ПАМЯТЬ:
• Использовано: {status_data.get('memory_used', 'НЕТ')}
• Сигналов в БД: {status_data.get('db_signals', 0)}

🔧 СОСТОЯНИЕ СЕРВИСОВ:
• gRPC сервер: {status_data.get('grpc_status', 'НЕТ')}
• Tinkoff API: {status_data.get('api_status', 'НЕТ')}
• База данных: {status_data.get('db_status', 'НЕТ')}

━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️ Для обновления статуса используйте /start
"""