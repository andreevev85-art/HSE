# panicker3000/data/data_cache.py
"""
Система кеширования данных.
Кеширует свечи, цены и другие данные на 5 минут для снижения нагрузки на API.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# КОНСТАНТЫ
# ============================================================================
DEFAULT_CACHE_TTL = 300  # 5 минут в секундах
MAX_CACHE_SIZE = 1000  # Максимальное количество записей в кеше


# ============================================================================
# КЛАСС CacheItem
# ============================================================================
@dataclass
class CacheItem:
    """Элемент кеша с данными и временем создания"""
    data: Any
    created_at: datetime
    ttl: int  # Time To Live в секундах

    def is_expired(self) -> bool:
        """Проверка, истёк ли срок жизни кеша"""
        now = datetime.now()
        expiration_time = self.created_at + timedelta(seconds=self.ttl)
        return now > expiration_time

    def time_until_expiry(self) -> float:
        """Сколько секунд осталось до истечения срока жизни"""
        now = datetime.now()
        expiration_time = self.created_at + timedelta(seconds=self.ttl)
        return (expiration_time - now).total_seconds()


# ============================================================================
# КЛАСС CacheKey
# ============================================================================
class CacheKey:
    """Ключ для кеширования (тикер + тип данных + параметры)"""

    def __init__(self, ticker: str, data_type: str, **params):
        self.ticker = ticker
        self.data_type = data_type  # 'candles', 'price', 'instrument_info'
        self.params = params

    def __str__(self) -> str:
        """Строковое представление ключа"""
        params_str = "_".join(f"{k}_{v}" for k, v in sorted(self.params.items()))
        return f"{self.ticker}_{self.data_type}_{params_str}"

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return str(self) == str(other)


# ============================================================================
# КЛАСС DataCache
# ============================================================================
class DataCache:
    """Менеджер кеширования данных"""

    # ------------------------------------------------------------------------
    # ИНИЦИАЛИЗАЦИЯ
    # ------------------------------------------------------------------------
    def __init__(self, default_ttl: int = DEFAULT_CACHE_TTL):
        """
        Инициализация кеша

        Args:
            default_ttl: Время жизни кеша по умолчанию (секунды)
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheItem] = {}
        self._lock = asyncio.Lock()
        logger.info(f"DataCache инициализирован (TTL={default_ttl}с)")

    # ------------------------------------------------------------------------
    # ОСНОВНЫЕ МЕТОДЫ: GET
    # ------------------------------------------------------------------------
    async def get(self, key: Union[str, CacheKey]) -> Optional[Any]:
        """
        Получить данные из кеша

        Args:
            key: Ключ кеша

        Returns:
            Данные или None если нет в кеше или истёк срок
        """
        cache_key = str(key) if isinstance(key, CacheKey) else key

        async with self._lock:
            if cache_key not in self._cache:
                logger.debug(f"Кеш MISS: {cache_key}")
                return None

            item = self._cache[cache_key]

            if item.is_expired():
                # Удаляем просроченный элемент
                del self._cache[cache_key]
                logger.debug(f"Кеш EXPIRED: {cache_key}")
                return None

            # Обновляем время последнего доступа
            logger.debug(f"Кеш HIT: {cache_key}")
            return item.data

    # ------------------------------------------------------------------------
    # ОСНОВНЫЕ МЕТОДЫ: SET
    # ------------------------------------------------------------------------
    async def set(self, key: Union[str, CacheKey], data: Any, ttl: Optional[int] = None):
        """
        Сохранить данные в кеш

        Args:
            key: Ключ кеша
            data: Данные для кеширования
            ttl: Время жизни в секундах (если None - используется default_ttl)
        """
        cache_key = str(key) if isinstance(key, CacheKey) else key
        ttl = ttl or self.default_ttl

        async with self._lock:
            # Проверяем размер кеша
            if len(self._cache) >= MAX_CACHE_SIZE:
                await self._cleanup_oldest()

            # Сохраняем данные
            self._cache[cache_key] = CacheItem(
                data=data,
                created_at=datetime.now(),
                ttl=ttl
            )

            logger.debug(f"Кеш SET: {cache_key} (TTL={ttl}с)")

    # ------------------------------------------------------------------------
    # ОСНОВНЫЕ МЕТОДЫ: DELETE
    # ------------------------------------------------------------------------
    async def delete(self, key: Union[str, CacheKey]) -> bool:
        """
        Удалить данные из кеша

        Args:
            key: Ключ кеша

        Returns:
            True если данные были удалены, False если их не было
        """
        cache_key = str(key) if isinstance(key, CacheKey) else key

        async with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.debug(f"Кеш DELETE: {cache_key}")
                return True
            return False

    # ------------------------------------------------------------------------
    # ОСНОВНЫЕ МЕТОДЫ: CLEAR
    # ------------------------------------------------------------------------
    async def clear(self):
        """Очистить весь кеш"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Кеш CLEAR: удалено {count} записей")

    # ------------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------------
    async def _cleanup_oldest(self):
        """Удалить самые старые записи при превышении лимита"""
        if not self._cache:
            return

        # Сортируем по времени создания (самые старые сначала)
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1].created_at
        )

        # Удаляем 10% самых старых записей
        to_remove = max(1, len(sorted_items) // 10)

        for i in range(to_remove):
            key, _ = sorted_items[i]
            del self._cache[key]

        logger.debug(f"Кеш CLEANUP: удалено {to_remove} старых записей")

    async def cleanup_expired(self):
        """Очистить все просроченные записи"""
        async with self._lock:
            expired_keys = [
                key for key, item in self._cache.items()
                if item.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"Кеш CLEANUP_EXPIRED: удалено {len(expired_keys)} записей")

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кеша"""
        now = datetime.now()
        expired_count = 0
        total_size = 0

        # Подсчитываем размер данных (приблизительно)
        for item in self._cache.values():
            if item.is_expired():
                expired_count += 1
            # Простая оценка размера
            total_size += len(str(item.data)) if item.data else 0

        return {
            'total_items': len(self._cache),
            'expired_items': expired_count,
            'cache_size_bytes': total_size,
            'max_size': MAX_CACHE_SIZE,
            'default_ttl': self.default_ttl
        }

    # ------------------------------------------------------------------------
    # СПЕЦИАЛИЗИРОВАННЫЕ МЕТОДЫ (для удобства)
    # ------------------------------------------------------------------------
    async def get_candles(self, ticker: str, interval: str, days_back: int) -> Optional[List]:
        """
        Получить свечи из кеша

        Args:
            ticker: Тикер акции
            interval: Интервал свечей ('min1', 'min5', 'hour', 'day')
            days_back: Количество дней истории

        Returns:
            Список свечей или None
        """
        key = CacheKey(ticker, 'candles', interval=interval, days_back=days_back)
        return await self.get(key)

    async def set_candles(self, ticker: str, interval: str, days_back: int, candles: List):
        """
        Сохранить свечи в кеш

        Args:
            ticker: Тикер акции
            interval: Интервал свечей
            days_back: Количество дней истории
            candles: Список свечей
        """
        key = CacheKey(ticker, 'candles', interval=interval, days_back=days_back)
        await self.set(key, candles)

    async def get_price(self, ticker: str) -> Optional[float]:
        """
        Получить цену из кеша

        Args:
            ticker: Тикер акции

        Returns:
            Цена или None
        """
        key = CacheKey(ticker, 'price')
        return await self.get(key)

    async def set_price(self, ticker: str, price: float, ttl: int = 60):
        """
        Сохранить цену в кеш (короткий TTL)

        Args:
            ticker: Тикер акции
            price: Цена
            ttl: Время жизни (по умолчанию 60 секунд)
        """
        key = CacheKey(ticker, 'price')
        await self.set(key, price, ttl)


# ============================================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР КЕША
# ============================================================================
# Создаём глобальный экземпляр для использования во всём приложении
_cache_instance: Optional[DataCache] = None


def get_cache() -> DataCache:
    """Получить глобальный экземпляр кеша (синглтон)"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DataCache()
    return _cache_instance


async def clear_global_cache():
    """Очистить глобальный кеш"""
    global _cache_instance
    if _cache_instance:
        await _cache_instance.clear()