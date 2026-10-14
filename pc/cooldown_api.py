"""
클로드 쿨다운 — API 사용량
==========================
구독 한도(5시간·주간)와 따로, **API 키로 부른 것**이 얼마 들었나를 본다. 이 파일은
**순수 로직만** 담는다(Tk·네트워크 없음). 단독으로도 돌아간다:

    python cooldown_api.py          # 이번 달 요약을 콘솔에 출력

API 는 사용량을 따로 알려 주지 않는다(콘솔 청구 기록은 관리자 키가 있어야 읽힌다).
그래서 API 를 부르는 프로그램이 **부를 때마다 한 줄씩 남긴 기록**을 모아 셈한다.
기록이 하나도 없는 PC 에서는 메뉴에 이 항목이 안 보인다(`available`).

읽는 기록(한 줄에 JSON 하나):

    {"at": "2026-10-14 15:06:28", "who": "밴드톡 출결", "model": "claude-sonnet-5-5",
     "in": 1200, "out": 300, "cw": 0, "cr": 0, "usd": 0.0054}

- `%APPDATA%\\AdminHelper\\claude_usage.jsonl` — AdminHelper 가 쓰는 것
- `~/.claude_api_usage/*.jsonl` — 다른 프로그램도 같은 꼴로 여기에 쓰면 같이 셈한다

달러는 응답 토큰으로 센 값이라 실제 청구와 몇 센트 어긋날 수 있다.
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

DAYS = 14  # 일별 막대에 그릴 날 수
MONTHS = 6  # 달별로 셀 달 수


def sources() -> list[str]:
    """있는 기록 파일들."""
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        out.append(os.path.join(appdata, "AdminHelper", "claude_usage.jsonl"))
    out += sorted(glob.glob(os.path.join(os.path.expanduser("~"), ".claude_api_usage", "*.jsonl")))
    return [p for p in out if os.path.isfile(p)]


def available() -> bool:
    try:
        return bool(sources())
    except OSError:
        return False


def read_rows() -> list[dict]:
    rows = []
    for path in sources():
        try:
            with open(path, "rb") as f:
                raw = f.read().decode("utf-8", "replace")
        except OSError:
            continue
        for line in raw.splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue  # 반쯤 쓰다 끊긴 줄
            if not isinstance(r, dict):
                continue
            try:
                r["_at"] = datetime.strptime(str(r.get("at", ""))[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            rows.append(r)
    rows.sort(key=lambda r: r["_at"])
    return rows


@dataclass
class ApiReport:
    rows: int = 0
    first: datetime | None = None
    month_usd: float = 0.0
    month_count: int = 0
    today_usd: float = 0.0
    today_count: int = 0
    last_month_usd: float = 0.0
    forecast: float | None = None  # 이번 달 하루 평균으로 달말까지 늘린 값
    days: list = field(default_factory=list)  # [(date, usd)] 최근 DAYS 일, 오래된 것부터
    months: list = field(default_factory=list)  # [(date(달 1일), usd)] 최근 MONTHS 달
    by_who: list = field(default_factory=list)  # [(이름, 건수, usd)] 이번 달, 많이 쓴 순
    tokens_in: int = 0  # 이번 달 입력 토큰(캐시 포함)
    tokens_out: int = 0


def _month_start(d: date, back: int = 0) -> date:
    y, m = d.year, d.month - back
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


def analyze(rows: list[dict], now: datetime | None = None) -> ApiReport:
    now = now or datetime.now()
    today = now.date()
    this_m = _month_start(today)
    last_m = _month_start(today, 1)
    rep = ApiReport(rows=len(rows), first=rows[0]["_at"] if rows else None)
    per_day: dict[date, float] = {}
    per_month: dict[date, float] = {}
    who: dict[str, list] = {}
    for r in rows:
        usd = float(r.get("usd") or 0)
        d = r["_at"].date()
        per_day[d] = per_day.get(d, 0.0) + usd
        m = _month_start(d)
        per_month[m] = per_month.get(m, 0.0) + usd
        if m == this_m:
            rep.month_usd += usd
            rep.month_count += 1
            rep.tokens_in += int(r.get("in") or 0) + int(r.get("cw") or 0) + int(r.get("cr") or 0)
            rep.tokens_out += int(r.get("out") or 0)
            w = who.setdefault(str(r.get("who") or "기타"), [0, 0.0])
            w[0] += 1
            w[1] += usd
        elif m == last_m:
            rep.last_month_usd += usd
        if d == today:
            rep.today_usd += usd
            rep.today_count += 1
    rep.days = [(today - timedelta(days=i), per_day.get(today - timedelta(days=i), 0.0))
                for i in range(DAYS - 1, -1, -1)]
    rep.months = [(_month_start(today, i), per_month.get(_month_start(today, i), 0.0))
                  for i in range(MONTHS - 1, -1, -1)]
    rep.by_who = sorted(((k, v[0], v[1]) for k, v in who.items()), key=lambda t: -t[2])
    # 이번 달 첫 기록(이번 달에 처음 켰으면 그날)부터 오늘까지의 하루 평균으로 늘린다
    month_days = [d for d in per_day if d >= this_m]
    if month_days:
        start = min(month_days)
        span = (today - start).days + 1
        left = (_month_start(today, -1) - today).days - 1
        rep.forecast = rep.month_usd + rep.month_usd / span * left
    return rep


def usd_text(v: float) -> str:
    """$1 밑은 센트 아래 한 자리까지 — $0.04 와 $0.004 가 다 0.00 으로 보이지 않게."""
    return f"${v:,.2f}" if v >= 1 or v == 0 else f"${v:.3f}"


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("기록:", sources() or "없음")
    r = analyze(read_rows())
    print(f"이번 달 {usd_text(r.month_usd)} ({r.month_count}건) · 오늘 {usd_text(r.today_usd)}"
          f" · 지난 달 {usd_text(r.last_month_usd)}"
          + (f" · 달말 예상 {usd_text(r.forecast)}" if r.forecast is not None else ""))
    for name, n, usd in r.by_who:
        print(f"  {name:12} {n:4}건 {usd_text(usd)}")
    print("일별:", " ".join(f"{d:%m/%d}={usd_text(v)}" for d, v in r.days if v))
