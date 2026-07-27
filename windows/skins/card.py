"""
카드형 — 여백을 두고 숫자를 크게 앞세운 기본 모양.
위계: 숫자(24pt) > 남은시간(10pt) > 항목 이름(8pt). 게이지는 3px 선으로 절제.
"""

from __future__ import annotations

import tkinter as tk

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
)

PAD = 18


class Section:
    """한 한도 덩어리 — 이름 / 큰 숫자 + 남은시간 / 얇은 게이지."""

    def __init__(self, parent: tk.Misc, label: str, inner: int):
        self.inner = inner
        box = tk.Frame(parent, bg=BG)
        box.pack(fill="x", padx=PAD)

        tk.Label(box, text=label, bg=BG, fg=LABEL, font=(KR, 8), anchor="w").pack(
            fill="x"
        )

        row = tk.Frame(box, bg=BG)
        row.pack(fill="x")
        self.value = tk.Label(row, text="--", bg=BG, fg=FAINT, font=(NUM, 24, "bold"))
        self.value.pack(side="left")
        self.left = tk.Label(row, text="", bg=BG, fg=SUB, font=(KR, 10))
        self.left.pack(side="right", anchor="s", pady=(0, 9))

        self.bar = tk.Canvas(
            box, height=3, width=inner, bg=TRACK, highlightthickness=0, bd=0
        )
        self.bar.pack(fill="x", pady=(3, 0))

    def set(self, pct: float | None, left: str) -> None:
        color = tone(pct)
        self.value.config(text="--" if pct is None else f"{pct:.0f}%", fg=color)
        self.left.config(text=left, fg=SUB if pct is not None else FAINT)
        self.bar.delete("all")
        # 배치 전에는 winfo_width() 가 0 이 아니라 **1** 을 돌려준다.
        # `or` 로 받으면 1 이 참이라 폴백이 죽고, 게이지가 0.4px 로 그려진 뒤
        # 다음 조회(최대 5분)까지 그대로 남는다. 디자인을 바꿀 때 이 경로를 탄다.
        measured = self.bar.winfo_width()
        width = measured if measured > 1 else self.inner
        if pct is not None:
            self.bar.create_rectangle(0, 0, width * pct / 100, 3, fill=color, width=0)


class CardSkin(Skin):
    key = "card"
    name = "카드형"
    width = 260

    def build(self, parent: tk.Misc) -> None:
        inner = self.width - PAD * 2

        # 머리말 — 평소엔 제목, 오류일 땐 빨간 띠. 높이는 그대로 유지된다.
        self.head = tk.Frame(parent, bg=BG)
        self.head.pack(fill="x", pady=(0, 4))
        self.accent = tk.Frame(self.head, bg=BG, width=3)
        self.accent.pack(side="left", fill="y")
        self.head_pad = tk.Frame(self.head, bg=BG)
        self.head_pad.pack(fill="x", padx=(PAD - 3, PAD), pady=(15, 9))
        self.title = tk.Label(
            self.head_pad, text="클로드 사용량", bg=BG, fg=TITLE, font=(KR, 10, "bold")
        )
        self.title.pack(side="left")
        self.stamp = tk.Label(self.head_pad, text="", bg=BG, fg=FAINT, font=(KR, 8))
        self.stamp.pack(side="right")

        self.five = Section(parent, "5시간 한도", inner)
        tk.Frame(parent, bg=BG, height=17).pack()
        self.week = Section(parent, "주간 한도", inner)

        tk.Frame(parent, bg=LINE, height=1).pack(fill="x", padx=PAD, pady=(18, 0))

        foot = tk.Frame(parent, bg=BG)
        foot.pack(fill="x", padx=PAD, pady=(9, 15))
        self.foot_label = tk.Label(foot, text="", bg=BG, fg=LABEL, font=(KR, 8))
        self.foot_label.pack(side="left")
        self.foot_value = tk.Label(foot, text="", bg=BG, fg=SUB, font=(KR, 9))
        self.foot_value.pack(side="left", padx=(7, 0))
        self.note = tk.Label(foot, text="불러오는 중", bg=BG, fg=FAINT, font=(KR, 8))
        self.note.pack(side="right")

    # -------------------------------------------------- 머리말 두 얼굴
    def _head_normal(self) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=BG)
        self.accent.configure(bg=BG)
        self.title.configure(text="클로드 사용량", fg=TITLE)
        self.stamp.configure(fg=FAINT)

    def _head_error(self, text: str) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=RED_BG)
        self.accent.configure(bg=RED)
        self.title.configure(text=text, fg=RED)
        self.stamp.configure(fg=RED_DIM)

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._head_normal()
        self.five.set(usage.five.pct, usage.five.left)
        self.week.set(usage.week.pct, usage.week.left)
        self.stamp.config(text=f"{stamp} 기준")

        text = scoped_text(usage)
        self.foot_label.config(text="모델별" if text else "")
        self.foot_value.config(text=text)
        self.note.config(text="")

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        self._head_error(text)
        if not keep_values:
            self.stamp.config(text=stamp)
            self.five.set(None, "")
            self.week.set(None, "")
            self.foot_label.config(text="")
            self.foot_value.config(text="")
        self.note.config(text="")
