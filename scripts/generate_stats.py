#!/usr/bin/env python3
"""Генерация SVG-карточек статистики GitHub для профиля rasuliyonn.

Тянет данные из GitHub GraphQL + REST и рисует четыре карточки в стиле
баннера профиля (тёмный фон #0B1120, акценты #38BDF8 / #818CF8 / #C084FC).
Никаких сторонних сервисов — файлы коммитятся в репозиторий.
"""

import datetime as dt
import json
import os
import urllib.error
import urllib.request

TOKEN = os.environ.get("GITHUB_TOKEN", "")
LOGIN = os.environ.get("GH_LOGIN", "rasuliyonn")
OUT_DIR = os.environ.get("OUT_DIR", "assets")

BG = "#0B1120"
BORDER = "#1E293B"
TITLE = "#38BDF8"
ACCENT = "#818CF8"
ACCENT2 = "#C084FC"
TEXT = "#9FB0C9"
BRIGHT = "#E2E8F0"
DIM = "#64748B"

FONT = "'Segoe UI',-apple-system,'Helvetica Neue',Arial,sans-serif"
MONO = "'SF Mono','JetBrains Mono',Consolas,monospace"

MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн",
             "июл", "авг", "сен", "окт", "ноя", "дек"]

LANG_COLORS = {
    "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "Python": "#3572A5",
    "HTML": "#E34C26", "CSS": "#563D7C", "SCSS": "#C6538C",
    "EJS": "#A91E50", "Shell": "#89E051", "Java": "#B07219",
    "C#": "#178600", "C++": "#F34B7D", "Go": "#00ADD8",
    "PHP": "#4F5D95", "Ruby": "#701516", "Vue": "#41B883",
    "Svelte": "#FF3E00", "Astro": "#FF5A03", "Dockerfile": "#384D54",
    "Jupyter Notebook": "#DA5B0B", "Batchfile": "#C1F12E",
}


# ---------------------------------------------------------------- API

def _request(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats-generator")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def graphql(query, variables):
    return _request("https://api.github.com/graphql",
                    {"query": query, "variables": variables})


PROFILE_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}
"""


def fetch_profile():
    data = graphql(PROFILE_QUERY, {"login": LOGIN})
    if "errors" in data:
        raise SystemExit("GraphQL error: " + json.dumps(data["errors"], ensure_ascii=False))
    return data["data"]["user"]


def fetch_languages():
    """Суммарные байты по языкам для публичных репозиториев."""
    repos, page = [], 1
    while True:
        chunk = _request(
            f"https://api.github.com/users/{LOGIN}/repos"
            f"?per_page=100&type=owner&page={page}"
        )
        if not chunk:
            break
        repos.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1

    totals = {}
    for repo in repos:
        if repo.get("fork") or repo.get("archived"):
            continue
        try:
            langs = _request(repo["languages_url"])
        except urllib.error.HTTPError:
            continue
        for name, size in langs.items():
            totals[name] = totals.get(name, 0) + size
    return totals


# ---------------------------------------------------------------- helpers

def esc(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def fmt(number):
    """1234567 -> '1 234 567' (узкий неразрывный пробел)."""
    return f"{number:,}".replace(",", "\u202f")


def card(width, height, body, title):
    """Обёртка карточки: фон, рамка, заголовок."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" \
viewBox="0 0 {width} {height}" fill="none" role="img" aria-label="{esc(title)}">
  <defs>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{TITLE}"/>
      <stop offset="0.6" stop-color="{ACCENT}"/>
      <stop offset="1" stop-color="{ACCENT2}"/>
    </linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" fill="{BG}" stroke="{BORDER}"/>
  <rect x="26" y="0" width="64" height="3" rx="1.5" fill="url(#accent)"/>
  <text x="26" y="40" font-family="{FONT}" font-size="15" font-weight="600" \
