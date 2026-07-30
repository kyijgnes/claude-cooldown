"""
아크형 — 5시간 / 주간을 270도 도넛 게이지 두 개로 나란히 본다.
링은 PIL 로 4배 확대해 그린 뒤 줄여 붙여 계단현상을 없앤다.
(ImageTk 가 없으면 Canvas.create_arc 로 자동 대체)

값이 바뀌면 링 이미지만 다시 만들어 갈아 끼운다. 위젯·항목은 build() 에서 한 번만 만든다.
"""

from __future__ import annotations

import math
import tkinter as tk
import tkinter.font as tkfont

from cooldown_core import Usage, pace

from .base import KR, NUM, P, Skin, scoped_text, tone

try:
    from PIL import Image, ImageDraw, ImageTk

    try:
        RESAMPLE = Image.Resampling.LANCZOS
    except AttributeError:  # 구버전 Pillow
        RESAMPLE = Image.LANCZOS
    HAVE_PIL = True
except Exception:  # noqa: BLE001  PIL 이 없어도 스킨은 떠야 한다
    HAVE_PIL = False

# ---------------------------------------------------------------- 치수
H = 150  # 창 세로. 네 상태 모두 이 값 그대로다.
MARGIN = 24  # 좌우 여백 — 구분선·꼬리말·오류 띠가 함께 쓴다
GAP_X = 72  # 가운데에서 게이지 중심까지

CY = 62  # 게이지 중심 y
R_OUT = 46  # 링 바깥 반지름
W_ARC = 12  # 링 두께
R_MID = R_OUT - W_ARC // 2  # 중심선 = 둥근 끝 캡이 놓이는 반지름

START = 135.0  # PIL 각도(시계방향, 0=3시). 135 = 왼쪽 아래
SWEEP = 270.0  # 아래가 트인 270도
SS = 4  # 슈퍼샘플링 배율

Y_BASE = 71  # 퍼센트 숫자 베이스라인 (링 정중앙)
Y_LABEL = 92  # 링 아래 트인 자리에 들어가는 이름
Y_RESET = 112
Y_LINE = 126
Y_FOOT = 138
BAR_TOP = 125  # 오류 띠 — 구분선·꼬리말과 같은 자리를 덮는다
BAR_H = 20

F_NUM = (NUM, -24, "bold")
F_SIG = (NUM, -13, "bold")
F_LABEL = (KR, -12)
F_SMALL = (KR, -12)
F_ERR = (KR, -13, "bold")


# ---------------------------------------------------------------- 그리기
def _cap(d, c: float, r: float, ang: float, w: float, fill: str) -> None:
    """아크 끝을 둥글게 막는 원. 중심선 반지름 r 위에 올린다."""
    x = c + r * math.cos(math.radians(ang))
    y = c + r * math.sin(math.radians(ang))
    d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=fill)


def _angle(pct: float) -> float:
    """사용률(0~100) 이 링 위에서 서는 각도."""
    return START + SWEEP * max(0.0, min(100.0, pct)) / 100.0


def _ring(pct: float | None, due: float | None = None):
    """링 한 개를 이미지로 그린다. PIL 의 arc 는 bbox 안쪽으로 두께를 그린다.
    `due` 를 주면 그 자리에 '지금쯤' 눈금을 링을 가로질러 긋는다."""
    size = 2 * R_OUT + 2
    s = size * SS
    img = Image.new("RGB", (s, s), P.bg)
    d = ImageDraw.Draw(img)
    c = s / 2
    w = W_ARC * SS
    r = R_MID * SS
    ro = R_OUT * SS
    box = (c - ro, c - ro, c + ro, c + ro)

    d.arc(box, START, START + SWEEP, fill=P.track, width=int(w))
    _cap(d, c, r, START, w, P.track)
    _cap(d, c, r, START + SWEEP, w, P.track)

    if pct is not None:
        color = tone(pct)
        end = _angle(pct)
        if end - START > 0.6:
            d.arc(box, START, end, fill=color, width=int(w))
        _cap(d, c, r, START, w, color)
        _cap(d, c, r, end, w, color)

    if due is not None:
        # 링 두께를 한 뼘씩 넘겨 그어야 채워진 색 위에서도 눈에 걸린다
        a = math.radians(_angle(due))
        r0 = (R_MID - W_ARC / 2 - 1) * SS
        r1 = (R_MID + W_ARC / 2 + 1) * SS
        d.line(
            (c + r0 * math.cos(a), c + r0 * math.sin(a),
             c + r1 * math.cos(a), c + r1 * math.sin(a)),
            fill=P.title, width=int(2 * SS),
        )

    return ImageTk.PhotoImage(img.resize((size, size), RESAMPLE))


