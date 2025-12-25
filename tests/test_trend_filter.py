# panicker3000/tests/test_trend_filter.py
"""
Тесты для фильтра тренда (скользящие средние).
"""

# ============================================================================
# ИМПОРТЫ
# ============================================================================
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.filters.trend_filter import TrendFilter, TrendDirection, TradeAction


# ============================================================================
# ТЕСТ 1: ИНИЦИАЛИЗАЦИЯ
# ============================================================================
def test_trend_filter_initialization():
    """Тест инициализации фильтра"""
    print("🧪 Тест 1: Инициализация TrendFilter")

    # С параметрами по умолчанию
    filter_default = TrendFilter()

    # С кастомными параметрами
    custom_config = {
        'ma_period': 50,
        'trend_threshold': 2.0,
        'require_trend_alignment': False
    }
    filter_custom = TrendFilter(custom_config)

    assert filter_default.ma_period == 20
    assert filter_default.trend_threshold == 1.0
    assert filter_default.require_trend_alignment == True

    assert filter_custom.ma_period == 50
    assert filter_custom.trend_threshold == 2.0
    assert filter_custom.require_trend_alignment == False

    print(f"✅ По умолчанию: MA{filter_default.ma_period}, threshold={filter_default.trend_threshold}%")
    print(f"✅ Кастомный: MA{filter_custom.ma_period}, threshold={filter_custom.trend_threshold}%")
    return True


