# panicker3000/core/filters/time_filter.py
"""
Фильтр времени торговой сессии.
Исключает утренний/вечерний шум (работает только в 11:00-16:00 МСК).
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from typing import Dict, Any, Tuple
from datetime import datetime, time
import logging
import pytz

logger = logging.getLogger(__name__)

# ============================================================================
# ИСПРАВЛЕННЫЙ ИМПОРТ MARKET CALENDAR
# ============================================================================
import sys
import os

# Добавляем корень проекта в sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
panicker3000_dir = os.path.dirname(os.path.dirname(current_dir))
if panicker3000_dir not in sys.path:
    sys.path.insert(0, panicker3000_dir)

# Теперь пробуем импортировать
try:
    from data.market_calendar import get_market_calendar
    MARKET_CALENDAR_AVAILABLE = True
    logger.info("✅ MarketCalendar доступен для TimeFilter")
except ImportError as e:
    logger.warning(f"⚠️  MarketCalendar не доступен: {e}. Используется упрощённая проверка")
    MARKET_CALENDAR_AVAILABLE = False
    get_market_calendar = None

# ============================================================================
# КЛАСС TimeFilter
# ============================================================================
class TimeFilter:
    """Фильтр проверки времени торговой сессии"""

    # ------------------------------------------------------------------------
    # КОНСТАНТЫ
    # ------------------------------------------------------------------------
    # Активное время для торговли (МСК)
    ACTIVE_START = time(11, 0)  # 11:00
    ACTIVE_END = time(16, 0)  # 16:00

    # Полная торговая сессия MOEX (МСК)
    MARKET_OPEN = time(10, 0)  # 10:00
    MARKET_CLOSE = time(18, 30)  # 18:30

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация фильтра

        Args:
            config: Конфигурация фильтра (может переопределять константы)
        """
        self.config = config or {}
        self.calendar = None  # ДОБАВЛЯЕМ ЭТУ СТРОКУ

        # Инициализируем календарь если доступен
        if MARKET_CALENDAR_AVAILABLE and get_market_calendar:
            try:
                self.calendar = get_market_calendar()
                logger.info("✅ TimeFilter инициализирован с MarketCalendar")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации MarketCalendar: {e}")
                self.calendar = None
        else:
            logger.warning("⚠️  TimeFilter работает без MarketCalendar (упрощённый режим)")

        # Можно переопределить из конфига
        if 'active_start' in self.config:
            self.ACTIVE_START = self._parse_time(self.config['active_start'])
        if 'active_end' in self.config:
            self.ACTIVE_END = self._parse_time(self.config['active_end'])

        logger.debug(f"TimeFilter инициализирован: {self.ACTIVE_START}-{self.ACTIVE_END}")

    # ------------------------------------------------------------------------
    # ОСНОВНОЙ МЕТОД: ПРОВЕРКА
    # ------------------------------------------------------------------------
    def check(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Проверяет, находится ли текущее время в активной торговой зоне

        Args:
            signal_data: Данные сигнала (должен содержать 'timestamp')

        Returns:
            (passed, message):
            - passed: True если время в активной зоне
            - message: Пояснение результата
        """
        try:
            # Получаем время из данных сигнала
            current_dt = self._get_current_datetime(signal_data)
            current_time = current_dt.time()

            # 1. ПРОВЕРКА С CALENDAR (если доступен)
            if self.calendar is not None:
                return self._check_with_calendar(current_dt)

            # 2. РЕЗЕРВНЫЙ ВАРИАНТ (старая логика)
            # Проверка полной торговой сессии
            if not self._is_market_open(current_time):
                return False, f"Биржа закрыта ({current_time.strftime('%H:%M')})"

            # Проверка активной зоны
            if self._is_active_time(current_time):
                return True, f"Время в активной зоне ({current_time.strftime('%H:%M')})"
            else:
                return False, f"Время вне активной зоне ({current_time.strftime('%H:%M')})"

        except Exception as e:
            logger.error(f"Ошибка в TimeFilter: {e}")
            return False, f"Ошибка проверки времени: {e}"

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def _is_market_open(self, current_time: time) -> bool:
        """Проверяет, открыта ли биржа в принципе"""
        return self.MARKET_OPEN <= current_time <= self.MARKET_CLOSE

    def _is_active_time(self, current_time: time) -> bool:
        """Проверяет, находится ли время в активной зоне"""
        return self.ACTIVE_START <= current_time <= self.ACTIVE_END

    def _parse_time(self, time_str: str) -> time:
        """Парсит строку времени в объект time"""
        try:
            if ':' in time_str:
                hours, minutes = map(int, time_str.split(':'))
                return time(hours, minutes)
            else:
                # Если передано число (например, 1100)
                time_int = int(time_str)
                hours = time_int // 100
                minutes = time_int % 100
                return time(hours, minutes)
        except (ValueError, TypeError) as e:
            logger.warning(f"Не удалось распарсить время '{time_str}': {e}")
            return time(11, 0)  # Значение по умолчанию

    # ===================================================================
    # НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С CALENDAR
    # ===================================================================
    def _check_with_calendar(self, current_dt: datetime) -> Tuple[bool, str]:
        """Проверка времени с использованием MarketCalendar"""
        # 1. Проверяем торговый день и открыта ли биржа
        is_open, market_msg = self.calendar.is_market_open_now()

        if not is_open:
            return False, market_msg

        # 2. Проверка активной зоны (11:00-16:00)
        current_time = current_dt.time()

        if self._is_active_time(current_time):
            return True, f"Время в активной зоне ({current_time.strftime('%H:%M')})"
        else:
            return False, f"Время вне активной зоне ({current_time.strftime('%H:%M')})"

    def _get_current_datetime(self, signal_data: Dict[str, Any]) -> datetime:
        """Получаем текущее datetime с учётом данных сигнала"""
        timestamp = signal_data.get('timestamp')

        if not timestamp:
            return datetime.now(pytz.timezone('Europe/Moscow'))

        # Преобразуем к datetime если это строка
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return dt.astimezone(pytz.timezone('Europe/Moscow'))
            except ValueError:
                return datetime.now(pytz.timezone('Europe/Moscow'))
        elif isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                return timestamp.replace(tzinfo=pytz.timezone('Europe/Moscow'))
            return timestamp
        else:
            return datetime.now(pytz.timezone('Europe/Moscow'))

    # ------------------------------------------------------------------------
    # МЕТОДЫ ДЛЯ ТЕСТИРОВАНИЯ
    # ------------------------------------------------------------------------
    def get_active_hours(self) -> Tuple[time, time]:
        """Получить активные часы для отладки"""
        return self.ACTIVE_START, self.ACTIVE_END

    def get_market_hours(self) -> Tuple[time, time]:
        """Получить часы работы биржи"""
        return self.MARKET_OPEN, self.MARKET_CLOSE