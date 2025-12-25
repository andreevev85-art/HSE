"""
Сквозной интеграционный тест для PanicDetector.
Проверяет полный алгоритм из 8 шагов.
"""

import sys
import os
from datetime import datetime, time, timedelta
from unittest.mock import Mock, patch
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def create_mock_config_loader():
    """Создает мок ConfigLoader с тестовыми порогами"""
    mock_loader = Mock()
    mock_loader.load_panic_thresholds.return_value = {
        'panic_thresholds': {
            'red': {'rsi_buy': 25, 'rsi_sell': 75, 'volume_min': 2.0},
            'yellow': {'rsi_buy': 30, 'rsi_sell': 70, 'volume_min': 1.5},
            'white': {'rsi_buy': 35, 'rsi_sell': 65, 'volume_min': 1.2}
        }
    }
    return mock_loader


def test_panic_detector_initialization():
    """Тест 1: Инициализация детектора"""
    from core.panic_detector import PanicDetector

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    assert detector is not None
    assert hasattr(detector, 'filters')
    assert hasattr(detector, 'analyze_ticker')


def test_basic_conditions_check():
    """Тест 2: Проверка базовых условий"""
    from core.panic_detector import PanicDetector, SignalType

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # Случай паники
    test_data_panic = {
        'ticker': 'SBER',
        'rsi_14': 24,
        'volume_ratio': 1.8,
        'price': 300.0
    }

    with patch.object(detector, '_check_market_time', return_value=True):
        passed, signal_type, message = detector.check_basic_conditions(test_data_panic)

        assert passed is True
        assert signal_type == SignalType.PANIC
        # ИСПРАВЛЕНО: проверяем что сообщение содержит 'panic' (а не 'паник')
        assert 'panic' in message.lower()

    # Случай жадности
    test_data_greed = {
        'ticker': 'SBER',
        'rsi_14': 76,
        'volume_ratio': 1.8,
        'price': 300.0
    }

    with patch.object(detector, '_check_market_time', return_value=True):
        passed, signal_type, message = detector.check_basic_conditions(test_data_greed)

        assert passed is True
        assert signal_type == SignalType.GREED
        # ИСПРАВЛЕНО: проверяем что сообщение содержит 'greed' (а не 'жадность')
        assert 'greed' in message.lower()

    # Случай без сигнала
    test_data_no_signal = {
        'ticker': 'SBER',
        'rsi_14': 50,
        'volume_ratio': 1.8,
        'price': 300.0
    }

    with patch.object(detector, '_check_market_time', return_value=True):
        passed, signal_type, message = detector.check_basic_conditions(test_data_no_signal)

        assert passed is False
        assert signal_type is None


def test_base_level_calculation():
    """Тест 3: Расчет базового уровня"""
    from core.panic_detector import PanicDetector, SignalType, BaseLevel

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # Случай STRONG (все три периода в зоне)
    base_level = detector.get_base_level(
        rsi_7=22,
        rsi_14=24,
        rsi_21=26,
        signal_type=SignalType.PANIC
    )
    assert base_level == BaseLevel.STRONG

    # Случай GOOD (два периода в зоне)
    base_level = detector.get_base_level(
        rsi_7=22,
        rsi_14=24,
        rsi_21=45,
        signal_type=SignalType.PANIC
    )
    assert base_level == BaseLevel.GOOD

    # Случай URGENT (только RSI14 в зоне)
    base_level = detector.get_base_level(
        rsi_7=40,
        rsi_14=28,
        rsi_21=45,
        signal_type=SignalType.PANIC
    )
    assert base_level == BaseLevel.URGENT

    # Случай NONE (ничего в зоне)
    base_level = detector.get_base_level(
        rsi_7=40,
        rsi_14=45,
        rsi_21=50,
        signal_type=SignalType.PANIC
    )
    assert base_level == BaseLevel.NONE


def test_volume_adjustment():
    """Тест 4: Коррекция уровнем объема"""
    from core.panic_detector import PanicDetector, BaseLevel

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # URGENT + большой объем = GOOD
    adjusted = detector.adjust_level_by_volume(BaseLevel.URGENT, 2.3)
    assert adjusted == BaseLevel.GOOD

    # GOOD + большой объем = STRONG
    adjusted = detector.adjust_level_by_volume(BaseLevel.GOOD, 2.1)
    assert adjusted == BaseLevel.STRONG

    # STRONG + большой объем = STRONG (уже максимум)
    adjusted = detector.adjust_level_by_volume(BaseLevel.STRONG, 2.5)
    assert adjusted == BaseLevel.STRONG

    # URGENT + маленький объем = URGENT (без изменений)
    adjusted = detector.adjust_level_by_volume(BaseLevel.URGENT, 1.3)
    assert adjusted == BaseLevel.URGENT


