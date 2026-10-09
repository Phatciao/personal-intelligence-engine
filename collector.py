
"""Free-first collector for Personal Intelligence Engine."""
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

FEEDS = [
    {
        "name": "arXiv AI Research",
        "url": (
            "https://export.arxiv.org/api/query"
            "?search_query=cat:cs.AI&start=0&max_results=15"
            "&sortBy=submittedDate&sortOrder=descending"
        ),
        "category": "AI / Research",
    },
    {
        "name": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
        "category": "AI / Industry",
    },
]


def tag_name(tag):
    return tag.rsplit("}", 1)[-1].lower()


def get_text(element, names):
    for child in element.iter():
        if tag_name(child.tag) in names:
            if child.text and child.text.strip():
                return " ".join(child.text.split())
    return ""


def collect(feed):
    request = urllib.request.Request(
        feed["url"],
        headers={"User-Agent": "PersonalIntelligenceEngine/1.0"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    items = []
    for entry in root.iter():
        if tag_name(entry.tag) not in ("entry", "item"):
            continue

        title = get_text(entry, {"title"})
        link = ""

        for node in entry.iter():
            if tag_name(node.tag) == "link":
                link = (
                    node.attrib.get("href", "")
                    or (node.text or "").strip()
                )
                if link:
                    break

        summary = get_text(entry, {"summary", "description"})
        published = get_text(entry, {"published", "updated", "pubdate"})

        if title and link:
            items.append({
                "title": title,
                "url": link,
                "summary": summary[:600],
                "published_at": published,
                "source": feed["name"],
                "category": feed["category"],
                "label": "SIGNAL",
                "verification": "Chưa xác minh độc lập",
            })

    return items


def main():
    items, errors = [], []

    for feed in FEEDS:
        try:
            items.extend(collect(feed))
        except Exception as exc:
            errors.append({
                "source": feed["name"],
                "error": str(exc)[:200],
            })

    unique = {}
    for item in items:
        unique[item["url"]] = item

    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if not errors else "partial",
        "items_count": len(unique),
        "items": list(unique.values())[:50],
        "source_errors": errors,
        "note": (
            "Headlines are signals, not verified facts or forecasts. "
            "Open original sources before relying on claims."
        ),
    }

    output = Path("data/latest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Collected {result['items_count']} unique items.")
    print(f"Feed errors: {len(errors)}")


if __name__ == "__main__":
    main()
