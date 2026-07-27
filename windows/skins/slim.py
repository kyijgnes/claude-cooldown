"""
초슬림 바 — 화면 가장자리에 붙여 두는 낮고 긴 띠.
두 칸(5시간·주간)에 숫자와 눈금 게이지를 넣고, 오른쪽 끝에 모델별·기준 시각을 둔다.
왼쪽 세로 띠는 두 한도 중 더 급한 쪽 색. 오류일 때는 띠와 바탕이 빨강으로 바뀌고
모델별 자리에 상태 문구가 대신 들어간다 (자리를 새로 만들지 않으므로 높이는 그대로).

    ┃ 5시간 17%   4시간 12분 후 │ 주간 56%   2일 07시간 후 │ Fable 7%
    ┃ ▪▪▪▪▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫     │ ▪▪▪▪▪▪▪▪▪▪▪▫▫▫▫▫▫▫▫▫     │ 03:07 기준

폭은 "100%" · "6일 23시간 후" 같은 최대 길이 문자열을 실제 글꼴로 재서 칸을 나눈다.
창 폭(width)은 고정이라 그 최악 케이스가 들어가도록 넉넉히 잡았고, 남는 글자는 … 로 줄인다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from cooldown_core import Usage

from .base import (
    BG,
    FAINT,
    KR,
    LABEL,
    LINE,
    NUM,
    RED,
    RED_BG,
    SUB,
    TRACK,
    Skin,
    scoped_text,
    tone,
    worst,
)

# ---------------------------------------------------------------- 치수
H = 54  # 창 높이. 네 상태 모두 이 값 그대로다.
ACC = 4  # 왼쪽 상태 띠
PAD_L = ACC + 12
PAD_R = 14
GAP = 16  # 칸 사이
TOP_Y = 19  # 윗줄 중심
BAR_Y, BAR_H = 36, 6
BAR_CY = BAR_Y + BAR_H // 2
SEG_GAP = 2  # 눈금 사이
LV_GAP = 6  # 항목 이름 ↔ 숫자
VR_GAP = 10  # 숫자 ↔ 남은시간 최소 간격
LBL_BASE = 2  # 9pt 글자를 큰 숫자의 기준선에 맞추는 보정
SM_BASE = 3  # 8pt 글자 보정
DIV_TOP, DIV_BOT = 12, 44

# 폭을 정할 때 쓰는 최대 길이 표본
MAX_VALUE = "100%"
# 주간은 '6일 23시간 후'보다 하루 안쪽으로 들어온 '23시간 59분 후'가 더 넓다.
MAX_LEFT = ("4시간 59분 후", "23시간 59분 후")
MAX_STAMP = "23:59 기준"
MAX_SCOPED = "Claude Opus 99%"
MAX_ERROR = "재로그인 필요"


def _clip(text: str, font: tkfont.Font, maxw: int) -> str:
    """maxw 를 넘으면 뒤를 잘라 … 를 붙인다. 자리가 없으면 아예 비운다(겹침 방지)."""
    if maxw <= 0:
        return ""
    if font.measure(text) <= maxw:
        return text
    while text and font.measure(text + "…") > maxw:
        text = text[:-1]
    return text + "…"


def _fit(text: str, font: tkfont.Font, maxw: int) -> str:
    """'Claude Sonnet 4.5 12%' 처럼 길면 뒤 퍼센트는 남기고 이름만 줄인다."""
    if font.measure(text) <= maxw:
        return text
    head, _, tail = text.rpartition(" ")
    while head and font.measure(f"{head}… {tail}") > maxw:
        head = head[:-1]
    return f"{head}… {tail}" if head else _clip(text, font, maxw)


# ---------------------------------------------------------------- 한 칸
class Cell:
    """한 한도 — 이름 / 숫자 / 남은시간 한 줄 + 그 아래 눈금 게이지.

    자리는 만들 때 한 번 잡고, 이후에는 글자와 색만 바꿔 끼운다.
    """

    def __init__(self, skin: SlimSkin, x: int, w: int, label: str):
        self.c = skin.c
        self.f_value = skin.f_value
        self.f_small = skin.f_small
        self.x, self.w = x, w

        self.c.create_text(
            x, TOP_Y + LBL_BASE, text=label, anchor="w",
            font=skin.f_label, fill=LABEL,
        )
        self.vx = x + skin.f_label.measure(label) + LV_GAP
        self.value = self.c.create_text(
            self.vx, TOP_Y, text="--", anchor="w", font=self.f_value, fill=FAINT
        )
        self.left = self.c.create_text(
            x + w, TOP_Y + SM_BASE, text="", anchor="e", font=self.f_small, fill=SUB
        )

        count = max(8, w // 8)
        pitch = w / count
        seg_w = max(3.0, pitch - SEG_GAP)
        self.segs = [
            self.c.create_rectangle(
                x + i * pitch, BAR_Y, x + i * pitch + seg_w, BAR_Y + BAR_H,
                fill=TRACK, width=0,
            )
            for i in range(count)
        ]

    def set(self, pct: float | None, left: str) -> None:
        color = tone(pct)
        value = "--" if pct is None else f"{pct:.0f}%"
        self.c.itemconfigure(self.value, text=value, fill=color)

        room = int(self.x + self.w - (self.vx + self.f_value.measure(value) + VR_GAP))
        self.c.itemconfigure(
            self.left,
            text=_clip(left, self.f_small, room),
            fill=SUB if pct is not None else FAINT,
        )

        # 내림이라 꽉 찬 게이지는 100% 뿐이다. 값이 있으면 아무리 작아도 한 칸은 켠다.
        # (반올림이면 98~100%가 모두 꽉 참으로 보여 한도 소진 여부를 구분 못 한다.)
        n = len(self.segs)
        filled = 0 if not pct else max(1, min(n, int(pct * n / 100)))
        for i, seg in enumerate(self.segs):
            self.c.itemconfigure(seg, fill=color if i < filled else TRACK)


# ---------------------------------------------------------------- 스킨
class SlimSkin(Skin):
    key = "slim"
    name = "슬림 바"
    width = 480

    def build(self, parent: tk.Misc) -> None:
        self.f_label = tkfont.Font(parent, family=KR, size=9)
        self.f_value = tkfont.Font(parent, family=NUM, size=13, weight="bold")
        self.f_small = tkfont.Font(parent, family=KR, size=8)
        self.f_msg = tkfont.Font(parent, family=KR, size=9, weight="bold")

        self.c = tk.Canvas(
            parent, width=self.width, height=H, bg=BG, highlightthickness=0, bd=0
        )
        self.c.pack(fill="both", expand=True)

        # 최대 길이 문자열을 실제 글꼴로 재서 폭을 나눈다.
        # 두 칸이 필요한 만큼 먼저 가져가고, 오른쪽 칸은 남은 폭을 제 몫만큼만 쓴다.
        need_cell = max(
            self.f_label.measure(label)
            + LV_GAP
            + self.f_value.measure(MAX_VALUE)
            + VR_GAP
            + self.f_small.measure(left)
            for label, left in zip(("5시간", "주간"), MAX_LEFT)
        )
        need_right = max(
            self.f_small.measure(MAX_STAMP),
            self.f_small.measure(MAX_SCOPED),
            self.f_msg.measure(MAX_ERROR),
        )
        avail = self.width - PAD_L - PAD_R - GAP * 2
        self.right_w = min(need_right, max(60, avail - need_cell * 2))
        cell_w = (avail - self.right_w) // 2

        self.accent = self.c.create_rectangle(0, 0, ACC, H, fill=TRACK, width=0)

        x1 = PAD_L
        x2 = PAD_L + cell_w + GAP
        rx = self.width - PAD_R
        self.five = Cell(self, x1, cell_w, "5시간")
        self.week = Cell(self, x2, cell_w, "주간")
        for x in (x1, x2):
            self.c.create_line(
                x + cell_w + GAP // 2, DIV_TOP, x + cell_w + GAP // 2, DIV_BOT,
                fill=LINE, width=1,
            )

        # 오른쪽 윗자리 — 평소엔 모델별, 오류일 땐 상태 문구. 같은 자리를 나눠 쓴다.
        self.model = self.c.create_text(
            rx, TOP_Y + SM_BASE, text="불러오는 중", anchor="e",
            font=self.f_small, fill=FAINT,
        )
        self.msg = self.c.create_text(
            rx, TOP_Y + LBL_BASE, text="", anchor="e", font=self.f_msg, fill=RED
        )
        self.stamp = self.c.create_text(
            rx, BAR_CY, text="", anchor="e", font=self.f_small, fill=FAINT
        )

        self.five.set(None, "")
        self.week.set(None, "")

    # -------------------------------------------------- 바탕 두 얼굴
    def _paint(self, bg: str, accent: str) -> None:
        self.c.configure(bg=bg)
        self.c.itemconfigure(self.accent, fill=accent)

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._paint(BG, tone(worst(usage)))
        self.five.set(usage.five.pct, usage.five.left)
        self.week.set(usage.week.pct, usage.week.left)

        text = scoped_text(usage, 1)
        self.c.itemconfigure(
            self.model, text=_fit(text, self.f_small, self.right_w), fill=LABEL
        )
        self.c.itemconfigure(self.msg, text="")
        self.c.itemconfigure(self.stamp, text=f"{stamp} 기준")

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        # 기준 시각은 오류일수록 중요하다 — 붉게 죽이지 않고 FAINT 그대로 둔다.
        self._paint(RED_BG, RED)
        self.c.itemconfigure(self.model, text="")
        self.c.itemconfigure(self.msg, text=_clip(text, self.f_msg, self.right_w))
        if not keep_values:
            self.five.set(None, "")
            self.week.set(None, "")
            self.c.itemconfigure(self.stamp, text=stamp)
