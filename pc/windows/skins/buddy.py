"""
바 캐릭터: 클로디 자리에 사용자가 고른 캐릭터 **한 명**을 세운다.

그림은 `cooldown_pack`(사용자 PC 의 `~/.claude_cooldown_pack/<캐릭터>/<동작>/`), 고른 한 명은
`cooldown_pack.active()`. 클로디(`claudi.py`)와 같은 약속(`home`·`start`·`react`·`hold`·`let_go`·
`absorbed`·`to_local`·`on_morph`·`unmorph`, 11-20 부터 `catch`·`drag`·`drop`·`set_away`·
`set_mood`·`celebrate`)을 지켜서 스킨은 `self.claudi` 이름 그대로 부른다.

- 바 본체 캔버스와 **알림 칸 캔버스(`mirror`)에 같은 그림을 겹쳐 그린다.** 알림 칸은 tk 의 따로 된
  캔버스라 본체 그림이 그 밑으로 숨기 때문이다. 알림 칸에서는 그림을 글자 **아래**에 깔고, 글자는
  스킨이 바탕색 테두리를 둘러 읽히게 한다(11-20 사용자 지시: 알림과 조금 겹쳐도 됨, 대신 구분되게).

상호작용(11-20 사용자: 마당 없이 한 명이니 손에 닿는 반응이 중요하다)
- 누르기: 폴짝 놀람. 자꾸 누르면 짜증 → 화남 → 포기(`base.Annoy`, 포기하면 `GIVEUP_SEC` 동안 축 처져
  아무 반응 안 하다 회복). 안 누르면 단계가 서서히 내려간다. (옛 「연타 기절」은 없앴다)
- 길게 누르기: 눌림이 이어지다 놓으면 튕겨 오른다.
- 끌기: 캐릭터 위에서 눌러 끌면 **창이 아니라 캐릭터가** 마우스를 따라간다(끌림). 끄는 동안은 투명한
  맨 위 작은 창(`carry.Carry`)에 타서 화면 어디로든 가고 바 안 제자리는 빈다. 놓은 자리가 바 위면
  거기 내려앉아 통통 튀며 뛰어서, 바 밖이면 곧은 줄로 미끄러지듯(`carry.Flight`, 뛰기 그림이 있으면
  뛰기를 틀며) 제자리로 온다. **끄는 동안 마구 흔들면**(`base.Shake`) 놓은 뒤 헤롱헤롱 기절한다.
- 그림: 후보(`pack.pick_clip`) 하나 = 그림 한 장(고정 그림은 효과를 구워 움직인다) 또는 이어 붙이기 묶음.
  평소 동작은 후보가 많으면 최근에 튼 절반은 피해 고른다(`_avoid`).
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

from . import carry
from .base import Annoy, Shake

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
RETURN_SEC = 1.4    # 놓은 뒤 이 시간 안에 제자리로 (멀리 끌었으면 그만큼 빨리 걷는다)
RETURN_MIN = 1.2    # 돌아가는 걸음의 가장 느린 속도 (px/틱)
WIDE_FX = ("쓰러짐", "빙글")  # 옆으로 눕거나 도는 효과는 폭을 더 준다 (안 주면 작아진다)
WIDE_K = 1.7
TAG = "buddy"

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
        self._speed = RETURN_MIN
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
        if self.mode in ("기절", "포기"):  # 뻗어 있거나 체념한 동안은 받기만 하고 아무 일 없음
            return
        if self.mode == "자리비움":  # 누른 사람이 곧 돌아온 사람이다
            self.set_away(False)
            return
        stage = self._annoy.tap(now)
        if stage >= 3:
            self._give_up()
            return
        self.vy += POKE_VY * (1.0, 0.6, 0.35)[stage]
        self.target = None
        self.mode = "" if self.mode == "복귀" else self.mode
        self._play(("놀람", "짜증", "화남")[stage], busy=True)

    def _give_up(self) -> None:
        """자꾸 눌러 체념했다. 한동안 축 처져 아무 반응 안 하다 회복한다."""
        self.mode = "포기"
        self.held = False
        self.target = None
        self.vy = 0.0
        self._play("포기", GIVEUP_SEC, busy=True)

    def hold(self, x: float, y: float) -> None:
        if self.mode in ("기절", "끌림", "자리비움", "포기") or not self._hit(x, y):
            return
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
            self.mode = "끌림"
            self.held = False
            self.target = None
            self._played = True
            self._shake.reset()
            self._play("끌림", 3600, busy=True)
        self._touched = self.now()
        nx, bottom = x + self._grab_off[0], y + self._grab_off[1]
        self._shake.feed(nx, bottom, self._touched)
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
            w = int(self.max_w * WIDE_K) + 8
            h = self.height + 12
            self._carry = carry.Carry(self.c, w, h, (w / 2, h - 4))
        except tk.TclError:
            self._carry = None

    def _land(self) -> None:
        if self._carry is not None:
            self._carry.close()
        self._carry = None
        self._flight = None
        self._dirty = True

    def put_down(self) -> None:
        if self.mode != "끌림":
            return
        nx, bottom = self._held_at
        dizzy = self._shake.dizzy(self.now())
        self._shake.reset()
        if self._carry is None or carry.inside(self.c, nx, bottom - self.height / 2):
            # 바 위에 놓았다: 그 자리에 내려앉아 통통 튀고 제자리로 뛰어간다 (흔들렸으면 그 자리에서 기절)
            self._land()
            cw, ch = self._area()
            lo, hi = self.w / 2, cw - self.w / 2
            self.x = min(max(nx, lo), hi) if hi > lo else nx
            self.y = min(max(bottom, float(self.height)), float(ch)) - self.y1
            if dizzy:
                self._faint()
            else:
                self._go_home()
            return
        # 바 밖에 놓았다: 그 자리에서 제자리로 곧은 줄을 따라 미끄러지듯 온다
        self.mode = "날기"
        self.target = None
        self._dizzy = dizzy
        try:
            start = self._carry.at
            end = carry.screen_of(self.c, self.home_x, self.y1)
        except tk.TclError:
            self._land()
            self.mode = ""
            return
        self._flight = carry.Flight(start, end, self.now())
        if end[0] != start[0]:
            self._face(1 if end[0] > start[0] else -1)
        if not dizzy and pack.own(self.name, "뛰기", self.root):
            self._play("뛰기", 60, busy=True)  # 떠 있는 동안 뛰는 시늉

    def _go_home(self) -> None:
        """놓인 자리에서 제자리로 뛰어간다(멀리 있으면 그만큼 빨리 뛰어 RETURN_SEC 안에 닿는다)."""
        self.mode = "복귀"
        self.busy = False
        self.until = 0
        self.target = self.home_x
        ticks = RETURN_SEC * 1000 / TICK_MS
        self._speed = max(RETURN_MIN, abs(self.home_x - self.x) / ticks)

    # -------------------------------------------------- 자리비움 (PC 입력 없음)
    def set_away(self, away: bool) -> None:
        if away:
            if self.mode in ("기절", "끌림", "날기"):
                return  # 지금 손에 잡혀 있거나 뻗어 있다. 다음에 앱이 다시 알려 준다
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
        self.until = 0  # 지금 동작을 끊고 새 분위기로 바로 다시 고른다
        self.busy = False

    def celebrate(self) -> None:
        if self.mode:
            return
        self.vy += POKE_VY * 1.3
        self.target = None
        self._play("축하", 2.6, busy=True)

    # -------------------------------------------------- 그림
    def _raw_for(self, clip: pack.Clip, flip: bool) -> tuple[list, int]:
        """후보 → ([(PIL RGBA, ms)], 되감을 자리), 바 높이에 맞춘 것 (굽기는 한 번만)."""
        key = ("raw", clip.key, flip)
        if key not in self._cache:
            from PIL import Image
            width = int(self.max_w * (WIDE_K if clip.effect in WIDE_FX else 1))
            try:
                raw, loop_from = pack.load_clip(clip, self.height, width)
            except Exception:  # 깨진 그림 하나 때문에 위젯이 죽으면 안 된다
                raw, loop_from = [], 0
            if flip:
                raw = [(im.transpose(Image.FLIP_LEFT_RIGHT), ms) for im, ms in raw]
            self._cache[key] = (raw, loop_from)
        return self._cache[key]

    def _frames_for(self, clip: pack.Clip, flip: bool, solid: bool = False) -> tuple[list, int]:
        """후보 → ([(PhotoImage, ms)], 되감을 자리). `solid` 는 떠 있는 창에 태울 그림(알파 반 자름)."""
        key = (clip.key, flip, solid)
        if key not in self._cache:
            from PIL import ImageTk
            raw, loop_from = self._raw_for(clip, flip)
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
        if self.mode == "복귀":
            if abs(self.x - self.home_x) > 2:
                self.target = self.home_x
            else:
                self.mode = ""
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
        if self.mode == "복귀":
            return self._speed
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
        self._dizzy = False
        self._play("기절", FAINT_SEC, busy=True, restart=True)
        if self.clip is not None and self.clip.effect == "헤롱" and self._cycle() > 0:
            self.until = self.now() + self._cycle()

    def step(self, now: float | None = None) -> bool:
        """한 틱. 그릴 게 바뀌었으면 참. 앱은 `_tick` 으로 40ms 마다, 시험은 직접 부른다."""
        now = self.now() if now is None else now
        dt = (now - self._last) * 1000
        self._last = now
        dirty = self._advance(dt)
        if self.mode == "끌림" and self._carry is not None and not carry.button_down():
            self.put_down()  # 놓은 것을 앱이 못 받았다 (창 전환 등). 떠 있는 채로 남지 않게
        if self.mode == "날기":
            return self._fly(now)
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
            if now >= self.until:  # 다시 기운을 차린다 (쌓인 짜증도 비운다)
                self.mode = ""
                self._annoy.reset()
                self.busy = False
                self.until = 0
                dirty = True
        elif self.mode == "끌림" or self.held:
            pass
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
        frames, _ = self._frames_for(self.clip, self._flip(), solid=True) if self.clip else ([], 0)
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
