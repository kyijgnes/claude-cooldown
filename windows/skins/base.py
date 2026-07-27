"""
스킨 공통 — 색·글꼴과 스킨이 지켜야 할 약속
=============================================
앱(cooldown_app.py)이 창·트레이·조회를 맡고, 스킨은 **그리기만** 한다.
스킨은 창을 만들지 않고, 네트워크를 치지 않고, 설정을 저장하지 않는다.
"""

from __future__ import annotations

import tkinter as tk

from cooldown_core import Usage

# ---------------------------------------------------------------- 색·글꼴
BG = "#15171c"
TITLE = "#e6edf3"
# 작은 글자(8pt)라 명암비를 4.5:1 이상으로 잡는다.
# BG 대비 — LABEL 5.8:1 / FAINT 4.8:1. 위계는 밝기보다 글자 크기로 준다.
LABEL = "#8b949e"
SUB = "#c2cad4"
FAINT = "#7d8590"
TRACK = "#252a32"
LINE = "#232830"
GREEN = "#3fb950"
AMBER = "#e3b341"
RED = "#ff5c61"
RED_BG = "#2b1418"
RED_DIM = "#a06068"

KR = "맑은 고딕"
NUM = "Segoe UI"


def tone(pct: float | None) -> str:
    """여유 초록 / 보통 노랑 / 임박 빨강."""
    if pct is None:
        return FAINT
    if pct < 50:
        return GREEN
    if pct < 80:
        return AMBER
    return RED


def worst(usage: Usage) -> float | None:
    """두 한도 중 더 급한 쪽 — 한 개짜리 상태 표시에 쓴다."""
    values = [x for x in (usage.five.pct, usage.week.pct) if x is not None]
    return max(values) if values else None


def scoped_text(usage: Usage, limit: int = 2) -> str:
    """'Fable 7%' 처럼 모델별 한도를 한 줄로. 없으면 빈 문자열."""
    items = [s for s in usage.scoped if s.pct is not None][:limit]
    return "   ".join(f"{s.label} {s.pct:.0f}%" for s in items)


# ---------------------------------------------------------------- 약속


class Skin:
    """위젯 본체 한 가지 모양.

    앱은 `build()` 로 한 번 그리고, 이후 `show()` / `show_error()` 로만 값을 바꾼다.
    드래그·우클릭 바인딩은 앱이 자식 위젯을 훑어서 알아서 건다.
    """

    key = ""  # 설정 파일에 저장되는 식별자
    name = ""  # 우클릭 메뉴에 뜨는 이름
    width = 260  # 창 가로 폭(px). 세로는 내용에서 계산된다.

    def build(self, parent: tk.Misc) -> None:
        """`parent` 안에 위젯을 구성한다. 스킨 하나당 한 번만 불린다."""
        raise NotImplementedError

    def show(self, usage: Usage, stamp: str) -> None:
        """정상 값을 표시한다. `stamp` 는 '03:07' 형태의 갱신 시각."""
        raise NotImplementedError

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        """오류를 표시한다.

        `keep_values` 가 참이면 숫자·게이지는 건드리지 않는다 (일시적 연결 실패).
        거짓이면 값이 없다는 뜻이므로 비운다 (로그인 만료).
        """
        raise NotImplementedError
