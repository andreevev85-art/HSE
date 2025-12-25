"""
Тест для проверки цен и данных по всем тикерам проекта.
"""
import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.tinkoff_client import TinkoffClient

def load_tickers():
    """Загружает список тикеров из конфигурационного файла."""
    try:
        config_path = os.path.join('config', 'tickers.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        tickers = [item['ticker'] for item in config.get('tickers', [])]
        print(f"📋 Загружено {len(tickers)} тикеров из конфига.")
        return tickers
    except Exception as e:
        print(f"⚠️ Не удалось загрузить конфиг: {e}. Используем тестовый набор.")
        return ['SBER', 'GAZP', 'LKOH', 'GMKN', 'YNDX', 'VTBR', 'TATN', 'ROSN']

def test_all_tickers():
    print("🔧 Тест данных для всех тикеров проекта")
    print("=" * 50)

    try:
        client = TinkoffClient()
        print("✅ Клиент инициализирован\n")

        tickers = load_tickers()

        for ticker in tickers:
            print(f"➡️  Проверка {ticker}...")
            price = client.get_last_price(ticker)

            if price:
                print(f"   ✅ Цена: {price:.2f}₽")
                # *Опционально*: Получение полных данных для анализа (RSI, объем)
                # data = client.get_ticker_data(ticker)
                # if data:
                #     print(f"   📊 RSI14: {data.get('rsi_14', 0):.1f}, Объём: {data.get('volume_ratio', 0):.1f}×")
            else:
                print(f"   ❌ Не удалось получить цену")

            print()  # Пустая строка для читаемости

        print("=" * 50)
        print("✅ Тест завершен. Все доступные тикеры проверены.")

    except Exception as e:
        print(f"\n❌ Критическая ошибка теста: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_all_tickers()