"""
Расчёт риск-метрик для сигналов паники/жадности.
Используется для ранжирования силы сигналов.
"""

import logging
import math
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Уровни риска"""
    VERY_LOW = "очень низкий"
    LOW = "низкий"
    MODERATE = "умеренный"
    HIGH = "высокий"
    VERY_HIGH = "очень высокий"
    EXTREME = "экстремальный"


@dataclass
class RiskMetrics:
    """Метрики риска для сигнала"""
    risk_score: float  # Общая оценка риска (0-100)
    risk_level: RiskLevel  # Уровень риска
    rsi_component: float  # Вклад RSI в риск
    volume_component: float  # Вклад объёма в риск
    volatility_component: float  # Вклад волатильности в риск
    interpretation: str  # Текстовая интерпретация


class RiskCalculator:
    """
    Калькулятор риск-метрик для сигналов.
    """

    def __init__(self, atr_normal: float = 2.0):
        """
        Args:
            atr_normal: Нормальное значение ATR для нормализации
        """
        self.atr_normal = atr_normal
        self.risk_thresholds = {
            RiskLevel.VERY_LOW: 10,
            RiskLevel.LOW: 25,
            RiskLevel.MODERATE: 50,
            RiskLevel.HIGH: 75,
            RiskLevel.VERY_HIGH: 90,
            RiskLevel.EXTREME: 100
        }

    def calculate_risk(self,
                       rsi: float,
                       volume_ratio: float,
                       atr: float,
                       signal_type: str = "panic") -> RiskMetrics:
        """
        Рассчитать риск-метрику для сигнала.

        Формула из ТЗ:
        Риск = (|RSI - 50| / 50) × log₂(Объём_коэффициент) × (АТР / Норма)

        Args:
            rsi: Значение RSI (0-100)
            volume_ratio: Коэффициент объёма (текущий/средний)
            atr: Текущее значение ATR
            signal_type: Тип сигнала ('panic' или 'greed')

        Returns:
            Объект RiskMetrics с рассчитанными метриками
        """
        try:
            # 1. Компонент RSI (|RSI - 50| / 50)
            rsi_deviation = abs(rsi - 50)
            rsi_component = rsi_deviation / 50  # 0-1

            # Корректируем для крайних значений
            if rsi_component > 1.0:
                rsi_component = 1.0 + (rsi_component - 1.0) * 0.5

            # 2. Компонент объёма (log₂(Объём_коэффициент))
            if volume_ratio <= 0:
                volume_component = 0
            else:
                volume_component = math.log2(volume_ratio + 1)  # +1 чтобы избежать отрицательных значений

            # Нормализуем к 0-2 диапазону
            volume_component = min(volume_component, 2.0) / 2.0

            # 3. Компонент волатильности (АТР / Норма)
            if atr <= 0:
                volatility_component = 0
            else:
                volatility_component = atr / self.atr_normal

            # Ограничиваем разумными пределами
            volatility_component = min(volatility_component, 3.0) / 3.0

            # 4. Общая формула риска
            if rsi_component == 0:
                risk_score = 0
            else:
                risk_score = rsi_component * volume_component * volatility_component

            # Масштабируем к 0-100
            risk_score = risk_score * 100

            # 5. Определяем уровень риска
            risk_level = self._get_risk_level(risk_score)

            # 6. Формируем интерпретацию
            interpretation = self._get_interpretation(
                risk_score, risk_level, rsi_component,
                volume_component, volatility_component, signal_type
            )

            return RiskMetrics(
                risk_score=risk_score,
                risk_level=risk_level,
                rsi_component=rsi_component * 100,
                volume_component=volume_component * 100,
                volatility_component=volatility_component * 100,
                interpretation=interpretation
            )

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта риска: {e}")
            # Возвращаем минимальный риск при ошибке
            return RiskMetrics(
                risk_score=10,
                risk_level=RiskLevel.VERY_LOW,
                rsi_component=10,
                volume_component=10,
                volatility_component=10,
                interpretation="Ошибка расчёта риска"
            )

    def _get_risk_level(self, risk_score: float) -> RiskLevel:
        """Определить уровень риска на основе оценки"""
        if risk_score <= self.risk_thresholds[RiskLevel.VERY_LOW]:
            return RiskLevel.VERY_LOW
        elif risk_score <= self.risk_thresholds[RiskLevel.LOW]:
            return RiskLevel.LOW
        elif risk_score <= self.risk_thresholds[RiskLevel.MODERATE]:
            return RiskLevel.MODERATE
        elif risk_score <= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif risk_score <= self.risk_thresholds[RiskLevel.VERY_HIGH]:
            return RiskLevel.VERY_HIGH
        else:
            return RiskLevel.EXTREME

    def _get_interpretation(self,
                            risk_score: float,
                            risk_level: RiskLevel,
                            rsi_component: float,
                            volume_component: float,
                            volatility_component: float,
                            signal_type: str) -> str:
        """Сформировать текстовую интерпретацию риска"""

        # Определяем основное сообщение
        level_messages = {
            RiskLevel.VERY_LOW: "Сигнал очень слабый",
            RiskLevel.LOW: "Сигнал слабый",
            RiskLevel.MODERATE: "Сигнал умеренной силы",
            RiskLevel.HIGH: "Сигнал сильный",
            RiskLevel.VERY_HIGH: "Сигнал очень сильный",
            RiskLevel.EXTREME: "ЭКСТРЕМАЛЬНЫЙ СИГНАЛ!"
        }

        main_message = level_messages.get(risk_level, "Сигнал")

        # Определяем тип сигнала
        signal_name = "паники" if signal_type.lower() == "panic" else "жадности"

        # Определяем доминирующий фактор
        components = [
            ("RSI", rsi_component),
            ("объём", volume_component),
            ("волатильность", volatility_component)
        ]
        dominant_factor = max(components, key=lambda x: x[1])[0]

        # Формируем интерпретацию
        interpretation = (
            f"{main_message} {signal_name}.\n"
            f"Оценка риска: {risk_score:.1f}/100 ({risk_level.value}).\n"
            f"Основной фактор: {dominant_factor}."
        )

        # Добавляем рекомендацию
        if risk_level in [RiskLevel.VERY_HIGH, RiskLevel.EXTREME]:
            interpretation += "\n⚠️  Требует немедленного внимания!"
        elif risk_level == RiskLevel.HIGH:
            interpretation += "\n📊 Рекомендуется пристальное наблюдение."
        elif risk_level == RiskLevel.MODERATE:
            interpretation += "\n👀 Рекомендуется мониторинг ситуации."
        else:
            interpretation += "\nℹ️  Можно отложить наблюдение."

        return interpretation

    def compare_risks(self, signals: list) -> list:
        """
        Сравнить риски нескольких сигналов для ранжирования.

        Args:
            signals: Список сигналов с полями rsi, volume_ratio, atr

        Returns:
            Отсортированный список сигналов по убыванию риска
        """
        if not signals:
            return []

        # Рассчитываем риск для каждого сигнала
        signals_with_risk = []
        for signal in signals:
            risk_metrics = self.calculate_risk(
                rsi=signal.get('rsi', 50),
                volume_ratio=signal.get('volume_ratio', 1),
                atr=signal.get('atr', self.atr_normal),
                signal_type=signal.get('signal_type', 'panic')
            )

            # Добавляем оценку риска к сигналу
            signal_copy = signal.copy()
            signal_copy['risk_score'] = risk_metrics.risk_score
            signal_copy['risk_level'] = risk_metrics.risk_level
            signal_copy['risk_interpretation'] = risk_metrics.interpretation
            signal_copy['risk_metrics'] = risk_metrics

            signals_with_risk.append(signal_copy)

        # Сортируем по убыванию риска
        sorted_signals = sorted(
            signals_with_risk,
            key=lambda x: x['risk_score'],
            reverse=True
        )

        logger.info(f"📊 Проранжировано {len(sorted_signals)} сигналов по риску")

        return sorted_signals
