# panicker3000/core/filters/trend_filter.py
"""
Фильтр тренда (скользящие средние).
Проверяет, соответствует ли сигнал текущему тренду.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from typing import Dict, Any, Tuple, Optional, List
import logging
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# ПЕРЕЧИСЛЕНИЯ
# ============================================================================
class TrendDirection(Enum):
    """Направление тренда"""
    BULLISH = "bullish"  # Восходящий
    BEARISH = "bearish"  # Нисходящий
    SIDEWAYS = "sideways"  # Боковой


class TradeAction(Enum):
    """Торговое действие"""
    BUY = "buy"  # Покупка
    SELL = "sell"  # Продажа


# ============================================================================
# КЛАСС TrendFilter
# ============================================================================
class TrendFilter:
    """Фильтр проверки тренда"""

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, config: Dict[str, Any] = None):
        """
        Инициализация фильтра

        Args:
            config: Конфигурация фильтра
                - ma_period: период скользящей средней (по умолчанию 20)
                - trend_threshold: минимальное отклонение от MA в % для определения тренда
                - require_trend_alignment: требовать соответствия тренду (True/False)
        """
        self.config = config or {}

        # Параметры из конфига
        self.ma_period = self.config.get('ma_period', 20)
        self.trend_threshold = self.config.get('trend_threshold', 1.0)  # в процентах
        self.require_trend_alignment = self.config.get('require_trend_alignment', True)

        logger.debug(f"TrendFilter инициализирован: MA{self.ma_period}, threshold={self.trend_threshold}%")

    # ------------------------------------------------------------------------
    # ОСНОВНОЙ МЕТОД: ПРОВЕРКА
    # ------------------------------------------------------------------------
    def check(self, signal_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Проверяет, соответствует ли сигнал текущему тренду

        Правила:
        - Для покупки (паники): цена должна быть выше SMA20 (восходящий тренд)
        - Для продажи (жадности): цена должна быть ниже SMA20 (нисходящий тренд)

        Args:
            signal_data: Данные сигнала

        Returns:
            (passed, message):
            - passed: True если сигнал соответствует тренду
            - message: Пояснение результата
        """
        try:
            ticker = signal_data.get('ticker', 'UNKNOWN')
            signal_type = signal_data.get('signal_type')  # 'panic' или 'greed'
            current_price = signal_data.get('price')
            sma_value = signal_data.get(f'sma_{self.ma_period}')

            # 1. Проверка наличия данных
            if current_price is None:
                return False, "Отсутствует текущая цена"

            if sma_value is None:
                # Попробуем рассчитать SMA из исторических данных
                historical_prices = signal_data.get('historical_prices')
                if historical_prices and len(historical_prices) >= self.ma_period:
                    sma_value = self.calculate_sma(historical_prices, self.ma_period)
                else:
                    return False, f"Отсутствует SMA{self.ma_period}"

            # 2. Если не требуется соответствие тренду, пропускаем
            if not self.require_trend_alignment:
                return True, f"Соответствие тренду не требуется"

            # 3. Определяем торговое действие по типу сигнала
            if signal_type == 'panic':
                trade_action = TradeAction.BUY
            elif signal_type == 'greed':
                trade_action = TradeAction.SELL
            else:
                # Если тип сигнала не указан, анализируем по RSI
                rsi = signal_data.get('rsi', signal_data.get('rsi_14'))
                if rsi is not None:
                    trade_action = TradeAction.BUY if rsi < 30 else TradeAction.SELL
                else:
                    return False, "Неопределён тип сигнала"

            # 4. Проверяем соответствие тренду
            if trade_action == TradeAction.BUY:
                # Для покупки: цена должна быть выше SMA
                if current_price > sma_value:
                    deviation = ((current_price - sma_value) / sma_value) * 100
                    return True, f"Покупка: цена {current_price:.2f} > SMA{sma_value:.2f} (+{deviation:.1f}%)"
                else:
                    deviation = ((sma_value - current_price) / sma_value) * 100
                    return False, f"Покупка: цена {current_price:.2f} < SMA{sma_value:.2f} (-{deviation:.1f}%)"

            else:  # TradeAction.SELL
                # Для продажи: цена должна быть ниже SMA
                if current_price < sma_value:
                    deviation = ((sma_value - current_price) / sma_value) * 100
                    return True, f"Продажа: цена {current_price:.2f} < SMA{sma_value:.2f} (-{deviation:.1f}%)"
                else:
                    deviation = ((current_price - sma_value) / sma_value) * 100
                    return False, f"Продажа: цена {current_price:.2f} > SMA{sma_value:.2f} (+{deviation:.1f}%)"

        except Exception as e:
            logger.error(f"Ошибка в TrendFilter для {ticker}: {e}")
            return False, f"Ошибка проверки тренда: {e}"

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def calculate_sma(self, prices: List[float], period: int = None) -> Optional[float]:
        """
        Рассчитывает Simple Moving Average

        Args:
            prices: Список цен
            period: Период для расчёта (по умолчанию self.ma_period)

        Returns:
            Значение SMA или None при ошибке
        """
        if not prices:
            return None

        period = period or self.ma_period

        if len(prices) < period:
            logger.warning(f"Недостаточно данных для SMA{period} (нужно {period}, есть {len(prices)})")
            return None

        try:
            # Берём последние 'period' значений
            recent_prices = prices[-period:]
            sma = sum(recent_prices) / period

            logger.debug(f"Рассчитана SMA{period}: {sma:.2f}")
            return sma

        except Exception as e:
            logger.error(f"Ошибка расчёта SMA: {e}")
            return None

    def calculate_ema(self, prices: List[float], period: int = None) -> Optional[float]:
        """
        Рассчитывает Exponential Moving Average

        Args:
            prices: Список цен
            period: Период для расчёта (по умолчанию self.ma_period)

        Returns:
            Значение EMA или None при ошибке
        """
        if not prices or len(prices) < period:
            return None

        period = period or self.ma_period

        try:
            # Начинаем с SMA как первое значение EMA
            sma = self.calculate_sma(prices[:period], period)
            if sma is None:
                return None

            multiplier = 2 / (period + 1)
            ema = sma

            # Рассчитываем EMA для оставшихся цен
            for price in prices[period:]:
                ema = (price - ema) * multiplier + ema

            logger.debug(f"Рассчитана EMA{period}: {ema:.2f}")
            return ema

        except Exception as e:
            logger.error(f"Ошибка расчёта EMA: {e}")
            return None

    # ------------------------------------------------------------------------
    # МЕТОД: АНАЛИЗ ТРЕНДА
    # ------------------------------------------------------------------------
    def analyze_trend(self, ticker: str, prices: List[float],
                      use_ema: bool = False) -> Dict[str, Any]:
        """
        Анализ тренда инструмента

        Args:
            ticker: Тикер акции
            prices: Список цен
            use_ema: Использовать EMA вместо SMA

        Returns:
            Словарь с результатами анализа
        """
        try:
            if not prices or len(prices) < self.ma_period:
                return {'error': f'Недостаточно данных (нужно {self.ma_period}, есть {len(prices)})'}

            current_price = prices[-1]

            # Рассчитываем среднюю
            if use_ema:
                ma_value = self.calculate_ema(prices, self.ma_period)
                ma_type = 'EMA'
            else:
                ma_value = self.calculate_sma(prices, self.ma_period)
                ma_type = 'SMA'

            if ma_value is None:
                return {'error': 'Не удалось рассчитать скользящую среднюю'}

            # Определяем направление тренда
            price_ma_ratio = (current_price / ma_value - 1) * 100  # Отклонение в %

            if abs(price_ma_ratio) < self.trend_threshold:
                trend = TrendDirection.SIDEWAYS
                strength = "Слабый"
            elif price_ma_ratio > 0:
                trend = TrendDirection.BULLISH
                strength = "Сильный" if price_ma_ratio > 2 * self.trend_threshold else "Умеренный"
            else:
                trend = TrendDirection.BEARISH
                strength = "Сильный" if abs(price_ma_ratio) > 2 * self.trend_threshold else "Умеренный"

            return {
                'ticker': ticker,
                'current_price': current_price,
                'ma_value': ma_value,
                'ma_type': ma_type,
                'ma_period': self.ma_period,
                'deviation_percent': price_ma_ratio,
                'trend': trend.value,
                'trend_strength': strength,
                'trend_direction': trend
            }

        except Exception as e:
            logger.error(f"Ошибка анализа тренда {ticker}: {e}")
            return {'error': str(e)}