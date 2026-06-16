from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import sys
import logging

sys.path.insert(0, '/opt/airflow')

from modules import config
from modules.database import init_db
from modules.analyze import find_similar_pairs_from_db
from modules.filtrating import filter_from_db, export_events_to_csv

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'sgn3',
    'retries': 0,
    'start_date': datetime(2026, 5, 29),
}

dag = DAG(
    'ria_analysis',
    default_args=default_args,
    schedule=None,               # только ручной запуск
    catchup=False,
    tags=['ria', 'analysis'],
)

def init_db_task():
    init_db()
    logger.info("База данных инициализирована")
    return "DB initialized"

def analyze_task():
    count = find_similar_pairs_from_db(threshold=config.SIMILARITY_THRESHOLD)
    logger.info(f"Поиск похожих пар завершён. Найдено новых пар: {count}")
    return count

def filter_task():
    count = filter_from_db(
        similarity_threshold=config.SIMILARITY_THRESHOLD,
        min_occurrences=config.MIN_OCCURRENCES
    )
    logger.info(f"Фильтрация событий завершена. Сохранено событий: {count}")
    return count

def export_task():
    export_events_to_csv()
    logger.info("Экспорт в CSV завершён")
    return "CSV exported"

t0 = PythonOperator(task_id='init_db', python_callable=init_db_task, dag=dag)
t1 = PythonOperator(task_id='analyze', python_callable=analyze_task, dag=dag)
t2 = PythonOperator(task_id='filter', python_callable=filter_task, dag=dag)
t3 = PythonOperator(task_id='export_csv', python_callable=export_task, dag=dag)

t0 >> t1 >> t2 >> t3