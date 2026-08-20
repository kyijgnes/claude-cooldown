"""
클로드 쿨다운 — 사용량 기록·통계
==================================
위젯이 조회에 성공할 때마다 퍼센트를 한 줄씩 남기고(`record`), 쌓인 기록에서
'언제 얼마나 썼나'를 셈한다(`analyze`). 이 파일은 **순수 로직만** 담는다
(Tk·네트워크 없음). 단독으로도 돌아간다:

    python cooldown_stats.py        # 지금까지 쌓인 기록 요약을 콘솔에 출력

**사용량 = 주간 퍼센트가 오른 만큼(%p).** 5시간 퍼센트는 5시간마다 0으로 돌아가
더할 수가 없지만, 주간 퍼센트는 7일 창 안에서 늘기만 하므로 그 증가분이 곧 그
사이에 쓴 양이다. 창이 바뀌는 순간(초기화)만 따로 다룬다 — 그때는 퍼센트가
떨어지므로, 뺄셈 대신 **새 창에서 지금까지 쓴 양**을 그 증가분으로 본다.

기록 파일은 `~/.claude_cooldown_history.jsonl` — 한 줄에 한 표본:

    [찍은때, 5시간%, 주간%, 5시간초기화, 주간초기화]      (시각은 전부 epoch 초)

값이 그대로면 안 쓴다(클로드를 안 쓰면 퍼센트가 안 변한다). 다만 `HEARTBEAT`
간격으로 한 줄은 남겨, 기록이 끊긴 구간(컴퓨터 꺼짐)과 '안 쓴 구간'을 가른다.

★★ **초기화 시각은 분 단위로 맞춰서 쓰고 읽는다**(`_grid`). 서버가 주는 `resets_at`
은 요청 때마다 **1초씩 흔들린다**(`…01:59:59.55` ↔ `…02:00:00.4` — 남은 시간을
초 단위로 잘라 지금에 더해 주는 듯하다). 그 1초를 '창이 바뀐 것'으로 읽으면
`deltas` 가 표본마다 **주간 퍼센트 전체를 새로 더해** 하루 사용량이 수천 %p 로
나온다(2026-08-20 에 잡은 버그). 초기화 시각은 실제로 늘 분 경계라, 분으로
반올림하면 흔들림이 통째로 사라진다 — 옛 기록도 읽을 때 같이 맞춰 준다.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

HIST_PATH = os.path.join(os.path.expanduser("~"), ".claude_cooldown_history.jsonl")

KEEP_DAYS = 120  # 이보다 오래된 줄은 덜어낸다
HEARTBEAT = 1800  # 값이 그대로여도 이 간격(초)마다 한 줄은 남긴다
TRIM_AT = 40000  # 줄이 이보다 많아지면 한 번 정리한다 (앱 시작할 때만 본다)
GRID = 60  # 초기화 시각을 맞출 눈금(초) — 응답이 ±1초로 흔들린다 (맨 위 설명)
FIVE_SPAN = timedelta(hours=5)
WEEK_SPAN = timedelta(days=7)
DAY_PP = 100 / 7  # 하루치 사용량(%p) — 주간 한도를 7일에 고르게 나눈 값
GAP_SEC = HEARTBEAT * 2  # 표본이 이보다 벌어지면 기록이 끊긴 구간(컴퓨터 꺼짐)

_last_row: list | None = None  # 마지막으로 쓴 줄 (같은 값을 또 쓰지 않으려고)


# ---------------------------------------------------------------- 기록


def _epoch(when: datetime | None) -> int | None:
    if when is None:
        return None
    if when.tzinfo is None:  # 시간대가 빠진 값이 오면 UTC 로 본다
        when = when.replace(tzinfo=timezone.utc)
    try:
        return int(when.timestamp())
    except (ValueError, OSError, OverflowError):
        return None


def _grid(ts: int | None) -> int | None:
    """초기화 시각을 분 눈금에 맞춘다 — 응답이 ±1초로 흔들려서다 (맨 위 설명).

    실제 초기화는 늘 분 경계라 반올림해도 잃는 것이 없고, 대신 **같은 창이면 늘 같은
    값**이 되어 창이 바뀐 것과 그냥 흔들린 것을 가를 수 있다. 흔들리는 채로 두면
    `record` 의 '값이 그대로면 안 쓴다' 도 영영 안 걸려 기록이 세 배로 쌓인다.
    """
    return None if ts is None else int(round(ts / GRID)) * GRID


def _pct(value) -> float | None:
    """소수 첫째 자리까지만 — 부동소수 찌꺼기로 '값이 바뀐 것'처럼 보이지 않게."""
    return None if value is None else round(float(value), 1)


def _row(usage) -> list | None:
    """Usage 한 개를 기록 한 줄로. 둘 다 값이 없으면 남길 게 없다."""
    if usage.five.pct is None and usage.week.pct is None:
        return None
    return [
        _epoch(usage.fetched_at) or int(time.time()),
        _pct(usage.five.pct),
        _pct(usage.week.pct),
        _grid(_epoch(usage.five.resets_at)),
        _grid(_epoch(usage.week.resets_at)),
    ]


def _tail_row(path: str) -> list | None:
    """파일 끝 줄. 앱을 다시 켰을 때 직전 값과 이어 보려고 한 번만 읽는다."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        row = _parse(line)
        if row is not None:
            return row
    return None


