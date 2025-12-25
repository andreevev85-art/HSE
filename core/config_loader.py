"""
Модуль загрузки конфигурации для Паникёра 3000.
Загружает настройки из YAML файлов с использованием ruamel.yaml.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from ruamel.yaml import YAML

# ============================================================================
# НАСТРОЙКА ЛОГГИРОВАНИЯ
# ============================================================================
logger = logging.getLogger(__name__)
yaml = YAML()


# ============================================================================
# КЛАСС ConfigLoader
# ============================================================================
class ConfigLoader:
    """
    Загрузчик конфигурации из YAML файлов.
    Обеспечивает доступ к настройкам проекта.
    """

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, config_path: Optional[str] = None):
        """
        Инициализация загрузчика конфигурации.

        Args:
            config_path: Путь к директории с конфигами. Если None - используется config/ в корне проекта.
        """
        self._setup_logging()
        self.config_dir = self._get_config_dir(config_path)
        self.settings = {}
        self.tickers = {}
        self.panic_thresholds = {}

        self._load_all_configs()
        logger.info("ConfigLoader инициализирован")

    # ------------------------------------------------------------------------
    # НАСТРОЙКА ЛОГГИРОВАНИЯ
    # ------------------------------------------------------------------------
    def _setup_logging(self):
        """Настройка логирования для модуля"""
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

    # ------------------------------------------------------------------------
    # ПОЛУЧЕНИЕ ПУТИ К КОНФИГАМ
    # ------------------------------------------------------------------------
    def _get_config_dir(self, config_path: Optional[str]) -> Path:
        """
        Определение директории с конфигурационными файлами.

        Returns:
            Path: Путь к директории с конфигами
        """
        if config_path:
            path = Path(config_path)
        else:
            # Определяем путь относительно текущего файла
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent
            path = project_root / "config"

        # Создаём директорию, если её нет
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Директория конфигов: {path}")

        return path

    # ------------------------------------------------------------------------
    # ЗАГРУЗКА ВСЕХ КОНФИГОВ
    # ------------------------------------------------------------------------
    def _load_all_configs(self):
        """Загрузка всех конфигурационных файлов"""
        try:
            self.settings = self._load_config_file("settings.yaml", self._get_default_settings())
            self.tickers = self._load_config_file("tickers.yaml", self._get_default_tickers())
            self.panic_thresholds = self._load_config_file("panic_thresholds.yaml",
                                                           self._get_default_panic_thresholds())
            self._telegram_commands = self._load_config_file("telegram_commands.yaml", {})
            logger.info("Все конфигурационные файлы загружены")

        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            raise

    def _load_all_configs(self):
        """Загрузка всех конфигурационных файлов"""
        try:
            self.settings = self._load_config_file("settings.yaml", self._get_default_settings())
            self.tickers = self._load_config_file("tickers.yaml", self._get_default_tickers())
            self.panic_thresholds = self._load_config_file("panic_thresholds.yaml",
                                                           self._get_default_panic_thresholds())
            self._telegram_commands = self._load_config_file("telegram_commands.yaml", {})

            logger.info("Все конфигурационные файлы загружены")

        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            raise

    # ------------------------------------------------------------------------
    # ЗАГРУЗКА КОНФИГУРАЦИОННОГО ФАЙЛА
    # ------------------------------------------------------------------------
    def _load_config_file(self, filename: str, default_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Загрузка конфигурационного файла.
        Если файл не существует, создаётся с дефолтными значениями.

        Args:
            filename: Имя файла конфигурации
            default_config: Дефолтная конфигурация

        Returns:
            Dict[str, Any]: Загруженная конфигурация
        """
        filepath = self.config_dir / filename

        if not filepath.exists():
            logger.warning(f"Файл {filename} не найден, создаём с дефолтными значениями")
            self._save_config_file(filepath, default_config)
            return default_config

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = yaml.load(f)

            if not config:
                logger.warning(f"Файл {filename} пуст, используем дефолтные значения")
                return default_config

            logger.info(f"Файл {filename} успешно загружен")
            return config

        except Exception as e:
            logger.error(f"Ошибка загрузки файла {filename}: {e}")
            return default_config

    # ------------------------------------------------------------------------
    # СОХРАНЕНИЕ КОНФИГУРАЦИОННОГО ФАЙЛА
    # ------------------------------------------------------------------------
    def _save_config_file(self, filepath: Path, config: Dict[str, Any]):
        """
        Сохранение конфигурации в файл.

        Args:
            filepath: Путь к файлу
            config: Конфигурация для сохранения
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(config, f)

            logger.info(f"Файл {filepath.name} сохранён с дефолтными значениями")

        except Exception as e:
            logger.error(f"Ошибка сохранения файла {filepath.name}: {e}")
            raise

    # ------------------------------------------------------------------------
    # ДЕФОЛТНЫЕ КОНФИГУРАЦИИ
    # ------------------------------------------------------------------------
    def _get_default_settings(self) -> Dict[str, Any]:
        """Дефолтные настройки проекта"""
        return {
            "telegram": {
                "token": "${TELEGRAM_TOKEN}",
                "alert_cooldown": 7200,
                "daily_report_time": "18:30"
            },
            "tinkoff": {
                "token": "${TINKOFF_API_TOKEN}",
                "sandbox": False,
                "request_timeout": 10,
                "retry_attempts": 3
            },
            "scanning": {
                "interval_minutes": 5,
                "market_hours": {
                    "start": "10:00",
                    "end": "18:30"
                }
            }
        }

    def _get_default_tickers(self) -> Dict[str, Any]:
        """Дефолтный список тикеров"""
        return {
            "tickers": [
                "SBER",
                "GAZP",
                "LKOH",
                "GMKN",
                "YNDX",
                "ROSN",
                "TATN",
                "NVTK",
                "MTSS",
                "MOEX"
            ],
            "parameters": {
                "candle_interval": "1min",
                "history_days": 30
            }
        }

    def _get_default_panic_thresholds(self) -> Dict[str, Any]:
        """Дефолтные пороги для обнаружения паники"""
        return {
            "panic_thresholds": {
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

    # ------------------------------------------------------------------------
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Получение значения настройки.

        Args:
            key: Ключ настройки (например, 'telegram.token')
            default: Значение по умолчанию, если ключ не найден

        Returns:
            Any: Значение настройки
        """
        try:
            keys = key.split('.')
            value = self.settings

            for k in keys:
                value = value[k]

            return value
        except (KeyError, TypeError):
            logger.debug(f"Настройка '{key}' не найдена, возвращаем дефолт: {default}")
            return default

    def get_tickers(self) -> list:
        """Получение списка тикеров"""
        return self.tickers.get("tickers", [])

    def get_panic_threshold(self, level: str, threshold_type: str) -> Any:
        """
        Получение порога для определённого уровня паники.

        Args:
            level: Уровень паники ('red', 'yellow', 'white')
            threshold_type: Тип порога ('rsi_buy', 'rsi_sell', 'volume_min')

        Returns:
            Any: Значение порога
        """
        try:
            thresholds = self.panic_thresholds.get("panic_thresholds", {})
            level_thresholds = thresholds.get(level, {})
            return level_thresholds.get(threshold_type)
        except KeyError:
            logger.warning(f"Порог не найден: level={level}, type={threshold_type}")
            return None

    # ------------------------------------------------------------------------
    # МЕТОДЫ ЗАГРУЗКИ КОНФИГОВ
    # ------------------------------------------------------------------------
    def load_panic_thresholds(self) -> Dict[str, Any]:
        """
        Загрузка пороговых значений для паники.

        Returns:
            Dict[str, Any]: Пороговые значения из panic_thresholds.yaml
        """
        return self.panic_thresholds

    def load_telegram_commands(self) -> Dict[str, Any]:
        """
        Загрузка команд Telegram из telegram_commands.yaml

        Returns:
            Dict[str, Any]: Команды Telegram
        """
        if hasattr(self, '_telegram_commands'):
            return self._telegram_commands
        return {}

    def load_settings(self) -> Dict[str, Any]:
        """
        Загрузка основных настроек.

        Returns:
            Dict[str, Any]: Основные настройки из settings.yaml
        """
        return self.settings

    def load_tickers(self) -> Dict[str, Any]:
        """
        Загрузка списка тикеров.

        Returns:
            Dict[str, Any]: Список тикеров из tickers.yaml
        """
        return self.tickers

# ============================================================================
# ФУНКЦИИ ДЛЯ УДОБСТВА
# ============================================================================
def get_config() -> ConfigLoader:
    """
    Функция для получения экземпляра ConfigLoader.

    Returns:
        ConfigLoader: Экземпляр загрузчика конфигурации
    """
    return ConfigLoader()