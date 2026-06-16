import json
import logging
import re
from typing import List, Dict, Any

import numpy as np
from tqdm import tqdm

from modules import config
from modules.database import get_session, bulk_insert_vectors, NewsArticle, ArticleVector

logger = logging.getLogger(__name__)

import logging
import warnings

# Подавляем предупреждения transformers
warnings.filterwarnings("ignore", category=UserWarning)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)


def preprocess_texts(texts: List[str]) -> List[str]:
    """Лемматизация и очистка текстов. Тяжёлые импорты внутри."""
    import nltk
    from nltk.corpus import stopwords
    from pymorphy3 import MorphAnalyzer

    nltk.download('stopwords', quiet=True)

    morph = MorphAnalyzer()
    russian_stopwords = set(stopwords.words('russian') + [
        'этот', 'это', 'весь', 'который', 'такой', 'какой', 'наш', 'свой'
    ])

    def clean_text(text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'\d+', '', text)
        text = text.lower().strip()
        words = []
        for word in text.split():
            parsed = morph.parse(word)
            if parsed:
                lemma = parsed[0].normal_form
                if lemma not in russian_stopwords and len(lemma) > 2:
                    words.append(lemma)
        return ' '.join(words)

    cleaned = []
    for text in tqdm(texts, desc="Предобработка текстов", disable=True):
        cleaned.append(clean_text(text))
    return cleaned


def vectorize_from_db() -> int:
    """Векторизует статьи из БД. Тяжёлый импорт sentence_transformers внутри."""
    from sentence_transformers import SentenceTransformer

    with get_session() as session:
        vectorized_ids = {row[0] for row in session.query(ArticleVector.article_id).all()}
        articles = session.query(NewsArticle).filter(NewsArticle.id.notin_(vectorized_ids)).all()

        if not articles:
            logger.info("Нет новых статей для векторизации.")
            return 0

        titles = [a.title for a in articles]
        logger.info("Векторизация %d статей...", len(titles))

        preprocessed = preprocess_texts(titles)

        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")

        vector_records: List[Dict[str, Any]] = []
        for art, prep in tqdm(zip(articles, preprocessed), total=len(articles), desc="Векторизация", disable=True):
            vector = model.encode(prep).tolist()
            vector_records.append({
                "article_id": art.id,
                "preprocessed_text": prep,
                "vector_json": json.dumps(vector),
            })

        inserted = bulk_insert_vectors(vector_records, session)
        session.commit()
        logger.info("Сохранено %d векторов", inserted)
        return inserted