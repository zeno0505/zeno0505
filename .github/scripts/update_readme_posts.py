#!/usr/bin/env python3
"""Rewrite the marked section of README.md with the latest posts from the blog's Atom feed.

stdlib only (no third-party action).
- Feed unreachable -> exit 0, README untouched (feed may not exist yet / transient outage).
- Markers missing  -> exit 1.

Item format (2 lines per post, newest first, up to POST_COUNT):
    - 2026-10-10 · [title](url)<br><sub>first-paragraph excerpt, cut to ~EXCERPT_LEN chars…</sub>
  (renders as two lines: date · linked title / smaller muted excerpt)
"""
import html, os, re, sys, urllib.request, xml.etree.ElementTree as ET

FEED = os.environ.get("FEED_URL", "https://zeno0505.github.io/dev-articles/feed.xml")
N = int(os.environ.get("POST_COUNT", "5"))
EXCERPT_LEN = int(os.environ.get("EXCERPT_LEN", "60"))
README = os.environ.get("README_PATH", "README.md")
DRY_RUN = os.environ.get("DRY_RUN") == "1"  # print the new block, don't write
START, END = "<!-- BLOG-POST-LIST:START -->", "<!-- BLOG-POST-LIST:END -->"
A = "{http://www.w3.org/2005/Atom}"


def fetch(src):
    if os.path.exists(src):  # local file (dry runs / tests)
        return open(src, "rb").read()
    req = urllib.request.Request(src, headers={"User-Agent": "readme-updater"})
    return urllib.request.urlopen(req, timeout=20).read()


def plain(s):
    """feed <summary type="html"> -> one line of plain text."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def cut(s, n=EXCERPT_LEN):
    """Cut to ~n chars, preferring a word (space) boundary, then add an ellipsis."""
    if len(s) <= n:
        return s
    head = s[:n]
    sp = head.rfind(" ")
    if sp >= n * 0.7:
        head = head[:sp]
    return head.rstrip(" ,.;:·—-") + "…"


def md_text(s):
    """Escape for use inside markdown link text / inline HTML."""
    s = html.escape(s, quote=False)
    return re.sub(r"([\\`*_\[\]])", r"\\\1", s)


try:
    raw = fetch(FEED)
except Exception as e:
    print(f"feed fetch failed: {e}")
    sys.exit(0)

root = ET.fromstring(raw)
items = []
for e in root.findall(f"{A}entry"):
    title = re.sub(r"\s+", " ", html.unescape(e.findtext(f"{A}title") or "")).strip()  # text, not markup
    link = next((l.get("href") for l in e.findall(f"{A}link") if l.get("rel", "alternate") == "alternate"), None)
    date = (e.findtext(f"{A}published") or e.findtext(f"{A}updated") or "")[:10]
    summary = cut(plain(e.findtext(f"{A}summary") or e.findtext(f"{A}content")))
    if title and link:
        items.append((date, title, link, summary))
items.sort(key=lambda x: x[0], reverse=True)

lines = []
for d, t, l, s in items[:N]:
    # one source line on purpose: README rendering treats a newline as a soft break,
    # comment-style (gfm) rendering as a hard break; inline <br> looks the same in both.
    lines.append(f"- {d} · [{md_text(t)}]({l})" + (f"<br><sub>{md_text(s)}</sub>" if s else ""))
if not lines:
    lines = ["- 아직 글이 없습니다."]
block = "\n".join([START] + lines + [END])

text = open(README, encoding="utf-8").read()
if START not in text or END not in text:
    print("markers not found")
    sys.exit(1)
new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
n = min(len(items), N)
if DRY_RUN:
    print(block)
    print(f"[dry-run] {'would update' if new != text else 'no change'} ({n} posts)")
elif new != text:
    open(README, "w", encoding="utf-8").write(new)
    print(f"updated with {n} posts")
else:
    print("no change")
