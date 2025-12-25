# panicker3000/tests/test_data_cache.py
"""
Тесты для системы кеширования данных.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import sys
import os
import asyncio
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.data_cache import DataCache, CacheKey, CacheItem, get_cache


# ============================================================================
# ТЕСТ 1: КЛАСС CacheItem
# ============================================================================
def test_cache_item_creation_and_expiry():
    """Тест создания CacheItem и проверки срока жизни"""
    print("🧪 Тест 1: CacheItem создание и срок жизни")

    # Создаём элемент кеша с TTL 1 секунда
    item = CacheItem(
        data="test_data",
        created_at=datetime.now() - timedelta(seconds=2),  # 2 секунды назад
        ttl=1  # TTL 1 секунда
    )

    # Должен быть просрочен
    assert item.is_expired() == True
    print("✅ Элемент корректно помечен как просроченный")

    # Создаём элемент с будущим TTL
    item2 = CacheItem(
        data="test_data_fresh",
        created_at=datetime.now(),
        ttl=60  # 60 секунд
    )

    # Не должен быть просрочен
    assert item2.is_expired() == False
    print("✅ Свежий элемент не просрочен")

    return True


# ============================================================================
# ТЕСТ 2: КЛАСС CacheKey
# ============================================================================
def test_cache_key_creation():
    """Тест создания CacheKey"""
    print("\n🧪 Тест 2: CacheKey создание")

    # Простой ключ
    key1 = CacheKey("SBER", "candles")
    assert str(key1) == "SBER_candles_"
    print(f"✅ Простой ключ: {key1}")

    # Ключ с параметрами
    key2 = CacheKey("GAZP", "candles", interval="min5", days_back=30)
    expected_str = "GAZP_candles_days_back_30_interval_min5"
    assert str(key2) == expected_str
    print(f"✅ Ключ с параметрами: {key2}")

    # Проверка хэширования
    key3 = CacheKey("SBER", "candles", interval="min5")
    key4 = CacheKey("SBER", "candles", interval="min5")
    assert key3 == key4
    assert hash(key3) == hash(key4)
    print("✅ Хэширование и сравнение работают")

    return True


# ============================================================================
# ТЕСТ 3: ОСНОВНЫЕ ОПЕРАЦИИ КЕША
# ============================================================================
@pytest.mark.asyncio
async def test_cache_basic_operations():
    """Тест основных операций кеша (set/get/delete)"""
    print("\n🧪 Тест 3: Основные операции кеша")

    cache = DataCache(default_ttl=2)  # Короткий TTL для тестов

    # 1. Тест set и get
    await cache.set("test_key", "test_value")
    value = await cache.get("test_key")
    assert value == "test_value"
    print("✅ SET/GET работают")

    # 2. Тест get несуществующего ключа
    missing = await cache.get("non_existent")
    assert missing is None
    print("✅ GET несуществующего ключа возвращает None")

    # 3. Тест delete
    await cache.set("to_delete", "data")
    assert await cache.get("to_delete") == "data"

    deleted = await cache.delete("to_delete")
    assert deleted == True
    assert await cache.get("to_delete") is None
    print("✅ DELETE работает")

    # 4. Тест delete несуществующего ключа
    not_deleted = await cache.delete("non_existent")
    assert not_deleted == False
    print("✅ DELETE несуществующего ключа возвращает False")

    return True


# ============================================================================
# ТЕСТ 4: ИСТЕЧЕНИЕ СРОКА ЖИЗНИ
# ============================================================================
@pytest.mark.asyncio
async def test_cache_expiration():
    """Тест истечения срока жизни кеша"""
    print("\n🧪 Тест 4: Истечение срока жизни кеша")

    cache = DataCache(default_ttl=1)  # Очень короткий TTL

    # Сохраняем данные
    await cache.set("expiring_key", "expiring_value")

    # Сразу должны получить данные
    value1 = await cache.get("expiring_key")
    assert value1 == "expiring_value"
    print("✅ Данные доступны сразу после сохранения")

    # Ждём 1.5 секунды (больше чем TTL)
    await asyncio.sleep(1.5)

    # Теперь данные должны быть просрочены
    value2 = await cache.get("expiring_key")
    assert value2 is None
    print("✅ Данные удалены после истечения TTL")

    return True


# ============================================================================
# ТЕСТ 5: СПЕЦИАЛИЗИРОВАННЫЕ МЕТОДЫ
# ============================================================================
@pytest.mark.asyncio
async def test_cache_specialized_methods():
    """Тест специализированных методов (get_candles, set_candles, etc.)"""
    print("\n🧪 Тест 5: Специализированные методы")

    cache = DataCache(default_ttl=10)

    # Тест методов для свечей
    test_candles = [{"time": "2024-01-01", "open": 100, "close": 105}]

    await cache.set_candles("SBER", "min5", 30, test_candles)

    retrieved = await cache.get_candles("SBER", "min5", 30)
    assert retrieved == test_candles
    print("✅ set_candles/get_candles работают")

    # Тест методов для цены
    await cache.set_price("GAZP", 250.5, ttl=5)

    price = await cache.get_price("GAZP")
    assert price == 250.5
    print("✅ set_price/get_price работают")

    return True


# ============================================================================
# ТЕСТ 6: ГЛОБАЛЬНЫЙ КЕШ
# ============================================================================
def test_global_cache_singleton():
    """Тест глобального кеша (синглтон)"""
    print("\n🧪 Тест 6: Глобальный кеш")

    cache1 = get_cache()
    cache2 = get_cache()

    # Оба вызова должны возвращать один и тот же объект
    assert cache1 is cache2
    print("✅ get_cache возвращает один и тот же экземпляр (синглтон)")

    return True


# ============================================================================
# ТЕСТ 7: СТАТИСТИКА КЕША
# ============================================================================
@pytest.mark.asyncio
async def test_cache_statistics():
    """Тест получения статистики кеша"""
    print("\n🧪 Тест 7: Статистика кеша")

    cache = DataCache(default_ttl=10)

    # Добавляем несколько записей
    for i in range(5):
        await cache.set(f"key_{i}", f"value_{i}")

    stats = cache.get_stats()

    assert stats['total_items'] == 5
    assert stats['max_size'] == 1000  # Из констант
    assert stats['default_ttl'] == 10
    print(f"✅ Статистика: {stats}")

    return True


# ============================================================================
# ЗАПУСК ВСЕХ ТЕСТОВ
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ DATA CACHE")
    print("=" * 60)

    # Запуск синхронных тестов
    test_results = []

    try:
        test_results.append(test_cache_item_creation_and_expiry())
        test_results.append(test_cache_key_creation())
        test_results.append(test_global_cache_singleton())
    except Exception as e:
        print(f"❌ Ошибка в синхронных тестах: {e}")
        test_results.append(False)

    # Запуск асинхронных тестов
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async_tests = [
        test_cache_basic_operations,
        test_cache_expiration,
        test_cache_specialized_methods,
        test_cache_statistics
    ]

    for async_test in async_tests:
        try:
            result = loop.run_until_complete(async_test())
            test_results.append(result)
        except Exception as e:
            print(f"❌ Ошибка в асинхронном тесте: {e}")
            test_results.append(False)

    # Итог
    print("\n" + "=" * 60)
    all_passed = all(test_results)

    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ DATA CACHE ПРОЙДЕНЫ УСПЕШНО!")
        sys.exit(0)
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ DATA CACHE НЕ ПРОЙДЕНЫ")
        sys.exit(1)