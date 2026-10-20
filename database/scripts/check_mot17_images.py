
"""Check whether MOT17 images are available in the Hugging Face repository."""

from scripts.mot17 import list_repository_entries

sequence = "train/MOT17-02-FRCNN"
entries = list_repository_entries(sequence)

for entry in entries:
    print(entry.get("type"), entry.get("path"), entry.get("size"))
