"""
표형 — 한도 하나가 한 줄. 4열(한도 / 사용률 / 게이지 / 초기화까지)로 세로 정렬한다.
모델별 한도도 같은 표의 마지막 한 줄. 값이 없으면 줄 자리는 남기고 안만 비운다.
위계: 사용률 숫자(12pt) > 한도 이름(9pt) > 초기화까지(8pt).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from cooldown_core import Usage, five_due, pace

from .base import KR, MARK_W, NUM, P, Skin, mark_x, scoped_text, tone, worst

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
        self.name = tk.Label(body, text=name, bg=P.bg, fg=P.sub, font=(KR, 9), anchor="w")
        self.name.grid(row=r, column=0, sticky="w", pady=ROW_PAD)

        self.pct = tk.Label(
            body, text="--", bg=P.bg, fg=P.faint, font=(NUM, 12, "bold"), anchor="e"
        )
        self.pct.grid(row=r, column=1, sticky="e", pady=ROW_PAD)

        self.bar = tk.Canvas(
            body, width=GAUGE_W, height=GAUGE_H, bg=P.bg, highlightthickness=0, bd=0
        )
        self.bar.grid(row=r, column=2, sticky="w", padx=(10, 0), pady=ROW_PAD)

        self.left = tk.Label(body, text="", bg=P.bg, fg=P.faint, font=(KR, 8), anchor="e")
        self.left.grid(row=r, column=3, sticky="e", pady=ROW_PAD)

    def rename(self, text: str) -> None:
        self.name.config(text=text)

    def set(self, pct: float | None, left: str, due: float | None = None) -> None:
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
                fill=color if i < filled else P.track, width=0,
            )
        # '지금쯤' 눈금 — 칸 사이 틈에 떨어져도 보이게 맨 위에 대비색으로 긋는다
        if due is not None:
            x = mark_x(due, GAUGE_W)
            self.bar.create_rectangle(x, 0, x + MARK_W, GAUGE_H, fill=P.title, width=0)

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
        self.head = tk.Frame(parent, bg=P.bg)
        self.head.pack(fill="x")
        self.accent = tk.Frame(self.head, bg=P.bg, width=3)
        self.accent.pack(side="left", fill="y")
        self.head_pad = tk.Frame(self.head, bg=P.bg)
        self.head_pad.pack(fill="x", padx=(PAD - 3, PAD), pady=(13, 10))
        self.dot = tk.Canvas(
            self.head_pad, width=9, height=9, bg=P.bg, highlightthickness=0, bd=0
        )
        self.dot.pack(side="left", pady=(3, 0))
        self.title = tk.Label(
            self.head_pad, text="클로드 사용량", bg=P.bg, fg=P.title, font=(KR, 10, "bold")
        )
        self.title.pack(side="left", padx=(6, 0))
        self.stamp = tk.Label(self.head_pad, text="", bg=P.bg, fg=P.faint, font=(KR, 8))
        self.stamp.pack(side="right")

        body = tk.Frame(parent, bg=P.bg)
        body.pack(fill="x", padx=PAD, pady=(0, 14))
        for i, w in enumerate(COL):
            body.grid_columnconfigure(i, minsize=w)

        # 열 이름 — 게이지 열은 보면 아는 것이라 이름을 두지 않는다.
        hf = (KR, 8)
        tk.Label(body, text="한도", bg=P.bg, fg=P.label, font=hf).grid(
            row=0, column=0, sticky="w"
        )
        tk.Label(body, text="사용률", bg=P.bg, fg=P.label, font=hf).grid(
            row=0, column=1, sticky="e"
        )
        tk.Label(body, text="초기화까지", bg=P.bg, fg=P.label, font=hf).grid(
            row=0, column=3, sticky="e"
        )
        tk.Frame(body, bg=P.line, height=1).grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(3, 4)
        )

        self.five = Row(body, 2, "5시간")
        self.week = Row(body, 3, "주간")

        # 모델별 한도 줄과의 구분선. 그 줄이 비면 자리(1px)는 두고 색만 지운다.
        self.model_rule = tk.Frame(body, bg=P.line, height=1)
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
            w.configure(bg=P.bg)
        self.accent.configure(bg=P.bg)
        self.title.configure(text="클로드 사용량", fg=P.title)
        self.stamp.configure(fg=P.faint)
        self._dot(tone(pct), P.bg)

    def _head_error(self, text: str) -> None:
        for w in (self.head, self.head_pad, self.title, self.stamp):
            w.configure(bg=P.red_bg)
        self.accent.configure(bg=P.red)
        self.title.configure(text=text, fg=P.red)
        self.stamp.configure(fg=P.red_dim)
        self._dot(P.red, P.red_bg)

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
        p = pace(usage)
        self.five.set(usage.five.pct, usage.five.left, five_due(usage))
        self.week.set(usage.week.pct, usage.week.left, p.due if p else None)
        self.stamp.config(text=f"{stamp} 기준")

        # 모델별 한도가 없으면 base.scoped_text 가 빈 문자열을 준다 — 그 줄은 비운다.
        if scoped_text(usage, 1):
            top = max(
                (s for s in usage.scoped if s.pct is not None), key=lambda s: s.pct
            )
            self.model.rename(self._fit(top.label))
            self.model.set(top.pct, top.left)
            self.model_rule.configure(bg=P.line)
        else:
            self.model.clear()
            self.model_rule.configure(bg=P.bg)

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        self._head_error(text)
        if not keep_values:
            self.stamp.config(text=stamp)
            self.five.set(None, "")
            self.week.set(None, "")
            self.model.clear()
            self.model_rule.configure(bg=P.bg)

    def notice(self, text: str) -> None:
        # 값은 멀쩡한데 알릴 것(자동 시작 놓침)을 머리말 제목 자리에 호박색으로.
        # show() 가 _head_normal 로 제목을 정상으로 둔 직후 앱이 부른다 — 빈 문자열이면
        # 그대로 둔다(정상 제목 유지). 오류(빨강)일 땐 앱이 이걸 부르지 않는다.
        if not text:
            return
        self.title.configure(text=text, fg=P.amber)