def test_filters_execution():
    """Тест 5: Проверка выполнения фильтров"""
    from core.panic_detector import PanicDetector, BaseLevel, FinalLevel

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # Создаем моки для фильтров
    mock_filters = {}
    for key, filter_obj in detector.filters.items():
        mock_filter = Mock()
        mock_filter.check.return_value = (True, f"Фильтр {key} пройден")
        mock_filters[key] = mock_filter

    # Заменяем фильтры в детекторе
    detector.filters = mock_filters

    # Тестовые данные
    test_data = {
        'ticker': 'SBER',
        'price': 300.0,
        'current_atr': 5.0,
        'average_atr': 3.0,
        'sma_20': 295.0,
        'spread_percent': 0.05
    }

    # Применяем фильтры
    final_level, passed, failed = detector.apply_context_filters(
        test_data,
        BaseLevel.GOOD
    )

    # Проверяем результаты
    assert final_level == FinalLevel.YELLOW  # GOOD с фильтрами = YELLOW
    assert len(passed) == len(mock_filters)
    assert len(failed) == 0


def test_filter_penalties():
    """Тест 6: Проверка штрафов фильтров"""
    from core.panic_detector import PanicDetector, BaseLevel, FinalLevel

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # ИСПРАВЛЕНО: Создаем реальные ключи фильтров как в PanicDetector
    # Получаем реальные ключи из детектора
    real_filter_keys = list(detector.filters.keys())

    # Создаем моки для фильтров, где один не проходит
    mock_filters = {}

    for i, key in enumerate(real_filter_keys):
        mock_filter = Mock()
        if i == 2:  # третий фильтр не проходит
            mock_filter.check.return_value = (False, f"Фильтр {key} не пройден")
        else:
            mock_filter.check.return_value = (True, f"Фильтр {key} пройден")
        mock_filters[key] = mock_filter

    detector.filters = mock_filters

    test_data = {
        'ticker': 'SBER',
        'price': 300.0,
        'current_atr': 5.0,
        'average_atr': 3.0,
        'sma_20': 305.0,
        'spread_percent': 0.05
    }

    # GOOD с одним непройденным фильтром = URGENT (WHITE)
    final_level, passed, failed = detector.apply_context_filters(
        test_data,
        BaseLevel.GOOD
    )

    # ИСПРАВЛЕНО: GOOD (YELLOW) с одним непройденным фильтром = URGENT (WHITE)
    # GOOD = BaseLevel.GOOD = 2
    # Один фильтр не пройден = -1
    # 2 - 1 = 1 = URGENT (WHITE)
    assert final_level == FinalLevel.WHITE
    assert len(passed) == len(real_filter_keys) - 1
    assert len(failed) == 1


def test_full_analysis_strong_panic():
    """Тест 7: Полный анализ сильной паники"""
    from core.panic_detector import PanicDetector, SignalType, FinalLevel

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # Создаем моки для фильтров
    for key in detector.filters:
        detector.filters[key].check = Mock(return_value=(True, f"Фильтр {key} пройден"))

    # Тестовые данные для сильной паники
    test_data = {
        'ticker': 'SBER',
        'timestamp': datetime.now(),
        'rsi_7': 22,
        'rsi_14': 24,
        'rsi_21': 26,
        'volume_ratio': 2.3,
        'current_volume': 450_000_000,
        'average_volume': 195_000_000,
        'price': 310.0,
        'current_atr': 5.0,
        'average_atr': 3.0,
        'sma_20': 305.0,
        'spread_percent': 0.05
    }

    # Мокаем проверку времени рынка
    with patch.object(detector, '_check_market_time', return_value=True):
        signal = detector.analyze_ticker(test_data)

    assert signal is not None
    assert signal.ticker == 'SBER'
    assert signal.signal_type == SignalType.PANIC
    assert signal.final_level == FinalLevel.RED


def test_full_analysis_no_signal():
    """Тест 8: Полный анализ без сигнала"""
    from core.panic_detector import PanicDetector

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # Тестовые данные без сигнала
    test_data = {
        'ticker': 'GMKN',
        'timestamp': datetime.now(),
        'rsi_7': 48,
        'rsi_14': 52,
        'rsi_21': 55,
        'volume_ratio': 1.1,
        'price': 25000.0,
        'current_atr': 2.5,
        'average_atr': 2.5,
        'sma_20': 24800.0,
        'spread_percent': 0.1
    }

    with patch.object(detector, '_check_market_time', return_value=True):
        signal = detector.analyze_ticker(test_data)

    assert signal is None


def test_signal_type_detection():
    """Тест 9: Определение типа сигнала"""
    from core.panic_detector import PanicDetector, SignalType

    mock_loader = create_mock_config_loader()
    detector = PanicDetector(mock_loader)

    # Паника
    signal_type = detector._get_signal_type_from_rsi(24)
    assert signal_type == SignalType.PANIC

    # Жадность
    signal_type = detector._get_signal_type_from_rsi(76)
    assert signal_type == SignalType.GREED

    # Без сигнала
    signal_type = detector._get_signal_type_from_rsi(50)
    assert signal_type is None

    # Граничные случаи
    signal_type = detector._get_signal_type_from_rsi(35)
    assert signal_type == SignalType.PANIC

    signal_type = detector._get_signal_type_from_rsi(65)
    assert signal_type == SignalType.GREED