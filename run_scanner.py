# panicker3000/run_scanner.py
"""
ГЛАВНЫЙ СКРИПТ ЗАПУСКА СИСТЕМЫ «ПАНИКЁР 3000»

Основные функции:
1. Проверка времени работы биржи ММВБ с учётом праздников
2. Запуск gRPC сервера в отдельном процессе
3. Запуск Telegram бота
4. Обработка ошибок и graceful shutdown

Использование:
    python run_scanner.py
"""

# ============================================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================================
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

# Снижаем уровень для шумных библиотек
logging.getLogger('grpc').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('tinkoff').setLevel(logging.WARNING)

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import os
import sys
import subprocess
import time
from datetime import datetime, time as dt_time
from typing import Optional
import signal
import atexit
import yaml
import grpc
from typing import List, Dict, Any

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем MarketCalendar для проверки времени биржи
from data.market_calendar import get_market_calendar

# ============================================================================
# ГЛОБАЛЬНЫЙ ЛОГГЕР
# ============================================================================
logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
GRPC_SERVER_PORT = 50051
CHECK_INTERVAL = 60  # Проверка каждые 60 секунд
SCAN_INTERVAL = 60  # Интервал сканирования (секунды)
SCAN_COOLDOWN = 300  # Ожидание при закрытой бирже (секунды)
REQUEST_DELAY = 0.2  # Задержка между запросами к API


# ============================================================================
# УДАЛЕН КЛАСС MarketTimeChecker - заменён на MarketCalendar
# ============================================================================

# ============================================================================
# КЛАСС ConfigLoader
# ============================================================================
class ConfigLoader:
    """Загрузчик конфигурации"""

    @staticmethod
    def load_tickers() -> List[str]:
        """Загрузка списка тикеров из конфига"""
        try:
            config_path = os.path.join("config", "tickers.yaml")
            if not os.path.exists(config_path):
                logger.warning(f"⚠️  Файл конфига не найден: {config_path}")
                return ["SBER", "GAZP", "LKOH", "GMKN", "YNDX"]

            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Получаем список тикеров из структуры config
            tickers = []
            for item in config.get('tickers', []):
                if isinstance(item, dict) and 'ticker' in item:
                    tickers.append(item['ticker'])
                elif isinstance(item, str):
                    tickers.append(item)

            if not tickers:
                return ["SBER", "GAZP", "LKOH", "GMKN", "YNDX"]

            logger.info(f"📋 Загружено {len(tickers)} тикеров из конфига")
            return tickers

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки конфига: {e}")
            return ["SBER", "GAZP", "LKOH", "GMKN", "YNDX"]

    @staticmethod
    def load_scan_settings() -> Dict[str, Any]:
        """Загрузка настроек сканирования"""
        return {
            'scan_interval': SCAN_INTERVAL,
            'cooldown_closed': SCAN_COOLDOWN,
            'request_delay': REQUEST_DELAY,
            'max_retries': 3,
        }


