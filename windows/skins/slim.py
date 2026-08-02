"""
초슬림 바 — 작업표시줄에 얹거나 화면 가장자리에 붙여 두는 낮고 긴 띠.
**창 높이를 작업표시줄 높이에 맞춘다** (기본 48px, 설정·배율에 따라 달라지는 값을 실측).
두 칸(5시간·주간)에 숫자와 눈금 게이지를 넣고, 오른쪽 끝에 모델별·기준 시각을 둔다.
왼쪽 세로 띠는 두 한도 중 더 급한 쪽 색. 오류일 때는 띠와 바탕이 빨강으로 바뀌고
모델별 자리에 상태 문구가 대신 들어간다 (자리를 새로 만들지 않으므로 높이는 그대로).

    ┃ 5시간 17%   4시간 12분 후 │ 주간 56%   2일 07시간 후 │ Fable 7%
    ┃ ▪▪▪▪▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫     │ ▪▪▪▪▪▪▪▪▪▪▪▫▫▫▫┃▫▫▫▫▫     │ 03:07 기준

주간 게이지의 ┃ 는 '지금쯤' 눈금 — 주간 창이 흐른 만큼의 자리다. 채운 색이 눈금을
앞질렀으면 그만큼 빨리 쓰는 중. 숫자·판정은 우클릭 > 이번 주 사용 속도 에서 본다.

폭은 "100%" · "6일 23시간 후" 같은 최대 길이 문자열을 실제 글꼴로 재서 칸을 나눈다.
창 폭(width)은 고정이라 그 최악 케이스가 들어가도록 넉넉히 잡았고, 남는 글자는 … 로 줄인다.
"""

from __future__ import annotations

import math
import random
import tkinter as tk
from tkinter import font as tkfont

from cooldown_core import Usage, pace

from .base import (
    KR,
    MARK_W,
    NUM,
    P,
    Skin,
    mark_x,
    scoped_text,
    taskbar_height,
    tone,
    worst,
)

