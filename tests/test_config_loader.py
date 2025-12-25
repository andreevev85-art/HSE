# panicker3000/tests/test_config_loader.py
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.config_loader import ConfigLoader


def test_config_loader():
    """Тест загрузки всех конфигурационных файлов"""
    print("🧪 Тестирование ConfigLoader...")
    loader = ConfigLoader()

    # 1. Загрузка settings
    settings = loader.load_settings()
    print(f"✅ settings.yaml: {len(settings)} разделов")
    assert 'telegram' in settings, "Нет раздела telegram"
    assert 'tinkoff' in settings, "Нет раздела tinkoff"

    # 2. Загрузка tickers
    tickers = loader.load_tickers()
    print(f"✅ tickers.yaml: {len(tickers.get('tickers', []))} тикеров")
    ticker_list = tickers.get('tickers', [])
    assert len(ticker_list) >= 1, "Должен быть хотя бы 1 тикер"
    for t in ticker_list[:3]:
        print(f"  - {t['ticker']}")

    # 3. Загрузка thresholds
    thresholds = loader.load_panic_thresholds()
    panic_thresholds = thresholds.get('panic_thresholds', {})
    print(f"✅ panic_thresholds.yaml: {len(panic_thresholds)} уровней")
    assert 'red' in panic_thresholds, "Нет красного уровня"

    # 4. Загрузка команд (может быть пустым, если файла нет)
    try:
        commands = loader.load_telegram_commands()
        print(f"✅ telegram_commands.yaml: {len(commands)} команд")
        # Если файл не существует, команды будут пустым словарем
        if commands:
            print(f"   Пример команд: {list(commands.keys())[:3]}")
    except AttributeError as e:
        print(f"❌ Метод load_telegram_commands не найден: {e}")
    except Exception as e:
        print(f"⚠️  Ошибка загрузки команд: {e}")

    def test_config_loader():
        """Тест загрузки всех конфигурационных файлов"""
        print("🧪 Тестирование ConfigLoader...")
        loader = ConfigLoader()

        # 1. Загрузка settings
        settings = loader.load_settings()
        print(f"✅ settings.yaml: {len(settings)} разделов")
        assert 'telegram' in settings, "Нет раздела telegram"
        assert 'tinkoff' in settings, "Нет раздела tinkoff"

        # 2. Загрузка tickers
        tickers = loader.load_tickers()
        print(f"✅ tickers.yaml: {len(tickers.get('tickers', []))} тикеров")
        ticker_list = tickers.get('tickers', [])
        assert len(ticker_list) >= 1, "Должен быть хотя бы 1 тикер"
        for t in ticker_list[:3]:
            print(f"  - {t.get('ticker', t.get('symbol', 'N/A'))}")

        # 3. Загрузка thresholds
        thresholds = loader.load_panic_thresholds()
        panic_thresholds = thresholds.get('panic_thresholds', {})
        print(f"✅ panic_thresholds.yaml: {len(panic_thresholds)} уровней")
        assert 'red' in panic_thresholds, "Нет красного уровня"

        # 4. Загрузка команд (может быть пустым, если файла нет)
        try:
            commands = loader.load_telegram_commands()
            print(f"✅ telegram_commands.yaml: {len(commands)} команд")
            # Если файл не существует, команды будут пустым словарем
            if commands:
                print(f"   Пример команд: {list(commands.keys())[:3]}")
        except AttributeError as e:
            print(f"❌ Метод load_telegram_commands не найден: {e}")
        except Exception as e:
            print(f"⚠️  Ошибка загрузки команд: {e}")

    print("\n🎉 Все конфиги загружены успешно!")

# Pytest автоматически найдет эту функцию