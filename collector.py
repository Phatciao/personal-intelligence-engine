
#!/usr/bin/env python3
# Personal Intelligence Engine
# Free RSS collector — no paid API, no third-party Python packages.

import json
import re
import time
import hashlib
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from html import unescape


ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = ROOT / "data" / "latest.json"

USER_AGENT = (
    "Mozilla/5.0 (compatible; PersonalIntelligenceEngine/2.0; "
    "+https://github.com/Phatciao/personal-intelligence-engine)"
)

MAX_PER_SOURCE = 20
MAX_TOTAL_ITEMS = 150
REQUEST_TIMEOUT = 20

# RSS sources are free to access. Availability and feed contents can change.
SOURCES = [
    {
        "name": "arXiv AI",
        "category": "ai",
        "url": "https://export.arxiv.org/rss/cs.AI",
    },
    {
        "name": "OpenAI News",
        "category": "ai",
        "url": "https://openai.com/news/rss.xml",
    },
    {
        "name": "Hugging Face Blog",
        "category": "ai",
        "url": "https://huggingface.co/blog/feed.xml",
    },
    {
        "name": "BBC Sport Football",
        "category": "football",
        "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",
    },
    {
        "name": "Google News Arsenal",
        "category": "football",
        "url": "https://news.google.com/rss/search?q=Arsenal+FC&hl=en-GB&gl=GB&ceid=GB:en",
    },
    {
        "name": "Google News Premier League",
        "category": "football",
        "url": "https://news.google.com/rss/search?q=Premier+League+football&hl=en-GB&gl=GB&ceid=GB:en",
    },
    {
        "name": "BBC World",
        "category": "world",
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
    },
    {
        "name": "BBC Business",
        "category": "world",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
    },
    {
        "name": "Google News World Economy",
        "category": "world",
        "url": "https://news.google.com/rss/search?q=world+economy+business&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News AI Applications",
        "category": "ai",
        "url": "https://news.google.com/rss/search?q=artificial+intelligence+applications&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News Vietnam",
        "category": "vietnam",
        "url": "https://news.google.com/rss/search?q=Vietnam+economy+technology&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News Water Technology",
        "category": "water",
        "url": "https://news.google.com/rss/search?q=water+treatment+filtration+technology&hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Google News Energy",
        "category": "water",
        "url": "https://news.google.com/rss/search?q=energy+efficiency+heat+pump+technology&hl=en-US&gl=US&ceid=US:en",
    },
]

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean_html(value):
    """Remove HTML tags and normalize whitespace from feed fields."""
    if not value:
        return ""

    value = unescape(str(value))
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def child_text(element, names):
    """Find a child value by local tag name, regardless of XML namespace."""
    if element is None:
        return ""

    wanted = set(names)

    for child in element.iter():
        local_name = child.tag.split("}")[-1]

        if local_name in wanted:
            if local_name == "link":
                href = child.attrib.get("href")
                if href:
                    return href.strip()

            if child.text and child.text.strip():
                return child.text.strip()

    return ""


def parse_date(value):
    """Return a UTC ISO timestamp; blank if the source has no usable date."""
    if not value:
        return ""

    value = value.strip()

    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def classify_text(title, summary, source, fallback):
    text = " ".join([title, summary, source]).lower()

    if re.search(
        r"arsenal|premier league|football|soccer|ngoại hạng anh|"
        r"bóng đá|champions league",
        text,
    ):
        return "football"

    if re.search(
        r"waterco|water treatment|water filtration|chlorination|"
        r"heat pump|pump|pool|filtration|wastewater|water quality|"
        r"xử lý nước|hồ bơi|máy bơm|nước sạch",
        text,
    ):
        return "water"

    if re.search(
        r"vietnam|viet nam|việt nam|hanoi|ho chi minh|"
        r"vnexpress|vietnamnews|vietnamnet",
        text,
    ):
        return "vietnam"

    if re.search(
        r"artificial intelligence|\bai\b|machine learning|"
        r"deep learning|llm|openai|hugging face|arxiv|"
        r"neural network|generative ai|robotics",
        text,
    ):
        return "ai"

    if fallback in {"ai", "football", "water", "vietnam", "world"}:
        return fallback

    return "world"


