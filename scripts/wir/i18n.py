"""UI strings for charts and the PDF report (uk / en)."""
from __future__ import annotations

STR = {
    "en": {
        "axis_pm": "views per 1M views of the edition",
        "axis_pm_log": "views per 1M edition views (log scale)",
        "last12": "last 12 months",
        "spike_marker": "month with a spike day (excluded from trend)",
        "no_data_chart": "No article to chart",
        "report_title": "Interest in “{topic}” on Wikipedia",
        "report_sub": "{langs} · {start} – {end} ({months} full months) · humans only (agent={agent}) · "
                      "normalized per 1M views of each language edition · generated {today}",
        "answer": "Answer",
        "table_lang": "Edition", "table_article": "Article", "table_views": "Views/mo",
        "table_pm": "Per 1M", "table_change": "12-mo change", "table_trend": "Trend/yr [95% CI]",
        "table_verdict": "Verdict", "table_conf": "Confidence",
        "trust_title": "How far to trust it",
        "limits_title": "Assumptions & limitations",
        "footer": "Data: Wikimedia Analytics API (CC0) + Wikidata, retrieved {today}. Reproduce: {cmd}",
        "no_article": "no article (content gap)",
        "verdicts_short": {"growing": "growing", "declining": "declining", "flat": "flat", "mixed": "mixed",
                           "insufficient_data": "too little data", "no_article": "no article"},
        "verdicts": {"growing": "growing", "declining": "declining", "flat": "flat", "mixed": "mixed signals",
                     "insufficient_data": "insufficient data", "no_article": "no article"},
        "conf": {"high": "high", "medium": "medium", "low": "low", None: "—"},
        "sent_ok": "{lang}: interest {verdict} ({change} over 12 months as share of the edition; "
                   "trend {trend}/yr, 95% CI {lo}..{hi}); confidence {conf}.",
        "sent_missing": "{lang}: no article on this topic — not comparable (content gap, not zero interest).",
        "sent_insufficient": "{lang}: too little data to judge a trend.",
        "limits": [
            "Pageviews measure attention on Wikipedia, not willingness to pay; validate with search/app-store data or tests.",
            "A language edition is not a country; readers of big languages are spread across many markets.",
            "Bot filtering is imperfect and Wikipedia-wide traffic shifts over time; figures are normalized per edition.",
        ],
        "limit_single": "The topic is represented by {n} article(s) per edition; a basket of related articles is more robust.",
        "ranking": "Ranking ({rule}): {items}. Sensitivity: {stab}.",
    },
    "uk": {
        "axis_pm": "переглядів на 1 млн переглядів розділу",
        "axis_pm_log": "переглядів на 1 млн переглядів розділу (лог. шкала)",
        "last12": "останні 12 міс.",
        "spike_marker": "місяць зі сплеском (виключено з тренду)",
        "no_data_chart": "Немає статті для графіка",
        "report_title": "Інтерес до теми «{topic}» у Вікіпедії",
        "report_sub": "{langs} · {start} – {end} ({months} повних міс.) · лише люди (agent={agent}) · "
                      "нормалізовано на 1 млн переглядів кожного мовного розділу · згенеровано {today}",
        "answer": "Відповідь",
        "table_lang": "Розділ", "table_article": "Стаття", "table_views": "Перегл./міс",
        "table_pm": "На 1 млн", "table_change": "Зміна 12 міс.", "table_trend": "Тренд/рік [95% ДІ]",
        "table_verdict": "Вердикт", "table_conf": "Довіра",
        "trust_title": "Наскільки можна довіряти",
        "limits_title": "Припущення та обмеження",
        "footer": "Дані: Wikimedia Analytics API (CC0) + Wikidata, отримано {today}. Відтворити: {cmd}",
        "no_article": "статті немає (прогалина)",
        "verdicts_short": {"growing": "зростає", "declining": "знижується", "flat": "стабільно", "mixed": "суперечливо",
                           "insufficient_data": "мало даних", "no_article": "немає статті"},
        "verdicts": {"growing": "зростає", "declining": "знижується", "flat": "стабільний", "mixed": "суперечливі сигнали",
                     "insufficient_data": "замало даних", "no_article": "статті немає"},
        "conf": {"high": "висока", "medium": "середня", "low": "низька", None: "—"},
        "sent_ok": "{lang}: інтерес {verdict} ({change} за 12 міс. як частка розділу; тренд {trend}/рік, "
                   "95% ДІ {lo}..{hi}); довіра {conf}.",
        "sent_missing": "{lang}: статті на цю тему немає — порівняння неможливе (прогалина в контенті, а не нульовий інтерес).",
        "sent_insufficient": "{lang}: замало даних, щоб судити про тренд.",
        "limits": [
            "Перегляди — це увага у Вікіпедії, а не готовність платити; перевіряйте пошуковими даними, даними магазинів застосунків або тестами.",
            "Мовний розділ ≠ країна: читачі великих мов розподілені між багатьма ринками.",
            "Фільтр ботів неідеальний, а загальний трафік Вікіпедії змінюється; тому показники нормалізовані на розділ.",
        ],
        "limit_single": "Тему представлено {n} стат. на розділ; кошик пов'язаних статей дав би надійніший сигнал.",
        "ranking": "Рейтинг ({rule}): {items}. Стійкість: {stab}.",
    },
}

MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
MONTHS_UK_LOC = ["січні", "лютому", "березні", "квітні", "травні", "червні", "липні", "серпні",
                 "вересні", "жовтні", "листопаді", "грудні"]

CHECK_MSG = {
    "volume_alert": ("only {total} views in the last 12 months (<1/day): too little to trust a trend",
                     "лише {total} переглядів за 12 міс. (<1 на день): замало, щоб довіряти тренду"),
    "volume_warn": ("low volume: median {med} views/day in the last 12 months",
                    "малий обсяг: медіана {med} переглядів/день за останні 12 міс."),
    "volume_ok": ("median {med} views/day in the last 12 months",
                  "медіана {med} переглядів/день за останні 12 міс."),
    "spikes_flip": ("the 12-month change flips sign without spike days ({top}): news-driven, not a trend",
                    "без днів-сплесків зміна за 12 міс. змінює знак ({top}): це новинний ефект, а не тренд"),
    "spikes_alert": ("{share}% of window views fall on spike days ({top})",
                     "{share}% переглядів періоду припадає на дні-сплески ({top})"),
    "spikes_warn": ("{share}% of window views fall on spike days ({top}); the trend is computed without them",
                    "{share}% переглядів — дні-сплески ({top}); тренд пораховано без них"),
    "spikes_small": ("spikes are small ({share}% of views; largest: {top}); excluded from the trend",
                     "сплески незначні ({share}% переглядів; найбільші: {top}); виключені з тренду"),
    "spikes_none": ("no spike days detected", "днів-сплесків не виявлено"),
    "agreement_alert": ("methods disagree: 12-month change {c12}%, trend {tr}%/yr [{lo}; {hi}]",
                        "методи розходяться: зміна за 12 міс. {c12}%, тренд {tr}%/рік [{lo}; {hi}]"),
    "agreement_ok": ("12-month change, same-month YoY and trend agree in direction (range {a}..{b}%)",
                     "зміна за 12 міс., порівняння тих самих місяців і тренд узгоджені за напрямком "
                     "(діапазон {a}..{b}%)"),
    "precision_warn": ("wide 95% interval for the trend ({lo}..{hi}%/yr): direction ok, size uncertain",
                       "широкий 95% інтервал тренду ({lo}..{hi}%/рік): напрямок надійний, величина — ні"),
    "momentum_turn": ("the last 6 months vs a year earlier ({y6}%) point the other way than the 12-month "
                      "change ({c12}%): possible turning point, wait for more data",
                      "останні 6 міс. рік до року ({y6}%) показують протилежний напрямок до зміни за 12 міс. "
                      "({c12}%): можливий перелом, потрібні нові дані"),
    "momentum_slowing": ("the change is slowing: last 6 months vs a year earlier {y6}% against {c12}% over 12 months",
                         "зміна сповільнюється: останні 6 міс. рік до року {y6}% проти {c12}% за 12 міс."),
    "momentum_accel": ("the change is accelerating: last 6 months vs a year earlier {y6}% against {c12}% over 12 months",
                       "зміна прискорюється: останні 6 міс. рік до року {y6}% проти {c12}% за 12 міс."),
    "norm_warn": ("raw views {rc}% but share of the edition {c12}%: the edition itself changed {pc}%, "
                  "so the direction depends on normalization",
                  "сирі перегляди {rc}%, а частка в розділі {c12}%: сам розділ змінився на {pc}%, "
                  "тож напрямок залежить від нормалізації"),
    "norm_info": ("the whole {project} changed {pc}% over the same 12 months; figures are per 1M edition "
                  "views to remove that",
                  "увесь {project} змінився на {pc}% за ті самі 12 міс.; показники подано на 1 млн "
                  "переглядів розділу, щоб це прибрати"),
    "bots_warn": ("{share}% of all views are bots/automated; undetected bots may remain in 'user' views",
                  "{share}% усіх переглядів — боти; частина неперехоплених ботів може лишатися серед «людей»"),
    "bots_info": ("{share}% of all views are bots/automated (excluded)",
                  "{share}% усіх переглядів — боти (виключено)"),
    "age_alert": ("article first seen {first}, inside the window: growth partly reflects a new page being indexed",
                  "стаття з'явилася {first}, усередині періоду: зростання частково пояснюється індексацією нової сторінки"),
    "age_warn": ("article first seen {first}, shortly before the window",
                 "стаття з'явилася {first}, незадовго до періоду"),
    "season_info": ("seasonal: peak in {peak_en} (x{ratio} of an average month); compare 12-month totals "
                    "or the same months, never adjacent seasons",
                    "сезонність: пік у {peak_uk} (×{ratio} від середнього місяця); порівнюйте 12-місячні суми "
                    "або ті самі місяці, а не сусідні сезони"),
    "break": ("{start}..{end}: {note}", "{start}..{end}: {note_uk}"),
    "conc_alert": ("{share}% of the last 12 months' views fall in {month}; without that month the change is {wo}% "
                   "instead of {c12}%: an event, not a lasting trend",
                   "{share}% переглядів за 12 міс. припадає на {month}; без цього місяця зміна {wo}% замість "
                   "{c12}%: це подія, а не стійкий тренд"),
    "conc_warn": ("{share}% of the last 12 months' views fall in {month}: attention is concentrated around an event",
                  "{share}% переглядів за 12 міс. припадає на {month}: увага зосереджена навколо події"),
    "trim_warn": ("the trend is {t0}%/yr but {t3}%/yr without the last 3 months: the recent months drive it",
                  "тренд {t0}%/рік, але без останніх 3 міс. — {t3}%/рік: його визначають останні місяці"),
    "oneoff_info": ("the largest month ({month}) does not recur in other years: a one-off peak, not seasonality",
                    "найбільший місяць ({month}) не повторюється в інші роки: разовий пік, а не сезонність"),
    "basket_warn": ("only {pct}% of the topic's articles move in the overall direction",
                    "лише {pct}% статей теми рухаються в загальному напрямку"),
    "basket_alert": ("removing '{label}' reverses the direction: the topic trend rests on one article",
                     "без статті «{label}» напрямок змінюється: тренд теми тримається на одній статті"),
    "coverage_info": ("articles missing in this edition: {items}", "у цьому розділі немає статей: {items}"),
    "redirects_info": ("redirects carry {share}% of views (renamed page or common alias)",
                       "редиректи дають {share}% переглядів (перейменування або поширена альтернативна назва)"),
    "ambiguity_warn": ("'{label}' is ambiguous; used {qid} ({desc}). Re-run with --qid if the user meant something else",
                       "«{label}» — неоднозначна назва; використано {qid} ({desc})"),
    "proxy_info": ("'{title}' was chosen by the user, not matched via Wikidata",
                   "статтю «{title}» задав користувач, а не Wikidata"),
}


def render_check(check: dict, lang: str = "en") -> str:
    en, uk = CHECK_MSG[check["key"]]
    tpl = uk if lang == "uk" else en
    try:
        return tpl.format(**check["params"])
    except (KeyError, IndexError):
        return en.format(**check["params"])


def t(lang: str, key: str):
    return STR.get(lang, STR["en"]).get(key, STR["en"][key])
