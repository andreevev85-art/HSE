import streamlit as st
import sys
import os
import importlib
from datetime import datetime

# Добавляем путь к корню проекта
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from grpc_service.grpc_client import get_grpc_client

    GRPC_AVAILABLE = True
except ImportError as e:
    st.error(f"❌ Не удалось импортировать gRPC клиент: {e}")
    GRPC_AVAILABLE = False


# Инициализация gRPC клиента
@st.cache_resource
def get_client():
    if GRPC_AVAILABLE:
        try:
            client = get_grpc_client()
            return client
        except Exception as e:
            st.error(f"❌ Ошибка подключения к gRPC серверу: {e}")
            return None
    return None


grpc_client = get_client()

st.set_page_config(
    page_title="Паникёр 3000",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Получаем текущее время для статуса
now = datetime.now()
market_open = 10 <= now.hour < 19
time_to_close = 19 - now.hour if market_open else 0

# Верхняя панель
st.markdown(f"""
<div style="background-color:#1E1E1E;padding:10px;border-radius:10px;margin-bottom:20px">
    <h1 style="color:#FF4B4B;text-align:center;margin:0">🚨 ПАНИКЁР 3000 | ПУНКТ УПРАВЛЕНИЯ ПАНИКОЙ</h1>
    <div style="color:#FFFFFF;text-align:center;font-size:14px">
        Версия: 1.0 | Последнее обновление: {now.strftime('%H:%M:%S')} | Уровень тревоги: 🟡 ПОВЫШЕННЫЙ
    </div>
</div>
""", unsafe_allow_html=True)

# Боковая панель
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/panic.png", width=100)
    st.title("Навигация")

    page = st.radio(
        "Выберите раздел:",
        [
            "🚨 Текущие паники",
            "📊 Карта паники",
            "📈 История истерик",
            "📊 Индекс перегрева",
            "⚙️ Настройка детектора",
            "📋 Отчёты и статистика",
            "❓ Справка и обучение"
        ]
    )

    st.markdown("---")
    st.markdown("**Статус системы:**")

    status_col1, status_col2, status_col3 = st.columns(3)

    with status_col1:
        if grpc_client and GRPC_AVAILABLE:
            st.success("🟢 gRPC активен")
        else:
            st.error("🔴 gRPC ошибка")

    with status_col2:
        if market_open:
            st.success(f"🟢 Биржа открыта")
        else:
            st.warning("🔴 Биржа закрыта")

    with status_col3:
        if grpc_client and GRPC_AVAILABLE and market_open:
            try:
                # Пытаемся получить количество сигналов
                import yaml

                config_path = os.path.join("config", "tickers.yaml")
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                tickers = []
                for item in config.get('tickers', []):
                    if isinstance(item, dict) and 'ticker' in item:
                        tickers.append(item['ticker'])

                if tickers:
                    signals = grpc_client.scan_tickers(tickers[:3])  # Проверяем только первые 3
                    signal_count = len([s for s in signals if
                                        isinstance(s, dict) and s.get('level') not in ['❌ ИГНОРИРОВАТЬ', 'НЕИЗВЕСТНО']])
                    st.info(f"📊 Сигналов: {signal_count}")
                else:
                    st.info("📊 Сигналов: N/A")
            except:
                st.info("📊 Сигналов: N/A")
        else:
            st.info("📊 Сигналов: N/A")

    st.markdown("---")

    if market_open:
        st.markdown(f"**До закрытия:** {time_to_close}:{59 - now.minute:02d}")
    else:
        opens_at = 10 if now.hour >= 19 else 10
        st.markdown(f"**Открывается в:** {opens_at}:00")

    st.markdown("---")

    if st.button("🔄 Обновить данные", use_container_width=True):
        st.rerun()

# Динамическая загрузка страниц
try:
    pages_dir = os.path.join(os.path.dirname(__file__), "pages")

    # Для основных страниц с отдельными модулями
    if page in ["🚨 Текущие паники", "📊 Карта паники", "📈 История истерик",
                "📊 Индекс перегрева", "⚙️ Настройка детектора"]:

        # Определяем путь к модулю
        page_map = {
            "🚨 Текущие паники": "1_🚨_Текущие_паники.py",
            "📊 Карта паники": "2_📊_Карта_паники.py",
            "📈 История истерик": "3_📈_История_истерик.py",
            "📊 Индекс перегрева": "4_📊_Индекс_перегрева.py",
            "⚙️ Настройка детектора": "5_⚙️_Настройка_детектора.py"
        }

        module_path = os.path.join(pages_dir, page_map[page])

        if os.path.exists(module_path):
            try:
                spec = importlib.util.spec_from_file_location("page_module", module_path)
                page_module = importlib.util.module_from_spec(spec)
                sys.modules["page_module"] = page_module
                spec.loader.exec_module(page_module)
                if hasattr(page_module, 'show'):
                    page_module.show()
                else:
                    st.error(f"❌ Модуль {page} не содержит функцию 'show'")
            except Exception as e:
                st.error(f"❌ Ошибка загрузки страницы {page}: {e}")
                import traceback

                st.code(traceback.format_exc())
        else:
            st.error(f"❌ Файл {module_path} не найден")

    elif page == "📋 Отчёты и статистика":
        st.title("📋 Отчёты и статистика")

        if grpc_client and GRPC_AVAILABLE:
            try:
                stats = grpc_client.get_stats(days=7)
                st.success(f"📊 Статистика за 7 дней")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Всего сигналов", stats.get('total_signals', 'N/A'))
                with col2:
                    st.metric("🔴 Сильных", stats.get('strong_signals', 'N/A'))
                with col3:
                    st.metric("🟡 Умеренных", stats.get('moderate_signals', 'N/A'))
                with col4:
                    st.metric("⚪ Срочных", stats.get('urgent_signals', 'N/A'))

                col5, col6 = st.columns(2)
                with col5:
                    st.metric("Самый активный", f"{stats.get('most_active_ticker', 'N/A')}")
                    st.caption(f"({stats.get('most_active_count', 0)} сигналов)")
                with col6:
                    st.metric("Самый спокойный", f"{stats.get('most_calm_ticker', 'N/A')}")
                    st.caption(f"({stats.get('most_calm_count', 0)} сигналов)")

                st.divider()
                st.subheader("📈 Напряжённость рынка")
                tension = stats.get('market_tension', 'НЕИЗВЕСТНО')
                if tension == '🔴 ВЫСОКАЯ':
                    st.error(f"🔴 {tension}")
                elif tension == '🟡 УМЕРЕННАЯ':
                    st.warning(f"🟡 {tension}")
                elif tension == '🟢 СПОКОЙНАЯ':
                    st.success(f"🟢 {tension}")
                else:
                    st.info(f"📊 {tension}")

            except Exception as e:
                st.error(f"❌ Ошибка получения статистики: {e}")
        else:
            st.warning("⚠️ gRPC недоступен. Статистика недоступна.")

    else:  # Справка и обучение
        st.title("❓ Справка и обучение")

        tab1, tab2, tab3 = st.tabs(["📋 Общее", "🤖 Бот", "🖥 Дашборд"])

        with tab1:
            st.markdown("""
                ### 🎯 Назначение системы
                **Паникёр 3000** - система обнаружения рыночных аномалий на Мосбирже.

                ### ⏰ Время работы
                - **Биржа:** 10:00-18:30 МСК
                - **Сканирование:** каждые 60 секунд
                - **Отчёт:** ежедневно в 18:30

                ### 🚀 Запуск
                ```bash
                python run_scanner.py
                ```
                """)

        with tab2:
            st.markdown("""
                ### 🤖 Telegram-бот команды:

                **Основные:**
                - `/start` - главное меню
                - `/overheat [тикер]` - индекс перегрева акции
                - `/today` - все сигналов за сегодня
                - `/stats` - статистика за неделю
                - `/panicmap` - карта паники

                **Служебные:**
                - `/alerts on/off` - вкл/выкл уведомления
                - `/startscan` - возобновить сканирование
                - `/extreme` - самые сильные сигналов
                """)

        with tab3:
            st.markdown("""
                ### 🖥 Дашборд разделы:

                **🚨 Текущие паники** - активные сигналы прямо сейчас

                **📊 Карта паники** - тепловая карта активности за день

                **📈 История истерик** - архив сигналов по тикерам

                **📊 Индекс перегрева** - состояние всех акций

                **⚙️ Настройка детектора** - кастомизация параметров

                **📋 Отчёты и статистика** - аналитика за неделю
                """)

except Exception as e:
    st.error(f"❌ Ошибка при загрузке страницы: {e}")
    import traceback

    st.code(traceback.format_exc())

st.markdown("---")
st.caption(
    f"Система обнаружения рыночных аномалий | Данные обновляются в реальном времени | {now.strftime('%d.%m.%Y %H:%M:%S')}")

if not market_open:
    st.warning(f"⚠️ Биржа закрыта. Торговая сессия: 10:00-19:00 МСК. Следующее открытие в 10:00.")