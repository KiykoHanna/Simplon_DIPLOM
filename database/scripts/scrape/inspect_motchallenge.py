
from loguru import logger
import requests
from bs4 import BeautifulSoup

URL = "https://motchallenge.net/method/MOT=2987&chl=5"

def main() -> None:
    response = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    logger.info("Page title: {}", soup.title.get_text(strip=True)
                if soup.title else "Not found")

    for tag in soup.find_all(["h1", "h2", "h3"]):
        logger.info("Heading [{}]: {}", tag.name, tag.get_text(" ", strip=True))

    for index, table in enumerate(soup.find_all("table"), start=1):
        rows = table.find_all("tr")
        logger.info("Table {}: {} rows", index, len(rows))

        for row in rows[:5]:
            cells = row.find_all(["th", "td"])
            values = [cell.get_text(" ", strip=True) for cell in cells]
            logger.info("  Row: {}", values)

    logger.info("Links:")
    for link in soup.find_all("a", href=True)[:40]:
        text = link.get_text(" ", strip=True)
        href = link["href"]
        logger.info("  {} -> {}", text or "[no text]", href)

if __name__ == "__main__":
    main()
