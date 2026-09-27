"""Language-edition lookup: codes, names, Wikidata site ids, hosts."""
from __future__ import annotations

import difflib
import json
from functools import lru_cache

from . import config

# Frequent mistakes: country codes / legacy codes that are not Wikipedia editions.
ALIASES = {
    "ua": "uk", "cz": "cs", "gr": "el", "jp": "ja", "dk": "da", "kr": "ko", "cn": "zh",
    "rs": "sr", "by": "be", "ge": "ka", "il": "he", "iw": "he", "in": "id",
    "us": "en", "gb": "en", "en-us": "en", "en-gb": "en", "pt-br": "pt", "pt-pt": "pt",
    "zh-cn": "zh", "zh-tw": "zh", "nb": "no", "zh-min-nan": "nan", "zh-yue": "yue",
    "zh-classical": "lzh", "als": "gsw", "be-x-old": "be-tarask",
}

# Ukrainian names for the most requested editions (English/native names come from the asset).
UK_NAMES = {
    "українська": "uk", "англійська": "en", "польська": "pl", "чеська": "cs", "словацька": "sk",
    "німецька": "de", "французька": "fr", "іспанська": "es", "італійська": "it",
    "португальська": "pt", "румунська": "ro", "угорська": "hu", "болгарська": "bg",
    "сербська": "sr", "хорватська": "hr", "словенська": "sl", "литовська": "lt",
    "латиська": "lv", "естонська": "et", "фінська": "fi", "шведська": "sv", "норвезька": "no",
    "данська": "da", "нідерландська": "nl", "грецька": "el", "турецька": "tr", "російська": "ru",
    "білоруська": "be", "грузинська": "ka", "вірменська": "hy", "азербайджанська": "az",
    "казахська": "kk", "арабська": "ar", "іврит": "he", "перська": "fa", "гінді": "hi",
    "бенгальська": "bn", "індонезійська": "id", "малайська": "ms", "в'єтнамська": "vi",
    "тайська": "th", "китайська": "zh", "японська": "ja", "корейська": "ko", "урду": "ur",
    "суахілі": "sw", "філіппінська": "tl", "тагальська": "tl", "каталанська": "ca",
}


@lru_cache(maxsize=1)
def editions() -> dict[str, dict]:
    return json.loads((config.ASSETS / "wikipedias.json").read_text(encoding="utf-8"))


class UnknownLanguage(ValueError):
    pass


def normalize(token: str) -> str:
    """Map a code or a language name to a Wikipedia edition code, or raise."""
    raw = token.strip()
    t = raw.lower().replace("_", "-")
    ed = editions()
    if t.endswith(".wikipedia.org"):
        t = t.split(".")[0]
    if t.endswith("wiki") and t[:-4] in ed:
        t = t[:-4]
    if t in ed:
        return t
    if t in ALIASES:
        return ALIASES[t]
    if t in UK_NAMES:
        return UK_NAMES[t]
    for code, info in ed.items():
        if t in ((info.get("en") or "").lower(), (info.get("native") or "").lower()):
            return code
    names = list(ed) + [(i.get("en") or "").lower() for i in ed.values()] + list(UK_NAMES)
    close = difflib.get_close_matches(t, names, n=3, cutoff=0.6)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    raise UnknownLanguage(
        f"Unknown Wikipedia language '{raw}'. Use edition codes such as pl (Polish), "
        f"cs (Czech), uk (Ukrainian), en (English).{hint}")


def parse_list(spec: str) -> list[str]:
    out: list[str] = []
    for tok in spec.replace(";", ",").split(","):
        if tok.strip():
            code = normalize(tok)
            if code not in out:
                out.append(code)
    return out


def host(code: str) -> str:
    return editions()[code]["host"]


def site_id(code: str) -> str:
    return editions()[code]["db"]


def english_name(code: str) -> str:
    return editions()[code].get("en") or code
