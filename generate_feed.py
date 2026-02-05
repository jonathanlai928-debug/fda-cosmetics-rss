#!/usr/bin/env python3
import re
import html
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urljoin

PAGE_URL = "https://www.fda.gov/cosmetics/cosmetics-news-events"
SITE_BASE = "https://www.fda.gov"
MAX_ITEMS = 50
USER_AGENT = "Mozilla/5.0 (RSS generator; GitHub Pages)"

def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")

def parse_mmddyyyy(date_str: str) -> datetime:
    """
    Accepts M/D/YYYY, MM/DD/YYYY, and also M/D/YY (FDA page includes 2-digit years like 12/29/25). :contentReference[oaicite:2]{index=2}
    Assumption for 2-digit year: 2000 + YY.
    """
    s = date_str.strip()
    parts = s.split("/")
    if len(parts) != 3:
        raise ValueError(f"Unexpected date format: {date_str}")
    m, d, y = parts
    mm = int(m)
    dd = int(d)
    yy = int(y)
    if yy < 100:
        yy = 2000 + yy
    return datetime(yy, mm, dd, 0, 0, 0, tzinfo=timezone.utc)

def rfc2822(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")

def extract_recent_news_items(page_html: str) -> list[tuple[datetime, str, str]]:
    """
    Extract items from the 'Recent News & Updates' section which appears as dated bullets like:
      1/21/2026 - [Title link]
      12/29/25 - [Title link]
    :contentReference[oaicite:3]{index=3}

    Returns list of (pub_dt, title, absolute_url).
    """
    # Try to isolate the section to reduce noise.
    # We cut from "Recent News & Updates" to "Recent Federal Register Notices" if present.
    start_idx = page_html.lower().find("recent news &amp; updates")
    if start_idx == -1:
        start_idx = page_html.lower().find("recent news & updates")
    end_idx = page_html.lower().find("recent federal register notices")
    section = page_html[start_idx:end_idx] if start_idx != -1 and end_idx != -1 else page_html

    # Pattern: date - <a href="...">Title</a>
    # FDA links can be relative (e.g., /cosmetics/...) so we urljoin with SITE_BASE.
    pat = re.compile(
        r"(\d{1,2}/\d{1,2}/\d{2,4})\s*-\s*.*?<a[^>]+href=\"([^\"]+)\"[^>]*>\s*(.*?)\s*</a>",
        re.IGNORECASE | re.DOTALL,
    )

    items: list[tuple[datetime, str, str]] = []
    seen = set()

    for m in pat.finditer(section):
        date_str = m.group(1)
        href = m.group(2).strip()
        raw_title = m.group(3)

        title = re.sub(r"<[^>]+>", "", raw_title)
        title = html.unescape(re.sub(r"\s+", " ", title)).strip()

        url = urljoin(SITE_BASE, href)

        try:
            pub_dt = parse_mmddyyyy(date_str)
        except Exception:
            continue

        key = (title, url, pub_dt.date().isoformat())
        if title and key not in seen:
            seen.add(key)
            items.append((pub_dt, title, url))

    # Newest first
    items.sort(key=lambda x: x[0], reverse=True)
    return items[:MAX_ITEMS]

def main() -> int:
    page_html = fetch(PAGE_URL)
    items = extract_recent_news_items(page_html)

    build_dt = datetime.now(timezone.utc)

    rss_items = []
    for pub_dt, title, url in items:
        rss_items.append(
            f"""
    <item>
      <title>{html.escape(title)}</title>
      <link>{html.escape(url)}</link>
      <guid isPermaLink="true">{html.escape(url)}</guid>
      <pubDate>{rfc2822(pub_dt)}</pubDate>
    </item>""".strip()
        )

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{html.escape("FDA Cosmetics News & Events")}</title>
    <link>{html.escape(PAGE_URL)}</link>
    <description>{html.escape("Unofficial RSS feed generated from FDA Cosmetics News & Events (Recent News & Updates).")}</description>
    <lastBuildDate>{rfc2822(build_dt)}</lastBuildDate>
{chr(10).join(rss_items)}
  </channel>
</rss>
"""

    with open("feed.xml", "w", encoding="utf-8") as f:
        f.write(rss)

    print(f"Wrote feed.xml with {len(items)} items")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
