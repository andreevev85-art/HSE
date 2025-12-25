# tests/test_transaction_costs.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.panic_detector import PanicDetector


class MockConfigLoader:
    def load_panic_thresholds(self):
        return {'panic_thresholds': {
            'red': {'rsi_buy': 25, 'rsi_sell': 75, 'volume_min': 2.0},
            'yellow': {'rsi_buy': 30, 'rsi_sell': 70, 'volume_min': 1.5},
            'white': {'rsi_buy': 35, 'rsi_sell': 65, 'volume_min': 1.2}
        }}


def test_transaction_costs():
    """Тест транзакционных издержек"""
    config_loader = MockConfigLoader()
    detector = PanicDetector(config_loader)

    # Проверяем атрибуты
    assert detector.commission == 0.0005
    assert detector.slippage == 0.001

    # Тестируем calculate_net_return
    test_cases = [
        (0.10, 0.0980),  # 10% → 9.80% (0.10 - 0.002 = 0.098)
        (0.05, 0.0480),  # 5% → 4.80% (0.05 - 0.002 = 0.048)
        (0.00, -0.0020),  # 0% → -0.20% (0.00 - 0.002 = -0.002)
        (-0.05, -0.0520),  # -5% → -5.20% (-0.05 - 0.002 = -0.052)
        (-0.50, -0.5020),  # -50% → -50.20% (-0.50 - 0.002 = -0.502)
        (-0.99, -0.9920),  # -99% → -99.20% (-0.99 - 0.002 = -0.992)
        (-1.00, -0.999),  # -100% → -99.9% (ограничение сработает)
    ]

    for gross, expected in test_cases:
        net = detector.calculate_net_return(gross)
        assert abs(net - expected) < 0.0001, f"calculate_net_return({gross}) = {net}, ожидалось {expected}"

    print("✅ Все тесты транзакционных издержек пройдены")


if __name__ == "__main__":
    test_transaction_costs()