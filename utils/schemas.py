# panicker3000/utils/schemas.py
"""
Pydantic схемы для валидации данных в проекте Паникёр 3000.

Используются для:
1. Валидации сигналов
2. Проверки данных от Tinkoff API
3. Конфигурации gRPC
4. Обеспечения типизации между модулями
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field, validator, root_validator
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# ENUM ДЛЯ ТИПОВ СИГНАЛОВ
# ============================================================================
class SignalType(str, Enum):
    """Тип сигнала"""
    PANIC = "panic"  # Перепроданность (покупка)
    GREED = "greed"  # Перекупленность (продажа)


class BaseLevel(str, Enum):
    """Базовый уровень сигнала (после шага 5)"""
    STRONG = "strong"  # Сильный (все 3 периода подтверждают)
    GOOD = "good"  # Хороший (2 периода подтверждают)
    URGENT = "urgent"  # Срочный (только RSI14)
    NONE = "none"  # Нет сигнала


class FinalLevel(str, Enum):
    """Финальный уровень сигнала (после фильтров)"""
    RED = "red"  # 🔴 Сильный - для немедленного рассмотрения
    YELLOW = "yellow"  # 🟡 Хороший - для пристального внимания
    WHITE = "white"  # ⚪ Срочный - раннее предупреждение
    IGNORE = "ignore"  # ❌ Игнорировать


# ============================================================================
# СХЕМА: КЛАСТЕР ОБЪЁМА (ШАГ 9)
# ============================================================================
class VolumeCluster(BaseModel):
    """Кластер объёма для шага 9 алгоритма"""

    price_level: float = Field(..., description="Ценовой уровень кластера")
    volume_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Доля объёма на этом уровне (0-100%)"
    )
    volume_amount: Optional[float] = Field(
        None,
        description="Абсолютное значение объёма"
    )
    role: str = Field(
        "neutral",
        description="Роль уровня: support/resistance/neutral"
    )

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['support', 'resistance', 'neutral']
        if v not in allowed_roles:
            raise ValueError(f"Роль должна быть одной из: {allowed_roles}")
        return v

    class Config:
        """Конфигурация Pydantic"""
        schema_extra = {
            "example": {
                "price_level": 310.50,
                "volume_percentage": 45.2,
                "volume_amount": 150000000.0,
                "role": "support"
            }
        }


# ============================================================================
# СХЕМА: РИСК-МЕТРИКИ (ШАГ 10)
# ============================================================================
class RiskMetrics(BaseModel):
    """Риск-метрики для шага 10 алгоритма"""

    risk_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Общая оценка риска (0-100)"
    )
    rsi_component: float = Field(
        ...,
        description="Вклад RSI в риск"
    )
    volume_component: float = Field(
        ...,
        description="Вклад объёма в риск"
    )
    atr_component: Optional[float] = Field(
        None,
        description="Вклад волатильности (ATR) в риск"
    )
    interpretation: str = Field(
        ...,
        description="Текстовое описание риска"
    )

    @validator('risk_score')
    def validate_risk_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError("risk_score должен быть в диапазоне 0-100")
        return v

    class Config:
        schema_extra = {
            "example": {
                "risk_score": 65.5,
                "rsi_component": 0.7,
                "volume_component": 0.8,
                "atr_component": 0.6,
                "interpretation": "Высокий риск: сильная перекупленность + аномальный объём"
            }
        }


# ============================================================================
# ОСНОВНАЯ СХЕМА: СИГНАЛ ПАНИКИ (ЗАМЕНА dataclass)
# ============================================================================
class PanicSignal(BaseModel):
    """
    Полная схема сигнала паники/жадности
    Заменяет dataclass PanicSignal из panic_detector.py
    """

    # Основные данные
    ticker: str = Field(..., description="Тикер акции (SBER, GAZP и т.д.)")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Время обнаружения сигнала"
    )
    signal_type: SignalType = Field(
        ...,
        description="Тип сигнала: паника или жадность"
    )

    # Параметры RSI
    rsi_7: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="RSI за 7 дней"
    )
    rsi_14: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="RSI за 14 дней (основной)"
    )
    rsi_21: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="RSI за 21 дней"
    )

    # Объём
    volume_ratio: float = Field(
        ...,
        gt=0.0,
        description="Коэффициент объёма (текущий/средний)"
    )
    current_volume: Optional[float] = Field(
        None,
        gt=0.0,
        description="Текущий объём"
    )
    average_volume: Optional[float] = Field(
        None,
        gt=0.0,
        description="Средний дневной объём"
    )

    # Уровни
    base_level: BaseLevel = Field(..., description="Базовый уровень после шага 5")
    final_level: FinalLevel = Field(..., description="Финальный уровень после фильтров")

    # Фильтры
    passed_filters: List[str] = Field(
        default_factory=list,
        description="Список пройденных фильтров"
    )
    failed_filters: List[str] = Field(
        default_factory=list,
        description="Список непройденных фильтров"
    )

    # Контекст
    price: Optional[float] = Field(None, gt=0.0, description="Текущая цена")
    atr: Optional[float] = Field(None, gt=0.0, description="Average True Range")
    sma_20: Optional[float] = Field(None, description="Простая скользящая средняя за 20 дней")
    spread_percent: float = Field(
        default=0.1,
        ge=0.0,
        description="Спред в процентах (bid-ask spread)"
    )

    # Шаг 9: Кластеры объёма
    volume_clusters: List[VolumeCluster] = Field(
        default_factory=list,
        description="Список кластеров объёма"
    )
    cluster_summary: str = Field(
        default="",
        description="Текстовое описание кластеров"
    )

    # Шаг 10: Риск-метрики
    risk_metric: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Числовая оценка риска (0-100)"
    )
    risk_interpretation: str = Field(
        default="",
        description="Текстовое описание риска"
    )

    # Сообщения
    interpretation: str = Field(
        ...,
        description="Интерпретация сигнала для пользователя"
    )
    recommendation: str = Field(
        ...,
        description="Рекомендация по действию"
    )
    risk_level: str = Field(
        ...,
        description="Уровень риска (текстовый)"
    )

    # Валидаторы
    @validator('rsi_14')
    def validate_rsi_14(cls, v):
        if v < 0 or v > 100:
            raise ValueError("RSI должен быть в диапазоне 0-100")
        return v

    @validator('volume_ratio')
    def validate_volume_ratio(cls, v):
        if v <= 0:
            raise ValueError("Коэффициент объёма должен быть положительным")
        return v

    @root_validator
    def validate_signal_consistency(cls, values):
        """Проверка согласованности данных сигнала"""
        signal_type = values.get('signal_type')
        rsi_14 = values.get('rsi_14')

        if signal_type and rsi_14:
            if signal_type == SignalType.PANIC and rsi_14 > 50:
                logger.warning(f"PANIC сигнал с RSI={rsi_14} > 50")
            elif signal_type == SignalType.GREED and rsi_14 < 50:
                logger.warning(f"GREED сигнал с RSI={rsi_14} < 50")

        return values

    # Методы
    def get_rsi_tuple(self) -> Tuple[Optional[float], float, Optional[float]]:
        """Получить RSI значения как кортеж"""
        return (self.rsi_7, self.rsi_14, self.rsi_21)

    def get_emoji_for_level(self) -> str:
        """Получить эмодзи для уровня сигнала"""
        emoji_map = {
            FinalLevel.RED: "🔴",
            FinalLevel.YELLOW: "🟡",
            FinalLevel.WHITE: "⚪",
            FinalLevel.IGNORE: "❌"
        }
        return emoji_map.get(self.final_level, "⚪")

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь (совместимость со старым кодом)"""
        result = self.dict()
        result['timestamp'] = self.timestamp.isoformat()
        return result

    class Config:
        """Конфигурация Pydantic для PanicSignal"""
        use_enum_values = True  # Сохранять enum как значения
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Enum: lambda v: v.value
        }
        schema_extra = {
            "example": {
                "ticker": "SBER",
                "timestamp": "2024-01-15T14:30:00",
                "signal_type": "panic",
                "rsi_7": 22.5,
                "rsi_14": 24.0,
                "rsi_21": 26.0,
                "volume_ratio": 2.3,
                "current_volume": 450000000.0,
                "average_volume": 195000000.0,
                "base_level": "strong",
                "final_level": "red",
                "passed_filters": ["volatility", "trend"],
                "failed_filters": ["volume"],
                "price": 310.50,
                "atr": 1.8,
                "sma_20": 305.0,
                "spread_percent": 0.05,
                "interpretation": "Сильная паника, акция перепродана",
                "recommendation": "Рассмотреть контртрендовую покупку",
                "risk_level": "Высокий"
            }
        }


