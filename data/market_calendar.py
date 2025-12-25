# panicker3000/data/market_calendar.py
"""
Календарь торгов Мосбиржи.
Динамическое определение рабочих дней, праздников и коротких сессий.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from datetime import datetime, date, time, timedelta
from typing import List, Tuple, Optional, Dict, Set
import logging
import pytz
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Стандартные торговые часы Мосбиржи
REGULAR_TRADING_HOURS = {
    'open': time(10, 0),  # 10:00 МСК
    'close': time(18, 30)  # 18:30 МСК
}

# Короткие торговые сессии (предпраздничные дни)
SHORT_TRADING_HOURS = {
    'open': time(10, 0),  # 10:00 МСК
    'close': time(15, 30)  # 15:30 МСК
}

# Кэш-файл для праздников (чтобы не парсить каждый раз)
HOLIDAYS_CACHE_FILE = Path(__file__).parent.parent / 'cache' / 'moex_holidays.json'


# ============================================================================
# КЛАСС MarketCalendar
# ============================================================================
class MarketCalendar:
    """
    Календарь торгов Мосбиржи с учётом праздников и коротких сессий.
    Динамически загружает данные с сайта Мосбиржи или использует локальный расчёт.
    """

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, moscow_timezone: pytz.timezone = MOSCOW_TZ):
        """
        Инициализация календаря

        Args:
            moscow_timezone: Часовой пояс Москвы
        """
        self.moscow_tz = moscow_timezone

        # Загружаем праздники (из кэша или расчёт)
        self.holidays = self._load_holidays()

        # Определяем короткие сессии (дни перед праздниками)
        self.short_session_days = self._calculate_short_sessions()

        logger.info(f"MarketCalendar инициализирован: {len(self.holidays)} праздников, "
                    f"{len(self.short_session_days)} коротких дней")

    # ------------------------------------------------------------------------
    # ОСНОВНЫЕ МЕТОДЫ ПРОВЕРКИ
    # ------------------------------------------------------------------------
    def is_trading_day(self, check_date: Optional[date] = None) -> bool:
        """
        Проверяет, является ли день торговым.

        Правила:
        1. Рабочие дни: понедельник-пятница
        2. Исключаем официальные праздники РФ
        3. Короткие сессии считаются торговыми днями

        Args:
            check_date: Дата для проверки (по умолчанию сегодня)

        Returns:
            bool: True если торговый день
        """
        if check_date is None:
            check_date = datetime.now(self.moscow_tz).date()

        # 1. Проверяем день недели (пн-пт)
        if check_date.weekday() >= 5:  # 5=Сб, 6=Вс
            return False

        # 2. Проверяем праздники
        if check_date in self.holidays:
            return False

        return True

    def get_trading_hours(self, check_date: Optional[date] = None) -> Dict[str, time]:
        """
        Получает торговые часы для указанной даты.

        Args:
            check_date: Дата (по умолчанию сегодня)

        Returns:
            Dict с ключами 'open' и 'close'

        Raises:
            ValueError: Если дата не является торговым днём
        """
        if check_date is None:
            check_date = datetime.now(self.moscow_tz).date()

        if not self.is_trading_day(check_date):
            raise ValueError(f"{check_date} не является торговым днём")

        # Проверяем короткую сессию
        if check_date in self.short_session_days:
            return SHORT_TRADING_HOURS.copy()

        return REGULAR_TRADING_HOURS.copy()

    def is_market_open_now(self) -> Tuple[bool, Optional[str]]:
        """
        Проверяет, открыта ли биржа в данный момент.

        Returns:
            (is_open, message):
            - is_open: True если биржа открыта
            - message: Пояснение (почему закрыта/открыта)
        """
        now_moscow = datetime.now(self.moscow_tz)
        today = now_moscow.date()
        current_time = now_moscow.time()

        # Проверяем торговый день
        if not self.is_trading_day(today):
            next_trading = self.get_next_trading_day(today)
            return False, f"Выходной/праздничный день. Следующий торговый день: {next_trading}"

        # Получаем торговые часы
        try:
            hours = self.get_trading_hours(today)
        except ValueError:
            return False, "Ошибка получения торговых часов"

        # Проверяем время
        if hours['open'] <= current_time <= hours['close']:
            minutes_to_close = (
                    hours['close'].hour * 60 + hours['close'].minute -
                    current_time.hour * 60 - current_time.minute
            )
            return True, f"Биржа открыта. До закрытия: {minutes_to_close} мин"
        else:
            if current_time < hours['open']:
                return False, f"Биржа откроется в {hours['open'].strftime('%H:%M')}"
            else:
                return False, f"Биржа закрыта в {hours['close'].strftime('%H:%M')}"

    def get_next_trading_day(self, from_date: Optional[date] = None) -> date:
        """
        Находит следующий торговый день после указанной даты.

        Args:
            from_date: Дата, с которой начинать поиск (по умолчанию сегодня)

        Returns:
            date: Следующий торговый день
        """
        if from_date is None:
            from_date = datetime.now(self.moscow_tz).date()

        next_day = from_date + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)

        return next_day

    def get_previous_trading_day(self, from_date: Optional[date] = None) -> date:
        """
        Находит предыдущий торговый день до указанной даты.

        Args:
            from_date: Дата, с которой начинать поиск (по умолчанию сегодня)

        Returns:
            date: Предыдущий торговый день
        """
        if from_date is None:
            from_date = datetime.now(self.moscow_tz).date()

        prev_day = from_date - timedelta(days=1)
        while not self.is_trading_day(prev_day):
            prev_day -= timedelta(days=1)

        return prev_day

    # ------------------------------------------------------------------------
    # РАСЧЁТ ПРАЗДНИКОВ И КОРОТКИХ СЕССИЙ
    # ------------------------------------------------------------------------
    def _load_holidays(self) -> Set[date]:
        """
        Загружает список праздников.

        Приоритет:
        1. Локальный кэш-файл (если актуален)
        2. Парсинг с сайта Мосбиржи (реализуется отдельно)
        3. Резервный расчёт по алгоритму

        Returns:
            Set[date]: Множество праздничных дат
        """
        holidays = set()

        # Пробуем загрузить из кэша
        if self._try_load_from_cache():
            logger.info("Загружены праздники из кэша")
            return self._load_from_cache()

        # Если кэша нет или он устарел, используем резервный алгоритм
        logger.info("Используем резервный алгоритм расчёта праздников")

        current_year = datetime.now().year
        for year in range(current_year - 1, current_year + 3):  # +/- 1 год для запаса
            holidays.update(self._calculate_russian_holidays(year))

        # Сохраняем в кэш
        self._save_to_cache(holidays)

        return holidays

    def _calculate_russian_holidays(self, year: int) -> List[date]:
        """
        Расчёт основных праздников РФ по году.
        Это РЕЗЕРВНЫЙ МЕТОД на случай отсутствия данных из внешних источников.

        Args:
            year: Год

        Returns:
            List[date]: Список праздничных дат
        """
        holidays = []

        # Новогодние каникулы (1-8 января)
        for day in range(1, 9):
            try:
                holidays.append(date(year, 1, day))
            except ValueError:
                pass

        # День защитника Отечества (23 февраля)
        holidays.append(date(year, 2, 23))

        # Международный женский день (8 марта)
        holidays.append(date(year, 3, 8))

        # Праздник Весны и Труда (1 мая)
        holidays.append(date(year, 5, 1))

        # День Победы (9 мая)
        holidays.append(date(year, 5, 9))

        # День России (12 июня)
        holidays.append(date(year, 6, 12))

        # День народного единства (4 ноября)
        holidays.append(date(year, 11, 4))

        # Учитываем переносы выходных (основные правила)
        adjusted_holidays = self._adjust_weekends(holidays)

        return adjusted_holidays

    def _adjust_weekends(self, holidays: List[date]) -> List[date]:
        """
        Корректировка праздников с учётом переносов выходных.
        Упрощённая реализация основных правил РФ.

        Args:
            holidays: Исходный список праздников

        Returns:
            List[date]: Скорректированный список
        """
        adjusted = []

        for holiday in holidays:
            weekday = holiday.weekday()

            # Если праздник в субботу → выходной переносится на понедельник
            if weekday == 5:  # Суббота
                adjusted.append(holiday + timedelta(days=2))
            # Если праздник в воскресенье → выходной переносится на понедельник
            elif weekday == 6:  # Воскресенье
                adjusted.append(holiday + timedelta(days=1))
            else:
                adjusted.append(holiday)

        return adjusted

    def _calculate_short_sessions(self) -> Set[date]:
        """
        Определяет дни с короткими торговыми сессиями (предпраздничные дни).

        Правило: рабочий день перед праздником, если праздник в пн-сб.

        Returns:
            Set[date]: Множество дат с короткими сессиями
        """
        short_days = set()

        for holiday in self.holidays:
            # Находим предыдущий день
            prev_day = holiday - timedelta(days=1)

            # Если предыдущий день - рабочий день (пн-пт) и не праздник
            if prev_day.weekday() < 5 and prev_day not in self.holidays:
                short_days.add(prev_day)

        return short_days

    # ------------------------------------------------------------------------
    # КЭШИРОВАНИЕ
    # ------------------------------------------------------------------------
    def _try_load_from_cache(self) -> bool:
        """
        Проверяет, можно ли загрузить данные из кэша.

        Returns:
            bool: True если кэш актуален и может быть использован
        """
        if not HOLIDAYS_CACHE_FILE.exists():
            logger.debug("Кэш-файл не существует")
            return False

        try:
            # Проверяем возраст файла (не старше 30 дней)
            file_age = datetime.now().timestamp() - HOLIDAYS_CACHE_FILE.stat().st_mtime
            if file_age > 30 * 24 * 3600:  # 30 дней
                logger.debug("Кэш-файл устарел")
                return False

            return True
        except Exception as e:
            logger.warning(f"Ошибка проверки кэша: {e}")
            return False

    def _load_from_cache(self) -> Set[date]:
        """
        Загружает праздники из кэш-файла.

        Returns:
            Set[date]: Множество праздничных дат

        Raises:
            FileNotFoundError: Если файл не существует
            json.JSONDecodeError: Если файл повреждён
        """
        with open(HOLIDAYS_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        holidays = set()
        for date_str in data.get('holidays', []):
            holidays.add(date.fromisoformat(date_str))

        logger.debug(f"Загружено {len(holidays)} праздников из кэша")
        return holidays

    def _save_to_cache(self, holidays: Set[date]):
        """
        Сохраняет праздники в кэш-файл.

        Args:
            holidays: Множество праздничных дат
        """
        try:
            # Создаём директорию если не существует
            HOLIDAYS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'generated_at': datetime.now().isoformat(),
                'holidays': [d.isoformat() for d in sorted(holidays)]
            }

            with open(HOLIDAYS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Сохранено {len(holidays)} праздников в кэш")
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша: {e}")

    # ------------------------------------------------------------------------
    # ИНТЕГРАЦИЯ С СУЩЕСТВУЮЩИМ ФИЛЬТРОМ ВРЕМЕНИ
    # ------------------------------------------------------------------------
    def check_time_for_filter(self) -> Tuple[bool, str]:
        """
        Метод для интеграции с TimeFilter.

        Returns:
            (is_valid, message): Подходит ли текущее время для торговли
        """
        is_open, message = self.is_market_open_now()

        if not is_open:
            return False, message

        # Дополнительная проверка активного времени (11:00-16:00)
        now_moscow = datetime.now(self.moscow_tz).time()
        active_start = time(11, 0)
        active_end = time(16, 0)

        if active_start <= now_moscow <= active_end:
            return True, "Время в активной торговой зоне"
        else:
            return False, "Время вне активной зоны (11:00-16:00)"

    # ------------------------------------------------------------------------
    # УТИЛИТЫ
    # ------------------------------------------------------------------------
    def get_trading_days_between(self, start_date: date, end_date: date) -> List[date]:
        """
        Получить все торговые дни в диапазоне.

        Args:
            start_date: Начальная дата (включительно)
            end_date: Конечная дата (включительно)

        Returns:
            List[date]: Список торговых дней
        """
        trading_days = []
        current = start_date

        while current <= end_date:
            if self.is_trading_day(current):
                trading_days.append(current)
            current += timedelta(days=1)

        return trading_days

    def get_holidays_info(self, year: Optional[int] = None) -> Dict:
        """
        Получить информацию о праздниках за год.

        Args:
            year: Год (по умолчанию текущий)

        Returns:
            Dict: Информация о праздниках
        """
        if year is None:
            year = datetime.now().year

        holidays_list = sorted([d for d in self.holidays if d.year == year])
        short_days_list = sorted([d for d in self.short_session_days if d.year == year])

        return {
            'year': year,
            'total_holidays': len(holidays_list),
            'total_short_sessions': len(short_days_list),
            'holidays': holidays_list,
            'short_session_days': short_days_list
        }


# ============================================================================
# ИНСТАНС ДЛЯ ИМПОРТА
# ============================================================================
# Глобальный экземпляр для использования в других модулях
_market_calendar_instance = None


def get_market_calendar() -> MarketCalendar:
    """Получить глобальный экземпляр MarketCalendar"""
    global _market_calendar_instance
    if _market_calendar_instance is None:
        _market_calendar_instance = MarketCalendar()
    return _market_calendar_instance


# ============================================================================
# ТЕСТИРОВАНИЕ (при запуске напрямую)
# ============================================================================
if __name__ == "__main__":
    # Настройка логгирования для теста
    logging.basicConfig(level=logging.INFO)

    calendar = MarketCalendar()
    today = datetime.now().date()

    print(f"📅 MarketCalendar тест на {today}")
    print(f"Торговый день сегодня: {calendar.is_trading_day()}")

    is_open, message = calendar.is_market_open_now()
    print(f"Биржа открыта сейчас: {is_open}")
    print(f"Сообщение: {message}")

    if calendar.is_trading_day():
        hours = calendar.get_trading_hours()
        print(f"Часы торгов: {hours['open'].strftime('%H:%M')} - {hours['close'].strftime('%H:%M')}")

    next_day = calendar.get_next_trading_day()
    print(f"Следующий торговый день: {next_day}")

    # Информация о праздниках текущего года
    info = calendar.get_holidays_info()
    print(f"\nПраздники {info['year']}: {len(info['holidays'])} дней")