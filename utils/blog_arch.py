#!/usr/bin/env python3
import argparse
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "blogspot-archiver/1.0"

# ──── CONFIGURE ────────────────────────────────────────────────────────────────
DEFAULT_BLOG_URL = ""  # or pass via -b / --blog-url
# ────────────────────────────────────────────────────────────────────────────────

def slugify(text, maxlen=50):
    s = re.sub(r'[^\w\s-]', '', text).strip().lower()
    s = re.sub(r'[\s_-]+', '_', s)
    return s[:maxlen].strip('_')

def parse_iso_z(ts):
    # Handles "2025-05-02T05:05:00.002-04:00" or "...Z"
    if ts.endswith('Z'):
        ts = ts[:-1] + '+00:00'
    return datetime.fromisoformat(ts).astimezone(timezone.utc)

def fetch_entries(blog_url, start, end):
    base = blog_url.rstrip('/')
    entries = []
    idx = 1
    page_size = 100
    while True:
        feed_url = (
            f"{base}/feeds/posts/default?alt=json"
            f"&published-min={start}&published-max={end}"
            f"&start-index={idx}&max-results={page_size}"
        )
        r = requests.get(feed_url, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json().get("feed", {})
        batch = data.get("entry", [])
        if not batch:
            break
        entries.extend(batch)
        if len(batch) < page_size:
            break
        idx += len(batch)
    return entries

def download_file(url, dest_path):
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def archive_post(post, out_root):
    title     = post["title"]["$t"]
    pub_dt    = parse_iso_z(post["published"]["$t"])
    ts        = pub_dt.strftime("%Y%m%dT%H%M%SZ")
    slug      = slugify(title)
    post_dir  = os.path.join(out_root, f"{ts}")
    os.makedirs(post_dir, exist_ok=True)

    # 1) Locate the post’s HTML URL
    html_url = next(
        (L["href"] for L in post.get("link", [])
         if L.get("rel")=="alternate" and L.get("type")=="text/html"),
        None
    )
    if not html_url:
        print(f"⚠️  Skipping “{title}” (no HTML link)")
        return

    # 2) Download the raw HTML
    r = requests.get(html_url, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    html = r.text

    # 3) Download & rewrite CSS to ./css/...
    css_dir = os.path.join(post_dir, "css")
    os.makedirs(css_dir, exist_ok=True)
    for m in re.finditer(r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        href_m = re.search(r'href=["\']([^"\']+)["\']', tag)
        if not href_m:
            continue
        orig = href_m.group(1)
        full = urljoin(html_url, orig)
        name = os.path.basename(urlparse(full).path) or "style.css"
        dest = os.path.join(css_dir, name)
        try:
            download_file(full, dest)
            local = f"./css/{name}"
            html = html.replace(orig, local)
            print(f"  ↳ CSS {name}")
        except Exception as e:
            print(f"    ❌ CSS {full}: {e}")

    # 4) Prepare to download images and rewrite links
    img_dir = os.path.join(post_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    mapping = {}  # original_url -> "./images/filename"

    # 4a) <link rel="image_src" href="...">
    for m in re.finditer(r'<link\b[^>]*rel=["\']image_src["\'][^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        href_m = re.search(r'href=["\']([^"\']+)["\']', tag)
        if not href_m:
            continue
        orig = href_m.group(1)
        if orig.startswith("data:") or orig in mapping:
            continue
        full = urljoin(html_url, orig)
        name = os.path.basename(urlparse(full).path)
        if not name:
            continue
        dest = os.path.join(img_dir, name)
        try:
            download_file(full, dest)
            mapping[orig] = f"./images/{name}"
            print(f"  ↳ IMAGE_SRC {name}")
        except Exception as e:
            print(f"    ❌ IMAGE_SRC {full}: {e}")

    # 4b) <meta property="og:image" content="...">
    for m in re.finditer(r'<meta\b[^>]*property=["\']og:image["\'][^>]*>', html, re.IGNORECASE):
        tag = m.group(0)
        cont_m = re.search(r'content=["\']([^"\']+)["\']', tag)
        if not cont_m:
            continue
        orig = cont_m.group(1)
        if orig.startswith("data:") or orig in mapping:
            continue
        full = urljoin(html_url, orig)
        name = os.path.basename(urlparse(full).path)
        if not name:
            continue
        dest = os.path.join(img_dir, name)
        try:
            download_file(full, dest)
            mapping[orig] = f"./images/{name}"
            print(f"  ↳ OG-IMAGE {name}")
        except Exception as e:
            print(f"    ❌ OG-IMAGE {full}: {e}")

    # 4c) <img src="...">
    for m in re.finditer(r'<img\b[^>]*src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        orig = m.group(1)
        if orig.startswith("data:") or orig in mapping:
            continue
        full = urljoin(html_url, orig)
        name = os.path.basename(urlparse(full).path)
        if not name:
            continue
        dest = os.path.join(img_dir, name)
        try:
            download_file(full, dest)
            mapping[orig] = f"./images/{name}"
            print(f"  ↳ IMG {name}")
        except Exception as e:
            print(f"    ❌ IMG {full}: {e}")

    # 5) Final pass: rewrite *every* original URL to its mapped relative path
    for orig, local in mapping.items():
        html = html.replace(orig, local)

    # 6) Save the offline page
    out_file = os.path.join(post_dir, "index.html")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Archived “{title}” → {post_dir}")

def main():
    p = argparse.ArgumentParser(
        description="Archive Blogspot posts (HTML, CSS, images) as a fully offline page"
    )
    p.add_argument(
        "-b", "--blog-url",
        default=DEFAULT_BLOG_URL,
        help="Base Blogspot URL (e.g. https://foo.blogspot.com)"
    )
    p.add_argument("start", help="UTC start, e.g. 2025-05-01T00:00:00Z")
    p.add_argument("end",   help="UTC   end,   e.g. 2025-05-04T00:00:00Z")
    p.add_argument(
        "-o", "--out",
        default="archive",
        help="Root output folder (default: ./archive)"
    )
    args = p.parse_args()

    if not args.blog_url:
        p.error("You must supply --blog-url or set DEFAULT_BLOG_URL in the script")

    os.makedirs(args.out, exist_ok=True)
    print(f"Fetching posts from {args.blog_url}\n between {args.start} and {args.end}…")
    posts = fetch_entries(args.blog_url, args.start, args.end)
    print(f"Found {len(posts)} posts.\n")

    for post in posts:
        try:
            archive_post(post, args.out)
        except Exception as e:
            print(f"❌ Error archiving post: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
