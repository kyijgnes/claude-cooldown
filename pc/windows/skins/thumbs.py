"""
스킨 작은 그림 — 메인 화면 > 위젯 모양 의 고르기 카드에 들어가는 손그림
=======================================================================
진짜 스킨을 지어 줄이는 대신(창을 하나 더 띄워야 하고 느리다) 생김새만 몇 획으로 그린다.
색은 지금 한 벌 `P` 를 그대로 쓰므로 밝기·클로디 색을 바꾸면 카드도 같이 바뀐다.
새 스킨은 여기 `_DRAW` 에 한 줄 더하면 되고, 없으면 네모 하나로 그린다.
"""

from __future__ import annotations

import tkinter as tk

from .base import P

# 카드 밑에 쓰는 짧은 이름 (스킨 이름은 우클릭 메뉴·기록에 그대로 쓰므로 따로 둔다)
SHORT = {"card": "카드", "arc": "아크", "table": "표", "slim": "넓은 바", "mini": "좁은 바"}


def short_name(cls) -> str:
    return SHORT.get(cls.key, cls.name)


def _claudi(c: tk.Canvas, x: float, y: float, s: float = 2) -> None:
    """클로디 한 마리 (도트 몇 칸). (x, y) 는 왼쪽 위."""
    for col, row in ((1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1),
                     (1, 2), (2, 2), (3, 2), (1, 3), (3, 3)):
        c.create_rectangle(x + col * s, y + row * s, x + (col + 1) * s, y + (row + 1) * s,
                           fill=P.mascot, width=0)


def _bar(c: tk.Canvas, x: float, y: float, w: float, h: float, frac: float, color: str) -> None:
    c.create_rectangle(x, y, x + w, y + h, fill=P.gauge, width=0)
    c.create_rectangle(x, y, x + w * frac, y + h, fill=color, width=0)


def _box(c: tk.Canvas, w: int, h: int, bw: int, bh: int) -> tuple[float, float]:
    x, y = (w - bw) / 2, (h - bh) / 2
    c.create_rectangle(x, y, x + bw, y + bh, fill=P.bg, outline=P.line)
    return x, y


def _card(c, w, h):
    x, y = _box(c, w, h, 44, 36)
    _claudi(c, x + 32, y + 4)
    c.create_rectangle(x + 5, y + 6, x + 18, y + 8, fill=P.label, width=0)
    _bar(c, x + 5, y + 15, 34, 4, 0.2, P.green)
    c.create_rectangle(x + 5, y + 22, x + 16, y + 24, fill=P.label, width=0)
    _bar(c, x + 5, y + 27, 34, 4, 0.6, P.amber)


def _arc(c, w, h):
    x, y = _box(c, w, h, 50, 36)
    for i, (frac, color) in enumerate(((0.2, P.green), (0.6, P.amber))):
        cx = x + 13 + i * 22
        c.create_arc(cx - 9, y + 9, cx + 9, y + 27, start=-30, extent=240, style="arc",
                     outline=P.gauge, width=3)
        c.create_arc(cx - 9, y + 9, cx + 9, y + 27, start=210, extent=-240 * frac, style="arc",
                     outline=color, width=3)
    _claudi(c, x + 21, y + 28, 1.5)


def _table(c, w, h):
    x, y = _box(c, w, h, 54, 36)
    _claudi(c, x + 42, y + 4)
    for i, (frac, color) in enumerate(((0.2, P.green), (0.6, P.amber), (0.1, P.green))):
        ry = y + 6 + i * 9
        c.create_rectangle(x + 5, ry + 1, x + 16, ry + 3, fill=P.label, width=0)
        _bar(c, x + 19, ry, 20, 4, frac, color)
    c.create_line(x + 4, y + 14, x + 40, y + 14, fill=P.line)
    c.create_line(x + 4, y + 23, x + 40, y + 23, fill=P.line)


def _taskbar(c, w, h, bw):
    c.create_rectangle(0, h - 16, w, h, fill=P.gauge, width=0)
    x, y = (w - bw) / 2, h - 14
    c.create_rectangle(x, y, x + bw, y + 12, fill=P.bg, outline=P.line)
    return x, y


def _slim(c, w, h):
    x, y = _taskbar(c, w, h, 62)
    _claudi(c, x + 4, y + 2)
    _bar(c, x + 17, y + 4, 18, 4, 0.2, P.green)
    _bar(c, x + 39, y + 4, 18, 4, 0.6, P.amber)


def _mini(c, w, h):
    x, y = _taskbar(c, w, h, 34)
    _claudi(c, x + 3, y + 2)
    _bar(c, x + 15, y + 2, 15, 3, 0.2, P.green)
    _bar(c, x + 15, y + 7, 15, 3, 0.6, P.amber)


_DRAW = {"card": _card, "arc": _arc, "table": _table, "slim": _slim, "mini": _mini}


def draw(c: tk.Canvas, key: str, w: int, h: int) -> None:
    """캔버스 `c`(폭 w, 높이 h, 바탕은 부르는 쪽이 칠함)에 스킨 `key` 의 작은 그림."""
    fn = _DRAW.get(key)
    if fn is None:
        x, y = _box(c, w, h, 44, 32)
        _claudi(c, x + 4, y + 4)
        return
    fn(c, w, h)