def parse_feed(xml_bytes, source):
    """Parse RSS 2.0, RDF/RSS 1.0, or Atom entries."""
    root = ET.fromstring(xml_bytes)

    entries = []

    # RSS 2.0 and RSS 1.0 use item elements.
    for element in root.iter():
        if element.tag.split("}")[-1] == "item":
            entries.append(element)

    # Atom uses entry elements.
    if not entries:
        for element in root.iter():
            if element.tag.split("}")[-1] == "entry":
                entries.append(element)

    results = []

    for entry in entries[:MAX_PER_SOURCE]:
        title = clean_html(
            child_text(entry, ["title"])
        )

        link = child_text(entry, ["link"])

        # RSS feeds can provide a GUID instead of a link.
        if not link:
            guid = child_text(entry, ["guid", "id"])
            if guid.startswith(("https://", "http://")):
                link = guid

        summary_raw = child_text(
            entry,
            ["description", "summary", "encoded", "content"],
        )

        # Fall back to the namespaced content field where present.
        if not summary_raw:
            content_node = entry.find(CONTENT + "encoded")
            if content_node is not None:
                summary_raw = content_node.text or ""

        summary = clean_html(summary_raw)

        published_raw = child_text(
            entry,
            ["pubDate", "published", "updated", "date"],
        )

        if not published_raw:
            published_raw = child_text(entry, ["date"])

        published_at = parse_date(published_raw)

        if not title or not link:
            continue

        if not link.startswith(("https://", "http://")):
            continue

        category = classify_text(
            title,
            summary,
            source["name"],
            source["category"],
        )

        results.append({
            "title": title[:500],
            "url": link,
            "summary": summary[:2500],
            "published_at": published_at,
            "source": source["name"],
            "category": category,
            "label": "SIGNAL",
            "verification": "Chưa xác minh độc lập",
        })

    return results


def item_key(item):
    """Stable duplicate key, preferring URL."""
    url = item.get("url", "").strip().lower().rstrip("/")
    if url:
        return url

    title = item.get("title", "").strip().lower()
    return hashlib.sha256(title.encode("utf-8")).hexdigest()


def fetch_source(source):
    request = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT,
    ) as response:
        xml_bytes = response.read(5_000_000)

    return parse_feed(xml_bytes, source)


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    collected = []
    source_errors = []
    succeeded = 0

    print("Personal Intelligence Engine — free RSS collector")
    print("Sources:", len(SOURCES))

    for index, source in enumerate(SOURCES, start=1):
        print(
            f"[{index}/{len(SOURCES)}] Fetching: {source['name']}"
        )

        try:
            items = fetch_source(source)
            collected.extend(items)
            succeeded += 1

            print(f"  OK: {len(items)} items")

        except Exception as exc:
            message = f"{type(exc).__name__}: {str(exc)[:250]}"

            source_errors.append({
                "source": source["name"],
                "error": message,
            })

            print(f"  ERROR: {message}")

        # Avoid hammering feeds unnecessarily.
        time.sleep(0.3)

    unique = {}
    for item in collected:
        key = item_key(item)
        if key not in unique:
            unique[key] = item

    items = list(unique.values())

    # Put dated items first, newest first. Undated items follow.
    items.sort(
        key=lambda item: (
            bool(item.get("published_at")),
            item.get("published_at", ""),
        ),
        reverse=True,
    )

    items = items[:MAX_TOTAL_ITEMS]

    status = "ok" if succeeded > 0 else "error"

    payload = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": status,
        "items_count": len(items),
        "items": items,
        "source_errors": source_errors,
        "sources_attempted": len(SOURCES),
        "sources_succeeded": succeeded,
        "note": (
            "Free RSS collection. Feed summaries may be incomplete. "
            "Items have not been independently verified. "
            "Priority scores and interpretations are generated in the dashboard."
        ),
    }

    temporary_file = OUTPUT_FILE.with_suffix(".json.tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")

    temporary_file.replace(OUTPUT_FILE)

    print()
    print("Finished.")
    print("Status:", status)
    print("Sources succeeded:", succeeded, "/", len(SOURCES))
    print("Unique items:", len(items))
    print("Output:", OUTPUT_FILE)

    # Do not fail the whole workflow if a few feeds are temporarily down.
    # Fail only when every source fails.
    if succeeded == 0:
        raise SystemExit("All RSS sources failed; check network or feed URLs.")


if __name__ == "__main__":
    main()
