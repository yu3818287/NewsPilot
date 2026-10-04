import asyncio
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from models.news import Category, News
from services.article_extractor import build_local_digests


TAG_RE = re.compile(r"<[^>]+>")
SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
NEWS_NAMESPACE = "https://www.bing.com/news/search"
NEWS_SYNC_LOCK = asyncio.Lock()
BLOCKED_PHRASES = (
    "真人娱乐",
    "博彩",
    "投注平台",
    "app国际最新新闻",
    "pg胜天",
    "app下载最新版",
    "游戏大厅",
    "娱乐平台",
    "黑科网",
    "独家新闻官方版",
    "安卓网",
)


@dataclass
class LiveArticle:
    title: str
    summary: str
    source_name: str
    source_url: str
    publish_time: datetime
    category_name: str
    image: str | None = None
    content: str = ""
    raw_text: str = ""
    existing_id: int | None = None


def _plain_text(value: str | None) -> str:
    text = html.unescape(TAG_RE.sub(" ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _infer_category(query: str, title: str) -> str:
    title_value = title.lower()
    rules = {
        "国际": ["国际", "world", "global", "联合国", "美国", "欧洲", "日本", "韩国", "特朗普"],
        "财经": ["财经", "经济", "finance", "market", "股市", "央行", "公司"],
        "科技": ["科技", "ai", "人工智能", "芯片", "science", "technology", "机器人"],
        "体育": ["体育", "football", "basketball", "比赛", "冠军", "亚运"],
        "娱乐": ["娱乐", "电影", "音乐", "明星"],
        "社会": ["社会", "民生", "教育", "医疗"],
    }
    for category, words in rules.items():
        if any(word in title_value for word in words):
            return category
    query_value = query.lower()
    for category, words in rules.items():
        if any(word in query_value for word in words):
            return category
    return "国内"


def _normalise_search_query(query: str) -> str:
    lowered = query.lower()
    topic_rules = (
        (("人工智能", "ai", "大模型", "机器人"), "人工智能 科技"),
        (("财经", "经济", "股市", "金融"), "财经 经济"),
        (("体育", "足球", "篮球", "比赛"), "体育"),
        (("国际", "国外", "全球", "世界"), "国际 要闻"),
        (("国内", "中国", "社会", "民生"), "中国 要闻"),
    )
    matches = [replacement for hints, replacement in topic_rules if any(hint in lowered for hint in hints)]
    if matches:
        return " ".join(dict.fromkeys(matches))
    cleaned = re.sub(
        r"请|帮我|给我|推荐|筛选|查找|寻找|看看|新闻|资讯|最新|今天|今日|当日|实时|值得关注|\d+条|[？?，,。]",
        " ",
        query,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= 2 else "中国 国际 要闻"


def _actual_source_url(bing_link: str) -> str:
    try:
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(bing_link).query)
        return values.get("url", [bing_link])[0]
    except ValueError:
        return bing_link


def _child_text(item, suffix: str) -> str:
    for child in item:
        if child.tag.lower().endswith(suffix.lower()):
            return _plain_text(child.text)
    return ""


def _download_bing_rss(query: str, limit: int) -> list[LiveArticle]:
    params = urllib.parse.urlencode(
        {"q": _normalise_search_query(query), "format": "rss", "setlang": "zh-cn"}
    )
    url = f"https://www.bing.com/news/search?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 NewsPilot/2.1"})
    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    articles: list[LiveArticle] = []
    now = datetime.now()
    for item in root.findall("./channel/item"):
        title = _plain_text(item.findtext("title"))
        link = _actual_source_url((item.findtext("link") or "").strip())
        summary = _plain_text(item.findtext("description"))
        source = _child_text(item, "Source") or urllib.parse.urlsplit(link).hostname or "公开新闻源"
        image = _child_text(item, "Image") or None
        if image:
            image = image.replace("http://www.bing.com/", "https://www.bing.com/")
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo:
                published = published.astimezone(SHANGHAI).replace(tzinfo=None)
        except (TypeError, ValueError):
            continue
        if published.year != settings.news_year or published > now:
            continue
        if published < now - timedelta(days=14):
            continue
        if not link or not title or title.endswith("/"):
            continue
        if any(phrase in title.lower() for phrase in BLOCKED_PHRASES):
            continue
        articles.append(
            LiveArticle(
                title=title[:255],
                summary=(summary or title)[:500],
                source_name=source[:100],
                source_url=link[:1000],
                publish_time=published,
                category_name=_infer_category(query, title),
                image=image,
            )
        )
        if len(articles) >= limit:
            break
    return articles


