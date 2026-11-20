"""
바 캐릭터: 클로디 자리에 사용자가 고른 캐릭터 **한 명**을 세운다.

그림은 `cooldown_pack`(사용자 PC 의 `~/.claude_cooldown_pack/<캐릭터>/<동작>/`), 고른 한 명은
`cooldown_pack.active()`. 클로디(`claudi.py`)와 같은 약속(`home`·`start`·`react`·`hold`·`let_go`·
`absorbed`·`to_local`·`on_morph`·`unmorph`, 11-20 부터 `catch`·`drag`·`drop`·`set_away`·
`set_mood`·`celebrate`)을 지켜서 스킨은 `self.claudi` 이름 그대로 부른다.

- 바 본체 캔버스와 **알림 칸 캔버스(`mirror`)에 같은 그림을 겹쳐 그린다.** 알림 칸은 tk 의 따로 된
  캔버스라 본체 그림이 그 밑으로 숨기 때문이다. 알림 칸에서는 그림을 글자 **아래**에 깔고, 글자는
  스킨이 바탕색 테두리를 둘러 읽히게 한다(11-20 사용자 지시: 알림과 조금 겹쳐도 됨, 대신 구분되게).

상호작용(11-20 사용자: 마당 없이 한 명이니 손에 닿는 반응이 중요하다. 넷째: 「이런 것까지 돼?」 싶은 것도)
- 누르기: 폴짝 놀람. 자꾸 누르면 짜증 → 화남 → 포기(`base.Annoy`, 포기하면 `GIVEUP_SEC` 동안 축 처져
  아무 반응 안 하다 회복). 안 누르면 단계가 서서히 내려간다. (옛 「연타 기절」은 없앴다)
- 두 번 누르기(`DOUBLE_SEC` 안): 높이 점프.
- 길게 누르기: 눌림이 이어지다 놓으면 튕겨 오른다.
- 끌기: 캐릭터 위에서 눌러 끌면 **창이 아니라 캐릭터가** 마우스를 따라간다(끌림). 끄는 동안은 투명한
  맨 위 작은 창(`carry.Carry`)에 타서 화면 어디로든 가고(조금 크게, `CARRY_K`) 바 안 제자리는 빈다.
  놓으면 바 안이든 밖이든 **뛰기 그림으로, 처음엔 천천히 나중엔 빠르게** 곧은 줄로 제자리에 온다.
  걸리는 시간은 안팎 같은 셈(`carry.return_time`: 거리에 비례, 2.8초 한도).
- 흔들기 기절: 잡고 좌우로 2~3번 세게 흔들면(`base.Shake`) 잡힌 채로 헤롱 그림이 되고, 놓으면
  **그 자리에서**(바 밖이면 떠 있는 창 그대로) 헤롱헤롱 뻗었다가 일어나 뛰어 돌아간다.
- 던지기: 세게 휙 던지며 놓으면(`THROW_SPEED`) 중력을 받아 날아가 화면 벽·천장에 튕기고 바 높이 바닥에서
  통통 튀다 멈춘 뒤 뛰어 돌아온다.
- 창 제목 줄에 앉기: 다른 창 제목 줄 위에 놓으면(`wins.title_bar_at`) 거기 서서 인사하고 놀다가, 그 창이
  움직이거나 닫히면 떨어져(중력) 돌아오고, 누르거나 `PERCH_SEC` 지나면 폴짝 내려온다.
- 냠냠: 바 안 사용량 막대 위(캐릭터 칸 왼쪽)에 놓으면 그 자리에서 냠냠 씹고(「냠」 글자가 오름) 축하 뒤 돌아간다.
- 휠 굴리기: 캐릭터 위에서 휠을 굴리면 빙글 돈다(굴린 쪽으로). 3초 안에 `SPIN_FAINT` 번 넘게 굴리면 어지러워 기절.
- 쳐다보기: 마우스 커서가 가까이 오면 그쪽으로 돌아보고, 오래(`WATCH_GREET`) 대고 있으면 부끄럼.
- 쓰다듬기: 단추를 안 누르고 커서로 캐릭터 몸 위를 좌우로 문지르면(`RUB_TURNS`) 부끄럼.

감정(11-20 넷째, `pack.FEELINGS`, 그림이 없으면 `pack.FALLBACK` 으로 빌린다)
- 슬픔: 한도가 다 차 잠들기 전 · 포기에서 회복하기 전 · 던져져 벽·천장에 세게(`OUCH_SPEED`) 부딪혀 날며 울고
  내려앉아 잠깐 더 울다 돌아감 · 자리비움이 `AWAY_SAD` 넘게 이어지면 가끔.
- 당황: 잡히는 순간 `FLUSTER_SEC`(그 뒤 끌림) · 5시간 사용량이 `JUMP_WINDOW` 안에 `JUMP_PCT` 넘게 뛰었을 때(`note_usage`).
- 먹기: 사용량 막대 위 냠냠을 먹기 그림으로(없으면 서기를 쭈그려 구움) · 먹기 그림이 제 것이면 평소 가끔(`SNACK_P`) 간식.
- 부끄럼: 커서를 오래 대고 있을 때 · 쓰다듬기.
- 신남: 두 번 누르기 점프 뒤 · 한도 풀림 축하 뒤 이어서(`_after`).
- 심심: 아무도 안 건드린 지 `BORED_LONG` 넘으면 딴짓 대신.
- 그림: 후보(`pack.pick_clip`) 하나 = 그림 한 장(고정 그림은 효과를 구워 움직인다) 또는 이어 붙이기 묶음.
  평소 동작은 후보가 많으면 최근에 튼 절반은 피해 고른다(`_avoid`). 어두운 바에서는 둘레에 1px 밝은
  테두리를 깐다(`pack.halo`, 어두운 선이 묻히지 않게). 여백은 `pack.content_box` 가 걷는다.
- 평소 그림은 천천히(11-20 둘째: 정신없다): 한 그림을 몇 초씩(움직이는 그림은 한 바퀴 넘게 통째로) 두고,
  끝나면 서기 한 장(`pack.rest_clip`)으로 1~3초 쉬었다 다음으로. 바꿀 때는 짧게 겹쳐 바뀐다(`_fade`).
  끝난 그림에 「다음」(`pack.next_clips`)이 있으면 대개(`pack.NEXT_RATE`) 거기서 쉬지 않고 이어 고른다.
- 이동: 걷기는 평소 거닐기만. 제자리로 돌아갈 때·허둥댈 때는 뛰기. 점프는 반길 때·짧은 기쁨.
- 자리비움: PC 입력이 5분 없으면 집에서 자리비움 동작, 돌아오면 폴짝 반긴다(점프, 없으면 인사).
- 사용량 네 단계가 평소 동작에 늘 보인다: 여유(천천히, 자주 인사) · 보통(부지런히 거닒) ·
  허둥(80% 넘음, 쉬지 않고 오감) · 잠(한도). 5시간 한도가 풀리면 축하, 오류면 집에서 섬.

시험은 `pc/tests/test_char_interact.py`·`test_motions.py`: 시계를 `now` 로 바꿔 끼우고 `step(now)` 를 직접 돌린다.
"""

from __future__ import annotations

import math
import random
import time
import tkinter as tk

import cooldown_pack as pack

from . import carry, wins
from .base import P, Annoy, Shake

