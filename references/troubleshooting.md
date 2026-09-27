# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `uv: command not found` | uv not installed | Install uv (https://docs.astral.sh/uv/getting-started/installation/), then rerun. |
| exit 3 `Unknown Wikipedia language 'ua'` | country code instead of an edition code | Use the suggested code (`uk` for Ukrainian, `cs` for Czech, `el` for Greek, `ja` for Japanese). |
| exit 4 `Wikidata has no item matching` | unusual wording | Retry with the English name of the topic, or pass `--qid Q…` if you know the item. |
| summary says `NO ARTICLE` | no article in that edition | Report it as a content gap. Only with the user's consent: `--title <lang>=<exact title>` of a proxy article. |
| summary says `AMBIGUOUS` | the name has several meanings | Show the listed meanings to the user, then rerun with `--qid`. |
| exit 6 / `HTTP 429` messages on stderr | Wikimedia rate limit (200 req/min with a proper User-Agent, 10 req/min without) | Wait a minute and rerun the same command: fetched data is cached and not requested again. Set `WIR_CONTACT` to an email or URL to identify yourself. |
| very slow first run with many editions | each article × edition is a separate API series | Keep a run to ≤ 60 topic×edition pairs; follow-ups with `--from` reuse the cache. |
| garbled Cyrillic in the terminal (Windows) | console code page | The script writes UTF-8; read `summary.md` in the run directory, or set `PYTHONIOENCODING=utf-8`. |
| a `Python\` folder (~170 MB) appears in the working directory (Windows) | the shell has no `LOCALAPPDATA`, so the Windows `python.exe` alias (Python install manager) installs a runtime into `.\Python` when uv probes it | Set `LOCALAPPDATA=%USERPROFILE%\AppData\Local` in that shell; the folder is not needed and can be deleted. |
| `--offline` fails with "not cached" | offline mode only reads the cache | Run once online first. |

Environment variables: `WIR_CONTACT` (contact for the User-Agent), `WIR_CACHE_DIR` (cache location, default
`%LOCALAPPDATA%\wiki-interest-radar` on Windows, `~/.cache/wiki-interest-radar` on Linux, `~/Library/Caches/…` on macOS),
`WIR_MIN_INTERVAL` (seconds between requests, default 0.35), `WIR_QUIET=1` (no progress on stderr).
