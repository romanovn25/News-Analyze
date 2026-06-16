from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import sys
import logging

sys.path.insert(0, '/opt/airflow')

from modules.database import init_db
from modules.parser import collect_articles_for_date
from modules.vectorizer import vectorize_from_db

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'sgn3',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'start_date': datetime(2026, 5, 22),
}

dag = DAG(
    'ria_data_collection',
    default_args=default_args,
    schedule='@daily',
    catchup=True,
    max_active_runs=1,          # последовательно, чтобы не перегружать
    tags=['ria', 'collection'],
)

def init_db_task():
    init_db()
    logger.info("База данных инициализирована")
    return "DB initialized"

def parse_news(**context):
    from datetime import datetime
    target_date_str = context['ds']
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    logger.info(f"Начинаем парсинг за дату: {target_date}")
    inserted = collect_articles_for_date(target_date)
    logger.info(f"Парсинг завершён. Вставлено новых статей: {inserted}")
    return inserted

def vectorize_task():
    count = vectorize_from_db()
    logger.info(f"Векторизация завершена. Обработано статей: {count}")
    return count

t0 = PythonOperator(task_id='init_db', python_callable=init_db_task, dag=dag)
t1 = PythonOperator(task_id='parse_news', python_callable=parse_news, dag=dag)
t2 = PythonOperator(task_id='vectorize', python_callable=vectorize_task, dag=dag)

t0 >> t1 >> t2