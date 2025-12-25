import streamlit as st
import yaml
import os


def show():
    # ВСЁ что ниже должно быть с отступом

    st.title("⚙️ Настройка детектора")

    st.warning("Настройки сохраняются локально в config/panic_thresholds.yaml")

    # Раздел 1: Пороги обнаружения
    st.subheader("Пороги обнаружения паники")

    col1, col2 = st.columns(2)

    with col1:
        rsi_red = st.slider("RSI для красного уровня:", 20, 30, 25)
        rsi_yellow = st.slider("RSI для жёлтого уровня:", 25, 35, 30)
        rsi_white = st.slider("RSI для белого уровня:", 30, 40, 35)

    with col2:
        volume_red = st.slider("Объём для красного:", 1.5, 3.0, 2.0)
        volume_yellow = st.slider("Объём для жёлтого:", 1.2, 2.0, 1.5)
        volume_white = st.slider("Объём для белого:", 1.0, 1.8, 1.2)

    # Раздел 2: Фильтры
    st.subheader("Фильтры")
    filter_time = st.checkbox("Фильтр времени (11:00-16:00)", value=True)
    filter_volatility = st.checkbox("Фильтр волатильности", value=True)
    filter_trend = st.checkbox("Фильтр тренда", value=True)
    filter_spread = st.checkbox("Фильтр спреда", value=True)

    # Кнопки
    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button("💾 Сохранить настройки", type="primary"):
            config_data = {
                'panic_thresholds': {
                    'red': {'rsi_buy': rsi_red, 'rsi_sell': 75, 'volume_min': volume_red},
                    'yellow': {'rsi_buy': rsi_yellow, 'rsi_sell': 70, 'volume_min': volume_yellow},
                    'white': {'rsi_buy': rsi_white, 'rsi_sell': 65, 'volume_min': volume_white}
                }
            }

            try:
                config_path = os.path.join("config", "panic_thresholds.yaml")
                with open(config_path, 'w') as f:
                    yaml.dump(config_data, f)
                st.success("Настройки сохранены!")
            except Exception as e:
                st.error(f"Ошибка сохранения: {e}")

    with col_reset:
        if st.button("🔄 Сбросить к умолчаниям"):
            st.info("Значения сброшены к настройкам по умолчанию")
            st.rerun()

    st.divider()
    st.caption("Изменения вступят в силу после перезапуска сканера")


# Это должно остаться без отступа в конце файла
if __name__ == "__main__":
    show()