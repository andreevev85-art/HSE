"""Минимальная реализация базы данных для gRPC сервера"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

try:
    from utils.schemas import PanicSignal
except ImportError as e:
    print(f"⚠️  Не удалось импортировать Pydantic модели: {e}")
    PanicSignal = None

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path="signals.db"):
        import os
        import sqlite3

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(current_dir, db_path)

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # СОЗДАЁМ ПОДКЛЮЧЕНИЕ К БАЗЕ
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self):
        """Инициализация таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                level TEXT NOT NULL,
                rsi_14 REAL,
                volume_ratio REAL,
                price REAL,
                rsi_7 REAL,
                rsi_21 REAL,
                base_level TEXT,
                final_level TEXT,
                risk_metric REAL,
                volume_clusters TEXT,
                cluster_summary TEXT,
                passed_filters TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def get_last_signal(self, ticker):
        """Получить последний сигнал для тикера"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM signals WHERE ticker = ? ORDER BY timestamp DESC LIMIT 1",
            (ticker,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'ticker': row[1],
                'timestamp': row[2],
                'level': row[4]
            }
        return None

    def get_stats(self, days: int = 7) -> dict:
        """Получить статистику сигналов за указанное количество дней

        Args:
            days: Количество дней для анализа

        Returns:
            Словарь со статистикой:
            - total_signals: всего сигналов
            - strong_signals: количество сильных сигналов (🔴)
            - moderate_signals: количество умеренных сигналов (🟡)
            - urgent_signals: количество срочных сигналов (⚪)
            - most_active_ticker: самый активный тикер
            - most_active_count: количество сигналов у самого активного
            - most_calm_ticker: самый спокойный тикер (с сигналами)
            - most_calm_count: количество сигналов у самого спокойного
        """

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Вычисляем дату начала периода
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

        # 1. Общая статистика по уровням
        cursor.execute("""
            SELECT 
                COUNT(*) as total_signals,
                SUM(CASE WHEN level = '🔴 СИЛЬНЫЙ' THEN 1 ELSE 0 END) as strong_signals,
                SUM(CASE WHEN level = '🟡 ХОРОШИЙ' THEN 1 ELSE 0 END) as moderate_signals,
                SUM(CASE WHEN level = '⚪ СРОЧНЫЙ' THEN 1 ELSE 0 END) as urgent_signals
            FROM signals 
            WHERE timestamp >= ?
        """, (start_date,))

        stats_row = cursor.fetchone()

        # 2. Самый активный тикер
        cursor.execute("""
            SELECT ticker, COUNT(*) as signal_count
            FROM signals 
            WHERE timestamp >= ?
            GROUP BY ticker
            ORDER BY signal_count DESC
            LIMIT 1
        """, (start_date,))

        active_row = cursor.fetchone()

        # 3. Самый спокойный тикер (из тех, у кого есть сигналы)
        cursor.execute("""
            SELECT ticker, COUNT(*) as signal_count
            FROM signals 
            WHERE timestamp >= ?
            GROUP BY ticker
            ORDER BY signal_count ASC
            LIMIT 1
        """, (start_date,))

        calm_row = cursor.fetchone()

        conn.close()

        # Формируем результат
        result = {
            'total_signals': stats_row[0] if stats_row else 0,
            'strong_signals': stats_row[1] if stats_row else 0,
            'moderate_signals': stats_row[2] if stats_row else 0,
            'urgent_signals': stats_row[3] if stats_row else 0,
        }

        # Самый активный тикер
        if active_row:
            result['most_active_ticker'] = active_row[0]
            result['most_active_count'] = active_row[1]
        else:
            result['most_active_ticker'] = "НЕТ ДАННЫХ"
            result['most_active_count'] = 0

        # Самый спокойный тикер
        if calm_row:
            result['most_calm_ticker'] = calm_row[0]
            result['most_calm_count'] = calm_row[1]
        else:
            result['most_calm_ticker'] = "НЕТ ДАННЫХ"
            result['most_calm_count'] = 0

        # 4. Определяем общую напряжённость рынка
        total = result['total_signals']
        if total == 0:
            result['market_tension'] = "🟢 СПОКОЙНО"
        elif total < 10:
            result['market_tension'] = "🟡 УМЕРЕННО"
        else:
            result['market_tension'] = "🔴 ПАНИКА"

        return result

        # 5. Средняя риск-метрика
        cursor.execute("""
            SELECT AVG(risk_metric)
            FROM signals 
            WHERE timestamp >= ? AND risk_metric IS NOT NULL
        """, (start_date,))

        avg_risk_row = cursor.fetchone()
        avg_risk = avg_risk_row[0] if avg_risk_row and avg_risk_row[0] else 0

        # Добавляем средний риск
        result['avg_risk_metric'] = round(avg_risk, 2)

    def get_top_signals(self, period: str = "today", limit: int = 3) -> List[dict]:
        """
        Получить топовые (самые сильные) сигналы за указанный период.

        Args:
            period: Период выборки ("today", "yesterday", "week", "month")
            limit: Максимальное количество сигналов

        Returns:
            Список словарей с топовыми сигналами, отсортированными по:
            1. Уровню (🔴 > 🟡 > ⚪)
            2. Объёмному коэффициенту (выше > ниже)
            3. Риск-метрике (выше > ниже)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Определяем временной диапазон на основе периода
            end_date = datetime.now()

            if period == "today":
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "yesterday":
                start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date.replace(hour=23, minute=59, second=59)
            elif period == "week":
                start_date = end_date - timedelta(days=7)
            elif period == "month":
                start_date = end_date - timedelta(days=30)
            else:
                # По умолчанию: сегодня
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

            # Форматируем даты для SQLite
            start_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
            end_str = end_date.strftime('%Y-%m-%d %H:%M:%S')

            # Приоритет уровней для сортировки
            level_priority = {
                '🔴 СИЛЬНЫЙ': 3,
                '🟡 ХОРОШИЙ': 2,
                '⚪ СРОЧНЫЙ': 1
            }

            # Сначала получаем все сигналы за период
            cursor.execute("""
                SELECT ticker, timestamp, signal_type, level, rsi_14, 
                       volume_ratio, price, risk_metric
                FROM signals 
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            """, (start_str, end_str))

            rows = cursor.fetchall()
            conn.close()

            # Конвертируем в словари
            signals = []
            for row in rows:
                signal_dict = {
                    'ticker': row[0],
                    'timestamp': row[1],
                    'signal_type': row[2],
                    'level': row[3],
                    'rsi_14': row[4],
                    'volume_ratio': row[5] or 1.0,
                    'price': row[6],
                    'risk_metric': row[7] or 0.0,
                    'level_priority': level_priority.get(row[3], 0)
                }
                signals.append(signal_dict)

            # Сортируем по приоритету
            signals.sort(key=lambda x: (
                -x['level_priority'],  # Высший уровень сначала
                -(x['volume_ratio'] or 0),  # Высокий объём сначала
                -(x['risk_metric'] or 0)  # Высокая риск-метрика сначала
            ))

            # Ограничиваем количество
            top_signals = signals[:limit]

            logger.info(f"📊 Получено топ-{len(top_signals)} сигналов за период {period}")
            return top_signals

        except Exception as e:
            logger.error(f"❌ Ошибка получения топ сигналов: {e}")
            return []

    def get_signal_history(self, ticker: str, days_back: int = 7, limit: int = 0) -> List[dict]:
        """Получить историю сигналов для конкретного тикера за указанный период

        Args:
            ticker: Символ тикера (например, 'SBER')
            days_back: Количество дней назад для выборки

        Returns:
            Список словарей с сигналами
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Вычисляем дату начала периода в формате SQLite
            start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d %H:%M:%S')

            # Получаем историю сигналов для тикера
            cursor.execute("""
                SELECT ticker, timestamp, signal_type, level, 
                       rsi_14, volume_ratio, price
                FROM signals 
                WHERE ticker = ? AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (ticker, start_date))

            rows = cursor.fetchall()
            conn.close()

            # Конвертируем в словари
            signals = []
            for row in rows:
                signal_dict = {
                    'ticker': row[0],
                    'timestamp': row[1],
                    'signal_type': row[2],
                    'level': row[3],
                    'rsi_14': row[4],
                    'volume_ratio': row[5],
                    'price': row[6],
                    'risk_metric': None  # ← ИЛИ 0.0
                }
                signals.append(signal_dict)

            logger.info(f"📊 Получено {len(signals)} сигналов для {ticker} за {days_back} дней")
            return signals

        except Exception as e:
            logger.error(f"❌ Ошибка получения истории сигналов для {ticker}: {e}")
            return []

    def save_signal(self, signal_data) -> bool:
        """Сохранить обнаруженный сигнал в базу данных

        Args:
            signal_data: PanicSignal или словарь с данными сигнала
        Returns:
            True если успешно сохранено, False при ошибке
        """
        try:
            # Конвертируем PanicSignal в словарь если нужно
            if PanicSignal and isinstance(signal_data, PanicSignal):
                signal_dict = signal_data.dict()
            else:
                signal_dict = signal_data

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Подготавливаем данные
            ticker = signal_dict.get('ticker')
            timestamp = signal_dict.get('detected_at') or signal_dict.get('timestamp')
            signal_type = signal_dict.get('signal_type')
            level = signal_dict.get('level')
            rsi_14 = signal_dict.get('rsi_14')
            volume_ratio = signal_dict.get('volume_ratio')
            price = signal_dict.get('current_price') or signal_dict.get('price')
            rsi_7 = signal_dict.get('rsi_7')
            rsi_21 = signal_dict.get('rsi_21')
            base_level = signal_dict.get('base_level')
            final_level = signal_dict.get('final_level')
            risk_metric = signal_dict.get('risk_metric')

            # Сериализуем сложные структуры в JSON
            volume_clusters = json.dumps(signal_dict.get('volume_clusters', [])) if signal_dict.get(
                'volume_clusters') else None
            cluster_summary = signal_dict.get('cluster_summary')
            passed_filters = json.dumps(signal_dict.get('passed_filters', {})) if signal_dict.get(
                'passed_filters') else None

            cursor.execute("""
                INSERT INTO signals 
                (ticker, timestamp, signal_type, level, rsi_14, volume_ratio, price,
                 rsi_7, rsi_21, base_level, final_level, risk_metric, 
                 volume_clusters, cluster_summary, passed_filters)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                timestamp,
                signal_type,
                level,
                rsi_14,
                volume_ratio,
                price,
                rsi_7,
                rsi_21,
                base_level,
                final_level,
                risk_metric,
                volume_clusters,
                cluster_summary,
                passed_filters
            ))

            conn.commit()
            conn.close()

            logger.info(f"✅ Сигнал сохранён в БД: {ticker} ({level})")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сигнала в БД: {e}")
            return False

    def get_panic_signals(self, days: int = 1, limit: int = 10) -> List[PanicSignal]:
        """Получить список сигналов как PanicSignal модели

        Args:
            days: Количество дней назад
            limit: Максимальное количество сигналов

        Returns:
            Список PanicSignal объектов
        """
        try:
            if not PanicSignal:
                logger.warning("Pydantic модели не загружены")
                return []

            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ticker, timestamp as detected_at, signal_type, level,
                       rsi_14, volume_ratio, price as current_price,
                       rsi_7, rsi_21, base_level, final_level, risk_metric,
                       volume_clusters, cluster_summary, passed_filters
                FROM signals 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (start_date, limit))

            rows = cursor.fetchall()
            conn.close()

            signals = []
            for row in rows:
                try:
                    signal_dict = {
                        'ticker': row[0],
                        'detected_at': row[1],
                        'signal_type': row[2],
                        'level': row[3],
                        'rsi_14': row[4],
                        'volume_ratio': row[5],
                        'current_price': row[6],
                        'rsi_7': row[7],
                        'rsi_21': row[8],
                        'base_level': row[9],
                        'final_level': row[10],
                        'risk_metric': row[11],
                        'volume_clusters': json.loads(row[12]) if row[12] else [],
                        'cluster_summary': row[13],
                        'passed_filters': json.loads(row[14]) if row[14] else {}
                    }

                    # Создаём PanicSignal
                    signal = PanicSignal(**signal_dict)
                    signals.append(signal)

                except Exception as e:
                    logger.warning(f"Не удалось создать PanicSignal из строки БД: {e}")
                    continue

            return signals

        except Exception as e:
            logger.error(f"❌ Ошибка получения PanicSignal из БД: {e}")
            return []

