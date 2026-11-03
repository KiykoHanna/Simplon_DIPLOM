
import requests
from bs4 import BeautifulSoup
from loguru import logger

URL = "https://www.cvlibs.net/datasets/kitti/eval_tracking.php"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    tables = soup.find_all("table")

    for table_index in [1, 3]:
        table = tables[table_index]
        logger.info("Inspecting table {}", table_index)

        for row_index, row in enumerate(table.find_all("tr")[:12]):
            cells = row.find_all(["th", "td"])
            values = [
                cell.get_text(" ", strip=True)
                for cell in cells
            ]

            links = [
                {
                    "text": link.get_text(" ", strip=True),
                    "url": link["href"],
                }
                for link in row.find_all("a", href=True)
            ]

            logger.info(
                "Row {}: {} | links: {}",
                row_index,
                values,
                links,
            )


if __name__ == "__main__":
    main()
