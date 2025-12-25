import streamlit as st
import sys
import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_tickers():
    """Загрузка тикеров из конфига"""
    try:
        config_path = os.path.join("config", "tickers.yaml")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        tickers = []
        for item in config.get('tickers', []):
            if isinstance(item, dict) and 'ticker' in item:
                tickers.append(item['ticker'])
            elif isinstance(item, str):
                tickers.append(item)

        return tickers if tickers else []
    except Exception as e:
        st.error(f"Ошибка загрузки тикеров: {e}")
        return []


def show():
    st.title("🚨 Текущие паники")

    try:
        from grpc_service.grpc_client import get_grpc_client
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "components"))
        from panic_card import create_panic_card
        grpc_client = get_grpc_client()
        GRPC_AVAILABLE = True
    except ImportError as e:
        GRPC_AVAILABLE = False
        grpc_client = None
        st.error(f"❌ gRPC клиент не доступен: {e}")

    if grpc_client and GRPC_AVAILABLE:
        try:
            tickers = load_tickers()
            if not tickers:
                st.warning("⚠️ Нет тикеров для сканирования. Проверьте config/tickers.yaml")
                return

            signals = grpc_client.scan_tickers(tickers)
            active_signals = [s for s in signals if
                              isinstance(s, dict) and s.get('level') not in ['❌ ИГНОРИРОВАТЬ', 'НЕИЗВЕСТНО']]

            if active_signals:
                st.success(f"✅ Найдено {len(active_signals)} активных сигналов")
                for signal in active_signals:
                    create_panic_card(signal)
                    st.divider()
            else:
                st.info("ℹ️ Активных сигналов нет")

        except Exception as e:
            st.error(f"❌ Ошибка получения сигналов: {str(e)}")
    else:
        st.warning("⚠️ gRPC недоступен. Запустите gRPC сервер.")

    if st.button("🔄 Обновить", type="primary"):
        st.rerun()


if __name__ == "__main__":
    show()