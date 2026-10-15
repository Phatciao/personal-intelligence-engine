
#!/usr/bin/env python3
# Personal Intelligence Engine
# Free RSS collector — Python standard library only.

import hashlib
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


ROOT = Path(__file__).resolve().parent
OUTPUT_FILE = ROOT / "data" / "latest.json"

USER_AGENT = (
    "Mozilla/5.0 (compatible; PersonalIntelligenceEngine/3.0; "
    "+https://github.com/Phatciao/personal-intelligence-engine)"
)

MAX_PER_SOURCE = 20
MAX_TOTAL_ITEMS = 150
MAX_AGE_DAYS = 30
REQUEST_TIMEOUT = 20

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
        # --- AI: nguồn chính thức và nghiên cứu miễn phí ---
    {
        "name": "Google DeepMind Blog",
        "category": "ai",
        "url": "https://deepmind.google/blog/rss.xml",
    },
    {
        "name": "Google Research",
        "category": "ai",
        "url": "https://research.google/blog/rss/",
    },
    {
        "name": "arXiv Machine Learning",
        "category": "ai",
        "url": "https://rss.arxiv.org/rss/cs.LG",
    },
    {
        "name": "TechCrunch AI",
        "category": "ai",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "name": "Hacker News AI Discussions",
        "category": "ai",
        "url": "https://hnrss.org/newest?q=AI",
    },

    # --- X: tài khoản công khai qua RSSHub ---
    # Thử nghiệm; dịch vụ trung gian có thể bị giới hạn.
    {
        "name": "X OpenAI",
        "category": "ai",
        "url": "https://rsshub.app/twitter/user/OpenAI",
    },
    {
        "name": "X Google DeepMind",
        "category": "ai",
        "url": "https://rsshub.app/twitter/user/GoogleDeepMind",
    },
    {
        "name": "X Simon Willison",
        "category": "ai",
        "url": "https://rsshub.app/twitter/user/simonw",
    },

    # --- Threads: thử nghiệm, chưa bảo đảm hoạt động ---
    {
        "name": "Threads Zuckerberg",
        "category": "ai",
        "url": "https://rsshub.app/threads/zuck",
    },
]

VALID_CATEGORIES = {"ai", "football", "water", "vietnam", "world"}

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"


def now_utc():
    return datetime.now(timezone.utc)


def now_iso():
    return now_utc().isoformat()


def clean_html(value):
    if not value:
        return ""

    value = unescape(str(value))
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def child_text(element, names):
    """Read RSS, RDF/RSS 1.0, or Atom values."""
    if element is None:
        return ""

    wanted = set(names)

    for child in element.iter():
        local = child.tag.split("}")[-1]

        if local not in wanted:
            continue

        if local == "link":
            href = child.attrib.get("href")
            if href:
                rel = child.attrib.get("rel", "alternate")
                if rel == "alternate":
                    return href.strip()

        if child.text and child.text.strip():
            return child.text.strip()

    return ""


def parse_date(value):
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


def classify_text(title, summary, fallback):
    """
    Classify by article text, never by publisher/source name.
    Feed category is only a fallback when content is ambiguous.
    """
    text = f"{title} {summary}".lower()

    if re.search(
        r"\barsenal\b|\bpremier league\b|\bfootball\b|\bsoccer\b|"
        r"ngoại hạng anh|bóng đá|champions league",
        text,
    ):
        return "football"

    if re.search(
        r"water treatment|water filtration|chlorination|"
        r"wastewater|water quality|desalination|"
        r"xử lý nước|lọc nước|nước thải|nước sạch|hồ bơi|"
        r"pool filtration|reverse osmosis|"
        r"heat pump|energy efficiency|electrolysis|"
        r"điện phân|tiết kiệm năng lượng",
        text,
    ):
        return "water"

    if re.search(
        r"\bvietnam\b|\bviet nam\b|việt nam|hanoi|ha noi|"
        r"ho chi minh|vnexpress|vietnamnews|vietnamnet|"
        r"báo chính phủ|chính phủ việt nam",
        text,
    ):
        return "vietnam"

    if re.search(
        r"artificial intelligence|machine learning|"
        r"deep learning|\bllm\b|openai|hugging face|arxiv|"
        r"neural network|generative ai|robotics|"
        r"trí tuệ nhân tạo|mô hình ngôn ngữ",
        text,
    ):
        return "ai"

    if fallback in VALID_CATEGORIES:
        return fallback

    return "world"