# ============================================================================
# СХЕМА: ДАННЫЕ ТИКЕРА
# ============================================================================
class TickerData(BaseModel):
    """Данные по тикеру для анализа"""

    ticker: str = Field(..., description="Тикер акции")
    price: Optional[float] = Field(None, description="Текущая цена")
    rsi_7: Optional[float] = Field(None, description="RSI за 7 дней")
    rsi_14: Optional[float] = Field(None, description="RSI за 14 дней")
    rsi_21: Optional[float] = Field(None, description="RSI за 21 дней")
    volume_ratio: float = Field(1.0, description="Коэффициент объёма")
    current_volume: Optional[float] = Field(None, description="Текущий объём")
    average_volume: Optional[float] = Field(None, description="Средний объём")
    atr: Optional[float] = Field(None, description="Average True Range")
    sma_20: Optional[float] = Field(None, description="SMA за 20 дней")
    spread_percent: float = Field(0.1, description="Спред")

    # Для шага 9: исторические данные для анализа кластеров
    historical_prices: List[float] = Field(
        default_factory=list,
        description="Исторические цены за день"
    )
    historical_volumes: List[float] = Field(
        default_factory=list,
        description="Исторические объёмы за день"
    )

    # Методы
    def has_required_data(self) -> bool:
        """Проверка наличия минимально необходимых данных"""
        required = ['ticker', 'rsi_14', 'volume_ratio', 'price']
        return all(getattr(self, field) is not None for field in required)

    def validate_for_analysis(self) -> Tuple[bool, str]:
        """Валидация данных для анализа"""
        if not self.ticker:
            return False, "Нет тикера"
        if self.rsi_14 is None:
            return False, "Нет RSI14"
        if self.volume_ratio is None:
            return False, "Нет коэффициента объёма"
        if self.price is None:
            return False, "Нет текущей цены"
        return True, "Данные валидны"

    class Config:
        schema_extra = {
            "example": {
                "ticker": "SBER",
                "price": 310.50,
                "rsi_7": 22.5,
                "rsi_14": 24.0,
                "rsi_21": 26.0,
                "volume_ratio": 2.3,
                "current_volume": 450000000.0,
                "average_volume": 195000000.0,
                "atr": 1.8,
                "sma_20": 305.0,
                "spread_percent": 0.05,
                "historical_prices": [310.0, 309.5, 310.2, 310.5],
                "historical_volumes": [1000000, 1500000, 1200000, 1800000]
            }
        }


