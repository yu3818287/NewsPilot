import asyncio
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from config.settings import settings
from services.deepseek import DeepSeekError, chat


SPACE_RE = re.compile(r"\s+")
SENTENCE_RE = re.compile(r"(?<=[。！？!?])")


@dataclass
class ExtractedPage:
    final_url: str
    description: str
    image_url: str | None
    text: str


class ArticleHTMLParser(HTMLParser):
    """Small dependency-free extractor focused on article metadata and paragraphs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.description = ""
        self.image_url = None
        self.paragraphs: list[str] = []
        self._skip_depth = 0
        self._content_depth = 0
        self._paragraph_depth = 0
        self._paragraph: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = {key.lower(): (value or "") for key, value in attrs}
        tag = tag.lower()
        if tag in {"script", "style", "svg", "nav", "header", "footer", "form", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"article", "main"}:
            self._content_depth += 1
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            value = attrs.get("content", "").strip()
            if key in {"og:image", "twitter:image", "twitter:image:src"} and value and not self.image_url:
                self.image_url = value
            if key in {"og:description", "description"} and len(value) > len(self.description):
                self.description = value
        if tag == "p":
            self._paragraph_depth += 1
            self._paragraph = []

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style", "svg", "nav", "header", "footer", "form", "noscript"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "p" and self._paragraph_depth:
            value = SPACE_RE.sub(" ", "".join(self._paragraph)).strip()
            if 25 <= len(value) <= 2000:
                self.paragraphs.append(value)
            self._paragraph_depth = 0
            self._paragraph = []
        if tag in {"article", "main"}:
            self._content_depth = max(0, self._content_depth - 1)

    def handle_data(self, data):
        if not self._skip_depth and self._paragraph_depth:
            self._paragraph.append(data)


def _safe_external_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme in {"http", "https"} and host not in {
            "localhost", "127.0.0.1", "::1"
        }
    except ValueError:
        return False


def _fetch_page(url: str) -> ExtractedPage:
    if not _safe_external_url(url):
        return ExtractedPage(url, "", None, "")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 NewsPilot/2.1",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        },
    )
    with urllib.request.urlopen(request, timeout=18) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            return ExtractedPage(response.geturl(), "", None, "")
        charset = response.headers.get_content_charset() or "utf-8"
        raw = response.read(2_500_000)
        try:
            markup = raw.decode(charset, errors="replace")
        except LookupError:
            markup = raw.decode("utf-8", errors="replace")
        parser = ArticleHTMLParser()
        parser.feed(markup)
        image_url = parser.image_url
        if image_url:
            image_url = urllib.parse.urljoin(response.geturl(), html.unescape(image_url))
        paragraphs = parser.paragraphs
        text = "\n".join(paragraphs[:35])
        return ExtractedPage(
            final_url=response.geturl(),
            description=SPACE_RE.sub(" ", html.unescape(parser.description)).strip(),
            image_url=image_url,
            text=text[:12_000],
        )


async def extract_page(url: str) -> ExtractedPage:
    try:
        return await asyncio.to_thread(_fetch_page, url)
    except Exception:
        return ExtractedPage(url, "", None, "")


def _cache_image(image_url: str) -> str | None:
    if not _safe_external_url(image_url):
        return None
    secure_url = image_url.replace("http://www.bing.com/", "https://www.bing.com/")
    digest = hashlib.sha256(secure_url.encode("utf-8")).hexdigest()[:24]
    settings.news_image_dir.mkdir(parents=True, exist_ok=True)
    existing = list(settings.news_image_dir.glob(f"{digest}.*"))
    if existing:
        return f"/uploads/news/{existing[0].name}"
    request = urllib.request.Request(secure_url, headers={"User-Agent": "Mozilla/5.0 NewsPilot/2.1"})
    with urllib.request.urlopen(request, timeout=18) as response:
        content_type = (response.headers.get_content_type() or "").lower()
        extensions = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
        extension = extensions.get(content_type)
        if not extension:
            return None
        payload = response.read(4_000_001)
        if not payload or len(payload) > 4_000_000:
            return None
    path = settings.news_image_dir / f"{digest}.{extension}"
    path.write_bytes(payload)
    return f"/uploads/news/{path.name}"


async def cache_image(image_url: str | None) -> str | None:
    if not image_url:
        return None
    try:
        return await asyncio.to_thread(_cache_image, image_url)
    except Exception:
        return None


def _fallback_digest(title: str, source: str, summary: str, extracted: str) -> tuple[str, str]:
    material = SPACE_RE.sub(" ", f"{summary} {extracted}").strip()
    sentences = [sentence.strip() for sentence in SENTENCE_RE.split(material) if len(sentence.strip()) > 15]
    unique = []
    seen = set()
    for sentence in sentences:
        key = sentence[:80]
        if key not in seen:
            seen.add(key)
            unique.append(sentence)
        if len("".join(unique)) >= 1200:
            break
    brief = "".join(unique)[:180] or title
    body = "\n\n".join(
        filter(
            None,
            [
                f"事件概述\n{brief}",
                f"公开报道要点\n{''.join(unique)[:1200]}",
                f"来源说明\n本地新闻代理根据 {source} 的公开报道整理，发布时间与原始来源见页面信息。",
            ],
        )
    )
    return brief[:500], body


async def build_local_digests(articles) -> None:
    """Fetch source pages and generate original local digests in one model call."""
    semaphore = asyncio.Semaphore(5)

    async def enrich(article):
        async with semaphore:
            page = await extract_page(article.source_url)
            if page.final_url and "bing.com/news/apiclick" not in page.final_url:
                article.source_url = page.final_url[:1000]
            article.raw_text = page.text
            if page.description and len(page.description) > len(article.summary):
                article.summary = page.description[:500]
            image_url = article.image or page.image_url
            article.image = await cache_image(image_url)

    await asyncio.gather(*(enrich(article) for article in articles))

    materials = []
    for index, article in enumerate(articles):
        materials.append(
            {
                "index": index,
                "title": article.title,
                "source": article.source_name,
                "published": article.publish_time.isoformat(),
                "rss_summary": article.summary,
                "source_excerpt": article.raw_text[:5000],
            }
        )
    prompt = (
        "你是中文新闻编辑。根据下面每条公开报道材料，写成适合新闻聚合应用本地阅读的原创摘要，"
        "不得补充材料中没有的事实，不得大段照抄。description 为100-180字；content 为600-1000字，"
        "使用四个纯文本段落：事件概述、关键事实、背景与影响、信息边界。若材料不足就明确写明。"
        "只返回严格 JSON：{\"articles\":[{\"index\":0,\"description\":\"...\",\"content\":\"...\"}]}。\n"
        + json.dumps(materials, ensure_ascii=False)
    )
    generated = {}
    try:
        raw = await chat([{"role": "user", "content": prompt}], temperature=0.15)
        raw = raw.strip().removeprefix("```json").removesuffix("```").strip()
        data = json.loads(raw)
        generated = {int(item["index"]): item for item in data.get("articles", [])}
    except (DeepSeekError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        generated = {}

    for index, article in enumerate(articles):
        item = generated.get(index, {})
        description = SPACE_RE.sub(" ", str(item.get("description", ""))).strip()
        content = str(item.get("content", "")).strip()
        if len(description) >= 60 and len(content) >= 300:
            article.summary = description[:500]
            article.content = content[:7000]
        else:
            article.summary, article.content = _fallback_digest(
                article.title, article.source_name, article.summary, article.raw_text
            )
