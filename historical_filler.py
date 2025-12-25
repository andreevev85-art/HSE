"""
Полноценный historical filler с 10-шаговой логикой Паникёра.
Обходит проверку времени, очищает БД, показывает детали каждого сигнала.
"""
import sys
import os
import sqlite3
import time
from datetime import datetime, timedelta
import pytz

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# ============================================================================
# 1. ОТКЛЮЧАЕМ ПРОВЕРКУ ВРЕМЕНИ (ПЕРЕД ИМПОРТОМ МОДУЛЕЙ)
# ============================================================================
import core.filters.time_filter as time_filter

original_time_check = time_filter.TimeFilter.check
time_filter.TimeFilter.check = lambda self, data: True  # Всегда True для исторических данных

print("=" * 60)
print("🎯 ПОЛНОЕ ИСТОРИЧЕСКОЕ НАПОЛНЕНИЕ БАЗЫ (10 ШАГОВ)")
print("=" * 60)


def load_tickers():
    """Загружаем тикеры из конфига"""
    try:
        import yaml
        with open('config/tickers.yaml', 'r') as f:
            config = yaml.safe_load(f)
        tickers = [item['ticker'] for item in config.get('tickers', [])]
        print(f"📋 Загружено {len(tickers)} тикеров")
        return tickers
    except:
        return ['SBER', 'GAZP', 'LKOH', 'GMKN', 'YDEX']


def calculate_indicators(prices, highs, lows, volumes):
    """Расчёт всех индикаторов для 10 шагов"""
    from core.indicators import safe_calculate_rsi, calculate_atr, calculate_sma

    calculate_rsi = safe_calculate_rsi

    # RSI с обработкой ошибок
    rsi_7 = calculate_rsi(prices, 7)
    rsi_14 = calculate_rsi(prices, 14)
    rsi_21 = calculate_rsi(prices, 21)

    # ATR с фильтрацией None
    atr_values = calculate_atr(highs, lows, prices, 14)
    valid_atr = [v for v in atr_values if v is not None]

    # SMA с фильтрацией None
    sma_20 = calculate_sma(prices, 20)
    valid_sma = [v for v in sma_20 if v is not None]

    # Значения по умолчанию
    rsi_7_val = rsi_7[-1] if rsi_7 and len(rsi_7) > 0 else 50.0
    rsi_14_val = rsi_14[-1] if rsi_14 and len(rsi_14) > 0 else 50.0
    rsi_21_val = rsi_21[-1] if rsi_21 and len(rsi_21) > 0 else 50.0

    current_atr = valid_atr[-1] if valid_atr else 2.0
    current_sma = valid_sma[-1] if valid_sma else prices[-1] if prices else 0

    # Средний ATR без None
    if valid_atr and len(valid_atr) >= 20:
        avg_atr = sum(valid_atr[-20:]) / 20
    else:
        avg_atr = current_atr

    # Объём
    current_volume = volumes[-1] if volumes else 0
    avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else current_volume
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

    return {
        'rsi_7': rsi_7_val,
        'rsi_14': rsi_14_val,
        'rsi_21': rsi_21_val,
        'atr': current_atr,
        'avg_atr': avg_atr,
        'sma_20': current_sma,
        'volume_ratio': volume_ratio,
        'current_volume': current_volume
    }

def determine_base_level(rsi_14, rsi_7, rsi_21):
    """ШАГ 5: Мультипериодная верификация → Базовый уровень"""
    # Определяем статусы
    rsi_14_status = 'OUTSIDE' if rsi_14 < 30 or rsi_14 > 70 else 'BORDER' if (25 <= rsi_14 <= 29) or (
                71 <= rsi_14 <= 75) else 'INSIDE'
    rsi_7_status = 'OUTSIDE' if rsi_7 < 30 or rsi_7 > 70 else 'INSIDE'
    rsi_21_status = 'OUTSIDE' if rsi_21 < 30 or rsi_21 > 70 else 'INSIDE'

    # Матрица решений (из проекта)
    if rsi_14_status == 'OUTSIDE' and rsi_7_status == 'OUTSIDE' and rsi_21_status == 'OUTSIDE':
        return 'STRONG'
    elif rsi_14_status == 'OUTSIDE' and (rsi_7_status == 'OUTSIDE' or rsi_21_status == 'OUTSIDE'):
        return 'GOOD'
    elif rsi_14_status == 'BORDER' and (rsi_7_status == 'OUTSIDE' or rsi_21_status == 'OUTSIDE'):
        return 'GOOD'
    elif rsi_14_status == 'BORDER':
        return 'URGENT'
    else:
        return 'IGNORE'


