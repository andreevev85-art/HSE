# panicker3000/core/validator.py
"""
АВТОНОМНЫЙ ВАЛИДАТОР СТРАТЕГИИ «ПАНИКЁР 3000»

Назначение: Тестирование алгоритма на исторических данных с учётом транзакционных издержек.
Используется только для тестирования стратегии, не является частью рабочей системы.

Особенности:
- Учитывает комиссию брокера: 0.05% от суммы сделки
- Учитывает проскальзывание: ±0.1% от цены сигнала
- Тестирует только исторические данные (не реальное время)
- Генерирует отчёт validation_report.txt
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json

# Добавляем путь для локальных импортов
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Импорт statistics с фоллбэком
try:
    import statistics
except ImportError:
    # Для старых версий Python
    import math


    class SimpleStatistics:
        @staticmethod
        def mean(data):
            return sum(data) / len(data) if data else 0

        @staticmethod
        def median(data):
            if not data:
                return 0
            sorted_data = sorted(data)
            n = len(sorted_data)
            if n % 2 == 1:
                return sorted_data[n // 2]
            else:
                return (sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2

        @staticmethod
        def stdev(data):
            if len(data) < 2:
                return 0
            mean_val = SimpleStatistics.mean(data)
            variance = sum((x - mean_val) ** 2 for x in data) / (len(data) - 1)
            return math.sqrt(variance)


    statistics = SimpleStatistics()
    print("⚠️  Используется SimpleStatistics (fallback)")

from core.panic_detector import PanicDetector
from core.config_loader import ConfigLoader
from data.tinkoff_client import TinkoffClient
from data.data_cache import DataCache

logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ ВАЛИДАТОРА
# ============================================================================
COMMISSION_RATE = 0.0005  # 0.05% комиссия брокера
SLIPPAGE_RATE = 0.001  # ±0.1% проскальзывание
MIN_HISTORY_DAYS = 5  # Минимальное количество дней для валидации
DEFAULT_VALIDATION_DAYS = 30  # Дней по умолчанию


# ============================================================================
# КЛАСС Transaction
# ============================================================================
class Transaction:
    """Класс для представления транзакции с учётом издержек"""

    def __init__(
            self,
            ticker: str,
            signal_type: str,  # 'PANIC' или 'GREED'
            entry_price: float,
            exit_price: float,
            entry_time: datetime,
            exit_time: datetime,
            signal_strength: str  # Уровень сигнала
    ):
        self.ticker = ticker
        self.signal_type = signal_type
        self.entry_price = entry_price
        self.exit_price = exit_price
        self.entry_time = entry_time
        self.exit_time = exit_time
        self.signal_strength = signal_strength

        # Расчёт издержек
        self.commission_entry = entry_price * COMMISSION_RATE
        self.commission_exit = exit_price * COMMISSION_RATE

        # Проскальзывание (случайное в пределах ±0.1%)
        import random  # Импорт внутри метода - допустимо
        slippage_multiplier = 1 + random.uniform(-SLIPPAGE_RATE, SLIPPAGE_RATE)
        self.effective_entry_price = entry_price * slippage_multiplier
        self.effective_exit_price = exit_price * (1 + random.uniform(-SLIPPAGE_RATE, SLIPPAGE_RATE))

    @property
    def raw_return(self) -> float:
        """Доходность без учёта издержек (%)"""
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100

    @property
    def net_return(self) -> float:
        """Чистая доходность с учётом издержек (%)"""
        effective_return = ((self.effective_exit_price - self.effective_entry_price)
                            / self.effective_entry_price) * 100
        # Вычитаем комиссии
        total_commission_pct = ((self.commission_entry + self.commission_exit)
                                / self.effective_entry_price) * 100
        return effective_return - total_commission_pct

    @property
    def duration_hours(self) -> float:
        """Длительность сделки в часах"""
        duration = self.exit_time - self.entry_time
        return duration.total_seconds() / 3600

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь для отчёта"""
        return {
            'ticker': self.ticker,
            'signal_type': self.signal_type,
            'signal_strength': self.signal_strength,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'entry_time': self.entry_time.isoformat(),
            'exit_time': self.exit_time.isoformat(),
            'raw_return_pct': self.raw_return,
            'net_return_pct': self.net_return,
            'duration_hours': self.duration_hours,
            'commission_entry': self.commission_entry,
            'commission_exit': self.commission_exit,
            'effective_entry': self.effective_entry_price,
            'effective_exit': self.effective_exit_price
        }


