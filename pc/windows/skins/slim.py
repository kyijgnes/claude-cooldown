"""
초슬림 바 — 작업표시줄에 얹거나 화면 가장자리에 붙여 두는 낮고 긴 띠.
**창 높이를 작업표시줄 높이에 맞춘다** (기본 48px, 설정·배율에 따라 달라지는 값을 실측).
두 칸(5시간·주간)에 숫자와 눈금 게이지를 넣고, 오른쪽 끝에 번갈아 칸과 상태 점을 둔다.
왼쪽 세로 띠는 두 한도 중 더 급한 쪽 색. 오류일 때는 띠와 바탕이 빨강으로 바뀌고
번갈아 칸에 상태 문구가 대신 들어간다 (자리를 새로 만들지 않으므로 높이는 그대로).

    ┃ 5시간 17%   4시간 12분 후 │ 주간 56%   2일 07시간 후 │  Fable 7% ●
    ┃ ▪▪▪▪▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫▫     │ ▪▪▪▪▪▪▪▪▪▪▪▫▫▫▫┃▫▫▫▫▫     │

주간 게이지의 ┃ 는 '지금쯤' 눈금 — 주간 창이 흐른 만큼의 자리다. 채운 색이 눈금을
앞질렀으면 그만큼 빨리 쓰는 중. 숫자·판정은 우클릭 > 이번 주 사용 속도 에서 본다.

오른쪽 끝 두 가지:
- **번갈아 칸** — 한 줄뿐인데 보여 줄 것이 여럿이라 하나씩 바꿔 띄운다(모델별 한도 ·
  알림 · 오류). 칸보다 긴 글자는 **좌우로 훑어(pan)** 끝까지 보여 준다. 그래서 칸 자체는
  좁아도 된다 — 창 폭을 460 까지 줄인 근거다. **글자는 게이지 아래끝에 맞춰 아래 정렬.**
  ★ 훑는 글자가 옆 칸을 침범하지 않게, 이 칸만 **따로 캔버스**(`self.slot`)로 만들어
    거기 담는다. tk 캔버스는 제 테두리에서 잘라 주므로 이게 유일하게 깔끔한 길이다
    (한 캔버스에 그리면 도형 단위 클리핑이 없어 마스코트·게이지 위로 글자가 흘러넘친다).
- **상태 점** — 오른쪽 위 구석. 마지막 조회가 됐으면 초록, 안 됐으면 빨강. 옛 '03:07 기준'
  자리를 대신한다(시각은 작업표시줄 시계에 있으니 지금 것인지만 알면 된다).
  ★ 점 자체는 **앱이 그린다**(`status_spot()` 으로 자리만 알려 준다) — 새로고침 스피너가
    같은 자리에서 그 둘레를 도는 링이라, 둘을 한 캔버스에 두어야 겹쳐도 조화롭다.

폭은 "100%" · "6일 23시간 후" 같은 최대 길이 문자열을 실제 글꼴로 재서 칸을 나눈다.
두 한도 칸이 제 몫을 먼저 가져가고, 번갈아 칸은 남는 만큼만 쓴다(모자라면 훑는다).
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
    taskbar_height,
    tone,
    worst,
)
from .claudi import Claudi

# ---------------------------------------------------------------- 치수
# 세로 배치는 작업표시줄 높이에서 계산한다 (build 참고). 가로만 여기서 고정.
# 왼쪽 끝엔 상태 띠(accent, 한도 색). 마스코트는 **주간 칸과 오른쪽(모델/기준) 사이
# 빈 틈(MGAP)** 에 앉는다 — 그 자리를 미리 비워 두므로 긴 모델명이 와도 안 겹친다.
# 마스코트는 상태와 무관하게 클로드 코랄색으로 고정 — 상태는 띠가 맡는다.
ACC = 4  # 왼쪽 상태 띠 (한도 색)
PAD_L = ACC + 12  # 내용 시작 (띠 뒤)
PAD_R = 10
# 주간 칸 ↔ 번갈아 칸 사이의 틈 — 여기 가운데에 마스코트가 앉는다.
# ★ **42 보다 줄이지 말 것** — 마스코트는 팔까지 11칸(22px)인데 숨쉬기·기지개로
#   부풀고 계단식 기울임으로 윗줄이 옆으로 밀려, 실제로는 30px 남짓 쓴다.
MGAP = 42
# 상태 점(과 그 둘레를 도는 새로고침 링)이 앉는 오른쪽 위 구석. 앱이 그리므로 자리만 잡는다.
DOT_INSET = 12
MIN_SLOT = 52  # 번갈아 칸이 아무리 좁아도 이만큼은 준다 (그 아래는 훑어도 못 읽는다)
GAP = 16  # 칸 사이
SEG_GAP = 2  # 눈금 사이
MARK_OUT = 2  # '지금쯤' 눈금이 게이지 위아래로 삐져나오는 길이
LV_GAP = 6  # 항목 이름 ↔ 숫자
VR_GAP = 10  # 숫자 ↔ 남은시간 최소 간격
LBL_BASE = 2  # 9pt 글자를 큰 숫자의 기준선에 맞추는 보정
SM_BASE = 3  # 8pt 글자 보정
ROW_GAP = 6  # 윗줄 ↔ 게이지

# ---------------------------------------------------------------- 번갈아 뜨는 칸
# 오른쪽 자리는 한 줄인데 보여 줄 것은 여럿이다(모델별 한도 · 주간 적정선 · 알림 · 오류).
# 그래서 하나씩 번갈아 띄운다 — 보여 주던 것이 위로 밀리며 바탕색에 스며들고,
# 다음 것이 아래에서 떠오른다. **칸보다 긴 글자는 좌우로 훑어** 끝까지 보여 준다.
SLOT_HOLD = 4200  # 한 가지를 보여 주는 시간 (ms). 훑는 것은 훑는 시간이 더해진다.
SLOT_STEP = 35  # 애니메이션 한 프레임 (ms)
SLOT_FRAMES = 6  # 나가기·들어오기 각각의 프레임 수
SLOT_RISE = 4  # 밀려 나가는 거리 (px)
PAN_WAIT = 950  # 훑기 전·후로 멈춰 서 있는 시간 (ms) — 머리와 꼬리를 읽을 틈
PAN_SPEED = 44  # 훑는 속도 (px/초). 눈으로 따라갈 만큼 느리게.
PAN_MAX = 2.8  # 칸 폭의 이 배까지만 훑는다 — 더 길면 … 로 줄인다 (하염없이 안 흐르게)
# ★ 몇 px 만 넘칠 때도 **그 시간을 다 써서 천천히** 민다. 속도대로 하면 4px 를
#   0.1초에 밀어 버려 글자가 흠칫 떠는 것처럼 보인다 (실제로 그랬다).
PAN_MIN_FRAMES = 14  # 약 0.5초
MAX_SLOTS = 4  # 한 바퀴에 넣는 최대 가짓수 (더 있으면 뒤를 자른다)

# 폭을 정할 때 쓰는 최대 길이 표본
MAX_VALUE = "100%"
# 주간은 '6일 23시간 후'보다 하루 안쪽으로 들어온 '23시간 59분 후'가 더 넓다.
MAX_LEFT = ("4시간 59분 후", "23시간 59분 후")
# 번갈아 칸이 '자르지 않고' 담아 주면 좋은 것들. 못 담아도 훑어서 보여 주므로
# 이건 최소 요구가 아니라 **바라는 폭**이다 (두 한도 칸이 먼저 제 몫을 가져간다).
MAX_SCOPED = "Claude Opus 99%"
MAX_ERROR = "눌러서 로그인 잇기"
MAX_NOTICE = "23:59 핑 실패"




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


def _mix(a: str, b: str, t: float) -> str:
    """두 색 사이 (t=0 이면 a, 1 이면 b). 글자를 바탕색으로 스미게 할 때 쓴다 —
    tk 캔버스 글자에는 투명도가 없어서, 색을 바탕 쪽으로 당겨 페이드를 흉내 낸다."""
    t = max(0.0, min(1.0, t))
    try:
        x = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        y = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    except (ValueError, IndexError):  # 이름 있는 색(#rrggbb 가 아님) — 섞지 않는다
        return b if t > 0.5 else a
    return "#%02x%02x%02x" % tuple(int(p + (q - p) * t) for p, q in zip(x, y))


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
    name = "작업표시줄 슬림 바"
    # 두 한도 칸이 제 몫(need_cell×2 ≈ 324px)을 가져가고 남는 만큼이 번갈아 칸이다.
    # ★ **긴 글자는 잘리지 않고 훑어서** 보여 주므로 이 폭을 늘릴 까닭이 없다 —
    #   작업표시줄에서 자리를 덜 먹는 쪽이 낫다. (520 까지 넓혔다가 되돌린 값)
    #   더 줄이면 두 한도 칸의 '23시간 59분 후' 부터 잘린다.
    width = 460
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
        want_right = max(
            self.f_small.measure(MAX_SCOPED),
            self.f_small.measure(MAX_NOTICE),
            self.f_msg.measure(MAX_ERROR),
        )
        # 가로: [띠] 5시간칸 |GAP| 주간칸 |MGAP(마스코트)| 번갈아칸.
        # 두 한도 칸이 먼저 제 몫을 가져가고, 남는 만큼이 번갈아 칸이다.
        # (상태 점은 오른쪽 위 구석이라 이 줄의 가로를 먹지 않는다)
        avail = self.width - PAD_L - PAD_R - GAP - MGAP
        self.right_w = min(want_right, max(MIN_SLOT, avail - need_cell * 2))
        cell_w = (avail - self.right_w) // 2

        self.accent = self.c.create_rectangle(0, 0, ACC, self.h, fill=P.track, width=0)

        x1 = PAD_L
        x2 = PAD_L + cell_w + GAP
        rx = self.width - PAD_R
        self.five = Cell(self, x1, cell_w, "5시간")
        self.week = Cell(self, x2, cell_w, "주간")
        week_end = x2 + cell_w
        right_x0 = week_end + MGAP  # 번갈아 칸 왼쪽 경계
        # 구분선: 5시간|주간, 그리고 주간|마스코트틈 (오른쪽은 마스코트가 가른다)
        for dx in (x1 + cell_w + GAP // 2, week_end + 7):
            self.c.create_line(dx, self.div_top, dx, self.div_bot, fill=P.line, width=1)

        # 번갈아 칸은 **아래 정렬** — 글자 밑선을 게이지 아래끝(div_bot)에 맞춘다.
        # 가운데에 띄우면 두 한도 칸의 두 줄 사이에 붕 떠 보인다.
        line = self.f_small.metrics("linespace")
        slot_h = line + SLOT_RISE * 2
        self.slot_h = slot_h
        # ★ 훑는 글자가 옆으로 흘러넘치지 않게 이 칸만 따로 캔버스로 둔다 (테두리에서 잘림)
        self.slot = tk.Canvas(
            self.c, width=self.right_w, height=slot_h, bg=P.bg,
            highlightthickness=0, bd=0,
        )
        self.c.create_window(rx, self.div_bot + SLOT_RISE, window=self.slot, anchor="se")
        self.model = self.slot.create_text(
            self.right_w, slot_h / 2, text="불러오는 중", anchor="e",
            font=self.f_small, fill=P.faint,
        )

        # 상태 점 자리 — 오른쪽 위 구석. 그리는 건 앱이 한다(새로고침 링과 한 캔버스).
        self.dot_spot = (self.width - DOT_INSET, DOT_INSET)

        # 클로디는 구분선과 번갈아 칸 사이 빈 틈 가운데에 앉는다. 노는 상자는 **바 전체**다
        # (완주 축하 폭죽이 바를 가로질러 터진다). **맨 마지막에 켠다** — 매 프레임 다시
        # 그리므로 늘 맨 위에 온다.
        self.claudi = Claudi(self.c, (PAD_L, 0, self.width - PAD_R, self.h))
        self.claudi.home((week_end + 7 + right_x0) // 2)
        self._slot_init()
        self.claudi.start()  # 코랄 도트 마스코트 — 통통 튀고 눌리면 폴짝

        self.five.set(None, "")
        self.week.set(None, "")

    # -------------------------------------------------- 번갈아 뜨는 오른쪽 칸
    # 한 자리를 여럿이 나눠 쓴다. `show()` 가 늘 있는 것들(모델별·적정선)을 세우고,
    # `notice()` 가 있을 때만 알림을 얹는다. 둘은 잇달아 불리므로 **바로 반영하지 않고**
    # 한 박자 뒤(after_idle)에 한 번만 반영한다 — 안 그러면 갱신마다 알림이 사라졌다
    # 다시 붙어 순서가 처음으로 되감긴다.
    # 한 가지가 뜨는 흐름:  들어오기 → 멈춤 → (길면 훑기 → 멈춤) → 나가기 → 다음
    def _slot_init(self) -> None:
        self._slot: list[tuple[str, str, bool]] = []  # (글자, 색, 굵게?)
        self._slot_base: list[tuple[str, str, bool]] = []
        self._slot_notice: tuple[str, str, bool] | None = None
        self._slot_i = 0
        self._slot_on = True
        self._slot_pan = 0.0  # 지금 것이 칸보다 넘치는 폭 (0 이면 훑지 않는다)
        self._slot_pending = None
        # build 가 다시 불려도(테마 전환) 세대는 **올리기만** 한다 — 0 으로 되돌리면
        # 옛 캔버스에 걸려 있던 콜백이 새 세대와 번호가 겹쳐 두 루프가 같이 돈다.
        self._slot_gen = getattr(self, "_slot_gen", 0) + 1

    def _slot_queue(self) -> None:
        if self._slot_pending is None:
            try:
                self._slot_pending = self.slot.after_idle(self._slot_commit)
            except tk.TclError:
                pass

    def _slot_cancel(self) -> None:
        """예약해 둔 반영을 물린다. **`None` 으로 두기만 하면 안 된다** — 그러면
        예약은 그대로 살아 있다가 나중에 옛 목록으로 자리를 덮어쓴다."""
        if self._slot_pending is not None:
            try:
                self.slot.after_cancel(self._slot_pending)
            except (tk.TclError, ValueError):
                pass
            self._slot_pending = None

    def _slot_commit(self) -> None:
        self._slot_pending = None
        items = list(self._slot_base)[:MAX_SLOTS]
        if self._slot_notice is not None:
            items.append(self._slot_notice)
        if items == self._slot:
            return  # 내용이 그대로면 돌던 자리를 지킨다
        # 알림이 새로 떴으면 순서를 기다리지 않고 그것부터 보여 준다
        fresh = self._slot_notice is not None and self._slot_notice not in self._slot
        self._slot = items
        if not items:
            try:
                self.slot.itemconfigure(self.model, text="")
            except tk.TclError:
                pass
            return
        self._slot_i = len(items) - 1 if fresh else min(self._slot_i, len(items) - 1)
        self._slot_gen += 1  # 돌던 흐름을 은퇴시키고
        self._slot_enter(self._slot_gen, SLOT_FRAMES)  # 지금 것을 곧바로 앉힌다

    def _slot_seat(self) -> tuple[str, str, bool]:
        """지금 차례인 것을 글꼴·자리와 함께 앉히고, 넘치는 폭(`_slot_pan`)을 잰다."""
        text, color, bold = self._slot[min(self._slot_i, len(self._slot) - 1)]
        font = self.f_msg if bold else self.f_small
        # 하염없이 흐르지 않게, 칸의 PAN_MAX 배를 넘는 글자는 … 로 줄여서 들인다
        text = _fit(text, font, int(self.right_w * PAN_MAX))
        self._slot_pan = max(0.0, font.measure(text) - self.right_w)
        self.slot.itemconfigure(
            self.model, text=text, font=font,
            anchor="w" if self._slot_pan else "e",
        )
        return text, color, bold

    def _slot_paint(self, dx: float = 0.0, dy: float = 0.0, fade: float = 0.0) -> None:
        """`dx` 는 훑은 만큼, `dy` 는 위아래 밀림, `fade` 는 바탕에 스민 정도."""
        if not self._slot:
            return
        color = self._slot[min(self._slot_i, len(self._slot) - 1)][1]
        x = dx if self._slot_pan else self.right_w  # 훑을 땐 왼쪽 끝에서 시작한다
        try:
            self.slot.coords(self.model, x, self.slot_h / 2 + dy)
            self.slot.itemconfigure(
                self.model, fill=_mix(color, self.slot.cget("bg"), fade)
            )
        except tk.TclError:  # 캔버스가 사라졌다 (스킨·테마 전환)
            pass

    def _slot_after(self, gen: int, ms: int, fn) -> None:
        try:
            self.slot.after(ms, lambda: fn(gen))
        except tk.TclError:
            pass

    def _slot_moves(self) -> bool:
        """흐름을 돌릴 까닭이 있나 — 가짓수가 둘 이상이거나, 하나라도 넘쳐서 훑어야 하거나."""
        return self._slot_on and (len(self._slot) > 1 or self._slot_pan > 0)

    def _slot_enter(self, gen: int, n: int) -> None:
        """아래에서 떠오른다. n=SLOT_FRAMES 면 애니메이션 없이 바로 앉힌다."""
        if gen != self._slot_gen or not self._slot:
            return
        if n <= 0 or n >= SLOT_FRAMES:
            self._slot_seat()
        t = min(1.0, n / SLOT_FRAMES)
        self._slot_paint(dy=SLOT_RISE * (1 - t), fade=1 - t)
        if n < SLOT_FRAMES:
            self._slot_after(gen, SLOT_STEP, lambda g: self._slot_enter(g, n + 1))
        elif self._slot_moves():
            self._slot_after(gen, PAN_WAIT if self._slot_pan else SLOT_HOLD,
                             lambda g: self._slot_pan_step(g, 0))

    def _slot_pan_step(self, gen: int, n: int) -> None:
        """칸보다 긴 글자를 왼쪽으로 훑는다. 넘치는 게 없으면 곧바로 나간다."""
        if gen != self._slot_gen or not self._slot_moves():
            return
        if self._slot_pan <= 0:
            self._slot_out(gen, 1)
            return
        frames = max(PAN_MIN_FRAMES, int(self._slot_pan / PAN_SPEED * 1000 / SLOT_STEP))
        self._slot_paint(dx=-self._slot_pan * min(1.0, n / frames))
        if n < frames:
            self._slot_after(gen, SLOT_STEP, lambda g: self._slot_pan_step(g, n + 1))
        else:  # 꼬리까지 다 보여 준 채로 잠깐 멈췄다 나간다
            self._slot_after(gen, PAN_WAIT, lambda g: self._slot_out(g, 1))

    def _slot_out(self, gen: int, n: int) -> None:
        """보여 주던 것이 위로 밀리며 바탕에 스민다."""
        if gen != self._slot_gen or not self._slot_moves():
            return
        t = n / SLOT_FRAMES
        self._slot_paint(dx=-self._slot_pan, dy=-SLOT_RISE * t, fade=t)
        if n < SLOT_FRAMES:
            self._slot_after(gen, SLOT_STEP, lambda g: self._slot_out(g, n + 1))
        else:
            self._slot_i = (self._slot_i + 1) % len(self._slot)
            self._slot_enter(gen, 0)

    def status_spot(self) -> tuple[int, int, str]:
        """상태 점·새로고침 링을 놓을 자리(창 기준 한가운데)와 그 자리의 바탕색."""
        return self.dot_spot[0], self.dot_spot[1], self.c.cget("bg")

    # -------------------------------------------------- 클로디 (놀이는 claudi.py 에)
    def react(self, x: float | None = None, y: float | None = None) -> None:
        self.claudi.react(*self.claudi.to_local(self, x, y))

    def absorbed(self) -> bool:
        return self.claudi.absorbed()

    def hold(self, x: float, y: float) -> None:
        self.claudi.hold(*self.claudi.to_local(self, x, y))

    def let_go(self) -> None:
        self.claudi.let_go()

    # -------------------------------------------------- 바탕 두 얼굴
    def _paint(self, bg: str, accent: str) -> None:
        self.c.configure(bg=bg)
        self.slot.configure(bg=bg)  # 번갈아 칸도 같은 바탕이라야 이어져 보인다
        self.c.itemconfigure(self.accent, fill=accent)

    # -------------------------------------------------- 값
    def show(self, usage: Usage, stamp: str) -> None:
        self._paint(P.bg, tone(worst(usage)))
        p = pace(usage)
        self.five.set(usage.five.pct, usage.five.left, five_due(usage))
        self.week.set(usage.week.pct, usage.week.left, p.due if p else None)

        # 번갈아 칸에 띄울 것들 — 모델별 한도(Fable 7%)와 알림. **적정선은 넣지 않는다**:
        # 게이지에 눈금(┃)으로 이미 서 있어서 숫자를 또 적을 까닭이 없다.
        self._slot_base = [
            (f"{s.label} {s.pct:.0f}%", P.label, False)
            for s in usage.scoped
            if s.pct is not None
        ]
        self._slot_notice = None  # 알림은 곧바로 이어 불리는 notice() 가 다시 얹는다
        self._slot_on = True
        self._slot_queue()
        # 상태 점은 앱이 그린다 (stamp 는 안 쓴다: 시각은 작업표시줄 시계에 있다)

    def show_error(self, text: str, keep_values: bool, stamp: str) -> None:
        self._paint(P.red_bg, P.red)
        # 오류가 번갈아 칸을 통째로 쓴다 (굵게·빨강 한 가지만). 길면 훑어서 다 보여 준다.
        self._slot_cancel()  # 조회 성공으로 예약해 뒀던 반영이 오류를 덮지 않게
        self._slot_base = []
        self._slot_notice = None
        self._slot_on = True
        self._slot_i = 0
        self._slot = [(text, P.red, True)]
        self._slot_gen += 1
        self._slot_enter(self._slot_gen, SLOT_FRAMES)
        if not keep_values:
            self.five.set(None, "")
            self.week.set(None, "")

    def notice(self, text: str) -> None:
        # 값은 멀쩡한데 알릴 것(핑 실패·놓침)을 번갈아 칸에 호박색으로 끼운다.
        # show() 직후 앱이 부른다 — 빈 문자열이면 그대로 둔다(show() 가 이미 비웠다).
        # 뜨는 순간 순서를 기다리지 않고 먼저 보여 준다(_slot_commit 의 fresh).
        if not text:
            return
        self._slot_notice = (text, P.amber, False)
        self._slot_queue()
