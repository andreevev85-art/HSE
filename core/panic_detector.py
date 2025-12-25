# panicker3000/core/panic_detector.py
"""
Ядро системы обнаружения паники/жадности.
Реализует 10-шаговый алгоритм с мультипериодной верификацией RSI,
анализом кластеров объёма и риск-метриками.

Использует Pydantic модели из utils.schemas для валидации данных.
"""

# ============================================================================
# ИМПОРТЫ (ИСПРАВЛЕННЫЕ ПУТИ)
# ============================================================================
import sys
import os
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
import logging

# Исправляем пути импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Теперь импортируем Pydantic модели
try:
    from panicker3000.utils.schemas import (
        PanicSignal,
        SignalType,
        BaseLevel,
        FinalLevel,
        VolumeCluster,
        TickerData,
        RiskMetrics
    )
except ImportError:
    # Альтернативный путь для запуска из корня проекта
    try:
        from utils.schemas import (
            PanicSignal,
            SignalType,
            BaseLevel,
            FinalLevel,
            VolumeCluster,
            TickerData,
            RiskMetrics
        )
    except ImportError as e:
        print(f"❌ Ошибка импорта Pydantic схем: {e}")
        print(f"   Текущий путь: {sys.path}")
        sys.exit(1)

# Импортируем фильтры
try:
    from panicker3000.core.filters.time_filter import TimeFilter
    from panicker3000.core.filters.volume_filter import VolumeFilter
    from panicker3000.core.filters.volatility_filter import VolatilityFilter
    from panicker3000.core.filters.trend_filter import TrendFilter
except ImportError:
    try:
        from core.filters.time_filter import TimeFilter
        from core.filters.volume_filter import VolumeFilter
        from core.filters.volatility_filter import VolatilityFilter
        from core.filters.trend_filter import TrendFilter
    except ImportError as e:
        print(f"❌ Ошибка импорта фильтров: {e}")
        sys.exit(1)

# Импортируем анализаторы
try:
    from panicker3000.core.cluster_analyzer import VolumeClusterAnalyzer
    from panicker3000.core.risk_metrics import RiskCalculator

    CLUSTER_ANALYZER_AVAILABLE = True
except ImportError:
    try:
        from core.cluster_analyzer import VolumeClusterAnalyzer
        from core.risk_metrics import RiskCalculator

        CLUSTER_ANALYZER_AVAILABLE = True
    except ImportError:
        CLUSTER_ANALYZER_AVAILABLE = False
        VolumeClusterAnalyzer = None
        RiskCalculator = None

# Импортируем MarketCalendar
try:
    from panicker3000.data.market_calendar import get_market_calendar
except ImportError:
    try:
        from data.market_calendar import get_market_calendar
    except ImportError as e:
        print(f"❌ Ошибка импорта market_calendar: {e}")
        sys.exit(1)

from panicker3000.utils.schemas import VolumeCluster

# Определяем логгер
logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
DEFAULT_THRESHOLDS = {
    'red': {'rsi_buy': 25, 'rsi_sell': 75, 'volume_min': 2.0},
    'yellow': {'rsi_buy': 30, 'rsi_sell': 70, 'volume_min': 1.5},
    'white': {'rsi_buy': 35, 'rsi_sell': 65, 'volume_min': 1.2}
}


