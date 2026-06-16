import logging
from sqlalchemy import inspect, text
from modules.database import get_session, init_db, Base
from modules.config import DB_PATH

logger = logging.getLogger(__name__)


def check_db_schema():
    """
    Проверяет:
    - подключение к БД
    - наличие всех ожидаемых таблиц
    - вывод структуры (имена таблиц и колонок)
    """
    init_db()  # создаст таблицы, если их нет (но не трогает данные)

    with get_session() as session:
        # 1. Проверка соединения через простой запрос к метатаблице sqlite_master
        result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        tables = [row[0] for row in result]
        logger.info(f"Таблицы в БД ({DB_PATH}): {tables}")

        # 2. Ожидаемый набор таблиц (на основе моделей из database.py)
        expected_tables = {'news_articles', 'article_vectors', 'similar_pairs', 'recurrent_events'}

        # 3. Проверяем наличие всех ожидаемых таблиц
        missing = expected_tables - set(tables)
        if missing:
            logger.warning(f"Отсутствуют таблицы: {missing}")
        else:
            logger.info("Все ожидаемые таблицы присутствуют.")

        # 4. Для каждой таблицы выводим колонки (схему)
        inspector = inspect(session.bind)
        for table in expected_tables:
            if table in tables:
                columns = inspector.get_columns(table)
                col_names = [col['name'] for col in columns]
                logger.info(f"Таблица {table}: колонки {col_names}")

        return {
            "status": "ok" if not missing else "missing_tables",
            "db_path": DB_PATH,
            "tables_found": tables,
            "missing_tables": list(missing),
        }