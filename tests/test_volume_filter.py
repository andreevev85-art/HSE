# panicker3000/tests/test_volume_filter.py
"""
Тесты для фильтра объёма.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.filters.volume_filter import VolumeFilter


# ============================================================================
# ТЕСТ 1: ИНИЦИАЛИЗАЦИЯ
# ============================================================================
def test_volume_filter_initialization():
    """Тест инициализации фильтра"""
    print("🧪 Тест 1: Инициализация VolumeFilter")

    # С параметрами по умолчанию
    filter_default = VolumeFilter()

    # С кастомными параметрами
    custom_config = {
        'min_volume_ratio': 2.0,
        'use_forecast': False
    }
    filter_custom = VolumeFilter(custom_config)

    assert filter_default.min_volume_ratio == 1.5
    assert filter_custom.min_volume_ratio == 2.0
    assert filter_custom.use_forecast == False

    print(f"✅ По умолчанию: ratio={filter_default.min_volume_ratio}")
    print(f"✅ Кастомный: ratio={filter_custom.min_volume_ratio}")
    return True


# ============================================================================
# ТЕСТ 2: УСПЕШНАЯ ПРОВЕРКА (ОБЪЁМ ДОСТАТОЧНЫЙ)
# ============================================================================
def test_check_sufficient_volume():
    """Тест проверки с достаточным объёмом"""
    print("\n🧪 Тест 2: Проверка с достаточным объёмом")

    filter_obj = VolumeFilter({'min_volume_ratio': 1.5})

    # Устанавливаем тестовый средний объём для SBER
    filter_obj.set_average_volume('SBER', 100_000_000)  # 100 млн

    # Текущий объём 200 млн (коэффициент 2.0)
    signal_data = {
        'ticker': 'SBER',
        'current_volume': 200_000_000
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == True
    assert "2.0×" in message
    print(f"✅ Достаточный объём: {message}")
    return True


# ============================================================================
# ТЕСТ 3: НЕУДАЧНАЯ ПРОВЕРКА (ОБЪЁМ НЕДОСТАТОЧНЫЙ)
# ============================================================================
def test_check_insufficient_volume():
    """Тест проверки с недостаточным объёмом"""
    print("\n🧪 Тест 3: Проверка с недостаточным объёмом")

    filter_obj = VolumeFilter({'min_volume_ratio': 1.5})
    filter_obj.set_average_volume('GAZP', 100_000_000)

    # Текущий объём 120 млн (коэффициент 1.2)
    signal_data = {
        'ticker': 'GAZP',
        'current_volume': 120_000_000
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == False
    assert "недостаточен" in message or "1.2×" in message
    print(f"✅ Недостаточный объём: {message}")
    return True


# ============================================================================
# ТЕСТ 4: ПРОВЕРКА БЕЗ ДАННЫХ
# ============================================================================
def test_check_without_data():
    """Тест проверки без необходимых данных"""
    print("\n🧪 Тест 4: Проверка без данных")

    filter_obj = VolumeFilter()

    # Без тикера
    signal_no_ticker = {'current_volume': 100_000_000}
    passed1, msg1 = filter_obj.check(signal_no_ticker)
    assert passed1 == False
    assert "тикер" in msg1.lower()
    print(f"✅ Без тикера: {msg1}")

    # Без объёма
    signal_no_volume = {'ticker': 'SBER'}
    passed2, msg2 = filter_obj.check(signal_no_volume)
    assert passed2 == False
    assert "объём" in msg2.lower()
    print(f"✅ Без объёма: {msg2}")

    return True


# ============================================================================
# ТЕСТ 5: ИСТОРИЧЕСКИЕ ДАННЫЕ
# ============================================================================
def test_check_with_historical_data():
    """Тест проверки с историческими данными в signal_data"""
    print("\n🧪 Тест 5: Проверка с историческими данными")

    filter_obj = VolumeFilter({'min_volume_ratio': 1.5})

    # Сигнал с историческими объёмами (среднее = 150)
    signal_data = {
        'ticker': 'LKOH',
        'current_volume': 300_000_000,  # 300 млн
        'historical_volumes': [
            100_000_000,  # 100 млн
            150_000_000,  # 150 млн
            200_000_000  # 200 млн
        ]
    }

    passed, message = filter_obj.check(signal_data)

    # Среднее из historical_volumes = 150 млн
    # Коэффициент = 300 / 150 = 2.0
    assert passed == True
    assert "2.0×" in message
    print(f"✅ С историческими данными: {message}")
    return True


# ============================================================================
# ТЕСТ 6: ПРОГНОЗ ОБЪЁМА
# ============================================================================
def test_volume_forecast():
    """Тест прогноза объёма на день"""
    print("\n🧪 Тест 6: Прогноз объёма")

    filter_obj = VolumeFilter({'use_forecast': True})
    filter_obj.set_average_volume('SBER', 100_000_000)

    forecast = filter_obj.get_volume_forecast('SBER')

    # Прогноз должен быть не None и положительным
    assert forecast is not None
    assert forecast > 0

    print(f"✅ Прогноз объёма SBER: {forecast:,.0f} руб")
    return True


# ============================================================================
# ЗАПУСК ВСЕХ ТЕСТОВ
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ VOLUME FILTER")
    print("=" * 60)

    test_results = []

    tests = [
        test_volume_filter_initialization,
        test_check_sufficient_volume,
        test_check_insufficient_volume,
        test_check_without_data,
        test_check_with_historical_data,
        test_volume_forecast
    ]

    for test_func in tests:
        try:
            result = test_func()
            test_results.append(result)
        except Exception as e:
            print(f"❌ Ошибка в тесте {test_func.__name__}: {e}")
            test_results.append(False)

    # Итог
    print("\n" + "=" * 60)
    all_passed = all(test_results)

    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ VOLUME FILTER ПРОЙДЕНЫ УСПЕШНО!")
        sys.exit(0)
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ VOLUME FILTER НЕ ПРОЙДЕНЫ")
        sys.exit(1)