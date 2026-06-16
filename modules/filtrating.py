"""
Агрегация семантически схожих пар в рекуррентные события.
Результаты сохраняются в таблицу recurrent_events.
"""

import json
import logging
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import pandas as pd
from tqdm import tqdm

from modules import config
from modules.database import get_session, SimilarPair, NewsArticle, RecurrentEvent

logger = logging.getLogger(__name__)


def filter_from_db(similarity_threshold: float = 0.80, min_occurrences: int = 3) -> int:
    """
    Агрегирует рекуррентные события на основе данных из SQLite.
    Результат сохраняется в таблицу recurrent_events.

    Returns:
        Количество сохранённых событий.
    """
    with get_session() as session:
        # Загружаем пары вместе с данными статей (фильтр по порогу)
        pairs = (
            session.query(SimilarPair, NewsArticle)
            .join(NewsArticle, SimilarPair.article_id_1 == NewsArticle.id)
            .filter(SimilarPair.similarity >= similarity_threshold)
            .all()
        )

        # Группировка по оригинальной статье (article_id_1)
        groups: Dict[int, Dict] = defaultdict(lambda: {
            "original_id": None,
            "date_to_titles": defaultdict(list)
        })

        for pair, art1 in pairs:
            g = groups[pair.article_id_1]
            g["original_id"] = pair.article_id_1
            g["date_to_titles"][art1.date].append(art1.title)

            # Вторая статья
            art2 = session.query(NewsArticle).filter_by(id=pair.article_id_2).first()
            if art2:
                g["date_to_titles"][art2.date].append(art2.title)

        # Очистка старых записей (идемпотентность: удаляем всё и вставляем заново)
        session.query(RecurrentEvent).delete()
        session.commit()

        inserted_count = 0
        for _key, data in tqdm(groups.items(), desc="Агрегация событий"):
            all_dates = sorted(data["date_to_titles"].keys())
            if len(all_dates) < min_occurrences:
                continue

            date_objects = [datetime.strptime(d, "%Y-%m-%d") for d in all_dates]
            diffs = [
                (date_objects[i] - date_objects[i - 1]).days
                for i in range(1, len(date_objects))
            ]
            titles_flat = [t for d in all_dates for t in data["date_to_titles"][d]]

            event = RecurrentEvent(
                original_article_id=data["original_id"],
                first_seen=all_dates[0],
                last_seen=all_dates[-1],
                total_mentions=len(all_dates),
                avg_interval_days=statistics.mean(diffs) if diffs else 0.0,
                dates_json=json.dumps(all_dates, ensure_ascii=False),
                titles_json=json.dumps(titles_flat, ensure_ascii=False),
            )
            session.add(event)
            inserted_count += 1

        session.commit()
        logger.info("Сохранено %d рекуррентных событий", inserted_count)
        return inserted_count


def export_events_to_csv(csv_path: str = None) -> None:
    """
    Экспортирует события из таблицы recurrent_events в CSV для визуализации.
    """
    if csv_path is None:
        csv_path = str(config.DATA_DIR / "filtered_events.csv")

    with get_session() as session:
        events = (
            session.query(RecurrentEvent, NewsArticle)
            .join(NewsArticle, RecurrentEvent.original_article_id == NewsArticle.id)
            .order_by(RecurrentEvent.total_mentions.desc())
            .all()
        )

        rows = []
        for event, article in events:
            rows.append({
                "Заголовок": article.title,
                "Ссылка": article.url,
                "Первое упоминание": event.first_seen,
                "Последнее упоминание": event.last_seen,
                "Всего упоминаний": event.total_mentions,
                "Средний интервал (дни)": round(event.avg_interval_days, 2),
                "Даты": "; ".join(json.loads(event.dates_json)),
                "Заголовки": "; ".join(json.loads(event.titles_json)),
            })

        df = pd.DataFrame(rows)
        df.to_csv(csv_path, index=False, encoding="utf-8")
        logger.info("Экспортировано %d событий в %s", len(rows), csv_path)


if __name__ == "__main__":
    from modules.database import init_db
    init_db()
    count = filter_from_db(
        similarity_threshold=config.SIMILARITY_THRESHOLD,
        min_occurrences=config.MIN_OCCURRENCES
    )
    print(f"Сохранено событий: {count}")
    export_events_to_csv()