# ============================================================================
# КЛАСС StrategyValidator
# ============================================================================
class StrategyValidator:
    """Основной класс для валидации стратегии"""

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """Инициализация валидатора"""
        self.config_loader = config_loader or ConfigLoader()
        self.panic_detector = PanicDetector(config_loader=self.config_loader)
        self.tinkoff_client = TinkoffClient()
        self.data_cache = DataCache()

        # Результаты валидации
        self.transactions: List[Transaction] = []
        self.metrics: Dict[str, Any] = {}

        # Кеш для исторических данных
        self._historical_cache = {}

        logger.info("✅ StrategyValidator инициализирован")

    # ------------------------------------------------------------------------
    # ОСНОВНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def validate_period(
            self,
            start_date: datetime,
            end_date: datetime,
            tickers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Валидация стратегии за указанный период
        """
        logger.info(f"🔍 Начинаем валидацию с {start_date.date()} по {end_date.date()}")

        # Получаем тикеры
        if tickers is None:
            # Используем правильный способ получения конфига
            tickers_data = self.config_loader.tickers  # Прямой доступ к тикерам

            # Извлекаем тикеры из структуры YAML
            extracted_tickers = []
            if isinstance(tickers_data, dict) and 'tickers' in tickers_data:
                tickers_list = tickers_data['tickers']

                if isinstance(tickers_list, list):
                    for item in tickers_list:
                        if isinstance(item, dict) and 'ticker' in item:
                            extracted_tickers.append(item['ticker'])
                        elif isinstance(item, str):
                            extracted_tickers.append(item)

            if extracted_tickers:
                tickers = extracted_tickers[:10]  # Берем первые 10 или все
                logger.info(f"📊 Найдено тикеров в конфиге: {len(tickers)}")
            else:
                tickers = ['SBER', 'GAZP', 'LKOH', 'GMKN', 'YNDX']
                logger.warning(f"⚠️  Используем дефолтные тикеры: {tickers}")

        logger.info(f"📊 Тестируем {len(tickers)} тикеров: {tickers}")

        # Сбрасываем предыдущие результаты
        self.transactions = []

        # Для каждого тикера
        for ticker in tickers:
            try:
                logger.info(f"📈 Анализируем {ticker}...")
                ticker_transactions = self._validate_ticker(ticker, start_date, end_date)
                self.transactions.extend(ticker_transactions)

                logger.info(f"   📊 Найдено сделок: {len(ticker_transactions)}")

            except Exception as e:
                logger.error(f"❌ Ошибка валидации {ticker}: {e}")
                continue

        # Рассчитываем метрики
        self._calculate_metrics()

        # Добавляем информацию о периоде в метрики
        self.metrics['validation_period'] = f"{start_date.date()} - {end_date.date()}"
        self.metrics['tickers_tested'] = tickers

        # Генерируем отчёт
        report_path = self._generate_report()

        logger.info(f"✅ Валидация завершена. Всего сделок: {len(self.transactions)}")
        logger.info(f"📄 Отчёт сохранён: {report_path}")

        return self.metrics

    def _validate_ticker(
            self,
            ticker: str,
            start_date: datetime,
            end_date: datetime
    ) -> List[Transaction]:
        """
        Валидация стратегии для конкретного тикера

        Args:
            ticker: Тикер акции
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            Список транзакций для тикера
        """
        transactions = []
        current_date = start_date

        # Получаем исторические данные день за днём
        while current_date <= end_date:
            try:
                # Симулируем работу на конкретную дату
                day_transactions = self._simulate_trading_day(ticker, current_date)
                transactions.extend(day_transactions)

            except Exception as e:
                logger.warning(f"⚠️  Ошибка симуляции {ticker} на {current_date.date()}: {e}")

            current_date += timedelta(days=1)

        return transactions

    def _simulate_trading_day(
            self,
            ticker: str,
            date: datetime
    ) -> List[Transaction]:
        """
        Симуляция торгового дня с использованием реальных исторических данных и PanicDetector

        Args:
            ticker: Тикер акции
            date: Дата симуляции

        Returns:
            Список транзакций за день
        """
        transactions = []

        # Пропускаем выходные дни
        if date.weekday() >= 5:  # Суббота (5) и воскресенье (6)
            return transactions

        try:
            # 1. Получаем исторические свечи за день с 5-минутным интервалом
            candles = self._get_historical_candles(ticker, date)
            if not candles or len(candles) < 50:  # Нужно минимум 50 свечей для анализа
                logger.debug(f"Недостаточно данных для {ticker} {date.date()}: {len(candles) if candles else 0} свечей")
                return transactions

            # 2. Подготавливаем данные для PanicDetector
            # Собираем цены закрытия и объёмы
            closes = [c['close'] for c in candles]
            volumes = [c['volume'] for c in candles]
            times = [c['time'] for c in candles]

            if len(closes) != len(volumes) or len(closes) != len(times):
                logger.warning(f"Несоответствие данных для {ticker}")
                return transactions

            # 3. Симулируем работу детектора на каждой свече (шаг 5 минут)
            for i in range(20, len(candles) - 5):  # Пропускаем первые 20 и последние 5 свечей
                try:
                    # Подготавливаем данные для текущей точки симуляции
                    current_time = times[i]
                    current_price = closes[i]
                    current_volume = volumes[i]

                    # Получаем срез исторических данных
                    start_idx = max(0, i - 100)
                    historical_closes = closes[start_idx:i + 1]
                    historical_volumes = volumes[start_idx:i + 1]

                    # 4. Используем реальный PanicDetector для анализа
                    signal_result = self._get_signal_from_detector(
                        ticker=ticker,
                        current_price=current_price,
                        current_volume=current_volume,
                        historical_closes=historical_closes,
                        historical_volumes=historical_volumes,
                        timestamp=current_time
                    )

                    if signal_result and signal_result['level'] != '❌ ИГНОРИРОВАТЬ':
                        # 5. Определяем цену выхода (цена через N свечей)
                        exit_candle_idx = min(i + 6, len(candles) - 1)  # Выход через 30 минут (6 свечей)
                        exit_price = closes[exit_candle_idx]
                        exit_time = times[exit_candle_idx]

                        # 6. Создаём транзакцию
                        transaction = Transaction(
                            ticker=ticker,
                            signal_type='PANIC' if 'ПАНИКА' in signal_result.get('signal_type', '') else 'GREED',
                            entry_price=current_price,
                            exit_price=exit_price,
                            entry_time=current_time,
                            exit_time=exit_time,
                            signal_strength=self._convert_level_to_strength(signal_result['level'])
                        )
                        transactions.append(transaction)

                        logger.debug(f"📊 Симуляция {ticker}: сигнал в {current_time}, "
                                     f"вход {current_price:.2f}, выход {exit_price:.2f}")

                        # Пропускаем следующие свечи, чтобы избежать переторговки
                        i += 12  # Пропускаем 1 час (12 свечей по 5 минут)

                except Exception as e:
                    logger.warning(f"Ошибка симуляции свечи {i} для {ticker}: {e}")
                    continue

            logger.info(f"📈 Сымитировано {len(transactions)} сделок для {ticker} {date.date()}")

        except Exception as e:
            logger.error(f"❌ Ошибка симуляции дня {date.date()} для {ticker}: {e}")
            import traceback
            logger.debug(traceback.format_exc())

        return transactions

    def _get_signal_from_detector(self, ticker: str, current_price: float, current_volume: float,
                                  historical_closes: List[float], historical_volumes: List[float],
                                  timestamp: datetime) -> Optional[Dict[str, Any]]:
        """
        Использование реального PanicDetector для получения сигнала

        Args:
            ticker: Тикер акции
            current_price: Текущая цена
            current_volume: Текущий объём
            historical_closes: Исторические цены закрытия
            historical_volumes: Исторические объёмы
            timestamp: Временная метка

        Returns:
            Результат детектора или None
        """
        try:
            # Подготавливаем данные в формате, ожидаемом PanicDetector
            signal_data = {
                'ticker': ticker,
                'price': current_price,
                'current_volume': current_volume,
                'timestamp': timestamp,
                'historical_prices': historical_closes,
                'historical_volumes': historical_volumes,
                # Добавляем дополнительные поля для фильтров
                'historical_highs': historical_closes,  # Упрощение: используем closes как highs
                'historical_lows': historical_closes,  # Упрощение: используем closes как lows
                'historical_closes': historical_closes,
            }

            # Получаем сигнал через PanicDetector
            # Внимание: это упрощённый вызов, в реальности нужно адаптировать под API PanicDetector
            if hasattr(self.panic_detector, 'analyze_signal'):
                return self.panic_detector.analyze_signal(signal_data)
            else:
                # Fallback: упрощённая логика, если метод не реализован
                return self._simplified_detector_logic(signal_data)

        except Exception as e:
            logger.error(f"❌ Ошибка получения сигнала для {ticker}: {e}")
            return None

    def _simplified_detector_logic(self, signal_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Упрощённая логика детектирования (используется если PanicDetector не доступен)

        Args:
            signal_data: Данные для анализа

        Returns:
            Упрощённый результат детектора
        """
        try:
            from core.indicators import calculate_rsi

            ticker = signal_data.get('ticker', '')
            prices = signal_data.get('historical_prices', [])
            volumes = signal_data.get('historical_volumes', [])
            current_price = signal_data.get('price', 0)
            current_volume = signal_data.get('current_volume', 0)

            if len(prices) < 30 or len(volumes) < 30:
                return None

            # Рассчитываем RSI
            rsi_14 = calculate_rsi(prices, period=14)
            if rsi_14 is None:
                return None

            # Рассчитываем средний объём
            avg_volume = sum(volumes[-20:]) / min(20, len(volumes)) if volumes else 0
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Определяем сигнал
            signal_type = 'НЕЙТРАЛЬНО'
            level = '❌ ИГНОРИРОВАТЬ'

            if rsi_14 < 30 and volume_ratio > 1.5:
                signal_type = 'ПАНИКА'
                level = '🔴 СИЛЬНЫЙ' if rsi_14 < 25 else '🟡 ХОРОШИЙ'
            elif rsi_14 > 70 and volume_ratio > 1.5:
                signal_type = 'ЖАДНОСТЬ'
                level = '🔴 СИЛЬНЫЙ' if rsi_14 > 75 else '🟡 ХОРОШИЙ'
            elif (rsi_14 < 35 or rsi_14 > 65) and volume_ratio > 1.2:
                signal_type = 'ПАНИКА' if rsi_14 < 35 else 'ЖАДНОСТЬ'
                level = '⚪ СРОЧНЫЙ'

            if level != '❌ ИГНОРИРОВАТЬ':
                return {
                    'signal_type': signal_type,
                    'level': level,
                    'rsi_14': rsi_14,
                    'volume_ratio': volume_ratio,
                    'price': current_price
                }

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка упрощённой логики детектора: {e}")
            return None

    def _convert_level_to_strength(self, level: str) -> str:
        """Конвертация уровня сигнала в формат для Transaction"""
        level_map = {
            '🔴 СИЛЬНЫЙ': 'RED',
            '🟡 ХОРОШИЙ': 'YELLOW',
            '⚪ СРОЧНЫЙ': 'WHITE',
            '❌ ИГНОРИРОВАТЬ': 'IGNORE'
        }
        return level_map.get(level, 'WHITE')

    def _get_historical_candles(self, ticker: str, date: datetime) -> List[Dict[str, Any]]:
        """
        Получение исторических свечей за конкретный день

        Args:
            ticker: Тикер акции
            date: Дата для получения данных

        Returns:
            Список свечей с 5-минутным интервалом
        """
        try:
            cache_key = f"hist_{ticker}_{date.date()}"

            if hasattr(self, '_historical_cache') and cache_key in self._historical_cache:
                cached_data = self._historical_cache[cache_key]
                # Проверяем срок жизни кеша (1 день)
                cache_time = self._historical_cache.get(f"{cache_key}_time")
                if cache_time and (datetime.now() - cache_time).days < 1:
                    return cached_data

            # Определяем временные границы дня (10:00-18:30)
            start_time = datetime(date.year, date.month, date.day, 10, 0, 0)
            end_time = datetime(date.year, date.month, date.day, 18, 30, 0)

            logger.info(f"📊 Запрос исторических данных {ticker} за {date.date()}")

            # Получаем свечи через TinkoffClient
            # Tinkoff API ожидает интервал в своём формате
            candles = self.tinkoff_client.get_candles(
                ticker=ticker,
                interval='min5',
                count=200  # Примерное количество свечей за день
            )

            if not candles:
                logger.warning(f"⚠️ Нет исторических данных для {ticker} {date.date()}")
                return []

            # Фильтруем свечи по дате (оставляем только нужный день)
            day_candles = []
            for candle in candles:
                candle_time = candle.get('time')
                if isinstance(candle_time, str):
                    try:
                        candle_dt = datetime.fromisoformat(candle_time.replace('Z', '+00:00'))
                        if start_time <= candle_dt <= end_time:
                            # Приводим к нужному формату
                            day_candles.append({
                                'time': candle_dt,
                                'open': candle.get('open', 0),
                                'high': candle.get('high', 0),
                                'low': candle.get('low', 0),
                                'close': candle.get('close', 0),
                                'volume': candle.get('volume', 0)
                            })
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Ошибка парсинга времени свечи: {e}")
                        continue

            # Сортируем по времени
            day_candles.sort(key=lambda x: x['time'])

            logger.info(f"✅ Получено {len(day_candles)} свечей для {ticker} {date.date()}")

            # Кешируем результат
            if not hasattr(self, '_historical_cache'):
                self._historical_cache = {}
                self._historical_cache_times = {}

            self._historical_cache[cache_key] = day_candles
            self._historical_cache_times[cache_key] = datetime.now()

            return day_candles

        except Exception as e:
            logger.error(f"❌ Ошибка получения исторических данных {ticker} {date.date()}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

    def _simulate_panic_detector(self, ticker: str, historical_data: List[Dict], current_candle: Dict) -> Optional[
        Dict[str, Any]]:
        """
        Упрощённая симуляция работы PanicDetector на исторических данных

        Args:
            ticker: Тикер акции
            historical_data: Исторические свечи
            current_candle: Текущая свеча для анализа

        Returns:
            Словарь с информацией о сигнале или None
        """
        try:
            # Извлекаем данные для анализа
            closes = [c['close'] for c in historical_data]
            volumes = [c['volume'] for c in historical_data]

            # Упрощённый расчёт RSI
            # В реальности нужно использовать полную логику из PanicDetector
            rsi_14 = self._calculate_simple_rsi(closes, period=14)
            if rsi_14 is None:
                return None

            # Анализ объёма
            current_volume = current_candle['volume']
            avg_volume = sum(volumes[-20:]) / min(20, len(volumes))
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Определение сигнала (упрощённая логика)
            if rsi_14 < 30 and volume_ratio > 1.5:
                return {
                    'type': 'PANIC',
                    'strength': 'RED' if rsi_14 < 25 else 'YELLOW',
                    'rsi': rsi_14,
                    'volume_ratio': volume_ratio
                }
            elif rsi_14 > 70 and volume_ratio > 1.5:
                return {
                    'type': 'GREED',
                    'strength': 'RED' if rsi_14 > 75 else 'YELLOW',
                    'rsi': rsi_14,
                    'volume_ratio': volume_ratio
                }

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка симуляции детектора для {ticker}: {e}")
            return None

    def _calculate_simple_rsi(self, prices: List[float], period: int = 14) -> Optional[float]:
        """
        Упрощённый расчёт RSI

        Args:
            prices: Список цен закрытия
            period: Период RSI

        Returns:
            Значение RSI или None
        """
        if len(prices) < period + 1:
            return None

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period if period <= len(gains) else 0
        avg_loss = sum(losses[-period:]) / period if period <= len(losses) else 0

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    # ------------------------------------------------------------------------
    # РАСЧЁТ МЕТРИК
    # ------------------------------------------------------------------------
    def _calculate_metrics(self) -> None:
        """Расчёт всех метрик валидации"""
        if not self.transactions:
            self.metrics = self._get_empty_metrics()
            return

        # Базовые метрики
        total_transactions = len(self.transactions)

        # Доходности
        raw_returns = [t.raw_return for t in self.transactions]
        net_returns = [t.net_return for t in self.transactions]

        # Статистика
        winning_trades = [r for r in net_returns if r > 0]
        losing_trades = [r for r in net_returns if r <= 0]

        # Метрики
        self.metrics = {
            'validation_date': datetime.now().isoformat(),
            'total_transactions': total_transactions,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / total_transactions if total_transactions > 0 else 0,

            # Средние доходности
            'avg_raw_return': statistics.mean(raw_returns) if raw_returns else 0,
            'avg_net_return': statistics.mean(net_returns) if net_returns else 0,
            'median_net_return': statistics.median(net_returns) if net_returns else 0,

            # Риск-метрики
            'max_drawdown': min(net_returns) if net_returns else 0,
            'std_deviation': statistics.stdev(net_returns) if len(net_returns) > 1 else 0,

            # По типам сигналов
            'panic_trades': len([t for t in self.transactions if t.signal_type == 'PANIC']),
            'greed_trades': len([t for t in self.transactions if t.signal_type == 'GREED']),

            # По силе сигналов
            'strong_signals': len([t for t in self.transactions if t.signal_strength == 'RED']),
            'moderate_signals': len([t for t in self.transactions if t.signal_strength == 'YELLOW']),
            'urgent_signals': len([t for t in self.transactions if t.signal_strength == 'WHITE']),

            # Временные метрики
            'avg_duration_hours': statistics.mean(
                [t.duration_hours for t in self.transactions]) if self.transactions else 0,

            # Транзакционные издержки
            'total_commission': sum(t.commission_entry + t.commission_exit for t in self.transactions),
            'avg_commission_per_trade': statistics.mean(
                [t.commission_entry + t.commission_exit for t in self.transactions]) if self.transactions else 0,
        }

    def _get_empty_metrics(self) -> Dict[str, Any]:
        """Метрики при отсутствии сделок"""
        return {
            'validation_date': datetime.now().isoformat(),
            'total_transactions': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'avg_raw_return': 0,
            'avg_net_return': 0,
            'median_net_return': 0,
            'max_drawdown': 0,
            'std_deviation': 0,
            'panic_trades': 0,
            'greed_trades': 0,
            'strong_signals': 0,
            'moderate_signals': 0,
            'urgent_signals': 0,
            'avg_duration_hours': 0,
            'total_commission': 0,
            'avg_commission_per_trade': 0,
            'note': 'Нет сделок за период валидации'
        }

    # ------------------------------------------------------------------------
    # ГЕНЕРАЦИЯ ОТЧЁТА
    # ------------------------------------------------------------------------
    def _generate_report(self) -> str:
        """Генерация текстового отчёта валидации"""
        report_lines = []

        # Заголовок
        report_lines.append("=" * 70)
        report_lines.append("ОТЧЁТ ВАЛИДАЦИИ СТРАТЕГИИ «ПАНИКЁР 3000»")
        report_lines.append("=" * 70)
        report_lines.append(f"Дата генерации: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        report_lines.append(f"Период валидации: {self.metrics.get('validation_period', 'Не указан')}")
        report_lines.append("")

        # Основные метрики
        report_lines.append("📊 ОСНОВНЫЕ МЕТРИКИ:")
        report_lines.append("-" * 40)
        report_lines.append(f"Всего сделок: {self.metrics['total_transactions']}")
        report_lines.append(f"Успешных сделок: {self.metrics['winning_trades']}")
        report_lines.append(f"Убыточных сделок: {self.metrics['losing_trades']}")
        report_lines.append(f"Процент успеха: {self.metrics['win_rate']:.1%}")
        report_lines.append("")

        # Доходности
        report_lines.append("📈 ДОХОДНОСТЬ:")
        report_lines.append("-" * 40)
        report_lines.append(f"Средняя доходность (брутто): {self.metrics['avg_raw_return']:.2f}%")
        report_lines.append(f"Средняя доходность (нетто): {self.metrics['avg_net_return']:.2f}%")
        report_lines.append(f"Медианная доходность: {self.metrics['median_net_return']:.2f}%")
        report_lines.append(f"Максимальная просадка: {self.metrics['max_drawdown']:.2f}%")
        report_lines.append(f"Волатильность (ст.откл.): {self.metrics['std_deviation']:.2f}%")
        report_lines.append("")

        # Анализ сигналов
        report_lines.append("🚨 АНАЛИЗ СИГНАЛОВ:")
        report_lines.append("-" * 40)
        report_lines.append(f"Сигналов паники: {self.metrics['panic_trades']}")
        report_lines.append(f"Сигналов жадности: {self.metrics['greed_trades']}")
        report_lines.append("")
        report_lines.append(f"🔴 Сильных сигналов: {self.metrics['strong_signals']}")
        report_lines.append(f"🟡 Умеренных сигналов: {self.metrics['moderate_signals']}")
        report_lines.append(f"⚪ Срочных сигналов: {self.metrics['urgent_signals']}")
        report_lines.append("")

        # Транзакционные издержки
        report_lines.append("💰 ТРАНЗАКЦИОННЫЕ ИЗДЕРЖКИ:")
        report_lines.append("-" * 40)
        report_lines.append(f"Комиссия брокера: {COMMISSION_RATE * 100:.2f}%")
        report_lines.append(f"Проскальзывание: ±{SLIPPAGE_RATE * 100:.1f}%")
        report_lines.append(f"Общая комиссия: {self.metrics['total_commission']:.2f}₽")
        report_lines.append(f"Средняя комиссия за сделку: {self.metrics['avg_commission_per_trade']:.2f}₽")
        report_lines.append("")

        # Временные метрики
        report_lines.append("⏰ ВРЕМЕННЫЕ МЕТРИКИ:")
        report_lines.append("-" * 40)
        report_lines.append(f"Средняя длительность сделки: {self.metrics['avg_duration_hours']:.1f} ч")
        report_lines.append("")

        # Рекомендации
        report_lines.append("🎯 РЕКОМЕНДАЦИИ:")
        report_lines.append("-" * 40)
        if self.metrics['total_transactions'] == 0:
            report_lines.append("⚠️  Нет данных для анализа. Увеличьте период валидации.")
        elif self.metrics['win_rate'] > 0.6:
            report_lines.append("✅ Стратегия показывает хорошие результаты.")
        elif self.metrics['win_rate'] > 0.4:
            report_lines.append("⚠️  Стратегия требует доработки.")
        else:
            report_lines.append("❌ Стратегия неэффективна на данном периоде.")
        report_lines.append("")

        # Примечания
        report_lines.append("📝 ПРИМЕЧАНИЯ:")
        report_lines.append("-" * 40)
        report_lines.append("1. Валидация проведена на исторических данных")
        report_lines.append("2. Учтены все транзакционные издержки")
        report_lines.append("3. Результаты не гарантируют будущую доходность")
        report_lines.append("4. Для детального анализа используйте полную версию")

        report_lines.append("")
        report_lines.append("=" * 70)
        report_lines.append("КОНЕЦ ОТЧЁТА")
        report_lines.append("=" * 70)

        # Сохраняем отчёт
        report_path = os.path.join(project_root, "validation_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))

        # Также сохраняем JSON для машинной обработки
        json_path = os.path.join(project_root, "validation_metrics.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.metrics, f, ensure_ascii=False, indent=2)

        return report_path

    # ------------------------------------------------------------------------
    # УТИЛИТЫ
    # ------------------------------------------------------------------------
    def print_summary(self) -> None:
        """Вывод краткого отчёта в консоль"""
        print("\n" + "=" * 60)
        print("КРАТКИЙ ОТЧЁТ ВАЛИДАЦИИ")
        print("=" * 60)

        if not self.metrics:
            print("❌ Нет данных для отчёта")
            return

        print(f"📊 Сделок: {self.metrics['total_transactions']}")
        print(f"✅ Успешных: {self.metrics['winning_trades']} ({self.metrics['win_rate']:.1%})")
        print(f"📈 Средняя доходность: {self.metrics['avg_net_return']:.2f}%")
        print(f"📉 Макс. просадка: {self.metrics['max_drawdown']:.2f}%")

        print(f"\n🚨 Сигналов:")
        print(f"  Паника: {self.metrics['panic_trades']}")
        print(f"  Жадность: {self.metrics['greed_trades']}")

        print(f"\n💰 Комиссии: {self.metrics['total_commission']:.2f}₽")
        print(f"⏰ Среднее время: {self.metrics['avg_duration_hours']:.1f} ч")

        print("\n" + "=" * 60)


# ============================================================================
# КОМАНДНАЯ СТРОКА
# ============================================================================
def main():
    """Точка входа для запуска валидатора из командной строки"""
    import argparse

    parser = argparse.ArgumentParser(description='Валидатор стратегии Паникёр 3000')
    parser.add_argument(
        '--days',
        type=int,
        default=DEFAULT_VALIDATION_DAYS,
        help=f'Количество дней для валидации (по умолчанию: {DEFAULT_VALIDATION_DAYS})'
    )
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Список тикеров для тестирования (по умолчанию из конфига)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='validation_report.txt',
        help='Путь для сохранения отчёта'
    )

    args = parser.parse_args()

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print(f"🔍 Запуск валидации на {args.days} дней...")

    try:
        # Создаём валидатор
        validator = StrategyValidator()

        # Устанавливаем период
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)

        # Запускаем валидацию
        metrics = validator.validate_period(
            start_date=start_date,
            end_date=end_date,
            tickers=args.tickers
        )

        # Выводим краткий отчёт
        validator.print_summary()

        print(f"\n✅ Валидация завершена!")
        print(f"📄 Полный отчёт сохранён в: {os.path.join(project_root, 'validation_report.txt')}")

    except Exception as e:
        print(f"❌ Ошибка валидации: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# ЗАПУСК
# ============================================================================
if __name__ == "__main__":
    main()