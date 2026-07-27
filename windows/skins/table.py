"""
표형 — 한도 하나가 한 줄. 4열(한도 / 사용률 / 게이지 / 초기화까지)로 세로 정렬한다.
모델별 한도도 같은 표의 마지막 한 줄. 값이 없으면 줄 자리는 남기고 안만 비운다.
위계: 사용률 숫자(12pt) > 한도 이름(9pt) > 초기화까지(8pt).
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
    RED_DIM,
    SUB,
    TITLE,
    TRACK,
    Skin,
    scoped_text,
    tone,
    worst,
)

PAD = 14
# 한도 / 사용률 / 게이지 / 초기화까지
# 가장 긴 문자열('Claude Sonnet' · '100%' · '10시간 00분 후')을 재고 글자 상자 여백 6을
# 더해 잡은 폭. 합 288 + 좌우 여백 28 = 316
COL = (86, 48, 72, 82)
CHROME = 6  # 라벨이 글자 말고 더 먹는 폭
GAUGE_W, GAUGE_H, SEGS, GAP = 60, 8, 10, 1.5
ROW_PAD = 2


class Row:
    """표 한 줄 — 이름 / 사용률 / 눈금 게이지 / 초기화까지."""

    def __init__(self, body: tk.Misc, r: int, name: str = ""):
        self.name = tk.Label(body, text=name, bg=BG, fg=SUB, font=(KR, 9), anchor="w")
        self.name.grid(row=r, column=0, sticky="w", pady=ROW_PAD)

        self.pct = tk.Label(
            body, text="--", bg=BG, fg=FAINT, font=(NUM, 12, "bold"), anchor="e"
        )
        self.pct.grid(row=r, column=1, sticky="e", pady=ROW_PAD)

        self.bar = tk.Canvas(
            body, width=GAUGE_W, height=GAUGE_H, bg=BG, highlightthickness=0, bd=0
        )
        self.bar.grid(row=r, column=2, sticky="w", padx=(10, 0), pady=ROW_PAD)

        self.left = tk.Label(body, text="", bg=BG, fg=FAINT, font=(KR, 8), anchor="e")
        self.left.grid(row=r, column=3, sticky="e", pady=ROW_PAD)

    def rename(self, text: str) -> None:
        self.name.config(text=text)

    def set(self, pct: float | None, left: str) -> None:
        color = tone(pct)
        self.pct.config(text="--" if pct is None else f"{pct:.0f}%", fg=color)
        self.left.config(text=left)

        # 켜진 한 칸 = 이미 넘긴 10%. 내림이라 꽉 찬 게이지는 100% 뿐이다.
        # (반올림이면 95~100%가 모두 꽉 참으로 보여 한도 소진 여부를 구분 못 한다.)
        # 값이 있으면 아무리 작아도 한 칸은 켠다.
        filled = 0
        if pct is not None and pct > 0:
            filled = max(1, min(SEGS, int(pct * SEGS / 100)))
        step = GAUGE_W / SEGS
        self.bar.delete("all")
        for i in range(SEGS):
            x0 = i * step
            self.bar.create_rectangle(
                x0, 0, x0 + step - GAP, GAUGE_H,
                fill=color if i < filled else TRACK, width=0,
            )

    def clear(self) -> None:
        """줄 자리는 그대로 두고 안만 비운다 — 해당 한도가 아예 없을 때."""
        self.name.config(text="")
        self.pct.config(text="")
        self.left.config(text="")
        self.bar.delete("all")


class TableSkin(Skin):
    key = "table"
    name = "표형"
    width = 316

    def build(self, parent: tk.Misc) -> None:
        self._kr9 = tkfont.Font(font=(KR, 9))

        # 머리말 — 평소엔 상태점 + 제목, 오류일 땐 같은 자리가 빨간 띠가 된다.
        self.head = tk.Frame(parent, bg=BG)
        self.head.pack(fill="x")
        self.accent = tk.Frame(self.head, bg=BG, width=3)
        self.accent.pack(side="left", fill="y")
        self.head_pad = tk.Frame(self.head, bg=BG)
        self.head_pad.pack(fill="x", padx=(PAD - 3, PAD), pady=(13, 10))
        self.dot = tk.Canvas(
            self.head_pad, width=9, height=9, bg=BG, highlightthickness=0, bd=0
        )
        self.dot.pack(side="left", pady=(3, 0))
        self.title = tk.Label(
            self.head_pad, text="클로드 사용량", bg=BG, fg=TITLE, font=(KR, 10, "bold")
        )
        self.title.pack(side="left", padx=(6, 0))
        self.stamp = tk.Label(self.head_pad, text="", bg=BG, fg=FAINT, font=(KR, 8))
        self.stamp.pack(side="right")

        body = tk.Frame(parent, bg=BG)
        body.pack(fill="x", padx=PAD, pady=(0, 14))
        for i, w in enumerate(COL):
            body.grid_columnconfigure(i, minsize=w)

        # 열 이름 — 게이지 열은 보면 아는 것이라 이름을 두지 않는다.
        hf = (KR, 8)
        tk.Label(body, text="한도", bg=BG, fg=LABEL, font=hf).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(body, text="사용률", bg=BG, fg=LABEL, font=hf).grid(
            row=0, column=1, sticky="e"
        )
        tk.Label(body, text="초기화까지", bg=BG, fg=LABEL, font=hf).grid(
            row=0, column=3, sticky="e"
        )
        tk.Frame(body, bg=LINE, height=1).grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(3, 4)
        )

        self.five = Row(body, 2, "5시간")
        self.week = Row(body, 3, "주간")

        # 모델별 한도 줄과의 구분선. 그 줄이 비면 자리(1px)는 두고 색만 지운다.
        self.model_rule = tk.Frame(body, bg=LINE, height=1)
        self.model_rule.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(4, 4))

        # 모델별 한도 — 값이 없어도 이 줄은 사라지지 않는다 (창 높이 고정).
        self.model = Row(body, 5)

        # 줄 높이를 못 박아 둔다. 비어 있는 줄도 같은 높이를 차지한다.
        cell = tkfont.Font(font=(NUM, 12, "bold")).metrics("linespace") + 4
        for r in (2, 3, 5):
            body.grid_rowconfigure(r, minsize=max(cell, GAUGE_H) + ROW_PAD * 2)

    # -------------------------------------------------- 머리말 두 얼굴
    def _dot(self, color: str, bg: str) -> None:
        self.dot.configure(bg=bg)
        self.dot.delete("all")
        self.dot.create_oval(0, 0, 8, 8, fill=color, width=0)

    def _head_normal(self, pct: float | None) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=BG)
        self.accent.configure(bg=BG)
        self.title.configure(text="클로드 사용량", fg=TITLE)
        self.stamp.configure(fg=FAINT)
        self._dot(tone(pct), BG)

    def _head_error(self, text: str) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=RED_BG)
        self.accent.configure(bg=RED)
        self.title.configure(text=text, fg=RED)
        self.stamp.configure(fg=RED_DIM)
        self._dot(RED, RED_BG)

    # -------------------------------------------------- 이름 칸에 맞춰 자르기
    def _fit(self, text: str) -> str:
        """긴 모델 이름은 이름 칸 안에서 잘라 넣는다 (열이 밀려나지 않게)."""
        px = COL[0] - CHROME
        if self._kr9.measure(text) <= px:
            return text
        while text and self._kr9.measure(text + "…") > px:
            text = text[:-1]
        return text + "…"

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._head_normal(worst(usage))
        self.five.set(usage.five.pct, usage.five.left)
        self.week.set(usage.week.pct, usage.week.left)
        self.stamp.config(text=f"{stamp} 기준")

        # 모델별 한도가 없으면 base.scoped_text 가 빈 문자열을 준다 — 그 줄은 비운다.
        if scoped_text(usage, 1):
            top = max(
                (s for s in usage.scoped if s.pct is not None), key=lambda s: s.pct
            )
            self.model.rename(self._fit(top.label))
            self.model.set(top.pct, top.left)
            self.model_rule.configure(bg=LINE)
        else:
            self.model.clear()
            self.model_rule.configure(bg=BG)

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        self._head_error(text)
        if not keep_values:
            self.stamp.config(text=stamp)
            self.five.set(None, "")
            self.week.set(None, "")
            self.model.clear()
            self.model_rule.configure(bg=BG)
