import streamlit as st


def create_overheat_bar(percentage, ticker=None):
    if percentage is None:
        return

    filled = int(percentage / 20)
    bars = "🟩" * filled + "⬜" * (5 - filled)

    col1, col2, col3 = st.columns([1, 3, 1])

    with col1:
        if ticker:
            st.write(ticker)

    with col2:
        st.progress(percentage / 100)
        st.caption(f"{bars} {percentage}%")

    with col3:
        if percentage > 80:
            st.write("🔥 Сильный")
        elif percentage > 60:
            st.write("🟡 Умеренный")
        else:
            st.write("🟢 Низкий")