def _parse(line: str) -> list | None:
    try:
        row = json.loads(line)
    except ValueError:
        return None
    if not isinstance(row, list) or len(row) < 3 or not isinstance(row[0], (int, float)):
        return None
    row = list(row) + [None] * (5 - len(row))
    # 옛 줄은 흔들리는 초까지 그대로 들어 있다 — 읽을 때 눈금에 맞춰 준다
    return [int(row[0]), row[1], row[2], _grid(row[3]), _grid(row[4])]


def record(usage, path: str = HIST_PATH) -> None:
    """조회에 성공할 때마다 부른다. 값이 그대로면(클로드를 안 씀) 건너뛴다."""
    global _last_row
    row = _row(usage)
    if row is None:
        return
    if _last_row is None:
        _last_row = _tail_row(path)
    if _last_row is not None:
        if row[1:] == _last_row[1:] and row[0] - _last_row[0] < HEARTBEAT:
            return
        if row[0] <= _last_row[0]:  # 시계가 뒤로 갔다 — 순서가 꼬이지 않게 건너뛴다
            return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        return
    _last_row = row


def trim(path: str = HIST_PATH, keep_days: int = KEEP_DAYS) -> None:
    """오래된 줄을 덜어낸다. 앱을 켤 때 한 번만 부르면 된다 (파일을 통째로 다시 쓴다)."""
    try:
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return
    if len(lines) < TRIM_AT:
        return
    floor = time.time() - keep_days * 86400
    kept = [ln for ln in lines if (r := _parse(ln)) is not None and r[0] >= floor]
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + ("\n" if kept else ""))
    except OSError:
        pass


# ---------------------------------------------------------------- 읽기


@dataclass
class Sample:
    """기록 한 줄. `at` 은 **로컬 시각**(naive) — 날짜·시간대 셈이 전부 로컬 기준이다."""

    at: datetime
    five: float | None
    week: float | None
    five_reset: int | None
    week_reset: int | None


