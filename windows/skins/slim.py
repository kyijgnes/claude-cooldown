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

from cooldown_core import Usage, five_due, pace

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
MASCOT_U = 2    # 도트 한 칸 (px). 팔까지 가로 11칸(22px) · 세로 8칸(16px)
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
HIT_R = 15            # 이 반경 안을 누르면 '직접 찌름'으로 본다 (px — 도트 그림 크기에 맞춤)
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


# ---------------------------------------------------------------- 마스코트 도트 그림
# 클로디는 **도트(픽셀) 그림**이다. 한 칸이 MASCOT_U px 인 격자에 네모만 찍어 그리므로
# 20~30px 에서도 획이 뭉개지지 않는다. 좌표는 전부 '몇 번째 칸'(col, row)이고,
# 실제 픽셀 변환은 `_sprite` 한 곳에서만 한다.
#
#   col: 0..8 이 머리(가로 9칸), 그 밖 -1 / 9 가 팔이 뻗는 자리
#   row: 0..5 가 머리, 6·7 이 다리와 발
#
# **몸통도 입도 없다** — 큰 머리에 짧은 팔 둘·다리 둘만 붙은 친구.
# 표정은 **눈으로만** 낸다(옛 클로디도 눈이 얼굴의 거의 전부였다).
#
# ★ 머리는 **9칸**이라야 한다. 7칸으로 줄이면 눈 구멍 둘이 살을 다 먹어 머리가
#   가로로 갈라져 보인다(게 집게처럼). 눈 옆·사이에 살이 남아야 얼굴로 읽힌다.
# ★ 팔은 **눈 아래**에서 나간다. 눈 높이에 걸치면 수염처럼 보인다.
HEAD = (
    "..#####..",   # 0 머리 위 (모서리 깎음)
    ".#######.",   # 1
    "#########",   # 2 눈
    "#########",   # 3 눈
    "#########",   # 4 팔이 여기서 옆으로
    ".#######.",   # 5 턱
)
LEGS = ("..#...#..", ".##...##.")       # 평소 — 다리 둘에 발
LEGS_WIDE = (".#.....#.", "##.....##")  # 기절 — 다리가 벌어져 주저앉는다

# 팔은 **한 칸**이다(짧게). **왼팔 기준**이고 오른팔은 좌우로 뒤집어 쓴다(`8 - col`).
# -1 번쩍 / 0 옆으로 / 1 축 늘어뜨림
# ★ 팔 칸은 **그 줄의 머리 끝에 닿아야** 한다. 안 그러면 한 칸 떨어져 떠 보인다
#   (줄마다 머리 폭이 달라서 팔이 내려갈수록 안쪽 칸으로 붙는다).
ARM = {
    -1: ((-1, 3),),
    0: ((-1, 4),),
    1: ((0, 5),),
}

# 눈은 바탕색으로 파낸 칸이다 (오류 시 붉은 바탕에서도 얼굴이 남는다).
EYES = {
    "idle": ((2, 2), (3, 2), (2, 3), (3, 3), (5, 2), (6, 2), (5, 3), (6, 3)),
    "blink": ((2, 3), (3, 3), (5, 3), (6, 3)),                     # — —
    # 눈웃음은 **넓고 낮은 띠**(가늘게 뜬 눈)다. ∧ 모양을 칸으로 찍으면 이 크기에선
    # 떨어진 점 셋으로 보여 얼굴이 아니라 얼룩이 된다.
    "grin": ((1, 3), (2, 3), (3, 3), (5, 3), (6, 3), (7, 3)),
    "surprise": ((1, 2), (2, 2), (3, 2), (1, 3), (2, 3), (3, 3),   # 크게 뜬 눈
                 (5, 2), (6, 2), (7, 2), (5, 3), (6, 3), (7, 3)),
    "faint": ((1, 2), (3, 2), (2, 3), (1, 4), (3, 4),              # X_X
              (5, 2), (7, 2), (6, 3), (5, 4), (7, 4)),
}