# ============================================================================
# СХЕМА: ЗАПРОС НА СКАНИРОВАНИЕ
# ============================================================================
class ScanRequest(BaseModel):
    """Запрос на сканирование тикера"""

    ticker: str = Field(..., description="Тикер для сканирования")
    include_clusters: bool = Field(
        True,
        description="Включать ли анализ кластеров объёма"
    )
    include_risk: bool = Field(
        True,
        description="Включать ли расчёт риск-метрик"
    )

    class Config:
        schema_extra = {
            "example": {
                "ticker": "SBER",
                "include_clusters": True,
                "include_risk": True
            }
        }


class ScanResponse(BaseModel):
    """Ответ на запрос сканирования"""

    success: bool = Field(..., description="Успешно ли выполнено сканирование")
    signal: Optional[PanicSignal] = Field(
        None,
        description="Обнаруженный сигнал (если есть)"
    )
    error_message: Optional[str] = Field(
        None,
        description="Сообщение об ошибке (если success=False)"
    )
    processing_time_ms: float = Field(
        ...,
        description="Время обработки в миллисекундах"
    )

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "signal": {...},  # Здесь будет PanicSignal
                "error_message": None,
                "processing_time_ms": 125.5
            }
        }


# ============================================================================
# СХЕМА: КОНФИГУРАЦИЯ
# ============================================================================
class ThresholdConfig(BaseModel):
    """Пороговые значения для уровней сигнала"""

    rsi_buy: float = Field(..., ge=0.0, le=100.0, description="RSI для покупки")
    rsi_sell: float = Field(..., ge=0.0, le=100.0, description="RSI для продажи")
    volume_min: float = Field(..., gt=0.0, description="Минимальный коэффициент объёма")


