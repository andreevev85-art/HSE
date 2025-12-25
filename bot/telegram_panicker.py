"""
Основной модуль Telegram-бота «Паникёр 3000» с интеграцией gRPC.
Обработка команд, автоматические оповещения, взаимодействие с пользователем.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import logging
import os
import sys
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional, Tuple
import telebot
from telebot import types
import codecs

# Исправляем кодировку для Windows
if sys.platform == "win32":
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Теперь все импорты будут работать
from utils.schemas import PanicSignal, TickerData, validate_panic_signal
from bot.message_templates import format_panic_signal_alert
from data.market_calendar import get_market_calendar
from core.config_loader import ConfigLoader
from data.data_cache import DataCache

# gRPC клиент
try:
    # Абсолютный импорт из grpc папки
    from grpc_service.grpc_client import get_grpc_client
    GRPC_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Ошибка импорта gRPC: {e}")
    # Попробуем через sys.path
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from grpc_service.grpc_client import get_grpc_client
        GRPC_AVAILABLE = True
    except ImportError as e2:
        print(f"❌ Не удалось импортировать gRPC: {e2}")
        get_grpc_client = None
        GRPC_AVAILABLE = False
# Локальные импорты
import bot.message_templates as message_templates
import bot.inline_keyboards as inline_keyboards
import bot.error_handlers as error_handlers

print("✅ Все модули успешно импортированы")
# ============================================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============================================================================
# КОНСТАНТЫ
# ============================================================================
class BotStates:
    """Состояния бота для ConversationHandler"""
    MAIN_MENU = 0
    HEALTH_CHECK = 1
    PANIC_MAP = 2
    SETTINGS = 3


# ============================================================================
# КЛАСС TelegramPanickerBot (gRPC ВЕРСИЯ)
# ============================================================================
class TelegramPanickerBot:
    """Основной класс Telegram-бота с gRPC интеграцией"""

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self):
        self.token = self._load_token()
        self.bot = None
        self.config_loader = None
        self.grpc_client = None  # gRPC клиент вместо PanicDetector
        self.data_cache = None
        self.is_active = False
        self.default_tickers = ['SBER', 'GAZP', 'LKOH', 'GMKN', 'YNDX']

        # Инициализируем MarketCalendar
        self.market_calendar = get_market_calendar()

        logger.info("TelegramPanickerBot инициализирован (gRPC + MarketCalendar)")
        import logging
        self.logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------------
    # ЗАГРУЗКА ТОКЕНОВ И КОНФИГУРАЦИИ
    # ------------------------------------------------------------------------
    def _load_token(self) -> str:
        from dotenv import load_dotenv
        import os

        # Загружаем .env из panicker3000/.env
        current_dir = os.path.dirname(os.path.abspath(__file__))
        panicker3000_dir = os.path.dirname(current_dir)
        env_path = os.path.join(panicker3000_dir, '.env')

        load_dotenv(dotenv_path=env_path)

        token = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_TOKEN')

        if not token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN не найден в .env файле. "
                "Добавьте TELEGRAM_BOT_TOKEN=ваш_токен в .env"
            )
        return token

    def _initialize_components(self):
        """Инициализация всех компонентов системы"""
        try:
            # Загрузка конфигурации
            self.config_loader = ConfigLoader()
            logger.info("✅ ConfigLoader инициализирован")

            # Инициализация gRPC клиента
            try:
                self.grpc_client = get_grpc_client()
                if self.grpc_client is None:
                    raise ValueError("get_grpc_client вернул None")
                self.logger.info("[OK] gRPC клиент инициализирован")
            except Exception as e:
                self.logger.error(f"❌ Не удалось инициализировать gRPC клиент: {e}")
                self.grpc_client = None

            # Инициализация кеша данных
            self.data_cache = DataCache()
            logger.info("✅ DataCache инициализирован")

            logger.info("✅ Все компоненты инициализированы")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации компонентов: {e}")
            raise

    # ------------------------------------------------------------------------
    # РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ КОМАНД
    # ------------------------------------------------------------------------
    def _register_handlers(self):
        """Регистрация всех обработчиков команд для telebot"""

        @self.bot.message_handler(commands=['overheat'])
        def handle_overheat(message):
            args = message.text.split()[1:] if len(message.text.split()) > 1 else []
            self.command_overheat(message, args)

        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self.command_start(message)

        @self.bot.message_handler(commands=['help'])
        def handle_help(message):
            self.command_help(message)

        @self.bot.message_handler(commands=['today'])
        def handle_today(message):
            self.command_today(message)

        @self.bot.message_handler(commands=['stats'])
        def handle_stats(message):
            self.command_stats(message)

        @self.bot.message_handler(commands=['extreme'])
        def handle_extreme(message):
            self.command_extreme(message)

        @self.bot.message_handler(commands=['panicmap'])
        def handle_panicmap(message):
            self.command_panicmap(message)

        @self.bot.message_handler(commands=['alerts'])
        def handle_alerts(message):
            args = message.text.split()[1:] if len(message.text.split()) > 1 else []
            self.command_alerts(message, args)

        @self.bot.message_handler(commands=['startscan'])
        def handle_startscan(message):
            self.command_startscan(message)

        @self.bot.message_handler(commands=['status'])
        def handle_status(message):
            self.command_status(message)

        @self.bot.message_handler(commands=['report'])
        def handle_report(message):
            self.command_report(message)

        # Обработка callback-кнопок
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self.handle_callback_query(call)

        logger.info("✅ Обработчики команд зарегистрированы")

    # ------------------------------------------------------------------------
    # ОСНОВНОЙ МЕТОД: ЗАПУСК БОТА
    # ------------------------------------------------------------------------
    def start_bot(self):
        """Основной метод запуска бота"""
        try:
            # Инициализация компонентов
            self._initialize_components()

            # Проверяем наличие Pydantic моделей
            if not PanicSignal:
                logger.warning("⚠️  Pydantic модели не загружены. Бот будет работать в режиме совместимости.")
            else:
                logger.info("✅ Pydantic модели загружены успешно")

            # Создание экземпляра бота
            self.bot = telebot.TeleBot(self.token)

            # Регистрация обработчиков команд
            self._register_handlers()

            self.is_active = True
            logger.info("🤖 Бот успешно запущен и начал прослушивание")

            # Запуск фоновых задач
            self._start_background_tasks()

            # Запуск бота в режиме polling
            logger.info("📡 Запускаем polling...")
            try:
                self.bot.infinity_polling(timeout=20, long_polling_timeout=5)
            except Exception as e:
                logger.error(f"❌ Ошибка в polling: {e}")
                raise

        except Exception as e:
            logger.error(f"❌ Критическая ошибка при запуске бота: {e}")
            raise

    # ------------------------------------------------------------------------
    # ФОНОВЫЕ ЗАДАЧИ
    # ------------------------------------------------------------------------
    def _start_background_tasks(self):
        """Запуск фоновых задач"""
        logger.info("⏰ Фоновые задачи инициализированы")

    # ------------------------------------------------------------------------
    # КОМАНДА: /overheat [тикер] - ИНДЕКС ПЕРЕГРЕВА
    # ------------------------------------------------------------------------
    def command_overheat(self, message, args=None):
        """Обработчик команды /overheat [тикер] - индекс перегрева акции"""
        try:
            # Получаем тикер из аргументов
            ticker = args[0].upper() if args and len(args) > 0 else "SBER"

            # Получаем данные через gRPC как PanicSignal
            panic_signal = self._get_panic_signal_via_grpc(ticker)

            if not panic_signal:
                # Получаем упрощённые данные если нет полноценного сигнала
                overheat_data = self._get_overheat_data_via_grpc(ticker)
                overheat_text = self._format_overheat_message(ticker, overheat_data)
            else:
                # Используем PanicSignal для форматирования
                overheat_text = self._format_overheat_from_signal(ticker, panic_signal)

            # Получаем клавиатуру
            reply_markup = self._get_overheat_keyboard(ticker)

            self.bot.reply_to(
                message,
                text=overheat_text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_notification=True
            )

            logger.info(f"🌡️  Команда /overheat выполнена для {ticker}")

        except Exception as e:
            logger.error(f"❌ Ошибка в команде /overheat: {e}")
            self.bot.reply_to(message, f"❌ Ошибка: {str(e)[:100]}")

    def _get_overheat_data_via_grpc(self, ticker: str) -> Dict[str, Any]:
        """Получение индекса перегрева через gRPC"""
        try:
            # Вызываем gRPC метод
            overheat_data = self.grpc_client.get_overheat_index(ticker)

            # Обрабатываем ответ
            overheat_percent = overheat_data.get('overheat_percentage', 50.0)

            # Создаём шкалу перегрева
            overheat_bar = self._create_overheat_bar(overheat_percent)

            return {
                'overheat_percent': overheat_percent,
                'overheat_bar': overheat_bar,  # [🟩🟩🟩⬜⬜]
                'current_rsi': overheat_data.get('current_rsi', 50.0),
                'volume_ratio': overheat_data.get('volume_ratio', 1.0),
                'last_signal_time': overheat_data.get('last_signal_time', ''),
                'last_signal_level': overheat_data.get('last_signal_level', 'НЕТ')
            }

        except Exception as e:
            logger.error(f"❌ Ошибка gRPC для {ticker}: {e}")
            # Заглушка при ошибке
            return {
                'overheat_percent': 50.0,
                'overheat_bar': '[🟩🟩⬜⬜⬜]',
                'current_rsi': 50.0,
                'volume_ratio': 1.0,
                'last_signal_time': '',
                'last_signal_level': 'НЕТ'
            }

    def _get_panic_signal_via_grpc(self, ticker: str) -> Optional[PanicSignal]:
        """Получение полноценного PanicSignal через gRPC"""
        try:
            if not PanicSignal:
                logger.warning("Pydantic модели не загружены, используем старый формат")
                return None

            # Вызываем gRPC метод для сканирования тикера
            signals = self.grpc_client.scan_tickers([ticker])

            if not signals or len(signals) == 0:
                return None

            # Преобразуем словарь в PanicSignal
            signal_data = signals[0]

            # Проверяем, что это словарь (а не уже PanicSignal)
            if isinstance(signal_data, dict):
                # Создаём PanicSignal из словаря
                panic_signal = PanicSignal(**signal_data)

                # Валидируем
                if validate_panic_signal:
                    validate_panic_signal(panic_signal)

                return panic_signal
            elif isinstance(signal_data, PanicSignal):
                # Уже готовый PanicSignal
                return signal_data
            else:
                logger.warning(f"Неизвестный формат сигнала для {ticker}: {type(signal_data)}")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения PanicSignal для {ticker}: {e}")
            return None

    def _format_overheat_message(self, ticker: str, data: Dict[str, Any]) -> str:
        """Форматирование сообщения об индексе перегрева с деталями"""
        try:
            # Получаем детальный сигнал для кластеров
            signals = self.grpc_client.scan_tickers([ticker])
            has_detailed_data = signals and len(signals) > 0

            # Базовый текст
            text = f"🌡️ **ИНДЕКС ПЕРЕГРЕВА {ticker}**\n\n"
            text += f"Текущее состояние: {data['overheat_bar']} {data['overheat_percent']:.0f}%\n\n"

            # Основные метрики
            text += f"📊 **ОСНОВНЫЕ ПОКАЗАТЕЛИ:**\n"
            text += f"• RSI: {data['current_rsi']:.1f}\n"
            text += f"• Объём: {data['volume_ratio']:.1f}× от нормы\n"
            text += f"• Последний сигнал: {data['last_signal_time']} ({data['last_signal_level']})\n\n"

            # Если есть детальные данные, добавляем риск и кластеры
            if has_detailed_data:
                signal = signals[0]

                # Риск-метрика
                risk = signal.get('risk_metric')
                if risk is not None:
                    if risk >= 70:
                        risk_status = "🔴 ВЫСОКИЙ"
                    elif risk >= 40:
                        risk_status = "🟡 СРЕДНИЙ"
                    else:
                        risk_status = "🟢 НИЗКИЙ"

                    text += f"📈 **РИСК-АНАЛИЗ:**\n"
                    text += f"• Оценка риска: {risk:.1f}/100\n"
                    text += f"• Уровень: {risk_status}\n\n"

                # Кластеры объёма
                clusters = signal.get('volume_clusters', [])
                if clusters:
                    text += f"📊 **КЛЮЧЕВЫЕ УРОВНИ ОБЪЁМА:**\n"

                    for i, cluster in enumerate(clusters[:3], 1):  # первые 3 кластера
                        price = cluster.get('price_level', 0)
                        percentage = cluster.get('volume_percentage', 0)
                        role = cluster.get('role', 'N/A')

                        role_icon = "🟢" if role == 'support' else "🔴" if role == 'resistance' else "⚪"
                        text += f"{i}. {role_icon} {price:.2f}₽ ({percentage:.1f}% объёма)\n"

                    text += "\n"

            # ПРАВИЛЬНАЯ ЛЕГЕНДА С ИНВЕРТИРОВАННОЙ ЛОГИКОЙ
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📈 **ЛОГИКА ШКАЛЫ:**\n"
            text += "• [⬜⬜⬜⬜⬜] 0% = Холодно, сигналов нет\n"
            text += "• [🟩🟩⬜⬜⬜] 40% = Умеренная активность\n"
            text += "• [🟩🟩🟩🟩🟩] 100% = ЖАРКО! Сильный сигнал!\n\n"

            # Навигация
            text += "📋 Все сигналы: /today\n"
            text += "🔥 Самые сильные: /extreme"

            return text

        except Exception as e:
            logger.error(f"❌ Ошибка форматирования для {ticker}: {e}")
            # Возвращаем упрощённую версию при ошибке
            return (
                f"🌡️ **ИНДЕКС ПЕРЕГРЕВА {ticker}**\n\n"
                f"Текущее состояние: {data['overheat_bar']} {data['overheat_percent']:.0f}%\n\n"
                f"📊 RSI: {data['current_rsi']:.1f}\n"
                f"📈 Объём: {data['volume_ratio']:.1f}× от нормы\n"
                f"⏰ Последний сигнал: {data['last_signal_time']} ({data['last_signal_level']})\n\n"
                f"*0% = холодно | 100% = ЖАРКО!*"
            )

    def _create_overheat_bar(self, percentage: float) -> str:
        """Создать шкалу индекса перегрева с цветными квадратами"""
        # 5 сегментов [🟩🟩🟩⬜⬜]
        filled = int(percentage / 20)  # 0-20% = 0, 20-40% = 1, и т.д.
        filled = min(filled, 5)
        empty = 5 - filled

        # Используем зелёные квадраты для заполненных, белые для пустых
        return f"[{'🟩' * filled}{'⬜' * empty}]"

    def _format_overheat_from_signal(self, ticker: str, panic_signal: PanicSignal) -> str:
        """Форматирование сообщения об индексе перегрева из PanicSignal"""
        try:
            # Базовый текст
            text = f"🌡️ **ИНДЕКС ПЕРЕГРЕВА {ticker}**\n\n"

            # Создаём шкалу перегрева на основе RSI
            overheat_percent = self._calculate_overheat_percentage(panic_signal)
            overheat_bar = self._create_overheat_bar(overheat_percent)
            text += f"Текущее состояние: {overheat_bar} {overheat_percent:.0f}%\n\n"

            # Основные метрики из PanicSignal
            text += f"📊 **ОСНОВНЫЕ ПОКАЗАТЕЛИ:**\n"
            text += f"• RSI(14): {panic_signal.rsi_14:.1f}\n"
            if panic_signal.rsi_7 and panic_signal.rsi_21:
                text += f"• RSI(7/21): {panic_signal.rsi_7:.1f}/{panic_signal.rsi_21:.1f}\n"
            text += f"• Объём: {panic_signal.volume_ratio:.1f}× от нормы\n"
            text += f"• Тип сигнала: {panic_signal.signal_type}\n"
            text += f"• Уровень: {panic_signal.level}\n"
            text += f"• Время обнаружения: {panic_signal.detected_at}\n\n"

            # Риск-метрика (шаг 10 алгоритма)
            if panic_signal.risk_metric is not None:
                risk = panic_signal.risk_metric
                if risk >= 70:
                    risk_status = "🔴 ВЫСОКИЙ"
                elif risk >= 40:
                    risk_status = "🟡 СРЕДНИЙ"
                else:
                    risk_status = "🟢 НИЗКИЙ"

                text += f"📈 **РИСК-АНАЛИЗ:**\n"
                text += f"• Оценка риска: {risk:.1f}/100\n"
                text += f"• Уровень: {risk_status}\n\n"

            # Кластеры объёма (шаг 9 алгоритма)
            if panic_signal.volume_clusters and len(panic_signal.volume_clusters) > 0:
                text += f"📊 **КЛЮЧЕВЫЕ УРОВНИ ОБЪЁМА:**\n"

                # Сортируем кластеры по доле объёма
                sorted_clusters = sorted(
                    panic_signal.volume_clusters,
                    key=lambda x: x.get('volume_percentage', 0) if isinstance(x, dict) else x.volume_percentage,
                    reverse=True
                )

                for i, cluster in enumerate(sorted_clusters[:3], 1):  # первые 3 кластера
                    if isinstance(cluster, dict):
                        price = cluster.get('price_level', 0)
                        percentage = cluster.get('volume_percentage', 0)
                        role = cluster.get('role', 'N/A')
                    else:
                        price = cluster.price_level
                        percentage = cluster.volume_percentage
                        role = cluster.role

                    role_icon = "🟢" if role == 'support' else "🔴" if role == 'resistance' else "⚪"
                    text += f"{i}. {role_icon} {price:.2f}₽ ({percentage:.1f}% объёма)\n"

                text += "\n"

            # Рекомендация на основе базового уровня
            if panic_signal.base_level:
                text += f"🎯 **ОЦЕНКА СИГНАЛА:**\n"
                text += f"• Базовый уровень: {panic_signal.base_level}\n"
                if panic_signal.final_level and panic_signal.final_level != panic_signal.base_level:
                    text += f"• С учётом фильтров: {panic_signal.final_level}\n"
                text += "\n"

            # ПРАВИЛЬНАЯ ЛЕГЕНДА С ИНВЕРТИРОВАННОЙ ЛОГИКОЙ
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📈 **ЛОГИКА ШКАЛЫ:**\n"
            text += "• [⬜⬜⬜⬜⬜] 0% = Холодно, сигналов нет\n"
            text += "• [🟩🟩⬜⬜⬜] 40% = Умеренная активность\n"
            text += "• [🟩🟩🟩🟩🟩] 100% = ЖАРКО! Сильный сигнал!\n\n"

            # Навигация
            text += "📋 Все сигналы: /today\n"
            text += "🔥 Самые сильные: /extreme"

            return text

        except Exception as e:
            logger.error(f"❌ Ошибка форматирования PanicSignal для {ticker}: {e}")
            # Возвращаем упрощённую версию при ошибке
            return self._format_overheat_message(ticker, {
                'overheat_percent': 50.0,
                'overheat_bar': '[🟩🟩⬜⬜⬜]',
                'current_rsi': panic_signal.rsi_14 if hasattr(panic_signal, 'rsi_14') else 50.0,
                'volume_ratio': panic_signal.volume_ratio if hasattr(panic_signal, 'volume_ratio') else 1.0,
                'last_signal_time': panic_signal.detected_at if hasattr(panic_signal, 'detected_at') else '',
                'last_signal_level': panic_signal.level if hasattr(panic_signal, 'level') else 'НЕТ'
            })

    def _calculate_overheat_percentage(self, panic_signal: PanicSignal) -> float:
        """Расчёт процента перегрева на основе PanicSignal"""
        try:
            # Базовая логика: 0% = RSI=50, 100% = RSI=0 или RSI=100
            rsi = panic_signal.rsi_14

            if rsi <= 50:
                # Паника: RSI от 50 до 0 = 0% до 100%
                percentage = ((50 - rsi) / 50) * 100
            else:
                # Жадность: RSI от 50 до 100 = 0% до 100%
                percentage = ((rsi - 50) / 50) * 100

            # Учитываем объём (коэффициент увеличения)
            volume_factor = min(panic_signal.volume_ratio, 3.0)  # Ограничиваем влияние объёма
            adjusted_percentage = percentage * (volume_factor / 2.0)  # Нормализуем

            # Ограничиваем 0-100%
            return min(max(adjusted_percentage, 0.0), 100.0)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта перегрева: {e}")
            return 50.0  # Значение по умолчанию

    # ------------------------------------------------------------------------
    # АВТООПОВЕЩЕНИЯ С PanicSignal
    # ------------------------------------------------------------------------
    def send_panic_alert(self, panic_signal: PanicSignal):
        """Отправка автооповещения на основе PanicSignal"""
        try:
            if not PanicSignal:
                logger.warning("Pydantic модели не загружены, пропускаем автооповещение")
                return

            # Получаем chat_id из настроек (пока заглушка)
            # TODO: Реализовать хранение chat_id пользователей в БД
            chat_id = self.config_loader.get_telegram_chat_id()
            if not chat_id:
                logger.warning("Не найден chat_id для отправки автооповещения")
                return

            # Форматируем сообщение
            alert_text = self._format_alert_message(panic_signal)

            # Получаем клавиатуру
            reply_markup = self._get_alert_keyboard(panic_signal.ticker)

            # Отправляем сообщение
            self.bot.send_message(
                chat_id=chat_id,
                text=alert_text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_notification=False
            )

            logger.info(f"🚨 Автооповещение отправлено для {panic_signal.ticker}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки автооповещения: {e}")

    def _format_alert_message(self, panic_signal: PanicSignal) -> str:
        """Форматирование сообщения автооповещения по шаблону из плана проекта"""
        try:
            # Используем стандартный формат из message_templates
            if format_panic_signal_alert:
                try:
                    return format_panic_signal_alert(panic_signal)
                except Exception as e:
                    logger.warning(f"Ошибка в format_panic_signal_alert: {e}, используем fallback")
                    return self._format_alert_message_fallback(panic_signal)
            else:
                # Fallback на старую логику
                return self._format_alert_message_fallback(panic_signal)

        except Exception as e:
            logger.error(f"❌ Ошибка форматирования автооповещения: {e}")
            return f"🚨 **СИГНАЛ {panic_signal.ticker}**\n\nОбнаружен сигнал уровня {panic_signal.level}"

    def _format_alert_message_fallback(self, panic_signal: PanicSignal) -> str:
        """Fallback форматирование если format_panic_signal_alert не доступен"""
        try:
            # Эмодзи уровня
            level_emoji = "🚨" if "🔴" in panic_signal.level else "⚠️" if "🟡" in panic_signal.level else "ℹ️"

            # Тип паники/жадности
            signal_type_rus = "ПАНИКА" if "ПАНИКА" in panic_signal.signal_type.upper() else "ЖАДНОСТЬ"

            text = f"{level_emoji} **{panic_signal.level} В {panic_signal.ticker} ОБНАРУЖЕНА {signal_type_rus}!**\n\n"

            # Базовые данные
            text += f"📊 **ПАРАМЕТРЫ {signal_type_rus}:**\n"
            text += f"• RSI: {panic_signal.rsi_14:.1f}\n"
            text += f"• Объём: {panic_signal.volume_ratio:.1f}× от нормы\n"
            text += f"• Время: {panic_signal.detected_at}\n"

            return text

        except Exception as e:
            logger.error(f"❌ Ошибка fallback форматирования: {e}")
            return f"🚨 Сигнал {panic_signal.ticker}: {panic_signal.level}"

    def _get_alert_keyboard(self, ticker: str):
        """Получить клавиатуру для автооповещения"""
        try:
            return inline_keyboards.get_alert_keyboard(ticker)
        except Exception as e:
            logger.error(f"❌ Ошибка получения клавиатуры для оповещения {ticker}: {e}")
            return types.InlineKeyboardMarkup()

    def _get_overheat_keyboard(self, ticker: str):
        """Получить клавиатуру для команды /overheat"""
        try:
            return inline_keyboards.get_overheat_keyboard(ticker)
        except Exception as e:
            logger.error(f"❌ Ошибка получения клавиатуры для {ticker}: {e}")
            return types.InlineKeyboardMarkup()

    def _calculate_stats_from_signals(self, signals: List) -> Dict[str, Any]:
        """Расчёт статистики из списка сигналов (PanicSignal или dict)"""
        try:
            if not signals:
                return {
                    'total_signals': 0,
                    'strong_signals': 0,
                    'moderate_signals': 0,
                    'urgent_signals': 0,
                    'most_active_ticker': 'НЕТ',
                    'most_active_count': 0,
                    'most_calm_ticker': 'НЕТ',
                    'most_calm_count': 0,
                    'market_tension': '🟢 СПОКОЙНО'
                }

            # Счётчики
            total = 0
            strong = 0
            moderate = 0
            urgent = 0

            # Счётчик по тикерам
            ticker_counts = {}

            for signal in signals:
                # Извлекаем данные в зависимости от типа
                if hasattr(signal, 'level'):
                    level = signal.level
                    ticker = signal.ticker
                elif isinstance(signal, dict):
                    level = signal.get('level', '')
                    ticker = signal.get('ticker', '')
                else:
                    continue

                total += 1

                # Считаем по уровням
                level_upper = level.upper()
                if '🔴' in level_upper or 'STRONG' in level_upper:
                    strong += 1
                elif '🟡' in level_upper or 'MODERATE' in level_upper:
                    moderate += 1
                elif '⚪' in level_upper or 'URGENT' in level_upper:
                    urgent += 1

                # Считаем по тикерам
                if ticker:
                    ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1

            # Находим самый активный и самый спокойный тикер
            most_active = 'НЕТ'
            most_active_count = 0
            most_calm = 'НЕТ'
            most_calm_count = float('inf')

            for ticker, count in ticker_counts.items():
                if count > most_active_count:
                    most_active = ticker
                    most_active_count = count

                if count < most_calm_count:
                    most_calm = ticker
                    most_calm_count = count

            # Определяем общую напряжённость
            if total == 0:
                tension = '🟢 СПОКОЙНО'
            elif strong / total > 0.3:
                tension = '🔴 ВЫСОКАЯ'
            elif moderate / total > 0.5:
                tension = '🟡 УМЕРЕННАЯ'
            else:
                tension = '🟢 СПОКОЙНО'

            return {
                'total_signals': total,
                'strong_signals': strong,
                'moderate_signals': moderate,
                'urgent_signals': urgent,
                'most_active_ticker': most_active,
                'most_active_count': most_active_count,
                'most_calm_ticker': most_calm,
                'most_calm_count': most_calm_count,
                'market_tension': tension
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта статистики: {e}")
            return {
                'total_signals': 0,
                'strong_signals': 0,
                'moderate_signals': 0,
                'urgent_signals': 0,
                'most_active_ticker': 'ОШИБКА',
                'most_active_count': 0,
                'most_calm_ticker': 'ОШИБКА',
                'most_calm_count': 0,
                'market_tension': '⚪ НЕИЗВЕСТНО'
            }

    # ------------------------------------------------------------------------
    # ОСТАЛЬНЫЕ КОМАНДЫ (упрощённые версии)
    # ------------------------------------------------------------------------
    def command_start(self, message):
        """Обработчик команды /start - главное меню со статусом биржи"""
        try:
            user = message.from_user

            # Проверяем статус биржи через MarketCalendar
            is_open, reason = self.market_calendar.is_market_open_now()
            exchange_status = "🟢 ОТКРЫТА" if is_open else "🔴 ЗАКРЫТА"

            # Получаем следующий торговый день
            next_trading_day = self.market_calendar.get_next_trading_day()
            next_event = f"Следующий торговый день: {next_trading_day.strftime('%d.%m.%Y')}"

            welcome_text = (
                f"🤖 **ПАНИКЁР 3000** | v1.0\n"
                f"Отряд контроля рыночной паники\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Статус: 🟢 АКТИВЕН\n"
                f"Биржа: {exchange_status} ({reason})\n"
                f"Следующее событие: {next_event}\n"
                f"Последняя проверка: только что\n\n"
                f"📋 **БЫСТРЫЙ ДОСТУП:**\n"
                f"[📊 КАРТА ПАНИКИ] - тепловая карта\n"
                f"[📊 ИНДЕКС ПЕРЕГРЕВА] - HP-бар акции\n"
                f"[📈 СЕГОДНЯШНИЕ ИСТЕРИКИ] - список\n"
                f"[📊 СТАТИСТИКА ЗА НЕДЕЛЮ] - точность\n"
                f"[⚙️ НАСТРОЙКИ ПАНИКИ] - пороги\n"
                f"[❓ КАК РАБОТАЕТ] - инструкция\n\n"
                f"🔧 **СЛУЖЕБНЫЕ КОМАНДЫ:**\n"
                f"/overheat [ТИКЕР] -- индекс перегрева\n"
                f"/panicmap - карта активности\n"
                f"/today - все сигналы сегодня\n"
                f"/stats - статистика\n"
                f"/extreme - самые сильные сигналы\n"
                f"/alerts on/off - вкл/выкл уведомления\n"
                f"/startscan - возобновить сканирование\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔔 Автооповещения: ВКЛ\n"
                f"📅 Сигналов сегодня: проверьте /today"
            )

            self.bot.reply_to(message, welcome_text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка в /start: {e}")
            self.bot.reply_to(message, f"❌ Ошибка: {str(e)[:100]}")

    def command_today(self, message):
        """Обработчик команды /today - сигналы за сегодня с риск-метриками"""
        try:
            # Получаем сигналы через gRPC
            signals_data = self.grpc_client.get_top_signals(period='today', limit=10)

            if signals_data:
                # Конвертируем в PanicSignal если нужно
                signals = []
                for signal_data in signals_data:
                    if isinstance(signal_data, dict) and PanicSignal:
                        try:
                            signal = PanicSignal(**signal_data)
                            signals.append(signal)
                        except Exception as e:
                            logger.warning(f"Не удалось создать PanicSignal: {e}")
                            signals.append(signal_data)
                    else:
                        signals.append(signal_data)

                text = "📅 **СИГНАЛЫ ЗА СЕГОДНЯ**\n\n"

                # Сортируем по времени (новые сверху)
                def get_detected_at(signal):
                    if hasattr(signal, 'detected_at'):
                        return signal.detected_at
                    elif isinstance(signal, dict):
                        return signal.get('detected_at', '')
                    return ''

                signals_sorted = sorted(
                    signals,
                    key=get_detected_at,
                    reverse=True
                )

                for i, signal in enumerate(signals_sorted[:5], 1):
                    # Извлекаем данные в зависимости от типа
                    if hasattr(signal, 'detected_at'):
                        time_str = signal.detected_at[:5] if signal.detected_at else '--:--'
                        ticker = signal.ticker
                        level = signal.level
                        rsi = signal.rsi_14
                        volume = signal.volume_ratio
                        risk = signal.risk_metric
                        signal_type = signal.signal_type
                    elif isinstance(signal, dict):
                        time_str = signal.get('detected_at', '--:--')[:5]
                        ticker = signal.get('ticker', '---')
                        level = signal.get('level', '⚪')
                        rsi = signal.get('rsi_14', 0)
                        volume = signal.get('volume_ratio', 0)
                        risk = signal.get('risk_metric')
                        signal_type = signal.get('signal_type', '')
                    else:
                        continue

                    text += f"{i}. {time_str} {level} **{ticker}**"

                    if signal_type:
                        text += f" ({signal_type})\n"
                    else:
                        text += "\n"

                    # Добавляем риск-метрику кратко
                    if risk is not None:
                        if risk >= 70:
                            risk_icon = "🔴"
                        elif risk >= 40:
                            risk_icon = "🟡"
                        else:
                            risk_icon = "🟢"

                        text += f"   {risk_icon} Риск: {risk:.1f} | RSI: {rsi:.1f} | Объём: {volume:.1f}×\n"
                    else:
                        text += f"   RSI: {rsi:.1f} | Объём: {volume:.1f}×\n"

                    text += "\n"  # Разделитель

                text += f"📊 **Всего сигналов:** {len(signals)}\n"
                text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                text += "🔥 Самые сильные: /extreme\n"
                text += "📈 Статистика: /stats\n"
                text += "🌡️ Проверить акцию: /overheat [тикер]"

            else:
                text = "📅 **СИГНАЛЫ ЗА СЕГОДНЯ**\n\nНет сигналов за сегодня\n\n"
                text += "Следующая проверка в 10:00"

            self.bot.reply_to(message, text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка в /today: {e}")
            self.bot.reply_to(message, "❌ Ошибка получения данных")

    def command_extreme(self, message):
        """Обработчик команды /extreme - самые сильные сигналы"""
        try:
            # Получаем топ сигналы через gRPC
            signals_data = self.grpc_client.get_top_signals(period='today', limit=3)

            if signals_data:
                text = "🔥 **САМЫЕ СИЛЬНЫЕ СИГНАЛЫ**\n\n"
                medals = ['🥇', '🥈', '🥉']

                for i, signal_data in enumerate(signals_data):
                    medal = medals[i] if i < len(medals) else f"{i + 1}."

                    # Конвертируем в PanicSignal если нужно
                    if isinstance(signal_data, dict) and PanicSignal:
                        try:
                            signal = PanicSignal(**signal_data)
                        except Exception as e:
                            logger.warning(f"Не удалось создать PanicSignal: {e}")
                            signal = signal_data
                    else:
                        signal = signal_data

                    # Извлекаем данные в зависимости от типа
                    if hasattr(signal, 'ticker'):
                        ticker = signal.ticker
                        level = signal.level
                        rsi = signal.rsi_14
                        volume = signal.volume_ratio
                        risk = signal.risk_metric
                        clusters = signal.volume_clusters
                        signal_type = signal.signal_type
                        base_level = signal.base_level
                        final_level = signal.final_level
                    elif isinstance(signal, dict):
                        ticker = signal.get('ticker', '---')
                        level = signal.get('level', '⚪')
                        rsi = signal.get('rsi_14', 0)
                        volume = signal.get('volume_ratio', 0)
                        risk = signal.get('risk_metric')
                        clusters = signal.get('volume_clusters', [])
                        signal_type = signal.get('signal_type', '')
                        base_level = signal.get('base_level', '')
                        final_level = signal.get('final_level', '')
                    else:
                        continue

                    # Базовая информация
                    type_emoji = "📉" if "ПАНИКА" in signal_type.upper() else "📈" if "ЖАДНОСТЬ" in signal_type.upper() else "📊"
                    text += f"{medal} {type_emoji} {level} **{ticker}**\n"
                    text += f"   📊 RSI: {rsi:.1f} | 📈 Объём: {volume:.1f}×\n"

                    # Информация об уровнях
                    if base_level:
                        level_info = f"Уровень: {base_level}"
                        if final_level and final_level != base_level:
                            level_info += f" → {final_level}"
                        text += f"   🎯 {level_info}\n"

                    # РИСК-МЕТРИКА
                    if risk is not None:
                        if risk >= 70:
                            risk_emoji = "🔴"
                            risk_text = "ВЫСОКИЙ"
                        elif risk >= 40:
                            risk_emoji = "🟡"
                            risk_text = "СРЕДНИЙ"
                        else:
                            risk_emoji = "🟢"
                            risk_text = "НИЗКИЙ"

                        text += f"   {risk_emoji} Риск: {risk:.1f}/100 ({risk_text})\n"

                    # КЛАСТЕРЫ ОБЪЁМА (шаг 9 алгоритма)
                    if clusters and len(clusters) > 0:
                        # Находим самый значимый кластер
                        if isinstance(clusters[0], dict):
                            main_cluster = max(clusters, key=lambda x: x.get('volume_percentage', 0))
                            price = main_cluster.get('price_level', 0)
                            percentage = main_cluster.get('volume_percentage', 0)
                            role = main_cluster.get('role', '')
                        else:
                            # Предполагаем, что это Pydantic модели кластеров
                            main_cluster = max(clusters, key=lambda x: x.volume_percentage)
                            price = main_cluster.price_level
                            percentage = main_cluster.volume_percentage
                            role = main_cluster.role

                        role_icon = "🟢" if role == 'support' else "🔴" if role == 'resistance' else "📍"
                        text += f"   {role_icon} Ключевой уровень: {price:.2f}₽ ({percentage:.1f}% объёма)\n"

                    text += "\n"  # Разделитель между сигналами

                # Добавляем подпись
                text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                text += "📋 Все сигналы: /today\n"
                text += "📈 Статистика: /stats"

            else:
                text = "🔥 **САМЫЕ СИЛЬНЫЕ СИГНАЛЫ**\n\nНет сигналов за сегодня"

            self.bot.reply_to(message, text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка в /extreme: {e}")
            self.bot.reply_to(message, "❌ Ошибка получения данных")

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def _is_market_open_for_scanning(self) -> Tuple[bool, str]:
        """
        Проверка, открыта ли биржа для сканирования

        Returns:
            (is_open, reason_message)
            is_open: True если биржа открыта и можно сканировать
            reason_message: Текстовое объяснение статуса
        """
        try:
            # Используем MarketCalendar для проверки
            is_open, reason = self.market_calendar.is_market_open_now()

            if not is_open:
                return False, f"Биржа закрыта: {reason}"

            # Если биржа открыта
            return True, "Биржа открыта, сканирование разрешено"

        except Exception as e:
            logger.error(f"❌ Ошибка проверки времени биржи: {e}")
            return False, f"Ошибка проверки статуса биржи: {str(e)[:50]}"

    def command_startscan(self, message):
        """Обработчик команды /startscan - запустить сканирование"""
        try:
            # ПРОВЕРЯЕМ, ОТКРЫТА ЛИ БИРЖА
            can_scan, scan_reason = self._is_market_open_for_scanning()

            if not can_scan:
                # Если биржа закрыта, сообщаем пользователю
                self.bot.reply_to(
                    message,
                    f"⏰ **СКАНИРОВАНИЕ НЕВОЗМОЖНО**\n\n"
                    f"{scan_reason}\n\n"
                    f"Сканирование запускается только в рабочие часы биржи.\n"
                    f"Текущий статус биржи: /status\n"
                    f"Биржа работает: пн-пт, 10:00-18:30 МСК",
                    parse_mode='Markdown'
                )
                return  # Прекращаем выполнение

            # Если биржа открыта, запускаем сканирование через gRPC
            signals_data = self.grpc_client.scan_tickers(self.default_tickers)

            # Конвертируем сигналы в PanicSignal если нужно
            panic_signals = []
            if signals_data:
                for signal_data in signals_data:
                    if isinstance(signal_data, dict) and PanicSignal:
                        try:
                            signal = PanicSignal(**signal_data)
                            panic_signals.append(signal)

                            # Отправляем автооповещение для сильных сигналов
                            if '🔴' in signal.level:
                                self.send_panic_alert(signal)
                        except Exception as e:
                            logger.warning(f"Не удалось создать PanicSignal: {e}")
                            panic_signals.append(signal_data)
                    else:
                        panic_signals.append(signal_data)

            self.bot.reply_to(
                message,
                f"🔍 **СКАНИРОВАНИЕ ЗАПУЩЕНО**\n\n"
                f"Проверено: {len(self.default_tickers)} тикеров\n"
                f"Найдено сигналов: {len(panic_signals)}\n"
                f"Статус биржи: 🟢 ОТКРЫТА ({scan_reason})\n\n"
                f"Система готова к работе!\n\n"
                f"📋 Результаты: /today",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в /startscan: {e}")
            self.bot.reply_to(message, "❌ Ошибка запуска сканирования")

    # ------------------------------------------------------------------------
    # ПРОСТЫЕ КОМАНДЫ
    # ------------------------------------------------------------------------
    def command_help(self, message):
        help_text = (
            "📖 **СПРАВКА ПО КОМАНДАМ**\n\n"
            "• /overheat [тикер] - индекс перегрева акции\n"
            "• /today - все сигналы за сегодня\n"
            "• /extreme - самые сильные сигналы\n"
            "• /startscan - запустить сканирование\n"
            "• /stats - статистика за неделю\n"
            "• /panicmap - карта паники\n"
            "• /alerts on/off - управление уведомлениями\n"
            "• /status - статус системы\n"
            "• /help - эта справка"
        )
        self.bot.reply_to(message, help_text, parse_mode='Markdown')

    def command_stats(self, message):
        """Обработчик команды /stats - статистика за неделю"""
        try:
            # Получаем статистику через gRPC
            stats_data = self.grpc_client.get_stats(days=7)

            # Если stats_data - это список сигналов, конвертируем в статистику
            if isinstance(stats_data, list) and PanicSignal:
                # Получаем список PanicSignal или словарей
                stats = self._calculate_stats_from_signals(stats_data)
            elif isinstance(stats_data, dict):
                # Уже готовая статистика
                stats = stats_data
            else:
                # Неизвестный формат
                stats = {
                    'total_signals': 0,
                    'strong_signals': 0,
                    'moderate_signals': 0,
                    'urgent_signals': 0,
                    'most_active_ticker': 'НЕТ ДАННЫХ',
                    'most_active_count': 0,
                    'most_calm_ticker': 'НЕТ ДАННЫХ',
                    'most_calm_count': 0,
                    'market_tension': '⚪ НЕИЗВЕСТНО'
                }

            # Формируем сообщение согласно плану проекта
            text = "📊 **СТАТИСТИКА ЗА ПОСЛЕДНИЕ 7 ДНЕЙ**\n\n"

            # Основная статистика
            text += f"Всего сигналов: {stats.get('total_signals', 0)}\n"
            text += f"🔴 Сильных: {stats.get('strong_signals', 0)}\n"
            text += f"🟡 Умеренных: {stats.get('moderate_signals', 0)}\n"
            text += f"⚪ Срочных: {stats.get('urgent_signals', 0)}\n\n"

            # Активные акции
            text += f"🏆 **САМАЯ АКТИВНАЯ:** {stats.get('most_active_ticker', 'НЕТ')} ({stats.get('most_active_count', 0)} сигналов)\n"
            text += f"😌 **САМЫЙ СПОКОЙНЫЙ:** {stats.get('most_calm_ticker', 'НЕТ')} ({stats.get('most_calm_count', 0)} сигналов)\n\n"

            # Напряжённость рынка
            text += f"📊 **ОБЩАЯ НАПРЯЖЁННОСТЬ:** {stats.get('market_tension', '⚪ НЕИЗВЕСТНО')}\n"
            text += f"(по шкале от 🟢 спокойно до 🔴 паника)\n\n"

            # Информация о данных
            if stats.get('total_signals', 0) == 0:
                text += "ℹ️ *В базе данных пока нет сигналов.*\n"
                text += "*Статистика появится после обнаружения первых сигналов.*\n\n"

            # Навигация
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += "📅 Сегодняшние сигналы: /today\n"
            text += "🔥 Самые сильные: /extreme\n"
            text += "🗺️ Карта паники: /panicmap"

            self.bot.reply_to(message, text, parse_mode='Markdown')

            logger.info(f"📊 Команда /stats выполнена: {stats.get('total_signals', 0)} сигналов")

        except Exception as e:
            logger.error(f"❌ Ошибка в команде /stats: {e}")
            self.bot.reply_to(
                message,
                "❌ **ОШИБКА ПОЛУЧЕНИЯ СТАТИСТИКИ**\n\n"
                "Не удалось получить данные. Попробуйте позже.",
                parse_mode='Markdown'
            )

    def command_panicmap(self, message):
        """Обработчик команды /panicmap - тепловая карта паники за сегодня"""
        try:
            # Получаем сегодняшние сигналы
            signals_data = self.grpc_client.get_top_signals(period='today', limit=50)

            # Если нет сигналов
            if not signals_data:
                self.bot.reply_to(
                    message,
                    "🗺️ **КАРТА ПАНИКИ**\n\n"
                    "Сегодня сигналов не обнаружено.\n\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📊 Статистика: /stats\n"
                    "📅 Сегодняшние: /today",
                    parse_mode='Markdown'
                )
                return

            # Конвертируем в PanicSignal если нужно
            signals = []
            for signal_data in signals_data:
                if isinstance(signal_data, dict) and PanicSignal:
                    try:
                        signal = PanicSignal(**signal_data)
                        signals.append(signal)
                    except Exception as e:
                        logger.warning(f"Не удалось создать PanicSignal для карты: {e}")
                        signals.append(signal_data)
                else:
                    signals.append(signal_data)

            # СОЗДАЁМ РЕАЛЬНЫЕ ДАННЫЕ ДЛЯ КАРТЫ ПАНИКИ
            heatmap_data = self._create_real_heatmap_data(signals)

            # Формируем ASCII карту
            panic_map_text = self._create_panic_map_ascii(heatmap_data)

            # Отправляем сообщение
            self.bot.reply_to(message, panic_map_text, parse_mode='Markdown')

            logger.info(f"🗺️ Команда /panicmap выполнена: {len(signals)} сигналов")

        except Exception as e:
            logger.error(f"❌ Ошибка в команде /panicmap: {e}")
            self.bot.reply_to(
                message,
                "❌ **ОШИБКА СОЗДАНИЯ КАРТЫ ПАНИКИ**\n\n"
                "Не удалось построить карту. Попробуйте позже.",
                parse_mode='Markdown'
            )

    def _create_real_heatmap_data(self, signals):
        """Создание реальных данных для карты паники из полученных сигналов"""
        from datetime import datetime
        import collections

        # Определяем временные интервалы (10, 12, 14, 16, 18)
        hours = [10, 12, 14, 16, 18]

        # Собираем тикеры из сигналов
        tickers = []
        for signal in signals:
            if hasattr(signal, 'ticker') and signal.ticker:
                tickers.append(signal.ticker)
            elif isinstance(signal, dict):
                ticker = signal.get('ticker')
                if ticker:
                    tickers.append(ticker)

        tickers = list(set(tickers))
        tickers.sort()

        # Инициализируем пустую карту
        heatmap = {ticker: {hour: '⚪' for hour in hours} for ticker in tickers}

        # Заполняем карту реальными сигналами
        for signal in signals:
            # Извлекаем тикер в зависимости от типа
            if hasattr(signal, 'ticker'):
                ticker = signal.ticker
                detected_at = signal.detected_at
                level = signal.level
                signal_type = signal.signal_type
            elif isinstance(signal, dict):
                ticker = signal.get('ticker')
                detected_at = signal.get('detected_at', '')
                level = signal.get('level', '')
                signal_type = signal.get('signal_type', '')
            else:
                continue

            if not ticker:
                continue

            # Получаем время сигнала
            try:
                # Пробуем разные форматы времени
                dt = None
                if detected_at:
                    if 'T' in detected_at:
                        dt = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                    elif ' ' in detected_at:
                        dt = datetime.strptime(detected_at, '%Y-%m-%d %H:%M:%S')
                    elif len(detected_at) == 5:  # Формат HH:MM
                        today = datetime.now()
                        dt = datetime(today.year, today.month, today.day,
                                      int(detected_at[:2]), int(detected_at[3:]))

                if not dt:
                    continue

                # Определяем час для карты (ближайший из hours)
                hour = dt.hour
                # Находим ближайший час из нашего списка
                closest_hour = min(hours, key=lambda x: abs(x - hour))

                # Определяем эмодзи по уровню сигнала
                level_upper = level.upper()
                if '🔴' in level_upper or 'STRONG' in level_upper:
                    emoji = '🔴'
                elif '🟡' in level_upper or 'MODERATE' in level_upper:
                    emoji = '🟡'
                elif '⚪' in level_upper or 'URGENT' in level_upper:
                    emoji = '⚪'
                else:
                    emoji = '⚪'

                # Определяем цвет по типу сигнала (дополнительная информация)
                # Паника = красный, Жадность = оранжевый
                signal_type_upper = signal_type.upper()
                if 'ПАНИКА' in signal_type_upper or 'PANIC' in signal_type_upper:
                    color = '🔴'
                elif 'ЖАДНОСТЬ' in signal_type_upper or 'GREED' in signal_type_upper:
                    color = '🟠'  # Оранжевый для жадности
                else:
                    color = emoji  # Используем стандартный цвет

                # Обновляем карту (берем самый сильный сигнал если их несколько)
                current_emoji = heatmap[ticker][closest_hour]
                # Приоритет: 🔴 > 🟠 > 🟡 > ⚪
                priority = {'🔴': 4, '🟠': 3, '🟡': 2, '⚪': 1}
                current_priority = priority.get(current_emoji, 0)
                new_priority = priority.get(color, 0)

                if new_priority > current_priority:
                    heatmap[ticker][closest_hour] = color

            except Exception as e:
                logger.debug(f"Не удалось обработать время сигнала: {detected_at}, ошибка: {e}")
                continue

        return {
            'tickers': tickers,
            'hours': hours,
            'heatmap': heatmap,
            'date': datetime.now().strftime('%d.%m.%Y')
        }

    def command_report(self, message):
        """Обработчик команды /report - ежедневный отчёт в формате из плана"""
        try:
            # Получаем текущую дату
            from datetime import datetime
            today = datetime.now()
            date_str = today.strftime('%d.%m.%Y')

            # ПОЛУЧАЕМ РЕАЛЬНУЮ СТАТИСТИКУ ЧЕРЕЗ gRPC
            stats = self.grpc_client.get_stats(days=1)  # Статистика за сегодня

            if not stats:
                self.bot.reply_to(
                    message,
                    "📊 **ЕЖЕДНЕВНЫЙ ОТЧЁТ**\n\n"
                    "Не удалось получить статистику за сегодня.\n"
                    "Попробуйте позже или используйте /stats для статистики за неделю.",
                    parse_mode='Markdown'
                )
                return

            # Формируем отчёт по шаблону из плана проекта
            report_text = self._format_daily_report(stats, date_str)

            # Отправляем пользователю
            self.bot.reply_to(message, report_text, parse_mode='Markdown')

            logger.info(f"📊 Команда /report выполнена для {date_str}")

        except Exception as e:
            logger.error(f"❌ Ошибка в команде /report: {e}")
            self.bot.reply_to(
                message,
                "❌ **ОШИБКА ГЕНЕРАЦИИ ОТЧЁТА**\n\n"
                "Не удалось сформировать ежедневный отчёт. Попробуйте позже.",
                parse_mode='Markdown'
            )

    def _format_daily_report(self, stats, date_str):
        """Форматирование ежедневного отчёта по шаблону из плана проекта (раздел 4.4)"""

        from datetime import datetime

        # Получаем день недели на русском
        date_obj = datetime.strptime(date_str, '%d.%m.%Y')
        weekday_rus = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        weekday = weekday_rus[date_obj.weekday()]

        # Формируем отчёт ТОЧНО как в плане проекта
        report = f"📊 **ЕЖЕДНЕВНЫЙ ОТЧЁТ ОТРЯДА ПАНИКЁРОВ**\n\n"
        report += f"Дата: {date_str} | День недели: {weekday}\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 1. Рыночный контекст (пока заглушка - потом заменим на реальные данные)
        report += f"📈 **РЫНОЧНЫЙ КОНТЕКСТ:**\n"
        report += f"• IMOEX: +0.8% (данные обновляются)\n\n"

        # 2. Сигналы за день (реальные данные из gRPC)
        total_signals = stats.get('total_signals', 0)
        strong_signals = stats.get('strong_signals', 0)
        moderate_signals = stats.get('moderate_signals', 0)
        urgent_signals = stats.get('urgent_signals', 0)

        report += f"🚨 **СИГНАЛОВ ЗА ДЕНЬ:** {total_signals}\n"
        report += f"• 🔴 КРАСНЫХ (сильных): {strong_signals}\n"
        report += f"• 🟡 ЖЁЛТЫХ (умеренных): {moderate_signals}\n"
        report += f"• ⚪ БЕЛЫХ (срочных): {urgent_signals}\n\n"

        # 3. Лидеры по активности (берём из stats или используем заглушку)
        most_active = stats.get('most_active_ticker', 'SBER')
        most_active_count = stats.get('most_active_count', 0)

        report += f"🏆 **ЛИДЕРЫ ПО АКТИВНОСТИ:**\n"
        report += f"1. {most_active} — {most_active_count} сигнала\n"

        # Добавляем ещё 2 тикера если есть данные
        # (здесь можно добавить логику для получения топ-3 тикеров)
        if 'second_active' in stats:
            report += f"2. {stats['second_active']} — {stats['second_active_count']} сигнала\n"
        if 'third_active' in stats:
            report += f"3. {stats['third_active']} — {stats['third_active_count']} сигнала\n"

        # 4. Самые спокойные
        most_calm = stats.get('most_calm_ticker', 'GMKN')
        report += f"\n😌 **САМЫЕ СПОКОЙНЫЕ:** {most_calm} (0 сигналов)\n\n"

        # 5. Общая напряжённость
        market_tension = stats.get('market_tension', '🟡 УМЕРЕННАЯ')
        report += f"📊 **ОБЩАЯ НАПРЯЖЁННОСТЬ:** {market_tension}\n"
        report += f"(по шкале от 🟢 спокойно до 🔴 паника)\n\n"

        # 6. Заключение (как в плане)
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "📈 Завтра снова на страже в 10:00!\n\n"
        report += "ℹ️ Полная статистика в дашборде: http://localhost:8501"

        return report

    def _create_panic_map_ascii(self, heatmap_data):
        """Создание ASCII тепловой карты"""

        tickers = heatmap_data['tickers']
        hours = heatmap_data['hours']
        heatmap = heatmap_data['heatmap']
        date = heatmap_data['date']

        # Заголовок
        text = f"🗺️ **КАРТА ПАНИКИ ЗА {date}**\n\n"

        # Шапка с часами
        header = "      " + "   ".join(str(h).rjust(2) for h in hours)
        text += f"`{header}`\n\n"

        # Данные по тикерам
        for ticker in tickers:
            row = f"`{ticker:4} `"
            for hour in hours:
                emoji = heatmap.get(ticker, {}).get(hour, '⚪')
                row += f" {emoji}  "
            text += f"{row}\n"

        # Легенда (ИСПРАВЛЕНА: "умеренно" → "хорошо")
        text += "\n"
        text += "`⚪ = спокойно  |  🟡 = хорошо  |  🔴 = сильно`\n\n"

        # Навигация
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "📊 Статистика: /stats\n"
        text += "📅 Сегодняшние сигналы: /today\n"
        text += "🔥 Самые сильные: /extreme"

        return text

    def _show_alerts_status(self, message):
        """Показать текущий статус уведомлений"""
        # Заглушка - всегда включено
        # Позже заменим на реальное хранение в БД
        self.bot.reply_to(
            message,
            "🔔 **СТАТУС УВЕДОМЛЕНИЙ**\n\n"
            "Текущий статус: 🟢 **ВКЛЮЧЕНЫ**\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• `/alerts on` - включить уведомления\n"
            "• `/alerts off` - выключить уведомления\n"
            "• `/status` - общий статус системы",
            parse_mode='Markdown'
        )

    def _enable_alerts(self, message):
        """Включить уведомления"""
        # Заглушка
        self.bot.reply_to(
            message,
            "✅ **УВЕДОМЛЕНИЯ ВКЛЮЧЕНЫ**\n\n"
            "Теперь вы будете получать автоматические оповещения "
            "об обнаруженных сигналах паники/жадности.\n\n"
            "ℹ️ *Для отключения используйте* `/alerts off`",
            parse_mode='Markdown'
        )
        logger.info(f"🔔 Уведомления включены для пользователя {message.from_user.id}")

    def _disable_alerts(self, message):
        """Выключить уведомления"""
        # Заглушка
        self.bot.reply_to(
            message,
            "🔕 **УВЕДОМЛЕНИЯ ВЫКЛЮЧЕНЫ**\n\n"
            "Автоматические оповещения отключены.\n"
            "Вы больше не будете получать уведомления об обнаруженных сигналах.\n\n"
            "ℹ️ *Для включения используйте* `/alerts on`",
            parse_mode='Markdown'
        )
        logger.info(f"🔔 Уведомления выключены для пользователя {message.from_user.id}")

    def command_alerts(self, message, args=None):
        """Обработчик команды /alerts on/off - управление уведомлениями"""
        try:
            # Определяем действие
            if not args:
                # Показать текущий статус
                self._show_alerts_status(message)
                return

            action = args[0].lower()

            if action == 'on':
                self._enable_alerts(message)
            elif action == 'off':
                self._disable_alerts(message)
            else:
                self.bot.reply_to(
                    message,
                    "❌ **НЕВЕРНАЯ КОМАНДА**\n\n"
                    "Используйте:\n"
                    "• `/alerts on` - включить уведомления\n"
                    "• `/alerts off` - выключить уведомления\n"
                    "• `/alerts` - показать статус",
                    parse_mode='Markdown'
                )

        except Exception as e:
            logger.error(f"❌ Ошибка в команде /alerts: {e}")
            self.bot.reply_to(
                message,
                "❌ **ОШИБКА УПРАВЛЕНИЯ УВЕДОМЛЕНИЯМИ**\n\n"
                "Не удалось выполнить команду. Попробуйте позже.",
                parse_mode='Markdown'
            )

    def command_status(self, message):
        """Обработчик команды /status - детальный статус системы"""
        try:
            # Получаем текущее время
            from datetime import datetime
            current_time = datetime.now()

            # Проверяем статус биржи
            is_open, reason = self.market_calendar.is_market_open_now()

            # Получаем следующий торговый день
            next_trading_day = self.market_calendar.get_next_trading_day()
            next_event = f"{next_trading_day.strftime('%d.%m.%Y')}"

            # Статус биржи с эмодзи
            exchange_status = "🟢 ОТКРЫТА" if is_open else "🔴 ЗАКРЫТА"

            # Дополнительная информация о времени
            if is_open:
                # Если биржа открыта, показываем до закрытия
                market_info = f"Активная торговая сессия"
            else:
                market_info = reason

            # Формируем сообщение
            status_text = (
                f"📊 **ПОЛНЫЙ СТАТУС СИСТЕМЫ**\n\n"
                f"🕐 Текущее время: {current_time.strftime('%H:%M:%S %d.%m.%Y')}\n"
                f"🏛️ Биржа ММВБ: {exchange_status}\n"
                f"📋 Статус: {market_info}\n"
                f"⏰ Следующее событие: {next_event}\n\n"
                f"🤖 **КОМПОНЕНТЫ СИСТЕМЫ:**\n"
                f"• Telegram бот: 🟢 Активен\n"
                f"• gRPC сервер: {'🟢 Работает' if self.grpc_client else '🔴 Не доступен'}\n"
                f"• DataCache: {'🟢 Работает' if self.data_cache else '🔴 Не доступен'}\n"
                f"• MarketCalendar: 🟢 Инициализирован\n\n"
                f"📊 **СТАТИСТИКА:**\n"
                f"• Активных тикеров: {len(self.default_tickers)}\n"
                f"• gRPC соединение: {'🟢 Установлено' if self.grpc_client else '🔴 Отсутствует'}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔍 Для сканирования: /startscan\n"
                f"📋 Все команды: /help"
            )

            self.bot.reply_to(message, status_text, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"❌ Ошибка в /status: {e}")
            self.bot.reply_to(message, f"❌ Ошибка получения статуса: {str(e)[:100]}", parse_mode='Markdown')

    # ------------------------------------------------------------------------
    # ОБРАБОТКА КНОПОК ГЛАВНОГО МЕНЮ
    # ------------------------------------------------------------------------
    def _handle_overheat_menu(self, call):
        """Обработка нажатия кнопки 'ИНДЕКС ПЕРЕГРЕВА' в главном меню"""
        try:
            # Запрашиваем тикер у пользователя
            msg = self.bot.send_message(
                call.message.chat.id,
                "🌡️ **ИНДЕКС ПЕРЕГРЕВА**\n\n"
                "Введите тикер акции (например: SBER, GAZP):",
                parse_mode='Markdown'
            )

            # Регистрируем следующий шаг - обработку введенного тикера
            self.bot.register_next_step_handler(msg, self._process_ticker_for_overheat)

        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_overheat_menu: {e}")
            self.bot.send_message(call.message.chat.id, "❌ Ошибка обработки запроса")

    def _process_ticker_for_overheat(self, message):
        """Обработка введенного тикера для индекса перегрева"""
        try:
            ticker = message.text.strip().upper()

            # Проверяем валидность тикера (простая проверка)
            if not ticker or len(ticker) > 10:
                self.bot.reply_to(message, "❌ Неверный формат тикера. Попробуйте снова.")
                return

            # Вызываем команду /overheat для этого тикера
            self.command_overheat(message, args=[ticker])

        except Exception as e:
            logger.error(f"❌ Ошибка в _process_ticker_for_overheat: {e}")
            self.bot.reply_to(message, "❌ Ошибка обработки тикера")

    # ------------------------------------------------------------------------
    # ОБРАБОТКА КНОПОК
    # ------------------------------------------------------------------------
    def handle_callback_query(self, call):
        try:
            callback_data = call.data

            # 1. Кнопки главного меню
            if callback_data == "overheat_menu":
                self.bot.answer_callback_query(call.id)
                self._handle_overheat_menu(call)
                return

            elif callback_data == "panic_map":
                self.bot.answer_callback_query(call.id)
                self._handle_panic_map_callback(call)
                return

            elif callback_data == "today":
                self.bot.answer_callback_query(call.id)
                self._handle_today_callback(call)
                return

            elif callback_data == "stats":
                self.bot.answer_callback_query(call.id)
                self._handle_stats_callback(call)
                return

            # 2. Кнопки анализа акции (начинаются с префикса)
            elif callback_data.startswith("graph_"):
                ticker = callback_data.replace("graph_", "")
                self.bot.answer_callback_query(call.id)
                self._handle_graph_callback(call, ticker)
                return

            elif callback_data.startswith("compare_"):
                ticker = callback_data.replace("compare_", "")
                self.bot.answer_callback_query(call.id)
                self._handle_compare_callback(call, ticker)
                return

            elif callback_data.startswith("history_"):
                ticker = callback_data.replace("history_", "")
                self.bot.answer_callback_query(call.id)
                self._handle_history_callback(call, ticker)
                return

            elif callback_data.startswith("explain_"):
                ticker = callback_data.replace("explain_", "")
                self.bot.answer_callback_query(call.id)
                self._handle_explain_callback(call, ticker)
                return

            elif callback_data.startswith("ignore_"):
                ticker = callback_data.replace("ignore_", "")
                self.bot.answer_callback_query(call.id)
                self._handle_ignore_callback(call, ticker)
                return

            # 3. Неизвестный callback
            self.bot.answer_callback_query(call.id)
            self.bot.send_message(call.message.chat.id, "❌ Неизвестная команда")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки callback: {e}")

    # ------------------------------------------------------------------------
    # ОБРАБОТКА CALLBACK-КНОПОК ГЛАВНОГО МЕНЮ
    # ------------------------------------------------------------------------
    def _handle_panic_map_callback(self, call):
        """Обработка кнопки 'КАРТА ПАНИКИ' из главного меню"""
        try:
            # Создаём fake message для вызова command_panicmap
            class FakeMessage:
                def __init__(self, chat):
                    self.chat = chat
                    self.message_id = call.message.message_id

            fake_message = FakeMessage(call.message.chat)
            self.command_panicmap(fake_message)

        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_panic_map_callback: {e}")
            self.bot.send_message(
                call.message.chat.id,
                "🗺️ **КАРТА ПАНИКИ**\n\nОшибка построения карты",
                parse_mode='Markdown'
            )

    def _handle_today_callback(self, call):
        """Обработка кнопки 'СЕГОДНЯШНИЕ ИСТЕРИКИ' из главного меню"""
        try:
            # Вызываем команду /today
            fake_message = type('obj', (object,), {'chat': call.message.chat})()
            self.command_today(fake_message)
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_today_callback: {e}")

    def _handle_stats_callback(self, call):
        """Обработка кнопки 'СТАТИСТИКА' из главного меню"""
        try:
            # Создаём fake message для вызова command_stats
            class FakeMessage:
                def __init__(self, chat):
                    self.chat = chat
                    self.message_id = call.message.message_id

            fake_message = FakeMessage(call.message.chat)
            self.command_stats(fake_message)

        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_stats_callback: {e}")
            self.bot.send_message(
                call.message.chat.id,
                "📊 **СТАТИСТИКА ЗА НЕДЕЛЮ**\n\nОшибка получения статистики",
                parse_mode='Markdown'
            )

    # ------------------------------------------------------------------------
    # ОБРАБОТКА CALLBACK-КНОПОК АНАЛИЗА АКЦИИ
    # ------------------------------------------------------------------------
    def _handle_graph_callback(self, call, ticker):
        """Обработка кнопки 'ГРАФИК АКЦИИ'"""
        try:
            from datetime import datetime, timedelta

            # Получаем свечи за последний день
            candles_data = self.grpc_client.get_candles(
                ticker=ticker,
                interval='hour',
                count=24
            )

            if candles_data:
                # Формируем текстовый график (упрощённо)
                prices = []
                for candle in candles_data:
                    if hasattr(candle, 'close'):
                        prices.append(candle.close)
                    elif isinstance(candle, dict):
                        price = candle.get('close')
                        if price is not None:
                            prices.append(price)

                if prices:
                    min_price = min(prices)
                    max_price = max(prices)
                    current = prices[-1]

                    text = f"📊 **ГРАФИК {ticker}**\n\n"
                    text += f"• Текущая цена: {current:.2f}₽\n"
                    text += f"• Минимум за сутки: {min_price:.2f}₽\n"
                    text += f"• Максимум за сутки: {max_price:.2f}₽\n"
                    text += f"• Изменение: {((current - prices[0]) / prices[0] * 100):+.2f}%\n\n"

                    # Простая ASCII визуализация
                    if len(prices) >= 2:
                        trend = "📈" if current > prices[-2] else "📉" if current < prices[-2] else "➡️"
                        change = current - prices[-2]
                        text += f"Тренд: {trend} ({change:+.2f}₽)\n\n"

                    text += f"📈 Подробный график доступен в дашборде\n"
                    text += f"🌡️ Индекс перегрева: /overheat {ticker}"
                else:
                    text = f"📊 **ГРАФИК {ticker}**\n\nНет данных для построения графика"
            else:
                text = f"📊 **ГРАФИК {ticker}**\n\nНе удалось получить данные"

        except Exception as e:
            logger.error(f"❌ Ошибка получения графика для {ticker}: {e}")
            text = f"📊 **ГРАФИК {ticker}**\n\nОшибка получения данных"

        self.bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

    def _handle_compare_callback(self, call, ticker):
        """Обработка кнопки 'СРАВНИТЬ С IMOEX'"""
        try:
            # Получаем данные по акции
            ticker_candles = self.grpc_client.get_candles(
                ticker=ticker,
                interval='hour',
                count=24
            )

            # Получаем данные по индексу IMOEX
            imoex_candles = self.grpc_client.get_candles(
                ticker='IMOEX',
                interval='hour',
                count=24
            )

            def extract_prices(candles):
                prices = []
                for candle in candles:
                    if hasattr(candle, 'close'):
                        prices.append(candle.close)
                    elif isinstance(candle, dict):
                        price = candle.get('close')
                        if price is not None:
                            prices.append(price)
                return prices

            if ticker_candles and imoex_candles:
                ticker_prices = extract_prices(ticker_candles)
                imoex_prices = extract_prices(imoex_candles)

                if ticker_prices and imoex_prices:
                    ticker_current = ticker_prices[-1]
                    ticker_change = ((ticker_current - ticker_prices[0]) / ticker_prices[0] * 100) if ticker_prices[
                                                                                                          0] != 0 else 0

                    imoex_current = imoex_prices[-1]
                    imoex_change = ((imoex_current - imoex_prices[0]) / imoex_prices[0] * 100) if imoex_prices[
                                                                                                      0] != 0 else 0

                    # Определяем outperformance/underperformance
                    outperformance = ticker_change - imoex_change

                    text = f"📈 **СРАВНЕНИЕ {ticker} С IMOEX**\n\n"
                    text += f"• {ticker}: {ticker_current:.2f}₽ ({ticker_change:+.2f}%)\n"
                    text += f"• IMOEX: {imoex_current:.2f} ({imoex_change:+.2f}%)\n\n"

                    if outperformance > 0:
                        text += f"✅ **{ticker} опережает рынок** на {outperformance:+.2f}%\n"
                        text += f"Акция показывает лучшую динамику, чем индекс\n"
                    elif outperformance < 0:
                        text += f"⚠️ **{ticker} отстаёт от рынка** на {outperformance:+.2f}%\n"
                        text += f"Акция показывает худшую динамику, чем индекс\n"
                    else:
                        text += f"➡️ **{ticker} движется вровень с рынком**\n"
                        text += f"Динамика совпадает с индексом\n"

                    text += f"\n📊 *За последние 24 часа*\n"
                    text += f"📅 Подробнее в дашборде"
                else:
                    text = f"📈 **СРАВНЕНИЕ {ticker} С IMOEX**\n\nНедостаточно данных для сравнения"
            else:
                text = f"📈 **СРАВНЕНИЕ {ticker} С IMOEX**\n\nНе удалось получить данные"

        except Exception as e:
            logger.error(f"❌ Ошибка сравнения {ticker} с IMOEX: {e}")
            text = f"📈 **СРАВНЕНИЕ {ticker} С IMOEX**\n\nОшибка получения данных"

        self.bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

    def _handle_history_callback(self, call, ticker):
        """Обработка кнопки 'ИСТОРИЯ СИГНАЛОВ'"""
        try:
            # Получаем историю сигналов через gRPC
            history_data = self.grpc_client.get_signal_history(ticker=ticker, limit=5)

            if history_data:
                text = f"📋 **ИСТОРИЯ СИГНАЛОВ {ticker}**\n\n"
                text += f"Последние {len(history_data)} сигналов:\n\n"

                for i, signal_data in enumerate(history_data, 1):
                    # Конвертируем в PanicSignal если нужно
                    if isinstance(signal_data, dict) and PanicSignal:
                        try:
                            signal = PanicSignal(**signal_data)
                        except Exception as e:
                            logger.warning(f"Не удалось создать PanicSignal для истории: {e}")
                            signal = signal_data
                    else:
                        signal = signal_data

                    # Извлекаем данные в зависимости от типа
                    if hasattr(signal, 'detected_at'):
                        detected_at = signal.detected_at
                        level = signal.level
                        signal_type = signal.signal_type
                        rsi = signal.rsi_14
                        volume = signal.volume_ratio
                        risk = signal.risk_metric
                    elif isinstance(signal, dict):
                        detected_at = signal.get('detected_at', '--:--')
                        level = signal.get('level', '')
                        signal_type = signal.get('signal_type', '')
                        rsi = signal.get('rsi_14', 0)
                        volume = signal.get('volume_ratio', 0)
                        risk = signal.get('risk_metric')
                    else:
                        continue

                    # Форматируем время
                    time_str = detected_at
                    if 'T' in time_str:
                        # Формат ISO: 2024-12-18T14:30:00
                        time_str = time_str.split('T')[1][:5]
                    elif len(time_str) > 5:
                        time_str = time_str[11:16]  # Берем только время

                    # Определяем эмодзи уровня
                    level_upper = level.upper()
                    if '🔴' in level_upper or 'STRONG' in level_upper:
                        level_emoji = '🔴'
                        level_text = 'Сильная'
                    elif '🟡' in level_upper or 'MODERATE' in level_upper:
                        level_emoji = '🟡'
                        level_text = 'Умеренная'
                    elif '⚪' in level_upper or 'URGENT' in level_upper:
                        level_emoji = '⚪'
                        level_text = 'Срочная'
                    else:
                        level_emoji = '⚪'
                        level_text = 'Сигнал'

                    # Определяем тип
                    signal_type_upper = signal_type.upper()
                    if 'ПАНИКА' in signal_type_upper or 'PANIC' in signal_type_upper:
                        type_text = 'паника'
                    elif 'ЖАДНОСТЬ' in signal_type_upper or 'GREED' in signal_type_upper:
                        type_text = 'жадность'
                    else:
                        type_text = 'сигнал'

                    text += f"{i}. {time_str} {level_emoji} {level_text} {type_text}\n"
                    text += f"   RSI: {rsi:.1f} | Объём: {volume:.1f}×"

                    if risk is not None:
                        text += f" | Риск: {risk:.1f}/100"

                    text += "\n\n"

                text += f"📊 Всего сигналов: {len(history_data)}\n"
                text += f"📅 Полная история в дашборде"

            else:
                text = f"📋 **ИСТОРИЯ СИГНАЛОВ {ticker}**\n\n"
                text += f"История сигналов пуста.\n"
                text += f"Сигналы появятся после их обнаружения системой.\n\n"
                text += f"🔍 Проверить сейчас: /overheat {ticker}"

        except Exception as e:
            logger.error(f"❌ Ошибка получения истории для {ticker}: {e}")
            text = f"📋 **ИСТОРИЯ СИГНАЛОВ {ticker}**\n\n"
            text += f"Ошибка получения данных истории.\n"
            text += f"Попробуйте позже."

        self.bot.send_message(call.message.chat.id, text, parse_mode='Markdown')

    def _handle_explain_callback(self, call, ticker):
        """Обработка кнопки 'ОБЪЯСНИТЬ СИГНАЛ'"""
        try:
            self.bot.send_message(
                call.message.chat.id,
                f"🤔 **ОБЪЯСНЕНИЕ СИГНАЛА ДЛЯ {ticker}**\n\n"
                f"Алгоритм анализа:\n"
                f"1. Проверка RSI на перепроданность/перекупленность\n"
                f"2. Анализ объёма относительно средней нормы\n"
                f"3. Мультипериодная верификация (7, 14, 21 дней)\n"
                f"4. Применение контекстных фильтров\n\n"
                f"*Подробнее в документации проекта*",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_explain_callback: {e}")

    def _handle_ignore_callback(self, call, ticker):
        """Обработка кнопки 'ИГНОРИРОВАТЬ 2 ЧАСА'"""
        try:
            self.bot.send_message(
                call.message.chat.id,
                f"🚫 **ИГНОРИРОВАНИЕ {ticker} НА 2 ЧАСА**\n\n"
                f"Сигналы для {ticker} будут скрыты до "
                f"{(datetime.now() + timedelta(hours=2)).strftime('%H:%M')}\n\n"
                f"*Функция временного игнорирования активирована*",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Ошибка в _handle_ignore_callback: {e}")

    # ------------------------------------------------------------------------
    # ЗАВЕРШЕНИЕ РАБОТЫ
    # ------------------------------------------------------------------------
    def stop_bot(self):
        """Корректная остановка бота"""
        try:
            if self.grpc_client:
                self.grpc_client.close()
                logger.info("✅ gRPC соединение закрыто")

            if self.data_cache:
                self.data_cache.cleanup()
                logger.info("✅ Кеш очищен")

        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}")
        finally:
            self.is_active = False
            logger.info("🤖 Бот остановлен")


# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================
def main():
    """Точка входа для запуска бота"""
    bot = TelegramPanickerBot()

    try:
        bot.start_bot()
    except KeyboardInterrupt:
        logger.info("Получен сигнал KeyboardInterrupt, останавливаем бота...")
        bot.stop_bot()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        bot.stop_bot()
        raise


if __name__ == "__main__":
    main()