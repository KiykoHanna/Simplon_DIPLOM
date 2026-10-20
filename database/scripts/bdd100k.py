
"""Scrape public annotation metadata from the BDD100K documentation."""

import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from loguru import logger

DOC_URL = "https://github.com/bdd100k/bdd100k/blob/master/doc/source/format.rst"
REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "bdd100k"
    / "reports"
    / "bdd100k_documentation.json"
)
REQUEST_TIMEOUT = 30


def scrape_documentation() -> dict[str, object]:
    """Extract annotation metadata from the official BDD100K documentation."""
    response = requests.get(DOC_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.select_one("article.markdown-body")

    if content is None:
        raise ValueError("Could not locate documentation content on the page.")

    text = content.get_text("\n", strip=True)

    report = {
        "source_url": DOC_URL,
        "title": soup.title.get_text(strip=True) if soup.title else None,
        "categories": {},
        "annotation_fields": [],
        "annotation_geometry_types": [],
        "documentation_text": text,
    }

    for heading in content.find_all(["h2", "h3", "h4"]):
        title = heading.get_text(" ", strip=True)
        if title in {
            "Object Detection",
            "Instance Segmentation, Box Tracking, Segmentation Tracking",
            "Semantic Segmentation",
            "Panoptic Segmentation",
            "Drivable Area",
            "Lane Marking",
            "Pose Estimation",
        }:
            report["categories"][title] = True

    for field in ("box2d", "box3d", "poly2d", "attributes", "labels"):
        if field in text:
            report["annotation_fields"].append(field)

    for geometry in ("box2d", "box3d", "poly2d", "rle"):
        if geometry in text:
            report["annotation_geometry_types"].append(geometry)

    return report


def main() -> None:
    """Scrape the documentation and save a JSON report."""
    report = scrape_documentation()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("BDD100K documentation report saved to {}", REPORT_PATH)


if __name__ == "__main__":
    main()
