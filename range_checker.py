import json
import re
from pathlib import Path

RANGES_PATH = Path(__file__).parent / "ranges.json"

with open(RANGES_PATH, "r", encoding="utf-8") as f:
    RANGES = json.load(f)


ALIAS_MAP = {}
for main_name, info in RANGES.items():
    ALIAS_MAP[main_name.lower()] = main_name
    for alias in info.get("aliases", []):
        ALIAS_MAP[alias.lower()] = main_name


def normalize_name(name: str) -> str:
    """Lowercase and strip extra characters so names match more easily."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9 ]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def find_test(name: str):
    """Return the main test name from ranges.json, or None if unknown."""
    return ALIAS_MAP.get(normalize_name(name))


def to_number(value):
    """Convert '12.5', '12.5 g/dL' or '1,50,000' to a float. Returns None if it fails."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d[\d,]*\.?\d*", str(value))
    if not match:
        return None
    return float(match.group().replace(",", ""))


def check_value(name, value, report_min=None, report_max=None):
    """
    Decide if a value is low / normal / high.
    Uses the range printed on the report first, then falls back to ranges.json.
    Returns a dict: {status, min, max, source}
    """
    num = to_number(value)
    low = to_number(report_min)
    high = to_number(report_max)
    source = "report"

    if low is None and high is None:
        test = find_test(name)
        if test is None:
            return {"status": "unknown", "min": None, "max": None, "source": "none"}
        low = RANGES[test]["min"]
        high = RANGES[test]["max"]
        source = "reference file"

    if num is None:
        return {"status": "unknown", "min": low, "max": high, "source": source}

    if low is not None and num < low:
        status = "low"
    elif high is not None and num > high:
        status = "high"
    else:
        status = "normal"

    return {"status": status, "min": low, "max": high, "source": source}


if __name__ == "__main__":
    print(check_value("Hb", "10.2"))                     # low, from reference file
    print(check_value("SGPT", 80))                       # high
    print(check_value("Glucose", 90, 70, 110))           # normal, from report
    print(check_value("Some Rare Test", 5))              # unknown