SPRITE_H = (len(HEAD) + len(LEGS)) * MASCOT_U   # 도트 그림 전체 높이 (px)


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
        self._start_mascot()  # 코랄 도트 마스코트 — 통통 튀고 눌리면 폴짝

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

    # -------------------------------------------------- 마스코트 '클로디' (도트 캐릭터)
    # 슬림 바에 사는 코랄색 도트 친구 — 몸통 없이 큰 머리에 팔 둘·다리 둘.
    # 통통 튀고, 이따금 손을 흔들고, 누르면 팔을 번쩍 들고 놀라고, 많이 누르면 기절한다.
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
        self._wave = 0                # 손 흔들기 남은 프레임
        self._look_dir = self._tilt_dir = self._wave_dir = 1
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
        # 창 밖으로 안 튀게 — 도트 그림 높이를 빼고 남는 만큼만 올라간다
        lift = max(4.0, (self.h - SPRITE_H) / 2 - 1)
        self._yoff = max(-lift, min(lift * 0.65, self._yoff + self._vy))
        self._vr += -SPRING_K * self._roff
        self._vr *= 1 - SPRING_DAMP
        self._roff += self._vr
        if self._surprise > 0:
            self._surprise -= 1
        if self._clicks > 0:  # 눌림 누적은 서서히 식는다
            self._clicks = max(0.0, self._clicks - CLICK_DECAY)

    # -------------------------------------------------- 심심할 때 하는 잔동작
    def _idle_step(self) -> None:
        """쉬는 동안 이따금 딴짓을 시킨다 — 손 흔들기·눈 굴리기·고개 갸웃·기지개·
        부르르·반짝이 뿜기·가끔 폴짝. 한 번에 하나씩만, 반응(눌림)으로 출렁일 땐 쉰다."""
        # 뿜은 반짝이 갱신 (위로 떠오르며 사그라든다)
        if self._sparks:
            for s in self._sparks:
                s[1] += s[2]; s[2] += 0.015; s[3] -= 1  # y+=vy, 서서히 처지고, 수명--
            self._sparks = [s for s in self._sparks if s[3] > 0]
        for key in ("_blink", "_look", "_tilt", "_stretch", "_wiggle", "_wave"):
            v = getattr(self, key)
            if v > 0:
                setattr(self, key, v - 1)
        busy = (self._blink or self._look or self._tilt or self._stretch
                or self._wiggle or self._wave)
        moving = abs(self._vy) + abs(self._yoff) > 0.8
        self._next_gesture -= 1
        if self._next_gesture <= 0 and not busy and not moving:
            self._begin_gesture()
            self._next_gesture = random.randint(30, 100)  # 다음 딴짓까지 1.4~4.5초

    def _begin_gesture(self) -> None:
        g = random.choice(
            ("blink", "blink", "wave", "wave", "look", "tilt",
             "stretch", "wiggle", "sparkle", "hop")
        )
        if g == "blink":
            self._blink = 3
        elif g == "wave":  # 손 흔들기 — 한 팔을 네 프레임마다 올렸다 내린다
            self._wave = 24; self._wave_dir = random.choice((-1, 1))
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
                [self.mascot_cx + random.uniform(-3, 3),
                 self.h / 2 - 4.5 * MASCOT_U, -0.55, 16]
            )
        elif g == "hop":
            self._vy -= JUMP_IMPULSE * 0.7  # 혼자 살짝 폴짝

    def _draw_mascot(self) -> None:
        """매 프레임 지우고 다시 그린다. 평소엔 숨쉬듯 잔잔히 + 이따금 잔동작,
        누르면 팔을 번쩍 들고 출렁이며 눈웃음/놀람, 기절하면 X_X + 별이 뱅뱅."""
        c = self.c
        c.delete("mascot")
        if self._faint > 0:
            self._draw_faint(c, self.mascot_cx, c.cget("bg"))
            return
        t = self._t

        # --- 잔동작에서 오는 보정값들 ---
        eye_dx = 0  # 눈 굴리기는 **칸 단위**로 옮긴다 (도트가 흐려지지 않게)
        if self._look:
            pr = 1 - self._look / 26
            eye_dx = self._look_dir if math.sin(pr * math.pi) > 0.5 else 0
        tilt = 0.0
        if self._tilt:  # 고개 갸웃 — 기울였다 돌아온다
            pr = 1 - self._tilt / 34
            tilt = self._tilt_dir * 0.42 * math.sin(pr * math.pi)
        sxk = syk = 1.0
        stretch = 0.0
        if self._stretch:  # 기지개 — 위로 쭉 늘었다 준다 (팔도 번쩍)
            stretch = math.sin((1 - self._stretch / 22) * math.pi)
            syk = 1 + 0.24 * stretch; sxk = 1 - 0.10 * stretch
        wig = 0.0
        if self._wiggle:  # 부르르 — 빠르게 좌우로 떨었다 잦아든다
            wig = 0.5 * (self._wiggle / 16) * math.sin(self._wiggle * 1.7)

        spring_scale = 1.0 + max(0.0, -self._yoff) * 0.02  # 위로 뜰수록 살짝 커짐
        breathe = 1 + 0.045 * math.sin(t * 0.09)           # 숨쉬듯 부풀락
        sxk *= spring_scale * breathe
        syk *= spring_scale * breathe
        cy = self.h / 2 + math.sin(t * 0.12) * 1.1 + self._yoff   # 잔잔한 통통 + 용수철
        lean = math.sin(t * 0.05) * 0.10 + self._roff + tilt + wig
        speed = abs(self._vy) + abs(self._yoff)                   # 출렁이는 중이면 신났다

        # 표정과 팔 — 콕 찔리면 놀라 만세, 출렁이면 눈웃음, 기지개도 만세
        if self._surprise > 0:
            expr, arms = "surprise", (-1, -1)
        elif speed > 1.2:
            expr, arms = "grin", (-1, -1)
        elif self._blink > 0:
            expr, arms = "blink", (0, 0)
        elif stretch > 0.5:
            expr, arms = "idle", (-1, -1)
        elif self._wave:  # 손 흔들기 — 한 팔만 번쩍, 그 팔이 오르내린다
            up = (self._wave // 4) % 2 == 0
            expr = "grin"
            arms = (-1 if up else 0, 0) if self._wave_dir < 0 else (0, -1 if up else 0)
        else:
            expr, arms = "idle", (0, 0)

        self._sprite(expr, arms, LEGS, self.mascot_cx, cy,
                     MASCOT_U * sxk, MASCOT_U * syk, lean, eye_dx)
        self._draw_sparks(c)

    def _sprite(self, expr: str, arms: tuple[int, int], legs: tuple[str, ...],
                cx: float, cy: float, ux: float, uy: float,
                lean: float = 0.0, eye_dx: int = 0) -> None:
        """도트 그림 한 장. 칸 경계를 같은 식으로 계산하므로 확대·기울임에도 틈이 안 생긴다.

        `lean` 은 기울임 — 위쪽 줄일수록 옆으로 더 미는 **계단식**이라 도트 결이 유지된다
        (도형을 돌리면 이 크기에서 획이 뭉개진다).
        """
        c = self.c
        bg = c.cget("bg")
        mid = (len(HEAD) + len(legs)) / 2
        x0 = cx - 4.5 * ux   # 머리 9칸의 왼쪽
        y0 = cy - mid * uy   # 머리 7줄 + 다리 2줄의 맨 위

        def cell(col: float, row: float, color: str, span: int = 1) -> None:
            x = x0 + col * ux + lean * (mid - row) * uy
            y = y0 + row * uy
            c.create_rectangle(x, y, x + span * ux, y + uy,
                               fill=color, width=0, tags="mascot")

        def paint(lines: tuple[str, ...], top: int) -> None:
            """줄마다 이어진 칸을 **한 덩이로** 그린다 — 매 프레임 도형 수를 3분의 1로.
            경계 식이 낱칸과 같으므로 그림은 한 픽셀도 안 달라진다."""
            for r, line in enumerate(lines):
                col = 0
                while col < len(line):
                    if line[col] != "#":
                        col += 1
                        continue
                    run = 1
                    while col + run < len(line) and line[col + run] == "#":
                        run += 1
                    cell(col, top + r, MASCOT_COLOR, run)
                    col += run

        for col, row in ARM[arms[0]]:            # 왼팔
            cell(col, row, MASCOT_COLOR)
        for col, row in ARM[arms[1]]:            # 오른팔 — 좌우 뒤집기
            cell(8 - col, row, MASCOT_COLOR)
        paint(HEAD, 0)
        paint(legs, len(HEAD))
        for col, row in EYES[expr]:
            cell(col + eye_dx, row, bg)

    def _draw_sparks(self, c: tk.Canvas) -> None:
        """뿜은 반짝이 — 도트답게 작은 십자(칸 다섯)로 떠오르며 사그라든다."""
        for sx, sy, _vy, life in self._sparks:
            u = MASCOT_U * 0.6 * (life / 16)
            if u < 0.7:
                continue
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                x, y = sx + dx * u, sy + dy * u
                c.create_rectangle(x - u / 2, y - u / 2, x + u / 2, y + u / 2,
                                   fill=MASCOT_COLOR, width=0, tags="mascot")

    def _draw_faint(self, c: tk.Canvas, cx: int, bg: str) -> None:
        """기절 — 크게 부풀려 주저앉고(다리가 벌어진다), X_X 눈에 팔은 축 늘어진다.
        작아서 눈이 안 보이던 걸 FAINT_SCALE 로 키워 X 를 확실히 보이게 한다."""
        t = self._t
        u = MASCOT_U * FAINT_SCALE
        cy = self.h / 2 + 2.0 + math.sin(t * 0.25) * 0.6  # 살짝 처져 흐느적
        lean = math.sin(t * 0.2) * 0.20                   # 어질어질 크게 흔들
        self._sprite("faint", (1, 1), LEGS_WIDE, cx, cy, u, u, lean)
        # 어질어질 별 세 개가 머리 위를 돈다 (역시 도트 십자)
        oy = cy - 4.6 * u
        for i in range(3):
            a = t * 0.35 + i * (math.pi * 2 / 3)
            sx = cx + math.cos(a) * 8.0
            sy = oy + math.sin(a) * 2.4
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                x, y = sx + dx * 2.0, sy + dy * 2.0
                c.create_rectangle(x - 1, y - 1, x + 1, y + 1,
                                   fill=P.amber, width=0, tags="mascot")

    # -------------------------------------------------- 바탕 두 얼굴
    def _paint(self, bg: str, accent: str) -> None:
        self.c.configure(bg=bg)
        self.c.itemconfigure(self.accent, fill=accent)

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._paint(P.bg, tone(worst(usage)))
        p = pace(usage)
        self.five.set(usage.five.pct, usage.five.left, five_due(usage))
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

    def notice(self, text: str) -> None:
        # 값은 멀쩡한데 알릴 것(자동 시작 놓침)을 오른쪽 윗자리(모델별 자리)에 호박색으로.
        # show() 가 그 자리에 모델별을 채운 직후 앱이 부른다 — 빈 문자열이면 그대로 둔다.
        # 자리가 좁아 시각을 앞세운 문구를 _clip(뒤를 자름)으로 넣어 시각이 남게 한다.
        if not text:
            return
        self.c.itemconfigure(
            self.model, text=_clip(text, self.f_small, self.right_w), fill=P.amber
        )
        self.c.itemconfigure(self.msg, text="")
