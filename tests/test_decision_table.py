# panicker3000/tests/test_decision_table.py
"""
Тест матрицы решений (шаг 8 алгоритма).
Проверяет, как базовый уровень корректируется фильтрами.
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import sys
import os
from enum import Enum
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ============================================================================
# КОНСТАНТЫ И ПЕРЕЧИСЛЕНИЯ
# ============================================================================
class SignalLevel(Enum):
    """Уровни сигнала"""
    STRONG = "🔴 СИЛЬНЫЙ"
    GOOD = "🟡 ХОРОШИЙ"
    URGENT = "⚪ СРОЧНЫЙ"
    IGNORE = "❌ ИГНОРИРОВАТЬ"


class BaseLevel(Enum):
    """Базовые уровни (до фильтров)"""
    STRONG = "Сильный"
    GOOD = "Хороший"
    URGENT = "Срочный"


# ============================================================================
# ТЕСТИРУЕМАЯ ФУНКЦИЯ (ЗАГЛУШКА)
# ============================================================================
def apply_filters_to_level(base_level: BaseLevel, filters_passed: int) -> SignalLevel:
    """
    Применяет фильтры к базовому уровню (шаг 8 алгоритма).

    Args:
        base_level: Базовый уровень (до фильтров)
        filters_passed: Количество пройденных фильтров (0-4)

    Returns:
        Финальный уровень сигнала
    """
    # Логика из ТЗ: каждый непройденный фильтр понижает уровень на одну ступень
    # Уровни: STRONG → GOOD → URGENT → IGNORE

    level_map = {
        BaseLevel.STRONG: SignalLevel.STRONG,
        BaseLevel.GOOD: SignalLevel.GOOD,
        BaseLevel.URGENT: SignalLevel.URGENT,
    }

    # Начальный уровень
    current_level = level_map[base_level]

    # Количество непройденных фильтров
    failed_filters = 4 - filters_passed

    # Понижаем уровень за каждый непройденный фильтр
    for _ in range(failed_filters):
        if current_level == SignalLevel.STRONG:
            current_level = SignalLevel.GOOD
        elif current_level == SignalLevel.GOOD:
            current_level = SignalLevel.URGENT
        elif current_level == SignalLevel.URGENT:
            current_level = SignalLevel.IGNORE
        else:
            break  # Уже IGNORE

    return current_level


# ============================================================================
# ТЕСТОВЫЕ СЛУЧАИ (MATRIX)
# ============================================================================
def generate_test_cases() -> list:
    """
    Генерирует все тестовые случаи для матрицы решений.
    Возвращает список тестовых случаев.
    """
    test_cases = []

    # Матрица: (базовый уровень, пройдено фильтров, ожидаемый финальный уровень)
    matrix = [
        # Базовый уровень: STRONG
        (BaseLevel.STRONG, 4, SignalLevel.STRONG, "STRONG + все фильтры → STRONG"),
        (BaseLevel.STRONG, 3, SignalLevel.GOOD, "STRONG + 3 фильтра → GOOD"),
        (BaseLevel.STRONG, 2, SignalLevel.URGENT, "STRONG + 2 фильтра → URGENT"),
        (BaseLevel.STRONG, 1, SignalLevel.IGNORE, "STRONG + 1 фильтр → IGNORE"),
        (BaseLevel.STRONG, 0, SignalLevel.IGNORE, "STRONG + 0 фильтров → IGNORE"),

        # Базовый уровень: GOOD
        (BaseLevel.GOOD, 4, SignalLevel.GOOD, "GOOD + все фильтры → GOOD"),
        (BaseLevel.GOOD, 3, SignalLevel.URGENT, "GOOD + 3 фильтра → URGENT"),
        (BaseLevel.GOOD, 2, SignalLevel.IGNORE, "GOOD + 2 фильтра → IGNORE"),
        (BaseLevel.GOOD, 1, SignalLevel.IGNORE, "GOOD + 1 фильтр → IGNORE"),
        (BaseLevel.GOOD, 0, SignalLevel.IGNORE, "GOOD + 0 фильтров → IGNORE"),

        # Базовый уровень: URGENT
        (BaseLevel.URGENT, 4, SignalLevel.URGENT, "URGENT + все фильтры → URGENT"),
        (BaseLevel.URGENT, 3, SignalLevel.IGNORE, "URGENT + 3 фильтра → IGNORE"),
        (BaseLevel.URGENT, 2, SignalLevel.IGNORE, "URGENT + 2 фильтра → IGNORE"),
        (BaseLevel.URGENT, 1, SignalLevel.IGNORE, "URGENT + 1 фильтр → IGNORE"),
        (BaseLevel.URGENT, 0, SignalLevel.IGNORE, "URGENT + 0 фильтров → IGNORE"),
    ]

    return matrix


# ============================================================================
# ОСНОВНОЙ ТЕСТ
# ============================================================================
def test_decision_matrix():
    """
    Тест полной матрицы решений.
    Проверяет все комбинации базовых уровней и фильтров.
    """
    print("🧪 Тест: Матрица решений (шаг 8 алгоритма)")
    print("=" * 70)
    print("Логика: каждый непройденный фильтр понижает уровень на одну ступень")
    print("Уровни: STRONG → GOOD → URGENT → IGNORE")
    print("=" * 70)

    test_cases = generate_test_cases()
    passed = 0
    failed_cases = []

    for base_level, filters_passed, expected, description in test_cases:
        result = apply_filters_to_level(base_level, filters_passed)

        if result == expected:
            passed += 1
            status = "✅"
        else:
            status = "❌"
            failed_cases.append({
                'description': description,
                'base': base_level.value,
                'filters': filters_passed,
                'expected': expected.value,
                'actual': result.value
            })

        # Форматируем вывод
        base_str = str(base_level.value).ljust(10)
        filters_str = f"{filters_passed}/4".ljust(4)
        result_str = str(result.value)

        print(f"{status} {base_str} | фильтры: {filters_str} | результат: {result_str}")

    print("\n" + "=" * 70)
    print(f"📊 Результат: {passed}/{len(test_cases)}")

    # Детали ошибок
    if failed_cases:
        print("\n❌ Проваленные тесты:")
        for case in failed_cases:
            print(f"  - {case['description']}")
            print(f"    Ожидалось: {case['expected']}")
            print(f"    Получено:  {case['actual']}")
            print()

    assert passed == len(test_cases), f"Провалено {len(test_cases) - passed} тестов"
    return passed == len(test_cases)


# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ
# ============================================================================
def test_edge_cases():
    """
    Тест граничных случаев.
    """
    print("\n🧪 Тест: Граничные случаи")

    edge_cases = [
        # Проверка на отрицательное количество фильтров
        (BaseLevel.STRONG, -1, SignalLevel.IGNORE, "Отрицательные фильтры → IGNORE"),
        # Проверка на избыточное количество фильтров
        (BaseLevel.STRONG, 5, SignalLevel.STRONG, "5 фильтров → STRONG (максимум)"),
        # Проверка на уровень ниже IGNORE (должен остаться IGNORE)
        (BaseLevel.URGENT, 0, SignalLevel.IGNORE, "URGENT + 0 фильтров → IGNORE"),
    ]

    passed = 0
    for base_level, filters_passed, expected, description in edge_cases:
        try:
            result = apply_filters_to_level(base_level, filters_passed)
            if result == expected:
                passed += 1
                print(f"✅ {description}")
            else:
                print(f"❌ {description}")
                print(f"   Ожидалось: {expected.value}")
                print(f"   Получено:  {result.value}")
        except Exception as e:
            print(f"❌ {description} - ошибка: {e}")

    print(f"📊 Результат: {passed}/{len(edge_cases)}")
    return passed == len(edge_cases)


# ============================================================================
# ТЕСТ ПРИМЕРОВ ИЗ ТЗ
# ============================================================================
def test_tz_examples():
    """
    Тест примеров из технического задания.
    Проверяет конкретные случаи, описанные в ТЗ.
    """
    print("\n🧪 Тест: Примеры из ТЗ")

    # Примеры из раздела 3.2 ТЗ
    tz_examples = [
        # Пример 1: Сильная паника (все фильтры пройдены)
        {
            'description': 'Пример 1: SBER - сильная паника',
            'base_level': BaseLevel.STRONG,
            'filters_passed': 4,
            'expected': SignalLevel.STRONG,
            'expected_text': '🔴 СИЛЬНЫЙ'
        },
        # Пример 2: Умеренная жадность (3 из 4 фильтров)
        {
            'description': 'Пример 2: GAZP - умеренная жадность',
            'base_level': BaseLevel.GOOD,
            'filters_passed': 3,
            'expected': SignalLevel.URGENT,  # GOOD + 1 непройденный фильтр
            'expected_text': '⚪ СРОЧНЫЙ'
        },
    ]

    passed = 0
    for example in tz_examples:
        result = apply_filters_to_level(
            example['base_level'],
            example['filters_passed']
        )

        if result == example['expected']:
            passed += 1
            print(f"✅ {example['description']}")
            print(f"   {example['expected_text']} - корректно")
        else:
            print(f"❌ {example['description']}")
            print(f"   Ожидалось: {example['expected_text']}")
            print(f"   Получено:  {result.value}")

    print(f"📊 Результат: {passed}/{len(tz_examples)}")
    return passed == len(tz_examples)


# ============================================================================
# ЗАПУСК ТЕСТОВ
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТ МАТРИЦЫ РЕШЕНИЙ (ШАГ 8 АЛГОРИТМА)")
    print("=" * 70)

    results = []

    try:
        results.append(test_decision_matrix())
    except Exception as e:
        print(f"\n❌ Ошибка в test_decision_matrix: {e}")
        results.append(False)

    try:
        results.append(test_edge_cases())
    except Exception as e:
        print(f"\n❌ Ошибка в test_edge_cases: {e}")
        results.append(False)

    try:
        results.append(test_tz_examples())
    except Exception as e:
        print(f"\n❌ Ошибка в test_tz_examples: {e}")
        results.append(False)

    print("\n" + "=" * 70)
    total_passed = sum(results)
    total_tests = len(results)

    if total_passed == total_tests:
        print(f"✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ: {total_passed}/{total_tests}")
        sys.exit(0)
    else:
        print(f"❌ ПРОЙДЕНО: {total_passed}/{total_tests}")
        sys.exit(1)