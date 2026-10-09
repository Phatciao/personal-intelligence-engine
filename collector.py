

"""Free-first Personal Intelligence Engine collector. No paid API keys."""
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

def gnews(query, hl="en-US", gl="US", ceid="US:en"):
    return (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query)
        + f"&hl={hl}&gl={gl}&ceid={ceid}"
    )

FEEDS = [
    {
        "name": "arXiv AI Research",
        "url": "https://export.arxiv.org/api/query?search_query=cat:cs.AI&start=0&max_results=15&sortBy=submittedDate&sortOrder=descending",
        "category": "AI / Research",
    },
    {
        "name": "OpenAI News",
        "url": "https://openai.com/news/rss.xml",
        "category": "AI / Industry",
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "AI / Industry",
    },
    {
        "name": "BBC Sport Premier League",
        "url": "https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml",
        "category": "Football / Premier League",
    },
    {
        "name": "Arsenal news (Google News RSS)",
        "url": gnews("Arsenal FC when:7d", "en-GB", "GB", "GB:en"),
        "category": "Football / Arsenal",
    },
    {
        "name": "Premier League news (Google News RSS)",
        "url": gnews('"Premier League" football when:7d', "en-GB", "GB", "GB:en"),
        "category": "Football / Premier League",
    },
    {
        "name": "BBC World News",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "World / Politics & Society",
    },
    {
        "name": "BBC Business News",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "category": "World / Economy",
    },
    {
        "name": "World economy (Google News RSS)",
        "url": gnews("world economy trade inflation central banks when:7d"),
        "category": "World / Economy",
    },
    {
        "name": "AI applications (Google News RSS)",
        "url": gnews('"AI" business applications productivity when:7d'),
        "category": "AI / Applications",
    },
]

USER_AGENT = "PersonalIntelligenceEngine/1.1"

def lname(tag):
    return tag.rsplit("}", 1)[-1].lower()

def get_text(element, names):
    for node in element.iter():
        if lname(node.tag) in names and node.text and node.text.strip():
            return " ".join(node.text.split())
    return ""

def get_link(element):
    for node in element.iter():
        if lname(node.tag) == "link":
            href = (node.attrib.get("href") or "").strip()
            text = (node.text or "").strip()
            rel = (node.attrib.get("rel") or "alternate").lower()
            if href and rel in ("alternate", ""):
                return href
            if text:
                return text
            if href:
                return href
    guid = get_text(element, {"guid", "id"})
    if guid.startswith(("http://", "https://")):
        return guid
    return ""

def collect(feed):
    request = urllib.request.Request(
        feed["url"],
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    results = []
    for entry in root.iter():
        if lname(entry.tag) not in ("item", "entry"):
            continue

        title = get_text(entry, {"title"})
        url = get_link(entry)
        if not title or not url or not url.startswith(("http://", "https://")):
            continue

        results.append({
            "title": title,
            "url": url,
            "summary": get_text(
                entry, {"summary", "description", "content", "encoded"}
            )[:900],
            "published_at": get_text(
                entry, {"published", "updated", "pubdate", "date"}
            ),
            "source": feed["name"],
            "category": feed["category"],
            "label": "SIGNAL",
            "verification": "Chưa xác minh độc lập",
        })
        if len(results) >= 12:
            break

    return results

def main():
    items = []
    errors = []
    successful = 0

    for feed in FEEDS:
        try:
            batch = collect(feed)
            items.extend(batch)
            successful += 1
            print(f"OK: {feed['name']} - {len(batch)} items")
        except Exception as exc:
            errors.append({
                "source": feed["name"],
                "error": str(exc)[:240],
            })
            print(f"WARN: {feed['name']} - {str(exc)[:160]}")
        time.sleep(0.25)

    unique = {}
    for item in items:
        unique.setdefault(item["url"], item)

    data = list(unique.values())
    data.sort(
        key=lambda item: item.get("published_at", ""),
        reverse=True,
    )
    data = data[:100]

    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "ok" if not errors
            else ("partial" if successful else "error")
        ),
        "items_count": len(data),
        "items": data,
        "source_errors": errors,
        "sources_attempted": len(FEEDS),
        "sources_succeeded": successful,
        "note": (
            "Headlines are signals, not verified facts or forecasts. "
            "Some results use Google News RSS. Check original publishers "
            "before relying on claims."
        ),
    }

    output = Path("data/latest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Collected {len(data)} items; "
        f"sources succeeded: {successful}/{len(FEEDS)}"
    )

if __name__ == "__main__":
    main()
