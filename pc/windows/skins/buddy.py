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

★ 1모션 원칙(11-21 사용자: 놀람과 짜증이 번갈아 나온다, 끌 때 다른 게 잠깐 나온다, 쳐다보기도 섞인다).
  상호작용 하나가 시작되면 끝날 때까지 **그 동작 그림 하나만** 보인다. 중간에 평소 그림·다른 상호작용이
  끼지 않고, 겹치면 우선순위 하나만 이긴다. 바뀌는 것은 단계가 오를 때(연타·흔들기)뿐이다.
- 누르기: **누를 때가 아니라 뗄 때** 정한다(`react` 는 받아 두기만, 앱 `_release` 가 `tap_up`). 끌려던 것이면
  아무 그림도 안 비친다. 첫 누름은 `DOUBLE_SEC` 기다려 두 번 누르기(깡충)가 아니면 놀람.
- 연타: `STREAK_GAP` 안에 잇달아 누르면 한 덩어리다. 그동안 그림은 그대로 두고 단계가 오를 때만
  짜증 → 화남 → 포기로 바뀐다(`base.Annoy`, 내려가지 않는다). 놀람이 다시 나오지 않는다.
  포기하면 `GIVEUP_SEC` 동안 축 처져 아무 반응 안 하다 회복.
- 길게 누르기: 눌림이 이어지다(`HOLD_WAIT` 더 누르고 있어야 보인다) 놓으면 눌림 그대로 튕겨 오른다.
- 끌기: 캐릭터 위에서 눌러 끌면 **창이 아니라 캐릭터가** 마우스를 따라간다. 판정되는 순간 곧바로 끌림.
  끄는 동안은 투명한 맨 위 작은 창(`carry.Carry`)에 타서 화면 어디로든 가고(조금 크게, `CARRY_K`).
  놓으면 뛰기 그림으로, 처음엔 천천히 나중엔 빠르게 곧은 줄로 제자리에 온다(`carry.return_time`).
- 흔들기 세 단계(`base.ShakeMeter`): 잡고 세게 흔들수록 끌림 → 어질 → 헤롱 → 기절. 멈추면 천천히 내려온다.
  놓으면 그 자리에서 어질·헤롱은 잠깐(`DIZZY_SEC`), 기절은 뻗었다가(바 밖이면 떠 있는 창 그대로) 뛰어 돌아간다.
  어지러운 채로는 던져지지 않는다.
- 던지기: 세게 휙 던지며 놓으면(`THROW_SPEED`) 날아감. 잘 보이게 조금 크게(`TOSS_K`), 처음에 잠깐 멈칫한 뒤
  (`TOSS_PAUSE`) 조금 느린 시간(`TOSS_SLOW`)으로 중력을 받아 날아 화면 벽·천장에 튕기고 바 높이 바닥에서
  통통 튀다 멈춘 뒤 뛰어 돌아온다. 세게 부딪히면(`BONK_SPEED`) 그때부터 내려앉을 때까지 꽈당.
- 창 제목 줄에 앉기: 다른 창 제목 줄 위에 놓으면(`wins.title_bar_at`) 거기 앉아 있다가(앉기 하나), 그 창이
  움직이거나 닫히면 떨어져(중력) 돌아오고, 누르거나 `PERCH_SEC` 지나면 폴짝 내려온다.
- 냠냠: 바 안 사용량 막대 위(캐릭터 칸 왼쪽)에 놓으면 서기 그림을 쭈그렸다 폈다 굽어 씹고(「냠」 글자가 오름) 돌아간다.
- 휠 굴리기: 빙글(굴린 쪽으로, 빙글 그림이 없으면 지금 그림을 돌려 굽는다). `SPIN_WINDOW` 안에 `SPIN_FAINT` 번이면 기절.
- 커서(`_watch`): 커서가 가까이(`WATCH_NEAR`) 오면 한 번 정해 떠날 때까지 그것 하나. 몸 위에 `HOVER_SEC`
  가만히 머물면 갸웃, 아니면 쳐다보기. 그사이 몸 위를 좌우로 문지르면(`RUB_TURNS`) 간지럼으로 올라가 그대로.
  누르거나 끈 뒤에는 커서가 한 번 떠났다 와야 다시 본다(누른 손이 곧 커서라 놀람 뒤에 바로 섞이지 않게).
- 하트: 가운데 단추(「♥」가 오름) · 빼꼼: 바 양 끝 바로 밖(`PEEK_RANGE`)에 놓으면 바 끝에 반쯤 숨어 들락날락,
  누르면 돌아옴 · 밀기: 거닐다 왼쪽 끝(사용량 막대)에 닿으면 가끔(`PUSH_P`) · 깸: 잠·자리비움 중에 누름 ·
  허우적: 화면 위쪽(`FLAIL_TOP`)에 놓으면 허우적대며 바로 떨어져 내려앉음. 칸이 비면 `pack.FALLBACK`.
- 놓는 자리는 던지기 > 바 위(어지러움 > 냠냠 > 복귀) > 빼꼼 > 창 제목 줄 > 허우적 > 날아 돌아옴.
  누르기는 깸 > 포기 > 깡충 > 놀람·짜증·화남.
- 감정 묶음(슬픔·당황·먹기·부끄럼·신남·심심)은 11-21 에 뺐다. 팩에 그 폴더가 남아 있어도 안 쓴다.
- 그림: 후보(`pack.pick_clip`) 하나 = 그림 한 장(고정 그림은 효과를 구워 움직인다) 또는 이어 붙이기 묶음.
  평소 동작은 후보가 많으면 최근에 튼 절반은 피해 고른다(`_avoid`). 어두운 바에서는 둘레에 1px 밝은
  테두리를 깐다(`pack.halo`, 어두운 선이 묻히지 않게). 여백은 `pack.content_box` 가 걷는다.
