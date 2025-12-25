# panicker3000/tests/test_tinkoff_client.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.tinkoff_client import TinkoffClient


def test_client():
    print("🔧 Тест TinkoffClient...")

    try:
        client = TinkoffClient()
        print("✅ Клиент создан")

        # Тест 1: Реальная цена SBER
        price = client.get_last_price('SBER')
        if price:
            print(f"✅ Цена SBER: {price:.2f}₽")
            if 200 <= price <= 400:
                print("✅ Цена в реалистичном диапазоне")
            else:
                print(f"⚠️  Цена вне обычного диапазона ({price:.2f}₽)")
        else:
            print("❌ Не удалось получить цену SBER")
            return False

        # Тест 2: Полные данные
        data = client.get_ticker_data('SBER')
        if data:
            print(f"✅ Данные SBER получены")
            print(f"   Цена: {data.get('price', 0):.2f}₽")
            print(f"   RSI14: {data.get('rsi_14', 0):.1f}")
            print(f"   Объём: {data.get('volume_ratio', 0):.1f}×")
            return True
        else:
            print("❌ Не удалось получить данные SBER")
            return False

    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_client()
    sys.exit(0 if success else 1)