def _download_google_rss(query: str, limit: int) -> list[LiveArticle]:
    search = f"{query} when:2d after:{settings.news_year}-01-01"
    params = urllib.parse.urlencode({"q": search, "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"})
    request = urllib.request.Request(
        f"https://news.google.com/rss/search?{params}",
        headers={"User-Agent": "Mozilla/5.0 NewsPilot/2.1"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())
    articles = []
    now = datetime.now()
    for item in root.findall("./channel/item"):
        title = _plain_text(item.findtext("title"))
        source_node = item.find("source")
        source = _plain_text(source_node.text if source_node is not None else "Google News")
        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.tzinfo:
                published = published.astimezone(SHANGHAI).replace(tzinfo=None)
        except (TypeError, ValueError):
            continue
        if published.year != settings.news_year or published > now:
            continue
        if any(phrase in title.lower() for phrase in BLOCKED_PHRASES):
            continue
        articles.append(
            LiveArticle(
                title=title[:255],
                summary=_plain_text(item.findtext("description"))[:500] or title,
                source_name=source[:100],
                source_url=(item.findtext("link") or "")[:1000],
                publish_time=published,
                category_name=_infer_category(query, title),
            )
        )
        if len(articles) >= limit:
            break
    return articles


async def search_live_news(query: str, limit: int = 12) -> list[LiveArticle]:
    try:
        articles = await asyncio.to_thread(_download_bing_rss, query, limit)
        if articles:
            return articles
    except Exception:
        pass
    return await asyncio.to_thread(_download_google_rss, query, limit)


async def _prepare_candidates(db: AsyncSession, articles: list[LiveArticle]) -> list[LiveArticle]:
    candidates = []
    seen_urls = set()
    seen_titles = set()
    for article in articles:
        normalized_title = "".join(article.title.lower().split())
        normalized_url = article.source_url.rstrip("/")
        if normalized_url in seen_urls or normalized_title in seen_titles:
            continue
        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        result = await db.execute(
            select(News).where(
                or_(News.source_url == article.source_url, News.title == article.title)
            ).limit(1)
        )
        existing = result.scalars().first()
        if existing:
            article.existing_id = existing.id
            needs_upgrade = not existing.image or len(existing.content or "") < 450 or "公开 RSS 聚合" in (existing.content or "")
            if needs_upgrade:
                candidates.append(article)
        else:
            candidates.append(article)
    return candidates


async def save_articles(db: AsyncSession, articles: list[LiveArticle]) -> list[News]:
    category_rows = (await db.execute(select(Category))).scalars().all()
    categories = {row.name: row.id for row in category_rows}
    stored = []
    for article in articles:
        news = await db.get(News, article.existing_id) if article.existing_id else None
        if news:
            news.description = article.summary
            news.content = article.content
            news.image = article.image or news.image
            news.source_url = article.source_url
            news.source_name = article.source_name
            news.author = article.source_name
            news.publish_time = article.publish_time
            news.fetched_at = datetime.now()
        else:
            news = News(
                title=article.title,
                description=article.summary,
                content=article.content,
                image=article.image,
                author=article.source_name,
                category_id=categories.get(article.category_name) or categories.get("头条") or 1,
                views=0,
                publish_time=article.publish_time,
                source_url=article.source_url,
                source_name=article.source_name,
                is_ai_fetched=True,
                fetched_at=datetime.now(),
            )
            db.add(news)
        stored.append(news)
    if stored:
        await db.flush()
        for news in stored:
            await db.refresh(news)
    return stored


async def fetch_and_store(db: AsyncSession, query: str, limit: int = 12) -> list[News]:
    async with NEWS_SYNC_LOCK:
        found = await search_live_news(query, limit)
        candidates = await _prepare_candidates(db, found)
        if not candidates:
            return []
        await build_local_digests(candidates)
        return await save_articles(db, candidates)


async def sync_default_feeds(db: AsyncSession) -> int:
    total = 0
    for query in ("中国 要闻", "国际 要闻", "人工智能 科技"):
        total += len(await fetch_and_store(db, query, 8))
    return total
