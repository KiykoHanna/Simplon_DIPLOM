
import requests
from bs4 import BeautifulSoup
from loguru import logger

URL = "https://motchallenge.net/methods/MOT-6903-5.html"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.find("h1")
    tables = soup.find_all("table")

    logger.info(
        "Title: {}",
        title.get_text(" ", strip=True) if title else None,
    )
    logger.info("Tables found: {}", len(tables))

    for index, table in enumerate(tables):
        rows = table.find_all("tr")
        logger.info("Table {}: {} rows", index, len(rows))

        for row in rows[:4]:
            cells = [
                cell.get_text(" ", strip=True)
                for cell in row.find_all(["th", "td"])
            ]
            logger.info("Row: {}", cells)

    logger.success("Method page inspection completed")


if __name__ == "__main__":
    main()
