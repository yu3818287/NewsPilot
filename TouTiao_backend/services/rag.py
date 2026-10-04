import math
import re
from collections import Counter

from models.news import News


WORD_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")
STOP_CHARS = set("的了是在和与及或就都也很把被让这那一个有没有我你他她它请想看找给")


def tokenize(text: str) -> list[str]:
    raw = WORD_RE.findall((text or "").lower())
    chinese = [token for token in raw if len(token) == 1 and token not in STOP_CHARS]
    latin = [token for token in raw if len(token) > 1]
    bigrams = [f"{chinese[i]}{chinese[i + 1]}" for i in range(len(chinese) - 1)]
    return latin + chinese + bigrams


def bm25_rank(query: str, documents: list[News], limit: int = 8) -> list[News]:
    if not documents:
        return []
    query_tokens = list(dict.fromkeys(tokenize(query)))
    if not query_tokens:
        return documents[:limit]

    doc_tokens = [
        tokenize(f"{item.title} {item.description or ''} {item.content[:2000]}")
        for item in documents
    ]
    avg_length = sum(map(len, doc_tokens)) / max(len(doc_tokens), 1)
    frequencies = [Counter(tokens) for tokens in doc_tokens]
    document_frequency = Counter(
        token for tokens in doc_tokens for token in set(tokens) if token in query_tokens
    )
    scores: list[tuple[float, int]] = []
    k1, b = 1.5, 0.75
    for index, (news, tokens, frequency) in enumerate(zip(documents, doc_tokens, frequencies)):
        score = 0.0
        for token in query_tokens:
            tf = frequency[token]
            if not tf:
                continue
            df = document_frequency[token]
            idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            normalizer = tf + k1 * (1 - b + b * len(tokens) / max(avg_length, 1))
            score += idf * tf * (k1 + 1) / normalizer
        freshness = max(0, (news.publish_time.year - 2025)) * 0.08
        popularity = math.log1p(news.views or 0) * 0.015
        scores.append((score + freshness + popularity, index))
    scores.sort(reverse=True)
    return [documents[index] for score, index in scores[:limit] if score > 0]