def apply_filters(indicators, price, spread_percent=0.05):
    """ШАГ 7: Применение контекстных фильтров"""
    filters_passed = 4
    filters_failed = []

    # Фильтр времени (у нас всегда пройден, так как отключен)

    # Фильтр волатильности (ATR > 0.8 × средний ATR)
    if indicators['atr'] <= 0.8 * indicators['avg_atr']:
        filters_passed -= 1
        filters_failed.append('Волатильность')

    # Фильтр тренда (покупать если цена > SMA20, продавать если < SMA20)
    # Упрощённо: считаем что RSI<30 = покупка, RSI>70 = продажа
    if indicators['rsi_14'] < 30 and price <= indicators['sma_20']:
        filters_passed -= 1
        filters_failed.append('Тренд')
    elif indicators['rsi_14'] > 70 and price >= indicators['sma_20']:
        filters_passed -= 1
        filters_failed.append('Тренд')

    # Фильтр спреда (спред < 0.1%)
    if spread_percent >= 0.1:
        filters_passed -= 1
        filters_failed.append('Спред')

    return filters_passed, filters_failed


def calculate_final_level(base_level, volume_ratio, filters_passed):
    """ШАГ 6-8: Коррекция объёмом и фильтрами → Финальный уровень"""
    level_map = {'STRONG': '🔴 СИЛЬНЫЙ', 'GOOD': '🟡 ХОРОШИЙ', 'URGENT': '⚪ СРОЧНЫЙ', 'IGNORE': '❌ ИГНОРИРОВАТЬ'}

    # Коррекция объёмом (ШАГ 6)
    if volume_ratio >= 2.0 and base_level != 'STRONG':
        if base_level == 'GOOD':
            base_level = 'STRONG'
        elif base_level == 'URGENT':
            base_level = 'GOOD'

    # Применение фильтров (ШАГ 7)
    filters_failed = 4 - filters_passed
    for _ in range(filters_failed):
        if base_level == 'STRONG':
            base_level = 'GOOD'
        elif base_level == 'GOOD':
            base_level = 'URGENT'
        elif base_level == 'URGENT':
            base_level = 'IGNORE'

    return level_map.get(base_level, '❌'), base_level


def analyze_full_10_steps(ticker_data, candle_date):
    """Полный 10-шаговый анализ для исторических данных"""
    # ШАГ 1: Пропускаем (время отключено)
    # ШАГ 2: Данные есть (проверено ранее)

    prices = ticker_data['historical_prices']
    volumes = ticker_data['historical_volumes']
    highs = ticker_data['historical_highs']
    lows = ticker_data['historical_lows']
    price = ticker_data['price']

    if len(prices) < 21:  # Нужно для RSI(21)
        return None

    # ШАГ 3-4: RSI(14) и Объём
    indicators = calculate_indicators(prices, highs, lows, volumes)

    # Базовые условия
    if not ((indicators['rsi_14'] < 30 or indicators['rsi_14'] > 70) and indicators['volume_ratio'] >= 1.5):
        return None

    # ШАГ 5: Мультипериодная верификация
    base_level = determine_base_level(
        indicators['rsi_14'],
        indicators['rsi_7'],
        indicators['rsi_21']
    )

    if base_level == 'IGNORE':
        return None

    # ШАГ 6: Коррекция объёмом (уже в calculate_final_level)

    # ШАГ 7: Контекстные фильтры
    filters_passed, filters_failed = apply_filters(indicators, price)

    # ШАГ 8: Финальное решение
    final_symbol, final_level = calculate_final_level(
        base_level,
        indicators['volume_ratio'],
        filters_passed
    )

    # ШАГ 9: Кластеры объёма (упрощённо)
    volume_clusters = 3 if indicators['volume_ratio'] > 2.0 else 2 if indicators['volume_ratio'] > 1.5 else 1

    # ШАГ 10: Риск-метрика
    risk_metric = (abs(indicators['rsi_14'] - 50) / 50) * indicators['volume_ratio']

    signal_type = 'ПАНИКА' if indicators['rsi_14'] < 30 else 'ЖАДНОСТЬ'

    return {
        'ticker': ticker_data['ticker'],
        'timestamp': candle_date,
        'signal_type': signal_type,
        'level': final_level,
        'level_symbol': final_symbol,
        'rsi_7': round(indicators['rsi_7'], 1),
        'rsi_14': round(indicators['rsi_14'], 1),
        'rsi_21': round(indicators['rsi_21'], 1),
        'volume_ratio': round(indicators['volume_ratio'], 2),
        'price': round(price, 2),
        'filters_passed': filters_passed,
        'filters_failed': filters_failed,
        'volume_clusters': volume_clusters,
        'risk_metric': round(risk_metric, 3)
    }


