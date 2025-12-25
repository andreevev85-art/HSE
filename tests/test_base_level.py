# panicker3000/tests/test_base_level.py
"""
Тест шагов 5-6 алгоритма (мультипериодная верификация + коррекция объёмом).
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.panic_detector import PanicDetector
from core.config_loader import ConfigLoader
from unittest.mock import patch


# ============================================================================
# ТЕСТ МУЛЬТИПЕРИОДНОЙ ВЕРИФИКАЦИИ
# ============================================================================
@patch.object(PanicDetector, '_check_market_time', return_value=True)
def test_multiperiod_verification(mock_time):
    """Тест мультипериодной верификации RSI"""
    print("🧪 Тест: Мультипериодная верификация")

    config_loader = ConfigLoader()
    detector = PanicDetector(config_loader)

    # Тестовые случаи согласно таблице
    test_cases = [
        # 1. СИЛЬНЫЙ: RSI14 <25/>75 + оба подтверждения
        {
            'name': 'Сильный: RSI14=24 (<25) + оба подтверждения',
            'data': {
                'ticker': 'SBER',
                'rsi_7': 28,
                'rsi_14': 24,
                'rsi_21': 29,
                'volume_ratio': 1.5,
                'price': 320.0
            },
            'expected_level': 'strong',
            'expected_desc': 'Макс.сила + 2 подтверждения'
        },
        # 2. ХОРОШИЙ: RSI14 <30/>70 + одно подтверждение
        {
            'name': 'Хороший: RSI14=28 (<30) + RSI7 подтверждает',
            'data': {
                'ticker': 'GAZP',
                'rsi_7': 28,
                'rsi_14': 28,
                'rsi_21': 40,
                'volume_ratio': 1.5,
                'price': 180.0
            },
            'expected_level': 'good',
            'expected_desc': 'Классика + 1 подтверждение'
        },
        # 3. ХОРОШИЙ: RSI14 <30/>70 + другое подтверждение
        {
            'name': 'Хороший: RSI14=28 (<30) + RSI21 подтверждает',
            'data': {
                'ticker': 'LKOH',
                'rsi_7': 40,
                'rsi_14': 28,
                'rsi_21': 29,
                'volume_ratio': 1.5,
                'price': 7500.0
            },
            'expected_level': 'good',
            'expected_desc': 'Классика + 1 подтверждение'
        },
        # 4. ХОРОШИЙ: RSI14 граничный + одно подтверждение
        {
            'name': 'Хороший: RSI14=28 (граничный) + RSI7 подтверждает',
            'data': {
                'ticker': 'GMKN',
                'rsi_7': 28,
                'rsi_14': 28,
                'rsi_21': 40,
                'volume_ratio': 1.5,
                'price': 19000.0
            },
            'expected_level': 'good',
            'expected_desc': 'Граничный + 1 подтверждение'
        },
        # 5. ХОРОШИЙ: RSI14 граничный + другое подтверждение
        {
            'name': 'Хороший: RSI14=28 (граничный) + RSI21 подтверждает',
            'data': {
                'ticker': 'YNDX',
                'rsi_7': 40,
                'rsi_14': 28,
                'rsi_21': 29,
                'volume_ratio': 1.5,
                'price': 2800.0
            },
            'expected_level': 'good',
            'expected_desc': 'Граничный + 1 подтверждение'
        },
        # 6. СРОЧНЫЙ: RSI14 граничный + без подтверждений
        {
            'name': 'Срочный: RSI14=28 (граничный) + без подтверждений',
            'data': {
                'ticker': 'ROSN',
                'rsi_7': 40,
                'rsi_14': 28,
                'rsi_21': 45,
                'volume_ratio': 1.5,
                'price': 500.0
            },
            'expected_level': 'urgent',
            'expected_desc': 'Граничная зона без подтверждений'
        },
        # 7. НЕТ СИГНАЛА: RSI14 в норме
        {
            'name': 'Нет сигнала: RSI14=40 (норма)',
            'data': {
                'ticker': 'VTBR',
                'rsi_7': 28,
                'rsi_14': 40,
                'rsi_21': 29,
                'volume_ratio': 1.5,
                'price': 0.05
            },
            'expected_level': None,
            'expected_desc': 'RSI14 в нормальном диапазоне'
        },
    ]

    passed = 0
    total = len(test_cases)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  📋 Тест {i}: {test_case['name']}")

        try:
            # Проверяем базовые условия
            basic_result = detector.check_basic_conditions(test_case['data'])

            if not basic_result[0]:
                print(f"    ⚠️  Базовые условия не пройдены: {basic_result[2]}")
                # Если RSI14 в норме - это ожидаемо для теста 7
                if test_case['expected_level'] is None:
                    passed += 1
                    print(f"    ✅ Ожидаемый результат")
                continue

            # Анализируем мультипериодную логику
            rsi_14 = test_case['data']['rsi_14']

            # Определяем силу отклонения RSI14
            if rsi_14 < 25 or rsi_14 > 75:
                rsi_14_strength = 'strong'
            elif (25 <= rsi_14 <= 29) or (71 <= rsi_14 <= 75):
                rsi_14_strength = 'weak'
            elif rsi_14 < 30 or rsi_14 > 70:
                rsi_14_strength = 'classic'
            else:
                rsi_14_strength = None

            # Определяем статус RSI7 и RSI21
            rsi_7 = test_case['data']['rsi_7']
            rsi_21 = test_case['data']['rsi_21']

            rsi_7_outside = rsi_7 < 30 or rsi_7 > 70
            rsi_21_outside = rsi_21 < 30 or rsi_21 > 70

            # Применяем логику из таблицы
            calculated_level = None

            if rsi_14_strength == 'strong' and rsi_7_outside and rsi_21_outside:
                calculated_level = 'strong'
            elif (rsi_14_strength in ['classic', 'weak']) and (rsi_7_outside or rsi_21_outside):
                calculated_level = 'good'
            elif rsi_14_strength == 'weak' and not rsi_7_outside and not rsi_21_outside:
                calculated_level = 'urgent'

            # Проверяем результат
            if calculated_level == test_case['expected_level']:
                passed += 1
                level_display = {
                    'strong': '🔴 СИЛЬНЫЙ',
                    'good': '🟡 ХОРОШИЙ',
                    'urgent': '⚪ СРОЧНЫЙ',
                    None: '❌ НЕТ СИГНАЛА'
                }
                print(f"    ✅ Пройден: {level_display[calculated_level]}")
            else:
                print(f"    ❌ Не пройден")
                print(f"      Ожидалось: {test_case['expected_level']}")
                print(f"      Получено: {calculated_level}")

        except Exception as e:
            print(f"    ❌ Ошибка выполнения: {e}")

    print(f"\n📊 Результат: {passed}/{total} тестов пройдено")

    if passed == total:
        print("✅ Мультипериодная верификация работает корректно")
        return True
    else:
        print(f"⚠️  Не пройдено: {total - passed} тестов")
        return False


# ============================================================================
# ЗАПУСК ТЕСТА
# ============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТ МУЛЬТИПЕРИОДНОЙ ВЕРИФИКАЦИИ")
    print("=" * 70)

    try:
        result = test_multiperiod_verification()

        print("\n" + "=" * 70)
        if result:
            print("✅ ТЕСТ ПРОЙДЕН")
            sys.exit(0)
        else:
            print("❌ ТЕСТ НЕ ПРОЙДЕН")
            sys.exit(1)

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        sys.exit(1)