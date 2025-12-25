# panicker3000/core/filters/__init__.py
"""
Фильтры для проверки контекста сигналов.
Каждый фильтр — отдельный класс с методом check().
"""

# Добавьте в начало файла:
if __name__ == "__main__":
    print("Это модуль импортов, не запускайте его напрямую")
    exit(1)

# Остальной код:
try:
    from .time_filter import TimeFilter
    from .volume_filter import VolumeFilter
    from .volatility_filter import VolatilityFilter
    from .trend_filter import TrendFilter

    __all__ = [
        'TimeFilter',
        'VolumeFilter',
        'VolatilityFilter',
        'TrendFilter'
    ]

except ImportError as e:
    # Если некоторые модули ещё не созданы
    print(f"Предупреждение при импорте фильтров: {e}")
    __all__ = []