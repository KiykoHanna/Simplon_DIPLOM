
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from loguru import logger

URL = "https://www.cvlibs.net/datasets/kitti/eval_tracking.php"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    logger.info(
        "Page title: {}",
        soup.title.get_text(" ", strip=True) if soup.title else None,
    )

    tables = soup.find_all("table")
    logger.info("Tables found: {}", len(tables))

    for index, table in enumerate(tables):
        rows = table.find_all("tr")
        logger.info("Table {}: {} rows", index, len(rows))

        for row in rows[:8]:
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

            if links:
                logger.info("Links: {}", links)

    logger.success("KITTI leaderboard inspection completed")


if __name__ == "__main__":
    main()
