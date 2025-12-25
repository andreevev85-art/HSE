# panicker3000/tests/test_time_filter.py
"""
Тесты для фильтра времени.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import sys
import os
from datetime import datetime, time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.filters.time_filter import TimeFilter


# ============================================================================
# ТЕСТ 1: ИНИЦИАЛИЗАЦИЯ
# ============================================================================
def test_time_filter_initialization():
    """Тест инициализации фильтра"""
    print("🧪 Тест 1: Инициализация TimeFilter")

    filter_obj = TimeFilter()
    start, end = filter_obj.get_active_hours()

    assert start == time(11, 0)
    assert end == time(16, 0)
    print(f"✅ Активные часы: {start}-{end}")
    return True


# ============================================================================
# ТЕСТ 2: ПРОВЕРКА ВНУТРИ АКТИВНОЙ ЗОНЫ
# ============================================================================
def test_check_inside_active_zone():
    """Тест проверки внутри активной зоны"""
    print("\n🧪 Тест 2: Проверка внутри активной зоны")

    filter_obj = TimeFilter()

    # Создаём время внутри активной зоны (14:30)
    test_time = datetime(2024, 1, 1, 14, 30)
    signal_data = {'timestamp': test_time}

    passed, message = filter_obj.check(signal_data)

    assert passed == True
    assert "активной зоне" in message
    print(f"✅ Внутри активной зоны: {message}")
    return True


# ============================================================================
# ТЕСТ 3: ПРОВЕРКА ВНЕ АКТИВНОЙ ЗОНЫ
# ============================================================================
def test_check_outside_active_zone():
    """Тест проверки вне активной зоны"""
    print("\n🧪 Тест 3: Проверка вне активной зоны")

    filter_obj = TimeFilter()

    # Создаём время вне активной зоны (9:30 - до открытия)
    test_time = datetime(2024, 1, 1, 9, 30)
    signal_data = {'timestamp': test_time}

    passed, message = filter_obj.check(signal_data)

    assert passed == False
    assert "Биржа закрыта" in message or "вне активной зоны" in message
    print(f"✅ Вне активной зоны: {message}")
    return True


# ============================================================================
# ТЕСТ 4: КОНФИГУРАЦИЯ ИЗ КОНФИГА
# ============================================================================
def test_custom_config():
    """Тест кастомной конфигурации"""
    print("\n🧪 Тест 4: Кастомная конфигурация")

    custom_config = {
        'active_start': '10:30',
        'active_end': '17:00'
    }

    filter_obj = TimeFilter(custom_config)
    start, end = filter_obj.get_active_hours()

    assert start == time(10, 30)
    assert end == time(17, 0)
    print(f"✅ Кастомные активные часы: {start}-{end}")
    return True


# ============================================================================
# ЗАПУСК ВСЕХ ТЕСТОВ
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ TIME FILTER")
    print("=" * 60)

    test_results = []

    tests = [
        test_time_filter_initialization,
        test_check_inside_active_zone,
        test_check_outside_active_zone,
        test_custom_config
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
        print("🎉 ВСЕ ТЕСТЫ TIME FILTER ПРОЙДЕНЫ УСПЕШНО!")
        sys.exit(0)
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ TIME FILTER НЕ ПРОЙДЕНЫ")
        sys.exit(1)