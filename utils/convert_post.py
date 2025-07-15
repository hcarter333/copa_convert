#!/usr/bin/env python3
"""Download a single Blogspot post and convert to Tufte CSS HTML."""

import os
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from utils.blog_arch import download_file, USER_AGENT


def convert_post(url: str, out_dir: str = "output") -> str:
    """Download *url* and save converted HTML under *out_dir*.

    Returns the path to the generated HTML file.
    """
    r = requests.get(url, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    body = soup.find("div", class_="post-body-container")
    if body is None:
        raise RuntimeError("post-body-container div not found")

    os.makedirs(out_dir, exist_ok=True)
    img_dir = os.path.join(out_dir, "img")
    os.makedirs(img_dir, exist_ok=True)

    # Download images referenced in the body
    for img in body.find_all("img"):
        src = img.get("src")
        if not src or src.startswith("data:"):
            continue
        full = urljoin(url, src)
        name = os.path.basename(urlparse(full).path)
        if not name:
            continue
        dest = os.path.join(img_dir, name)
        try:
            download_file(full, dest)
            img["src"] = f"img/{name}"
            print(f"  ↳ downloaded {name}")
        except Exception as e:
            print(f"    ❌ {full}: {e}")

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <link rel=\"stylesheet\" href=\"https://cootermaroos.com/tufte.css\" />
  <title>{soup.title.string if soup.title else ''}</title>
</head>
<body>
<article>
{body}
</article>
</body>
</html>
"""

    filename = os.path.basename(urlparse(url).path) or "index.html"
    out_path = os.path.join(out_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved HTML to {out_path}")
    return out_path


def main():
    import argparse

    p = argparse.ArgumentParser(description="Convert a single Blogspot post")
    p.add_argument("url", help="URL of the blog post")
    p.add_argument("-o", "--out", default="output", help="Output directory")
    args = p.parse_args()

    convert_post(args.url, args.out)


if __name__ == "__main__":
    main()