# ---------------------------------------------------------------- 치수
# 세로 배치는 작업표시줄 높이에서 계산한다 (build 참고). 가로만 여기서 고정.
# 왼쪽 끝엔 상태 띠(accent, 한도 색). 마스코트는 **주간 칸과 오른쪽(모델/기준) 사이
# 빈 틈(MGAP)** 에 앉는다 — 그 자리를 미리 비워 두므로 긴 모델명이 와도 안 겹친다.
# 마스코트는 상태와 무관하게 클로드 코랄색으로 고정 — 상태는 띠가 맡는다.
ACC = 4  # 왼쪽 상태 띠 (한도 색)
PAD_L = ACC + 12  # 내용 시작 (띠 뒤)
PAD_R = 14
MGAP = 46  # 주간 칸 ↔ 오른쪽 사이의 넓힌 틈 — 여기 가운데에 마스코트를 앉힌다
MASCOT_R = 10   # 별빛 반지름 (px) — 기본 크기
MASCOT_COLOR = "#d97757"  # 클로드 코랄 — 밝게/어둡게 양쪽에서 그대로 쓴다
FRAME_MS = 45  # 애니메이션 한 프레임 (약 22fps — 물리가 부드럽게 이어지게)
# 눌림 반응은 용수철처럼 — 누를 때마다 위로 튀는 '속도'를 더한다. 연타하면 힘이
# 쌓여 자연스럽게 출렁이고(뚝 끊기지 않고), 너무 많이 치면 기절한다.
JUMP_IMPULSE = 2.6    # 아무 데나 눌렀을 때 위로 튀는 속도
POKE_MULT = 1.8       # 마스코트를 직접 콕 찌르면 반응이 이만큼 커진다
SPIN_IMPULSE = 0.22   # 누를 때 좌우로 도는 힘 (부호를 번갈아 흔든다)
SPRING_K = 0.20       # 제자리로 당기는 용수철 세기
SPRING_DAMP = 0.14    # 감쇠 (0=계속 튐, 1=즉시 멈춤)
FAINT_AT = 30.0       # 직접 콕 찌른 게 이만큼 쌓여야 기절 (딴 데 클릭은 안 쌓임)
CLICK_DECAY = 0.12    # 눌림 누적이 프레임마다 이만큼 식는다
FAINT_FRAMES = 60     # 기절 지속 (약 2.7초)
FAINT_SCALE = 1.35    # 기절 땐 크게 부풀려 X_X 눈이 또렷이 보이게
SURPRISE_FRAMES = 7   # 직접 찔렸을 때 눈이 동그래지는 프레임 수
HIT_R = 13            # 이 반경 안을 누르면 '직접 찌름'으로 본다 (px)
GAP = 16  # 칸 사이
SEG_GAP = 2  # 눈금 사이
MARK_OUT = 2  # '지금쯤' 눈금이 게이지 위아래로 삐져나오는 길이
LV_GAP = 6  # 항목 이름 ↔ 숫자
VR_GAP = 10  # 숫자 ↔ 남은시간 최소 간격
LBL_BASE = 2  # 9pt 글자를 큰 숫자의 기준선에 맞추는 보정
SM_BASE = 3  # 8pt 글자 보정
ROW_GAP = 6  # 윗줄 ↔ 게이지

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
            x, skin.top_y + LBL_BASE, text=label, anchor="w",
            font=skin.f_label, fill=P.label,
        )
        self.vx = x + skin.f_label.measure(label) + LV_GAP
        self.value = self.c.create_text(
            self.vx, skin.top_y, text="--", anchor="w", font=self.f_value, fill=P.faint
        )
        self.left = self.c.create_text(
            x + w, skin.top_y + SM_BASE, text="", anchor="e",
            font=self.f_small, fill=P.sub,
        )

        count = max(8, w // 8)
        pitch = w / count
        seg_w = max(3.0, pitch - SEG_GAP)
        self.segs = [
            self.c.create_rectangle(
                x + i * pitch, skin.bar_y,
                x + i * pitch + seg_w, skin.bar_y + skin.bar_h,
                fill=P.track, width=0,
            )
            for i in range(count)
        ]

        # '지금쯤' 눈금 — 칸 사이 틈에 떨어져도 보이게 눈금들 **뒤에** 만들어(맨 위)
        # 위아래로 MARK_OUT 만큼 삐져나오게 긋는다. 안 쓸 땐 숨긴다.
        self.mark_y0 = skin.bar_y - MARK_OUT
        self.mark_y1 = skin.bar_y + skin.bar_h + MARK_OUT
        self.mark = self.c.create_rectangle(
            0, 0, 0, 0, fill=P.title, width=0, state="hidden"
        )

    def set(self, pct: float | None, left: str, due: float | None = None) -> None:
        color = tone(pct)
        value = "--" if pct is None else f"{pct:.0f}%"
        self.c.itemconfigure(self.value, text=value, fill=color)

        room = int(self.x + self.w - (self.vx + self.f_value.measure(value) + VR_GAP))
        self.c.itemconfigure(
            self.left,
            text=_clip(left, self.f_small, room),
            fill=P.sub if pct is not None else P.faint,
        )

        # 내림이라 꽉 찬 게이지는 100% 뿐이다. 값이 있으면 아무리 작아도 한 칸은 켠다.
        # (반올림이면 98~100%가 모두 꽉 참으로 보여 한도 소진 여부를 구분 못 한다.)
        n = len(self.segs)
        filled = 0 if not pct else max(1, min(n, int(pct * n / 100)))
        for i, seg in enumerate(self.segs):
            self.c.itemconfigure(seg, fill=color if i < filled else P.track)

        if due is None:
            self.c.itemconfigure(self.mark, state="hidden")
        else:
            x = self.x + mark_x(due, self.w)
            self.c.coords(self.mark, x, self.mark_y0, x + MARK_W, self.mark_y1)
            self.c.itemconfigure(self.mark, state="normal", fill=P.title)


# ---------------------------------------------------------------- 스킨
class SlimSkin(Skin):
    key = "slim"
    name = "슬림 바 (작업표시줄용)"
    width = 480
    dockable = True

    def build(self, parent: tk.Misc) -> None:
        self.f_label = tkfont.Font(parent, family=KR, size=9)
        self.f_value = tkfont.Font(parent, family=NUM, size=13, weight="bold")
        self.f_small = tkfont.Font(parent, family=KR, size=8)
        self.f_msg = tkfont.Font(parent, family=KR, size=9, weight="bold")

        # 창 높이를 작업표시줄에 맞추고, 그 안에서 세로 배치를 나눈다.
        # 작은 작업표시줄(40px)이든 고배율(60px 이상)이든 같은 비율로 앉는다.
        self.h = taskbar_height()
        row_h = self.f_value.metrics("linespace")
        self.bar_h = 6 if self.h >= 44 else 5
        slack = max(0, self.h - row_h - ROW_GAP - self.bar_h)
        top = slack * 45 // 100  # 위가 조금 좁아야 안정돼 보인다
        self.top_y = top + row_h // 2
        self.bar_y = top + row_h + ROW_GAP
        self.bar_cy = self.bar_y + self.bar_h // 2
        self.div_top = top
        self.div_bot = self.bar_y + self.bar_h

        self.c = tk.Canvas(
            parent, width=self.width, height=self.h, bg=P.bg,
            highlightthickness=0, bd=0,
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
        # 가로: [띠] 5시간칸 |GAP| 주간칸 |MGAP(마스코트)| 오른쪽칸.
        # 오른쪽 자리를 미리 확보하므로(right_w) 마스코트는 그 왼쪽 빈 틈에서만 논다.
        avail = self.width - PAD_L - PAD_R - GAP - MGAP
        self.right_w = min(need_right, max(60, avail - need_cell * 2))
        cell_w = (avail - self.right_w) // 2

        self.accent = self.c.create_rectangle(0, 0, ACC, self.h, fill=P.track, width=0)

        x1 = PAD_L
        x2 = PAD_L + cell_w + GAP
        rx = self.width - PAD_R
        self.five = Cell(self, x1, cell_w, "5시간")
        self.week = Cell(self, x2, cell_w, "주간")
        week_end = x2 + cell_w
        right_x0 = week_end + MGAP  # 오른쪽 칸(모델/기준) 왼쪽 경계
        # 구분선: 5시간|주간, 그리고 주간|마스코트틈 (오른쪽 칸은 마스코트가 가른다)
        for dx in (x1 + cell_w + GAP // 2, week_end + 7):
            self.c.create_line(dx, self.div_top, dx, self.div_bot, fill=P.line, width=1)

        # 마스코트는 그 구분선과 오른쪽 칸 사이 빈 틈 가운데에 앉는다
        self.mascot_cx = (week_end + 7 + right_x0) // 2
        self._start_mascot()  # 코랄 별빛 마스코트 — 통통 튀고 눌리면 폴짝

        # 오른쪽 윗자리 — 평소엔 모델별, 오류일 땐 상태 문구. 같은 자리를 나눠 쓴다.
        self.model = self.c.create_text(
            rx, self.top_y + SM_BASE, text="불러오는 중", anchor="e",
            font=self.f_small, fill=P.faint,
        )
        self.msg = self.c.create_text(
            rx, self.top_y + LBL_BASE, text="", anchor="e", font=self.f_msg, fill=P.red
        )
        self.stamp = self.c.create_text(
            rx, self.bar_cy, text="", anchor="e", font=self.f_small, fill=P.faint
        )

        self.five.set(None, "")
        self.week.set(None, "")

    # -------------------------------------------------- 마스코트 '클로디' (클로드 별빛)
    # 슬림 바에 사는 코랄색 별빛 캐릭터. 통통 튀고, 누르면 반응하고, 너무 많이
    # 누르면 기절한다. 이름은 '클로디'(Claudi — 클로드의 작은 별).
    def _start_mascot(self) -> None:
        """마스코트 애니메이션을 켠다. build 가 다시 불려도(테마 전환 등) 세대(gen)
        토큰으로 옛 루프를 은퇴시켜 두 루프가 겹치지 않게 한다."""
        self._t = 0
        self._yoff = self._vy = 0.0   # 상하 용수철(위치·속도)
        self._roff = self._vr = 0.0   # 좌우 흔들 용수철
        self._clicks = 0.0            # 직접 콕 누적 (식으면서 준다)
        self._faint = 0               # 기절 남은 프레임
        self._surprise = 0            # 직접 찔려 눈이 동그래진 프레임
        self._spin_dir = 1            # 누를 때 도는 방향 (번갈아)
        # 심심할 때 하는 잔동작들 — 한 번에 하나씩, 사이사이 쉰다
        self._blink = self._look = self._tilt = self._stretch = self._wiggle = 0
        self._look_dir = self._tilt_dir = 1
        self._sparks: list[list[float]] = []   # 뿜은 반짝이 [x, y, vy, life]
        self._next_gesture = random.randint(20, 60)
        self._anim_gen = getattr(self, "_anim_gen", 0) + 1
        self._draw_mascot()  # 첫 프레임은 바로 그린다
        self.c.after(FRAME_MS, lambda c=self.c, g=self._anim_gen: self._animate(c, g))

    def _hit(self, x: float, y: float) -> bool:
        """누른 자리가 마스코트 위인가 (직접 콕 찌름)."""
        dx = x - self.mascot_cx
        dy = y - self.h / 2
        return dx * dx + dy * dy <= HIT_R * HIT_R

    def react(self, x: float | None = None, y: float | None = None) -> None:
        """눌렀을 때 반응. 좌표로 **마스코트를 직접 찔렀는지** 보고 다르게 논다:
        직접 찌르면 크게 놀라 펄쩍(눈 동그래짐)·많이 찌르면 기절.
        **딴 데 클릭은 잔잔히 통통만 하고 기절엔 안 쌓인다.**"""
        if self._faint > 0:
            return
        if x is not None and self._hit(x, y):  # 콕! — 크게 놀란다
            self._vy -= JUMP_IMPULSE * POKE_MULT
            self._vr += SPIN_IMPULSE * 1.8 * self._spin_dir
            self._surprise = SURPRISE_FRAMES
            self._clicks += 2.0  # 직접 찌른 것만 지치게 한다
            if self._clicks >= FAINT_AT:  # 과부하 — 뻗는다
                self._faint = FAINT_FRAMES
                self._clicks = 0.0
                self._surprise = 0
        else:  # 딴 데 — 잔잔히 통통 (기절과 무관)
            self._vy -= JUMP_IMPULSE
            self._vr += SPIN_IMPULSE * self._spin_dir
        self._spin_dir = -self._spin_dir

    def _animate(self, canvas: tk.Canvas, gen: int) -> None:
        if gen != self._anim_gen:  # 새 build 가 시작됐다 — 이 루프는 은퇴
            return
        self._t += 1
        self._step_physics()
        if self._faint == 0:
            self._idle_step()
        try:
            self._draw_mascot()
        except tk.TclError:  # 캔버스가 사라졌다 (스킨/테마 전환)
            return
        canvas.after(FRAME_MS, lambda: self._animate(canvas, gen))

    def _step_physics(self) -> None:
        """용수철 한 걸음. 눌림으로 생긴 속도를 제자리(0)로 부드럽게 당긴다."""
        if self._faint > 0:  # 기절 중 — 서서히 늘어졌다가 깨어난다
            self._faint -= 1
            self._vy *= 0.8; self._yoff *= 0.85
            self._vr *= 0.9; self._roff *= 0.9
            if self._faint == 0:  # 깨어남 — 말끔히 리셋
                self._yoff = self._vy = self._roff = self._vr = 0.0
            return
        self._vy += -SPRING_K * self._yoff
        self._vy *= 1 - SPRING_DAMP
        self._yoff = max(-14.0, min(9.0, self._yoff + self._vy))  # 화면 밖으로 안 튀게
        self._vr += -SPRING_K * self._roff
        self._vr *= 1 - SPRING_DAMP
        self._roff += self._vr
        if self._surprise > 0:
            self._surprise -= 1
        if self._clicks > 0:  # 눌림 누적은 서서히 식는다
            self._clicks = max(0.0, self._clicks - CLICK_DECAY)

    # -------------------------------------------------- 심심할 때 하는 잔동작
    def _idle_step(self) -> None:
        """쉬는 동안 이따금 딴짓을 시킨다 — 눈 굴리기·고개 갸웃·기지개·부르르·
        반짝이 뿜기·가끔 폴짝. 한 번에 하나씩만, 반응(눌림)으로 출렁일 땐 쉰다."""
        # 뿜은 반짝이 갱신 (위로 떠오르며 사그라든다)
        if self._sparks:
            for s in self._sparks:
                s[1] += s[2]; s[2] += 0.015; s[3] -= 1  # y+=vy, 서서히 처지고, 수명--
            self._sparks = [s for s in self._sparks if s[3] > 0]
        for key in ("_blink", "_look", "_tilt", "_stretch", "_wiggle"):
            v = getattr(self, key)
            if v > 0:
                setattr(self, key, v - 1)
        busy = self._blink or self._look or self._tilt or self._stretch or self._wiggle
        moving = abs(self._vy) + abs(self._yoff) > 0.8
        self._next_gesture -= 1
        if self._next_gesture <= 0 and not busy and not moving:
            self._begin_gesture()
            self._next_gesture = random.randint(30, 100)  # 다음 딴짓까지 1.4~4.5초

    def _begin_gesture(self) -> None:
        g = random.choice(
            ("blink", "blink", "look", "tilt", "stretch", "wiggle", "sparkle", "hop")
        )
        if g == "blink":
            self._blink = 3
        elif g == "look":
            self._look = 26; self._look_dir = random.choice((-1, 1))
        elif g == "tilt":
            self._tilt = 34; self._tilt_dir = random.choice((-1, 1))
        elif g == "stretch":
            self._stretch = 22
        elif g == "wiggle":
            self._wiggle = 16
        elif g == "sparkle":
            self._sparks.append(
                [self.mascot_cx + random.uniform(-3, 3), self.h / 2 - MASCOT_R, -0.55, 16]
            )
        elif g == "hop":
            self._vy -= JUMP_IMPULSE * 0.7  # 혼자 살짝 폴짝

    def _draw_mascot(self) -> None:
        """매 프레임 지우고 다시 그린다. 평소엔 숨쉬듯 잔잔히 + 이따금 잔동작,
        누르면 출렁이며 눈웃음/놀람, 기절하면 X_X + 별이 뱅뱅."""
        c = self.c
        c.delete("mascot")
        bg = c.cget("bg")
        if self._faint > 0:
            self._draw_faint(c, self.mascot_cx, bg)
            return
        t = self._t
        cx = self.mascot_cx

        # --- 잔동작에서 오는 보정값들 ---
        eye_dx = 0.0
        if self._look:  # 눈(과 고개)을 한쪽으로 굴렸다 돌아온다
            pr = 1 - self._look / 26
            eye_dx = self._look_dir * 2.3 * math.sin(pr * math.pi)
        tilt = 0.0
        if self._tilt:  # 고개 갸웃 — 기울였다 돌아온다
            pr = 1 - self._tilt / 34
            tilt = self._tilt_dir * 0.42 * math.sin(pr * math.pi)
        sxk = syk = 1.0
        if self._stretch:  # 기지개 — 위로 쭉 늘었다 준다
            e = math.sin((1 - self._stretch / 22) * math.pi)
            syk = 1 + 0.24 * e; sxk = 1 - 0.13 * e
        wig = 0.0
        if self._wiggle:  # 부르르 — 빠르게 좌우로 떨었다 잦아든다
            wig = 0.5 * (self._wiggle / 16) * math.sin(self._wiggle * 1.7)

        spring_scale = 1.0 + max(0.0, -self._yoff) * 0.02  # 위로 뜰수록 살짝 커짐
        breathe = 1 + 0.045 * math.sin(t * 0.09)           # 숨쉬듯 부풀락
        sxk *= spring_scale * breathe
        syk *= spring_scale * breathe
        cy = self.h / 2 + math.sin(t * 0.12) * 1.1 + self._yoff   # 잔잔한 통통 + 용수철
        sway = math.sin(t * 0.05) * 0.22 + self._roff + tilt + wig
        speed = abs(self._vy) + abs(self._yoff)                   # 출렁이는 중이면 신났다

        self._rays(c, cx, cy, sway, t, sxk, syk)
        brx = MASCOT_R * 0.62 * sxk  # 통통한 몸통
        bry = MASCOT_R * 0.62 * syk
        c.create_oval(cx - brx, cy - bry, cx + brx, cy + bry, fill=MASCOT_COLOR, width=0, tags="mascot")

        # 뿜은 반짝이 (몸에서 떠오르며 작아진다)
        for s in self._sparks:
            r = 1.7 * (s[3] / 16)
            if r < 0.4:
                continue
            c.create_line(s[0] - r, s[1], s[0] + r, s[1], fill=MASCOT_COLOR,
                          width=1.3, capstyle="round", tags="mascot")
            c.create_line(s[0], s[1] - r, s[0], s[1] + r, fill=MASCOT_COLOR,
                          width=1.3, capstyle="round", tags="mascot")

        # 눈 — 바탕색으로 파낸다. 콕 찔리면 O O, 출렁이면 ∧∧, 깜빡이면 —, 굴리면 옆으로.
        # ★ 눈은 반짝임 점보다 확실히 커야 한다 — 비슷하면 이 크기에선 둘 다 '+' 로 뭉개져
        #   얼굴이 아니라 반짝임이 셋 있는 것처럼 보인다.
        er, ex, ey = 1.5, 2.4, cy - 1.4 * syk
        exL, exR = cx - ex + eye_dx, cx + ex + eye_dx
        if self._surprise > 0:  # O O — 직접 찔려 놀란 동그란 눈
            wr = 1.9
            for ecx in (exL, exR):
                c.create_oval(ecx - wr, ey - wr, ecx + wr, ey + wr, fill=bg, width=0, tags="mascot")
        elif speed > 1.2:  # ∧∧ 눈웃음 — 위로 볼록한 짧은 호
            for ecx in (exL, exR):
                c.create_arc(ecx - er - 0.4, ey - 0.2, ecx + er + 0.4, ey + er + 1.4,
                             start=20, extent=140, style="arc",
                             outline=bg, width=1.5, tags="mascot")
        elif self._blink > 0:  # — — 깜빡
            for ecx in (exL, exR):
                c.create_line(ecx - er, ey, ecx + er, ey,
                              fill=bg, width=1.7, capstyle="round", tags="mascot")
        else:
            for ecx in (exL, exR):
                c.create_oval(ecx - er, ey - er, ecx + er, ey + er, fill=bg, width=0, tags="mascot")

        self._mouth(c, cx, cy, syk, bg, grin=speed > 1.2, surprised=self._surprise > 0)

    def _rays(self, c: tk.Canvas, cx: float, cy: float, sway: float,
              t: float, sxk: float, syk: float, s: float = 1.0) -> None:
        """별빛 — **상하좌우 넷만 살**이고 대각선 넷은 떠 있는 점이다(폰 아이콘과 같은 결).

        예전엔 여덟 살을 길고 짧게 번갈아 뻗었는데, 이 크기에서 눈에 들어오는 건
        상하좌우 넷뿐이라 짧은 살은 팔다리처럼만 보였다. 점으로 바꾸니 반짝임이 산다.
        """
        for k in range(4):
            ang = math.pi / 2 * k - math.pi / 2 + sway
            rr = MASCOT_R * s * (1 + 0.10 * math.sin(t * 0.2 + k))   # 살짝 반짝
            c.create_line(
                cx, cy, cx + math.cos(ang) * rr * sxk, cy + math.sin(ang) * rr * syk,
                fill=MASCOT_COLOR, width=2, capstyle="round", tags="mascot",
            )
        for k in range(4):
            ang = math.pi / 2 * k - math.pi / 4 + sway
            dd = MASCOT_R * 1.02 * s * (1 + 0.10 * math.sin(t * 0.2 + k + 2))
            px = cx + math.cos(ang) * dd * sxk
            py = cy + math.sin(ang) * dd * syk
            r = 0.95 * s
            c.create_oval(px - r, py - r, px + r, py + r,
                          fill=MASCOT_COLOR, width=0, tags="mascot")

    def _mouth(self, c: tk.Canvas, cx: float, cy: float, syk: float, bg: str,
               grin: bool, surprised: bool) -> None:
        """작은 웃는 입. 놀라면 동그랗게, 신나면 크게 벌린다. 눈과 달리 굴리지 않는다."""
        my = cy + 1.6 * syk
        if surprised:
            r = 1.0
            c.create_oval(cx - r, my - r, cx + r, my + r, fill=bg, width=0, tags="mascot")
            return
        w, h = (2.2, 1.9) if grin else (1.9, 1.4)
        c.create_arc(cx - w, my - h, cx + w, my + h,
                     start=205, extent=130, style="arc",
                     outline=bg, width=1.3, tags="mascot")

    def _draw_faint(self, c: tk.Canvas, cx: int, bg: str) -> None:
        """기절 — 크게 부풀려 늘어지고, 또렷한 X_X 눈에, 별 세 개가 머리 위를 돈다.
        작아서 눈이 안 보이던 걸 FAINT_SCALE 로 키워 X 를 확실히 보이게 한다."""
        t = self._t
        s = FAINT_SCALE
        cy = self.h / 2 + 2.0 + math.sin(t * 0.25) * 0.6  # 살짝 처져 흐느적
        tilt = math.sin(t * 0.2) * 0.5                    # 어질어질 크게 흔들
        self._rays(c, cx, cy, tilt, t, 1.0, 1.0, s)
        br = MASCOT_R * 0.62 * s
        c.create_oval(cx - br, cy - br, cx + br, cy + br, fill=MASCOT_COLOR, width=0, tags="mascot")
        # X_X 눈 — 바탕색 십자, 큼직하고 도톰하게
        ex, ey, es = 2.7, cy - 1.4, 2.0
        for sx in (-ex, ex):
            c.create_line(cx + sx - es, ey - es, cx + sx + es, ey + es,
                          fill=bg, width=2.0, capstyle="round", tags="mascot")
            c.create_line(cx + sx - es, ey + es, cx + sx + es, ey - es,
                          fill=bg, width=2.0, capstyle="round", tags="mascot")
        # 어질어질 별 세 개가 머리 위를 돈다
        oy = cy - MASCOT_R * s - 3
        for i in range(3):
            a = t * 0.35 + i * (math.pi * 2 / 3)
            sx = cx + math.cos(a) * 7.0
            sy = oy + math.sin(a) * 2.2
            r = 2.1
            c.create_line(sx - r, sy, sx + r, sy, fill=P.amber, width=1.4, capstyle="round", tags="mascot")
            c.create_line(sx, sy - r, sx, sy + r, fill=P.amber, width=1.4, capstyle="round", tags="mascot")

    # -------------------------------------------------- 바탕 두 얼굴
    def _paint(self, bg: str, accent: str) -> None:
        self.c.configure(bg=bg)
        self.c.itemconfigure(self.accent, fill=accent)

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._paint(P.bg, tone(worst(usage)))
        p = pace(usage)
        self.five.set(usage.five.pct, usage.five.left)
        self.week.set(usage.week.pct, usage.week.left, p.due if p else None)

        text = scoped_text(usage, 1)
        self.c.itemconfigure(
            self.model, text=_fit(text, self.f_small, self.right_w), fill=P.label
        )
        self.c.itemconfigure(self.msg, text="")
        self.c.itemconfigure(self.stamp, text=f"{stamp} 기준")

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        # 기준 시각은 오류일수록 중요하다 — 붉게 죽이지 않고 P.faint 그대로 둔다.
        self._paint(P.red_bg, P.red)
        self.c.itemconfigure(self.model, text="")
        self.c.itemconfigure(self.msg, text=_clip(text, self.f_msg, self.right_w))
        if not keep_values:
            self.five.set(None, "")
            self.week.set(None, "")
            self.c.itemconfigure(self.stamp, text=stamp)
