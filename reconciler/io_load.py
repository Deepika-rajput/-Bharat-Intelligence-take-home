"""CSV loading helpers."""
import csv


def load(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))