fill="{TITLE}" letter-spacing="1.6">{esc(title)}</text>
{body}
</svg>
"""


# ---------------------------------------------------------------- cards

def stats_card(user):
    """Одна колонка: подпись слева, значение справа."""
    repos = user["repositories"]
    stars = sum(n["stargazerCount"] for n in repos["nodes"])
    contrib = user["contributionsCollection"]

    items = [
        ("Контрибуции за год", contrib["contributionCalendar"]["totalContributions"], TITLE),
        ("Коммиты", contrib["totalCommitContributions"], ACCENT),
        ("Pull Requests", contrib["totalPullRequestContributions"], ACCENT2),
        ("Issues", contrib["totalIssueContributions"], TITLE),
        ("Звёзды", stars, ACCENT),
        ("Репозитории", repos["totalCount"], ACCENT2),
    ]

    width = 430
    height = 78 + len(items) * 34
    label_x, value_x = 44, width - 26
    rows = []
    for index, (label, value, color) in enumerate(items):
        y = 78 + index * 34
        rows.append(
            f'  <circle cx="30" cy="{y - 4}" r="4" fill="{color}"/>\n'
            f'  <text x="{label_x}" y="{y}" font-family="{FONT}" font-size="13" '
            f'fill="{TEXT}">{esc(label)}</text>\n'
            f'  <text x="{value_x}" y="{y}" text-anchor="end" font-family="{MONO}" '
            f'font-size="15" font-weight="700" fill="{BRIGHT}">{esc(fmt(value))}</text>'
        )
    return card(width, height, "\n".join(rows), "СТАТИСТИКА GITHUB")


def langs_card(totals, limit=6):
    """Горизонтальные полосы по доле языка."""
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    total = sum(totals.values()) or 1

    width = 430
    height = 78 + len(ranked) * 34
    bar_x, bar_w = 26, width - 52
    parts = []
    for index, (name, size) in enumerate(ranked):
        pct = size / total * 100
        y = 78 + index * 34
        color = LANG_COLORS.get(name, ACCENT)
        filled = max(bar_w * pct / 100, 4)
        parts.append(
            f'  <text x="{bar_x}" y="{y}" font-family="{FONT}" font-size="12.5" '
            f'fill="{BRIGHT}">{esc(name)}</text>\n'
            f'  <text x="{bar_x + bar_w}" y="{y}" text-anchor="end" font-family="{MONO}" '
            f'font-size="12" fill="{TEXT}">{pct:.1f}%</text>\n'
            f'  <rect x="{bar_x}" y="{y + 7}" width="{bar_w}" height="7" rx="3.5" '
            f'fill="{BORDER}"/>\n'
            f'  <rect x="{bar_x}" y="{y + 7}" width="{filled:.1f}" height="7" rx="3.5" '
            f'fill="{color}"/>'
        )
    return card(width, height, "\n".join(parts), "ТОП ЯЗЫКОВ")


def streak_card(days):
    """Текущая серия, лучшая серия, всего контрибуций."""
    current = longest = run = 0
    for _, count in days:
        if count > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    # текущая серия: считаем назад от сегодня; если сегодня пусто — от вчера
    tail = [c for _, c in days]
    start = len(tail) - 1
    if start >= 0 and tail[start] == 0:
        start -= 1
    index = start
    while index >= 0 and tail[index] > 0:
        current += 1
        index -= 1

    total = sum(tail)
    blocks = [
        ("Текущая серия", current, "дней", TITLE),
        ("Лучшая серия", longest, "дней", ACCENT),
        ("Всего контрибуций", total, "за год", ACCENT2),
    ]

    width, height = 880, 165
    parts = []
    for index, (label, value, unit, color) in enumerate(blocks):
        x = width / 3 * (index + 0.5)
        parts.append(
            f'  <text x="{x:.0f}" y="74" text-anchor="middle" font-family="{FONT}" '
            f'font-size="13" fill="{TEXT}" letter-spacing="1">{esc(label)}</text>\n'
            f'  <text x="{x:.0f}" y="122" text-anchor="middle" font-family="{MONO}" '
            f'font-size="42" font-weight="700" fill="{color}">{esc(fmt(value))}</text>\n'
            f'  <text x="{x:.0f}" y="144" text-anchor="middle" font-family="{FONT}" '
            f'font-size="12" fill="{DIM}">{esc(unit)}</text>'
        )
        if index < 2:
            line_x = width / 3 * (index + 1)
            parts.append(f'  <line x1="{line_x:.0f}" y1="62" x2="{line_x:.0f}" y2="146" '
                         f'stroke="{BORDER}"/>')
    return card(width, height, "\n".join(parts), "СЕРИЯ КОММИТОВ")


def activity_card(weeks):
    """Площадной график контрибуций по неделям."""
    points = [sum(day["contributionCount"] for day in week["contributionDays"])
              for week in weeks]
    if not points:
        points = [0]

    width, height = 880, 260
    left, right, top, bottom = 26, 26, 74, 40
    plot_w = width - left - right
    plot_h = height - top - bottom
    peak = max(points) or 1
    step = plot_w / max(len(points) - 1, 1)

    coords = []
    for index, value in enumerate(points):
        x = left + index * step
        y = top + plot_h - (value / peak) * plot_h
        coords.append((x, y))

    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = (f"{left:.1f},{top + plot_h:.1f} " + line +
            f" {coords[-1][0]:.1f},{top + plot_h:.1f}")

    grid = "\n".join(
        f'  <line x1="{left}" y1="{top + plot_h * f:.1f}" x2="{width - right}" '
        f'y2="{top + plot_h * f:.1f}" stroke="{BORDER}" stroke-opacity="0.7"/>'
        for f in (0, 0.5, 1)
    )

    # подписи месяцев по первой неделе каждого месяца
    labels, seen = [], set()
    for index, week in enumerate(weeks):
        first = week["contributionDays"][0]["date"]
        month = int(first[5:7])
        if month not in seen:
            seen.add(month)
            labels.append(
                f'  <text x="{left + index * step:.1f}" y="{height - 14}" '
                f'font-family="{FONT}" font-size="11" fill="{DIM}">'
                f'{MONTHS_RU[month - 1]}</text>'
            )

    body = f"""  <defs>
    <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.55"/>
      <stop offset="1" stop-color="{ACCENT}" stop-opacity="0.02"/>
    </linearGradient>
    <linearGradient id="stroke" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{TITLE}"/>
      <stop offset="0.5" stop-color="{ACCENT}"/>
      <stop offset="1" stop-color="{ACCENT2}"/>
    </linearGradient>
  </defs>
{grid}
  <polygon points="{area}" fill="url(#fill)"/>
  <polyline points="{line}" fill="none" stroke="url(#stroke)" stroke-width="2.5" \
