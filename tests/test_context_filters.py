# panicker3000/tests/test_context_filters.py
"""
Тест классов фильтров.
"""

import sys
import os
from datetime import datetime, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import patch


# ============================================================================
# ТЕСТ TimeFilter
# ============================================================================
def test_time_filter_unit():
    print("🧪 Тест: TimeFilter")

    from core.filters.time_filter import TimeFilter
    from datetime import time, datetime

    filter_instance = TimeFilter()

    # Это уже объекты time
    active_start = filter_instance.ACTIVE_START  # datetime.time(11, 0)
    active_end = filter_instance.ACTIVE_END  # datetime.time(16, 0)

    print(f"  Активная зона: {active_start} - {active_end}")

    test_cases = [
        (time(active_start.hour - 1, active_start.minute), False, "до активной зоны"),
        (active_start, True, "начало активной зоны"),
        (time((active_start.hour + active_end.hour) // 2, 30), True, "середина дня"),
        (active_end, True, "конец активной зоны"),
        (time(active_end.hour + 1, active_end.minute), False, "после активной зоны"),
    ]

    passed = 0
    for test_time, expected, desc in test_cases:
        # Создаем timestamp
        test_datetime = datetime(2024, 1, 15, test_time.hour, test_time.minute)
        test_data = {'timestamp': test_datetime}

        result = filter_instance.check(test_data)
        result_bool = result[0] if isinstance(result, tuple) else result

        if result_bool == expected:
            passed += 1
            status = '✅' if result_bool else '✅'
            print(f"  {status} {desc}")
        else:
            print(f"  ❌ {desc}")

    print(f"\n📊 Результат: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


# ============================================================================
# ТЕСТ VolatilityFilter
# ============================================================================
def test_volatility_filter_unit():
    print("\n🧪 Тест: VolatilityFilter")

    from core.filters.volatility_filter import VolatilityFilter

    filter_instance = VolatilityFilter()

    test_cases = [
        {
            'data': {
                'current_atr': 2.0,
                'average_atr': 2.5,
                'price': 250.0
            },
            'expected': True,  # 2.0/2.5=0.8× (на границе), 2.0/250=0.8% > 0.5%
            'desc': 'АТР на границе'
        },
        {
            'data': {
                'current_atr': 1.9,
                'average_atr': 2.5,
                'price': 250.0
            },
            'expected': False,  # 1.9/2.5=0.76× < 0.8, 1.9/250=0.76% > 0.5%
            'desc': 'АТР ниже порога'
        },
        {
            'data': {
                'current_atr': 2.1,
                'average_atr': 2.5,
                'price': 250.0
            },
            'expected': True,  # 2.1/2.5=0.84× > 0.8, 2.1/250=0.84% > 0.5%
            'desc': 'АТР выше порога'
        },
        {
            'data': {
                'current_atr': 0.5,
                'average_atr': 1.0,
                'price': 100.0
            },
            'expected': False,  # 0.5/1.0=0.5× < 0.8, И 0.5/100=0.5% == 0.5% порог (НЕ <, поэтому False)
            'desc': 'АТР равен min_absolute_atr'
        },
    ]

    passed = 0
    for case in test_cases:
        result = filter_instance.check(case['data'])
        result_bool = result[0] if isinstance(result, tuple) else result

        if result_bool == case['expected']:
            passed += 1
            status = '✅' if result_bool else '✅'
            print(f"  {status} {case['desc']}")
        else:
            print(f"  ❌ {case['desc']}")
            print(f"    Ожидалось: {case['expected']}")
            print(f"    Получено: {result_bool}")
            if isinstance(result, tuple) and len(result) > 1:
                print(f"    Сообщение: {result[1]}")

    print(f"\n📊 Результат: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


# ============================================================================
# ТЕСТ TrendFilter
# ============================================================================
def test_trend_filter_unit():
    print("\n🧪 Тест: TrendFilter")

    from core.filters.trend_filter import TrendFilter

    filter_instance = TrendFilter()

    test_cases = [
        {
            'data': {'signal_type': 'panic', 'price': 95.0, 'sma_20': 100.0},
            'expected': False,
            'desc': 'Паника: цена ниже SMA20'
        },
        {
            'data': {'signal_type': 'panic', 'price': 105.0, 'sma_20': 100.0},
            'expected': True,
            'desc': 'Паника: цена выше SMA20'
        },
        {
            'data': {'signal_type': 'greed', 'price': 105.0, 'sma_20': 100.0},
            'expected': False,
            'desc': 'Жадность: цена выше SMA20'
        },
        {
            'data': {'signal_type': 'greed', 'price': 95.0, 'sma_20': 100.0},
            'expected': True,
            'desc': 'Жадность: цена ниже SMA20'
        },
    ]

    passed = 0
    for case in test_cases:
        result = filter_instance.check(case['data'])
        result_bool = result[0] if isinstance(result, tuple) else result

        if result_bool == case['expected']:
            passed += 1
            status = '✅' if result_bool else '✅'
            print(f"  {status} {case['desc']}")
        else:
            print(f"  ❌ {case['desc']}")
            print(f"    Ожидалось: {case['expected']}")
            print(f"    Получено: {result_bool}")

    print(f"\n📊 Результат: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТЫ КЛАССОВ ФИЛЬТРОВ")
    print("=" * 70)

    test_results = []

    try:
        test_results.append(test_time_filter_unit())
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        test_results.append(False)

    try:
        test_results.append(test_volatility_filter_unit())
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        test_results.append(False)

    try:
        test_results.append(test_trend_filter_unit())
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        test_results.append(False)

    print("\n" + "=" * 70)
    passed_count = sum(test_results)
    total_count = len(test_results)

    if passed_count == total_count:
        print(f"✅ ПРОЙДЕНО: {passed_count}/{total_count}")
        sys.exit(0)
    else:
        print(f"❌ ПРОЙДЕНО: {passed_count}/{total_count}")
        sys.exit(1)