import os
from pathlib import Path

# from dotenv import load_dotenv

# load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "ria_news.db"))

# Параметры парсинга
PARSING_START_DATE = os.getenv("PARSING_START_DATE", "2023-01-01")
PARSING_END_DATE = os.getenv("PARSING_END_DATE", "2024-12-31")

# Параметры анализа
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.80"))
MIN_OCCURRENCES = int(os.getenv("MIN_OCCURRENCES", "1"))

# FAISS
FAISS_TOP_K = int(os.getenv("FAISS_TOP_K", "20"))

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")