# ============================================================================
# КЛАСС PanicDetector (ОБНОВЛЁН ДЛЯ PYDANTIC)
# ============================================================================
class PanicDetector:
    """Основной класс для обнаружения сигналов паники/жадности"""

    def __init__(self, config_loader):
        """Инициализация детектора"""
        self.config_loader = config_loader
        self.thresholds = self._load_thresholds()

        # Транзакционные издержки (только для валидатора)
        self.commission = 0.0005  # 0.05%
        self.slippage = 0.001  # ±0.1%

        try:
            self.market_calendar = get_market_calendar()
        except Exception as e:
            print(f"⚠️  Ошибка инициализации MarketCalendar: {e}")

            # Создаём заглушку
            class MockCalendar:
                def is_market_open_now(self):
                    return True, "Работает (заглушка)"

            self.market_calendar = MockCalendar()

        # Инициализация фильтров
        self.filters = {
            'volume': VolumeFilter({'min_volume_ratio': self.thresholds['white']['volume_min']}),
            'volatility': VolatilityFilter(),
            'trend': TrendFilter()
        }

        # Инициализация анализаторов
        self.cluster_analyzer = None
        self.risk_calculator = None

        if CLUSTER_ANALYZER_AVAILABLE:
            try:
                self.cluster_analyzer = VolumeClusterAnalyzer(num_clusters=3)
                print("✅ VolumeClusterAnalyzer инициализирован")
            except Exception as e:
                print(f"❌ Ошибка инициализации VolumeClusterAnalyzer: {e}")

            try:
                self.risk_calculator = RiskCalculator(atr_normal=2.0)
                print("✅ RiskCalculator инициализирован")
            except Exception as e:
                print(f"❌ Ошибка инициализации RiskCalculator: {e}")

        print("✅ PanicDetector инициализирован с Pydantic поддержкой")

    # ------------------------------------------------------------------------
    # ОСНОВНЫЕ ПУБЛИЧНЫЕ МЕТОДЫ (ОБНОВЛЕНЫ)
    # ------------------------------------------------------------------------
    def detect_panic(self, ticker_data: Dict, return_dict: bool = False) -> Optional[Union[PanicSignal, Dict]]:
        """
        Основной метод обнаружения паники

        Args:
            ticker_data: Данные по тикеру
            return_dict: Если True, возвращает словарь (обратная совместимость)

        Returns:
            PanicSignal или словарь, или None если сигнала нет
        """
        try:
            signal = self.analyze_ticker(ticker_data)

            if not signal:
                return None

            if return_dict:
                return self.signal_to_dict(signal)
            return signal

        except Exception as e:
            print(f"❌ Ошибка в detect_panic: {e}")
            return None

    def analyze_multiple_tickers(self, tickers_data: List[Dict]) -> List[PanicSignal]:
        """
        Анализ нескольких тикеров

        Args:
            tickers_data: Список словарей с данными тикеров

        Returns:
            Список PanicSignal объектов
        """
        signals = []

        for ticker_data in tickers_data:
            try:
                signal = self.analyze_ticker(ticker_data)
                if signal:
                    signals.append(signal)
            except Exception as e:
                ticker = ticker_data.get('ticker', 'UNKNOWN')
                print(f"❌ Ошибка анализа {ticker}: {e}")

        print(f"📊 Проанализировано {len(tickers_data)} тикеров, найдено {len(signals)} сигналов")
        return signals

    def signal_to_dict(self, signal: PanicSignal) -> Dict:
        """
        Конвертация PanicSignal в словарь для обратной совместимости
        """
        try:
            return signal.dict()
        except Exception as e:
            print(f"❌ Ошибка конвертации сигнала в словарь: {e}")
            # Fallback
            return {
                'ticker': signal.ticker,
                'timestamp': signal.timestamp,
                'signal_type': signal.signal_type.value,
                'rsi_14': signal.rsi_14,
                'volume_ratio': signal.volume_ratio,
                'final_level': signal.final_level.value,
                'interpretation': signal.interpretation,
                'recommendation': signal.recommendation
            }

    # ------------------------------------------------------------------------
    # ВАЛИДАЦИЯ ДАННЫХ
    # ------------------------------------------------------------------------
    def validate_ticker_data(self, ticker_data: Dict) -> Optional[TickerData]:
        """
        Валидация входных данных

        Returns:
            TickerData объект или None при ошибке
        """
        try:
            required_fields = ['ticker', 'rsi_14', 'volume_ratio', 'price']
            for field in required_fields:
                if field not in ticker_data:
                    print(f"⚠️  Отсутствует поле {field} в данных")
                    return None

            return TickerData(
                ticker=ticker_data['ticker'],
                price=ticker_data['price'],
                rsi_7=ticker_data.get('rsi_7'),
                rsi_14=ticker_data['rsi_14'],
                rsi_21=ticker_data.get('rsi_21'),
                volume_ratio=ticker_data['volume_ratio'],
                current_volume=ticker_data.get('current_volume'),
                average_volume=ticker_data.get('average_volume'),
                atr=ticker_data.get('atr'),
                sma_20=ticker_data.get('sma_20'),
                spread_percent=ticker_data.get('spread_percent', 0.1),
                historical_prices=ticker_data.get('historical_prices', []),
                historical_volumes=ticker_data.get('historical_volumes', [])
            )
        except Exception as e:
            print(f"❌ Ошибка валидации данных: {e}")
            return None

    # ------------------------------------------------------------------------
    # ШАГ 1-4: БАЗОВЫЕ ПРОВЕРКИ
    # ------------------------------------------------------------------------
    def check_basic_conditions(self, ticker_data: Dict) -> Tuple[bool, Optional[SignalType], str]:
        """Шаги 1-4: Проверка базовых условий"""
        ticker = ticker_data.get('ticker', 'UNKNOWN')

        # Шаг 1: Проверка времени биржи
        if not self._check_market_time():
            is_open, reason = self.market_calendar.is_market_open_now()
            return False, None, f"Биржа закрыта ({reason})"

        # Шаг 2: Проверка наличия данных
        if not self._validate_data(ticker_data):
            return False, None, f"Недостаточно данных для {ticker}"

        # Шаг 3: Проверка RSI(14)
        rsi_14 = ticker_data.get('rsi_14')
        if rsi_14 is None:
            return False, None, f"Нет данных RSI14 для {ticker}"

        signal_type = self._get_signal_type_from_rsi(rsi_14)
        if signal_type is None:
            return False, None, f"RSI14 в нормальном диапазоне ({rsi_14})"

        # Шаг 4: Проверка объёма
        volume_ratio = ticker_data.get('volume_ratio', 0)
        min_volume = self.thresholds['white']['volume_min']

        if volume_ratio < min_volume:
            return False, None, f"Объём недостаточен: {volume_ratio:.1f}× < {min_volume}×"

        return True, signal_type, f"Базовые условия выполнены: {signal_type.value.upper()}, RSI={rsi_14}, объём={volume_ratio:.1f}×"

    # ------------------------------------------------------------------------
    # ШАГ 5: МУЛЬТИПЕРИОДНАЯ ВЕРИФИКАЦИЯ
    # ------------------------------------------------------------------------
    def get_base_level(self, rsi_7: float, rsi_14: float, rsi_21: float,
                       signal_type: SignalType) -> BaseLevel:
        """Шаг 5: Мультипериодная верификация → Базовый уровень"""

        def is_outside(rsi_value: float) -> bool:
            if signal_type == SignalType.PANIC:
                return rsi_value < self.thresholds['white']['rsi_buy']
            else:
                return rsi_value > self.thresholds['white']['rsi_sell']

        outside_7 = is_outside(rsi_7)
        outside_14 = is_outside(rsi_14)
        outside_21 = is_outside(rsi_21)

        if outside_7 and outside_14 and outside_21:
            return BaseLevel.STRONG
        elif (outside_7 and outside_14) or (outside_14 and outside_21):
            return BaseLevel.GOOD
        elif outside_14:
            return BaseLevel.URGENT
        else:
            return BaseLevel.NONE

    # ------------------------------------------------------------------------
    # ШАГ 6: КОРРЕКЦИЯ ОБЪЁМОМ
    # ------------------------------------------------------------------------
    def adjust_level_by_volume(self, base_level: BaseLevel, volume_ratio: float) -> BaseLevel:
        """Шаг 6: Коррекция базового уровня объёмом"""
        if volume_ratio < 2.0:
            return base_level

        level_order = [BaseLevel.URGENT, BaseLevel.GOOD, BaseLevel.STRONG]

        try:
            current_index = level_order.index(base_level)
            if current_index < len(level_order) - 1:
                return level_order[current_index + 1]
        except ValueError:
            pass

        return base_level

    # ------------------------------------------------------------------------
    # ШАГ 7: КОНТЕКСТНЫЕ ФИЛЬТРЫ
    # ------------------------------------------------------------------------
    def apply_context_filters(self, ticker_data: Dict, base_level: BaseLevel) -> Tuple[
        FinalLevel, List[str], List[str]]:
        """Шаг 7: Применение контекстных фильтров"""
        passed = []
        failed = []
        current_level = base_level

        filter_order = ['volatility', 'trend', 'volume']
        level_order = [BaseLevel.STRONG, BaseLevel.GOOD, BaseLevel.URGENT, BaseLevel.NONE]

        for filter_name in filter_order:
            filter_obj = self.filters.get(filter_name)
            if not filter_obj:
                continue

            result = filter_obj.check(ticker_data)

            passed_filter = False
            filter_message = ""

            if isinstance(result, tuple) and len(result) == 2:
                passed_filter, filter_message = result
            else:
                passed_filter = bool(result)
                filter_message = f"пройден" if passed_filter else f"не пройден"

            if passed_filter:
                passed.append(f"{filter_name}: {filter_message}")
            else:
                failed.append(f"{filter_name}: {filter_message}")

                try:
                    current_index = level_order.index(current_level)
                    if current_index < len(level_order) - 1:
                        current_level = level_order[current_index + 1]
                except ValueError:
                    pass

        final_level = self._convert_to_final_level(current_level)
        return final_level, passed, failed

    # ------------------------------------------------------------------------
    # ШАГ 8-10: ПОЛНЫЙ АНАЛИЗ С КЛАСТЕРАМИ И РИСКОМ
    # ------------------------------------------------------------------------
    def analyze_ticker(self, ticker_data: Dict) -> Optional[PanicSignal]:
        """
        Полный 10-шаговый анализ тикера

        Returns:
            PanicSignal или None если сигнала нет
        """
        ticker = ticker_data.get('ticker', 'UNKNOWN')
        print(f"🔍 Анализ {ticker} (10 шагов)")

        # Шаг 1-4: Базовые условия
        basic_ok, signal_type, basic_msg = self.check_basic_conditions(ticker_data)
        if not basic_ok:
            print(f"{ticker}: {basic_msg}")
            return None

        # Получаем RSI значения
        rsi_7 = ticker_data.get('rsi_7')
        rsi_14 = ticker_data.get('rsi_14')
        rsi_21 = ticker_data.get('rsi_21')

        # Шаг 5: Мультипериодная верификация
        base_level = self.get_base_level(rsi_7, rsi_14, rsi_21, signal_type)
        if base_level == BaseLevel.NONE:
            print(f"{ticker}: Нет мультипериодного подтверждения")
            return None

        # Шаг 6: Коррекция объёмом
        volume_ratio = ticker_data.get('volume_ratio', 1.0)
        base_level = self.adjust_level_by_volume(base_level, volume_ratio)

        # Шаг 7: Контекстные фильтры
        final_level, passed_filters, failed_filters = self.apply_context_filters(ticker_data, base_level)

        # Шаг 8: Финальное решение
        if final_level == FinalLevel.IGNORE:
            print(f"{ticker}: Сигнал отфильтрован")
            return None

        # Шаг 9: Анализ кластеров объёма
        volume_clusters = []
        cluster_summary = ""

        if self.cluster_analyzer is not None:
            volume_clusters, cluster_summary = self._analyze_volume_clusters(ticker_data)

        # Шаг 10: Расчёт риск-метрики
        risk_metric = None
        risk_interpretation = ""

        if self.risk_calculator is not None:
            risk_metric, risk_interpretation = self._calculate_risk_metrics(
                ticker_data, rsi_14, volume_ratio, signal_type
            )

        # СОЗДАЁМ PYDANTIC МОДЕЛЬ PanicSignal
        try:
            signal = PanicSignal(
                ticker=ticker,
                timestamp=datetime.now(),
                signal_type=signal_type,

                rsi_7=rsi_7,
                rsi_14=rsi_14,
                rsi_21=rsi_21,

                volume_ratio=volume_ratio,
                current_volume=ticker_data.get('current_volume'),
                average_volume=ticker_data.get('average_volume'),

                base_level=base_level,
                final_level=final_level,

                passed_filters=passed_filters,
                failed_filters=failed_filters,

                price=ticker_data.get('price'),
                atr=ticker_data.get('atr'),
                sma_20=ticker_data.get('sma_20'),
                spread_percent=ticker_data.get('spread_percent', 0.1),

                volume_clusters=volume_clusters,
                cluster_summary=cluster_summary,

                risk_metric=risk_metric,
                risk_interpretation=risk_interpretation,

                interpretation=self._generate_interpretation(signal_type, final_level, risk_interpretation),
                recommendation=self._generate_recommendation(signal_type, final_level),
                risk_level=self._get_risk_level(final_level, len(failed_filters), risk_metric)
            )

            level_emojis = {
                FinalLevel.RED: "🔴",
                FinalLevel.YELLOW: "🟡",
                FinalLevel.WHITE: "⚪"
            }
            emoji = level_emojis.get(final_level, "")
            print(f"✅ Обнаружен сигнал: {ticker} {emoji} {signal_type.value}")
            return signal

        except Exception as e:
            print(f"❌ Ошибка создания PanicSignal: {e}")
            return None

    # ------------------------------------------------------------------------
    # ШАГ 9: АНАЛИЗ КЛАСТЕРОВ ОБЪЁМА
    # ------------------------------------------------------------------------
    def _analyze_volume_clusters(self, ticker_data: Dict) -> Tuple[List[VolumeCluster], str]:
        """Шаг 9: Анализ кластеров объёма"""
        try:
            historical_prices = ticker_data.get('historical_prices', [])
            historical_volumes = ticker_data.get('historical_volumes', [])

            if not historical_prices or not historical_volumes:
                print(f"⚠️  Нет исторических данных для анализа кластеров")
                return [], "Нет данных для анализа кластеров объёма"

            if len(historical_prices) != len(historical_volumes):
                print(f"❌ Несовпадение размеров: цены={len(historical_prices)}, объёмы={len(historical_volumes)}")
                return [], "Ошибка данных для анализа кластеров"

            print(f"📊 Анализ кластеров объёма: {len(historical_prices)} точек данных")
            clusters = self.cluster_analyzer.analyze(historical_prices, historical_volumes)

            # В методе _analyze_volume_clusters()
            pydantic_clusters = []
            for cluster in clusters:
                try:
                    # Пробуем создать schema VolumeCluster из любого объекта
                    if hasattr(cluster, 'price_level') and hasattr(cluster, 'volume_percentage'):
                        # Это объект из cluster_analyzer
                        schema_cluster = VolumeCluster(
                            price_level=cluster.price_level,
                            volume_percentage=cluster.volume_percentage,
                            significance=getattr(cluster, 'significance', 'medium'),
                            cluster_type=getattr(cluster, 'cluster_type', 'unknown')
                        )
                        pydantic_clusters.append(schema_cluster)
                    elif isinstance(cluster, dict):
                        # Это словарь
                        schema_cluster = VolumeCluster(**cluster)
                        pydantic_clusters.append(schema_cluster)
                    else:
                        print(f"⚠️  Неизвестный формат кластера: {type(cluster)}")
                except Exception as e:
                    print(f"⚠️  Ошибка обработки кластера: {e}")

            if pydantic_clusters:
                summary = self.cluster_analyzer.get_clusters_summary(clusters)
                print(f"✅ Найдено {len(pydantic_clusters)} кластеров объёма")
                return pydantic_clusters, summary
            else:
                print("ℹ️  Кластеры объёма не обнаружены")
                return [], "Кластеры объёма не обнаружены"

        except Exception as e:
            print(f"❌ Ошибка анализа кластеров объёма: {e}")
            return [], f"Ошибка анализа кластеров: {str(e)}"

    # ------------------------------------------------------------------------
    # ШАГ 10: РАСЧЁТ РИСК-МЕТРИК
    # ------------------------------------------------------------------------
    def _calculate_risk_metrics(self, ticker_data: Dict, rsi_14: float,
                                volume_ratio: float, signal_type: SignalType) -> Tuple[Optional[float], str]:
        """Шаг 10: Расчёт риск-метрик"""
        try:
            atr = ticker_data.get('atr', 2.0)
            signal_type_str = 'panic' if signal_type == SignalType.PANIC else 'greed'

            risk_metrics = self.risk_calculator.calculate_risk(
                rsi=rsi_14,
                volume_ratio=volume_ratio,
                atr=atr,
                signal_type=signal_type_str
            )

            print(f"📊 Рассчитана риск-метрика: {risk_metrics.risk_score:.1f}/100")
            return risk_metrics.risk_score, risk_metrics.interpretation

        except Exception as e:
            print(f"❌ Ошибка расчёта риск-метрик: {e}")
            return None, f"Ошибка расчёта риск-метрик: {str(e)}"

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def _load_thresholds(self) -> Dict:
        """Загрузка пороговых значений"""
        try:
            config = self.config_loader.load_panic_thresholds()
            return config.get('panic_thresholds', DEFAULT_THRESHOLDS)
        except Exception as e:
            print(f"Ошибка загрузки порогов: {e}, используем значения по умолчанию")
            return DEFAULT_THRESHOLDS

    def _check_market_time(self) -> bool:
        """Шаг 1: Проверка времени работы биржи"""
        try:
            is_open, reason = self.market_calendar.is_market_open_now()
            if not is_open:
                print(f"⏰ Биржа закрыта: {reason}")
            return is_open
        except Exception as e:
            print(f"⚠️  Ошибка проверки времени биржи: {e}")
            return True  # По умолчанию считаем что открыта

    def _validate_data(self, data: Dict) -> bool:
        """Шаг 2: Проверка наличия данных"""
        required_fields = ['ticker', 'rsi_14', 'volume_ratio', 'price']
        return all(field in data and data[field] is not None for field in required_fields)

    def _get_signal_type_from_rsi(self, rsi_14: float) -> Optional[SignalType]:
        """Определение типа сигнала по RSI14"""
        if rsi_14 <= self.thresholds['white']['rsi_buy']:
            return SignalType.PANIC
        elif rsi_14 >= self.thresholds['white']['rsi_sell']:
            return SignalType.GREED
        return None

    def _convert_to_final_level(self, base_level: BaseLevel) -> FinalLevel:
        """Конвертация BaseLevel в FinalLevel"""
        mapping = {
            BaseLevel.STRONG: FinalLevel.RED,
            BaseLevel.GOOD: FinalLevel.YELLOW,
            BaseLevel.URGENT: FinalLevel.WHITE,
            BaseLevel.NONE: FinalLevel.IGNORE
        }
        return mapping.get(base_level, FinalLevel.IGNORE)

    def _generate_interpretation(self, signal_type: SignalType, final_level: FinalLevel,
                                 risk_interpretation: str = "") -> str:
        """Генерация интерпретации сигнала"""
        if signal_type == SignalType.PANIC:
            base_text = "Рынок перепродан, наблюдаются признаки панических продаж"
        else:
            base_text = "Рынок перекуплен, наблюдаются признаки жадности"

        level_text = {
            FinalLevel.RED: "Сильное отклонение от нормы",
            FinalLevel.YELLOW: "Умеренное отклонение от нормы",
            FinalLevel.WHITE: "Раннее предупреждение"
        }.get(final_level, "Неопределённый уровень")

        interpretation = f"{level_text}. {base_text}"

        if risk_interpretation:
            interpretation += f"\n\n📊 {risk_interpretation}"

        return interpretation

    def _generate_recommendation(self, signal_type: SignalType, final_level: FinalLevel) -> str:
        """Генерация рекомендации"""
        if final_level == FinalLevel.IGNORE:
            return "Игнорировать"

        if signal_type == SignalType.PANIC:
            actions = {
                FinalLevel.RED: "Рассмотреть контртрендовую покупку",
                FinalLevel.YELLOW: "Подготовиться к возможной покупке",
                FinalLevel.WHITE: "Наблюдать за развитием ситуации"
            }
        else:
            actions = {
                FinalLevel.RED: "Рассмотреть фиксацию прибыли или продажу",
                FinalLevel.YELLOW: "Подготовиться к возможной продаже",
                FinalLevel.WHITE: "Наблюдать за развитием ситуации"
            }

        return actions.get(final_level, "Наблюдать")

    def _get_risk_level(self, final_level: FinalLevel, failed_filters_count: int,
                        risk_metric: Optional[float] = None) -> str:
        """Определение уровня риска"""
        if risk_metric is not None:
            if risk_metric >= 80:
                risk_text = "Очень высокий"
            elif risk_metric >= 60:
                risk_text = "Высокий"
            elif risk_metric >= 40:
                risk_text = "Средний"
            elif risk_metric >= 20:
                risk_text = "Низкий"
            else:
                risk_text = "Очень низкий"

            return f"{risk_text} (оценка: {risk_metric:.1f}/100)"

        if final_level == FinalLevel.RED and failed_filters_count == 0:
            return "Высокий (сильный сигнал, все фильтры пройдены)"
        elif final_level == FinalLevel.RED:
            return "Высокий (сильный сигнал, но есть непройденные фильтры)"
        elif final_level == FinalLevel.YELLOW:
            return "Средний (умеренный сигнал)"
        elif final_level == FinalLevel.WHITE:
            return "Низкий (предупредительный сигнал)"
        else:
            return "Неопределённый"

    def calculate_net_return(self, signal_return: float) -> float:
        """Расчёт чистой доходности с учётом издержек"""
        net_return = signal_return - (2 * self.commission) - self.slippage
        return max(net_return, -0.999)  # Не ниже -99.9%
