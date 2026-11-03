
import requests
from bs4 import BeautifulSoup
from loguru import logger

URL = (
    "https://www.cvlibs.net/datasets/kitti/"
    "eval_tracking_detail.php?"
    "result=526264d3e21093b3f74541a3b0eb3c5818ac92ef"
)
HEADERS = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    logger.info(
        "Page title: {}",
        soup.title.get_text(" ", strip=True) if soup.title else None,
    )

    for tag in soup.find_all(["h1", "h2", "h3"]):
        logger.info("Heading: {}", tag.get_text(" ", strip=True))

    for index, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        logger.info("Table {}: {} rows", index, len(rows))

        for row in rows[:10]:
            cells = [
                cell.get_text(" ", strip=True)
                for cell in row.find_all(["th", "td"])
            ]
            if cells:
                logger.info("Row: {}", cells)

    logger.info("Page links:")
    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        logger.info("{} -> {}", text, link["href"])

    logger.success("KITTI detail inspection completed")


if __name__ == "__main__":
    main()