def _band(w: int, h: int, radius: int, fill: str, outline: str):
    img = Image.new("RGB", (w * SS, h * SS), P.bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (0, 0, w * SS - 1, h * SS - 1),
        radius=radius * SS,
        fill=fill,
        outline=outline,
        width=SS,
    )
    return ImageTk.PhotoImage(img.resize((w, h), RESAMPLE))


# ---------------------------------------------------------------- 게이지 한 개
class Gauge:
    """도넛 한 개 — 링 / 큰 숫자 / 이름 / 남은 시간."""

    def __init__(self, canvas: tk.Canvas, cx: int, label: str, fonts):
        self.c = canvas
        self.cx = cx
        self.f_num, self.f_sig = fonts
        self.image = None  # PhotoImage 는 붙들어 두지 않으면 GC 로 사라진다
        self.drawn = None  # 마지막으로 그린 값 — 같으면 다시 그리지 않는다

        if HAVE_PIL:
            self.image = _ring(None)
            self.ring = canvas.create_image(cx, CY, image=self.image)
            self.track = self.arc = self.mark = None
        else:
            box = (cx - R_MID, CY - R_MID, cx + R_MID, CY + R_MID)
            self.ring = None
            self.track = canvas.create_arc(
                *box, start=225, extent=-SWEEP, style="arc",
                outline=P.track, width=W_ARC,
            )
            self.arc = canvas.create_arc(
                *box, start=225, extent=-0.01, style="arc",
                outline=P.track, width=W_ARC, state="hidden",
            )
            self.mark = canvas.create_line(
                0, 0, 0, 0, fill=P.title, width=2, state="hidden"
            )

        self.num = canvas.create_text(
            cx, Y_BASE, text="", anchor="nw", fill=P.faint, font=F_NUM
        )
        self.sig = canvas.create_text(
            cx, Y_BASE, text="", anchor="nw", fill=P.faint, font=F_SIG
        )
        canvas.create_text(cx, Y_LABEL, text=label, fill=P.label, font=F_LABEL)
        self.left = canvas.create_text(cx, Y_RESET, text="", fill=P.sub, font=F_SMALL)
        self._percent(None, P.faint)

    def set(self, pct: float | None, left: str, due: float | None = None) -> None:
        color = tone(pct)
        self._ring(pct, color, due)
        self._percent(pct, color)
        self.c.itemconfigure(
            self.left, text=left, fill=P.sub if pct is not None else P.faint
        )

    def _ring(self, pct: float | None, color: str, due: float | None) -> None:
        # 눈금은 1분마다 조금씩 움직이므로 값과 함께 '마지막으로 그린 것'에 넣는다
        if (pct, due) == self.drawn:
            return
        self.drawn = (pct, due)
        if HAVE_PIL:
            image = _ring(pct, due)  # 캔버스에 먼저 걸고 나서 참조를 옮긴다
            self.c.itemconfigure(self.ring, image=image)
            self.image = image  # 놓으면 GC 로 사라진다
            return

        if due is None:
            self.c.itemconfigure(self.mark, state="hidden")
        else:
            a = math.radians(_angle(due))
            r0, r1 = R_MID - W_ARC / 2 - 1, R_MID + W_ARC / 2 + 1
            self.c.coords(
                self.mark,
                self.cx + r0 * math.cos(a), CY + r0 * math.sin(a),
                self.cx + r1 * math.cos(a), CY + r1 * math.sin(a),
            )
            self.c.itemconfigure(self.mark, state="normal")
        if pct is None or pct <= 0:
            self.c.itemconfigure(self.arc, state="hidden")
            return
        span = SWEEP * min(100.0, pct) / 100.0
        self.c.itemconfigure(
            self.arc, extent=-span, outline=color, state="normal"
        )

    def _percent(self, pct: float | None, color: str) -> None:
        """숫자는 크게, % 는 작게 — 100% 도 링 안에 들어오게."""
        num, sig = ("--", "") if pct is None else (f"{pct:.0f}", "%")
        wn = self.f_num.measure(num)
        ws = self.f_sig.measure(sig)
        gap = 2 if sig else 0
        x = self.cx - (wn + gap + ws) / 2
        self.c.coords(self.num, x, Y_BASE - self.f_num.metrics("ascent"))
        self.c.itemconfigure(self.num, text=num, fill=color)
        self.c.coords(self.sig, x + wn + gap, Y_BASE - self.f_sig.metrics("ascent"))
        self.c.itemconfigure(self.sig, text=sig, fill=color)