class PanicThresholds(BaseModel):
    """Все пороги для обнаружения паники"""

    red: ThresholdConfig
    yellow: ThresholdConfig
    white: ThresholdConfig

    @validator('red', 'yellow', 'white')
    def validate_thresholds(cls, v, values, field):
        """Проверка, что RSI для покупки < RSI для продажи"""
        if v.rsi_buy >= v.rsi_sell:
            raise ValueError(f"{field.name}: rsi_buy должен быть меньше rsi_sell")
        return v

    class Config:
        schema_extra = {
            "example": {
                "red": {
                    "rsi_buy": 25,
                    "rsi_sell": 75,
                    "volume_min": 2.0
                },
                "yellow": {
                    "rsi_buy": 30,
                    "rsi_sell": 70,
                    "volume_min": 1.5
                },
                "white": {
                    "rsi_buy": 35,
                    "rsi_sell": 65,
                    "volume_min": 1.2
                }
            }
        }


# ============================================================================
# СХЕМА: СТАТИСТИКА
# ============================================================================
class DailyStats(BaseModel):
    """Статистика за день"""

    date: str = Field(..., description="Дата в формате YYYY-MM-DD")
    total_signals: int = Field(0, ge=0, description="Всего сигналов")
    strong_signals: int = Field(0, ge=0, description="Сильных сигналов")
    moderate_signals: int = Field(0, ge=0, description="Умеренных сигналов")
    urgent_signals: int = Field(0, ge=0, description="Срочных сигналов")
    most_active_ticker: str = Field("", description="Самый активный тикер")
    most_active_count: int = Field(0, ge=0, description="Количество сигналов у самого активного")
    most_calm_ticker: str = Field("", description="Самый спокойный тикер")
    most_calm_count: int = Field(0, ge=0, description="Количество сигналов у самого спокойного")
    market_tension: str = Field("", description="Напряжённость рынка")

    class Config:
        schema_extra = {
            "example": {
                "date": "2024-01-15",
                "total_signals": 24,
                "strong_signals": 5,
                "moderate_signals": 12,
                "urgent_signals": 7,
                "most_active_ticker": "SBER",
                "most_active_count": 8,
                "most_calm_ticker": "GMKN",
                "most_calm_count": 1,
                "market_tension": "🟡 УМЕРЕННАЯ"
            }
        }


# ============================================================================
# ЭКСПОРТИРУЕМЫЕ ФУНКЦИИ
# ============================================================================
def validate_panic_signal(data: Dict[str, Any]) -> Tuple[bool, Optional[PanicSignal], str]:
    """
    Валидация данных сигнала

    Args:
        data: Словарь с данными сигнала

    Returns:
        (is_valid, panic_signal, error_message)
    """
    try:
        signal = PanicSignal(**data)
        return True, signal, "Сигнал валиден"
    except Exception as e:
        logger.error(f"❌ Ошибка валидации сигнала: {e}")
        return False, None, f"Ошибка валидации: {str(e)}"


def validate_ticker_data(data: Dict[str, Any]) -> Tuple[bool, Optional[TickerData], str]:
    """
    Валидация данных тикера

    Args:
        data: Словарь с данными тикера

    Returns:
        (is_valid, ticker_data, error_message)
    """
    try:
        ticker_data = TickerData(**data)

        # Дополнительная проверка
        is_valid, message = ticker_data.validate_for_analysis()
        if not is_valid:
            return False, None, message

        return True, ticker_data, "Данные тикера валидны"
    except Exception as e:
        logger.error(f"❌ Ошибка валидации данных тикера: {e}")
        return False, None, f"Ошибка валидации: {str(e)}"