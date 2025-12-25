import streamlit as st
import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def show():
    st.title("⚙️ Настройка детектора")

    # Загружаем текущие настройки
    try:
        config_path = os.path.join("config", "panic_thresholds.yaml")
        with open(config_path, 'r', encoding='utf-8') as f:
            current_config = yaml.safe_load(f)

        thresholds = current_config.get('panic_thresholds', {})
        red = thresholds.get('red', {'rsi_buy': 25, 'volume_min': 2.0})
        yellow = thresholds.get('yellow', {'rsi_buy': 30, 'volume_min': 1.5})
        white = thresholds.get('white', {'rsi_buy': 35, 'volume_min': 1.2})
    except:
        red = {'rsi_buy': 25, 'volume_min': 2.0}
        yellow = {'rsi_buy': 30, 'volume_min': 1.5}
        white = {'rsi_buy': 35, 'volume_min': 1.2}

    st.subheader("Пороги обнаружения паники")

    col1, col2 = st.columns(2)

    with col1:
        rsi_red = st.slider("RSI для 🔴 уровня:", 20, 30, red['rsi_buy'])
        rsi_yellow = st.slider("RSI для 🟡 уровня:", 25, 35, yellow['rsi_buy'])
        rsi_white = st.slider("RSI для ⚪ уровня:", 30, 40, white['rsi_buy'])

    with col2:
        volume_red = st.slider("Объём для 🔴:", 1.5, 3.0, red['volume_min'])
        volume_yellow = st.slider("Объём для 🟡:", 1.2, 2.0, yellow['volume_min'])
        volume_white = st.slider("Объём для ⚪:", 1.0, 1.8, white['volume_min'])

    st.subheader("Фильтры")
    filter_time = st.checkbox("Фильтр времени (11:00-16:00)", value=True)
    filter_volatility = st.checkbox("Фильтр волатильности", value=True)
    filter_trend = st.checkbox("Фильтр тренда", value=True)
    filter_spread = st.checkbox("Фильтр спреда", value=True)

    col_save, col_reset = st.columns(2)

    with col_save:
        if st.button("💾 Сохранить настройки", type="primary", use_container_width=True):
            config_data = {
                'panic_thresholds': {
                    'red': {'rsi_buy': rsi_red, 'rsi_sell': 75, 'volume_min': volume_red},
                    'yellow': {'rsi_buy': rsi_yellow, 'rsi_sell': 70, 'volume_min': volume_yellow},
                    'white': {'rsi_buy': rsi_white, 'rsi_sell': 65, 'volume_min': volume_white}
                }
            }

            try:
                os.makedirs("config", exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
                st.success("✅ Настройки сохранены в config/panic_thresholds.yaml")
            except Exception as e:
                st.error(f"❌ Ошибка сохранения: {e}")

    with col_reset:
        if st.button("🔄 Сбросить к умолчаниям", use_container_width=True):
            st.info("Значения сброшены. Обновите страницу.")

    st.divider()
    st.caption("Изменения вступят в силу после перезапуска сканера")


if __name__ == "__main__":
    show()