# ---------------------------------------------------------------- 스킨
class ArcSkin(Skin):
    key = "arc"
    name = "아크형"
    width = 280
    _ok_stamp = ""  # 마지막으로 값을 받은 시각

    def build(self, parent: tk.Misc) -> None:
        self.f_num = tkfont.Font(root=parent, font=F_NUM)
        self.f_sig = tkfont.Font(root=parent, font=F_SIG)

        self.c = c = tk.Canvas(
            parent, width=self.width, height=H, bg=P.bg, highlightthickness=0, bd=0
        )
        c.pack(fill="both", expand=True)

        mid = self.width // 2
        fonts = (self.f_num, self.f_sig)
        self.five = Gauge(c, mid - GAP_X, "5시간", fonts)
        self.week = Gauge(c, mid + GAP_X, "주간", fonts)

        x0, x1 = MARGIN, self.width - MARGIN
        self.line = c.create_line(x0, Y_LINE, x1, Y_LINE, fill=P.line)
        self.stamp = c.create_text(
            x0, Y_FOOT, text="", anchor="w", fill=P.label, font=F_SMALL
        )
        self.scoped = c.create_text(
            x1, Y_FOOT, text="", anchor="e", fill=P.sub, font=F_SMALL
        )
        self.dot = c.create_oval(0, 0, 0, 0, width=0, state="hidden")

        # 오류 띠 — 구분선·꼬리말과 같은 자리. 켜고 끄기만 하므로 높이가 안 변한다.
        if HAVE_PIL:
            self.band_image = _band(x1 - x0, BAR_H, 6, P.red_bg, P.red)
            self.band = c.create_image(
                x0, BAR_TOP, anchor="nw", image=self.band_image, state="hidden"
            )
        else:
            self.band = c.create_rectangle(
                x0, BAR_TOP, x1, BAR_TOP + BAR_H,
                fill=P.red_bg, outline=P.red, state="hidden",
            )
        cy = BAR_TOP + BAR_H // 2
        self.err_dot = c.create_oval(
            x0 + 10, cy - 3, x0 + 16, cy + 3, fill=P.red, width=0, state="hidden"
        )
        self.err_text = c.create_text(
            x0 + 23, cy, text="", anchor="w", fill=P.red, font=F_ERR, state="hidden"
        )
        self.err_stamp = c.create_text(
            x1 - 10, cy, text="", anchor="e", fill=P.red_dim,
            font=F_SMALL, state="hidden",
        )

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._ok_stamp = stamp  # 값이 언제 것인지 — 오류 띠에서도 이걸 쓴다
        p = pace(usage)
        self.five.set(usage.five.pct, usage.five.left)
        self.week.set(usage.week.pct, usage.week.left, p.due if p else None)
        self._error(None, stamp)
        self._foot(stamp, usage)

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        if not keep_values:
            self.five.set(None, "")
            self.week.set(None, "")
            self._foot(stamp, None)
            self._ok_stamp = ""
        self._error(text, stamp)

    # -------------------------------------------------- 꼬리말 두 얼굴
    def _foot(self, stamp: str, usage: Usage | None) -> None:
        c = self.c
        c.itemconfigure(self.stamp, text=f"{stamp} 기준" if stamp else "")

        text = scoped_text(usage, 1) if usage is not None else ""
        c.itemconfigure(self.scoped, text=text)
        pcts = [s.pct for s in usage.scoped if s.pct is not None] if usage else []
        box = c.bbox(self.scoped) if text and pcts else None
        if box is None:
            c.itemconfigure(self.dot, state="hidden")
            return
        c.coords(self.dot, box[0] - 12, Y_FOOT - 3, box[0] - 6, Y_FOOT + 3)
        c.itemconfigure(self.dot, fill=tone(pcts[0]), state="normal")

    def _error(self, text: str | None, stamp: str) -> None:
        c = self.c
        on, off = ("normal", "hidden") if text else ("hidden", "normal")
        for item in (self.band, self.err_dot, self.err_text, self.err_stamp):
            c.itemconfigure(item, state=on)
        for item in (self.line, self.stamp, self.scoped):
            c.itemconfigure(item, state=off)
        if text:
            c.itemconfigure(self.err_text, text=text)
            # 화면에 남은 값이 언제 것인지를 보여야 한다. 실패한 시각을 '기준' 이라고
            # 쓰면, 옛 숫자를 띄워 놓고 방금 잰 것처럼 말하는 셈이 된다.
            shown = f"{self._ok_stamp} 기준" if self._ok_stamp else stamp
            c.itemconfigure(self.err_stamp, text=shown)
            c.itemconfigure(self.dot, state="hidden")
