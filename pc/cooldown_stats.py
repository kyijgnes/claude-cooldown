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
FIVE_SPAN = timedelta(hours=5)
DAY_PP = 100 / 7  # 하루치 사용량(%p) — 주간 한도를 이레에 고르게 나눈 값

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
        _epoch(usage.five.resets_at),
        _epoch(usage.week.resets_at),
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
    return [int(row[0]), row[1], row[2], row[3], row[4]]


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


def deltas(samples: list[Sample]) -> list[tuple[datetime, float]]:
    """(시각, 그 사이에 쓴 %p). 주간 퍼센트가 오른 만큼을 **뒤 표본 시각**에 단다.

    주간 창이 바뀌면(초기화) 퍼센트가 떨어지므로 뺄셈이 음수가 된다 — 그때는
    새 창에서 지금까지 쓴 양(= 지금 퍼센트)이 그 사이에 쓴 양이다.
    """
    out: list[tuple[datetime, float]] = []
    prev: Sample | None = None
    for s in samples:
        if s.week is None:
            continue
        if prev is not None:
            rolled = (
                s.week_reset is not None
                and prev.week_reset is not None
                and s.week_reset != prev.week_reset
            )
            gain = s.week if rolled else s.week - prev.week
            if gain > 0:
                out.append((s.at, gain))
        prev = s
    return out


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
    days: list = field(default_factory=list)  # [(date, %p)]
    hours: list = field(default_factory=list)  # 24개
    windows: list = field(default_factory=list)  # [Window]
    today: float = 0.0
    yesterday: float = 0.0
    avg_day: float = 0.0  # 최근 이레 하루 평균 (기록이 짧으면 그만큼으로 나눈다)
    busiest: tuple | None = None  # (date, %p) 가장 많이 쓴 날
    peak_hour: int | None = None  # 가장 많이 쓰는 시간대
    win_avg: float | None = None  # 5시간 창 평균 최고 %
    win_full: int = 0  # 90% 넘긴 창 수


def analyze(samples: list[Sample], days: int = 14, today: date | None = None) -> Report:
    rep = Report(samples=len(samples))
    if not samples:
        return rep
    rep.first = samples[0].at
    rep.span_days = max(0.0, (samples[-1].at - samples[0].at).total_seconds() / 86400)

    today = today or date.today()
    rep.days = daily(samples, days, today)
    rep.hours = hourly(samples)
    rep.windows = five_windows(samples)

    table = dict(rep.days)
    rep.today = table.get(today, 0.0)
    rep.yesterday = table.get(today - timedelta(days=1), 0.0)

    # 하루 평균: 기록이 이레보다 짧으면 그 날수로 나눈다 (0 으로 희석되지 않게)
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
    return rep


# ---------------------------------------------------------------- 단독 확인

if __name__ == "__main__":
    _s = read_samples()
    _r = analyze(_s)
    print(f"기록 {_r.samples}개 · {_r.span_days:.1f}일" + (
        f" (처음 {_r.first:%m/%d %H:%M})" if _r.first else ""
    ))
    if not _s:
        raise SystemExit("아직 쌓인 기록이 없습니다 — 위젯이 떠 있는 동안 쌓입니다.")
    print(f"오늘 {_r.today:.1f}%p · 어제 {_r.yesterday:.1f}%p · 하루 평균 {_r.avg_day:.1f}%p")
    if _r.busiest:
        print(f"가장 많이 쓴 날 {_r.busiest[0]:%m/%d} {_r.busiest[1]:.1f}%p")
    if _r.peak_hour is not None:
        print(f"가장 많이 쓰는 때 {_r.peak_hour:02d}시")
    if _r.win_avg is not None:
        print(f"5시간 창 {len(_r.windows)}개 · 평균 최고 {_r.win_avg:.0f}% · 90%↑ {_r.win_full}개")
    print()
    for _d, _v in _r.days:
        print(f"  {_d:%m/%d}({'월화수목금토일'[_d.weekday()]})  {_v:5.1f}%p  "
              + "█" * int(_v / 2))
