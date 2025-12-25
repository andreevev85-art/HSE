#!/usr/bin/env python3
"""
Ярлык для запуска дашборда Паникёра 3000
Запуск: python run_dashboard.py
"""

import subprocess
import sys
import os


def main():
    """Запуск Streamlit дашборда"""
    print("🚀 Запуск дашборда Паникёр 3000...")
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print(f"🐍 Python: {sys.executable}")
    print("🌐 Откройте: http://localhost:8501")
    print("-" * 50)

    # Команда запуска Streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        "dashboard/app.py",
        "--server.port=8501",
        "--server.headless=false",
        "--theme.base=dark"
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Дашборд остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()