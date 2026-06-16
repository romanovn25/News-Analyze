# 📰 News Recurrence Analysis Pipeline

Система для автоматического обнаружения рекуррентных новостных событий по данным с **ria.ru**.  
Пайплайн парсит новости, векторизует их с помощью **Sentence‑Transformers**, находит семантически похожие пары через **FAISS**, агрегирует их в повторяющиеся события и визуализирует через **Dash‑дашборд**.

Проект построен на **Apache Airflow** и полностью контейнеризирован через **Docker Compose**.

---

## 🚀 Быстрый старт

```bash
# 1. Склонировать репозиторий
git clone https://github.com/your-username/news-recurrence-analysis.git
cd news-recurrence-analysis

# 2. Создать .env (пример)
cp .env.example .env

# 3. Запустить все сервисы (Airflow + Dashboard)
docker-compose up -d --build
```

# Конфигурационные параметры:
**Период парсинга**
PARSING_START_DATE=2023-01-01
PARSING_END_DATE=2024-12-31

**Порог схожести для FAISS (0.0–1.0)**
SIMILARITY_THRESHOLD=0.80

**Минимальное число упоминаний для события**
MIN_OCCURRENCES=3

**Количество ближайших соседей в FAISS**
FAISS_TOP_K=20

**Путь к SQLite (внутри контейнера)**
DB_PATH=/opt/airflow/data/ria_news.db

**Настройки Airflow (можно оставить по умолчанию)**
AIRFLOW_UID=50000
FERNET_KEY=...