def normalize_title(title):
    text = clean_html(title).lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url):
    """Remove common tracking parameters for more stable deduplication."""
    try:
        parts = urlsplit(url.strip())
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return url.strip().lower().rstrip("/")

        tracking_prefixes = ("utm_",)
        tracking_names = {
            "fbclid", "gclid", "ocid", "at_campaign",
            "at_medium", "ved", "usg",
        }

        query = [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in tracking_names
            and not key.lower().startswith(tracking_prefixes)
        ]

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            urlencode(query),
            "",
        ))
    except (TypeError, ValueError):
        return url.strip().lower().rstrip("/")


def item_key(item):
    """
    Exact normalized title catches copies published through different feeds.
    URL is used only when no title exists.
    """
    title = normalize_title(item.get("title", ""))

    if title:
        return hashlib.sha256(title.encode("utf-8")).hexdigest()

    url = normalize_url(item.get("url", ""))
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def age_hours(item, reference=None):
    published = item.get("published_at", "")

    if not published:
        return None

    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        reference = reference or now_utc()
        return max(0.0, (reference - dt).total_seconds() / 3600)
    except (TypeError, ValueError, OverflowError):
        return None


def quality_flags(item):
    flags = []

    if not item.get("summary"):
        flags.append("missing_summary")

    if len(item.get("summary", "")) < 100:
        flags.append("short_summary")

    if not item.get("published_at"):
        flags.append("missing_date")
    else:
        hours = age_hours(item)
        if hours is not None and hours > 24 * 7:
            flags.append("older_than_7_days")

    if not item.get("url"):
        flags.append("missing_url")

    return flags


def triage_score(item):
    """
    A transparent screening heuristic, NOT a verified importance score.
    Scores help sort candidates; they must not be presented as facts.
    """
    title = item.get("title", "").lower()
    summary = item.get("summary", "").lower()
    text = f"{title} {summary}"

    score = 30
    reasons = []

    high_impact = (
        "war", "invasion", "ceasefire", "sanction", "tariff",
        "central bank", "interest rate", "inflation", "recession",
        "election", "coup", "nuclear", "oil supply", "gas supply",
        "energy crisis", "trade deal", "export ban",
        "chiến tranh", "ngừng bắn", "trừng phạt", "lạm phát",
        "lãi suất", "bầu cử", "khủng hoảng năng lượng",
    )

    if any(term in text for term in high_impact):
        score += 20
        reasons.append("potential_high_impact_topic")

    concrete_change = (
        "announced", "approved", "banned", "launched", "signed",
        "published", "raised", "cut rates", "resigned", "arrested",
        "confirmed", "results", "official data",
        "công bố", "phê duyệt", "ban hành", "ký kết",
    )

    if any(term in text for term in concrete_change):
        score += 10
        reasons.append("possible_concrete_development")

    uncertain_terms = (
        "rumour", "rumor", "speculation", "unconfirmed",
        "allegedly", "reportedly", "tin đồn", "chưa xác nhận",
    )

    if any(term in text for term in uncertain_terms):
        score -= 10
        reasons.append("uncertainty_language")

    hours = age_hours(item)

    if hours is None:
        score -= 8
        reasons.append("publication_date_missing")
    elif hours <= 24:
        score += 12
        reasons.append("published_within_24_hours")
    elif hours <= 72:
        score += 7
        reasons.append("published_within_72_hours")
    elif hours > 24 * 7:
        score -= 12
        reasons.append("older_than_7_days")

    if not item.get("summary") or len(item["summary"]) < 100:
        score -= 8
        reasons.append("summary_insufficient")

    return max(0, min(100, score)), reasons


def parse_feed(xml_bytes, source):
    root = ET.fromstring(xml_bytes)
    entries = []

    for element in root.iter():
        if element.tag.split("}")[-1] == "item":
            entries.append(element)

    if not entries:
        for element in root.iter():
            if element.tag.split("}")[-1] == "entry":
                entries.append(element)

    results = []

    for entry in entries[:MAX_PER_SOURCE]:
        title = clean_html(child_text(entry, ["title"]))
        link = child_text(entry, ["link"])

        if not link:
            guid = child_text(entry, ["guid", "id"])
            if guid.startswith(("https://", "http://")):
                link = guid

        summary_raw = child_text(
            entry,
            ["description", "summary", "encoded", "content"],
        )

        if not summary_raw:
            content_node = entry.find(CONTENT + "encoded")
            if content_node is not None:
                summary_raw = content_node.text or ""

        summary = clean_html(summary_raw)

        published_raw = child_text(
            entry, ["pubDate", "published", "updated", "date"]
        )
        published_at = parse_date(published_raw)

        if not title or not link:
            continue

        if not link.startswith(("https://", "http://")):
            continue

        category = classify_text(
            title,
            summary,
            source.get("category", "world"),
        )

        item = {
            "title": title[:500],
            "url": link,
            "summary": summary[:2500],
            "published_at": published_at,
            "source": source["name"],
            "category": category,

            # Neutral label: collection does not prove importance.
            "label": "NEWS",

            # RSS collection does not independently verify claims.
            "verification": "Chưa xác minh độc lập",
        }

        score, reasons = triage_score(item)
        item["triage_score"] = score
        item["triage_reasons"] = reasons
        item["quality_flags"] = quality_flags(item)

        results.append(item)

    return results


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