TICK_MS = 40
HURRY = 1.3
POKE_VY = -5.0
SPRING_K = 0.25
SPRING_DAMP = 0.7
EVENT_MIN, EVENT_MAX = 0.9, 4.0
FAINT_SEC = 2.6     # 기절해 있는 시간 (헤롱 효과면 그 장면 길이만큼)
GIVEUP_SEC = 6.0    # 포기하고 축 처져 있는 시간 (그동안 눌러도 반응 안 함)
REST_MIN, REST_MAX = 1.0, 3.0   # 평소 그림 사이에 서기 한 장으로 쉬는 시간
SHOW_MIN, SHOW_MAX = 3.0, 9.0   # 딴짓·인사 한 그림을 두는 시간 (움직이는 그림은 바퀴 수로 맞춘다)
SHOWS = ("서기", "딴짓", "인사", "점프")  # 끝나면 쉬거나 「다음」으로 잇는 평소 그림
FADE = (0.25, 0.5, 0.75)        # 평소 그림이 바뀔 때 겹치는 장면 (섞는 몫)
FADE_MS = 60
JOY_P = 0.06                    # 여유일 때 평소 고르기에서 점프(짧은 기쁨)가 나올 몫 (점프 그림이 있을 때만)
WELCOME_SEC = 2.4   # 돌아온 사람을 반기는 시간
WIDE_FX = ("쓰러짐", "빙글")  # 옆으로 눕거나 도는 효과는 폭을 더 준다 (안 주면 작아진다)
WIDE_K = 1.7
CARRY_K = 1.3       # 잡고 끄는 동안은 이만큼 크게 (손에 든 느낌, 잘 보이게)
DOUBLE_SEC = 0.35   # 두 번 누르기로 보는 사이
THROW_SPEED = 1100.0  # 놓는 순간 이보다 빠르면(px/초) 던진 것
THROW_MAX = 4000.0
GRAVITY = 2600.0    # px/초²
BOUNCE = 0.5        # 바닥에 튕길 때 남는 빠르기
WALL_BOUNCE = 0.6
TOSS_MAX = 6.0      # 던진 뒤 이 시간이 지나면 어디 있든 돌아온다
PERCH_SEC = 40.0    # 창 제목 줄에 앉아 있는 시간
PERCH_CHECK = 4     # 이 틱마다 앉은 창 자리를 본다
EAT_SEC = 2.4       # 사용량 막대를 냠냠 씹는 시간
YUM_EVERY = 0.45    # 「냠」 글자가 나오는 사이
YUM_LIFE = 0.8
SPIN_SEC = 1.2      # 휠 한 번에 도는 시간 (더 굴리면 늘어남)
SPIN_WINDOW = 3.0
SPIN_FAINT = 10     # SPIN_WINDOW 안에 이만큼 굴리면 어지러워 기절
WATCH_NEAR = 90     # 커서가 이만큼(px) 안이면 쳐다본다
WATCH_GREET = 2.5   # 이만큼 오래 가까이 있으면 인사
WATCH_COOL = 25.0
# 감정 (11-20 넷째, `pack.FEELINGS`): 언제 나오나는 머리 목록
FLUSTER_SEC = 0.6   # 잡히는 순간 당황하는 시간 (그 뒤 끌림)
SAD_SEC = 2.4
OUCH_SPEED = 1500.0  # 던져 벽·천장에 이보다 세게 부딪히면 운다
SNACK_P = 0.03      # 평소 고르기에서 간식(먹기)이 나올 몫 (먹기 그림이 제 것일 때만)
BORED_LONG = 600.0  # 아무도 안 건드린 지 이만큼 지나면 딴짓 대신 심심
AWAY_SAD = 1800.0   # 자리비움이 이만큼 넘게 이어지면
AWAY_SAD_P = 0.15   # 자리비움 그림을 고를 때 이 몫으로 슬픔
JUMP_PCT = 8.0      # 5시간 사용량이 JUMP_WINDOW 초 안에 이만큼 넘게 뛰면 당황
JUMP_WINDOW = 900.0
RUB_TURNS = 4       # 커서로 캐릭터 위를 좌우로 이만큼 오가면(쓰다듬기) 부끄럼
RUB_SWING = 6.0
RUB_WINDOW = 2.0
TAG = "buddy"
FX_TAG = "buddy_fx"

# 사용량 단계별 평소 동작: (쉬는 시간 범위(초), 거닐 확률, 인사 확률, 걷는 속도(px/틱), 딴짓까지(초))
STYLE = {
    "여유": ((3.0, 8.0), 0.25, 0.18, 0.40, 25.0),
    "보통": ((1.6, 4.5), 0.50, 0.06, 0.65, 60.0),
}