stroke-linejoin="round" stroke-linecap="round"/>
{chr(10).join(labels)}
  <text x="{width - right}" y="40" text-anchor="end" font-family="{MONO}" \
font-size="12" fill="{TEXT}">макс. {esc(fmt(peak))}/нед</text>"""

    return card(width, height, body, "АКТИВНОСТЬ ЗА ГОД")


# ---------------------------------------------------------------- main

def main():
    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN не задан")

    user = fetch_profile()
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [(d["date"], d["contributionCount"])
            for week in weeks for d in week["contributionDays"]]

    try:
        languages = fetch_languages()
    except Exception as exc:  # языки не критичны — не роняем весь прогон
        print(f"  ! языки не получены: {exc}")
        languages = {}

    os.makedirs(OUT_DIR, exist_ok=True)
    files = {
        "stats.svg": stats_card(user),
        "top-langs.svg": langs_card(languages) if languages else None,
        "streak.svg": streak_card(days),
        "activity.svg": activity_card(weeks),
    }

    for name, svg in files.items():
        if svg is None:
            continue
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(svg)
        print(f"  ✓ {path} ({len(svg)} B)")

    contrib = user["contributionsCollection"]
    print(f"  контрибуций за год: {contrib['contributionCalendar']['totalContributions']}")


if __name__ == "__main__":
    main()