def deduplicate(items):
    """
    Merge exact-title copies across feeds.
    Keep the version with the best summary and usable publication date.
    Record all feeds that carried the same title.
    """
    groups = {}

    for item in items:
        key = item_key(item)

        if key not in groups:
            candidate = dict(item)
            candidate["sources_seen"] = [item.get("source", "")]
            groups[key] = candidate
            continue

        existing = groups[key]
        source_name = item.get("source", "")

        if source_name and source_name not in existing["sources_seen"]:
            existing["sources_seen"].append(source_name)

        old_quality = (
            len(existing.get("summary", "")),
            bool(existing.get("published_at")),
        )
        new_quality = (
            len(item.get("summary", "")),
            bool(item.get("published_at")),
        )

        if new_quality > old_quality:
            sources_seen = existing["sources_seen"]
            existing.update(item)
            existing["sources_seen"] = sources_seen

    return list(groups.values())


def select_items(items):
    """
    Keep a broad feed, but limit extreme category dominance.
    This is a collection safeguard, not a claim about world importance.
    """
    reference = now_utc()

    for item in items:
        hours = age_hours(item, reference)

        if hours is not None and hours > MAX_AGE_DAYS * 24:
            item["quality_flags"] = list(
                set(item.get("quality_flags", []) + ["older_than_30_days"])
            )

    # Put stronger candidates first; date is only a tie-breaker.
    items.sort(
        key=lambda item: (
            item.get("triage_score", 0),
            item.get("published_at", ""),
        ),
        reverse=True,
    )

    category_caps = {
        "world": 75,
        "ai": 45,
        "football": 40,
        "vietnam": 35,
        "water": 30,
    }

    counts = {category: 0 for category in VALID_CATEGORIES}
    selected = []
    overflow = []

    for item in items:
        category = item.get("category", "world")

        if (
            len(selected) < MAX_TOTAL_ITEMS
            and counts.get(category, 0) < category_caps.get(category, 30)
        ):
            selected.append(item)
            counts[category] = counts.get(category, 0) + 1
        else:
            overflow.append(item)

    # Fill unused capacity if a category has too few items.
    for item in overflow:
        if len(selected) >= MAX_TOTAL_ITEMS:
            break
        selected.append(item)

    # Dashboard users see the newest records first by default.
    selected.sort(
        key=lambda item: (
            bool(item.get("published_at")),
            item.get("published_at", ""),
        ),
        reverse=True,
    )

    return selected[:MAX_TOTAL_ITEMS]


def main():
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    collected = []
    source_errors = []
    succeeded = 0

    print("Personal Intelligence Engine — collector v3")
    print("Sources:", len(SOURCES))

    for index, source in enumerate(SOURCES, start=1):
        print(f"[{index}/{len(SOURCES)}] {source['name']}")

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

        time.sleep(0.3)

    unique_items = deduplicate(collected)
    items = select_items(unique_items)

    status = "ok" if succeeded > 0 else "error"

    category_counts = {}
    for item in items:
        category = item.get("category", "world")
        category_counts[category] = category_counts.get(category, 0) + 1

    payload = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "status": status,
        "items_count": len(items),
        "items": items,
        "category_counts": category_counts,
        "source_errors": source_errors,
        "sources_attempted": len(SOURCES),
        "sources_succeeded": succeeded,
        "deduplication": {
            "raw_items": len(collected),
            "unique_titles": len(unique_items),
            "duplicates_removed": len(collected) - len(unique_items),
        },
        "note": (
            "Free RSS collection. NEWS is a neutral label, not an importance "
            "claim. triage_score is a transparent heuristic, not verified "
            "importance. Feed content has not been independently verified. "
            "quality_flags identify missing or potentially stale data."
        ),
    }

    temporary_file = OUTPUT_FILE.with_suffix(".json.tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")

    temporary_file.replace(OUTPUT_FILE)

    print("\nFinished.")
    print("Status:", status)
    print("Sources succeeded:", succeeded, "/", len(SOURCES))
    print("Raw items:", len(collected))
    print("Unique titles:", len(unique_items))
    print("Selected items:", len(items))
    print("Categories:", category_counts)
    print("Output:", OUTPUT_FILE)

    if succeeded == 0:
        raise SystemExit("All RSS sources failed; check network or feed URLs.")


if __name__ == "__main__":
    main()

