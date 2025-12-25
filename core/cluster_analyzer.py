"""
Анализ кластеров объёма.
Определение ключевых ценовых уровней на основе распределения объёма.
"""

import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VolumeCluster:
    """Кластер объёма - ключевой ценовой уровень"""
    price_level: float  # Ценовой уровень
    volume_percentage: float  # Доля объёма на этом уровне (%)
    total_volume: float  # Суммарный объём на уровне
    role: str  # 'support', 'resistance', 'neutral'
    significance: float  # Значимость уровня (0-1)


class VolumeClusterAnalyzer:
    """
    Анализатор кластеров объёма.
    Определяет ключевые ценовые уровни на основе распределения объёма.
    """

    def __init__(self, num_clusters: int = 3):
        """
        Args:
            num_clusters: Количество ключевых уровней для определения
        """
        self.num_clusters = num_clusters
        self.min_volume_share = 0.1  # Минимальная доля объёма для уровня (10%)

    def analyze(self, prices: List[float], volumes: List[float]) -> List[VolumeCluster]:
        """
        Анализ кластеров объёма на основе цен и объёмов.

        Args:
            prices: Список цен
            volumes: Список объёмов (соответствует ценам)

        Returns:
            Список ключевых кластеров объёма
        """
        if len(prices) == 0 or len(volumes) == 0:
            logger.warning("Нет данных для анализа кластеров объёма")
            return []

        if len(prices) != len(volumes):
            logger.error(f"Несовпадение размеров: цены={len(prices)}, объёмы={len(volumes)}")
            return []

        try:
            # 1. Группируем объёмы по ценовым зонам
            clusters = self._group_volume_by_price_zones(prices, volumes)

            # 2. Находим наиболее значимые уровни
            significant_clusters = self._find_significant_clusters(clusters)

            # 3. Определяем роль каждого уровня (поддержка/сопротивление)
            clusters_with_roles = self._assign_roles(significant_clusters, prices)

            logger.info(f"📊 Найдено {len(clusters_with_roles)} ключевых уровней объёма")

            return clusters_with_roles

        except Exception as e:
            logger.error(f"❌ Ошибка анализа кластеров объёма: {e}")
            return []

    def _group_volume_by_price_zones(self, prices: List[float], volumes: List[float]) -> List[Dict[str, Any]]:
        """
        Группировка объёма по ценовым зонам.

        Args:
            prices: Список цен
            volumes: Список объёмов

        Returns:
            Список кластеров с агрегированным объёмом
        """
        if not prices:
            return []

        # Определяем диапазон цен
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price

        if price_range == 0:
            # Все цены одинаковые - один кластер
            total_volume = sum(volumes)
            return [{
                'price_level': prices[0],
                'total_volume': total_volume,
                'count': len(prices)
            }]

        # Создаём 20 ценовых зон (биннинг)
        num_bins = min(20, len(set(prices)))
        bins = np.linspace(min_price, max_price, num_bins + 1)

        clusters = []
        for i in range(len(bins) - 1):
            lower = bins[i]
            upper = bins[i + 1]
            center = (lower + upper) / 2

            # Суммируем объём в этой зоне
            zone_volume = 0
            count = 0

            for price, volume in zip(prices, volumes):
                if lower <= price <= upper:
                    zone_volume += volume
                    count += 1

            if zone_volume > 0:
                clusters.append({
                    'price_level': center,
                    'total_volume': zone_volume,
                    'count': count,
                    'price_range': (lower, upper)
                })

        return clusters

    def _find_significant_clusters(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Нахождение наиболее значимых кластеров объёма.

        Args:
            clusters: Все обнаруженные кластеры

        Returns:
            Топ-N наиболее значимых кластеров
        """
        if not clusters:
            return []

        # Сортируем по объёму (по убыванию)
        sorted_clusters = sorted(clusters, key=lambda x: x['total_volume'], reverse=True)

        # Рассчитываем общий объём
        total_volume = sum(c['total_volume'] for c in sorted_clusters)

        # Оставляем только значимые кластеры (мин. доля объёма)
        significant_clusters = []
        for cluster in sorted_clusters:
            volume_share = cluster['total_volume'] / total_volume if total_volume > 0 else 0

            if volume_share >= self.min_volume_share:
                cluster['volume_percentage'] = volume_share * 100
                significant_clusters.append(cluster)

        # Берём топ-N наиболее значимых
        top_clusters = significant_clusters[:self.num_clusters]

        # Пересчитываем проценты относительно отобранных кластеров
        selected_volume = sum(c['total_volume'] for c in top_clusters)
        for cluster in top_clusters:
            if selected_volume > 0:
                cluster['volume_percentage'] = (cluster['total_volume'] / selected_volume) * 100

        return top_clusters

    def _assign_roles(self, clusters: List[Dict[str, Any]], prices: List[float]) -> List[VolumeCluster]:
        """
        Определение роли каждого уровня (поддержка/сопротивление).

        Args:
            clusters: Кластеры объёма
            prices: Исторические цены

        Returns:
            Кластеры с определёнными ролями
        """
        if not prices or not clusters:
            return []

        current_price = prices[-1]
        result = []

        for cluster in clusters:
            price_level = cluster['price_level']
            volume_percentage = cluster.get('volume_percentage', 0)
            total_volume = cluster['total_volume']

            # Определяем роль на основе позиции относительно текущей цены
            if price_level < current_price:
                role = 'support'  # Уровень поддержки
            elif price_level > current_price:
                role = 'resistance'  # Уровень сопротивления
            else:
                role = 'neutral'  # Текущий уровень

            # Рассчитываем значимость (чем больше объём, тем значимее)
            significance = min(volume_percentage / 100 * 2, 1.0)  # Нормализуем к 0-1

            result.append(VolumeCluster(
                price_level=price_level,
                volume_percentage=volume_percentage,
                total_volume=total_volume,
                role=role,
                significance=significance
            ))

        return result

    def get_clusters_summary(self, clusters: List[VolumeCluster]) -> str:
        """
        Получение текстового описания кластеров.

        Args:
            clusters: Список кластеров

        Returns:
            Текстовое описание
        """
        if not clusters:
            return "Кластеры объёма не обнаружены"

        summary = "📊 **КЛЮЧЕВЫЕ УРОВНИ ОБЪЁМА:**\n\n"

        for i, cluster in enumerate(clusters, 1):
            role_emoji = {
                'support': '🟢',
                'resistance': '🔴',
                'neutral': '🟡'
            }.get(cluster.role, '⚪')

            summary += (
                f"{i}. {role_emoji} **{cluster.price_level:.2f}₽** "
                f"({cluster.role})\n"
                f"   • Доля объёма: {cluster.volume_percentage:.1f}%\n"
                f"   • Значимость: {cluster.significance:.2f}/1.0\n"
            )

        return summary


# ============================================================================
# ТЕСТОВАЯ ФУНКЦИЯ
# ============================================================================
def test_volume_cluster_analyzer():
    """Тест анализатора кластеров объёма"""
    import random

    print("🧪 Тест VolumeClusterAnalyzer")
    print("=" * 50)

    # Создаём тестовые данные
    base_price = 100.0
    prices = []
    volumes = []

    for _ in range(100):
        # 3 ключевых уровня: 95, 100, 105
        price = base_price + random.choice([-5, 0, 5]) + random.uniform(-1, 1)
        volume = random.uniform(100, 1000)

        # Увеличиваем объём на ключевых уровнях
        if 94 <= price <= 96:
            volume *= 3
        elif 99 <= price <= 101:
            volume *= 2
        elif 104 <= price <= 106:
            volume *= 2.5

        prices.append(price)
        volumes.append(volume)

    # Анализируем
    analyzer = VolumeClusterAnalyzer(num_clusters=3)
    clusters = analyzer.analyze(prices, volumes)

    print(f"📊 Найдено кластеров: {len(clusters)}")

    for i, cluster in enumerate(clusters, 1):
        print(f"\n{i}. Уровень: {cluster.price_level:.2f}₽")
        print(f"   Роль: {cluster.role} ({cluster.volume_percentage:.1f}% объёма)")
        print(f"   Значимость: {cluster.significance:.2f}")

    # Выводим сводку
    print("\n" + "=" * 50)
    print(analyzer.get_clusters_summary(clusters))

    return len(clusters) > 0


if __name__ == "__main__":
    test_volume_cluster_analyzer()