# ============================================================================
# КЛАСС PanickerScanner
# ============================================================================
class PanickerScanner:
    """Основной класс для запуска и управления системой"""

    def __init__(self):
        self.grpc_process: Optional[subprocess.Popen] = None
        self.bot_process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.scanning = False  # Флаг сканирования
        self.tickers = []  # Список тикеров
        self.scan_settings = {}  # Настройки сканирования

        # Инициализируем MarketCalendar
        self.market_calendar = get_market_calendar()

        # ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ:
        self._init_components()

        # Регистрируем обработчики завершения
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("🤖 PanickerScanner инициализирован с MarketCalendar")

    def start_auto_scanning(self):
        """Запуск автосканирования в отдельном потоке"""
        if self.scanning:
            logger.warning("⚠️  Автосканирование уже запущено")
            return

        import threading
        self.scanning = True
        scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        scan_thread.start()
        logger.info("🔄 Автосканирование запущено в отдельном потоке")

    def stop_auto_scanning(self):
        """Остановка автосканирования"""
        self.scanning = False
        logger.info("⏹️  Автосканирование остановлено")

    def _scan_loop(self):
        """Основной цикл сканирования"""
        logger.info("🔍 Начинаем циклическое сканирование рынка...")

        scan_count = 0
        last_scan_time = datetime.now()

        while self.scanning and self.is_running:
            try:
                current_time = datetime.now()
                time_since_last_scan = (current_time - last_scan_time).total_seconds()

                # Проверяем, пора ли сканировать
                if time_since_last_scan < self.scan_settings['scan_interval']:
                    time.sleep(1)
                    continue

                # Обновляем время последнего сканирования
                last_scan_time = current_time
                scan_count += 1

                logger.info(f"🔍 Сканирование #{scan_count} начато в {current_time.strftime('%H:%M:%S')}")

                # Выполняем сканирование
                signals_found = self._scan_market()

                if signals_found:
                    logger.info(f"✅ Найдено {signals_found} сигналов")
                else:
                    logger.info("✅ Сигналов не обнаружено")

                # Ждём перед следующим сканированием
                time.sleep(1)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле сканирования: {e}")
                time.sleep(5)  # Пауза при ошибке

    def _scan_market(self) -> int:
        """Сканирование рынка и поиск сигналов"""
        # Используем MarketCalendar для проверки времени работы биржи
        is_open, reason = self.market_calendar.is_market_open_now()
        if not is_open:
            logger.info(f"⏰ Биржа закрыта ({reason}), пропускаем сканирование")
            return 0

        signals_found = 0

        for ticker in self.tickers:
            if not self.scanning or not self.is_running:
                break

            try:
                logger.debug(f"📊 Сканируем {ticker}...")

                # Вызываем gRPC сервис для сканирования тикера
                try:
                    import grpc
                    from grpc_service.proto.generated import panicker_pb2, panicker_pb2_grpc

                    # Создаём gRPC канал
                    channel = grpc.insecure_channel(f'localhost:{GRPC_SERVER_PORT}')
                    stub = panicker_pb2_grpc.PanickerServiceStub(channel)

                    # Вызываем метод ScanTicker
                    request = panicker_pb2.ScanTickerRequest(ticker=ticker)
                    response = stub.ScanTicker(request)

                    if response.signal_found:
                        signal_data = {
                            'ticker': ticker,
                            'level': response.level,
                            'signal_type': response.signal_type,
                            'rsi': response.rsi,
                            'volume_ratio': response.volume_ratio,
                            'timestamp': datetime.now().isoformat(),
                            'message': f"{response.level} {response.signal_type} в {ticker}! RSI={response.rsi:.1f}"
                        }
                    else:
                        signal_data = None

                except Exception as e:
                    logger.error(f"❌ Ошибка gRPC сканирования {ticker}: {e}")
                    signal_data = None

                if signal_data:
                    signals_found += 1
                    self._send_alert(signal_data)

                # Пауза между запросами
                time.sleep(self.scan_settings['request_delay'])

            except Exception as e:
                logger.error(f"❌ Ошибка сканирования {ticker}: {e}")

        return signals_found

    def _send_alert(self, signal_data):
        """Отправка оповещения через gRPC"""
        try:
            logger.info(f"🚨 Отправка оповещения: {signal_data['message']}")

            # Отправляем через gRPC
            try:
                import grpc
                from grpc_service.proto.generated import panicker_pb2, panicker_pb2_grpc

                channel = grpc.insecure_channel(f'localhost:{GRPC_SERVER_PORT}')
                stub = panicker_pb2_grpc.SignalsServiceStub(channel)

                # Создаём запрос
                request = panicker_pb2.SendAlertRequest(
                    ticker=signal_data['ticker'],
                    level=signal_data['level'],
                    signal_type=signal_data['signal_type'],
                    message=signal_data['message'],
                    rsi=signal_data['rsi'],
                    volume_ratio=signal_data['volume_ratio']
                )

                response = stub.SendAlert(request)

                if response.success:
                    logger.info(f"📤 Оповещение отправлено через gRPC: {signal_data['ticker']}")
                else:
                    logger.warning(f"⚠️  Оповещение не отправлено: {response.error_message}")

            except Exception as grpc_error:
                logger.error(f"❌ Ошибка gRPC отправки оповещения: {grpc_error}")
                # Логируем как запасной вариант
                logger.info(f"📤 Оповещение залогировано: {signal_data['ticker']} - {signal_data['level']}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки оповещения: {e}")

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ КОМПОНЕНТОВ
    # ------------------------------------------------------------------------
    def _init_components(self):
        """Инициализация компонентов для автосканирования"""
        try:
            # Загружаем конфигурацию
            self.tickers = ConfigLoader.load_tickers()
            self.scan_settings = ConfigLoader.load_scan_settings()

            logger.info(f"📋 Загружено {len(self.tickers)} тикеров для сканирования")
            logger.info(f"⚙️  Настройки сканирования: интервал {self.scan_settings['scan_interval']}с")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации компонентов: {e}")
            # Работаем с тестовыми данными
            self.tickers = ["SBER", "GAZP", "LKOH", "GMKN", "YNDX"]
            self.scan_settings = {
                'scan_interval': SCAN_INTERVAL,
                'cooldown_closed': SCAN_COOLDOWN,
                'request_delay': REQUEST_DELAY,
                'max_retries': 3,
            }

    # ------------------------------------------------------------------------
    # ЗАПУСК КОМПОНЕНТОВ
    # ------------------------------------------------------------------------
    def start_grpc_server(self) -> bool:
        """Запуск gRPC сервера в отдельном процессе"""
        try:
            logger.info("🚀 Запуск gRPC сервера...")

            # Команда для запуска сервера
            cmd = [sys.executable, "grpc_service/grpc_server.py"]

            # Запускаем процесс
            self.grpc_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=False
            )

            # Даём время на запуск
            time.sleep(3)

            # Проверяем, что процесс запущен
            if self.grpc_process.poll() is not None:
                # Процесс завершился
                stdout, _ = self.grpc_process.communicate()
                logger.error(f"❌ gRPC сервер завершился с ошибкой:\n{stdout}")
                return False

            logger.info(f"✅ gRPC сервер запущен (PID: {self.grpc_process.pid})")
            logger.info(f"   📡 Порт: {GRPC_SERVER_PORT}")

            # Читаем вывод в отдельном потоке (упрощённо)
            self._log_process_output(self.grpc_process, "gRPC Server")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска gRPC сервера: {e}")
            return False

    def start_telegram_bot(self) -> bool:
        """Запуск Telegram бота в отдельном процессе"""
        try:
            logger.info("🤖 Запуск Telegram бота...")

            # Команда для запуска бота
            cmd = [sys.executable, "bot/telegram_panicker.py"]

            # Запускаем процесс
            self.bot_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=False
            )

            # Даём время на запуск
            time.sleep(5)

            # Проверяем, что процесс запущен
            if self.bot_process.poll() is not None:
                # Процесс завершился
                try:
                    stdout, _ = self.bot_process.communicate(timeout=1)
                    if stdout:
                        try:
                            decoded_stdout = stdout.decode('utf-8')
                        except UnicodeDecodeError:
                            decoded_stdout = stdout.decode('cp1251', errors='ignore')
                        logger.error(f"❌ Telegram бот завершился с ошибкой:\n{decoded_stdout}")
                    else:
                        logger.error("❌ Telegram бот завершился без вывода")
                except Exception as e:
                    logger.error(f"❌ Ошибка при чтении вывода бота: {e}")
                return False

            logger.info(f"✅ Telegram бот запущен (PID: {self.bot_process.pid})")

            # Читаем вывод в отдельном потоке
            self._log_process_output(self.bot_process, "Telegram Bot")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка запуска Telegram бота: {e}")
            self.bot_process = None  # Гарантируем, что не останется None
            return False

    def _log_process_output(self, process: subprocess.Popen, process_name: str):
        """Чтение вывода процесса в отдельном потоке (упрощённо)"""
        import threading

        def read_output():
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    try:
                        # Пробуем декодировать как UTF-8, если не получается - используем cp1251 для Windows
                        decoded_line = line.decode('utf-8').strip()
                    except UnicodeDecodeError:
                        try:
                            decoded_line = line.decode('cp1251').strip()
                        except:
                            decoded_line = line.decode('utf-8', errors='ignore').strip()

                    if decoded_line:
                        logger.info(f"[{process_name}] {decoded_line}")
            except Exception as e:
                logger.error(f"❌ Ошибка чтения вывода {process_name}: {e}")

        thread = threading.Thread(target=read_output, daemon=True)
        thread.start()

    # ------------------------------------------------------------------------
    # ОСНОВНОЙ ЦИКЛ
    # ------------------------------------------------------------------------
    def run(self):
        """Основной цикл работы системы"""
        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК СИСТЕМЫ «ПАНИКЁР 3000»")
        logger.info("=" * 60)

        self.is_running = True

        try:
            # 1. Проверяем время биржи с помощью MarketCalendar
            is_open, reason = self.market_calendar.is_market_open_now()
            if not is_open:
                logger.warning(f"⏰ Биржа закрыта: {reason}. Запускаем в режиме тестирования...")
                # В тестовом режиме всё равно запускаем
                # В реальной системе здесь можно было бы ждать открытия

            # 2. Запускаем gRPC сервер
            if not self.start_grpc_server():
                logger.error("❌ Не удалось запустить gRPC сервер. Завершение.")
                return

            # 3. Запускаем Telegram бота
            if not self.start_telegram_bot():
                logger.error("❌ Не удалось запустить Telegram бота.")
                # gRPC сервер продолжает работать

            # 4. Запускаем автосканирование - ДОБАВЛЕНО
            logger.info("🔄 Запуск автосканирования...")
            self.start_auto_scanning()

            # 5. Основной цикл мониторинга
            logger.info("✅ Система полностью запущена. Мониторинг компонентов...")

            while self.is_running:
                # Проверяем состояние процессов
                self._check_processes()

                # Проверяем время биржи (только для логирования)
                is_open, reason = self.market_calendar.is_market_open_now()
                if not is_open and self.scanning:
                    logger.info(f"🔴 Биржа закрыта: {reason}. Автосканирование временно приостановлено.")
                    # Сканирование само приостановится в _scan_market()

                # Ждём перед следующей проверкой
                time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            logger.info("\n🛑 Получен сигнал KeyboardInterrupt")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в основном цикле: {e}")
        finally:
            self.cleanup()

    def _check_processes(self):
        """Проверка состояния запущенных процессов"""
        try:
            # Проверяем gRPC сервер
            if self.grpc_process and self.grpc_process.poll() is not None:
                logger.error("❌ gRPC сервер завершился неожиданно")
                # Можно попробовать перезапустить
                # self.start_grpc_server()

            # Проверяем Telegram бота
            if self.bot_process and self.bot_process.poll() is not None:
                logger.error("❌ Telegram бот завершился неожиданно")
                # Попробуем перезапустить
                logger.info("🔄 Перезапуск Telegram бота...")
                self.start_telegram_bot()

        except Exception as e:
            logger.error(f"❌ Ошибка проверки процессов: {e}")

    # ------------------------------------------------------------------------
    # ЗАВЕРШЕНИЕ РАБОТЫ
    # ------------------------------------------------------------------------
    def cleanup(self):
        """Корректное завершение всех компонентов"""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("🧹 Завершение работы системы...")

        # Останавливаем автосканирование - ДОБАВЛЕНО
        if self.scanning:
            logger.info("⏹️  Остановка автосканирования...")
            self.stop_auto_scanning()
            time.sleep(1)  # Даём время на завершение

        # Останавливаем Telegram бота
        if self.bot_process:
            logger.info("🛑 Остановка Telegram бота...")
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=5)
                logger.info("✅ Telegram бот остановлен")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  Telegram бот не ответил на terminate, принудительная остановка")
                self.bot_process.kill()
            except Exception as e:
                logger.error(f"❌ Ошибка остановки Telegram бота: {e}")

        # Останавливаем gRPC сервер
        if self.grpc_process:
            logger.info("🛑 Остановка gRPC сервера...")
            try:
                self.grpc_process.terminate()
                self.grpc_process.wait(timeout=5)
                logger.info("✅ gRPC сервер остановлен")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️  gRPC сервер не ответил на terminate, принудительная остановка")
                self.grpc_process.kill()
            except Exception as e:
                logger.error(f"❌ Ошибка остановки gRPC сервера: {e}")

        logger.info("👋 Система «Паникёр 3000» завершила работу")

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        logger.info(f"📡 Получен сигнал {signum}")
        self.cleanup()
        sys.exit(0)


