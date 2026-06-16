"""
Модуль парсинга новостей с ria.ru.
Сохраняет данные напрямую в SQLite.
"""

import logging
import time
from datetime import datetime, date as date_type
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from modules import config
from modules.database import get_session, bulk_insert_articles

logger = logging.getLogger(__name__)


def format_period(data: str) -> str:
    """Преобразует строку времени из элемента в формат HHMMSS."""
    hours = data.replace(" ", "").split(",")[-1].split(":")[0]
    minutes = data.replace(" ", "").split(":")[-1][:2]
    return f"{hours}{minutes}00"


def _fetch_articles_for_day(target_date: datetime) -> List[Dict[str, str]]:
    """Загружает все новости за один день. Возвращает список словарей."""
    base_url = "https://ria.ru/services"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/58.0.3029.110 Safari/537.3"
        )
    }
    formatted_date = target_date.strftime("%Y%m%d")
    date_str = target_date.strftime("%Y-%m-%d")
    last_time = "235900"
    prev_time = "235901"
    results: List[Dict[str, str]] = []

    while True:
        prev_time = last_time
        time.sleep(0.5)
        url = f"{base_url}/{formatted_date}/more.html?date={formatted_date}T{last_time}"
        logger.debug("Fetching: %s", url)

        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            news_items = soup.find_all("div", class_="list-item")

            if not news_items:
                break

            for item in news_items:
                title_tag = item.find("a", class_="list-item__title")
                info_tag = item.find("div", class_="list-item__info")
                if not title_tag or not info_tag:
                    continue

                title = title_tag.text.strip()
                link = title_tag["href"]
                last_time = format_period(info_tag.text)

                if prev_time == last_time:
                    break

                results.append({"date": date_str, "title": title, "url": link})

            if prev_time == last_time:
                break

        except requests.RequestException as exc:
            logger.error("Request failed for %s: %s", target_date, exc)
            break

    return results


def collect_articles_for_date(target_date: date_type) -> int:
    """
    Загружает статьи за указанную дату и сохраняет их в SQLite.

    Returns:
        Количество вставленных (новых) статей.
    """
    dt = datetime(target_date.year, target_date.month, target_date.day)
    articles = _fetch_articles_for_day(dt)
    logger.info("Fetched %d articles for %s", len(articles), target_date)

    with get_session() as session:
        inserted = bulk_insert_articles(articles, session)
        session.commit()
    return inserted


if __name__ == "__main__":
    # Для отладки (локально, вне Docker, должен быть файл .env с настройками)
    from modules.database import init_db
    init_db()
    test_date = datetime(2025, 1, 1).date()
    count = collect_articles_for_date(test_date)
    print(f"Inserted {count} articles for {test_date}")