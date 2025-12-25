# panicker3000/core/filters/volume_filter.py
"""
Фильтр анализа объёма.
Проверяет, достаточно ли текущий объём превышает среднедневной.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from typing import Dict, Any, Tuple, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============================================================================
# КЛАСС VolumeFilter
# ============================================================================
class VolumeFilter:
    """Фильтр проверки объёма торгов"""

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация фильтра

        Args:
            config: Конфигурация фильтра
                - min_volume_ratio: минимальный коэффициент объёма (по умолчанию 1.5)
                - use_forecast: использовать прогноз объёма на день (True/False)
        """
        self.config = config or {}

        # Параметры из конфига или значения по умолчанию
        self.min_volume_ratio = self.config.get('min_volume_ratio', 1.5)
        self.use_forecast = self.config.get('use_forecast', True)

        # Кеш для среднедневных объёмов {ticker: avg_volume}
        self.volume_cache = {}
        self.cache_expiry = {}

        logger.debug(f"VolumeFilter инициализирован: min_ratio={self.min_volume_ratio}")

    # ------------------------------------------------------------------------
    # ОСНОВНОЙ МЕТОД: ПРОВЕРКА
    # ------------------------------------------------------------------------
    def check(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Проверяет, достаточно ли текущий объём превышает норму

        Args:
            signal_data: Данные сигнала (должен содержать 'ticker', 'current_volume')

        Returns:
            (passed, message):
            - passed: True если объём достаточно высокий
            - message: Пояснение результата с коэффициентом
        """
        try:
            # Получаем данные из сигнала
            ticker = signal_data.get('ticker')
            current_volume = signal_data.get('current_volume')

            if not ticker:
                return False, "Отсутствует тикер"

            if current_volume is None:
                return False, "Отсутствует текущий объём"

            # Получаем среднедневной объём
            avg_volume = self._get_average_volume(ticker, signal_data)

            if avg_volume is None or avg_volume <= 0:
                return False, f"Нет данных по среднему объёму для {ticker}"

            # Рассчитываем коэффициент
            volume_ratio = current_volume / avg_volume

            # Проверяем порог
            if volume_ratio >= self.min_volume_ratio:
                return True, f"Объём {volume_ratio:.1f}× от нормы ({current_volume:.0f}/{avg_volume:.0f})"
            else:
                return False, f"Объём недостаточен: {volume_ratio:.1f}× < {self.min_volume_ratio}×"

        except ZeroDivisionError:
            return False, "Средний объём равен нулю"
        except Exception as e:
            logger.error(f"Ошибка в VolumeFilter для {ticker}: {e}")
            return False, f"Ошибка проверки объёма: {e}"

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def _get_average_volume(self, ticker: str, signal_data: Dict) -> Optional[float]:
        """
        Получает среднедневной объём для тикера

        Логика:
        1. Если есть исторические данные в signal_data -> расчёт из них
        2. Если есть кеш и он не устарел -> из кеша
        3. Иначе -> запрос к Tinkoff API за историческими данными
        """
        # 1. Проверяем исторические данные в signal_data
        historical_volumes = signal_data.get('historical_volumes')
        if historical_volumes and len(historical_volumes) > 0:
            avg = sum(historical_volumes) / len(historical_volumes)
            logger.debug(f"Средний объём {ticker} из исторических данных: {avg:.0f}")
            return avg

        # 2. Проверяем кеш
        if ticker in self.volume_cache:
            expiry_time = self.cache_expiry.get(ticker)
            if expiry_time and datetime.now() < expiry_time:
                logger.debug(f"Средний объём {ticker} из кеша: {self.volume_cache[ticker]:.0f}")
                return self.volume_cache[ticker]

        # 3. Запрашиваем исторические данные через TinkoffClient
        try:
            # Импортируем здесь, чтобы избежать циклических зависимостей
            from data.tinkoff_client import TinkoffClient

            client = TinkoffClient()

            # Запрашиваем дневные свечи за последние 20 дней
            candles = client.get_candles(
                ticker=ticker,
                interval='day',
                count=20
            )

            if candles and len(candles) > 0:
                # Извлекаем объёмы из свечей
                volumes = [candle['volume'] for candle in candles if 'volume' in candle]

                if volumes:
                    avg_volume = sum(volumes) / len(volumes)

                    # Сохраняем в кеш на 1 час
                    self.volume_cache[ticker] = avg_volume
                    self.cache_expiry[ticker] = datetime.now() + timedelta(hours=1)

                    logger.info(f"✅ Средний объём {ticker} из API: {avg_volume:.0f}")
                    return avg_volume
                else:
                    logger.warning(f"⚠️ Нет данных объёма в свечах для {ticker}")
            else:
                logger.warning(f"⚠️ Не удалось получить свечи для {ticker}")

        except ImportError as e:
            logger.error(f"❌ Не удалось импортировать TinkoffClient: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка запроса среднего объёма для {ticker}: {e}")

        # 4. Fallback: возвращаем None, если не удалось получить данные
        logger.warning(f"⚠️ Не удалось получить средний объём для {ticker}")
        return None

    # ------------------------------------------------------------------------
    # МЕТОД: ПРОГНОЗ НА ДЕНЬ
    # ------------------------------------------------------------------------
    def get_volume_forecast(self, ticker: str) -> Optional[float]:
        """
        Прогноз объёма на текущий день (опционально)

        Args:
            ticker: Тикер акции

        Returns:
            Прогнозируемый объём на день или None
        """
        if not self.use_forecast:
            return None

        try:
            avg_volume = self._get_average_volume(ticker, {'ticker': ticker})

            if avg_volume is None:
                return None

            # Более точный прогноз на основе времени дня и дня недели
            now = datetime.now()
            hour = now.hour
            weekday = now.weekday()  # 0=понедельник, 4=пятница

            # Базовый множитель на основе времени дня
            if hour < 10:
                time_factor = 0.6  # До открытия
            elif hour < 11:
                time_factor = 0.8  # Первый час
            elif hour < 15:
                time_factor = 1.0  # Пиковые часы
            elif hour < 17:
                time_factor = 0.9  # Послеобеденное время
            else:
                time_factor = 0.7  # Конец дня

            # Корректировка на день недели
            if weekday == 0:  # Понедельник
                day_factor = 1.1
            elif weekday == 4:  # Пятница
                day_factor = 0.9
            else:
                day_factor = 1.0

            # Итоговый прогноз
            forecast = avg_volume * time_factor * day_factor

            logger.debug(f"📊 Прогноз объёма {ticker}: {forecast:.0f} "
                         f"(время: {time_factor:.1f}, день: {day_factor:.1f})")

            return forecast

        except Exception as e:
            logger.error(f"❌ Ошибка прогноза объёма для {ticker}: {e}")
            return None

    # ------------------------------------------------------------------------
    # МЕТОДЫ ДЛЯ ТЕСТИРОВАНИЯ
    # ------------------------------------------------------------------------
    def set_average_volume(self, ticker: str, volume: float, expiry_hours: int = 1):
        """Установить средний объём для тестирования"""
        self.volume_cache[ticker] = volume
        self.cache_expiry[ticker] = datetime.now() + timedelta(hours=expiry_hours)

    def clear_cache(self):
        """Очистить кеш объёмов"""
        self.volume_cache.clear()
        self.cache_expiry.clear()