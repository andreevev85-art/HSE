#!/usr/bin/env python3
# test_tinkoff_client.py
import sys
import os
import logging

# Добавляем корень проекта в путь
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from panicker3000.data.tinkoff_client import TinkoffClient

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_connection(client):
    """Тест подключения к API"""
    print("=" * 60)
    print("🔌 ТЕСТ ПОДКЛЮЧЕНИЯ К API")
    print("=" * 60)

    success = client.test_connection()
    if success:
        print("✅ Подключение к API успешно установлено")
    else:
        print("❌ Не удалось подключиться к API")
        print("   Проверьте токен API в переменной окружения TINKOFF_API_TOKEN")
        print("   Убедитесь, что установлен пакет: pip install t-tech-investments")

    return success


def test_instrument_info(client):
    """Тест получения информации об инструменте"""
    print("\n" + "=" * 60)
    print("📊 ТЕСТ ПОЛУЧЕНИЯ ИНФОРМАЦИИ ОБ ИНСТРУМЕНТЕ")
    print("=" * 60)

    ticker = "SBER"
    print(f"🔍 Поиск информации для тикера: {ticker}")

    info = client.get_instrument_info(ticker)
    if info:
        print(f"✅ Найдена информация по {ticker}:")
        print(f"   Название: {info.get('name', 'N/A')}")
        print(f"   FIGI: {info.get('figi', 'N/A')}")
        print(f"   Лот: {info.get('lot', 'N/A')}")
        print(f"   Валюта: {info.get('currency', 'N/A')}")
        return True
    else:
        print(f"❌ Не удалось получить информацию по {ticker}")
        return False


def test_candles(client):
    """Тест получения свечей"""
    print("\n" + "=" * 60)
    print("📈 ТЕСТ ПОЛУЧЕНИЯ СВЕЧЕЙ")
    print("=" * 60)

    ticker = "SBER"
    print(f"📊 Запрос свечей для: {ticker}")

    try:
        candles = client.get_candles(ticker, interval='hour', count=5)
        if candles:
            print(f"✅ Получено {len(candles)} свечей:")
            for i, candle in enumerate(candles[-3:]):  # Показываем последние 3
                print(f"   Свеча {i + 1}: {candle['time']} - Цена закрытия: {candle['close']:.2f}")
            return True
        else:
            print(f"❌ Не удалось получить свечи для {ticker}")
            return False
    except Exception as e:
        print(f"❌ Ошибка при получении свечей: {e}")
        return False


def test_last_price(client):
    """Тест получения последней цены"""
    print("\n" + "=" * 60)
    print("💰 ТЕСТ ПОЛУЧЕНИЯ ПОСЛЕДНЕЙ ЦЕНЫ")
    print("=" * 60)

    ticker = "SBER"
    print(f"💸 Запрос последней цены для: {ticker}")

    price = client.get_last_price(ticker)
    if price:
        print(f"✅ Последняя цена {ticker}: {price:.2f}")
        return True
    else:
        print(f"❌ Не удалось получить цену для {ticker}")
        return False


def test_available_shares(client):
    """Тест получения списка акций"""
    print("\n" + "=" * 60)
    print("📋 ТЕСТ ПОЛУЧЕНИЯ СПИСКА АКЦИЙ")
    print("=" * 60)

    print("📊 Запрос списка акций MOEX...")

    shares = client.get_available_shares(exchange='MOEX')
    if shares:
        print(f"✅ Получено {len(shares)} акций MOEX")
        print("   Примеры акций:")
        for i, share in enumerate(shares[:5]):  # Показываем первые 5
            print(f"   {i + 1}. {share['ticker']} - {share['name']}")
        return True
    else:
        print("❌ Не удалось получить список акций")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 ЗАПУСК ТЕСТОВ TINKOFF API CLIENT")
    print("=" * 60)

    # Создаем клиент
    try:
        client = TinkoffClient()
        print("✅ Клиент создан успешно")
    except Exception as e:
        print(f"❌ Ошибка при создании клиента: {e}")
        print("   Убедитесь, что:")
        print("   1. Установлен пакет: pip install t-tech-investments")
        print("   2. Установлен токен API: export TINKOFF_API_TOKEN='ваш_токен'")
        return 1

    # Запускаем тесты
    tests = [
        test_connection,
        test_instrument_info,
        test_candles,
        test_last_price,
        test_available_shares
    ]

    results = []
    for test in tests:
        try:
            result = test(client)
            results.append(result)
        except Exception as e:
            print(f"❌ Ошибка в тесте {test.__name__}: {e}")
            results.append(False)

    # Выводим итог
    print("\n" + "=" * 60)
    print("📊 ИТОГ ТЕСТИРОВАНИЯ")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"✅ Пройдено тестов: {passed} из {total}")

    if passed == total:
        print("🎉 Все тесты пройдены успешно! Клиент готов к работе.")
        return 0
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте настройки.")
        return 1


if __name__ == "__main__":
    sys.exit(main())