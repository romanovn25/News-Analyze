import json
import logging
from typing import List, Dict, Any

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from modules.config import DB_PATH

logger = logging.getLogger(__name__)

Base = declarative_base()

class NewsArticle(Base):
    __tablename__ = "news_articles"
    id = Column(Integer, primary_key=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    title = Column(Text, nullable=False)
    url = Column(String(500), unique=True, nullable=False)

class ArticleVector(Base):
    __tablename__ = "article_vectors"
    article_id = Column(Integer, primary_key=True)
    preprocessed_text = Column(Text, nullable=True)
    vector_json = Column(Text, nullable=False)  # JSON-список

class SimilarPair(Base):
    __tablename__ = "similar_pairs"
    id = Column(Integer, primary_key=True)
    article_id_1 = Column(Integer, nullable=False)
    article_id_2 = Column(Integer, nullable=False)
    similarity = Column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("article_id_1", "article_id_2", name="uniq_pair"),)

class RecurrentEvent(Base):
    __tablename__ = "recurrent_events"
    id = Column(Integer, primary_key=True)
    original_article_id = Column(Integer, nullable=False)
    first_seen = Column(String(10), nullable=False)
    last_seen = Column(String(10), nullable=False)
    total_mentions = Column(Integer, nullable=False)
    avg_interval_days = Column(Float, nullable=False)
    dates_json = Column(Text, nullable=False)
    titles_json = Column(Text, nullable=False)

# engine и session
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_session() -> Session:
    return SessionLocal()

# ---- вспомогательные функции вставки ----
def bulk_insert_articles(articles: List[Dict[str, str]], session: Session) -> int:
    """Вставляет статьи, игнорируя дубликаты по url."""
    inserted = 0
    for art in articles:
        exists = session.query(NewsArticle).filter_by(url=art["url"]).first()
        if not exists:
            session.add(NewsArticle(date=art["date"], title=art["title"], url=art["url"]))
            inserted += 1
    #session.commit()
    return inserted

def bulk_insert_vectors(vectors: List[Dict[str, Any]], session: Session) -> int:
    """Вставляет векторы, перезаписывая существующие."""
    for v in vectors:
        session.merge(ArticleVector(
            article_id=v["article_id"],
            preprocessed_text=v.get("preprocessed_text", ""),
            vector_json=v["vector_json"]
        ))
    #session.commit()
    return len(vectors)

def bulk_insert_pairs(pairs: List[Dict[str, Any]], session: Session) -> int:
    """Вставляет пары с проверкой на уникальность."""
    inserted = 0
    for p in pairs:
        exists = session.query(SimilarPair).filter_by(
            article_id_1=p["article_id_1"], article_id_2=p["article_id_2"]
        ).first()
        if not exists:
            session.add(SimilarPair(**p))
            inserted += 1
    #session.commit()
    return inserted