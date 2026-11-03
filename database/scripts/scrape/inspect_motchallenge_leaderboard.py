
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from loguru import logger

URL = "https://motchallenge.net/results/MOT16/"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    logger.info("Page title: {}", soup.title.get_text(strip=True))
    logger.info("Tables found: {}", len(soup.find_all("table")))

    for table_index, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        logger.info(
            "Table {}: {} rows",
            table_index,
            len(rows),
        )

        if rows:
            headers = [
                cell.get_text(" ", strip=True)
                for cell in rows[0].find_all(["th", "td"])
            ]
            logger.info("Headers: {}", headers)

        for row in rows[1:6]:
            cells = [
                cell.get_text(" ", strip=True)
                for cell in row.find_all(["th", "td"])
            ]
            links = [
                {
                    "text": link.get_text(" ", strip=True),
                    "url": urljoin(URL, link["href"]),
                }
                for link in row.find_all("a", href=True)
            ]

            logger.info("Row: {}", cells)
            logger.info("Links: {}", links)

    logger.success("Leaderboard inspection completed")


if __name__ == "__main__":
    main()
