import json
import logging
from typing import List, Tuple

import numpy as np
from tqdm import tqdm

from modules import config
from modules.database import get_session, bulk_insert_pairs, ArticleVector

logger = logging.getLogger(__name__)


def load_vectors_from_db() -> Tuple[List[int], np.ndarray]:
    """Загружает article_id и векторы из БД. Возвращает (ids, нормализованные векторы)."""
    import faiss  # импорт внутри функции
    with get_session() as session:
        rows = session.query(ArticleVector.article_id, ArticleVector.vector_json).all()
        article_ids = [r[0] for r in rows]
        vectors = np.array([json.loads(r[1]) for r in rows], dtype="float32")
        faiss.normalize_L2(vectors)
        return article_ids, vectors


def find_similar_pairs_from_db(threshold: float = 0.8) -> int:
    import faiss  # убедимся, что импорт есть
    article_ids, vectors = load_vectors_from_db()
    if len(vectors) < 2:
        logger.warning("Недостаточно векторов для анализа: %d", len(vectors))
        return 0

    logger.info("Построение FAISS-индекса для %d векторов...", len(vectors))
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    k = min(config.FAISS_TOP_K, len(vectors))
    distances, indices = index.search(vectors, k + 1)

    pair_records = []
    for i in tqdm(range(len(vectors)), desc="Поиск схожих пар"):
        for dist, j in zip(distances[i][1:], indices[i][1:]):
            if dist < threshold:
                break
            if i < j:
                pair_records.append({
                    "article_id_1": article_ids[i],
                    "article_id_2": article_ids[j],
                    "similarity": float(dist),
                })

    with get_session() as session:
        inserted = bulk_insert_pairs(pair_records, session)
        session.commit()
        logger.info("Сохранено %d новых пар в БД", inserted)
    return inserted