# ============================================================================
# ТЕСТ 2: ПОКУПКА С ВОСХОДЯЩИМ ТРЕНДОМ
# ============================================================================
def test_buy_with_bullish_trend():
    """Тест покупки при восходящем тренде"""
    print("\n🧪 Тест 2: Покупка с восходящим трендом")

    filter_obj = TrendFilter()

    # Цена выше SMA20 - восходящий тренд
    signal_data = {
        'ticker': 'SBER',
        'signal_type': 'panic',  # Покупка
        'price': 320.0,
        'sma_20': 300.0
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == True
    assert "Покупка" in message
    assert "цена 320.00 > SMA300.00" in message
    print(f"✅ Покупка с восходящим трендом: {message}")
    return True


# ============================================================================
# ТЕСТ 3: ПОКУПКА С НИСХОДЯЩИМ ТРЕНДОМ
# ============================================================================
def test_buy_with_bearish_trend():
    """Тест покупки при нисходящем тренде (должно не пройти)"""
    print("\n🧪 Тест 3: Покупка с нисходящим трендом")

    filter_obj = TrendFilter()

    # Цена ниже SMA20 - нисходящий тренд
    signal_data = {
        'ticker': 'GAZP',
        'signal_type': 'panic',  # Покупка
        'price': 180.0,
        'sma_20': 200.0
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == False
    assert "Покупка" in message
    assert "цена 180.00 < SMA200.00" in message
    print(f"✅ Покупка с нисходящим трендом отклонена: {message}")
    return True


# ============================================================================
# ТЕСТ 4: ПРОДАЖА С НИСХОДЯЩИМ ТРЕНДОМ
# ============================================================================
def test_sell_with_bearish_trend():
    """Тест продажи при нисходящем тренде"""
    print("\n🧪 Тест 4: Продажа с нисходящим трендом")

    filter_obj = TrendFilter()

    # Цена ниже SMA20 - нисходящий тренд
    signal_data = {
        'ticker': 'LKOH',
        'signal_type': 'greed',  # Продажа
        'price': 7500.0,
        'sma_20': 8000.0
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == True
    assert "Продажа" in message
    assert "цена 7500.00 < SMA8000.00" in message
    print(f"✅ Продажа с нисходящим трендом: {message}")
    return True


# ============================================================================
# ТЕСТ 5: РАСЧЁТ SMA
# ============================================================================
def test_sma_calculation():
    """Тест расчёта Simple Moving Average"""
    print("\n🧪 Тест 5: Расчёт SMA")

    filter_obj = TrendFilter({'ma_period': 5})

    # Тестовые цены
    prices = [100, 102, 105, 103, 108, 107, 110]
    # Последние 5 цен: [105, 103, 108, 107, 110], среднее = (105+103+108+107+110)/5 = 106.6

    sma = filter_obj.calculate_sma(prices, period=5)

    assert sma is not None
    assert abs(sma - 106.6) < 0.1

    print(f"✅ SMA5 рассчитана: {sma:.2f}")
    return True


# ============================================================================
# ТЕСТ 6: РАСЧЁТ EMA
# ============================================================================
def test_ema_calculation():
    """Тест расчёта Exponential Moving Average"""
    print("\n🧪 Тест 6: Расчёт EMA")

    filter_obj = TrendFilter({'ma_period': 3})

    # Тестовые цены для EMA3
    prices = [100, 102, 105, 103, 108]

    ema = filter_obj.calculate_ema(prices, period=3)

    # EMA расчёт:
    # SMA первых 3 = (100+102+105)/3 = 102.33
    # Multiplier = 2/(3+1) = 0.5
    # EMA4 = (103 - 102.33)*0.5 + 102.33 = 102.665
    # EMA5 = (108 - 102.665)*0.5 + 102.665 = 105.3325

    assert ema is not None
    assert ema > 100 and ema < 110

    print(f"✅ EMA3 рассчитана: {ema:.2f}")
    return True


# ============================================================================
# ТЕСТ 7: АНАЛИЗ ТРЕНДА
# ============================================================================
def test_trend_analysis():
    """Тест анализа тренда"""
    print("\n🧪 Тест 7: Анализ тренда")

    filter_obj = TrendFilter({'ma_period': 10, 'trend_threshold': 2.0})

    # Тестовые цены с явным восходящим трендом
    prices = list(range(100, 150, 5))  # 100, 105, 110, ..., 145

    result = filter_obj.analyze_trend('SBER', prices)

    assert 'trend' in result
    assert 'deviation_percent' in result
    assert 'ma_value' in result

    # Последняя цена = 145, средняя должна быть меньше
    assert result['current_price'] == 145
    assert result['ma_value'] < 145
    assert result['trend'] == TrendDirection.BULLISH.value

    print(
        f"✅ Анализ тренда: {result['trend']} ({result['trend_strength']}), отклонение: {result['deviation_percent']:.1f}%")
    return True


# ============================================================================
# ТЕСТ 8: БЕЗ ТРЕБОВАНИЯ СООТВЕТСТВИЯ ТРЕНДУ
# ============================================================================
def test_no_trend_alignment_required():
    """Тест когда не требуется соответствие тренду"""
    print("\n🧪 Тест 8: Без требования соответствия тренду")

    filter_obj = TrendFilter({'require_trend_alignment': False})

    # Цена ниже SMA20 (плохо для покупки), но фильтр пропускает
    signal_data = {
        'ticker': 'YNDX',
        'signal_type': 'panic',  # Покупка
        'price': 2800.0,
        'sma_20': 3000.0
    }

    passed, message = filter_obj.check(signal_data)

    assert passed == True
    assert "не требуется" in message
    print(f"✅ Без требования тренда: {message}")
    return True


# ============================================================================
# ТЕСТ 9: ОПРЕДЕЛЕНИЕ ПО RSI
# ============================================================================
def test_signal_type_from_rsi():
    """Тест определения типа сигнала по RSI"""
    print("\n🧪 Тест 9: Определение типа сигнала по RSI")

    filter_obj = TrendFilter()

    # RSI < 30 = паника = покупка
    signal_panic = {
        'ticker': 'GMKN',
        'rsi': 25,  # Паника
        'price': 19000.0,
        'sma_20': 18500.0  # Цена выше SMA = восходящий тренд
    }

    passed1, message1 = filter_obj.check(signal_panic)
    assert passed1 == True
    assert "Покупка" in message1
    print(f"✅ RSI 25 = покупка: {message1}")

    # RSI > 70 = жадность = продажа
    signal_greed = {
        'ticker': 'GMKN',
        'rsi': 75,  # Жадность
        'price': 19000.0,
        'sma_20': 19500.0  # Цена ниже SMA = нисходящий тренд
    }

    passed2, message2 = filter_obj.check(signal_greed)
    assert passed2 == True
    assert "Продажа" in message2
    print(f"✅ RSI 75 = продажа: {message2}")

    return True


# ============================================================================
# ЗАПУСК ВСЕХ ТЕСТОВ
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ TREND FILTER")
    print("=" * 60)

    test_results = []

    tests = [
        test_trend_filter_initialization,
        test_buy_with_bullish_trend,
        test_buy_with_bearish_trend,
        test_sell_with_bearish_trend,
        test_sma_calculation,
        test_ema_calculation,
        test_trend_analysis,
        test_no_trend_alignment_required,
        test_signal_type_from_rsi
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
        print("🎉 ВСЕ ТЕСТЫ TREND FILTER ПРОЙДЕНЫ УСПЕШНО!")
        sys.exit(0)
    else:
        print("❌ НЕКОТОРЫЕ ТЕСТЫ TREND FILTER НЕ ПРОЙДЕНЫ")
        sys.exit(1)