# panicker3000/tests/test_volatility_filter.py
"""
Тесты для фильтра волатильности (ATR).
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.filters.volatility_filter import VolatilityFilter


# ============================================================================
# ТЕСТ 1: ИНИЦИАЛИЗАЦИЯ
# ============================================================================
def test_volatility_filter_initialization():
    """Тест инициализации фильтра"""
    print("🧪 Тест 1: Инициализация VolatilityFilter")

    # С параметрами по умолчанию
    filter_default = VolatilityFilter()

    # С кастомными параметрами
    custom_config = {
        'min_atr_ratio': 1.0,
        'min_absolute_atr': 1.0,
        'period': 20
    }
    filter_custom = VolatilityFilter(custom_config)

    assert filter_default.min_atr_ratio == 0.8
    assert filter_default.min_absolute_atr == 0.5
    assert filter_custom.min_atr_ratio == 1.0
    assert filter_custom.min_absolute_atr == 1.0
    assert filter_custom.period == 20

    print(f"✅ По умолчанию: ratio={filter_default.min_atr_ratio}, abs={filter_default.min_absolute_atr}%")
    print(f"✅ Кастомный: ratio={filter_custom.min_atr_ratio}, abs={filter_custom.min_absolute_atr}%")
    return True


# ============================================================================
# ТЕСТ 2: УСПЕШНАЯ ПРОВЕРКА (ВОЛАТИЛЬНОСТЬ ДОСТАТОЧНА)
# ============================================================================
def test_check_sufficient_volatility():
    """Тест проверки с достаточной волатильностью"""
    print("\n🧪 Тест 2: Проверка с достаточной волатильностью")

    filter_obj = VolatilityFilter({'min_atr_ratio': 0.8})

    # Текущий ATR = 10, средний ATR = 10, коэффициент = 1.0
    signal_data = {
        'ticker': 'SBER',
        'current_atr': 10.0,
        'average_atr': 10.0,
        'price': 300.0
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == True
    assert "достаточна" in message or "1.0×" in message
    print(f"✅ Достаточная волатильность: {message}")
    return True


# ============================================================================
# ТЕСТ 3: НЕУДАЧНАЯ ПРОВЕРКА (ВОЛАТИЛЬНОСТЬ НИЗКАЯ)
# ============================================================================
def test_check_low_volatility():
    """Тест проверки с низкой волатильностью"""
    print("\n🧪 Тест 3: Проверка с низкой волатильностью")

    filter_obj = VolatilityFilter({'min_atr_ratio': 0.8})

    # Текущий ATR = 5, средний ATR = 10, коэффициент = 0.5
    signal_data = {
        'ticker': 'GAZP',
        'current_atr': 5.0,
        'average_atr': 10.0,
        'price': 200.0
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == False
    assert "низкая" in message.lower() or "0.5×" in message
    print(f"✅ Низкая волатильность: {message}")
    return True


# ============================================================================
# ТЕСТ 4: АБСОЛЮТНАЯ ПРОВЕРКА ATR
# ============================================================================
def test_absolute_atr_check():
    """Тест абсолютной проверки ATR (в процентах от цены)"""
    print("\n🧪 Тест 4: Абсолютная проверка ATR")

    filter_obj = VolatilityFilter({'min_absolute_atr': 1.0})  # Минимум 1%

    # ATR = 2, цена = 300, ATR% = 0.67% < 1%
    signal_data = {
        'ticker': 'LKOH',
        'current_atr': 2.0,
        'average_atr': 3.0,
        'price': 300.0
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == False
    assert "слишком мал" in message or "0.67%" in message
    print(f"✅ Абсолютный ATR проверен: {message}")
    return True


# ============================================================================
# ТЕСТ 5: РАСЧЁТ ATR
# ============================================================================
def test_atr_calculation():
    """Тест расчёта Average True Range"""
    print("\n🧪 Тест 5: Расчёт ATR")

    filter_obj = VolatilityFilter()

    # Тестовые данные (простой случай)
    highs = [100, 105, 103, 108, 107]
    lows = [95, 98, 97, 101, 102]
    closes = [98, 102, 101, 106, 105]

    atr = filter_obj.calculate_atr(highs, lows, closes, period=3)

    # Ожидаем положительное значение
    assert atr is not None
    assert atr > 0

    print(f"✅ ATR рассчитан: {atr:.2f}")
    return True


# ============================================================================
# ТЕСТ 6: АНАЛИЗ ВОЛАТИЛЬНОСТИ
# ============================================================================
def test_volatility_analysis():
    """Тест анализа волатильности"""
    print("\n🧪 Тест 6: Анализ волатильности")

    filter_obj = VolatilityFilter({'period': 5})

    # Тестовые исторические данные
    historical_data = {
        'highs': [100, 102, 105, 103, 108, 107, 110, 109, 112, 111],
        'lows': [95, 96, 98, 97, 101, 102, 104, 105, 107, 108],
        'closes': [98, 100, 102, 101, 106, 105, 108, 107, 110, 109]
    }

    result = filter_obj.analyze_volatility('SBER', historical_data)

    assert 'current_atr' in result
    assert 'average_atr' in result
    assert 'atr_ratio' in result
    assert 'volatility_level' in result

    print(
        f"✅ Анализ волатильности: {result['volatility_level']} (ATR={result['current_atr']:.2f}, ratio={result['atr_ratio']:.2f})")
    return True


# ============================================================================
# ТЕСТ 7: ПРОВЕРКА БЕЗ ДАННЫХ
# ============================================================================
def test_check_without_data():
    """Тест проверки без необходимых данных"""
    print("\n🧪 Тест 7: Проверка без данных")

    filter_obj = VolatilityFilter()

    # Без ATR
    signal_no_atr = {'ticker': 'SBER', 'price': 300.0}
    passed1, msg1 = filter_obj.check(signal_no_atr)
    assert passed1 == False
    assert "отсутствует" in msg1.lower()
    print(f"✅ Без ATR: {msg1}")

    # С историческими ATR вместо average_atr
    signal_with_historical = {
        'ticker': 'GAZP',
        'current_atr': 8.0,
        'historical_atrs': [5.0, 6.0, 7.0, 8.0, 9.0],  # Среднее = 7.0
        'price': 200.0
    }
    passed2, msg2 = filter_obj.check(signal_with_historical)
    # Коэффициент = 8.0 / 7.0 = 1.14 > 0.8
    assert passed2 == True
    print(f"✅ С историческими ATR: {msg2}")

    return True


# ============================================================================
# ЗАПУСК ВСЕХ ТЕСТОВ
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ VOLATILITY FILTER")
    print("=" * 60)

    test_results = []

    tests = [
        test_volatility_filter_initialization,
        test_check_sufficient_volatility,
        test_check_low_volatility,
        test_absolute_atr_check,
        test_atr_calculation,
        test_volatility_analysis,
        test_check_without_data
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
        print("🎉 ВСЕ ТЕСТЫ VOLATILITY FILTER ПРОЙДЕНЫ УСПЕШНО!")
        sys.exit(0)
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ VOLATILITY FILTER НЕ ПРОЙДЕНЫ")
        sys.exit(1)