class Buddy:
    def __init__(self, canvas: tk.Canvas, box: tuple[float, float, float, float],
                 name: str, max_w: int | None = None, root: str = pack.PACK_DIR):
        self.c = canvas
        self.root = root
        self.name = name
        self.now = time.monotonic  # 시험은 가짜 시계로 바꿔 끼운다
        self.x0, self.y0, self.x1, self.y1 = box
        self.height = max(16, int(self.y1 - self.y0) - 2)
        self.max_w = max_w or int(self.height * 1.4)
        self.right = pack.faces_right(name, root)
        self.on_morph = None  # 앱이 걸어 두지만 쓰지 않는다 (공룡 변신 없음)
        self.mirror: tk.Canvas | None = None  # 알림 칸: 같은 그림을 겹쳐 그린다
        self.home_x = (self.x0 + self.x1) / 2
        self.x = self.home_x
        self.dir = 1 if self.right else -1
        self.target: float | None = None
        self.motion = ""
        self.clip: pack.Clip | None = None
        self.frames: list = []
        self.loop_from = 0  # 다 돌면 여기로 되감는다 (쓰러짐은 누운 채로만 돈다)
        self.fi = 0
        self.left_ms = 0.0
        self.until = 0.0
        self.busy = False
        self.y = 0.0
        self.vy = 0.0
        self.held = False
        # 지금 하는 큰 일: "" 평소 · "기절" · "끌림" · "날기"(바 밖에 놓아 날아오는 중) ·
        # "복귀"(바 위에 놓아 걸어 돌아가는 중) · "자리비움"
        self.mode = ""
        self.w = self.height
        self._mood = "여유"
        self._cache: dict = {}
        self._played = False
        self._gen = 0
        self._touched = self.now()
        self._last = self._touched
        self._items: dict = {}
        self._dirty = True  # 틱 밖에서 바뀐 것(끌기·동작 바꿈)이 있다. 다음 틱에 다시 그린다
        self._annoy = Annoy()
        self._shake = Shake()
        self._dizzy = False  # 흔들려 어지러운 채로 날아오는 중 (내려앉으면 기절)
        self._shown = False  # 지금 튼 것이 평소 그림(SHOWS)이다. 끝나면 쉬거나 「다음」으로 잇는다
        self._walk_clip: pack.Clip | None = None  # 「다음」이 고른 걷기 그림 (이번 거닐기에만)
        self._fade_n = 0  # self.frames 앞에 붙인 겹침 장면 수
        self._grab_off = (0.0, 0.0)
        self._ret: tuple[float, float, float] | None = None  # 바 안 뛰어 돌아가기: (떠난 x, 떠난 때, 걸릴 시간)
        self._pace = 1.0  # 그림 넘기는 빠르기 (뛰어 돌아갈 때 점점 빨라진다)
        self._held_dizzy = False  # 잡힌 채로 헤롱 그림을 트는 중
        self._trail: list[tuple[float, float, float]] = []  # 최근 끈 자리 (때, x, 발 y) — 던진 빠르기
        self._toss: dict | None = None  # 던져져 날아가는 중 (화면 좌표)
        self._perch: dict | None = None  # 창 제목 줄에 앉은 중
        self._tap_at = -99.0
        self._spins: list[float] = []
        self._yum: list[tuple[int, float]] = []  # (글자 항목, 나온 때)
        self._yum_next = 0.0
        self._eat_until = 0.0
        self._then_home = False  # 지금 동작이 끝나면 뛰어 돌아간다
        self._near_since: float | None = None
        self._greeted = -999.0
        self._ticks = 0
        self.pointer = None  # 커서 자리 (화면) 를 주는 함수. None 이면 tk 로 잰다 (시험은 바꿔 끼운다)
        self._big = False  # 떠 있는 창에 크게 그린다 (끄는 동안)
        self._after: tuple[str, float] | None = None  # 지금 동작이 끝나면 이어서 틀 감정 (동작, 초)
        self._fluster_until: float | None = None  # 잡히는 순간 당황이 끝나는 때
        self._away_since: float | None = None
        self._usage: list[tuple[float, float]] = []  # (때, 5시간 %)
        self._rub: dict = {"x": None, "dir": 0, "peak": 0.0, "turns": []}
        try:  # 어두운 바면 그림 둘레에 밝은 테두리
            rgb = canvas.winfo_rgb(P.bg)
            self._halo = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 65535 < 0.5
        except (tk.TclError, AttributeError):
            self._halo = False
        self._recent: dict[str, list] = {}  # 동작마다 최근에 튼 후보 key
        self._carry: carry.Carry | None = None  # 끄는 동안·날아오는 동안 타는 창
        self._flight: carry.Flight | None = None
        self._held_at = (0.0, 0.0)  # 끌고 있는 자리 (캔버스 좌표, 바 밖일 수 있다): 가운데 x, 발 y

    # -------------------------------------------------- 약속
    def home(self, cx: float, cy: float | None = None) -> None:
        self.home_x = self.x = cx

    def to_local(self, widget: tk.Misc, x: float | None, y: float | None):
        if x is None or y is None:
            return None, None
        top = self.c.winfo_toplevel()
        return (x - (self.c.winfo_rootx() - top.winfo_rootx()),
                y - (self.c.winfo_rooty() - top.winfo_rooty()))

    def start(self) -> None:
        self._play("서기", random.uniform(*STYLE["여유"][0]))
        self._gen += 1
        self._last = self.now()
        self._tick(self._gen)

    def absorbed(self) -> bool:
        played, self._played = self._played, False
        return played

    def react(self, x: float | None = None, y: float | None = None) -> None:
        if not self._hit(x, y):
            return
        now = self.now()
        self._played = True
        self._touched = now
        if self.mode in ("기절", "포기", "냠냠"):  # 뻗었거나 체념했거나 먹는 동안은 받기만 하고 아무 일 없음
            return
        if self.mode == "자리비움":  # 누른 사람이 곧 돌아온 사람이다
            self.set_away(False)
            return
        double = now - self._tap_at <= DOUBLE_SEC
        self._tap_at = now
        stage = self._annoy.tap(now)
        if stage >= 3:
            self._give_up()
            return
        self.target = None
        self._ret = None
        self.mode = "" if self.mode == "복귀" else self.mode
        if double and stage < 2:  # 두 번 눌렀다: 높이 점프
            self._tap_at = -99.0
            self.vy += POKE_VY * 1.8
            self._play("점프", 0.9, busy=True, restart=True)
            self._after = ("신남", 2.0)
            return
        self.vy += POKE_VY * (1.0, 0.6, 0.35)[stage]
        self._play(("놀람", "짜증", "화남")[stage], busy=True)

    def _give_up(self) -> None:
        """자꾸 눌러 체념했다. 한동안 축 처져 아무 반응 안 하다 회복한다."""
        self.mode = "포기"
        self.held = False
        self.target = None
        self.vy = 0.0
        self._play("포기", GIVEUP_SEC, busy=True)

    def hold(self, x: float, y: float) -> None:
        if self.mode in ("기절", "끌림", "자리비움", "포기", "냠냠") or not self._hit(x, y):
            return
        self._ret = None
        self._played = True
        self._touched = self.now()
        self.held = True
        self.target = None
        self._play("눌림", 3600, busy=True)

    def let_go(self) -> None:
        if self.held:
            self.held = False
            self.vy += POKE_VY * 1.2
            self._play("놀람", busy=True)

    def unmorph(self) -> None:
        pass

    # -------------------------------------------------- 끌기
    def catch(self, x: float | None, y: float | None) -> bool:
        """누른 자리가 캐릭터 위인가. 끌기를 시작하면 이 자리를 잡은 채로 따라간다."""
        if self._carry is not None or not self._hit(x, y):
            return False
        self._grab_off = (self.x - x, (self.y1 + self.y) - y)
        self._held_at = (self.x, self.y1 + self.y)
        return True

    def drag(self, x: float | None, y: float | None) -> None:
        """끄는 중 (캔버스 좌표, 바 밖일 수 있다). 캐릭터는 떠 있는 창에 타서 화면 어디로든 따라온다."""
        if x is None or y is None or self.mode in ("기절", "날기"):
            return
        if self.mode != "끌림":
            self._clear_yum()
            self.mode = "끌림"
            self.held = False
            self.target = None
            self._ret = None
            self._played = True
            self._shake.reset()
            self._held_dizzy = False
            self._trail = []
            self._big = True
            self._play("당황", 3600, busy=True)  # 잡히는 순간 잠깐 당황, 곧 끌림
            self._fluster_until = self.now() + FLUSTER_SEC
        now = self.now()
        self._touched = now
        nx, bottom = x + self._grab_off[0], y + self._grab_off[1]
        if self._shake.feed(nx, bottom, now):  # 막 어지러워졌다: 잡힌 채로 헤롱
            self._held_dizzy = True
            self._fluster_until = None
            self._play("기절", 3600, busy=True, restart=True)
        self._trail = [p for p in self._trail if now - p[0] <= 0.15] + [(now, nx, bottom)]
        if abs(nx - self._held_at[0]) > 0.5:
            self._face(1 if nx > self._held_at[0] else -1)
        self._held_at = (nx, bottom)
        self.vy = 0.0
        if self._carry is None:
            self._lift_out()
        if self._carry is not None:
            try:
                self._carry.move(*carry.screen_of(self.c, nx, bottom))
            except tk.TclError:
                pass
        self._dirty = True

    def _lift_out(self) -> None:
        """떠 있는 창을 만든다 (그림은 `_draw` 가 그 창에 그린다)."""
        try:
            w = int(self.max_w * WIDE_K * CARRY_K) + 8
            h = int(self.height * CARRY_K) + 12
            self._carry = carry.Carry(self.c, w, h, (w / 2, h - 4))
        except tk.TclError:
            self._carry = None

    def _land(self) -> None:
        if self._carry is not None:
            self._carry.close()
        self._carry = None
        self._flight = None
        self._toss = None
        self._perch = None
        self._big = False
        self._dirty = True

    def _throw_velocity(self, now: float) -> tuple[float, float] | None:
        """놓기 직전 0.12초 동안 손이 움직인 빠르기. 세게 휙 놓았으면 (vx, vy), 아니면 None."""
        pts = [p for p in self._trail if now - p[0] <= 0.12]
        if len(pts) < 2 or pts[-1][0] - pts[0][0] < 0.015:
            return None
        dt = pts[-1][0] - pts[0][0]
        vx, vy = (pts[-1][1] - pts[0][1]) / dt, (pts[-1][2] - pts[0][2]) / dt
        if math.hypot(vx, vy) < THROW_SPEED:
            return None
        clamp = lambda v: max(-THROW_MAX, min(THROW_MAX, v))  # noqa: E731
        return clamp(vx), clamp(vy)

    def put_down(self) -> None:
        if self.mode != "끌림":
            return
        now = self.now()
        nx, bottom = self._held_at
        dizzy = self._shake.dizzy(now)
        self._shake.reset()
        self._held_dizzy = False
        self._fluster_until = None
        self._big = False
        throw = self._throw_velocity(now)
        self._trail = []
        on_bar = self._carry is None or carry.inside(self.c, nx, bottom - self.height / 2)
        if dizzy and not on_bar:
            # 바 밖에서 흔들다 놓았다: 떠 있는 창 그대로 그 자리에서 헤롱헤롱 뻗었다가 돌아간다
            self.target = None
            self._faint()
            return
        if throw is not None and not dizzy and self._carry is not None:
            self._start_toss(*throw)
            return
        if on_bar:
            # 바 위에 놓았다: 그 자리에 내려앉는다 (흔들렸으면 그 자리에서 기절, 사용량 막대 위면 냠냠)
            self._land()
            cw, ch = self._area()
            lo, hi = self.w / 2, cw - self.w / 2
            self.x = min(max(nx, lo), hi) if hi > lo else nx
            self.y = min(max(bottom, float(self.height)), float(ch)) - self.y1
            if dizzy:
                self._faint()
            elif self.x < self.x0 - 2:
                self._eat()
            else:
                self._go_home()
            return
        # 바 밖에 놓았다: 창 제목 줄 위면 걸터앉고, 아니면 그 자리에서 제자리로 뛰어온다
        try:
            found = wins.title_bar_at(*carry.screen_of(self.c, nx, bottom))
        except Exception:  # noqa: BLE001
            found = None
        if found:
            self._sit(found)
            return
        self._return_home()

    def _return_home(self) -> None:
        """지금 자리에서 제자리로 뛰어간다. 떠 있는 창에 타 있으면 곧은 줄로(화면 위), 아니면 바 안에서."""
        self._toss = None
        self._perch = None
        if self._carry is None:
            self._go_home()
            return
        self.mode = "날기"
        self.target = None
        self._dizzy = False
        try:
            start = self._carry.at
            end = carry.screen_of(self.c, self.home_x, self.y1)
        except tk.TclError:
            self._land()
            self.mode = ""
            return
        self._flight = carry.Flight(start, end, self.now(), ease="in")
        if end[0] != start[0]:
            self._face(1 if end[0] > start[0] else -1)
        self._play("뛰기", 60, busy=True)  # 떠 있는 동안 뛴다 (그림이 없으면 걷기·서기를 빌린다)

    def _go_home(self) -> None:
        """놓인 자리에서 제자리로 뛰어간다. 처음엔 천천히 나중엔 빠르게, 시간은 `carry.return_time`."""
        self.mode = "복귀"
        self.busy = False
        self.until = 0
        self.target = None
        self._ret = (self.x, self.now(), carry.return_time(self.home_x - self.x))

    # -------------------------------------------------- 던지기 (중력·튕김)
    def _start_toss(self, vx: float, vy: float) -> None:
        if self._carry is None:
            self._go_home()
            return
        try:
            x, y = self._carry.at
            floor = carry.screen_of(self.c, self.home_x, self.y1)[1]
            box = wins.screen_box(self.c)
        except tk.TclError:
            self._land()
            self.mode = ""
            return
        if y > floor + 2:  # 바보다 아래에서 던졌다 (바가 화면 위쪽): 화면 바닥까지 떨어진다
            floor = box[3]
        self.mode = "던짐"
        self.target = None
        self._toss = {"x": x, "y": y, "vx": vx, "vy": vy, "t": self.now(), "start": self.now(),
                      "floor": floor, "box": box, "bounces": 0}
        if vx:
            self._face(1 if vx > 0 else -1)
        self._play("놀람", 3600, busy=True, restart=True)

    def _tossing(self, now: float) -> bool:
        t = self._toss
        if t is None or self._carry is None:
            self._return_home()
            return True
        dt = min(0.06, max(0.0, now - t["t"]))
        t["t"] = now
        t["vy"] += GRAVITY * dt
        t["x"] += t["vx"] * dt
        t["y"] += t["vy"] * dt
        left, top, right, _ = t["box"]
        half = self.max_w / 2
        hit = 0.0
        if t["x"] < left + half:
            hit = abs(t["vx"])
            t["x"], t["vx"] = left + half, abs(t["vx"]) * WALL_BOUNCE
            self._face(1)
        elif t["x"] > right - half:
            hit = abs(t["vx"])
            t["x"], t["vx"] = right - half, -abs(t["vx"]) * WALL_BOUNCE
            self._face(-1)
        if t["y"] - self.height < top:
            hit = max(hit, abs(t["vy"]))
            t["y"], t["vy"] = top + self.height, abs(t["vy"]) * 0.5
        if hit > OUCH_SPEED and not t.get("ouch"):  # 아야: 세게 부딪혀 운다
            t["ouch"] = True
            self._play("슬픔", 3600, busy=True, restart=True)
        settled = False
        if t["y"] >= t["floor"]:
            t["y"] = t["floor"]
            if t["vy"] > 260:  # 바닥에 튕긴다
                t["vy"] = -t["vy"] * BOUNCE
                t["vx"] *= 0.75
                t["bounces"] += 1
                if not t.get("ouch"):
                    self._play("놀람", 3600, busy=True, restart=True)
            else:
                settled = True
        try:
            self._carry.move(t["x"], t["y"])
        except tk.TclError:
            pass
        if settled and t.get("ouch"):  # 부딪혀 아팠다: 그 자리에서 잠깐 울고 돌아간다
            self._toss = None
            self.mode = "울음"
            self._play("슬픔", 1.6, busy=True)
        elif settled or now - t["start"] > TOSS_MAX:
            self._return_home()
        return True

    # -------------------------------------------------- 창 제목 줄에 앉기
    def _sit(self, found) -> None:
        hwnd, (l, t, r, b) = found
        try:
            sx = min(max(self._carry.at[0], l + wins.SIDE_IN), r - wins.SIDE_IN)
            self._carry.move(sx, t + 1)
            self._carry.on_click(self._hop_off)
        except (tk.TclError, AttributeError):
            self._return_home()
            return
        self.mode = "앉음"
        self.target = None
        self._perch = {"hwnd": hwnd, "rect": (l, t, r, b), "since": self.now()}
        self._play("인사", 2.4, busy=True)

    def _hop_off(self) -> None:
        """앉은 창에서 폴짝 내려온다 (눌렀을 때 · 오래 앉아 있었을 때)."""
        if self.mode == "앉음":
            self._played = True
            self._start_toss(0.0, -700.0)

    def _perching(self, now: float) -> bool:
        p = self._perch
        if p is None or self._carry is None:
            self._return_home()
            return True
        if self._ticks % PERCH_CHECK == 0:
            rect = wins.rect_of(p["hwnd"])
            if rect is None or max(abs(a - b) for a, b in zip(rect, p["rect"])) > 2:
                self._start_toss(0.0, 0.0)  # 앉은 창이 움직이거나 닫혔다: 떨어진다
                return True
        if now - p["since"] > PERCH_SEC:
            self._hop_off()
            return True
        if now >= self.until:
            long = now - p["since"] > 15
            pool = [m for m in ("서기", "딴짓") + (("잠",) if long else ()) if pack.own(self.name, m, self.root)]
            self._play(random.choice(pool or ["서기"]), random.uniform(3.0, 6.0), busy=True)
            return True
        return False

    # -------------------------------------------------- 냠냠 (사용량 막대 위에 놓음)
    def _eat(self) -> None:
        self.mode = "냠냠"
        self.target = None
        now = self.now()
        frames = [] if pack.own(self.name, "먹기", self.root) else self._chew_frames()
        if frames:  # 먹기 그림이 없으면 서기를 쭈그렸다 폈다 굽는다
            self._play_frames("냠냠", frames, EAT_SEC)
        else:
            self._play("먹기", EAT_SEC, busy=True)
        self._eat_until = now + EAT_SEC
        self._yum_next = now

    def _chew_frames(self) -> list:
        """서기 한 장을 쭈그렸다 폈다 굽는다 (씹는 시늉)."""
        rest = pack.rest_clip(self.name, self.root)
        if rest is None:
            return []
        key = ("chew", rest.key, self._flip())
        if key not in self._cache:
            out = []
            try:
                from PIL import ImageTk

                raw = self._raw_for(rest, self._flip())[0]
                if raw:
                    baked, _ = pack.bake([raw[0][0]], "쭈그러짐", 3)
                    fitted = pack.fit_frames(baked, self.height, 1.0, int(self.max_w * WIDE_K))
                    out = [(ImageTk.PhotoImage(im, master=self.c), int(ms * 0.6)) for im, ms in fitted]
            except Exception:  # noqa: BLE001 — 꾸밈일 뿐이다
                out = []
            self._cache[key] = out
        return self._cache[key]

    def _eating(self, now: float) -> bool:
        for item, born in list(self._yum):
            if now - born > YUM_LIFE:
                self._drop_item(item)
                self._yum.remove((item, born))
            else:
                try:
                    self.c.move(item, 0, -0.8)
                except tk.TclError:
                    pass
        if now >= self._eat_until:
            self._clear_yum()
            self.mode = ""
            self._then_home = abs(self.x - self.home_x) > 2
            self.vy += POKE_VY * 0.8
            self._play("축하", 1.2, busy=True)
            return True
        if now >= self._yum_next:
            self._yum_next = now + YUM_EVERY
            try:
                top = self.y1 + self.y - self.height
                item = self.c.create_text(self.x + random.uniform(-self.w / 3, self.w / 3), top + 6,
                                          text="냠", fill=P.title, font=("Malgun Gothic", 8, "bold"),
                                          tags=FX_TAG)
                self._yum.append((item, now))
            except tk.TclError:
                pass
        return True

    def _drop_item(self, item) -> None:
        try:
            self.c.delete(item)
        except tk.TclError:
            pass

    def _clear_yum(self) -> None:
        for item, _ in self._yum:
            self._drop_item(item)
        self._yum = []

    # -------------------------------------------------- 휠 → 빙글
    def wheel(self, x: float | None, y: float | None, delta: int) -> None:
        if not self._hit(x, y) or self.mode not in ("", "복귀") or self.held:
            return
        now = self.now()
        self._touched = now
        self._spins = [t for t in self._spins if now - t <= SPIN_WINDOW] + [now]
        if len(self._spins) >= SPIN_FAINT:  # 너무 돌렸다: 어지러워 뻗는다
            self._spins = []
            self._faint()
            return
        if self.motion == "빙글" and self.busy:
            self.until = min(now + 3.0, self.until + 0.5)
            return
        frames = self._spin_frames(delta > 0)
        if not frames:
            return
        self.mode = ""
        self.target = None
        self._ret = None
        self._then_home = abs(self.x - self.home_x) > 2
        self._play_frames("빙글", frames, SPIN_SEC)

    def _spin_frames(self, ccw: bool) -> list:
        clip = self.clip or pack.rest_clip(self.name, self.root)
        if clip is None:
            return []
        key = ("spin", clip.key, self._flip(), ccw)
        if key not in self._cache:
            out = []
            try:
                from PIL import Image, ImageTk

                raw = self._raw_for(clip, self._flip())[0]
                if raw:
                    baked, _ = pack.bake([raw[0][0]], "빙글", 2)
                    baked = baked[:-1]  # 끝의 쉬는 장면은 빼고 계속 돈다
                    if ccw:
                        baked = [(im.transpose(Image.FLIP_LEFT_RIGHT), ms) for im, ms in baked]
                    fitted = pack.fit_frames(baked, self.height, 1.0, int(self.max_w * WIDE_K))
                    out = [(ImageTk.PhotoImage(im, master=self.c), ms) for im, ms in fitted]
            except Exception:  # noqa: BLE001
                out = []
            self._cache[key] = out
        return self._cache[key]

    def _play_frames(self, motion: str, frames: list, seconds: float) -> None:
        """팩 후보가 아닌 장면(빙글·냠냠, 지금 그림을 돌리거나 굽은 것)을 튼다."""
        self.clip = None
        self.motion = motion
        self.frames = list(frames)
        self.loop_from = 0
        self.fi = 0
        self._fade_n = 0
        self._shown = False
        self.left_ms = self.frames[0][1] if self.frames else 200
        if self.frames:
            self.w = self.frames[0][0].width()
        self.until = self.now() + seconds
        self.busy = True
        self._dirty = True

    # -------------------------------------------------- 쳐다보기
    def _watch(self, now: float) -> None:
        """커서가 가까이 오면 그쪽을 본다. 오래 대고 있으면 인사."""
        try:
            if self.pointer is not None:
                px, py = self.pointer()
            else:
                if not self.c.winfo_viewable():
                    return
                px, py = self.c.winfo_pointerxy()
            cx = self.c.winfo_rootx() + self.x
            cy = self.c.winfo_rooty() + self.y1 + self.y - self.height / 2
        except (tk.TclError, TypeError, ValueError):
            return
        if abs(px - cx) > WATCH_NEAR or abs(py - cy) > WATCH_NEAR:
            self._near_since = None
            self._rub["x"] = None
            return
        if self._rubbed(px, py, cx, cy, now):  # 커서로 쓰다듬었다: 부끄럼
            self._greeted = now
            self._near_since = now
            self._show("부끄럼", 2.5)
            return
        if abs(px - cx) > 6:
            self._face(1 if px > cx else -1)
        if self._near_since is None:
            self._near_since = now
        elif (now - self._near_since >= WATCH_GREET and now - self._greeted >= WATCH_COOL
              and (self.motion in SHOWS or not self.busy)):
            self._greeted = now
            self._show("부끄럼", 2.0)

    def _rubbed(self, px: float, py: float, cx: float, cy: float, now: float) -> bool:
        """커서가 캐릭터 몸 위에서 좌우로 RUB_TURNS 번 넘게 오갔나 (단추 안 누르고 문지르기)."""
        r = self._rub
        if abs(px - cx) > self.w / 2 + 4 or abs(py - cy) > self.height / 2 + 4:
            r["x"] = None
            return False
        if r["x"] is None:
            r.update(x=px, dir=0, peak=px, turns=[])
            return False
        r["x"] = px
        if r["dir"] == 0:
            if abs(px - r["peak"]) >= RUB_SWING:
                r["dir"] = 1 if px > r["peak"] else -1
                r["peak"] = px
        elif (px - r["peak"]) * r["dir"] > 0:
            r["peak"] = px
        elif abs(px - r["peak"]) >= RUB_SWING:
            r["turns"].append(now)
            r["dir"] = -r["dir"]
            r["peak"] = px
        r["turns"] = [t for t in r["turns"] if now - t <= RUB_WINDOW]
        if len(r["turns"]) >= RUB_TURNS:
            r["turns"] = []
            return True
        return False

    # -------------------------------------------------- 자리비움 (PC 입력 없음)
    def set_away(self, away: bool) -> None:
        if away:
            if self.mode in ("기절", "끌림", "날기", "던짐", "앉음", "냠냠"):
                return  # 지금 손에 잡혀 있거나 뻗어 있거나 바 밖이다. 다음에 앱이 다시 알려 준다
            self._ret = None
            self._clear_yum()
            self.mode = "자리비움"
            self._away_since = self.now()
            self.held = False
            self.busy = False
            self.until = 0
            self.target = None
            return
        if self.mode != "자리비움":
            return
        self._away_since = None
        self.mode = ""
        self._touched = self.now()
        self.vy += POKE_VY
        self.target = None
        self._play("점프" if pack.own(self.name, "점프", self.root) else "인사", WELCOME_SEC, busy=True)

    # -------------------------------------------------- 사용량
    def set_mood(self, mood: str) -> None:
        if mood == self._mood:
            return
        self._mood = mood
        if self.mode:  # 기절·끌림·복귀·자리비움·포기 중이면 그 일을 마친 뒤 새 기분으로
            return
        self.target = None
        if mood == "잠":  # 한도가 다 찼다: 잠들기 전에 잠깐 슬프다
            self._play("슬픔", SAD_SEC, busy=True)
            return
        self.until = 0  # 지금 동작을 끊고 새 분위기로 바로 다시 고른다
        self.busy = False

    def note_usage(self, pct: float | None) -> None:
        """5시간 사용량(%)을 받는다. 짧은 새 크게 뛰었으면 당황한다."""
        if pct is None:
            return
        now = self.now()
        self._usage = [(t, p) for t, p in self._usage if now - t <= JUMP_WINDOW] + [(now, float(pct))]
        low = min(p for _, p in self._usage)
        if pct - low >= JUMP_PCT:
            self._usage = [(now, float(pct))]
            if not self.mode and not self.held:
                self.target = None
                self._play("당황", 2.0, busy=True)

    def celebrate(self) -> None:
        if self.mode:
            return
        self.vy += POKE_VY * 1.3
        self.target = None
        self._play("축하", 2.6, busy=True)
        self._after = ("신남", 2.0)

    # -------------------------------------------------- 그림
    def _raw_for(self, clip: pack.Clip, flip: bool, big: bool = False) -> tuple[list, int]:
        """후보 → ([(PIL RGBA, ms)], 되감을 자리), 바 높이에 맞춘 것 (굽기는 한 번만).
        `big` 은 끄는 동안 떠 있는 창에 크게 태울 것 (`CARRY_K` 배)."""
        key = ("raw", clip.key, flip, big)
        if key not in self._cache:
            from PIL import Image
            k = CARRY_K if big else 1.0
            width = int(self.max_w * k * (WIDE_K if clip.effect in (*WIDE_FX, "헤롱") else 1))
            try:
                raw, loop_from = pack.load_clip(clip, int(self.height * k), width)
                if self._halo:
                    raw = [(pack.halo(im), ms) for im, ms in raw]
            except Exception:  # 깨진 그림 하나 때문에 위젯이 죽으면 안 된다
                raw, loop_from = [], 0
            if flip:
                raw = [(im.transpose(Image.FLIP_LEFT_RIGHT), ms) for im, ms in raw]
            self._cache[key] = (raw, loop_from)
        return self._cache[key]

    def _frames_for(self, clip: pack.Clip, flip: bool, solid: bool = False,
                    big: bool = False) -> tuple[list, int]:
        """후보 → ([(PhotoImage, ms)], 되감을 자리). `solid` 는 떠 있는 창에 태울 그림(알파 반 자름)."""
        key = (clip.key, flip, solid, big)
        if key not in self._cache:
            from PIL import ImageTk
            raw, loop_from = self._raw_for(clip, flip, big)
            self._cache[key] = ([(ImageTk.PhotoImage(carry.solid(im) if solid else im, master=self.c), ms)
                                 for im, ms in raw], loop_from)
        return self._cache[key]

    def _flip(self) -> bool:
        return (self.dir > 0) != self.right

    def _refresh_frames(self) -> None:
        if self.clip:
            self.frames, self.loop_from = self._frames_for(self.clip, self._flip())
            if self.frames:
                self.w = self.frames[0][0].width()
            if self.loop_from >= len(self.frames):
                self.loop_from = 0
            if self._fade_n:  # 겹침 장면을 걷어 낸다 (돌아서는 등). 자리는 그만큼 당긴다
                self.fi = max(0, self.fi - self._fade_n)
                self._fade_n = 0

    def _fade(self, old_clip: pack.Clip, old_fi: int) -> None:
        """지금 그림에서 새 그림으로 짧게 겹쳐 바뀌게, 섞은 장면 몇 장을 앞에 붙인다(평소 그림만)."""
        if self._carry is not None or not self.frames:
            return
        try:
            from PIL import Image, ImageTk

            old = self._raw_for(old_clip, self._flip())[0]
            new = self._raw_for(self.clip, self._flip())[0]
            if not old or not new:
                return
            a, b = old[old_fi % len(old)][0], new[0][0]
            w, h = max(a.width, b.width), max(a.height, b.height)

            def on_board(im):
                board = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                board.paste(im, ((w - im.width) // 2, h - im.height))
                return board

            a, b = on_board(a), on_board(b)
            mixed = [(ImageTk.PhotoImage(Image.blend(a, b, t), master=self.c), FADE_MS) for t in FADE]
        except Exception:  # noqa: BLE001 — 꾸밈일 뿐이다
            return
        self.frames = mixed + list(self.frames)
        self.loop_from += len(mixed)
        self._fade_n = len(mixed)

    def _avoid(self, motion: str) -> list:
        """최근에 튼 후보들 (피할 것). 후보가 n 개면 최근 n//2 개(적어도 하나는 남긴다)."""
        n = len(pack.candidates(self.name, motion, self.root))
        keep = max(0, min(n - 1, n // 2))
        return self._recent.get(motion, [])[-keep:] if keep else []

    def _play(self, motion: str, seconds: float | None = None, busy: bool = False,
              restart: bool = False) -> None:
        clip = pack.pick_clip(self.name, motion, self.root, avoid=self._avoid(motion))
        if clip is None:
            return
        self._play_clip(motion, clip, seconds, busy, restart)

    def _play_clip(self, motion: str, clip: pack.Clip, seconds: float | None = None,
                   busy: bool = False, restart: bool = False, fade: bool = False) -> None:
        self._shown = False
        if clip != self.clip or motion != self.motion or restart:
            old_clip = self.clip
            old_fi = self.fi - self._fade_n
            self.clip, self.motion = clip, motion
            hist = self._recent.setdefault(motion, [])
            hist.append(clip.key)
            del hist[:-pack.MAX_PER_MOTION]
            self._fade_n = 0
            self._refresh_frames()
            self.fi = 0
            if fade and old_fi >= 0 and old_clip is not None and old_clip.key != clip.key:
                self._fade(old_clip, old_fi)
            self.left_ms = self.frames[0][1] if self.frames else 200
        if seconds is None:
            seconds = max(EVENT_MIN, min(EVENT_MAX, self._cycle() or 1.6))
        self.until = self.now() + seconds
        self.busy = busy
        self._dirty = True

    def _cycle(self) -> float:
        """지금 그림 한 바퀴(초). 한 장짜리면 0. 겹침 장면은 빼고 센다."""
        real = self.frames[self._fade_n:]
        return sum(ms for _, ms in real) / 1000 if len(real) > 1 else 0.0

    def _show(self, motion: str, want: float, clip: pack.Clip | None = None) -> None:
        """평소 그림 하나를 넉넉히 둔다: `want` 초쯤, 움직이는 그림은 바퀴가 끝나는 데까지."""
        if clip is None:
            clip = pack.pick_clip(self.name, motion, self.root, avoid=self._avoid(motion))
            if clip is None:
                return
        self._play_clip(motion, clip, 1.0, busy=True, fade=True)
        cyc = self._cycle()
        if cyc > 0:
            n = max(1, math.ceil(want / cyc - 1e-6))
            while n > 1 and n * cyc > SHOW_MAX:
                n -= 1
            want = n * cyc
        self.until = self.now() + want + self._fade_n * FADE_MS / 1000
        self._shown = True

    def _face(self, d: int) -> None:
        if d and d != self.dir:
            self.dir = d
            self._refresh_frames()

    def _hit(self, x, y) -> bool:
        if x is None or y is None or self._carry is not None:
            return False
        bottom = self.y1 + self.y
        return abs(x - self.x) <= self.w / 2 + 2 and bottom - self.height - 2 <= y <= bottom + 2

    def _area(self) -> tuple[float, float]:
        """끌어서 갈 수 있는 곳 = 바 캔버스 전체 (캐릭터가 통째로 안에 남게 가둔다)."""
        try:
            w, h = self.c.winfo_width(), self.c.winfo_height()
            if w <= 1:
                w, h = int(float(self.c.cget("width"))), int(float(self.c.cget("height")))
            return float(w), float(h)
        except (tk.TclError, ValueError):
            return self.x1, self.y1

    # -------------------------------------------------- 움직임
    def _bounds(self) -> tuple[float, float]:
        return self.x0 + self.w / 2, self.x1 - self.w / 2

    def _choose(self, now: float) -> None:
        lo, hi = self._bounds()
        if self._after is not None and not self.mode:  # 이어서 틀 감정 (점프 뒤 신남 등)
            m, secs = self._after
            self._after = None
            self._show(m, secs)
            return
        if self._then_home and not self.mode:  # 냠냠·빙글이 끝났다: 뛰어 돌아간다
            self._then_home = False
            if abs(self.x - self.home_x) > 2:
                self._go_home()
                return
        if self.mode == "복귀":  # 돌아가다 눌려 멈췄다: 그 자리에서 다시 뛴다
            if abs(self.x - self.home_x) > 2:
                self._go_home()
            else:
                self.mode = ""
            return
        if self.mode == "자리비움" or self._mood in ("잠", "오류"):
            if abs(self.x - self.home_x) > 2:
                self.target = self.home_x
            elif self.mode == "자리비움":
                long = self._away_since is not None and now - self._away_since > AWAY_SAD
                self._play("슬픔" if long and random.random() < AWAY_SAD_P else "자리비움", 3.0)
            elif self._mood == "잠":
                self._play("잠", 3.0)
            else:
                self._play("서기", 2.0)
            return
        if self._mood == "허둥" and hi > lo:  # 허둥댈 땐 쉬지 않고 오간다
            self.target = random.uniform(lo, hi)
            return
        idle, stroll, wave, _speed, bored = STYLE.get(self._mood, STYLE["여유"])
        finished = self.clip if self._shown and self.motion in SHOWS else None
        self._shown = False
        if finished is not None:
            # 평소 그림 하나가 끝났다: 「다음」이 있으면 대개 거기서 바로 잇고, 아니면 서기 한 장으로 쉰다
            if random.random() < pack.NEXT_RATE:
                nxt = pack.next_clips(self.name, finished, self.root)
                if nxt:
                    m, c = random.choice(nxt)
                    if m != "걷기":
                        self._show(m, self._want(m, idle), c)
                        return
                    if hi > lo:
                        self._walk_clip = c
                        self.target = random.uniform(lo, hi)
                        return
            rest = pack.rest_clip(self.name, self.root)
            if rest is not None and rest.key != finished.key:
                self._play_clip("서기", rest, random.uniform(REST_MIN, REST_MAX), fade=True)
                return
        if abs(self.x - self.home_x) > 2 and random.random() < 0.5:
            self.target = self.home_x  # 거닐다가 집으로 돌아온다
            return
        if pack.own(self.name, "먹기", self.root) and random.random() < SNACK_P:  # 간식 시간 (드물게)
            self._show("먹기", random.uniform(3.0, 5.0))
            return
        r = random.random()
        long_bored = now - self._touched > BORED_LONG
        if (now - self._touched > bored and r < 0.2
                and (pack.own(self.name, "딴짓", self.root) or pack.own(self.name, "심심", self.root))):
            m = "심심" if long_bored else "딴짓"  # 아무도 안 건드린 지 오래면 심심
            self._show(m, self._want("딴짓", idle))
        elif r < 0.2 + wave and pack.own(self.name, "인사", self.root):
            self._show("인사", self._want("인사", idle))
        elif r < 0.2 + wave + stroll and hi > lo:
            self.target = random.uniform(lo, hi)
        elif (self._mood == "여유" and r < 0.2 + wave + stroll + JOY_P
              and pack.own(self.name, "점프", self.root)):
            self._show("점프", 0.5)
        else:
            self._show("서기", self._want("서기", idle))

    @staticmethod
    def _want(motion: str, idle: tuple[float, float]) -> float:
        if motion == "서기":
            return random.uniform(*idle)
        if motion == "점프":
            return 0.5
        return random.uniform(SHOW_MIN, SHOW_MIN + 2.0)

    def _walk_motion(self) -> str:
        """걸어 움직일 때 틀 동작. 돌아갈 때·허둥댈 때는 뛰기(그림이 없으면 pack 이 걷기·서기를 빌린다)."""
        if self.mode == "복귀":
            return "뛰기"
        if self._mood == "허둥":
            if pack.own(self.name, "뛰기", self.root):
                return "뛰기"
            return "허둥" if pack.own(self.name, "허둥", self.root) else "걷기"
        return "걷기"

    def _walk_speed(self) -> float:
        if self._mood == "허둥":
            return HURRY
        return STYLE.get(self._mood, STYLE["여유"])[3]

    def _advance(self, ms: float) -> bool:
        if len(self.frames) < 2:
            return False
        self.left_ms -= ms
        moved = False
        while self.left_ms <= 0:
            self.fi += 1
            if self.fi >= len(self.frames):
                self.fi = self.loop_from if self.loop_from < len(self.frames) else 0
            self.left_ms += self.frames[self.fi][1]
            moved = True
        return moved

    def _faint(self) -> None:
        """헤롱헤롱 기절 (끌며 마구 흔들었을 때). 헤롱 장면이면 그 한 바퀴(비틀→쓰러짐→일어남)만큼."""
        self.mode = "기절"
        self.held = False
        self.target = None
        self._ret = None
        self._dizzy = False
        self._clear_yum()
        self._play("기절", FAINT_SEC, busy=True, restart=True)
        if self.clip is not None and self.clip.effect == "헤롱" and self._cycle() > 0:
            self.until = self.now() + self._cycle()

    def step(self, now: float | None = None) -> bool:
        """한 틱. 그릴 게 바뀌었으면 참. 앱은 `_tick` 으로 40ms 마다, 시험은 직접 부른다."""
        now = self.now() if now is None else now
        dt = (now - self._last) * 1000
        self._last = now
        self._ticks += 1
        dirty = self._advance(dt * self._pace)
        if self.mode == "끌림" and self._carry is not None and not carry.button_down():
            self.put_down()  # 놓은 것을 앱이 못 받았다 (창 전환 등). 떠 있는 채로 남지 않게
        if (self.mode == "끌림" and self._fluster_until is not None and now >= self._fluster_until
                and not self._held_dizzy):
            self._fluster_until = None
            self._play("끌림", 3600, busy=True)
            dirty = True
        if self.mode == "끌림" and self._held_dizzy and not self._shake.dizzy(now):
            self._held_dizzy = False  # 들고 가만히 있었더니 정신 차렸다
            self._play("끌림", 3600, busy=True)
            dirty = True
        self._pace = 1.0
        if self.mode == "날기":
            if self._flight is not None:  # 뛰어 오는 동안 점점 빨리 발을 놀린다
                self._pace = 0.6 + 1.0 * self._flight.progress(now)
            return self._fly(now)
        if self.mode == "던짐":
            return self._tossing(now)
        if self.mode == "앉음":
            return self._perching(now) or dirty
        if self.mode in ("기절", "울음") and self._carry is not None:  # 바 밖에서 뻗어 있거나 운다
            if now >= self.until:
                self.mode = ""
                self._return_home()
            return True
        if self.mode == "냠냠":
            dirty = self._eating(now) or dirty
        if self.mode != "끌림" and (abs(self.y) > 0.05 or abs(self.vy) > 0.05):
            self.vy = (self.vy - self.y * SPRING_K) * SPRING_DAMP
            self.y = max(self.y + self.vy, -(self.y1 - self.y0) * 0.35)
            if abs(self.y) <= 0.05 and abs(self.vy) <= 0.05:
                self.y = self.vy = 0.0
            dirty = True
        speed = self._walk_speed()
        if self.mode == "기절":
            if now >= self.until:  # 깨어난다. 놓인 자리가 제자리가 아니면 뛰어 돌아간다
                headlong = self.clip is not None and self.clip.effect == "헤롱"
                self.mode = ""
                if not headlong:  # 헤롱 장면은 스스로 일어난다. 아니면 털고 폴짝
                    self.vy += POKE_VY * 0.8
                    self._play("놀람", busy=True)
                if abs(self.x - self.home_x) > 2:
                    self._go_home()
                elif headlong:
                    self.busy = False
                    self.until = 0
                dirty = True
        elif self.mode == "포기":
            if now >= self.until:  # 다시 기운을 차린다 (쌓인 짜증도 비운다). 그 전에 잠깐 서럽다
                self.mode = ""
                self._annoy.reset()
                self._play("슬픔", SAD_SEC, busy=True)
                dirty = True
        elif self.mode in ("끌림", "냠냠") or self.held:
            pass
        elif self.mode == "복귀" and self._ret is not None and not self.busy:
            # 제자리로 뛰어간다: 처음엔 천천히 나중엔 빠르게 (바 밖에서 놓았을 때와 같은 셈)
            x0, t0, dur = self._ret
            p = min(1.0, max(0.0, (now - t0) / dur))
            self._pace = 0.6 + 1.0 * p
            d = self.home_x - self.x
            if abs(d) > 0.5:
                self._face(1 if d > 0 else -1)
            if self.motion != "뛰기":
                self._play("뛰기", 60)
            self.x = x0 + (self.home_x - x0) * carry.ease_in(p)
            if p >= 1.0:
                self.x = self.home_x
                self._ret = None
                self.mode = ""
                self.until = 0
            dirty = True
        elif self.target is not None and not self.busy:
            d = self.target - self.x
            if abs(d) <= speed:
                self.x, self.target = self.target, None
                self.until = 0
                self._walk_clip = None
                if self.mode == "복귀":
                    self.mode = ""
            else:
                self._face(1 if d > 0 else -1)
                walk = self._walk_motion()
                if walk == "걷기" and self._walk_clip is not None:
                    if self.clip != self._walk_clip:
                        self._play_clip("걷기", self._walk_clip, 60)
                elif self.motion != walk:
                    self._play(walk, 60)
                self.x += speed if d > 0 else -speed
            dirty = True
        elif now >= self.until:
            self.busy = False
            self._choose(now)
            dirty = True
        elif self.mode == "":
            self._watch(now)  # 커서 자리 읽기는 가볍다 (쓰다듬기를 놓치지 않게 틱마다)
        return dirty

    def _fly(self, now: float) -> bool:
        """날아오는 중 한 틱. 다 오면 바에 내려앉아 폴짝."""
        done = True
        if self._flight is not None and self._carry is not None:
            x, y, done = self._flight.at(now)
            self._carry.move(x, y)
        if done:  # 살며시 내려앉는다 (튀지 않게). 흔들려 왔으면 그 자리에서 헤롱헤롱
            self._land()
            self.mode = ""
            self.x, self.y, self.vy = self.home_x, 0.0, 0.0
            if self._dizzy:
                self._faint()
            else:
                rest = pack.rest_clip(self.name, self.root)
                if rest is not None:
                    self._play_clip("서기", rest, random.uniform(REST_MIN, REST_MAX))
        return True

    def _tick(self, gen: int) -> None:
        if gen != self._gen or not self.c.winfo_exists():
            return
        if self.step() or self._dirty or not self._items:
            self._dirty = False
            self._draw()
        self.c.after(TICK_MS, lambda: self._tick(gen))

    def _draw(self) -> None:
        if not self.frames:
            return
        if self._carry is not None:
            self._draw_carried()
            return
        img = self.frames[self.fi % len(self.frames)][0]
        x, y = self.x, self.y1 + self.y + (2 if self.held else 0)
        views = [(self.c, 0, 0, False)]
        if self.mirror is not None:
            try:
                dx = self.mirror.winfo_rootx() - self.c.winfo_rootx()
                dy = self.mirror.winfo_rooty() - self.c.winfo_rooty()
                views.append((self.mirror, dx, dy, True))
            except tk.TclError:
                pass
        for canvas, dx, dy, under in views:
            try:
                item = self._items.get(canvas)
                if item is None or not canvas.type(item):
                    item = canvas.create_image(x - dx, y - dy, image=img, anchor="s", tags=TAG)
                    self._items[canvas] = item
                else:
                    canvas.itemconfigure(item, image=img)
                    canvas.coords(item, x - dx, y - dy)
                canvas.itemconfigure(item, state="normal")
                if under:
                    canvas.tag_lower(item)  # 알림 칸에서는 글자 아래에 깐다
                else:
                    canvas.tag_raise(item)
            except tk.TclError:
                pass

    def _draw_carried(self) -> None:
        """떠 있는 창에 그린다. 바 안 제자리(본체·알림 칸)는 비운다."""
        for canvas, item in list(self._items.items()):
            try:
                canvas.itemconfigure(item, state="hidden")
            except tk.TclError:
                pass
        cv = self._carry.canvas
        big = self._big and self.mode == "끌림"
        frames, _ = (self._frames_for(self.clip, self._flip(), solid=True, big=big)
                     if self.clip else ([], 0))
        if not frames:
            return
        img = frames[self.fi % len(frames)][0]
        try:
            if not cv.find_withtag(TAG):
                cv.create_image(self._carry.ax, self._carry.ay, image=img, anchor="s", tags=TAG)
            else:
                cv.itemconfigure(TAG, image=img)
        except tk.TclError:
            pass
