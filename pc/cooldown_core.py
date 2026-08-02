"""
클로드 쿨다운 — 사용량 조회·파싱 공용 모듈
============================================
윈도우 앱·에이전트가 모두 이 모듈만 쓴다. 파서는 여기 한 곳에만 둔다.

응답 형식 (2026-07-28 실측 확인):
    {"five_hour": {"utilization": 7.0, "resets_at": "...+00:00"},
     "seven_day": {"utilization": 55.0, "resets_at": "..."},
     "limits": [{"kind": "weekly_scoped", "percent": 7,
                 "scope": {"model": {"display_name": "Fable"}}}, ...]}

utilization 은 0~100 스케일이다. 100 을 곱하지 말 것.
공식 문서화되지 않은 엔드포인트라 예고 없이 바뀔 수 있다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

CRED_PATH = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
MIN_INTERVAL = 300  # 초. 이보다 짧게 폴링하면 rate limit 에 걸린다.


class UsageError(Exception):
    """사용량을 못 가져왔다."""


class LoginRequired(UsageError):
    """토큰이 없거나 만료됐다. 사용자가 Claude Code 에 다시 로그인해야 한다."""


class ConnectionFailed(UsageError):
    """서버에 닿지도 못했다 (네트워크 끊김 등).

    요청이 서버에 도달하지 않았으므로 곧바로 다시 시도해도 rate limit 과 무관하다.
    반대로 429·5xx 는 서버가 받은 것이므로 이 예외를 쓰지 않는다.
    """


# ---------------------------------------------------------------- 값 객체


@dataclass
class Limit:
    """한도 하나. pct 가 None 이면 이 계정에 해당 한도가 없다는 뜻."""

    label: str
    pct: float | None = None
    resets_at: datetime | None = None

    @property
    def left(self) -> str:
        """'3시간 07분 후' 같은 남은 시간 문자열. 모르면 빈 문자열."""
        if self.resets_at is None:
            return ""
        when = self.resets_at
        if when.tzinfo is None:  # 시간대가 빠진 값이 오면 UTC 로 본다 (빼기가 터진다)
            when = when.replace(tzinfo=timezone.utc)
        secs = (when - datetime.now(timezone.utc)).total_seconds()
        if secs <= 0:
            return "곧 초기화"
        mins = int(secs // 60)
        if mins >= 1440:
            return f"{mins // 1440}일 {(mins % 1440) // 60}시간 후"
        if mins >= 60:
            return f"{mins // 60}시간 {mins % 60:02d}분 후"
        return f"{mins}분 후"

    @property
    def reset_iso(self) -> str | None:
        return self.resets_at.isoformat() if self.resets_at else None


@dataclass
class Usage:
    five: Limit
    week: Limit
    scoped: list[Limit] = field(default_factory=list)  # 모델별 주간 한도
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        """에이전트가 서버로 올리거나 파일로 저장할 때 쓰는 평평한 형태.
        토큰이나 원본은 절대 넣지 않는다."""
        return {
            "five_hour_pct": self.five.pct,
            "five_hour_reset": self.five.reset_iso,
            "seven_day_pct": self.week.pct,
            "seven_day_reset": self.week.reset_iso,
            "updated_at": self.fetched_at.isoformat(),
        }


# ---------------------------------------------------------------- 파싱


def _pct(node) -> float | None:
    """utilization / percent 를 0~100 으로 뽑는다."""
    if isinstance(node, (int, float)):
        value = float(node)
    elif isinstance(node, dict):
        for key in ("utilization", "percent"):
            candidate = node.get(key)
            if isinstance(candidate, (int, float)):
                value = float(candidate)
                break
        else:
            return None
    else:
        return None
    return max(0.0, min(100.0, value))


def _dt(node) -> datetime | None:
    if not isinstance(node, dict):
        return None
    raw = node.get("resets_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def _scoped(raw: dict) -> list[Limit]:
    """limits[] 에서 모델별 주간 한도만 골라낸다.
    (seven_day_opus / seven_day_sonnet 최상위 필드는 이제 항상 null 이다)"""
    out: list[Limit] = []
    for item in raw.get("limits") or []:
        if not isinstance(item, dict) or item.get("kind") != "weekly_scoped":
            continue
        model = (item.get("scope") or {}).get("model") or {}
        name = model.get("display_name") or model.get("id") or "모델별"
        out.append(Limit(str(name), _pct(item), _dt(item)))
    return out


def parse(raw: dict) -> Usage:
    try:
        five = Limit("5시간", _pct(raw.get("five_hour")), _dt(raw.get("five_hour")))
        week = Limit("주간", _pct(raw.get("seven_day")), _dt(raw.get("seven_day")))
        scoped = _scoped(raw)
    except (AttributeError, TypeError) as e:  # 응답 구조 자체가 달라졌다
        raise UsageError("형식 변경") from e

    # 필드 이름만 바뀌어도 예외 없이 전부 None 인 Usage 가 나온다.
    # 그대로 두면 화면에 '--' 만 뜨고 오류 표시가 없어, 고장난 줄도 모른다.
    if five.pct is None and week.pct is None:
        raise UsageError("형식 변경")

    return Usage(five=five, week=week, scoped=scoped, raw=raw)


# ---------------------------------------------------------------- 속도 분석

WEEK_SPAN = timedelta(days=7)
FIVE_SPAN = timedelta(hours=5)  # 5시간 창 길이 (정확히 5시간)
DAY_PP = 100 / 7  # 하루치 사용량(%p). 판정을 '며칠 앞섰나' 로 잡는 기준이다.
PROJECT_AFTER = 0.15  # 창이 이만큼(약 하루) 흐른 뒤부터 '이 속도면' 을 셈한다


@dataclass
class Pace:
    """주간 한도를 '지금쯤 얼마나 썼어야 하나' 와 견준 결과.

    주간 창은 달력의 월요일이 아니라 **resets_at 에서 7일 뺀 순간**부터다.
    창이 흐른 비율이 곧 알맞은 사용률(`due`) — 창이 2/7 흘렀으면 28% 가 제 속도다.
    """

    used: float  # 지금 쓴 %
    due: float  # 이 시점에 알맞은 % (창이 흐른 만큼)
    elapsed: float  # 창이 흐른 비율 0~1
    left_sec: float  # 초기화까지 남은 초
    projected: float | None  # 이 속도면 주 끝에 몇 % (창 초반엔 튀므로 None)
    runout: datetime | None  # 이 속도면 100% 에 닿는 시각 (창 안에서 안 닿으면 None)
    verdict: str  # '여유' / '알맞음' / '조금 빠름' / '많이 빠름' / '다 씀'
    level: int  # 0 넉넉 · 1 주의 · 2 위험 (색은 화면 쪽에서 고른다)

    @property
    def over(self) -> float:
        """알맞은 양보다 얼마나 앞섰나 (%p). 음수면 덜 쓴 것."""
        return self.used - self.due

    @property
    def days_left(self) -> float:
        return self.left_sec / 86400

    @property
    def per_day(self) -> float | None:
        """남은 기간 하루에 쓸 수 있는 %. 남은 게 하루 미만이면 None (그땐 하루로 못 나눈다)."""
        days = self.days_left
        if days < 1:
            return None
        return max(0.0, 100 - self.used) / days


def pace(usage: Usage, now: datetime | None = None) -> Pace | None:
    """주간 한도 속도 분석. 주간 값이나 초기화 시각이 없으면 None.

    **5시간 한도에는 쓰지 않는다** — 그 창은 첫 메시지에 열려 앞쪽에 몰아 쓰는 게
    정상이라, 고르게 쓰는 걸 전제로 한 이 계산이 뜻을 못 가진다.
    """
    week = usage.week
    if week.pct is None or week.resets_at is None:
        return None

    now = now or datetime.now(timezone.utc)
    end = week.resets_at
    if end.tzinfo is None:  # 시간대가 빠진 값이 오면 UTC 로 본다 (빼기가 터진다)
        end = end.replace(tzinfo=timezone.utc)

    span = WEEK_SPAN.total_seconds()
    # 창이 열린 순간부터 지금까지. 시계가 어긋나거나 창이 막 열렸어도
    # 0 으로 나누지 않게 아래를 60초로 막는다.
    elapsed = min(span, max(60.0, (now - (end - WEEK_SPAN)).total_seconds()))
    frac = elapsed / span
    used = float(week.pct)
    due = frac * 100
    left_sec = max(0.0, (end - now).total_seconds())

    # 창 초반에는 표본이 짧아 '이 속도면' 이 수백 %로 튄다 — 하루는 지나고 셈한다.
    # (창이 막 열렸을 땐 몇 분치 속도로 '4분 뒤 소진' 같은 헛말이 나온다)
    projected = runout = None
    if frac >= PROJECT_AFTER:
        projected = used / frac
        rate = used / elapsed  # %/초
        if rate > 0 and used < 100:
            when = now + timedelta(seconds=(100 - used) / rate)
            if when < end:  # 이 창 안에서 다 쓸 것 같을 때만 뜻이 있다
                runout = when

    over = used - due
    if used >= 99.5:
        verdict, level = "다 씀", 2
    elif over <= -DAY_PP:  # 하루치 이상 덜 썼다
        verdict, level = "여유", 0
    elif over <= DAY_PP / 2:  # 반나절 앞까지는 제 속도로 본다
        verdict, level = "알맞음", 0
    elif over <= DAY_PP * 1.5:
        verdict, level = "조금 빠름", 1
    else:
        verdict, level = "많이 빠름", 2

    return Pace(used, due, frac, left_sec, projected, runout, verdict, level)


def five_due(usage: Usage, now: datetime | None = None) -> float | None:
    """5시간 창이 흐른 비율(0~100). 5시간 게이지의 '지금쯤 여기까지' 눈금 자리다.

    주간의 pace() 와 달리 **판정(여유/빠름)은 내지 않는다** — 5시간 창은 첫 메시지에
    열려 앞쪽에 몰아 쓰는 게 정상이라 '고르게 썼나' 판정은 뜻이 없다. 다만 창이 얼마나
    흘렀는지 보여 주는 기준선은, 채운 양과 견주면 '이대로면 초기화 전에 바닥나겠다' 를
    한눈에 보게 해 준다.

    창이 없거나(초기화 시각 없음), 이미 풀렸으면(과거) None 을 돌려준다 — 눈금을 숨긴다.
    """
    five = usage.five
    if five.pct is None or five.resets_at is None:
        return None
    now = now or datetime.now(timezone.utc)
    end = five.resets_at
    if end.tzinfo is None:  # 시간대가 빠진 값이 오면 UTC 로 본다 (빼기가 터진다)
        end = end.replace(tzinfo=timezone.utc)
    span = FIVE_SPAN.total_seconds()
    left = (end - now).total_seconds()
    if left <= 0 or left > span:  # 이미 풀렸거나 창 길이를 벗어난 값 — 눈금이 뜻이 없다
        return None
    return max(0.0, min(100.0, (span - left) / span * 100))


# ---------------------------------------------------------------- 조회


def read_token() -> str:
    if not os.path.exists(CRED_PATH):
        raise LoginRequired("로그인 안 됨")
    try:
        with open(CRED_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise LoginRequired("로그인 정보 손상") from e
    token = (data.get("claudeAiOauth") or {}).get("accessToken")
    if not token:
        raise LoginRequired("로그인 안 됨")
    return token


def fetch_raw() -> dict:
    """응답 원본 JSON."""
    try:
        r = requests.get(
            USAGE_URL,
            headers={
                "Authorization": f"Bearer {read_token()}",
                "anthropic-beta": "oauth-2025-04-20",
            },
            timeout=15,
        )
    except requests.RequestException as e:
        raise ConnectionFailed("연결 실패") from e

    # 화면에 그대로 나가는 문구다. 슬림 바의 오류 자리가 좁으니 짧은 명사형으로.
    if r.status_code in (401, 403):
        raise LoginRequired("로그인 만료")
    if r.status_code == 429:
        raise UsageError("요청 과다")
    if r.status_code >= 400:
        raise UsageError(f"서버 오류 {r.status_code}")

    try:
        return r.json()
    except ValueError as e:
        raise UsageError("형식 변경") from e


def fetch() -> Usage:
    return parse(fetch_raw())


if __name__ == "__main__":
    _raw = fetch_raw()
    print(json.dumps(_raw, ensure_ascii=False, indent=2))
    _p = pace(parse(_raw))
    if _p is not None:
        _line = f"주간 {_p.used:.0f}% · 적정선 {_p.due:.0f}% · {_p.verdict}"
        if _p.projected is not None:
            _line += f" · 이 속도면 {_p.projected:.0f}%"
        if _p.runout is not None:
            _line += f" · {_p.runout.astimezone():%m/%d %H:%M} 소진"
        print("\n" + _line)
