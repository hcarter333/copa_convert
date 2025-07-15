# Blog Archiver Usage

`blog_arch.py` downloads Blogspot posts within a time range and rewrites
links so the pages work completely offline. Posts, images, and stylesheets
are saved inside an output directory.

## Requirements

- Python 3
- The [`requests`](https://pypi.org/project/requests/) package

Install `requests` with `pip install requests` if it is not already available.

## Command line

```bash
python3 utils/blog_arch.py -b BLOG_URL START END [-o OUTPUT]
```

Arguments:

- `-b`/`--blog-url` – Base URL of the Blogspot site (e.g.
  `https://example.blogspot.com`).
- `START` – ISO 8601 UTC timestamp for the beginning of the range, such as
  `2020-01-01T00:00:00Z`.
- `END` – ISO 8601 UTC timestamp for the end of the range.
- `-o`/`--out` – Directory to write the archives (default: `./archive`).

Each post is stored in a timestamped folder under the output directory.
`index.html` contains the page content with CSS and images referenced locally.

## Example

To archive posts from September 6 2015 through September 8 2016 from
<https://copaseticflow.blogspot.com> into `./archive`:

```bash
python3 utils/blog_arch.py \
    -b https://copaseticflow.blogspot.com \
    2015-09-06T00:00:00Z 2016-09-08T00:00:00Z \
    -o archive
```

During processing the script prints the downloaded CSS and images. If an
image URL returns an error, a warning is displayed but the archive continues.
