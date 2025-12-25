import streamlit as st
import pandas as pd


def create_panic_map(signals_by_hour):
    if not signals_by_hour:
        st.info("Нет данных для карты")
        return

    df = pd.DataFrame(signals_by_hour)

    heatmap_data = df.pivot_table(
        index='ticker',
        columns='hour',
        values='level',
        aggfunc='first',
        fill_value='⚪'
    )

    st.dataframe(
        heatmap_data,
        use_container_width=True,
        height=400
    )

    st.caption("⚪ = нет сигналов | 🟡 = умеренный | 🔴 = сильный")