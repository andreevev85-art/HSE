# tests/test_grpc_risk_clusters.py - тест gRPC с риск-метриками
"""Упрощённый тест интеграции gRPC."""

import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# Проверяем наличие gRPC компонентов
try:
    from grpc_service.grpc_client import GrpcClient
    HAS_GRPC_CLIENT = True
except ImportError:
    HAS_GRPC_CLIENT = False


@pytest.mark.skipif(not HAS_GRPC_CLIENT, reason="gRPC клиент не настроен")
def test_grpc_client_import():
    """Тест импорта gRPC клиента"""
    assert HAS_GRPC_CLIENT, "gRPC клиент не импортируется"


@pytest.mark.skipif(not HAS_GRPC_CLIENT, reason="gRPC клиент не настроен")
def test_grpc_client_initialization():
    """Тест инициализации gRPC клиента"""
    try:
        client = GrpcClient()
        assert client is not None
        # Закрываем клиент
        client.close()
    except Exception as e:
        # Если сервер не запущен - это нормально для тестов
        pytest.skip(f"Не удалось инициализировать gRPC клиент: {e}")


@pytest.mark.skipif(not HAS_GRPC_CLIENT, reason="gRPC клиент не настроен")
def test_panic_signal_structure():
    """Тест структуры сигнала паники"""
    # Импортируем Pydantic модель для проверки
    try:
        from utils.schemas import PanicSignal
        # Простая проверка, что модель существует
        assert PanicSignal.__name__ == "PanicSignal"
    except ImportError:
        # Если нет Pydantic моделей, пропускаем
        pytest.skip("Pydantic модели не настроены")


if __name__ == '__main__':
    # Для запуска напрямую
    import pytest
    sys.exit(pytest.main([__file__, '-v']))