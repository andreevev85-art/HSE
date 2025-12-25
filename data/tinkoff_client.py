"""
Клиент для работы с Tinkoff Invest API через официальную библиотеку t-tech-investments.
Получает реальные данные для анализа в проекте Паникёр 3000.
"""
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pytz

# ============================================================================
# 1. ИМПОРТ БИБЛИОТЕКИ T-TECH-INVESTMENTS
# ============================================================================
try:
    from t_tech.invest import Client, CandleInterval
    T_TECH_AVAILABLE = True
    logger = logging.getLogger(__name__)
except ImportError as e:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать t-tech-investments")
    print(f"   Установите: pip install t-tech-investments")
    print(f"   Ошибка: {e}")
    T_TECH_AVAILABLE = False
    sys.exit(1)

# Импорт для работы с .env
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    print("❌ python-dotenv не установлен: pip install python-dotenv")
    sys.exit(1)


# ============================================================================
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================
def _setup_logging() -> logging.Logger:
    """Настройка логирования для модуля."""
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def _load_token() -> str:
    """Загрузка токена API из .env файла."""
    if not DOTENV_AVAILABLE:
        raise ImportError("python-dotenv не установлен")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    env_path = os.path.join(project_root, '.env')

    if not os.path.exists(env_path):
        raise FileNotFoundError(f"Файл .env не найден: {env_path}")

    load_dotenv(env_path)

    token = (os.getenv('TINKOFF_TOKEN') or
             os.getenv('TINKOFF_API_TOKEN') or
             os.getenv('TINKOFF_INVEST_TOKEN') or
             os.getenv('T_TOKEN'))

    if not token:
        raise ValueError(
            "Токен API не найден в .env файле. "
            "Добавьте: TINKOFF_API_TOKEN=ваш_токен"
        )

    if not token.startswith('t.'):
        raise ValueError(
            f"Токен имеет неверный формат. Должен начинаться с 't.', получен: {token[:10]}..."
        )

    return token


def _convert_candle_interval(interval: str) -> CandleInterval:
    """Конвертация строкового интервала в CandleInterval."""
    interval_map = {
        'min1': CandleInterval.CANDLE_INTERVAL_1_MIN,
        'min5': CandleInterval.CANDLE_INTERVAL_5_MIN,
        'min15': CandleInterval.CANDLE_INTERVAL_15_MIN,
        'hour': CandleInterval.CANDLE_INTERVAL_HOUR,
        'day': CandleInterval.CANDLE_INTERVAL_DAY,
        'week': CandleInterval.CANDLE_INTERVAL_WEEK,
        'month': CandleInterval.CANDLE_INTERVAL_MONTH,
    }

    if interval not in interval_map:
        raise ValueError(
            f"Неверный интервал: {interval}. "
            f"Допустимые: {list(interval_map.keys())}"
        )

    return interval_map[interval]


