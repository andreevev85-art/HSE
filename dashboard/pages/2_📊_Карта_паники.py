import streamlit as st
import sys
import os
import yaml
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_tickers():
    try:
        config_path = os.path.join("config", "tickers.yaml")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        tickers = []
        for item in config.get('tickers', []):
            if isinstance(item, dict) and 'ticker' in item:
                tickers.append(item['ticker'])
        return tickers
    except:
        return []


def show():
    st.title("📊 Карта паники")

    try:
        from grpc_service.grpc_client import get_grpc_client
        grpc_client = get_grpc_client()
        GRPC_AVAILABLE = True
    except ImportError:
        GRPC_AVAILABLE = False
        grpc_client = None

    if grpc_client and GRPC_AVAILABLE:
        try:
            tickers = load_tickers()
            today_signals = []

            for ticker in tickers:
                history = grpc_client.get_signal_history(ticker, days_back=1)
                for signal in history:
                    if isinstance(signal, dict) and signal.get('detected_at'):
                        today_signals.append(signal)

            if today_signals:
                st.success(f"📅 Сигналов за сегодня: {len(today_signals)}")

                import pandas as pd
                df = pd.DataFrame(today_signals)
                df['hour'] = pd.to_datetime(df['detected_at']).dt.hour

                pivot = df.pivot_table(
                    index='ticker',
                    columns='hour',
                    values='level',
                    aggfunc=lambda x: x.iloc[0] if len(x) > 0 else '⚪',
                    fill_value='⚪'
                )

                st.dataframe(pivot, use_container_width=True, height=400)
                st.caption("⚪ = нет сигналов | 🟡 = умеренный | 🔴 = сильный")
            else:
                st.info("📅 Сегодня сигналов не было")

        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
    else:
        st.warning("⚠️ gRPC недоступен")


if __name__ == "__main__":
    show()