import os
import re
import sys
import subprocess
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_md

BASE_COURSE_ROOT = "https://penpot.app/courses"
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; PenpotCourseScraper/8.2)"
})

RESOURCE_EXTENSIONS = [
    ".penpot", ".svg", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip"
]

VIDEO_HOST_PATTERNS = [
    "youtube.com",
    "youtu.be",
    "vimeo.com",
    "peertube.kaleidos.net",  # PeerTube host used by Penpot course
]

visited = set()
# list of dicts: {"url": ..., "title": ..., "block": int or None}
lesson_pages = []
resource_status = {}       # resource_url -> "assets" or "lesson"
global_video_urls = set()  # all video URLs across the course


def is_same_site(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc
        return "penpot.app" in netloc or "penpot.dev" in netloc
    except Exception:
        return False


def looks_like_resource(url: str) -> bool:
    lower = url.lower().split("?", 1)[0]
    return any(lower.endswith(ext) for ext in RESOURCE_EXTENSIONS)


def looks_like_video(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(pat in host for pat in VIDEO_HOST_PATTERNS)


def fetch_html(url: str) -> str:
    resp = SESSION.get(url, timeout=20)
    resp.raise_for_status()
    return resp.text


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "untitled"


def extract_block_number_from_path(path: str):
    """
    From /courses/block-0/welcome/ -> 0
    Returns int block or None if not found.
    """
    m = re.search(r"/block-(\d+)", path)
    if m:
        return int(m.group(1))
    return None


def crawl(url: str):
    if url in visited:
        return
    visited.add(url)

    try:
        html = fetch_html(url)
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return

    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(url)
    path = parsed.path

    if path.startswith("/courses"):
        title_tag = soup.find("h1") or soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else url
        block = extract_block_number_from_path(path)
        lesson_pages.append({
            "url": url,
            "title": title,
            "block": block,
        })

    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        if is_same_site(href) and "/courses" in urlparse(href).path:
            crawl(href)


def download_file(url: str, dest_path: str):
    try:
        resp = SESSION.get(url, timeout=30, stream=True)
        resp.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded {url} -> {dest_path}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")


def handle_resource(url: str, lesson_folder: str, base_dest: str):
    """
    Flipped behavior:

      - First time: store in shared base_dest/assets/ and mark 'assets'
      - Later times: store in lesson_folder and mark 'lesson'
    """
    global resource_status

    filename = os.path.basename(urlparse(url).path.split("?", 1)[0]) or "file"
    assets_dir = os.path.join(base_dest, "assets")

    status = resource_status.get(url)

    if status is None:
        dest = os.path.join(assets_dir, filename)
        if not os.path.exists(dest):
            download_file(url, dest)
        resource_status[url] = "assets"
    elif status == "assets":
        dest = os.path.join(lesson_folder, filename)
        if not os.path.exists(dest):
            download_file(url, dest)
        resource_status[url] = "lesson"
    elif status == "lesson":
        return


def extract_from_section(html: str, base_url: str, lesson_folder: str, base_dest: str):
    """
    Restrict to section-wrapper; from there:
      - ALL .text-content blocks -> combined markdown
      - first <h3> under section-wrapper -> h3_title (for naming/frontmatter)
      - video-section (PeerTube/others) -> video URLs
      - collect assets (links + img src) within that section
    """
    global global_video_urls

    soup = BeautifulSoup(html, "html.parser")

    section = soup.find("section", class_=lambda c: c and "section-wrapper" in c)
    if section is None:
        section = soup

    # first h3 text in section-wrapper
    h3_tag = section.find("h3")
    h3_title = h3_tag.get_text(strip=True) if h3_tag else None

    # remove scripts/styles
    for tag in section.find_all(["script", "style"]):
        tag.decompose()

    # collect assets (links + images) from this section
    for a in section.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if looks_like_resource(href):
            handle_resource(href, lesson_folder, base_dest)

    for img in section.find_all("img", src=True):
        src = urljoin(base_url, img["src"])
        if looks_like_resource(src):
            handle_resource(src, lesson_folder, base_dest)

    # article text: collect *all* .text-content blocks
    text_blocks = section.find_all(class_=lambda c: c and "text-content" in c)
    if not text_blocks:
        text_blocks = [section]

    article_html = "\n\n".join(block.decode() for block in text_blocks)
    article_md = html_to_md(article_html, heading_style="ATX").strip()

    # video URLs from .video-section
    video_urls_local = set()
    video_container = section.find(class_=lambda c: c and "video-section" in c)
    if video_container:
        for iframe in video_container.find_all("iframe", src=True):
            src = urljoin(base_url, iframe["src"])
            if looks_like_video(src):
                video_urls_local.add(src)
        for a in video_container.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            if looks_like_video(href):
                video_urls_local.add(href)

    global_video_urls.update(video_urls_local)

    return article_md, sorted(video_urls_local), h3_title


def process_lesson_page(block_number: int, order_in_block: int, page: dict, base_dest: str):
    url = page["url"]
    title = page["title"]

    print(f"Processing [block {block_number} #{order_in_block:02d}] {title} - {url}")
    try:
        html = fetch_html(url)
    except Exception as e:
        print(f"Failed to re-fetch {url}: {e}")
        return

    # temporary folder for any assets during extraction
    temp_folder = os.path.join(base_dest, "_tmp")
    os.makedirs(temp_folder, exist_ok=True)

    article_md, video_urls_local, h3_title = extract_from_section(html, url, temp_folder, base_dest)

    block_str = str(block_number) if block_number is not None else "x"
    order_str = f"{order_in_block:02d}"

    # use h3 content as name; fall back to page title
    name_source = h3_title if h3_title else title
    h3_slug = slugify(name_source)

    folder_name = f"{block_str}-{order_str}-{h3_slug}.assignment"
    lesson_folder = os.path.join(base_dest, folder_name)
    os.makedirs(lesson_folder, exist_ok=True)

    # move any files from temp_folder into this lesson folder
    for item in os.listdir(temp_folder):
        src_path = os.path.join(temp_folder, item)
        dest_path = os.path.join(lesson_folder, item)
        if os.path.isfile(src_path) and not os.path.exists(dest_path):
            os.rename(src_path, dest_path)

    # frontmatter name uses the raw h3 text (or title if missing)
    frontmatter_name = (h3_title or title).replace('"', '\\"')

    # write index.md with frontmatter + content
    index_md_path = os.path.join(lesson_folder, "index.md")
    with open(index_md_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f'name: "{frontmatter_name}"\n')
        f.write('type: "Assignment"\n')
        f.write("published: true\n")
        f.write("---\n\n")
        f.write(f"# {title}\n\n")
        f.write(f"> Source: {url}\n\n")
        if video_urls_local:
            f.write("## Video\n\n")
            for v in video_urls_local:
                f.write(f"{v}\n")
            f.write("\n")
        f.write("## Content\n\n")
        f.write(article_md)
        f.write("\n")

    # clean up temp_folder if empty
    try:
        if not os.listdir(temp_folder):
            os.rmdir(temp_folder)
    except OSError:
        pass


def download_videos_with_ytdlp(assets_dir: str, video_list_path: str):
    """
    Use yt-dlp to download all videos listed in video_list_path into assets_dir/videos.
    """
    if not os.path.isfile(video_list_path):
        print(f"No video_urls.txt found at {video_list_path}, skipping yt-dlp.")
        return

    videos_out = os.path.join(assets_dir, "videos")
    os.makedirs(videos_out, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-a", video_list_path,
        "-o", os.path.join(videos_out, "%(title)s.%(ext)s"),
    ]
    print("Running yt-dlp to download videos:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("yt-dlp not found on PATH; install yt-dlp or run it manually.")


def main():
    # parse CLI: optional dest_dir and optional --no-video-download flag
    dest_dir = "pages"
    download_videos = True

    args = [arg for arg in sys.argv[1:] if arg.strip()]
    for arg in args:
        if arg == "--no-video-download":
            download_videos = False
        else:
            dest_dir = arg

    os.makedirs(dest_dir, exist_ok=True)
    assets_dir = os.path.join(dest_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    crawl(BASE_COURSE_ROOT)

    # group pages by block number
    by_block = {}
    for p in lesson_pages:
        block = p["block"]
        by_block.setdefault(block, []).append(p)

    total_pages = 0
    for block_number, pages in sorted(by_block.items(), key=lambda kv: (kv[0] is None, kv[0])):
        pages.sort(key=lambda p: p["url"])
        for idx, page in enumerate(pages, start=1):
            process_lesson_page(block_number, idx, page, dest_dir)
            total_pages += 1

    # write one comprehensive video_urls.txt in assets/
    video_list_path = os.path.join(assets_dir, "video_urls.txt")
    with open(video_list_path, "w", encoding="utf-8") as vf:
        for v in sorted(global_video_urls):
            vf.write(v + "\n")

    print(f"Total lesson/assignment pages captured: {total_pages}")
    print(f"Total distinct video URLs: {len(global_video_urls)}")
    print(f"Output written under: {os.path.abspath(dest_dir)}")
    print(f"Global video list: {video_list_path}")

    # OPTIONAL: download all videos with yt-dlp into assets/videos
    if download_videos:
        download_videos_with_ytdlp(assets_dir, video_list_path)
    else:
        print("Video download disabled (--no-video-download).")


if __name__ == "__main__":
    main()
