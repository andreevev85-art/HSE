# panicker3000/grpc/grpc_client.py
"""
gRPC клиент для взаимодействия с сервером Паникёра.
Используется Telegram-ботом вместо прямых вызовов PanicDetector.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import grpc
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import time

# ============================================================================
# PYDANTIC SCHEMAS IMPORT
# ============================================================================
try:
    # Пробуем импорт с префиксом panicker3000 (структура пакета)
    from panicker3000.utils.schemas import PanicSignal, validate_panic_signal

    PYDANTIC_AVAILABLE = True
except ImportError as e:
    # Если импорт с префиксом не сработал, пробуем стандартный путь
    try:
        from utils.schemas import PanicSignal, validate_panic_signal

        PYDANTIC_AVAILABLE = True
    except ImportError as e2:
        logging.warning(f"Pydantic schemas недоступны: {e2}")
        PanicSignal = None
        validate_panic_signal = None
        PYDANTIC_AVAILABLE = False

try:
    # gRPC модули находятся в поддиректории grpc/proto/generated/
    import sys
    import os

    # 1. Добавляем путь к сгенерированным proto файлам
    current_dir = os.path.dirname(os.path.abspath(__file__))  # папка grpc
    proto_generated_path = os.path.join(current_dir, 'proto', 'generated')

    if proto_generated_path not in sys.path:
        sys.path.insert(0, proto_generated_path)

    # 2. Импортируем модули
    import panicker_pb2
    import panicker_pb2_grpc

except ImportError as e:
    print(f"❌ Критическая ошибка: не удалось импортировать gRPC модули: {e}")
    print(f"Проверьте наличие файлов в {proto_generated_path}:")
    print(f"  - panicker_pb2.py")
    print(f"  - panicker_pb2_grpc.py")
    # Создаём заглушки чтобы код мог запуститься
    panicker_pb2 = None
    panicker_pb2_grpc = None
    print("⚠️ Созданы заглушки для gRPC модулей")

logger = logging.getLogger(__name__)


# ============================================================================
# КЛАСС GrpcClient
# ============================================================================
class GrpcClient:
    """Клиент для взаимодействия с gRPC сервером"""

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, host: str = 'localhost', port: int = 50051):
        """
        Инициализация gRPC клиента

        Args:
            host: Хост сервера
            port: Порт сервера
        """
        self.host = host
        self.port = port
        self.channel = grpc.insecure_channel(f'{host}:{port}')

        # Создаём заглушки для всех сервисов
        self.panicker_stub = panicker_pb2_grpc.PanickerServiceStub(self.channel)
        self.market_stub = panicker_pb2_grpc.MarketDataServiceStub(self.channel)
        self.signals_stub = panicker_pb2_grpc.SignalsServiceStub(self.channel)

        logger.info(f"gRPC клиент подключён к {host}:{port}")

    # ------------------------------------------------------------------------
    # МЕТОДЫ PanickerService
    # ------------------------------------------------------------------------
    def get_overheat_index(self, ticker: str) -> Dict[str, Any]:
        """
        Получить индекс перегрева для акции

        Args:
            ticker: Тикер акции

        Returns:
            Словарь с данными индекса перегрева
        """
        logger.info(f"Запрос индекса перегрева для {ticker}")

        try:
            response = self.panicker_stub.GetOverheatIndex(
                panicker_pb2.Ticker(symbol=ticker)
            )

            return {
                'ticker': response.ticker,
                'overheat_percentage': response.overheat_percentage,
                'current_rsi': response.current_rsi,
                'volume_ratio': response.volume_ratio,
                'last_signal_time': response.last_signal_time,
                'last_signal_level': self._convert_level_from_proto(response.last_signal_level)
            }

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при запросе индекса перегрева {ticker}: {e}")
            return self._get_default_overheat_response(ticker)
        except Exception as e:
            logger.error(f"Ошибка при запросе индекса перегрева {ticker}: {e}")
            return self._get_default_overheat_response(ticker)

    def scan_tickers(self, tickers: List[str], real_time: bool = True) -> List[Union[Dict[str, Any], PanicSignal]]:
        """
        Сканирование тикеров на наличие паники/жадности

        Returns:
            Список PanicSignal моделей или словарей (если Pydantic недоступен)
        """
        logger.info(f"Сканирование {len(tickers)} тикеров (режим: {'real-time' if real_time else 'historical'})")

        try:
            ticker_objs = [panicker_pb2.Ticker(symbol=t) for t in tickers]
            request = panicker_pb2.ScanRequest(tickers=ticker_objs, real_time=real_time)

            response = self.panicker_stub.ScanTickers(request)

            signals = []
            for signal in response.signals:
                converted = self._convert_signal_from_proto(signal)
                signals.append(converted)

            # Логируем тип возвращаемых данных
            if signals and PYDANTIC_AVAILABLE and isinstance(signals[0], PanicSignal):
                logger.info(f"✅ Найдено {len(signals)} Pydantic сигналов из {response.total_scanned} тикеров")
            else:
                logger.info(f"⚠️ Найдено {len(signals)} dict сигналов из {response.total_scanned} тикеров")

            return signals

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при сканировании: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при сканировании: {e}")
            return []

    def get_signal_history(self, ticker: str, days_back: int = 7) -> List[Dict[str, Any]]:
        """
        Получить историю сигналов для тикера

        Args:
            ticker: Тикер акции
            days_back: Количество дней истории

        Returns:
            Список исторических сигналов
        """
        logger.info(f"Запрос истории сигналов для {ticker} за {days_back} дней")

        try:
            end_date = datetime.now().isoformat()
            start_date = (datetime.now() - timedelta(days=days_back)).isoformat()

            request = panicker_pb2.HistoryRequest(
                ticker=ticker,
                days_back=days_back,
                limit=100
            )

            response = self.panicker_stub.GetSignalHistory(request)

            signals = []
            for signal in response.signals:
                signals.append(self._convert_signal_from_proto(signal))

            logger.info(f"Получено {len(signals)} исторических сигналов")
            return signals

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при запросе истории: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при запросе истории: {e}")
            return []

    # ------------------------------------------------------------------------
    # МЕТОДЫ MarketDataService
    # ------------------------------------------------------------------------
    def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Получить текущую цену тикера

        Args:
            ticker: Тикер акции

        Returns:
            Текущая цена или None при ошибке
        """
        logger.info(f"Запрос текущей цены для {ticker}")

        try:
            request = panicker_pb2.PriceRequest(tickers=[ticker])
            response = self.market_stub.GetCurrentPrices(request)

            price = response.prices.get(ticker)
            if price:
                return price
            else:
                logger.warning(f"Цена для {ticker} не найдена в ответе")
                return None

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при запросе цены {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при запросе цены {ticker}: {e}")
            return None

    def get_candles(self, ticker: str, interval: str = 'min5', count: int = 100) -> List[Dict[str, Any]]:
        """
        Получить свечи для тикера

        Args:
            ticker: Тикер акции
            interval: Интервал свечей
            count: Количество свечей

        Returns:
            Список свечей
        """
        logger.info(f"Запрос свечей для {ticker}, интервал {interval}, количество {count}")

        try:
            request = panicker_pb2.CandleRequest(
                ticker=ticker,
                interval=interval,
                count=count
            )

            response = self.market_stub.GetCandles(request)

            candles = []
            for candle in response.candles:
                candles.append({
                    'ticker': candle.ticker,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume,
                    'timestamp': candle.timestamp,
                    'interval': candle.interval
                })

            logger.info(f"Получено {len(candles)} свечей")
            return candles

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при запросе свечей {ticker}: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при запросе свечей {ticker}: {e}")
            return []

    # ------------------------------------------------------------------------
    # МЕТОДЫ SignalsService
    # ------------------------------------------------------------------------
    def get_top_signals(self, period: str = 'today', limit: int = 5) -> List[Dict[str, Any]]:
        """
        Получить топ сигналов за период

        Args:
            period: Период ('today', 'week', 'month')
            limit: Максимальное количество сигналов

        Returns:
            Список топ сигналов
        """
        logger.info(f"Запрос топ-{limit} сигналов за период {period}")

        try:
            request = panicker_pb2.TopRequest(period=period, limit=limit)
            response = self.signals_stub.GetTopSignals(request)

            signals = []
            for signal in response.top_signals:
                signals.append(self._convert_signal_from_proto(signal))

            logger.info(f"Получено {len(signals)} топ сигналов")
            return signals

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при запросе топ сигналов: {e}")
            return []
        except Exception as e:
            logger.error(f"Ошибка при запросе топ сигналов: {e}")
            return []

    def ignore_ticker(self, ticker: str, duration_hours: int = 2) -> bool:
        """
        Игнорировать тикер на указанное время

        Args:
            ticker: Тикер акции
            duration_hours: Длительность игнорирования в часах

        Returns:
            True если успешно, False если ошибка
        """
        logger.info(f"Игнорирование {ticker} на {duration_hours} часов")

        try:
            request = panicker_pb2.IgnoreRequest(
                ticker=ticker,
                duration_hours=duration_hours
            )

            response = self.signals_stub.IgnoreTicker(request)

            if response.success:
                logger.info(f"Тикер {ticker} игнорируется до {response.ignored_until}")
                return True
            else:
                logger.warning(f"Не удалось игнорировать {ticker}")
                return False

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при игнорировании {ticker}: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при игнорировании {ticker}: {e}")
            return False

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def _convert_signal_from_proto(self, signal) -> Union[Dict[str, Any], PanicSignal]:
        """Конвертация сигнала из proto в Pydantic модель (или словарь при ошибке)"""
        level_map = {
            panicker_pb2.PanicSignal.STRONG: '🔴 СИЛЬНЫЙ',
            panicker_pb2.PanicSignal.MODERATE: '🟡 ХОРОШИЙ',
            panicker_pb2.PanicSignal.URGENT: '⚪ СРОЧНЫЙ',
            panicker_pb2.PanicSignal.IGNORE: '❌ ИГНОРИРОВАТЬ'
        }

        signal_type_map = {
            panicker_pb2.PanicSignal.PANIC: 'ПАНИКА',
            panicker_pb2.PanicSignal.GREED: 'ЖАДНОСТЬ',
            panicker_pb2.PanicSignal.NEUTRAL: 'НЕЙТРАЛЬНО'
        }

        # Базовые поля
        result = {
            'ticker': signal.ticker,
            'signal_type': signal_type_map.get(signal.signal_type, 'НЕИЗВЕСТНО'),
            'level': level_map.get(signal.level, 'НЕИЗВЕСТНО'),
            'rsi_14': signal.rsi_14,
            'rsi_7': signal.rsi_7,
            'rsi_21': signal.rsi_21,
            'volume_ratio': signal.volume_ratio,
            'current_price': signal.current_price,
            'price': signal.current_price,  # Для совместимости
            'detected_at': signal.detected_at,
            'timestamp': datetime.now().isoformat(),
        }

        # Дополнительные поля (если есть)
        if hasattr(signal, 'risk_metric'):
            result['risk_metric'] = signal.risk_metric
        else:
            result['risk_metric'] = 0.0

        if hasattr(signal, 'interpretation'):
            result['interpretation'] = signal.interpretation
        else:
            result['interpretation'] = ''

        # Кластеры объёма (если есть)
        result['volume_clusters'] = []
        if hasattr(signal, 'volume_clusters'):
            for cluster in signal.volume_clusters:
                result['volume_clusters'].append({
                    'price_level': cluster.price_level,
                    'volume_percentage': cluster.volume_percentage,
                    'role': cluster.role
                })

        # ========================================================================
        # ПЫТАЕМСЯ СОЗДАТЬ PYDANTIC МОДЕЛЬ
        # ========================================================================
        if PYDANTIC_AVAILABLE and validate_panic_signal:
            try:
                is_valid, pydantic_signal, error = validate_panic_signal(result)
                if is_valid and pydantic_signal:
                    logger.info(f"✅ Создана Pydantic модель для {signal.ticker}")
                    return pydantic_signal  # Возвращаем PanicSignal
                else:
                    logger.warning(f"⚠️ Валидация не прошла для {signal.ticker}: {error}")
                    return result  # Возвращаем словарь как запасной вариант
            except Exception as e:
                logger.error(f"❌ Ошибка создания Pydantic модели: {e}")
                return result  # Возвращаем словарь

        # Если Pydantic недоступен, возвращаем словарь
        logger.info(f"⚠️ Pydantic недоступен, возвращаем dict для {signal.ticker}")
        return result

    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        logger.info(f"Запрос статистики за {days} дней")

        try:
            request = panicker_pb2.StatsRequest(days=days)
            response = self.signals_stub.GetStats(request)

            return {
                'total_signals': response.total_signals,
                'strong_signals': response.strong_signals,
                'moderate_signals': response.moderate_signals,
                'urgent_signals': response.urgent_signals,
                'most_active_ticker': response.most_active_ticker,
                'most_active_count': response.most_active_count,
                'most_calm_ticker': response.most_calm_ticker,
                'most_calm_count': response.most_calm_count,
                'market_tension': response.market_tension
            }

        except grpc.RpcError as e:
            logger.error(f"gRPC ошибка при запросе статистики: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при запросе статистики: {e}")
            raise

    def _convert_level_from_proto(self, level_proto: int) -> str:
        """Конвертация уровня из proto в строку"""
        level_map = {
            panicker_pb2.PanicSignal.STRONG: '🔴 СИЛЬНЫЙ',
            panicker_pb2.PanicSignal.MODERATE: '🟡 ХОРОШИЙ',
            panicker_pb2.PanicSignal.URGENT: '⚪ СРОЧНЫЙ',
            panicker_pb2.PanicSignal.IGNORE: '❌ ИГНОРИРОВАТЬ'
        }
        return level_map.get(level_proto, 'НЕИЗВЕСТНО')

    def _get_default_overheat_response(self, ticker: str) -> Dict[str, Any]:
        """Ответ по умолчанию при ошибке"""
        return {
            'ticker': ticker,
            'overheat_percentage': None,
            'current_rsi': None,
            'volume_ratio': None,
            'last_signal_time': '',
            'last_signal_level': 'ОШИБКА ПОДКЛЮЧЕНИЯ'
        }

    def _get_default_stats_response(self) -> Dict[str, Any]:
        """Ответ по умолчанию при ошибке получения статистики"""
        return {
            'total_signals': None,
            'strong_signals': None,
            'moderate_signals': None,
            'urgent_signals': None,
            'most_active_ticker': None,
            'most_active_count': None,
            'most_calm_ticker': None,
            'most_calm_count': None,
            'market_tension': None
        }

    # ------------------------------------------------------------------------
    # ЗАКРЫТИЕ СОЕДИНЕНИЯ
    # ------------------------------------------------------------------------
    def close(self):
        """Закрыть соединение с сервером"""
        if self.channel:
            self.channel.close()
            logger.info("Соединение с gRPC сервером закрыто")


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР КЛИЕНТА
# ============================================================================
_client_instance: Optional[GrpcClient] = None


def get_grpc_client() -> GrpcClient:
    """Получить глобальный экземпляр gRPC клиента (синглтон)"""
    global _client_instance
    if _client_instance is None:
        _client_instance = GrpcClient()
    return _client_instance

