"""Topic -> Wikidata item -> article per language edition (+ redirects).

The agent never types article titles or URLs: everything comes from Wikidata
sitelinks, so a missing article is reported as missing, never guessed.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import asdict, dataclass, field

from . import config, langs
from .fetch import Ctx, cached_json

NOT_A_TOPIC = re.compile(
    r"scholarly article|scientific article|article published|clinical trial|journal|"
    r"disambiguation page|wikimedia category|wikimedia list|wikimedia template|song|single by|"
    r"album|film|episode|family name|given name|painting|book by|novel by|video game|"
    r"musical group|band|television series|thesis|preprint", re.I)


class ResolveError(ValueError):
    pass


@dataclass
class Article:
    lang: str
    title: str
    exists: bool = True
    length: int | None = None       # page size in bytes (content depth hint)
    redirects: list[str] = field(default_factory=list)
    source: str = "wikidata"        # wikidata | user


@dataclass
class Member:
    query: str
    qid: str | None
    label: str
    description: str
    articles: dict[str, Article | None]            # lang -> article or None (missing)
    alternatives: list[dict] = field(default_factory=list)
    ambiguous: bool = False
    gap_hints: dict[str, list[str]] = field(default_factory=dict)  # lang -> articles mentioning it
    label_uk: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["articles"] = {k: (asdict(v) if v else None) for k, v in self.articles.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Member":
        arts = {k: (Article(**v) if v else None) for k, v in d["articles"].items()}
        return cls(d["query"], d.get("qid"), d.get("label", ""), d.get("description", ""), arts,
                   d.get("alternatives", []), d.get("ambiguous", False), d.get("gap_hints", {}),
                   d.get("label_uk", ""))


def _wd(params: dict) -> str:
    params = {**params, "format": "json"}
    return config.WIKIDATA_API + "?" + urllib.parse.urlencode(params)


def search(ctx: Ctx, query: str, lang: str, limit: int = 7) -> list[dict]:
    url = _wd({"action": "wbsearchentities", "search": query, "language": lang,
               "uselang": "en", "type": "item", "limit": limit})
    status, body = cached_json(ctx, url, 30 * 86400)
    if status != 200:
        return []
    return [{"qid": x["id"], "label": x.get("label", ""), "description": x.get("description", ""),
             "match": (x.get("match") or {}).get("text", "")} for x in body.get("search", [])]


def entities(ctx: Ctx, qids: list[str], sites: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(qids), 50):
        chunk = qids[i:i + 50]
        url = _wd({"action": "wbgetentities", "ids": "|".join(chunk),
                   "props": "sitelinks|labels|descriptions", "sitefilter": "|".join(sites),
                   "languages": "en|uk"})
        status, body = cached_json(ctx, url, 14 * 86400)
        if status != 200:
            continue
        for qid, ent in body.get("entities", {}).items():
            if "missing" in ent:
                continue
            out[qid] = {
                "sitelinks": {k: v["title"] for k, v in ent.get("sitelinks", {}).items()},
                "label": (ent.get("labels", {}).get("en") or ent.get("labels", {}).get("uk") or {}).get("value", ""),
                "label_uk": (ent.get("labels", {}).get("uk") or {}).get("value", ""),
                "description": (ent.get("descriptions", {}).get("en") or {}).get("value", ""),
            }
    return out


def sitelink_counts(ctx: Ctx, qids: list[str]) -> dict[str, int]:
    """Number of Wikimedia sites linked to each item: a cheap notability proxy
    used to pick the most common meaning of an ambiguous name."""
    url = _wd({"action": "wbgetentities", "ids": "|".join(qids[:50]), "props": "sitelinks"})
    status, body = cached_json(ctx, url, 30 * 86400)
    if status != 200:
        return {}
    return {q: len(e.get("sitelinks", {})) for q, e in body.get("entities", {}).items()}


def page_info(ctx: Ctx, lang: str, titles: list[str]) -> dict[str, Article]:
    """Existence, size and main-namespace redirects for up to 50 titles per call."""
    out: dict[str, Article] = {}
    host = langs.host(lang)
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        params = {"action": "query", "prop": "redirects|info", "titles": "|".join(chunk),
                  "rdnamespace": 0, "rdlimit": "max", "rdprop": "title", "redirects": 1,
                  "format": "json", "formatversion": 2}
        pages: dict[str, dict] = {}
        alias: dict[str, str] = {}
        while True:
            url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
            status, body = cached_json(ctx, url, 14 * 86400)
            if status != 200:
                break
            q = body.get("query", {})
            for n in q.get("normalized", []) + q.get("redirects", []):
                alias[n["from"]] = n["to"]
            for p in q.get("pages", []):
                cur = pages.setdefault(p["title"], {"missing": "missing" in p or "invalid" in p,
                                                    "length": p.get("length"), "redirects": []})
                cur["redirects"] += [r["title"] for r in p.get("redirects", [])]
            if "continue" not in body:
                break
            params = {**params, **body["continue"]}
        for t in chunk:
            canon = t
            for _ in range(3):
                canon = alias.get(canon, canon)
            p = pages.get(canon)
            if p is None or p["missing"]:
                out[t] = Article(lang, t, exists=False)
            else:
                out[t] = Article(lang, canon, True, p["length"], sorted(set(p["redirects"])))
    return out


def mentions(ctx: Ctx, lang: str, phrases: list[str], limit: int = 3) -> list[str]:
    """Existing articles in `lang` that mention the topic (hint for a content gap;
    never used as data automatically)."""
    seen: list[str] = []
    for ph in [p for p in phrases if p][:2]:
        params = {"action": "query", "list": "search", "srsearch": f'"{ph}"', "srlimit": limit,
                  "srnamespace": 0, "srprop": "", "format": "json", "formatversion": 2}
        url = f"https://{langs.host(lang)}/w/api.php?" + urllib.parse.urlencode(params)
        status, body = cached_json(ctx, url, 14 * 86400)
        if status != 200:
            continue
        for hit in body.get("query", {}).get("search", []):
            if hit["title"] not in seen:
                seen.append(hit["title"])
    return seen[:limit]


def _eligible(c: dict) -> bool:
    return not NOT_A_TOPIC.search(c.get("description") or "")


def resolve_member(ctx: Ctx, query: str, codes: list[str], qid: str | None = None,
                   user_titles: dict[str, str] | None = None) -> Member:
    sites = [langs.site_id(c) for c in codes]
    user_titles = user_titles or {}
    alternatives: list[dict] = []
    ambiguous = False
    info: dict[str, dict] = {}
    if qid:
        chosen = {"qid": qid, "label": "", "description": ""}
    elif query:
        search_langs = ["en"]
        if re.search(r"[^\x00-\x7f]", query):
            search_langs += [c for c in codes if c not in search_langs][:3]
            if "uk" not in search_langs:
                search_langs.append("uk")
        cands: dict[str, dict] = {}
        for sl in search_langs:
            for rank, c in enumerate(search(ctx, query, sl)):
                if c["qid"] not in cands or rank < cands[c["qid"]]["rank"]:
                    cands[c["qid"]] = {**c, "rank": rank}
        if not cands:
            raise ResolveError(f"Wikidata has no item matching '{query}'. Try an English "
                               f"name of the topic or pass --qid.")
        ordered = sorted(cands.values(), key=lambda c: c["rank"])
        info = entities(ctx, [c["qid"] for c in ordered], sites + ["enwiki"])
        for c in ordered:
            c["coverage"] = sum(1 for s in sites if s in info.get(c["qid"], {}).get("sitelinks", {}))
        eligible = [c for c in ordered if _eligible(c)] or ordered
        chosen = eligible[0]
        # Prefer an equally named item that actually has articles in the requested editions.
        if chosen["coverage"] == 0:
            better = [c for c in eligible if c["coverage"] > 0 and
                      c["label"].casefold() == chosen["label"].casefold()]
            if better:
                chosen = better[0]
        q = query.casefold()
        same_name = [c for c in eligible if c["qid"] != chosen["qid"] and c["label"].casefold() == q
                     and c["coverage"] >= max(1, len(sites) // 2)]
        ambiguous = bool(same_name) and chosen["label"].casefold() == q
        if ambiguous:
            # default to the most widely covered meaning (planet Mercury, not the car brand)
            pool = [chosen] + same_name
            counts = sitelink_counts(ctx, [c["qid"] for c in pool])
            chosen = max(pool, key=lambda c: (counts.get(c["qid"], 0), -c["rank"]))
        alternatives = [{"qid": c["qid"], "label": c["label"], "description": c["description"],
                         "coverage": f"{c['coverage']}/{len(sites)}"}
                        for c in eligible if c["qid"] != chosen["qid"]][:4]
    else:
        raise ResolveError("Give a topic (--topic) or a Wikidata id (--qid).")

    if chosen["qid"] not in info:
        info = entities(ctx, [chosen["qid"]], sites)
    if chosen["qid"] not in info:
        raise ResolveError(f"Wikidata item {chosen['qid']} not found.")
    ent = info[chosen["qid"]]
    member = Member(query=query or chosen["qid"], qid=chosen["qid"],
                    label=ent["label"] or chosen.get("label", ""),
                    description=ent["description"] or chosen.get("description", ""),
                    articles={}, alternatives=alternatives, ambiguous=ambiguous,
                    label_uk=ent.get("label_uk", ""))
    for code in codes:
        if code in user_titles:
            title, source = user_titles[code], "user"
        else:
            title, source = ent["sitelinks"].get(langs.site_id(code)), "wikidata"
        if not title:
            member.articles[code] = None
            continue
        art = page_info(ctx, code, [title])[title]
        art.source = source
        member.articles[code] = art if art.exists else None
    for code, art in member.articles.items():
        if art is None:
            phrases = [member.label] + ([query] if query and query.casefold() != member.label.casefold() else [])
            member.gap_hints[code] = mentions(ctx, code, phrases)
    return member
