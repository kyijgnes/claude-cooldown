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
from datetime import datetime, timezone

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
        secs = (self.resets_at - datetime.now(timezone.utc)).total_seconds()
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
    return Usage(
        five=Limit("5시간", _pct(raw.get("five_hour")), _dt(raw.get("five_hour"))),
        week=Limit("주간", _pct(raw.get("seven_day")), _dt(raw.get("seven_day"))),
        scoped=_scoped(raw),
        raw=raw,
    )


# ---------------------------------------------------------------- 조회


def read_token() -> str:
    if not os.path.exists(CRED_PATH):
        raise LoginRequired("Claude Code 로그인 정보가 없습니다")
    try:
        with open(CRED_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise LoginRequired("로그인 정보를 읽을 수 없습니다") from e
    token = (data.get("claudeAiOauth") or {}).get("accessToken")
    if not token:
        raise LoginRequired("로그인 정보가 비어 있습니다")
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

    if r.status_code in (401, 403):
        raise LoginRequired("로그인이 만료됐습니다")
    if r.status_code == 429:
        raise UsageError("요청이 너무 잦습니다")
    if r.status_code >= 400:
        raise UsageError(f"서버 오류 {r.status_code}")

    try:
        return r.json()
    except ValueError as e:
        raise UsageError("응답 형식이 바뀐 것 같습니다") from e


def fetch() -> Usage:
    return parse(fetch_raw())


if __name__ == "__main__":
    print(json.dumps(fetch_raw(), ensure_ascii=False, indent=2))