# ============================================================================
# КОМАНДНАЯ СТРОКА
# ============================================================================
def main():
    """Точка входа для запуска из командной строки"""
    import argparse

    parser = argparse.ArgumentParser(description='Запуск системы Паникёр 3000')
    parser.add_argument(
        '--test',
        action='store_true',
        help='Запуск в тестовом режиме (без проверки времени биржи)'
    )
    parser.add_argument(
        '--only-grpc',
        action='store_true',
        help='Запуск только gRPC сервера'
    )
    parser.add_argument(
        '--only-bot',
        action='store_true',
        help='Запуск только Telegram бота'
    )

    args = parser.parse_args()

    try:
        scanner = PanickerScanner()

        if args.only_grpc:
            logger.info("🚀 Запуск только gRPC сервера...")
            scanner.start_grpc_server()
            # Ждём завершения
            while scanner.grpc_process and scanner.grpc_process.poll() is None:
                time.sleep(1)

        elif args.only_bot:
            logger.info("🤖 Запуск только Telegram бота...")
            scanner.start_telegram_bot()
            # Ждём завершения
            while scanner.bot_process and scanner.bot_process.poll() is None:
                time.sleep(1)

        else:
            # Полный запуск
            scanner.run()

    except KeyboardInterrupt:
        logger.info("\n👋 Завершение по запросу пользователя")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)


# ============================================================================
# ЗАПУСК
# ============================================================================
if __name__ == "__main__":
    main()