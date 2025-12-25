
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(
    page_title="История истерик",
    page_icon="📈",
    layout="wide"
)

st.title("📈 История истерик")

# Предупреждение о тестовых данных
st.warning("""
⚠️ **Внимание:** На этой странице отображаются РЕАЛЬНЫЕ сигналы из системы.
Если сигналов нет - значит система еще не обнаружила панических ситуаций.
Работайте в часы торгов на Мосбирже для получения актуальных данных.
""")

# Получаем данные через gRPC
try:
    from grpc_service.grpc_client import get_grpc_client

    # Создаем колонки для выбора
    col1, col2 = st.columns(2)

    with col1:
        ticker = st.selectbox(
            "Выберите тикер:",
            ["SBER", "GAZP", "LKOH", "GMKN", "YNDX", "ROSN", "NVTK", "TATN", "MTSS", "ALRS"]
        )

    with col2:
        days_back = st.slider("Дней назад:", 1, 30, 7)

    # Получаем историю через gRPC
    if st.button("🔄 Обновить историю", type="primary"):
        with st.spinner("Получение данных..."):
            try:
                client = get_grpc_client()
                history = client.get_signal_history(ticker, days_back)

                if history:
                    st.success(f"📊 Найдено {len(history)} сигналов")

                    # Преобразуем в DataFrame для удобства
                    df_data = []
                    for signal in history:
                        df_data.append({
                            'Тикер': signal.get('ticker', ''),
                            'Дата': signal.get('timestamp', ''),
                            'Тип': signal.get('signal_type', ''),
                            'Уровень': signal.get('level', ''),
                            'RSI': signal.get('rsi_14', 0),
                            'Объём': signal.get('volume_ratio', 0),
                            'Цена': signal.get('current_price', 0)
                        })

                    df = pd.DataFrame(df_data)

                    # Отображаем таблицу
                    st.dataframe(
                        df,
                        use_container_width=True,
                        column_config={
                            "Цена": st.column_config.NumberColumn(format="%.2f ₽"),
                            "RSI": st.column_config.NumberColumn(format="%.1f"),
                            "Объём": st.column_config.NumberColumn(format="%.1f ×")
                        }
                    )

                    # Отображаем карточки
                    st.subheader("📋 Детали сигналов")

                    for i, signal in enumerate(history, 1):
                        level = signal.get('level', '')
                        level_emoji = '🔴' if 'СИЛЬНЫЙ' in level else '🟡' if 'ХОРОШИЙ' in level else '⚪'

                        with st.container():
                            col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 2])

                            with col_a:
                                st.metric(
                                    label=f"{level_emoji} {signal.get('signal_type', 'ПАНИКА')}",
                                    value=signal.get('ticker', '')
                                )

                            with col_b:
                                st.metric(
                                    label="RSI",
                                    value=f"{signal.get('rsi_14', 0):.1f}"
                                )

                            with col_c:
                                st.metric(
                                    label="Объём",
                                    value=f"{signal.get('volume_ratio', 0):.1f}×"
                                )

                            with col_d:
                                st.metric(
                                    label="Цена",
                                    value=f"{signal.get('current_price', 0):.2f}₽"
                                )

                        st.divider()

                else:
                    st.info(f"ℹ️ Сигналов для {ticker} за последние {days_back} дней не найдено")

            except Exception as e:
                st.error(f"❌ Ошибка получения данных: {e}")

    # Прямая проверка реальной цены
    st.divider()
    st.subheader("🔍 Проверка текущей цены")

    if st.button("Проверить текущую цену"):
        try:
            from data.tinkoff_client import TinkoffClient
            client = TinkoffClient()
            current_price = client.get_last_price(ticker)

            if current_price:
                st.success(f"✅ Текущая цена {ticker}: **{current_price:.2f}₽**")
                if current_price < 200:
                    st.warning(f"⚠️  Цена подозрительно низкая! Проверьте режим работы API.")
                else:
                    st.info(f"✅ Цена соответствует рыночной (~{current_price:.2f}₽)")
            else:
                st.error(f"❌ Не удалось получить цену {ticker}")

        except Exception as e:
            st.error(f"❌ Ошибка: {e}")

except ImportError as e:
    st.error(f"❌ Ошибка импорта модулей: {e}")
    st.info("""
    🔧 **Решение проблемы:**
    1. Убедитесь что gRPC сервер запущен: `python run_scanner.py`
    2. Проверьте наличие файлов в папке `grpc_service/`
    3. Перезапустите dashboard
    """)

# Информация о системе
with st.expander("ℹ️ Информация о системе"):
    st.write("""
    **История истерик** - страница для просмотра обнаруженных системой сигналов паники/жадности.

    **Как это работает:**
    1. Система анализирует данные в реальном времени
    2. При обнаружении сигнала он сохраняется в базу данных
    3. На этой странице отображается история сохранённых сигналов

    **Если сигналов нет:**
    - Торги на бирже не ведутся
    - Не было обнаружено сигналов паники/жадности
    - База данных пуста (первый запуск)
    """)
