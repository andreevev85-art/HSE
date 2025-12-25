# panicker3000/core/filters/volatility_filter.py
"""
Фильтр волатильности (ATR).
Проверяет, достаточно ли движение на рынке для торговли.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from typing import Dict, Any, Tuple, Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# КЛАСС VolatilityFilter
# ============================================================================
class VolatilityFilter:
    """Фильтр проверки волатильности рынка"""

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация фильтра

        Args:
            config: Конфигурация фильтра
                - min_atr_ratio: минимальное отношение текущего ATR к среднему (по умолчанию 0.8)
                - min_absolute_atr: минимальный абсолютный ATR в процентах (по умолчанию 0.5%)
                - period: период для расчёта среднего ATR (по умолчанию 14)
        """
        self.config = config or {}

        # Параметры из конфига
        self.min_atr_ratio = self.config.get('min_atr_ratio', 0.8)
        self.min_absolute_atr = self.config.get('min_absolute_atr', 0.5)  # в процентах
        self.period = self.config.get('period', 14)

        logger.debug(
            f"VolatilityFilter инициализирован: min_ratio={self.min_atr_ratio}, min_abs={self.min_absolute_atr}%")

    # ------------------------------------------------------------------------
    # ОСНОВНОЙ МЕТОД: ПРОВЕРКА
    # ------------------------------------------------------------------------
    def check(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Проверяет, достаточно ли волатильность для торговли

        Args:
            signal_data: Данные сигнала (должен содержать 'current_atr', 'average_atr')

        Returns:
            (passed, message):
            - passed: True если волатильность достаточна
            - message: Пояснение результата
        """
        try:
            ticker = signal_data.get('ticker', 'UNKNOWN')
            current_atr = signal_data.get('current_atr')
            average_atr = signal_data.get('average_atr')
            price = signal_data.get('price')

            # 1. Проверка наличия данных
            if current_atr is None:
                return False, "Отсутствует текущий ATR"

            if average_atr is None:
                # Попробуем рассчитать средний ATR из исторических данных
                historical_atrs = signal_data.get('historical_atrs')
                if historical_atrs and len(historical_atrs) > 0:
                    average_atr = sum(historical_atrs) / len(historical_atrs)
                else:
                    return False, "Отсутствует средний ATR"

            # 2. Абсолютная проверка (минимальный ATR в процентах)
            if price and price > 0:
                atr_percent = (current_atr / price) * 100
                if atr_percent < self.min_absolute_atr:
                    return False, f"ATR слишком мал: {atr_percent:.1f}% < {self.min_absolute_atr}%"

            # 3. Относительная проверка (текущий ATR vs средний)
            atr_ratio = current_atr / average_atr if average_atr > 0 else 0

            if atr_ratio >= self.min_atr_ratio:
                return True, f"Волатильность достаточна: ATR={current_atr:.2f} ({atr_ratio:.1f}× от среднего)"
            else:
                return False, f"Волатильность низкая: ATR={current_atr:.2f} ({atr_ratio:.1f}× от среднего)"

        except ZeroDivisionError:
            return False, "Средний ATR равен нулю"
        except Exception as e:
            logger.error(f"Ошибка в VolatilityFilter для {ticker}: {e}")
            return False, f"Ошибка проверки волатильности: {e}"

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def calculate_atr(self, high_prices: List[float], low_prices: List[float],
                      close_prices: List[float], period: int = None) -> Optional[float]:
        """
        Рассчитывает Average True Range (ATR)

        Args:
            high_prices: Список максимальных цен
            low_prices: Список минимальных цен
            close_prices: Список цен закрытия
            period: Период для расчёта (по умолчанию self.period)

        Returns:
            Значение ATR или None при ошибке
        """
        if not all([high_prices, low_prices, close_prices]):
            return None

        period = period or self.period

        try:
            if len(high_prices) < period or len(low_prices) < period or len(close_prices) < period:
                logger.warning(f"Недостаточно данных для расчёта ATR (нужно {period}, есть {len(close_prices)})")
                return None

            # Рассчитываем True Range для каждого периода
            true_ranges = []

            for i in range(1, len(high_prices)):
                # Три варианта:
                # 1. High[i] - Low[i] (разница текущего дня)
                # 2. |High[i] - Close[i-1]| (разница с предыдущим закрытием)
                # 3. |Low[i] - Close[i-1]| (разница с предыдущим закрытием)

                hl = high_prices[i] - low_prices[i]
                hc = abs(high_prices[i] - close_prices[i - 1])
                lc = abs(low_prices[i] - close_prices[i - 1])

                true_range = max(hl, hc, lc)
                true_ranges.append(true_range)

            # Берем последние 'period' значений
            recent_tr = true_ranges[-period:] if len(true_ranges) >= period else true_ranges

            # ATR = среднее значение True Range
            atr = sum(recent_tr) / len(recent_tr)

            logger.debug(f"Рассчитан ATR: {atr:.2f} (период {period})")
            return atr

        except Exception as e:
            logger.error(f"Ошибка расчёта ATR: {e}")
            return None

    # ------------------------------------------------------------------------
    # МЕТОД: АНАЛИЗ ВОЛАТИЛЬНОСТИ
    # ------------------------------------------------------------------------
    def analyze_volatility(self, ticker: str, historical_data: Dict) -> Dict[str, Any]:
        """
        Анализ волатильности инструмента

        Args:
            ticker: Тикер акции
            historical_data: Исторические данные с ценами

        Returns:
            Словарь с результатами анализа
        """
        try:
            highs = historical_data.get('highs', [])
            lows = historical_data.get('lows', [])
            closes = historical_data.get('closes', [])

            if not all([highs, lows, closes]):
                return {'error': 'Недостаточно данных для анализа'}

            # Рассчитываем текущий ATR
            current_atr = self.calculate_atr(highs, lows, closes, self.period)

            # Рассчитываем средний ATR за более длинный период
            if len(closes) >= self.period * 3:
                # Берем данные для расчёта среднего ATR
                avg_atr = self.calculate_atr(
                    highs[-self.period * 3:],
                    lows[-self.period * 3:],
                    closes[-self.period * 3:],
                    self.period * 2
                )
            else:
                avg_atr = current_atr

            # Анализ
            atr_ratio = current_atr / avg_atr if avg_atr and avg_atr > 0 else 0

            volatility_level = "Низкая"
            if current_atr:
                if atr_ratio > 1.5:
                    volatility_level = "Очень высокая"
                elif atr_ratio > 1.2:
                    volatility_level = "Высокая"
                elif atr_ratio > 0.8:
                    volatility_level = "Нормальная"
                else:
                    volatility_level = "Низкая"

            return {
                'ticker': ticker,
                'current_atr': current_atr,
                'average_atr': avg_atr,
                'atr_ratio': atr_ratio,
                'volatility_level': volatility_level,
                'period': self.period
            }

        except Exception as e:
            logger.error(f"Ошибка анализа волатильности {ticker}: {e}")
            return {'error': str(e)}