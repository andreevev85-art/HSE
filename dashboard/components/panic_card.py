import streamlit as st


def create_panic_card(signal):
    if not signal or not isinstance(signal, dict):
        return

    level = signal.get('level', '')

    if '🔴' in level:
        bg_color = "#2A0A0A"  # Тёмно-красный (почти бордовый)
        border_color = "#660000"
        emoji = "🔴"
    elif '🟡' in level:
        bg_color = "#332900"  # Тёмно-жёлтый
        border_color = "#665200"
        emoji = "🟡"
    else:
        bg_color = "#1A1A1A"  # Тёмно-серый
        border_color = "#444444"
        emoji = "⚪"

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f"""
        <div style="background-color:{bg_color};padding:15px;border-radius:10px;border:2px solid {border_color};margin-bottom:10px">
            <h4 style="margin:0;color:white">{emoji} {level}: {signal.get('ticker', 'N/A')}</h4>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        rsi = signal.get('rsi_14', 0)
        st.metric("RSI", f"{rsi:.1f}")

    col3, col4 = st.columns(2)

    with col3:
        volume = signal.get('volume_ratio', 0)
        st.metric("Объём", f"{volume:.1f}×")

    with col4:
        price = signal.get('current_price', 0)
        st.metric("Цена", f"{price:.2f}₽")

    return signal.get('ticker')