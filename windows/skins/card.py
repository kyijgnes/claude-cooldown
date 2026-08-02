"""
카드형 — 여백을 두고 숫자를 크게 앞세운 기본 모양.
위계: 숫자(24pt) > 남은시간(10pt) > 항목 이름(8pt). 게이지는 3px 선으로 절제.

주간 줄에는 '지금쯤 29% · 알맞음' 이 오른쪽에 붙고, 게이지의 그 자리에 눈금이 선다.
"""

from __future__ import annotations

import tkinter as tk

from cooldown_core import Pace, Usage, five_due, pace

from .base import KR, MARK_W, NUM, P, Skin, mark_x, pace_color, scoped_text, tone

PAD = 18
BAR_H = 3  # 게이지 두께
BAR_TOP = 3  # 게이지 위 여백 (눈금이 위아래로 삐져나올 자리를 캔버스 안에 둔다)
BAR_BOX = 9  # 게이지 칸 전체 높이


class Section:
    """한 한도 덩어리 — 이름 / 큰 숫자 + 남은시간 / 얇은 게이지."""

    def __init__(self, parent: tk.Misc, label: str, inner: int, hint: bool = False):
        self.inner = inner
        box = tk.Frame(parent, bg=P.bg)
        box.pack(fill="x", padx=PAD)

        head = tk.Frame(box, bg=P.bg)
        head.pack(fill="x")
        tk.Label(head, text=label, bg=P.bg, fg=P.label, font=(KR, 8), anchor="w").pack(
            side="left"
        )
        # 속도 자리 — 주간에만 둔다. 5시간 창은 앞쪽에 몰아 쓰는 게 정상이라 뜻이 없다.
        self.verdict = self.due = None
        if hint:
            self.verdict = tk.Label(head, text="", bg=P.bg, fg=P.faint, font=(KR, 8))
            self.verdict.pack(side="right")
            self.due = tk.Label(head, text="", bg=P.bg, fg=P.label, font=(KR, 8))
            self.due.pack(side="right", padx=(0, 7))

        row = tk.Frame(box, bg=P.bg)
        row.pack(fill="x")
        self.value = tk.Label(row, text="--", bg=P.bg, fg=P.faint, font=(NUM, 24, "bold"))
        self.value.pack(side="left")
        self.left = tk.Label(row, text="", bg=P.bg, fg=P.sub, font=(KR, 10))
        self.left.pack(side="right", anchor="s", pady=(0, 9))

        # 바탕은 P.bg 다 — 게이지 띠(P.track)는 안에 직접 그린다. 눈금이 띠 위아래로
        # 조금 삐져나와야 채워진 색 위에서도 눈에 걸린다.
        self.bar = tk.Canvas(
            box, height=BAR_BOX, width=inner, bg=P.bg, highlightthickness=0, bd=0
        )
        self.bar.pack(fill="x")

    def set(
        self,
        pct: float | None,
        left: str,
        p: Pace | None = None,
        due: float | None = None,
    ) -> None:
        # p(주간 속도)는 '지금쯤/판정' 글자 + 눈금에 쓰고, due(5시간)는 눈금에만 쓴다.
        color = tone(pct)
        self.value.config(text="--" if pct is None else f"{pct:.0f}%", fg=color)
        self.left.config(text=left, fg=P.sub if pct is not None else P.faint)

        if self.due is not None:
            self.due.config(text="" if p is None else f"적정선 {p.due:.0f}%")
            self.verdict.config(
                text="" if p is None else p.verdict,
                fg=P.faint if p is None else pace_color(p.level),
            )

        self.bar.delete("all")
        # 배치 전에는 winfo_width() 가 0 이 아니라 **1** 을 돌려준다.
        # `or` 로 받으면 1 이 참이라 폴백이 죽고, 게이지가 0.4px 로 그려진 뒤
        # 다음 조회(최대 5분)까지 그대로 남는다. 디자인을 바꿀 때 이 경로를 탄다.
        measured = self.bar.winfo_width()
        width = measured if measured > 1 else self.inner
        y0, y1 = BAR_TOP, BAR_TOP + BAR_H
        self.bar.create_rectangle(0, y0, width, y1, fill=P.track, width=0)
        if pct is not None:
            self.bar.create_rectangle(0, y0, width * pct / 100, y1, fill=color, width=0)
        mark_due = p.due if p is not None else due
        if mark_due is not None:
            x = mark_x(mark_due, width)
            self.bar.create_rectangle(x, 0, x + MARK_W, BAR_BOX, fill=P.title, width=0)


class CardSkin(Skin):
    key = "card"
    name = "카드형"
    width = 260

    def build(self, parent: tk.Misc) -> None:
        inner = self.width - PAD * 2

        # 머리말 — 평소엔 제목, 오류일 땐 빨간 띠. 높이는 그대로 유지된다.
        self.head = tk.Frame(parent, bg=P.bg)
        self.head.pack(fill="x", pady=(0, 4))
        self.accent = tk.Frame(self.head, bg=P.bg, width=3)
        self.accent.pack(side="left", fill="y")
        self.head_pad = tk.Frame(self.head, bg=P.bg)
        self.head_pad.pack(fill="x", padx=(PAD - 3, PAD), pady=(15, 9))
        self.title = tk.Label(
            self.head_pad, text="클로드 사용량", bg=P.bg, fg=P.title, font=(KR, 10, "bold")
        )
        self.title.pack(side="left")
        self.stamp = tk.Label(self.head_pad, text="", bg=P.bg, fg=P.faint, font=(KR, 8))
        self.stamp.pack(side="right")

        self.five = Section(parent, "5시간 한도", inner)
        tk.Frame(parent, bg=P.bg, height=14).pack()
        self.week = Section(parent, "주간 한도", inner, hint=True)

        tk.Frame(parent, bg=P.line, height=1).pack(fill="x", padx=PAD, pady=(18, 0))

        foot = tk.Frame(parent, bg=P.bg)
        foot.pack(fill="x", padx=PAD, pady=(9, 15))
        self.foot_label = tk.Label(foot, text="", bg=P.bg, fg=P.label, font=(KR, 8))
        self.foot_label.pack(side="left")
        self.foot_value = tk.Label(foot, text="", bg=P.bg, fg=P.sub, font=(KR, 9))
        self.foot_value.pack(side="left", padx=(7, 0))
        self.note = tk.Label(foot, text="불러오는 중", bg=P.bg, fg=P.faint, font=(KR, 8))
        self.note.pack(side="right")

    # -------------------------------------------------- 머리말 두 얼굴
    def _head_normal(self) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=P.bg)
        self.accent.configure(bg=P.bg)
        self.title.configure(text="클로드 사용량", fg=P.title)
        self.stamp.configure(fg=P.faint)

    def _head_error(self, text: str) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=P.red_bg)
        self.accent.configure(bg=P.red)
        self.title.configure(text=text, fg=P.red)
        self.stamp.configure(fg=P.red_dim)

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._head_normal()
        self.five.set(usage.five.pct, usage.five.left, due=five_due(usage))
        self.week.set(usage.week.pct, usage.week.left, pace(usage))
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

    def notice(self, text: str) -> None:
        # 값은 멀쩡한데 알릴 것(자동 시작 놓침)을 꼬리말 오른쪽에 호박색으로. show()/
        # show_error() 가 note 를 비운 직후 앱이 부른다 — 빈 문자열이면 그대로 둔다.
        if not text:
            return
        self.note.config(text=text, fg=P.amber)