# ============================================================================
# 3. ОСНОВНОЙ КЛАСС TINKOFFCLIENT
# ============================================================================
class TinkoffClient:
    """Клиент для работы с API Тинькофф Инвестиций."""

    def __init__(self, token: Optional[str] = None):
        """
        Инициализация клиента.

        Args:
            token: Токен API. Если не указан, загружается из .env
        """
        if not T_TECH_AVAILABLE:
            raise ImportError("Библиотека t-tech-investments не установлена")

        self.logger = _setup_logging()
        self.token = token or _load_token()

        self._figi_cache: Dict[str, str] = {}
        self._price_cache: Dict[str, float] = {}
        self._price_cache_time: Dict[str, datetime] = {}

        self.logger.info("✅ TinkoffClient инициализирован")

    # ========================================================================
    # 3.1. ОСНОВНЫЕ МЕТОДЫ ДЛЯ ПОЛУЧЕНИЯ ДАННЫХ
    # ========================================================================
    def get_last_price(self, ticker: str) -> Optional[float]:
        """
        Получить последнюю цену тикера.

        Args:
            ticker: Тикер акции (SBER, GAZP и т.д.)

        Returns:
            Последняя цена или None при ошибке
        """
        try:
            with Client(token=self.token) as client:
                figi = self._get_figi_by_ticker(ticker, client)
                if not figi:
                    self.logger.error(f"FIGI для {ticker} не найден")
                    return None

                response = client.market_data.get_last_prices(figi=[figi])

                if response.last_prices:
                    price = response.last_prices[0].price
                    price_float = float(str(price.units)) + float(str(price.nano)) / 1e9

                    self._price_cache[ticker] = price_float
                    self._price_cache_time[ticker] = datetime.now()

                    self.logger.info(f"✅ Цена {ticker}: {price_float:.2f}₽")
                    return price_float

                self.logger.warning(f"Цена для {ticker} не получена")
                return None

        except Exception as e:
            self.logger.error(f"❌ Ошибка получения цены {ticker}: {e}")
            return None

    def get_candles(
        self,
        ticker: str,
        interval: str = 'hour',
        count: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получить исторические свечи.

        Args:
            ticker: Тикер акции
            interval: Интервал ('min1', 'min5', 'min15', 'hour', 'day')
            count: Количество свечей

        Returns:
            Список свечей в формате словаря
        """
        try:
            with Client(token=self.token) as client:
                figi = self._get_figi_by_ticker(ticker, client)
                if not figi:
                    self.logger.error(f"FIGI для {ticker} не найден")
                    return []

                candle_interval = _convert_candle_interval(interval)

                moscow_tz = pytz.timezone('Europe/Moscow')
                to_time = datetime.now(moscow_tz)
                from_time = self._calculate_from_time(to_time, interval, count)

                from_time_utc = from_time.astimezone(pytz.UTC)
                to_time_utc = to_time.astimezone(pytz.UTC)

                response = client.get_all_candles(
                    figi=figi,
                    from_=from_time_utc,
                    to=to_time_utc,
                    interval=candle_interval
                )

                candles = []
                for candle in response:
                    candle_dict = {
                        'time': candle.time.astimezone(moscow_tz),
                        'open': self._quotation_to_float(candle.open),
                        'high': self._quotation_to_float(candle.high),
                        'low': self._quotation_to_float(candle.low),
                        'close': self._quotation_to_float(candle.close),
                        'volume': candle.volume,
                        'is_complete': candle.is_complete
                    }
                    candles.append(candle_dict)

                self.logger.info(f"✅ Получено {len(candles)} свечей для {ticker}")
                return candles

        except Exception as e:
            self.logger.error(f"❌ Ошибка получения свечей {ticker}: {e}")
            return []

    def get_orderbook(self, ticker: str, depth: int = 10) -> Dict[str, Any]:
        """
        Получить стакан заявок.

        Args:
            ticker: Тикер акции
            depth: Глубина стакана

        Returns:
            Информация о стакане
        """
        try:
            with Client(token=self.token) as client:
                figi = self._get_figi_by_ticker(ticker, client)
                if not figi:
                    return self._default_orderbook(ticker)

                response = client.market_data.get_order_book(figi=figi, depth=depth)

                if response.bids and response.asks:
                    best_bid = self._quotation_to_float(response.bids[0].price)
                    best_ask = self._quotation_to_float(response.asks[0].price)

                    spread = best_ask - best_bid
                    spread_percent = (spread / best_bid * 100) if best_bid > 0 else 0.0

                    bid_volume = sum(order.quantity for order in response.bids)
                    ask_volume = sum(order.quantity for order in response.asks)

                    result = {
                        'ticker': ticker,
                        'spread_percentage': spread_percent,
                        'best_bid': best_bid,
                        'best_ask': best_ask,
                        'bid_volume': bid_volume,
                        'ask_volume': ask_volume,
                        'timestamp': datetime.now().isoformat()
                    }

                    self.logger.info(f"✅ Стакан {ticker}: спред {spread_percent:.2f}%")
                    return result

                return self._default_orderbook(ticker)

        except Exception as e:
            self.logger.error(f"❌ Ошибка получения стакана {ticker}: {e}")
            return self._default_orderbook(ticker)

    def get_ticker_data(self, ticker: str) -> Dict[str, Any]:
        """
        Получить все данные по тикеру для анализа.

        Args:
            ticker: Тикер акции

        Returns:
            Словарь со всеми данными для анализа
        """
        self.logger.info(f"🔍 Получение данных для {ticker}...")

        try:
            candles = self.get_candles(ticker, interval='day', count=60)

            if not candles or len(candles) < 30:
                self.logger.error(f"Недостаточно данных для {ticker}: {len(candles)} свечей")
                return {}

            closes = [candle['close'] for candle in candles]
            volumes = [candle['volume'] for candle in candles]
            highs = [candle['high'] for candle in candles]
            lows = [candle['low'] for candle in candles]

            try:
                from core.indicators import calculate_rsi, calculate_atr, calculate_sma

                rsi_7 = calculate_rsi(closes, period=7)
                rsi_14 = calculate_rsi(closes, period=14)
                rsi_21 = calculate_rsi(closes, period=21)
                atr_values = calculate_atr(highs, lows, closes, period=14)
                sma_20 = calculate_sma(closes, period=20)

                current_rsi_7 = rsi_7[-1] if rsi_7 else 50.0
                current_rsi_14 = rsi_14[-1] if rsi_14 else 50.0
                current_rsi_21 = rsi_21[-1] if rsi_21 else 50.0
                current_atr = atr_values[-1] if atr_values else 2.0
                current_sma_20 = sma_20[-1] if sma_20 else closes[-1]
                avg_atr = sum(atr_values[-20:])/20 if atr_values and len(atr_values) >= 20 else current_atr

            except ImportError:
                self.logger.warning("Модуль индикаторов недоступен, используем базовые значения")
                current_rsi_7 = current_rsi_14 = current_rsi_21 = 50.0
                current_atr = 2.0
                current_sma_20 = closes[-1] if closes else 0
                avg_atr = current_atr

            current_volume = volumes[-1] if volumes else 0
            avg_volume = sum(volumes[-20:])/20 if len(volumes) >= 20 else current_volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            last_price = self.get_last_price(ticker)
            if last_price is None:
                last_price = closes[-1] if closes else 0

            orderbook = self.get_orderbook(ticker)

            result = {
                'ticker': ticker,
                'historical_prices': closes,
                'historical_volumes': volumes,
                'historical_highs': highs,
                'historical_lows': lows,
                'price': last_price,
                'current_price': last_price,
                'rsi_7': current_rsi_7,
                'rsi_14': current_rsi_14,
                'rsi_21': current_rsi_21,
                'volume_ratio': volume_ratio,
                'current_volume': current_volume,
                'average_volume': avg_volume,
                'atr': current_atr,
                'sma_20': current_sma_20,
                'spread_percent': orderbook.get('spread_percentage', 0.05),
                'current_atr': current_atr,
                'average_atr': avg_atr,
                'timestamp': datetime.now(pytz.timezone('Europe/Moscow')).isoformat(),
                'candles_count': len(candles)
            }

            self.logger.info(f"✅ Данные для {ticker} получены:")
            self.logger.info(f"   Цена: {last_price:.2f}₽ | RSI14: {current_rsi_14:.1f} | Объём: {volume_ratio:.1f}×")

            return result

        except Exception as e:
            self.logger.error(f"❌ Ошибка получения данных {ticker}: {e}")
            import traceback
            traceback.print_exc()
            return {}

    # ========================================================================
    # 3.2. ВСПОМОГАТЕЛЬНЫЕ ПРИВАТНЫЕ МЕТОДЫ
    # ========================================================================
    def _get_figi_by_ticker(self, ticker: str, client: Client) -> Optional[str]:
        """Найти FIGI по тикеру."""
        if ticker in self._figi_cache:
            return self._figi_cache[ticker]

        try:
            shares = client.instruments.shares()
            for share in shares.instruments:
                if share.ticker == ticker and share.api_trade_available_flag:
                    self._figi_cache[ticker] = share.figi
                    return share.figi

            bonds = client.instruments.bonds()
            for bond in bonds.instruments:
                if bond.ticker == ticker and bond.api_trade_available_flag:
                    self._figi_cache[ticker] = bond.figi
                    return bond.figi

            etfs = client.instruments.etfs()
            for etf in etfs.instruments:
                if etf.ticker == ticker and etf.api_trade_available_flag:
                    self._figi_cache[ticker] = etf.figi
                    return etf.figi

            self.logger.warning(f"Инструмент {ticker} не найден или недоступен для торговли")
            return None

        except Exception as e:
            self.logger.error(f"Ошибка поиска FIGI для {ticker}: {e}")
            return None

    def _calculate_from_time(
        self,
        to_time: datetime,
        interval: str,
        count: int
    ) -> datetime:
        """Рассчитать время начала запроса."""
        interval_deltas = {
            'min1': timedelta(minutes=count),
            'min5': timedelta(minutes=count * 5),
            'min15': timedelta(minutes=count * 15),
            'hour': timedelta(hours=count),
            'day': timedelta(days=count),
            'week': timedelta(weeks=count),
            'month': timedelta(days=count * 30)
        }

        delta = interval_deltas.get(interval, timedelta(days=count))
        return to_time - delta

    def _quotation_to_float(self, quotation) -> float:
        """Конвертация Quotation в float."""
        try:
            return float(str(quotation.units)) + float(str(quotation.nano)) / 1e9
        except:
            return 0.0

    def _default_orderbook(self, ticker: str) -> Dict[str, Any]:
        """Возвращает стакан по умолчанию при ошибке."""
        return {
            'ticker': ticker,
            'spread_percentage': 0.05,
            'best_bid': 0.0,
            'best_ask': 0.0,
            'bid_volume': 0,
            'ask_volume': 0,
            'timestamp': datetime.now().isoformat()
        }