def read_samples(days: int | None = None, path: str = HIST_PATH) -> list[Sample]:
    """오래된 것이 앞. `days` 를 주면 그만큼만 (없으면 전부)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    floor = None if days is None else time.time() - days * 86400
    out: list[Sample] = []
    for line in lines:
        row = _parse(line)
        if row is None or (floor is not None and row[0] < floor):
            continue
        try:
            at = datetime.fromtimestamp(row[0])
        except (ValueError, OSError, OverflowError):
            continue
        out.append(Sample(at, row[1], row[2], row[3], row[4]))
    out.sort(key=lambda s: s.at)
    return out


# ---------------------------------------------------------------- 셈


@dataclass
class Gain:
    """그 사이에 쓴 양 한 조각 — 언제 · 몇 %p · 어느 주간 창에서."""

    at: datetime
    pp: float
    week_reset: int | None


def gains(samples: list[Sample]) -> list[Gain]:
    """주간 퍼센트가 오른 만큼을 **뒤 표본 시각**에 달아 조각으로 늘어놓는다.

    주간 창이 바뀌면(초기화) 퍼센트가 떨어지므로 뺄셈이 음수가 된다 — 그때는
    새 창에서 지금까지 쓴 양(= 지금 퍼센트)이 그 사이에 쓴 양이다.

    ★ 창이 바뀐 것은 **초기화 시각이 달라졌거나 퍼센트가 떨어졌을 때**다. 앞의 것만
    보면 초기화 시각이 잠깐 빠져 오는 순간(실제로 그런 표본이 있다)을 놓치고, 뒤의
    것만 보면 창이 바뀌자마자 이미 쓴 양을 놓친다. 초기화 시각은 `_grid` 로 분에
    맞춰 읽으므로 ±1초 흔들림은 여기까지 오지 않는다.
    """
    out: list[Gain] = []
    prev: Sample | None = None
    for s in samples:
        if s.week is None:
            continue
        if prev is not None:
            rolled = (
                s.week_reset is not None
                and prev.week_reset is not None
                and s.week_reset != prev.week_reset
            ) or s.week < prev.week
            pp = s.week if rolled else s.week - prev.week
            if pp > 0:
                out.append(Gain(s.at, pp, s.week_reset))
        prev = s
    return out


def deltas(samples: list[Sample]) -> list[tuple[datetime, float]]:
    """(시각, 그 사이에 쓴 %p) — `gains` 에서 창 정보만 뗀 것."""
    return [(g.at, g.pp) for g in gains(samples)]


def daily(samples: list[Sample], days: int = 14, today: date | None = None):
    """최근 `days` 일의 (날짜, 사용 %p). 안 쓴 날도 0 으로 채워 자리를 남긴다."""
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    table = {start + timedelta(days=i): 0.0 for i in range(days)}
    for when, gain in deltas(samples):
        day = when.date()
        if day in table:
            table[day] += gain
    return [(d, table[d]) for d in sorted(table)]


def hourly(samples: list[Sample]) -> list[float]:
    """시간대(0~23시)별 사용 %p 합계 — 하루 중 언제 쓰는지."""
    hours = [0.0] * 24
    for when, gain in deltas(samples):
        hours[when.hour] += gain
    return hours


def weekday(samples: list[Sample]) -> list[float]:
    """요일(월~일)별 **하루 평균** %p — 어느 요일에 몰아 쓰는지.

    합계로 두면 기록에 든 그 요일 수가 다를 때(첫 주·마지막 주는 7일이 다 안 채워진다)
    막대 길이가 요일 수를 재는 셈이 된다. 실제로 그 요일이 며칠 있었는지로 나눈다.
    """
    total = [0.0] * 7
    seen: list[set] = [set() for _ in range(7)]
    for s in samples:  # 기록이 있던 날만 분모에 넣는다 (컴퓨터가 꺼져 있던 날 제외)
        d = s.at.date()
        seen[d.weekday()].add(d)
    for when, gain in deltas(samples):
        total[when.weekday()] += gain
    return [total[i] / len(seen[i]) if seen[i] else 0.0 for i in range(7)]


def by_month(samples: list[Sample], months: int = 6, today: date | None = None):
    """최근 `months` 개 달의 (달 첫날, %p, 잰 날수). 안 쓴 달도 0 으로 자리를 남긴다.

    **잰 날수**를 같이 주는 까닭: 이번 달은 아직 안 끝났고 첫 달은 도중부터 기록했다.
    합계만 견주면 그 두 달이 무조건 짧아 보인다 — 하루 평균으로 봐야 값이 뜻을 갖는다.
    """
    today = today or date.today()
    keys: list[date] = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    table = {k: 0.0 for k in keys}
    for when, gain in deltas(samples):
        key = date(when.year, when.month, 1)
        if key in table:
            table[key] += gain

    first = samples[0].at if samples else None
    last = samples[-1].at if samples else None
    out = []
    for k in sorted(table):
        nxt = date(k.year + (k.month == 12), k.month % 12 + 1, 1)
        span = 0.0
        if first is not None:
            lo = max(first, datetime(k.year, k.month, 1))
            hi = min(last, datetime(nxt.year, nxt.month, 1))
            span = max(0.0, (hi - lo).total_seconds() / 86400)
        out.append((k, table[k], span))
    return out


@dataclass
class LimitWeek:
    """주간 한도 창 하나 — 언제부터 언제까지, 그 창에서 몇 %를 썼나.

    달력 주가 아니라 **`seven_day.resets_at` 이 정하는 진짜 한도 창**이다. 한도가
    걸리는 단위가 이것이라 `100%` 눈금과 곧바로 견줄 수 있다.
    """

    start: datetime
    end: datetime
    used: float
    partial: bool = False  # 창 도중부터 기록이 시작됨 (실제보다 적게 잡힘)


def limit_weeks(samples: list[Sample], limit: int = 8) -> list[LimitWeek]:
    """주간 한도 창별 사용량. 최신이 뒤. 창 정보가 없는 조각은 버린다."""
    used: dict[int, float] = {}
    for g in gains(samples):
        if g.week_reset is None:
            continue
        used[g.week_reset] = used.get(g.week_reset, 0.0) + g.pp
    first = samples[0].at if samples else None
    out: list[LimitWeek] = []
    for reset in sorted(used)[-limit:]:
        try:
            end = datetime.fromtimestamp(reset)
        except (ValueError, OSError, OverflowError):
            continue
        start = end - WEEK_SPAN
        out.append(
            LimitWeek(start, end, used[reset], partial=first is not None and first > start)
        )
    return out


def coverage(samples: list[Sample]) -> tuple[float, float]:
    """(기록이 끊긴 시간(시간), 덮은 비율 0~1). 위젯이 꺼져 있던 만큼을 잰다.

    통계는 **위젯이 떠 있는 동안만** 쌓이므로, 끊긴 구간이 길면 모든 수치가 실제보다
    적다. 그 사실을 숨기지 않고 화면에 적어 준다.
    """
    if len(samples) < 2:
        return 0.0, 0.0
    gap = 0.0
    for a, b in zip(samples, samples[1:]):
        sec = (b.at - a.at).total_seconds()
        if sec > GAP_SEC:
            gap += sec
    span = (samples[-1].at - samples[0].at).total_seconds()
    return gap / 3600, max(0.0, 1 - gap / span) if span > 0 else 0.0


@dataclass
class Window:
    """5시간 창 하나 — 언제부터 언제까지, 그 안에서 퍼센트가 어디까지 찼나."""

    start: datetime
    end: datetime
    peak: float


def five_windows(samples: list[Sample], limit: int = 12) -> list[Window]:
    """최근 5시간 창들. 초기화 시각이 같은 표본을 한 창으로 묶는다. 최신이 뒤."""
    peaks: dict[int, float] = {}
    for s in samples:
        if s.five_reset is None or s.five is None:
            continue
        peaks[s.five_reset] = max(peaks.get(s.five_reset, 0.0), s.five)
    out: list[Window] = []
    for reset in sorted(peaks)[-limit:]:
        try:
            end = datetime.fromtimestamp(reset)
        except (ValueError, OSError, OverflowError):
            continue
        out.append(Window(end - FIVE_SPAN, end, peaks[reset]))
    return out


@dataclass
class Report:
    """화면이 그대로 그리면 되는 형태. 값이 없으면 빈 리스트·None 이다."""

    samples: int = 0
    span_days: float = 0.0  # 기록이 쌓인 날수
    first: datetime | None = None
    last: datetime | None = None
    days: list = field(default_factory=list)  # [(date, %p)]
    hours: list = field(default_factory=list)  # 24개
    windows: list = field(default_factory=list)  # [Window]
    today: float = 0.0
    yesterday: float = 0.0
    avg_day: float = 0.0  # 최근 7일 하루 평균 (기록이 짧으면 그만큼으로 나눈다)
    busiest: tuple | None = None  # (date, %p) 가장 많이 쓴 날
    peak_hour: int | None = None  # 가장 많이 쓰는 시간대
    win_avg: float | None = None  # 5시간 창 평균 최고 %
    win_full: int = 0  # 90% 넘긴 창 수

    # ---- 주별 (달력 주가 아니라 진짜 한도 창이다 — `LimitWeek`) ----
    limits: list = field(default_factory=list)  # [LimitWeek] 최신이 뒤
    week_now: object | None = None  # 지금 도는 창
    week_prev: object | None = None  # 바로 앞 창
    avg_week: float | None = None  # 다 채운 창의 평균 사용 %
    busiest_week: object | None = None  # 다 채운 창 중 가장 많이 쓴 것

    # ---- 월별 ----
    months: list = field(default_factory=list)  # [(달 첫날 date, %p, 잰 날수)]
    this_month: float = 0.0
    last_month: float = 0.0
    busiest_month: tuple | None = None

    # ---- 전체 ----
    total: float = 0.0  # 기록에 담긴 사용량 전부 (%p)
    total_avg_day: float = 0.0  # 기록 전 기간의 하루 평균
    weekdays: list = field(default_factory=list)  # 7개, 요일별 하루 평균 %p
    peak_weekday: int | None = None
    gap_hours: float = 0.0  # 기록이 끊긴 시간 (위젯이 꺼져 있던 만큼)
    covered: float = 0.0  # 기록이 덮은 비율 0~1
    trend: float | None = None  # 최근 7일 ÷ 그 전 7일 − 1 (없으면 None)


def analyze(samples: list[Sample], days: int = 14, today: date | None = None) -> Report:
    rep = Report(samples=len(samples))
    if not samples:
        return rep
    rep.first = samples[0].at
    rep.last = samples[-1].at
    rep.span_days = max(0.0, (samples[-1].at - samples[0].at).total_seconds() / 86400)

    today = today or date.today()
    rep.days = daily(samples, days, today)
    rep.hours = hourly(samples)
    rep.windows = five_windows(samples)

    table = dict(rep.days)
    rep.today = table.get(today, 0.0)
    rep.yesterday = table.get(today - timedelta(days=1), 0.0)

    # 하루 평균: 기록이 7일보다 짧으면 그 날수로 나눈다 (0 으로 희석되지 않게)
    span = max(1.0, min(7.0, rep.span_days + 1))
    recent = [v for d, v in rep.days if (today - d).days < 7]
    rep.avg_day = sum(recent) / span if recent else 0.0

    used = [(d, v) for d, v in rep.days if v > 0]
    rep.busiest = max(used, key=lambda x: x[1]) if used else None
    if any(rep.hours):
        rep.peak_hour = max(range(24), key=lambda h: rep.hours[h])

    if rep.windows:
        rep.win_avg = sum(w.peak for w in rep.windows) / len(rep.windows)
        rep.win_full = sum(1 for w in rep.windows if w.peak >= 90)

    # ---- 주별 (진짜 한도 창) ----
    rep.limits = limit_weeks(samples)
    running = [w for w in rep.limits if w.end > samples[-1].at]
    rep.week_now = running[-1] if running else None
    done = [w for w in rep.limits if w.end <= samples[-1].at]
    rep.week_prev = done[-1] if done else None
    # **평균**은 다 끝난 창만 센다 — 지금 도는 창은 아직 덜 찼으니 섞으면 낮아진다.
    # **최고**는 도는 창도 넣는다 — 이미 그만큼 쓴 것은 사실이다.
    # (도중부터 기록한 창은 둘 다 뺀다. 그 값은 실제보다 적다)
    done_full = [w for w in done if not w.partial]
    rep.avg_week = sum(w.used for w in done_full) / len(done_full) if done_full else None
    seen = [w for w in rep.limits if not w.partial]
    rep.busiest_week = max(seen, key=lambda w: w.used) if seen else None

    # ---- 월별 ----
    # 빈 달을 여섯 칸씩 늘어놓으면 화면이 텅 비어 보인다 — 기록이 걸친 달수만큼만
    span_m = (rep.last.year - rep.first.year) * 12 + rep.last.month - rep.first.month + 1
    rep.months = by_month(samples, min(6, max(3, span_m)), today)
    mt = {k: v for k, v, _n in rep.months}
    rep.this_month = mt.get(date(today.year, today.month, 1), 0.0)
    prev_m = date(today.year, today.month, 1) - timedelta(days=1)
    rep.last_month = mt.get(date(prev_m.year, prev_m.month, 1), 0.0)
    mused = [(d, v, n) for d, v, n in rep.months if v > 0]
    rep.busiest_month = max(mused, key=lambda x: x[1]) if mused else None

    # ---- 전체 ----
    all_gains = deltas(samples)
    rep.total = sum(g for _w, g in all_gains)
    rep.total_avg_day = rep.total / max(1.0, rep.span_days)
    rep.weekdays = weekday(samples)
    if any(rep.weekdays):
        rep.peak_weekday = max(range(7), key=lambda i: rep.weekdays[i])
    rep.gap_hours, rep.covered = coverage(samples)

    # 추세: 최근 7일 ÷ 그 전 7일. 앞 7일이 통째로 기록 밖이면 뜻이 없다
    if rep.span_days >= 13:
        cut = samples[-1].at - timedelta(days=7)
        prev_cut = cut - timedelta(days=7)
        now7 = sum(g for w, g in all_gains if w >= cut)
        was7 = sum(g for w, g in all_gains if prev_cut <= w < cut)
        if was7 > 0:
            rep.trend = now7 / was7 - 1
    return rep


# ---------------------------------------------------------------- 단독 확인

if __name__ == "__main__":
    _s = read_samples()
    _r = analyze(_s)
    print(f"기록 {_r.samples}개 · {_r.span_days:.1f}일" + (
        f" (처음 {_r.first:%m/%d %H:%M})" if _r.first else ""
    ) + " · 모든 % 는 주간 한도 기준")
    if not _s:
        raise SystemExit("아직 쌓인 기록이 없습니다 — 위젯이 떠 있는 동안 쌓입니다.")
    print(f"오늘 {_r.today:.1f}% · 어제 {_r.yesterday:.1f}% · 하루 평균 {_r.avg_day:.1f}%")
    if _r.busiest:
        print(f"가장 많이 쓴 날 {_r.busiest[0]:%m/%d} {_r.busiest[1]:.1f}%")
    if _r.peak_hour is not None:
        print(f"가장 많이 쓰는 때 {_r.peak_hour:02d}시")
    if _r.win_avg is not None:
        print(f"5시간 창 {len(_r.windows)}개 · 평균 최고 {_r.win_avg:.0f}% · 90%↑ {_r.win_full}개")
    print()
    for _d, _v in _r.days:
        print(f"  {_d:%m/%d}({'월화수목금토일'[_d.weekday()]})  {_v:5.1f}%  "
              + "█" * int(_v / 2))

    print("\n[주간 한도 창]")
    for _w in _r.limits:
        print(f"  {_w.start:%m/%d %H:%M} ~ {_w.end:%m/%d %H:%M}  {_w.used:5.1f}%"
              + ("  (도중부터)" if _w.partial else "") + "  " + "█" * int(_w.used / 4))
    if _r.avg_week is not None:
        print(f"  다 채운 창 평균 {_r.avg_week:.0f}%")

    print("\n[달별]")
    for _m, _v, _n in _r.months:
        if _v > 0:
            print(f"  {_m:%Y-%m}  {_v:6.1f}%  ({_n:.0f}일 · 하루 {_v / max(1.0, _n):.1f}%)")

    print("\n[전체]")
    print(f"  합계 {_r.total:.1f}% · 하루 평균 {_r.total_avg_day:.1f}%"
          f" · 이 속도면 한 주에 {_r.total_avg_day * 7:.0f}%")
    print("  요일별 하루 평균  " + " · ".join(
        f"{'월화수목금토일'[i]} {v:.0f}" for i, v in enumerate(_r.weekdays)))
    print(f"  못 센 시간 {_r.gap_hours:.0f}시간 (기록이 덮은 비율 {_r.covered * 100:.0f}%)")
    if _r.trend is not None:
        print(f"  최근 7일 추세 {_r.trend * 100:+.0f}%")