- 평소 그림은 천천히(11-20 둘째: 정신없다): 한 그림을 몇 초씩(움직이는 그림은 한 바퀴 넘게 통째로) 두고,
  끝나면 서기 한 장(`pack.rest_clip`)으로 1~3초 쉬었다 다음으로. 바꿀 때는 옛 그림이 옅어진 뒤 새 그림이
  짙어진다(`_fade`). ★ 두 그림을 겹쳐 섞지 않는다(11-21 사용자: 바뀔 때 잔상이 남는다).
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
from .base import P, Annoy, ShakeMeter

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
FADE = (0.6, 0.25, 0.45, 0.8)   # 평소 그림이 바뀔 때: 옛 그림 옅게 두 장 → 새 그림 옅게 두 장 (짙기)
FADE_OUT = 2                    # FADE 앞 몇 장이 옛 그림인가
FADE_MS = 50
JOY_P = 0.06                    # 여유일 때 평소 고르기에서 점프(짧은 기쁨)가 나올 몫 (점프 그림이 있을 때만)
WELCOME_SEC = 2.4   # 돌아온 사람을 반기는 시간
WIDE_FX = ("쓰러짐", "빙글")  # 옆으로 눕거나 도는 효과는 폭을 더 준다 (안 주면 작아진다)
WIDE_K = 1.7
CARRY_K = 1.3       # 잡고 끄는 동안은 이만큼 크게 (손에 든 느낌, 잘 보이게)
DOUBLE_SEC = 0.35   # 두 번 누르기로 보는 사이 (첫 누름은 이만큼 기다려 놀람인지 깡충인지 정한다)
STREAK_GAP = 1.0    # 이 안에 또 누르면 같은 연타 (그림을 바꾸지 않고 이어 둔다)
HOLD_WAIT = 0.25    # 앱이 꾹 누름을 알린 뒤 이만큼 더 누르고 있어야 눌림 그림 (곧 끌 것일 수 있다)
DIZZY_SEC = {"어질": 0.9, "헤롱": 1.6}  # 어지러운 채로 놓으면 그 자리에서 이만큼 비틀댄 뒤 돌아간다
THROW_SPEED = 1100.0  # 놓는 순간 이보다 빠르면(px/초) 던진 것
THROW_MAX = 4000.0
# 날아감이 빨라 잘 안 보인다(11-21 사용자): 조금 크게, 처음에 잠깐 멈칫, 조금 느린 시간으로 난다
TOSS_K = 1.5        # 나는 동안 이만큼 크게 (끄는 동안 CARRY_K 보다 조금 더)
TOSS_PAUSE = 0.14   # 던진 순간 그 자리에서 멈칫하는 시간 (그림이 먼저 눈에 들어오게)
TOSS_SLOW = 0.72    # 나는 동안 시간 흐름 (1 보다 작으면 같은 길을 더 천천히)
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
OUCH_SPEED = 1500.0  # 던져 벽·천장에 이보다 세게 부딪히면 내려앉아서도 잠깐 꽈당
OUCH_SEC = 1.6
RUB_TURNS = 4       # 커서로 캐릭터 위를 좌우로 이만큼 오가면(쓰다듬기) 간지럼
RUB_SWING = 6.0
RUB_WINDOW = 2.0
# 상호작용 하나에 그림 하나 (11-21)
BONK_SPEED = 600.0  # 던져져 벽·천장·바 끝에 이보다 세게 부딪히면 꽈당
WATCH_LOOK = 0.4    # 커서가 이만큼 가까이 머물면 쳐다보기 그림
HOVER_SEC = 2.0     # 커서가 몸 위에 이만큼 가만히 있으면 (쳐다보기 대신) 갸웃
HOVER_STILL = 4.0   # 이만큼(px) 안에서 움직이면 가만히 있는 것
LOOKS = ("쳐다보기", "갸웃", "간지럼")  # 커서가 가까이 있는 동안의 상호작용 (한 번 정하면 떠날 때까지)
STAGES = ("끌림", "어질", "헤롱", "기절")  # 흔든 단계별 그림
HEART_SEC = 2.2
HEART_N = 3         # 「♥」 글자 수
HEART_EVERY = 0.35
HEART_COLOR = "#ff6f91"
PEEK_RANGE = 90.0   # 바 끝에서 이만큼 밖에 놓으면 빼꼼
PEEK_DEEP = 0.25    # 깊이 숨을 때 몸 폭의 이만큼 더 밖으로
PEEK_SEC = (1.5, 3.5)
PUSH_P = 0.25       # 거닐 곳을 고를 때 사용량 막대 끝으로 가서 미는 몫 (밀기)
PUSH_SEC = 1.8
WAKE_SEC = 1.6
FLAIL_TOP = 0.35    # 화면 위쪽 이만큼(몫) 안에 놓으면 허우적대며 떨어진다
FLAIL_DROP = 200.0  # 그리고 바 바닥보다 이만큼 넘게 위여야
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
        self._shake = ShakeMeter()
        self._stage = 0  # 끄는 동안 흔든 단계 (0 끌림 · 1 어질 · 2 헤롱 · 3 기절)
        self._dizzy = False  # 흔들려 어지러운 채로 날아오는 중 (내려앉으면 기절)
        self._shown = False  # 지금 튼 것이 평소 그림(SHOWS)이다. 끝나면 쉬거나 「다음」으로 잇는다
        self._walk_clip: pack.Clip | None = None  # 「다음」이 고른 걷기 그림 (이번 거닐기에만)
        self._fade_n = 0  # self.frames 앞에 붙인 겹침 장면 수
        self._grab_off = (0.0, 0.0)
        self._ret: tuple[float, float, float] | None = None  # 바 안 뛰어 돌아가기: (떠난 x, 떠난 때, 걸릴 시간)
        self._pace = 1.0  # 그림 넘기는 빠르기 (뛰어 돌아갈 때 점점 빨라진다)
        self._trail: list[tuple[float, float, float]] = []  # 최근 끈 자리 (때, x, 발 y) — 던진 빠르기
        self._toss: dict | None = None  # 던져져 날아가는 중 (화면 좌표)
        self._perch: dict | None = None  # 창 제목 줄에 앉은 중
        self._tap_at = -99.0
        self._spins: list[float] = []
        self._yum: list[tuple[int, float]] = []  # (글자 항목, 나온 때)
        self._yum_next = 0.0
        self._eat_until = 0.0
        self._then_home = False  # 지금 동작이 끝나면 뛰어 돌아간다
        # 누르기 (11-21 1모션): 누른 때는 받아 두고 뗄 때 정한다. 연타는 한 덩어리
        self._pending: float | None = None  # 눌렀는데 아직 안 뗐다 (누른 때)
        self._tap_wait: tuple[float, str] | None = None  # (이때까지 또 안 누르면, 놀람·깡충)
        self._last_tap = -99.0
        self._taps = 0  # 이번 연타에서 누른 수
        self._tap_motion = ""  # 이번 연타의 그림 (놀람·깡충·짜증·화남)
        self._hold_show: float | None = None  # 이때 넘게 누르고 있으면 눌림 그림
        # 커서 (11-21 1모션): 가까이 온 동안 한 번 정한 그림 하나
        self._look: dict | None = None  # {"since": 가까이 온 때, "pick": None·LOOKS 하나}
        self._watch_armed = True  # 누르거나 끈 뒤에는 커서가 한 번 떠나야 다시 본다
        self._ticks = 0
        self.pointer = None  # 커서 자리 (화면) 를 주는 함수. None 이면 tk 로 잰다 (시험은 바꿔 끼운다)
        self._big = False  # 떠 있는 창에 크게 그린다 (끄는 동안)
        self._fly_k = 1.0  # 던져져 나는 동안 그림 배수
        self._rub: dict = {"x": None, "dir": 0, "peak": 0.0, "turns": []}
        self._hover: tuple[float, float, float] | None = None  # 커서가 몸 위에 머문 (때, x, y)
        self._hearts: list[float] = []  # 아직 안 띄운 「♥」 글자의 때
        self._peek: dict | None = None  # 바 끝에 숨어 내다보는 중: {"side": -1·1, "deep": bool}
        self._push_next = False  # 이번 거닐기 끝(왼쪽 끝)에 닿으면 민다
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
        """눌렀다 (앱 `_press`). 그림은 아직 안 바꾸고 받아 두기만 한다: 끌기로 이어지면 끌림만,
        꾹 누르면 눌림만, 그냥 떼면(`tap_up`) 그때 누르기 반응을 정한다 (11-21 1모션)."""
        if not self._hit(x, y):
            return
        now = self.now()
        self._played = True
        self._touched = now
        self._watch_armed = False
        self._pending = now

    def tap_up(self) -> None:
        """누른 손을 끌지 않고 뗐다: 받아 둔 누르기를 이제 정한다."""
        if self._pending is None:
            return
        self._pending = None
        self._tap(self.now())

    def _tap(self, now: float) -> None:
        if self.mode in ("기절", "포기", "냠냠", "끌림"):  # 뻗었거나 체념했거나 먹는 동안은 받기만 하고 아무 일 없음
            return
        if self.mode == "자리비움":  # 누른 사람이 곧 돌아온 사람이다: 화들짝 깬다
            self.set_away(False, woke=True)
            return
        if self.mode == "빼꼼":  # 숨어 있다 들켰다: 제자리로 뛰어간다
            self._peek = None
            self.vy += POKE_VY * 0.6
            self._go_home()
            return
        if self.mode == "" and self.motion == "잠":  # 한도가 차 자고 있다: 화들짝 깼다가 다시 잔다
            self._wake()
            return
        if self.mode == "봄":  # 쳐다보던 중에 눌렸다: 누르기가 이긴다
            self._end_look()
        streak = now - self._last_tap <= STREAK_GAP and (self._taps > 0)
        double = streak and self._taps == 1 and now - self._last_tap <= DOUBLE_SEC
        self._last_tap = now
        self._taps = self._taps + 1 if streak else 1
        if not streak:
            self._tap_motion = ""
            self._tap_wait = None
        stage = self._annoy.tap(now)
        if stage >= 3:
            self._give_up()
            return
        self.target = None
        self._ret = None
        self._walk_clip = None
        self.mode = "" if self.mode == "복귀" else self.mode
        keep = max(self.until, now + STREAK_GAP)  # 다음 누름까지 지금 그림 그대로 (사이에 평소 그림이 안 끼게)
        if stage == 0 and not self._tap_motion:
            # 아직 그림을 안 정했다. 첫 누름은 DOUBLE_SEC 기다려 본다: 또 누르면 깡충 후보, 그 뒤 곧 또
            # 누르면 연타(놀람). 기다리는 동안 그림은 그대로 둔다
            w = self._tap_wait
            if w is None or (w[1] == "놀람" and double):
                self._tap_wait = (now + DOUBLE_SEC, "깡충" if w is not None else "놀람")
                self.busy = True
                self.until = max(self.until, now + DOUBLE_SEC + STREAK_GAP)
                return
            self._tap_motion = "놀람"  # 셋째 빠른 누름(연타) · 늦은 둘째: 놀람으로 정한다
        self._tap_wait = None
        want = ("", "짜증", "화남")[stage] if stage else self._tap_motion
        if stage and self._tap_motion in ("짜증", "화남"):  # 연타 단계는 내려가지 않는다
            want = ("짜증", "화남")[max(("짜증", "화남").index(self._tap_motion), stage - 1)]
        self.vy += POKE_VY * (0.6, 0.6, 0.35)[stage] * (0.5 if want == self.motion else 1.0)
        self._tap_motion = want
        if self.motion == want and self.busy:  # 같은 그림 이어 두기 (다시 처음부터 틀지 않는다)
            self.until = keep
            return
        self._play(want, busy=True)
        self.until = max(self.until, keep)

    def _tap_settle(self, now: float) -> bool:
        """누른 뒤 DOUBLE_SEC 동안 또 안 눌렀다: 한 번이면 놀람, 두 번이면 깡충."""
        if self._tap_wait is None or now < self._tap_wait[0]:
            return False
        kind = self._tap_wait[1]
        self._tap_wait = None
        if self.mode not in ("", "복귀") or self.held:
            return False
        self._tap_motion = kind
        if kind == "깡충":  # 두 번 눌렀다: 높이 깡충
            self.vy += POKE_VY * 1.8
            self._play("깡충", 0.9, busy=True, restart=True)
        else:
            self.vy += POKE_VY
            self._play("놀람", busy=True)
        self.until = max(self.until, self._last_tap + STREAK_GAP)
        return True

    def _wake(self) -> None:
        """자다가 눌렸다: 화들짝 깬다 (짜증 단계는 안 센다)."""
        self.target = None
        self.vy += POKE_VY * 1.4
        self._play("깸", WAKE_SEC, busy=True, restart=True)

    def middle(self, x: float | None = None, y: float | None = None) -> None:
        """가운데 단추로 눌렀다: 하트 (「♥」 글자가 오른다)."""
        if not self._hit(x, y) or self.mode not in ("", "복귀", "봄") or self.held:
            return
        now = self.now()
        self._played = True
        self._touched = now
        self._watch_armed = False
        self._end_look()
        self.target = None
        self._ret = None
        self._then_home = self.mode == "복귀" or abs(self.x - self.home_x) > 2
        self.mode = ""
        self.vy += POKE_VY * 0.5
        self._play("하트", HEART_SEC, busy=True, restart=True)
        self._hearts = [now + i * HEART_EVERY for i in range(HEART_N)]

    def _give_up(self) -> None:
        """자꾸 눌러 체념했다. 한동안 축 처져 아무 반응 안 하다 회복한다."""
        self.mode = "포기"
        self.held = False
        self.target = None
        self.vy = 0.0
        self._tap_wait = None
        self._taps = 0
        self._tap_motion = ""
        self._play("포기", GIVEUP_SEC, busy=True)

    def hold(self, x: float, y: float) -> None:
        """꾹 누르고 있다 (앱이 HOLD_MS 뒤 한 번). 곧 끌 수도 있으니 HOLD_WAIT 더 지나야 눌림 그림."""
        if self.mode in ("기절", "끌림", "자리비움", "포기", "냠냠", "빼꼼") or not self._hit(x, y):
            return
        self._ret = None
        self._played = True
        self._touched = self.now()
        self.held = True
        self.target = None
        self._hold_show = self.now() + HOLD_WAIT
        self.busy = True
        self.until = max(self.until, self._hold_show + 1.0)  # 그동안 지금 그림 그대로

    def _hold_settle(self, now: float) -> bool:
        if self._hold_show is None or now < self._hold_show or not self.held:
            return False
        self._hold_show = None
        self._pending = None  # 꾹 누름이다 (뗄 때 누르기로 치지 않는다)
        self._tap_wait = None
        if self.mode == "봄":
            self._end_look()
        self._play("눌림", 3600, busy=True)
        return True

    def let_go(self) -> None:
        if not self.held:
            return
        self.held = False
        if self._hold_show is not None:  # 눌림이 보이기 전에 뗐다: 보통 누르기 (뗄 때 tap_up 이 정한다)
            self._hold_show = None
            self.until = self.now()
            return
        self.vy += POKE_VY * 1.2
        self._play("눌림", 0.6, busy=True)  # 눌림 그대로 튕겨 오른다 (같은 그림이라 바뀌지 않는다)

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
            # 끌기로 판정된 순간 곧바로 끌림 하나 (누를 때 받아 둔 누르기·꾹 누름은 버린다, 11-21 1모션)
            self._clear_yum()
            self._peek = None
            self._end_look()
            self._pending = self._tap_wait = self._hold_show = None
            self._taps = 0
            self._tap_motion = ""
            self._watch_armed = False
            self.mode = "끌림"
            self.held = False
            self.target = None
            self._ret = None
            self._walk_clip = None
            self._played = True
            self._shake.reset()
            self._stage = 0
            self._trail = []
            self._big = True
            self._play("끌림", 3600, busy=True, restart=True)
        now = self.now()
        self._touched = now
        nx, bottom = x + self._grab_off[0], y + self._grab_off[1]
        self._set_stage(self._shake.feed(nx, bottom, now))
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

    def _set_stage(self, stage: int) -> None:
        """흔든 단계가 바뀌었을 때만 그림을 바꾼다 (끌림 · 어질 · 헤롱 · 기절)."""
        if stage == self._stage:
            return
        self._stage = stage
        self._play(STAGES[stage], 3600, busy=True, restart=True)
        self._dirty = True

    def _lift_out(self) -> None:
        """떠 있는 창을 만든다 (그림은 `_draw` 가 그 창에 그린다)."""
        try:
            k = max(CARRY_K, TOSS_K)  # 던지면 같은 창에서 더 크게 난다
            w = int(self.max_w * WIDE_K * k) + 8
            h = int(self.height * k) + 12
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
        stage = self._shake.level(now)
        dizzy = stage > 0
        self._shake.reset()
        self._stage = 0
        self._big = False
        throw = self._throw_velocity(now)
        self._trail = []
        on_bar = self._carry is None or carry.inside(self.c, nx, bottom - self.height / 2)
        if dizzy and not on_bar:
            # 바 밖에서 흔들다 놓았다: 떠 있는 창 그대로 그 자리에서 비틀대거나 뻗었다가 돌아간다
            self.target = None
            self._faint(STAGES[stage])
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
                self._faint(STAGES[stage])
            elif self.x < self.x0 - 2:
                self._eat()
            else:
                self._go_home()
            return
        # 바 밖에 놓았다: 바 끝 바로 옆이면 빼꼼, 창 제목 줄 위면 걸터앉고, 화면 위쪽이면 허우적대며
        # 떨어지고, 아니면 그 자리에서 제자리로 뛰어온다
        side = self._peek_side(nx, bottom)
        if side:
            self._start_peek(side)
            return
        try:
            found = wins.title_bar_at(*carry.screen_of(self.c, nx, bottom))
        except Exception:  # noqa: BLE001
            found = None
        if found:
            self._sit(found)
            return
        if self._flail_drop():
            return
        self._return_home()

    def _peek_side(self, nx: float, bottom: float) -> int:
        """놓은 자리(캔버스 좌표)가 바 왼쪽 끝 바로 밖이면 -1, 오른쪽 끝 바로 밖이면 1, 아니면 0."""
        cw, ch = self._area()
        if not (-self.height * 0.6 <= bottom <= ch + self.height):
            return 0
        if -PEEK_RANGE <= nx < 0:
            return -1
        if cw < nx <= cw + PEEK_RANGE:
            return 1
        return 0

    def _start_peek(self, side: int) -> None:
        """바 끝에 반쯤 숨는다 (그림 반이 바 밖으로 잘린다). 누르면 돌아온다."""
        self._land()
        self.mode = "빼꼼"
        self.target = None
        self._ret = None
        self.y = self.vy = 0.0
        self._peek = {"side": side, "deep": True}
        self._face(-side)  # 바 안쪽을 본다
        self._peek_step()

    def _peek_step(self) -> None:
        """깊이 숨었다가 빼꼼 내다봤다가를 번갈아 (처음은 내다본다)."""
        p = self._peek
        cw, _ = self._area()
        edge = 0.0 if p["side"] < 0 else cw
        p["deep"] = not p["deep"]
        self._play("빼꼼", random.uniform(*PEEK_SEC), busy=True)
        self.x = edge + p["side"] * (self.w * PEEK_DEEP if p["deep"] else 0.0)
        self._dirty = True

    def _flail_drop(self) -> bool:
        """화면 위쪽 높은 곳에 놓였다: 허우적대며 바(제자리)로 떨어진다. 떨어지면 참."""
        if self._carry is None:
            return False
        try:
            x, y = self._carry.at
            fx, floor = carry.screen_of(self.c, self.home_x, self.y1)
            box = wins.screen_box(self.c)
        except (tk.TclError, TypeError, ValueError):
            return False
        top, bottom = box[1], box[3]
        if floor - y < FLAIL_DROP or not top <= y <= top + (bottom - top) * FLAIL_TOP:
            return False
        fall = math.sqrt(2 * (floor - y) / GRAVITY)
        vx = max(-THROW_MAX, min(THROW_MAX, (fx - x) / max(0.1, fall)))
        self._start_toss(vx, 0.0, flail=True)
        return True

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
    def _start_toss(self, vx: float, vy: float, flail: bool = False) -> None:
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
        try:  # 바 양 끝 (화면 x) · 바 윗변 (화면 y): 낮게 날다 바 끝에 부딪힌다
            cw, _ = self._area()
            bl, btop = carry.screen_of(self.c, 0, 0)
            bar = (bl, bl + cw, btop)
        except (tk.TclError, TypeError, ValueError):
            bar = None
        if y > floor + 2:  # 바보다 아래에서 던졌다 (바가 화면 위쪽): 화면 바닥까지 떨어진다
            floor = box[3]
        self.mode = "던짐"
        self.target = None
        now = self.now()
        pause = 0.0 if flail else TOSS_PAUSE  # 던진 순간 그 자리에서 잠깐 멈칫 (허우적은 바로 떨어진다)
        self._toss = {"x": x, "y": y, "vx": vx, "vy": vy, "t": now + pause, "start": now,
                      "floor": floor, "box": box, "bounces": 0, "bar": bar, "flail": flail,
                      "bonk": False}
        self._fly_k = 1.0 if flail else TOSS_K
        if vx:
            self._face(1 if vx > 0 else -1)
        self._play("허우적" if flail else "날아감", 3600, busy=True, restart=True)

    def _tossing(self, now: float) -> bool:
        t = self._toss
        if t is None or self._carry is None:
            self._return_home()
            return True
        if now < t["t"]:  # 멈칫하는 중
            return True
        dt = min(0.06, max(0.0, now - t["t"])) * (1.0 if t["flail"] else TOSS_SLOW)
        t["t"] = now
        t["vy"] += GRAVITY * dt
        t["x"] += t["vx"] * dt
        t["y"] += t["vy"] * dt
        left, top, right, _ = t["box"]
        k = 1.0 if t["flail"] else TOSS_K
        half = self.max_w * k / 2
        hit = 0.0
        if t["x"] < left + half:
            hit = abs(t["vx"])
            t["x"], t["vx"] = left + half, abs(t["vx"]) * WALL_BOUNCE
            self._face(1)
        elif t["x"] > right - half:
            hit = abs(t["vx"])
            t["x"], t["vx"] = right - half, -abs(t["vx"]) * WALL_BOUNCE
            self._face(-1)
        if t["y"] - self.height * k < top:
            hit = max(hit, abs(t["vy"]))
            t["y"], t["vy"] = top + self.height * k, abs(t["vy"]) * 0.5
        hit = max(hit, self._bar_end_hit(t, half))
        if hit > OUCH_SPEED:  # 아야: 세게 부딪혔다. 내려앉아서도 잠깐 꽈당
            t["ouch"] = True
        if hit > BONK_SPEED and not t["flail"] and not t["bonk"]:
            # 꽈당: 부딪힌 순간부터 내려앉을 때까지 꽈당 하나 (날아감으로 되돌아가지 않는다)
            t["bonk"] = True
            self._play("꽈당", 3600, busy=True, restart=True)
        settled = False
        if t["y"] >= t["floor"]:
            t["y"] = t["floor"]
            if t["vy"] > 260 and not t["flail"]:  # 바닥에 튕긴다 (허우적대며 떨어진 건 그대로 내려앉는다)
                t["vy"] = -t["vy"] * BOUNCE
                t["vx"] *= 0.75
                t["bounces"] += 1
            else:
                settled = True
        try:
            self._carry.move(t["x"], t["y"])
        except tk.TclError:
            pass
        if settled and t.get("ouch"):  # 세게 부딪혔다: 그 자리에서 잠깐 꽈당한 채로 있다 돌아간다
            self._toss = None
            self.mode = "울음"
            self.until = now + OUCH_SEC
        elif settled or now - t["start"] > TOSS_MAX:
            self._return_home()
        return True

    @staticmethod
    def _bar_end_hit(t: dict, half: float) -> float:
        """바 높이로 낮게 날다 바 밖에서 바 끝으로 들어오면 튕긴다. 부딪힌 빠르기 (안 부딪혔으면 0)."""
        bar = t.get("bar")
        px = t.get("px", t["x"])
        t["px"] = t["x"]
        if not bar:
            return 0.0
        bl, br, btop = bar
        if t["y"] <= btop + 2:
            return 0.0
        hit = 0.0
        if px <= bl - half < t["x"]:  # 왼쪽 밖에서 오른쪽으로 들어왔다
            hit = abs(t["vx"])
            t["x"], t["vx"] = bl - half, -abs(t["vx"]) * WALL_BOUNCE
        elif px >= br + half > t["x"]:
            hit = abs(t["vx"])
            t["x"], t["vx"] = br + half, abs(t["vx"]) * WALL_BOUNCE
        t["px"] = t["x"]
        return hit

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
        self._play("앉기", 3.0, busy=True, restart=True)  # 앉기 그림이 없으면 인사(손 흔들며 앉음)를 빌린다

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
        if now >= self.until:  # 앉아 있는 동안 내내 앉기 하나 (빌린 그림이어도 같은 것을 이어 둔다)
            self.until = now + 3.0
        return False

    # -------------------------------------------------- 냠냠 (사용량 막대 위에 놓음)
    def _eat(self) -> None:
        self.mode = "냠냠"
        self.target = None
        now = self.now()
        frames = self._chew_frames()  # 서기 그림을 쭈그렸다 폈다 굽는다 (먹기 칸은 11-21 에 뺐다)
        if frames:
            self._play_frames("냠냠", frames, EAT_SEC)
        else:
            self._play("서기", EAT_SEC, busy=True)
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

    def _float_texts(self, now: float) -> bool:
        """오르는 글자(「냠」·「♥」)를 올리고 다 된 것은 지운다. 띄울 「♥」가 남았으면 띄운다."""
        moved = bool(self._yum)
        for item, born in list(self._yum):
            if now - born > YUM_LIFE:
                self._drop_item(item)
                self._yum.remove((item, born))
            else:
                try:
                    self.c.move(item, 0, -0.8)
                except tk.TclError:
                    pass
        while self._hearts and now >= self._hearts[0]:
            self._hearts.pop(0)
            if self.motion == "하트" and self._carry is None:
                self._pop_text("♥", HEART_COLOR, now)
                moved = True
        return moved

    def _pop_text(self, text: str, color: str, now: float) -> None:
        try:
            top = self.y1 + self.y - self.height
            item = self.c.create_text(self.x + random.uniform(-self.w / 3, self.w / 3), top + 6,
                                      text=text, fill=color, font=("Malgun Gothic", 8, "bold"),
                                      tags=FX_TAG)
            self._yum.append((item, now))
        except tk.TclError:
            pass

    def _eating(self, now: float) -> bool:
        if now >= self._eat_until:  # 다 먹었다: 그대로 뛰어 돌아간다
            self._clear_yum()
            self.mode = ""
            self.vy += POKE_VY * 0.8
            if abs(self.x - self.home_x) > 2:
                self._go_home()
            else:
                self.busy = False
                self.until = 0
            return True
        if now >= self._yum_next:
            self._yum_next = now + YUM_EVERY
            self._pop_text("냠", P.title, now)
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
        self._hearts = []

    # -------------------------------------------------- 휠 → 빙글
    def wheel(self, x: float | None, y: float | None, delta: int) -> None:
        if not self._hit(x, y) or self.mode not in ("", "복귀", "봄") or self.held:
            return
        now = self.now()
        self._touched = now
        self._watch_armed = False
        self._end_look()
        self._spins = [t for t in self._spins if now - t <= SPIN_WINDOW] + [now]
        if len(self._spins) >= SPIN_FAINT:  # 너무 돌렸다: 어지러워 뻗는다
            self._spins = []
            self._faint()
            return
        if self.motion == "빙글" and self.busy:
            self.until = min(now + 3.0, self.until + 0.5)
            return
        if pack.own(self.name, "빙글", self.root):  # 제 빙글 그림이 있으면 그것 (효과는 움직임.json 대로)
            self.mode = ""
            self.target = None
            self._ret = None
            self._then_home = abs(self.x - self.home_x) > 2
            self._play("빙글", SPIN_SEC, busy=True, restart=True)
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

    # -------------------------------------------------- 커서 (쳐다보기 · 갸웃 · 간지럼)
    def _watch(self, now: float) -> None:
        """커서가 가까이 오면 한 번 정해 떠날 때까지 그것 하나 (11-21 1모션).
        몸 위에 HOVER_SEC 가만히 머물면 갸웃, 아니면 WATCH_LOOK 뒤 쳐다보기. 그사이 문지르면 간지럼으로 올라간다."""
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
        if abs(px - cx) > WATCH_NEAR or abs(py - cy) > WATCH_NEAR:  # 커서가 갔다
            self._rub["x"] = None
            self._hover = None
            self._watch_armed = True
            if self._look is not None:
                self._end_look()
            return
        if not self._watch_armed:  # 방금 누르거나 끈 손이다 (한 번 떠났다 와야 본다)
            return
        look = self._look
        if look is None:
            # 지금 누르기 반응 같은 상호작용을 하는 중이면 끼어들지 않는다 (끝난 뒤에 본다)
            if self.mode != "" or self.held or (self.busy and self.motion in pack.INTERACT):
                return
            look = self._look = {"since": now, "pick": None}
            self._rub["x"] = None
            self._hover = None
        rubbed = self._rubbed(px, py, cx, cy, now)
        if look["pick"] == "간지럼":
            return
        if rubbed:  # 문질렀다: 간지럼으로 올라가 떠날 때까지 그대로
            self._pick_look("간지럼")
            return
        if look["pick"] is not None:
            if abs(px - cx) > 6:
                self._face(1 if px > cx else -1)  # 같은 그림을 커서 쪽으로 돌린다
            return
        on_body = abs(px - cx) <= self.w / 2 + 2 and abs(py - cy) <= self.height / 2 + 2
        if on_body:  # 몸 위: 가만히 머물면 갸웃, 아니면 HOVER_SEC 뒤 쳐다보기
            if self._hovering(px, py, cx, cy, now):
                self._pick_look("갸웃")
            elif now - look["since"] >= HOVER_SEC:
                self._pick_look("쳐다보기")
            else:
                self._freeze(now)
            return
        if now - look["since"] >= WATCH_LOOK:
            if abs(px - cx) > 6:
                self._face(1 if px > cx else -1)
            self._pick_look("쳐다보기")
        else:
            self._freeze(now)

    def _freeze(self, now: float) -> None:
        """정하는 동안 지금 그림을 그대로 둔다 (평소 그림이 바뀌거나 거닐지 않게)."""
        self.target = None
        self._walk_clip = None
        self.until = max(self.until, now + 0.2)

    def _pick_look(self, motion: str) -> None:
        self._look["pick"] = motion
        self.mode = "봄"
        self.target = None
        self._ret = None
        self._walk_clip = None
        self._play(motion, 3600, busy=True, restart=True)

    def _end_look(self) -> None:
        """커서 상호작용을 접는다 (커서가 갔거나 다른 상호작용이 이겼다)."""
        was = self._look is not None and self._look.get("pick")
        self._look = None
        if self.mode == "봄":
            self.mode = ""
        if was and self.motion in LOOKS:
            self.busy = False
            self.until = 0

    def _hovering(self, px: float, py: float, cx: float, cy: float, now: float) -> bool:
        """커서가 몸 위에 HOVER_SEC 넘게 거의 가만히 있었나."""
        if abs(px - cx) > self.w / 2 + 2 or abs(py - cy) > self.height / 2 + 2:
            self._hover = None
            return False
        h = self._hover
        if h is None or abs(px - h[1]) > HOVER_STILL or abs(py - h[2]) > HOVER_STILL:
            self._hover = (now, px, py)
            return False
        if now - h[0] >= HOVER_SEC:
            self._hover = None
            return True
        return False

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
    def set_away(self, away: bool, woke: bool = False) -> None:
        """`woke` 는 자리비움 중에 캐릭터를 눌러 돌아왔다 (화들짝 깬 뒤 반긴다)."""
        if away:
            if self.mode in ("기절", "끌림", "날기", "던짐", "앉음", "냠냠"):
                return  # 지금 손에 잡혀 있거나 뻗어 있거나 바 밖이다. 다음에 앱이 다시 알려 준다
            self._ret = None
            self._clear_yum()
            self._peek = None
            self._end_look()
            self.mode = "자리비움"
            self.held = False
            self.busy = False
            self.until = 0
            self.target = None
            return
        if self.mode != "자리비움":
            return
        self.mode = ""
        self._touched = self.now()
        self.target = None
        if woke:  # 눌러서 깨웠다: 깸 하나 (반기기는 안 잇는다, 1모션)
            self._wake()
            return
        welcome = "점프" if pack.own(self.name, "점프", self.root) else "인사"
        self.vy += POKE_VY
        self._play(welcome, WELCOME_SEC, busy=True)

    # -------------------------------------------------- 사용량
    def set_mood(self, mood: str) -> None:
        if mood == self._mood:
            return
        self._mood = mood
        if self.mode or self._interacting():  # 상호작용 중이면 그 일을 마친 뒤 새 기분으로
            return
        self.target = None
        self.until = 0  # 지금 동작을 끊고 새 분위기로 바로 다시 고른다
        self.busy = False

    def _interacting(self) -> bool:
        """누르기 반응처럼 mode 없이 도는 상호작용 그림을 트는 중인가."""
        return ((self.busy and self.motion in pack.INTERACT) or self._tap_wait is not None or self._pending is not None
                or self.held)

    def celebrate(self) -> None:
        if self.mode or self._interacting():
            return
        self.vy += POKE_VY * 1.3
        self.target = None
        self._play("축하", 2.6, busy=True)

    # -------------------------------------------------- 그림
    def _raw_for(self, clip: pack.Clip, flip: bool, big: float = 1.0) -> tuple[list, int]:
        """후보 → ([(PIL RGBA, ms)], 되감을 자리), 바 높이에 맞춘 것 (굽기는 한 번만).
        `big` 은 떠 있는 창에 크게 태울 배수 (끄는 동안 `CARRY_K`, 나는 동안 `TOSS_K`)."""
        key = ("raw", clip.key, flip, big)
        if key not in self._cache:
            from PIL import Image
            k = float(big or 1.0)
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
                    big: float = 1.0) -> tuple[list, int]:
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
        """지금 그림에서 새 그림으로 부드럽게 바뀌게 장면 몇 장을 앞에 붙인다(평소 그림만).
        옛 그림이 옅어진 뒤 새 그림이 짙어진다. ★ 두 그림을 한 장에 겹쳐 섞지 않는다: 섞으면 옛 그림
        윤곽이 새 그림 위에 비쳐 잔상으로 보인다(11-21 사용자)."""
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

            def faint(im, t):
                out = im.copy()
                out.putalpha(im.getchannel("A").point(lambda v: int(v * t)))
                return out

            a, b = on_board(a), on_board(b)
            mixed = [(ImageTk.PhotoImage(faint(a if i < FADE_OUT else b, t), master=self.c), FADE_MS)
                     for i, t in enumerate(FADE)]
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
        # 상호작용은 빌린 그림이어도 늘 같은 것 (누를 때마다 다른 그림이 나오지 않게)
        clip = pack.pick_clip(self.name, motion, self.root, avoid=self._avoid(motion),
                              stable=motion in pack.INTERACT)
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
        if self.mode == "빼꼼" and self._peek is not None:  # 숨었다 내다봤다 (누를 때까지)
            self._peek_step()
            return
        if self.mode == "자리비움" or self._mood in ("잠", "오류"):
            if abs(self.x - self.home_x) > 2:
                self.target = self.home_x
            elif self.mode == "자리비움":
                self._play("자리비움", 3.0)
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
        r = random.random()
        if now - self._touched > bored and r < 0.2 and pack.own(self.name, "딴짓", self.root):
            self._show("딴짓", self._want("딴짓", idle))
        elif r < 0.2 + wave and pack.own(self.name, "인사", self.root):
            self._show("인사", self._want("인사", idle))
        elif r < 0.2 + wave + stroll and hi > lo:
            if random.random() < PUSH_P:  # 왼쪽 끝 사용량 막대까지 가서 밀어 본다
                self.target = lo
                self._push_next = True
            else:
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

    def _faint(self, motion: str = "기절") -> None:
        """흔들려 어지러운 채로 놓였다(휠을 너무 돌렸다): 그 자리에서. 기절은 뻗었다가(헤롱 장면이면
        그 한 바퀴 비틀→쓰러짐→일어남만큼), 어질·헤롱은 `DIZZY_SEC` 비틀댄 뒤 돌아간다.
        잡혀 있던 그림 그대로 이어 간다 (같은 그림을 처음부터 다시 틀지 않는다)."""
        self.mode = "기절"
        self.held = False
        self.target = None
        self._ret = None
        self._dizzy = False
        self._clear_yum()
        self._end_look()
        self._pending = self._tap_wait = self._hold_show = None
        if motion != "기절":
            self._play(motion, DIZZY_SEC.get(motion, 1.0), busy=True)
            return
        self._play("기절", FAINT_SEC, busy=True, restart=self.motion != "기절")
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
        if self.mode == "끌림":  # 흔들기를 멈추면 단계가 천천히 내려온다 (헤롱 → 어질 → 끌림)
            before = self._stage
            self._set_stage(self._shake.level(now))
            dirty = dirty or before != self._stage
        if self._pending is not None and not self.held and not carry.button_down():
            self.tap_up()  # 뗀 것을 앱이 못 알렸다 (시험·창 전환). 받아 둔 누르기를 이제 정한다
        dirty = self._tap_settle(now) or self._hold_settle(now) or dirty
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
        if self._yum or self._hearts:
            dirty = self._float_texts(now) or dirty
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
                self.mode = ""  # 다른 그림(놀람 등)을 끼우지 않고 곧장 돌아가거나 평소로
                if abs(self.x - self.home_x) > 2:
                    self._go_home()
                else:
                    self.busy = False
                    self.until = 0
                dirty = True
        elif self.mode == "포기":
            if now >= self.until:  # 다시 기운을 차린다 (쌓인 짜증도 비운다)
                self.mode = ""
                self._annoy.reset()
                self.busy = False
                self.until = 0
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
                # 사용량 막대 끝에 닿았다: 민다 (가다가 다른 일로 끊겼다 다른 곳에 닿은 것은 아님)
                if self._push_next and not self.mode and abs(self.x - self._bounds()[0]) < 1:
                    self._face(-1)
                    self._play("밀기", PUSH_SEC, busy=True)
                self._push_next = False
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
        elif now >= self.until and self.mode != "봄":
            self.busy = False
            self._choose(now)
            dirty = True
        if self.mode in ("", "봄") and not self.held and self._pending is None and self._tap_wait is None:
            before = self.motion
            self._watch(now)  # 커서 자리 읽기는 가볍다 (쓰다듬기를 놓치지 않게 틱마다)
            dirty = dirty or before != self.motion
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
                    canvas.tag_raise(FX_TAG)  # 오르는 글자(「냠」·「♥」)는 그림 위에
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
        if self._big and self.mode == "끌림":
            big = CARRY_K
        elif self.mode in ("던짐", "울음"):
            big = self._fly_k
        else:
            big = 1.0
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
