"""
스킨 공통 — 색·글꼴과 스킨이 지켜야 할 약속
=============================================
앱(cooldown_app.py)이 창·트레이·조회를 맡고, 스킨은 **그리기만** 한다.
스킨은 창을 만들지 않고, 네트워크를 치지 않고, 설정을 저장하지 않는다.
"""

from __future__ import annotations

import tkinter as tk

from cooldown_core import Usage

# ---------------------------------------------------------------- 색
class Palette:
    """색 한 벌.

    스킨은 `from .base import P` 로 **이 객체를** 받아 두고 `P.bg` 처럼 쓴다.
    테마를 바꿀 때 객체를 갈아 끼우지 않고 **값만 덮어쓰므로**, 이미 받아 둔
    쪽도 함께 바뀐다. (값을 직접 import 하면 그 시점 색이 굳어 버린다)
    """

    def __init__(self, **colors: str):
        self.__dict__.update(colors)

    def copy_from(self, other: Palette) -> None:
        self.__dict__.update(other.__dict__)


# 작은 글자(8pt)가 많아 흐린 색도 배경 대비 4.5:1 이상으로 잡는다.
# 위계는 밝기가 아니라 글자 크기로 준다.
DARK = Palette(
    bg="#15171c",
    title="#e6edf3",
    label="#8b949e",  # 5.8:1
    sub="#c2cad4",
    faint="#7d8590",  # 4.8:1
    track="#252a32",
    line="#232830",
    green="#3fb950",
    amber="#e3b341",
    red="#ff5c61",
    red_bg="#2b1418",
    red_dim="#a67c83",  # red_bg 대비 4.8:1
    icon_text="#0d1117",  # 트레이 아이콘 숫자 (밝은 바탕 위)
)

LIGHT = Palette(
    bg="#f3f5f7",
    title="#12161b",
    label="#57606a",  # 5.0:1
    sub="#2f3742",
    faint="#616a75",  # 4.6:1
    track="#dce1e7",
    line="#e3e8ed",
    green="#1a7f37",
    amber="#8a6100",
    red="#cf222e",
    red_bg="#ffebe9",
    red_dim="#8a5a5f",  # red_bg 대비 4.9:1
    icon_text="#ffffff",  # 어두운 바탕 위
)

P = Palette(**DARK.__dict__)  # 지금 쓰는 한 벌

KR = "맑은 고딕"
NUM = "Segoe UI"


def system_prefers_light() -> bool:
    """윈도우의 '앱 모드' 설정이 밝게인가. 못 읽으면 어둡게로 본다."""
    try:
        import winreg

        path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return bool(winreg.QueryValueEx(key, "AppsUseLightTheme")[0])
    except OSError:
        return False


def set_palette(kind: str) -> str:
    """'auto' / 'light' / 'dark' 를 받아 실제로 고른 쪽을 돌려준다."""
    picked = kind if kind in ("light", "dark") else (
        "light" if system_prefers_light() else "dark"
    )
    P.copy_from(LIGHT if picked == "light" else DARK)
    return picked


def taskbar_height(default: int = 48) -> int:
    """작업표시줄 높이(px). 못 재면 윈도우 11 기본값.

    작은 작업표시줄 설정이나 화면 배율에 따라 40~72px 사이로 달라진다.
    """
    try:
        import win32gui

        bar = win32gui.FindWindow("Shell_TrayWnd", None)
        if bar:
            _, top, _, bottom = win32gui.GetWindowRect(bar)
            height = bottom - top
            if 24 <= height <= 200:
                return height
    except Exception:  # noqa: BLE001
        pass
    return default


def tone(pct: float | None) -> str:
    """여유 초록 / 보통 노랑 / 임박 빨강. 테마에 맞는 색이 나온다."""
    if pct is None:
        return P.faint
    if pct < 50:
        return P.green
    if pct < 80:
        return P.amber
    return P.red


# '지금쯤' 눈금 — 주간 게이지 위에 세로로 긋는 가는 선. 색은 P.title(대비 최대)로
# 고정한다. 게이지 색(초록/노랑/빨강)을 쓰면 값처럼 보여 두 개를 헷갈린다.
MARK_W = 2


def pace_color(level: int) -> str:
    """속도 판정 색 — 0 넉넉 초록 / 1 주의 노랑 / 2 위험 빨강."""
    return (P.green, P.amber, P.red)[max(0, min(2, level))]


def mark_x(due: float, width: float) -> float:
    """게이지 폭 안에서 '지금쯤' 눈금이 설 x. 오른쪽 끝을 넘어가 잘리지 않게 당긴다."""
    x = width * max(0.0, min(100.0, due)) / 100
    return max(0.0, min(x, width - MARK_W))


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
    dockable = False  # 작업표시줄에 붙일 수 있는가 (그 높이에 맞게 그리는 스킨만 참)

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

    def react(self, x: float | None = None, y: float | None = None) -> None:
        """위젯을 눌렀을 때의 반응(선택). `x`/`y` 는 창 기준 누른 자리(스킨이 쓰면).
        기본은 아무것도 하지 않는다."""
        pass
