"""
build/fetch_online.py
=====================
Download the Reformation Hymnal JSON from the online hymnal service and save
it to reference/rh_online.json.

Usage:
    python -m build.fetch_online
"""

import json
import sys
import urllib.request
from pathlib import Path

URL = "https://app.sdarm.org/hymnal/data/reformation-hymnal-v2.json"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://hymnal.sdarm.org/",
}
OUT = Path(__file__).parent.parent / "reference" / "rh_online.json"


def fetch() -> dict:
    req = urllib.request.Request(URL, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    print(f"Fetching {URL} ...")
    try:
        data = fetch()
    except Exception as exc:
        sys.exit(f"Download failed: {exc}")

    hymns = data.get("hymns", [])
    topics = data.get("topics", [])
    print(f"  {len(hymns)} hymns, {len(topics)} topics")

    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved → {OUT}")


if __name__ == "__main__":
    main()
