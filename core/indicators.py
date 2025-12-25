# panicker3000/core/indicators.py
"""
Модуль расчёта технических индикаторов.
Реализует чистые математические формулы без тестовых значений.
"""

import numpy as np
from typing import List, Optional, Tuple


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Расчёт RSI (Relative Strength Index) - возвращает список всех значений.

    Args:
        prices: Список цен (обычно закрытия)
        period: Период RSI (по умолчанию 14)

    Returns:
        Список значений RSI (первые period элементов = NaN) или пустой список при ошибке
    """
    try:
        return safe_calculate_rsi(prices, period)
    except Exception:
        return []


def safe_calculate_rsi(prices, period=14):
    """Безопасный расчёт RSI - возвращает список значений"""
    if len(prices) < period + 1:
        return []

    try:
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gains = np.zeros(len(gains))
        avg_losses = np.zeros(len(losses))

        # Первое значение SMA
        if len(gains) >= period:
            avg_gains[period - 1] = np.mean(gains[:period])
            avg_losses[period - 1] = np.mean(losses[:period])
        else:
            return []

        # Остальные значения
        for i in range(period, len(gains)):
            avg_gains[i] = (avg_gains[i - 1] * (period - 1) + gains[i]) / period
            avg_losses[i] = (avg_losses[i - 1] * (period - 1) + losses[i]) / period

        with np.errstate(divide='ignore', invalid='ignore'):
            # Делим только где avg_losses != 0
            rs = np.divide(avg_gains, avg_losses, where=avg_losses != 0)
            # Где avg_losses = 0, устанавливаем RS = 100
            rs[avg_losses == 0] = 100.0

        rsi = 100 - (100 / (1 + rs))

        # Добавляем NaN в начало
        result = [float('nan')] * period
        result.extend(rsi[period - 1:].tolist())

        return result
    except Exception:
        return []


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[float]:
    """
    Расчёт ATR (Average True Range) - средний истинный диапазон.

    Формула:
    1. TrueRange = max(high-low, |high-prev_close|, |low-prev_close|)
    2. ATR = скользящее среднее(TrueRange, период)

    Args:
        highs: Список максимальных цен
        lows: Список минимальных цен
        closes: Список цен закрытия
        period: Период ATR (по умолчанию 14)

    Returns:
        Список значений ATR (первые period элементов = None)
    """
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return [None] * len(closes)

    # 1. Рассчитываем True Range
    tr_values = []

    for i in range(1, len(highs)):
        high_low = highs[i] - lows[i]
        high_prev_close = abs(highs[i] - closes[i - 1])
        low_prev_close = abs(lows[i] - closes[i - 1])

        true_range = max(high_low, high_prev_close, low_prev_close)
        tr_values.append(true_range)

    # 2. Рассчитываем ATR (простое скользящее среднее)
    atr_values = []

    for i in range(len(tr_values)):
        if i < period - 1:  # -1 потому что tr_values начинается с 1
            atr_values.append(None)
        elif i == period - 1:
            # Первое значение ATR = среднее первых period TR
            atr_values.append(np.mean(tr_values[i - period + 1:i + 1]))
        else:
            # Формула Уайлдера для ATR
            current_atr = (atr_values[-1] * (period - 1) + tr_values[i]) / period
            atr_values.append(current_atr)

    # 3. Добавляем None для первого элемента (нет предыдущего закрытия)
    atr_full = [None] + atr_values

    return atr_full


def calculate_sma(prices: List[float], period: int = 20) -> List[float]:
    """
    Расчёт SMA (Simple Moving Average) - простого скользящего среднего.

    Формула:
    SMA[i] = (цена[i] + цена[i-1] + ... + цена[i-period+1]) / period

    Args:
        prices: Список цен
        period: Период SMA

    Returns:
        Список значений SMA (первые period-1 элементов = None)
    """
    if len(prices) < period:
        return [None] * len(prices)

    sma_values = []

    for i in range(len(prices)):
        if i < period - 1:
            sma_values.append(None)
        else:
            window = prices[i - period + 1:i + 1]
            sma_values.append(np.mean(window))

    return sma_values


def calculate_ema(prices: List[float], period: int = 20) -> List[float]:
    """
    Расчёт EMA (Exponential Moving Average) - экспоненциального скользящего среднего.

    Формула:
    1. Multiplier = 2 / (period + 1)
    2. EMA[period] = SMA(period)  # первое значение
    3. EMA[i] = (цена[i] - EMA[i-1]) * multiplier + EMA[i-1]

    Args:
        prices: Список цен
        period: Период EMA

    Returns:
        Список значений EMA (первые period-1 элементов = None)
    """
    if len(prices) < period:
        return [None] * len(prices)

    # 1. Рассчитываем SMA для первого значения EMA
    sma = calculate_sma(prices, period)

    # 2. Коэффициент сглаживания
    multiplier = 2 / (period + 1)

    # 3. Рассчитываем EMA
    ema_values = [None] * (period - 1)

    if sma[period - 1] is not None:
        ema_values.append(sma[period - 1])  # Первое значение EMA = SMA

        for i in range(period, len(prices)):
            current_ema = (prices[i] - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(current_ema)
    else:
        ema_values = [None] * len(prices)

    return ema_values


# Вспомогательная функция для расчета объёмного коэффициента
def calculate_volume_ratio(current_volume: float, historical_volumes: List[float]) -> float:
    """
    Расчёт отношения текущего объёма к среднему историческому.

    Args:
        current_volume: Текущий объём
        historical_volumes: Список исторических объёмов

    Returns:
        Коэффициент: current_volume / average_volume
    """
    if not historical_volumes:
        return 1.0

    avg_volume = np.mean(historical_volumes)

    if avg_volume == 0:
        return 1.0

    return current_volume / avg_volume