def clear_database():
    """Очистка базы данных перед наполнением"""
    print("🧹 Очищаем базу данных...")
    try:
        db_path = os.path.join('data', 'signals.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Удаляем все записи
        cursor.execute("DELETE FROM signals")

        # Сбрасываем автоинкремент (если используется)
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='signals'")

        conn.commit()
        conn.close()
        print("✅ База данных очищена")
    except Exception as e:
        print(f"❌ Ошибка очистки БД: {e}")


def process_ticker_full(ticker, days_back=30):
    """Полная обработка тикера с выводом деталей"""
    print(f"\n{'=' * 40}")
    print(f"🔍 АНАЛИЗ {ticker} (10 ШАГОВ)")
    print(f"{'=' * 40}")

    try:
        from data.tinkoff_client import TinkoffClient

        # Получаем исторические данные
        client = TinkoffClient()
        candles = client.get_candles(ticker, interval='day', count=days_back * 2)

        if len(candles) < 30:
            print(f"⚠️ Недостаточно данных ({len(candles)} свечей)")
            return 0

        # Подключаемся к БД
        db_path = os.path.join('data', 'signals.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        signals_found = 0

        # Анализируем каждый день (пропускаем первые 21 для индикаторов)
        for i in range(21, min(len(candles), 51)):  # 21 + 30 дней
            candle = candles[i]

            # Форматируем дату для вывода
            if hasattr(candle['time'], 'date'):
                date_str = candle['time'].date()
            else:
                date_str = str(candle['time'])[:10]

            print(f"\n📅 {date_str} | Цена: {candle['close']:.2f}₽")

            # Подготовка данных для анализа
            analysis_data = {
                'ticker': ticker,
                'price': candle['close'],
                'historical_prices': [c['close'] for c in candles[:i + 1]],
                'historical_volumes': [c['volume'] for c in candles[:i + 1]],
                'historical_highs': [c['high'] for c in candles[:i + 1]],
                'historical_lows': [c['low'] for c in candles[:i + 1]]
            }

            # Полный 10-шаговый анализ
            signal = analyze_full_10_steps(analysis_data, candle['time'])

            if signal:
                # Выводим детали сигнала
                print(f"   🎯 СИГНАЛ ОБНАРУЖЕН:")
                print(f"   ├── Тип: {signal['signal_type']}")
                print(f"   ├── Уровень: {signal['level_symbol']} {signal['level']}")
                print(f"   ├── RSI: {signal['rsi_14']} (7д={signal['rsi_7']}, 21д={signal['rsi_21']})")
                print(f"   ├── Объём: {signal['volume_ratio']}× от нормы")
                print(f"   ├── Фильтры: {signal['filters_passed']}/4 пройдено")
                print(f"   ├── Кластеры: {signal['volume_clusters']}")
                print(f"   └── Риск: {signal['risk_metric']}")

                for col_name, col_type in [('rsi_7', 'REAL'), ('rsi_21', 'REAL'),
                                           ('filters_passed', 'INTEGER'), ('volume_clusters', 'INTEGER'),
                                           ('risk_metric', 'REAL')]:
                    try:
                        cursor.execute(f"SELECT {col_name} FROM signals LIMIT 1")
                    except sqlite3.OperationalError:
                        cursor.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_type}")

                # Сохраняем в БД
                cursor.execute("""
                    INSERT INTO signals 
                    (ticker, timestamp, signal_type, level, rsi_14, volume_ratio, price, rsi_7, rsi_21, filters_passed, volume_clusters, risk_metric)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal['ticker'],
                    signal['timestamp'],
                    signal['signal_type'],
                    signal['level'],
                    signal['rsi_14'],
                    signal['volume_ratio'],
                    signal['price'],
                    signal['rsi_7'],
                    signal['rsi_21'],
                    signal['filters_passed'],
                    signal['volume_clusters'],
                    signal['risk_metric']
                ))

                signals_found += 1
                print(f"   💾 Сохранено в БД")
            else:
                print(f"   ⏭️  Нет сигнала")

        conn.commit()
        conn.close()

        print(f"\n📊 ИТОГ для {ticker}: {signals_found} сигналов")
        return signals_found

    except Exception as e:
        print(f"❌ Ошибка обработки {ticker}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """Основная функция"""
    # Очищаем БД
    clear_database()

    # Загружаем тикеры
    tickers = load_tickers()
    print(f"\n📊 Тикеры для анализа: {', '.join(tickers)}")

    # Обработка
    total_signals = 0
    start_time = time.time()

    for ticker in tickers:
        signals = process_ticker_full(ticker, days_back=30)
        total_signals += signals
        time.sleep(0.5)  # Пауза между запросами

    # Итоги
    print(f"\n{'=' * 60}")
    print(f"🎯 ФИНАЛЬНЫЕ ИТОГИ НАПОЛНЕНИЯ БАЗЫ")
    print(f"{'=' * 60}")
    print(f"✅ Тикеров обработано: {len(tickers)}")
    print(f"✅ Всего сигналов найдено: {total_signals}")
    print(f"✅ Среднее на тикер: {total_signals / len(tickers) if tickers else 0:.1f}")
    print(f"⏱️  Общее время: {time.time() - start_time:.1f}с")

    # Показываем пример данных из БД
    try:
        db_path = os.path.join('data', 'signals.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Статистика по уровням
        cursor.execute("""
            SELECT level, COUNT(*) as count 
            FROM signals 
            GROUP BY level 
            ORDER BY CASE level 
                WHEN 'STRONG' THEN 1 
                WHEN 'GOOD' THEN 2 
                WHEN 'URGENT' THEN 3 
                ELSE 4 
            END
        """)
        level_stats = cursor.fetchall()

        print(f"\n📈 СТАТИСТИКА ПО УРОВНЯМ:")
        for level, count in level_stats:
            level_symbol = {'STRONG': '🔴', 'GOOD': '🟡', 'URGENT': '⚪', 'IGNORE': '❌'}.get(level, '?')
            print(f"   {level_symbol} {level}: {count} сигналов")

        # Последние 3 сигнала
        cursor.execute("""
            SELECT ticker, timestamp, signal_type, level, rsi_14, volume_ratio 
            FROM signals 
            ORDER BY timestamp DESC 
            LIMIT 3
        """)
        recent_signals = cursor.fetchall()

        if recent_signals:
            print(f"\n📅 ПОСЛЕДНИЕ СИГНАЛЫ В БАЗЕ:")
            for signal in recent_signals:
                ticker, timestamp, sig_type, level, rsi, vol = signal
                level_symbol = {'STRONG': '🔴', 'GOOD': '🟡', 'URGENT': '⚪', 'IGNORE': '❌'}.get(level, '?')
                date_str = str(timestamp)[:10] if isinstance(timestamp, str) else timestamp[:10]
                print(f"   {level_symbol} {ticker} | {date_str} | {sig_type} | RSI={rsi:.1f} | Объём={vol:.1f}×")

        conn.close()

    except Exception as e:
        print(f"\n⚠️  Не удалось прочитать статистику БД: {e}")

    # ============================================================================
    # ВОССТАНАВЛИВАЕМ ПРОВЕРКУ ВРЕМЕНИ
    # ============================================================================
    time_filter.TimeFilter.check = original_time_check

    print(f"\n{'=' * 60}")
    print(f"✅ ИСТОРИЧЕСКОЕ НАПОЛНЕНИЕ БАЗЫ ЗАВЕРШЕНО")
    print(f"📋 Проверьте бота: python bot/telegram_panicker.py")
    print(f"📊 Проверьте команды: /today, /stats, /overheat SBER")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Прервано пользователем")
        # Восстанавливаем проверку времени
        time_filter.TimeFilter.check = original_time_check
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        # Восстанавливаем проверку времени
        time_filter.TimeFilter.check = original_time_check