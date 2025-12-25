# panicker3000/grpc/grpc_server.py
"""
gRPC сервер для Паникёра 3000.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import grpc
from concurrent import futures
import logging
from datetime import datetime
import time
import sys
import os
from typing import Dict, Optional
import codecs

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

sys.path.extend([
    os.path.join(project_root, 'core'),
    os.path.join(project_root, 'data'),
    os.path.join(project_root, 'config'),
    os.path.join(project_root, 'utils')
])

# Исправляем кодировку для Windows
if sys.platform == "win32":
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ============================================================================
# PYDANTIC SCHEMAS IMPORT
# ============================================================================
try:
    # Пробуем импорт с префиксом panicker3000 (структура пакета)
    from panicker3000.utils.schemas import PanicSignal, TickerData, validate_panic_signal
    PYDANTIC_AVAILABLE = True
except ImportError as e:
    # Если импорт с префиксом не сработал, пробуем стандартный путь
    try:
        from utils.schemas import PanicSignal, TickerData, validate_panic_signal
        PYDANTIC_AVAILABLE = True
    except ImportError as e2:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать Pydantic модели!")
        print(f"Проверьте наличие файла: panicker3000/utils/schemas.py")
        print(f"Ошибка: {e2}")
        sys.exit(1)

# ============================================================================
# ИМПОРТ gRPC МОДУЛЕЙ (КРИТИЧЕСКИЙ)
# ============================================================================
# 1. Добавляем путь к сгенерированным proto файлам
current_dir = os.path.dirname(os.path.abspath(__file__))  # папка grpc
proto_generated_path = os.path.join(current_dir, 'proto', 'generated')

if proto_generated_path not in sys.path:
    sys.path.insert(0, proto_generated_path)

# 2. Импортируем модули (если нет — критическая ошибка)
try:
    import panicker_pb2
    import panicker_pb2_grpc
    print(f"✅ gRPC модули импортированы из {proto_generated_path}")
except ImportError as e:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось импортировать gRPC модули!")
    print(f"Путь: {proto_generated_path}")
    print(f"Файлы должны быть:")
    print(f"  - {os.path.join(proto_generated_path, 'panicker_pb2.py')}")
    print(f"  - {os.path.join(proto_generated_path, 'panicker_pb2_grpc.py')}")
    print(f"Ошибка: {e}")
    print("\nСгенерируйте gRPC модули командой:")
    print("python -m grpc_tools.protoc -Iproto --python_out=grpc/proto/generated --grpc_python_out=grpc/proto/generated proto/*.proto")
    sys.exit(1)

logger = logging.getLogger(__name__)

# ============================================================================
# РЕАЛЬНЫЕ ИМПОРТЫ ПРОЕКТА (проверка доступности)
# ============================================================================
try:
    from core.config_loader import ConfigLoader

    logger.info("✅ ConfigLoader импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ ConfigLoader недоступен: {e}")
    ConfigLoader = None

try:
    from core.panic_detector import PanicDetector

    logger.info("✅ PanicDetector импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ PanicDetector недоступен: {e}")
    PanicDetector = None

try:
    from data.tinkoff_client import TinkoffClient

    logger.info("✅ TinkoffClient импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ TinkoffClient недоступен: {e}")
    TinkoffClient = None

try:
    import yaml

    logger.info("✅ yaml импортирован успешно")
except ImportError as e:
    logger.warning(f"⚠️ yaml недоступен: {e}")
    yaml = None

# Анализаторы уже импортированы в panic_detector.py

# ============================================================================
# КЛАСС PanickerServiceServicer (ОБНОВЛЁН)
# ============================================================================
class PanickerServiceServicer(panicker_pb2_grpc.PanickerServiceServicer):

    def __init__(self):
        logger.info("PanickerServiceServicer инициализирован")

        # Инициализация реальных компонентов
        self.config_loader = None
        self.panic_detector = None

        try:
            if ConfigLoader is not None:
                self.config_loader = ConfigLoader()
                logger.info("✅ ConfigLoader инициализирован")

                if PanicDetector is not None:
                    self.panic_detector = PanicDetector(config_loader=self.config_loader)
                    logger.info("✅ PanicDetector инициализирован с поддержкой шагов 9-10")

            logger.info("✅ Все компоненты загружены")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации компонентов: {e}")
            logger.info("⚠️  Работаем в режиме заглушек")

    def ScanTickers(self, request, context):
        logger.info(f"ScanTickers: {len(request.tickers)} тикеров")

        signals = []
        tickers_scanned = 0

        # Пробуем использовать реальный PanicDetector если доступен
        if self.panic_detector is not None:
            logger.info("✅ Используем реальный PanicDetector для сканирования")

            for ticker_obj in request.tickers:
                ticker = ticker_obj.symbol
                tickers_scanned += 1

                try:
                    # ПОЛУЧАЕМ РЕАЛЬНЫЕ ДАННЫЕ ДЛЯ АНАЛИЗА
                    real_data = self._get_real_ticker_data(ticker)

                    if not real_data:
                        logger.error(f"❌ Не удалось получить данные для {ticker}")
                        continue

                    # Анализируем через реальный детектор (10 шагов)
                    logger.info(f"🔍 Анализируем {ticker} (10 шагов)...")
                    signal = self.panic_detector.analyze_ticker(real_data)

                    if signal:
                        # Конвертируем реальный сигнал в proto (с кластерами и риском)
                        proto_signal = self._convert_real_signal_to_proto(signal, real_data)
                        signals.append(proto_signal)

                        # СОХРАНЯЕМ СИГНАЛ В БД
                        try:
                            from data.database import Database
                            db = Database()

                            signal_data = {
                                'ticker': ticker,
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'signal_type': 'ПАНИКА' if signal.signal_type.name == 'PANIC' else 'ЖАДНОСТЬ',
                                'level': self._convert_level_to_text(signal.final_level),
                                'rsi_14': signal.rsi_14,
                                'volume_ratio': signal.volume_ratio,
                                'price': real_data.get('price', 0),
                                'risk_metric': signal.risk_metric,
                                'volume_clusters_count': len(signal.volume_clusters)
                            }

                            db.save_signal(signal_data)
                            logger.info(f"💾 Сигнал сохранён в БД: {ticker}")

                        except Exception as db_error:
                            logger.error(f"❌ Ошибка сохранения сигнала в БД: {db_error}")

                        # Логируем детали
                        logger.info(f"✅ Обнаружен сигнал для {ticker}:")
                        logger.info(f"   Уровень: {signal.final_level.value}")
                        logger.info(f"   Тип: {signal.signal_type.value}")
                        logger.info(f"   Риск: {signal.risk_metric}")
                        logger.info(f"   Кластеров: {len(signal.volume_clusters)}")

                        logger.debug(f"❌ Нет сигнала для {ticker}")

                except Exception as e:
                    logger.error(f"❌ Ошибка анализа {ticker}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

                logger.info(f"📊 Итог сканирования: {tickers_scanned} тикеров, {len(signals)} сигналов")
                return panicker_pb2.ScanResponse(
                    signals=signals,
                    scan_id=f"scan_{int(time.time())}",
                    timestamp=datetime.now().isoformat(),
                    total_scanned=tickers_scanned,
                    signals_found=len(signals)
                )
            else:
                # PanicDetector недоступен - возвращаем пустой результат
                logger.error("❌ PanicDetector недоступен, невозможно выполнить сканирование")
                return panicker_pb2.ScanResponse(
                    signals=[],
                    scan_id=f"scan_error_{int(time.time())}",
                    timestamp=datetime.now().isoformat(),
                    total_scanned=0,
                    signals_found=0
                )

        logger.info(f"📊 Итог сканирования: {tickers_scanned} тикеров, {len(signals)} сигналов")
        return panicker_pb2.ScanResponse(
            signals=signals,
            scan_id=f"scan_{int(time.time())}",
            timestamp=datetime.now().isoformat(),
            total_scanned=tickers_scanned,
            signals_found=len(signals)
        )

    def GetOverheatIndex(self, request, context):
        logger.info(f"GetOverheatIndex: {request.symbol}")

        # ПОЛУЧАЕМ РЕАЛЬНЫЕ ДАННЫЕ
        ticker_data = self._get_real_ticker_data(request.symbol)

        if not ticker_data:
            logger.error(f"❌ Не удалось получить данные для {request.symbol}")
            return panicker_pb2.OverheatIndex(
                ticker=request.symbol,
                overheat_percentage=0.0,
                current_rsi=50.0,
                volume_ratio=1.0,
                last_signal_time=datetime.now().isoformat(),
                last_signal_level=panicker_pb2.PanicSignal.URGENT
            )

        # Рассчитываем индекс перегрева на основе RSI и объёма
        rsi_14 = ticker_data.get('rsi_14', 50.0)
        volume_ratio = ticker_data.get('volume_ratio', 1.0)

        # Формула: 0% при RSI=50, 100% при RSI=0 или RSI=100
        overheat_percentage = abs(rsi_14 - 50) * 2  # 0-100%

        return panicker_pb2.OverheatIndex(
            ticker=request.symbol,
            overheat_percentage=overheat_percentage,
            current_rsi=rsi_14,
            volume_ratio=volume_ratio,
            last_signal_time=datetime.now().isoformat(),
            last_signal_level=panicker_pb2.PanicSignal.MODERATE
        )

    def GetSignalHistory(self, request, context):
        """Получить историю сигналов для тикера за указанный период"""
        logger.info(f"GetSignalHistory: {request.ticker}, дней назад: {request.days_back}")

        # Проверяем лимит
        limit = request.limit if request.limit > 0 else 100  # значение по умолчанию
        logger.info(f"GetSignalHistory: {request.ticker}, дней назад: {request.days_back}, лимит: {limit}")

        try:
            # Импортируем базу данных
            from data.database import Database
            from datetime import datetime, timedelta

            db = Database()

            # Получаем историю сигналов из базы данных
            history = db.get_signal_history(
                ticker=request.ticker,
                days_back=request.days_back
            )

            # Применяем лимит если указан
            if limit > 0 and len(history) > limit:
                history = history[:limit]

            # Конвертируем в proto формат
            signals_proto = []

            for signal in history:
                # Маппинг уровней
                level_map = {
                    '🔴 СИЛЬНЫЙ': panicker_pb2.PanicSignal.STRONG,
                    '🟡 ХОРОШИЙ': panicker_pb2.PanicSignal.MODERATE,
                    '⚪ СРОЧНЫЙ': panicker_pb2.PanicSignal.URGENT,
                    '❌ ИГНОРИРОВАТЬ': panicker_pb2.PanicSignal.IGNORE
                }

                # Маппинг типов
                signal_type_map = {
                    'ПАНИКА': panicker_pb2.PanicSignal.PANIC,
                    'ЖАДНОСТЬ': panicker_pb2.PanicSignal.GREED
                }

                proto_signal = panicker_pb2.PanicSignal(
                    ticker=signal.get('ticker', 'UNKNOWN'),
                    signal_type=signal_type_map.get(signal.get('signal_type', 'ПАНИКА'),
                                                    panicker_pb2.PanicSignal.PANIC),
                    level=level_map.get(signal.get('level', '⚪ СРОЧНЫЙ'), panicker_pb2.PanicSignal.URGENT),
                    rsi_14=signal.get('rsi_14', 50.0),
                    volume_ratio=signal.get('volume_ratio', 1.0),
                    current_price=signal.get('price', 0.0),
                    detected_at=signal.get('timestamp', datetime.now().isoformat()),
                    interpretation=signal.get('interpretation', 'Исторический сигнал'),
                    risk_metric=signal.get('risk_metric', 0.0)
                )
                signals_proto.append(proto_signal)

            logger.info(f"📊 Получено {len(signals_proto)} сигналов из БД для {request.ticker}")

            return panicker_pb2.SignalHistory(
                signals=signals_proto,
                total_count=len(signals_proto)
            )

        except ImportError as e:
            logger.error(f"❌ Ошибка импорта базы данных: {e}")
            # Возвращаем пустой список если БД недоступна
            return panicker_pb2.SignalHistory(
                signals=[],
                total_count=0
            )

        except Exception as e:
            logger.error(f"❌ Ошибка получения истории сигналов: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return panicker_pb2.SignalHistory(
                signals=[],
                total_count=0
            )

    def _convert_real_signal_to_proto(self, signal):
        """Конвертировать реальный сигнал PanicDetector в proto с кластерами и риском"""
        try:
            # ====================================================================
            # ПОДДЕРЖКА PYDANTIC MODELS
            # ====================================================================
            # Проверяем, является ли signal объектом PanicSignal из schemas.py
            if PYDANTIC_AVAILABLE and isinstance(signal, PanicSignal):
                logger.info(f"📊 Получен Pydantic сигнал для {signal.ticker}")
                # Используем валидированные данные из Pydantic модели
                signal_data = signal.dict()
                ticker = signal.ticker
                rsi_14 = signal.rsi_14
                volume_ratio = signal.volume_ratio
                final_level_str = signal.final_level.value if hasattr(signal.final_level, 'value') else str(
                    signal.final_level)
                signal_type_str = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(
                    signal.signal_type)

                # Маппинг уровней из Pydantic в proto
                level_map = {
                    'RED': panicker_pb2.PanicSignal.STRONG,
                    'YELLOW': panicker_pb2.PanicSignal.MODERATE,
                    'WHITE': panicker_pb2.PanicSignal.URGENT,
                    'IGNORE': panicker_pb2.PanicSignal.IGNORE
                }

                # Маппинг типов сигналов
                signal_type_map = {
                    'PANIC': panicker_pb2.PanicSignal.PANIC,
                    'GREED': panicker_pb2.PanicSignal.GREED
                }

                # Старая логика для обратной совместимости
                logger.info(f"📊 Получен сигнал в старом формате для {signal.ticker}")

                # Маппинг уровней из PanicDetector в proto
                level_map = {
                    'RED': panicker_pb2.PanicSignal.STRONG,
                    'YELLOW': panicker_pb2.PanicSignal.MODERATE,
                    'WHITE': panicker_pb2.PanicSignal.URGENT,
                    'IGNORE': panicker_pb2.PanicSignal.IGNORE
                }

                # Маппинг типов сигналов
                signal_type_map = {
                    'PANIC': panicker_pb2.PanicSignal.PANIC,
                    'GREED': panicker_pb2.PanicSignal.GREED
                }

            # Получаем цену из сигнала

            # Получаем финальный уровень как строку
            final_level_str = str(signal.final_level)
            if '.' in final_level_str:
                final_level_str = final_level_str.split('.')[-1]

            # Получаем тип сигнала как строку
            signal_type_str = str(signal.signal_type)
            if '.' in signal_type_str:
                signal_type_str = signal_type_str.split('.')[-1]

            # Создаём базовый сигнал
            proto_signal = panicker_pb2.PanicSignal(
                ticker=signal.ticker,
                signal_type=signal_type_map.get(signal_type_str, panicker_pb2.PanicSignal.PANIC),
                level=level_map.get(final_level_str, panicker_pb2.PanicSignal.MODERATE),
                rsi_14=signal.rsi_14 if hasattr(signal, 'rsi_14') else 50.0,
                rsi_7=signal.rsi_7 if hasattr(signal, 'rsi_7') else 50.0,
                rsi_21=signal.rsi_21 if hasattr(signal, 'rsi_21') else 50.0,
                volume_ratio=signal.volume_ratio if hasattr(signal, 'volume_ratio') else 1.0,
                current_price=current_price,
                detected_at=datetime.now().isoformat(),
                interpretation=signal.interpretation if hasattr(signal, 'interpretation') else "Реальный сигнал",
                risk_metric=signal.risk_metric if hasattr(signal, 'risk_metric') else 0.0
            )

            # Добавляем кластеры объёма (ШАГ 9)
            if hasattr(signal, 'volume_clusters') and signal.volume_clusters:
                logger.info(f"📊 Добавление кластеров объёма: {len(signal.volume_clusters)}")

                for cluster in signal.volume_clusters:
                    # Проверяем тип кластера
                    if hasattr(cluster, 'price_level'):
                        # Это объект VolumeCluster из cluster_analyzer.py
                        cluster_proto = proto_signal.volume_clusters.add()
                        cluster_proto.price_level = cluster.price_level
                        cluster_proto.volume_percentage = cluster.volume_percentage
                        cluster_proto.role = cluster.role
                    elif isinstance(cluster, dict):
                        # Это словарь с данными кластера
                        cluster_proto = proto_signal.volume_clusters.add()
                        cluster_proto.price_level = cluster.get('price_level', 0.0)
                        cluster_proto.volume_percentage = cluster.get('volume_percentage', 0.0)
                        cluster_proto.role = cluster.get('role', 'neutral')
                    
                        logger.warning(f"⚠️  Неизвестный тип кластера: {type(cluster)}")

                logger.info(f"✅ Добавлено {len(proto_signal.volume_clusters)} кластеров в proto-сигнал")

            # Добавляем риск-метрику и интерпретацию (ШАГ 10)
            if hasattr(signal, 'risk_metric') and signal.risk_metric is not None:
                proto_signal.risk_metric = signal.risk_metric
                logger.info(f"📊 Установлена риск-метрика: {signal.risk_metric}")

            if hasattr(signal, 'risk_interpretation') and signal.risk_interpretation:
                if proto_signal.interpretation:
                    proto_signal.interpretation = f"{proto_signal.interpretation}\n\n📊 РИСК-АНАЛИЗ:\n{signal.risk_interpretation}"
                
                    proto_signal.interpretation = f"📊 РИСК-АНАЛИЗ:\n{signal.risk_interpretation}"

            # Добавляем сводку по кластерам если есть
            if hasattr(signal, 'cluster_summary') and signal.cluster_summary:
                if proto_signal.interpretation:
                    proto_signal.interpretation = f"{proto_signal.interpretation}\n\n📊 КЛАСТЕРЫ ОБЪЁМА:\n{signal.cluster_summary}"
                
                    proto_signal.interpretation = f"📊 КЛАСТЕРЫ ОБЪЁМА:\n{signal.cluster_summary}"

            # Логирование итогов
            logger.info(f"📊 Итог конвертации для {signal.ticker}:")
            logger.info(f"   Уровень: {final_level_str}")
            logger.info(f"   Тип: {signal_type_str}")
            logger.info(f"   risk_metric = {proto_signal.risk_metric}")
            logger.info(f"   volume_clusters count = {len(proto_signal.volume_clusters)}")
            logger.info(f"   interpretation length = {len(proto_signal.interpretation)} символов")

            return proto_signal

        except Exception as e:
            logger.error(f"❌ Ошибка конвертации сигнала: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _convert_level_to_text(self, level):
        """Конвертировать уровень сигнала в текст"""
        level_map = {
            'RED': '🔴 СИЛЬНЫЙ',
            'YELLOW': '🟡 ХОРОШИЙ',
            'WHITE': '⚪ СРОЧНЫЙ',
            'IGNORE': '❌ ИГНОРИРОВАТЬ'
        }
        # Извлекаем значение из enum: "FinalLevel.YELLOW" → "YELLOW"
        level_str = str(level)
        if '.' in level_str:
            level_str = level_str.split('.')[-1]
        return level_map.get(level_str, 'НЕИЗВЕСТНО')

    def _get_real_ticker_data(self, ticker: str) -> Dict:
        """Получение РЕАЛЬНЫХ данных по тикеру из Tinkoff API"""
        try:
            from data.tinkoff_client import TinkoffClient
            from core.indicators import calculate_rsi, calculate_atr, calculate_sma

            client = TinkoffClient()

            # Получаем часовые свечи за последние 30 дней
            candles = client.get_candles(ticker, interval='hour', count=720)

            if not candles or len(candles) < 50:
                logger.error(f"❌ Недостаточно данных для {ticker}: {len(candles) if candles else 0} свечей")
                return {}

            # Извлекаем данные для расчётов
            closes = [candle['close'] for candle in candles]
            volumes = [candle['volume'] for candle in candles]
            highs = [candle['high'] for candle in candles]
            lows = [candle['low'] for candle in candles]

            # РАСЧЁТ РЕАЛЬНЫХ ПОКАЗАТЕЛЕЙ
            rsi_7 = calculate_rsi(closes, period=7)
            rsi_14 = calculate_rsi(closes, period=14)
            rsi_21 = calculate_rsi(closes, period=21)
            atr_value = calculate_atr(highs, lows, closes, period=14)
            sma_20 = calculate_sma(closes, period=20)

            # Текущий и средний объём
            current_volume = volumes[-1] if volumes else 0
            avg_volume = sum(volumes[-20:]) / min(20, len(volumes)) if volumes else 0
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            return {
                'ticker': ticker,
                'historical_prices': closes,
                'historical_volumes': volumes,
                'price': closes[-1] if closes else 0,
                'rsi_7': rsi_7[-1] if rsi_7 else 50.0,
                'rsi_14': rsi_14[-1] if rsi_14 else 50.0,
                'rsi_21': rsi_21[-1] if rsi_21 else 50.0,
                'volume_ratio': volume_ratio,
                'current_volume': current_volume,
                'average_volume': avg_volume,
                'atr': atr_value[-1] if atr_value else 2.0,
                'sma_20': sma_20[-1] if sma_20 else closes[-1] if closes else 0,
                'spread_percent': 0.05,
                'current_atr': atr_value[-1] if atr_value else 2.0,
                'average_atr': sum(atr_value[-20:]) / min(20, len(atr_value)) if atr_value else 2.0
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения РЕАЛЬНЫХ данных для {ticker}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {}

# ============================================================================
# КЛАСС MarketDataServiceServicer
# ============================================================================
class MarketDataServiceServicer(panicker_pb2_grpc.MarketDataServiceServicer):

    def __init__(self):
        logger.info("MarketDataServiceServicer инициализирован")

    def GetCandles(self, request, context):
        logger.info(f"GetCandles: {request.ticker}, интервал: {request.interval}, количество: {request.count}")

        try:
            # Импортируем TinkoffClient
            from data.tinkoff_client import TinkoffClient
            from datetime import datetime

            client = TinkoffClient()

            # Получаем свечи из API
            candles_data = client.get_candles(
                ticker=request.ticker,
                interval=request.interval,
                count=request.count
            )

            # Конвертируем в proto формат
            candles_proto = []

            for candle in candles_data:
                # Получаем время свечи как строку
                candle_time = candle.get('time')
                if isinstance(candle_time, str):
                    # Оставляем как есть (уже строка)
                    pass
                elif hasattr(candle_time, 'timestamp'):
                    # Это datetime объект - конвертируем в строку
                    candle_time = candle_time.isoformat()
                else:
                    # Используем текущее время как строку
                    candle_time = datetime.now().isoformat()

                # Создаём proto свечу (ВСЕ 8 полей!)
                candle_proto = panicker_pb2.Candle(
                    ticker=request.ticker,  # обязательное поле
                    open=candle.get('open', 0.0),
                    high=candle.get('high', 0.0),
                    low=candle.get('low', 0.0),
                    close=candle.get('close', 0.0),
                    volume=candle.get('volume', 0),
                    timestamp=candle_time,  # строка, а не Timestamp
                    interval=request.interval  # обязательное поле
                )
                candles_proto.append(candle_proto)

            logger.info(f"📊 Получено {len(candles_proto)} свечей для {request.ticker}")

            return panicker_pb2.CandleResponse(
                candles=candles_proto,
                request_id=f"candles_{request.ticker}_{int(time.time())}"
            )

        except ImportError as e:
            logger.error(f"❌ Ошибка импорта TinkoffClient: {e}")
            # Возвращаем пустой список если API недоступно
            return panicker_pb2.CandleResponse(
                candles=[],
                request_id=f"error_{request.ticker}"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка получения свечей для {request.ticker}: {e}")
            return panicker_pb2.CandleResponse(
                candles=[],
                request_id=f"error_{request.ticker}"
            )

    def GetCurrentPrices(self, request, context):
        logger.info(f"GetCurrentPrices: {len(request.tickers)} тикеров")

        try:
            # Получаем реальные цены через Tinkoff API
            from data.tinkoff_client import TinkoffClient

            client = TinkoffClient()
            prices = {}

            for ticker_obj in request.tickers:
                ticker = ticker_obj.symbol
                try:
                    # Получаем последнюю цену
                    last_price = client.get_last_price(ticker)
                    if last_price:
                        prices[ticker] = last_price
                    
                        prices[ticker] = 0.0
                        logger.warning(f"⚠️  Не удалось получить цену для {ticker}")
                except Exception as e:
                    logger.error(f"❌ Ошибка получения цены {ticker}: {e}")
                    prices[ticker] = 0.0

            logger.info(f"📊 Получены реальные цены для {len(prices)} тикеров")

            return panicker_pb2.PriceResponse(
                prices=prices,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в GetCurrentPrices: {e}")
            # Возвращаем пустые цены при ошибке
            return panicker_pb2.PriceResponse(
                prices={},
                timestamp=datetime.now().isoformat()
            )

    def GetOrderBook(self, request, context):
        logger.info(f"GetOrderBook: {request.ticker}")

        try:
            # Получаем реальный стакан через Tinkoff API
            from data.tinkoff_client import TinkoffClient

            client = TinkoffClient()
            orderbook = client.get_orderbook(request.ticker)

            if orderbook:
                spread = orderbook.get('spread_percentage', 0.05)
                return panicker_pb2.OrderBookResponse(
                    ticker=request.ticker,
                    spread_percentage=spread,
                    best_bid=orderbook.get('best_bid', 0.0),
                    best_ask=orderbook.get('best_ask', 0.0),
                    bid_volume=orderbook.get('bid_volume', 0),
                    ask_volume=orderbook.get('ask_volume', 0)
                )
            
                return panicker_pb2.OrderBookResponse(
                    ticker=request.ticker,
                    spread_percentage=0.05  # Значение по умолчанию
                )

        except Exception as e:
            logger.error(f"❌ Ошибка в GetOrderBook: {e}")
            return panicker_pb2.OrderBookResponse(
                ticker=request.ticker,
                spread_percentage=0.05
            )

# ============================================================================
# КЛАСС SignalsServiceServicer
# ============================================================================
class SignalsServiceServicer(panicker_pb2_grpc.SignalsServiceServicer):

    def __init__(self):
        logger.info("SignalsServiceServicer инициализирован")

    def GetTopSignals(self, request, context):
        logger.info(f"GetTopSignals: период {request.period}, лимит {request.limit}")

        try:
            # Импортируем базу данных
            from data.database import Database

            db = Database()

            # Получаем топ сигналов из базы данных
            top_signals = db.get_top_signals(
                period=request.period,
                limit=request.limit
            )

            # Конвертируем в proto формат
            signals_proto = []

            for signal in top_signals:
                # Маппинг уровней
                level_map = {
                    '🔴 СИЛЬНЫЙ': panicker_pb2.PanicSignal.STRONG,
                    '🟡 ХОРОШИЙ': panicker_pb2.PanicSignal.MODERATE,
                    '⚪ СРОЧНЫЙ': panicker_pb2.PanicSignal.URGENT,
                    '❌ ИГНОРИРОВАТЬ': panicker_pb2.PanicSignal.IGNORE
                }

                # Маппинг типов
                signal_type_map = {
                    'ПАНИКА': panicker_pb2.PanicSignal.PANIC,
                    'ЖАДНОСТЬ': panicker_pb2.PanicSignal.GREED
                }

                proto_signal = panicker_pb2.PanicSignal(
                    ticker=signal.get('ticker', 'UNKNOWN'),
                    signal_type=signal_type_map.get(signal.get('signal_type', 'ПАНИКА'),
                                                    panicker_pb2.PanicSignal.PANIC),
                    level=level_map.get(signal.get('level', '⚪ СРОЧНЫЙ'), panicker_pb2.PanicSignal.URGENT),
                    rsi_14=signal.get('rsi_14', 50.0),
                    volume_ratio=signal.get('volume_ratio', 1.0),
                    current_price=signal.get('price', 0.0),
                    detected_at=signal.get('timestamp', datetime.now().isoformat()),
                    interpretation=signal.get('interpretation', 'Сигнал из базы данных'),
                    risk_metric=signal.get('risk_metric', 0.0)
                )
                signals_proto.append(proto_signal)

            logger.info(f"📊 Получено {len(signals_proto)} сигналов из БД")

            return panicker_pb2.TopResponse(
                top_signals=signals_proto,
                period=request.period
            )

        except ImportError as e:
            logger.error(f"❌ Ошибка импорта базы данных: {e}")
            # Возвращаем пустой список если БД недоступна
            return panicker_pb2.TopResponse(
                top_signals=[],
                period=request.period
            )

        except Exception as e:
            logger.error(f"❌ Ошибка получения топ сигналов: {e}")
            return panicker_pb2.TopResponse(
                top_signals=[],
                period=request.period
            )

    def GetStats(self, request, context):
        """Получить статистику сигналов за указанный период"""
        logger.info(f"GetStats: запрос статистики за {request.days} дней")

        try:
            # Импортируем базу данных
            from data.database import Database

            db = Database()
            stats = db.get_stats(days=request.days)

            logger.info(f"📊 Статистика получена: всего {stats['total_signals']} сигналов")

            # Возвращаем статистику в proto формате
            return panicker_pb2.StatsResponse(
                total_signals=stats['total_signals'],
                strong_signals=stats['strong_signals'],
                moderate_signals=stats['moderate_signals'],
                urgent_signals=stats['urgent_signals'],
                most_active_ticker=stats['most_active_ticker'],
                most_active_count=stats['most_active_count'],
                most_calm_ticker=stats['most_calm_ticker'],
                most_calm_count=stats['most_calm_count'],
                market_tension=stats['market_tension']
            )


        except ImportError as e:

            logger.error(f"❌ Ошибка импорта базы данных: {e}")

            # Возвращаем нулевую статистику

            return panicker_pb2.StatsResponse(
                total_signals=0,
                strong_signals=0,
                moderate_signals=0,
                urgent_signals=0,
                most_active_ticker="НЕТ ДАННЫХ",
                most_active_count=0,
                most_calm_ticker="НЕТ ДАННЫХ",
                most_calm_count=0,
                market_tension="🟢 НЕТ ДАННЫХ"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return panicker_pb2.StatsResponse(
                total_signals=0,
                strong_signals=0,
                moderate_signals=0,
                urgent_signals=0,
                most_active_ticker="НЕТ ДАННЫХ",
                most_active_count=0,
                most_calm_ticker="НЕТ ДАННЫХ",
                most_calm_count=0,
                market_tension="🟢 НЕТ ДАННЫХ"
            )

    def IgnoreTicker(self, request, context):
        logger.info(f"IgnoreTicker: {request.ticker}")
        return panicker_pb2.IgnoreResponse(
            success=True,
            ignored_until=datetime.now().isoformat()
        )

    def StreamSignals(self, request, context):
        logger.info(f"StreamSignals: {len(request.tickers)} тикеров")
        return

# ============================================================================
# ФУНКЦИЯ serve
# ============================================================================
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    panicker_pb2_grpc.add_PanickerServiceServicer_to_server(
        PanickerServiceServicer(), server
    )
    panicker_pb2_grpc.add_MarketDataServiceServicer_to_server(
        MarketDataServiceServicer(), server
    )
    panicker_pb2_grpc.add_SignalsServiceServicer_to_server(
        SignalsServiceServicer(), server
    )

    port = 50051
    server.add_insecure_port(f'[::]:{port}')
    server.start()

    logger.info(f"✅ gRPC сервер запущен на порту {port}")
    logger.info("✅ Сервисы готовы к работе")
    logger.info("✅ Поддержка шагов 9-10 (кластеры объёма и риск-метрики) активирована")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Сервер остановлен")
        server.stop(0)

# ============================================================================
# ТОЧКА ВХОДА
# ============================================================================
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    serve()