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
- 누르기: 폴짝 놀람. **2초 안에 6번**(`base.FAINT_TAPS`) 누르면 기절했다 깨어난다.
- 길게 누르기: 눌림이 이어지다 놓으면 튕겨 오른다.
- 끌기: 캐릭터 위에서 눌러 끌면 **창이 아니라 캐릭터가** 마우스를 따라간다(끌림). 끄는 동안은 투명한
  맨 위 작은 창(`carry.Carry`)에 타서 화면 어디로든 가고 바 안 제자리는 빈다. 놓은 자리가 바 위면
  거기 내려앉아 통통 튀며 종종걸음으로, 바 밖이면 포물선을 그리며 날아와(`carry.Flight`) 제자리에 선다.
- 그림: 후보(`pack.pick_clip`) 하나 = 그림 한 장(고정 그림은 효과를 구워 움직인다) 또는 이어 붙이기 묶음.
  평소 동작은 후보가 많으면 최근에 튼 절반은 피해 고른다(`_avoid`).
- 자리비움: PC 입력이 5분 없으면 집에서 자리비움 동작, 돌아오면 폴짝 반긴다(인사).
- 사용량 네 단계가 평소 동작에 늘 보인다: 여유(천천히, 자주 인사) · 보통(부지런히 거닒) ·
  허둥(80% 넘음, 쉬지 않고 오감) · 잠(한도). 5시간 한도가 풀리면 축하, 오류면 집에서 섬.

시험은 `pc/tests/test_buddy.py`: 시계를 `now` 로 바꿔 끼우고 `step(now)` 를 직접 돌린다.
"""

from __future__ import annotations

import random
import time
import tkinter as tk

import cooldown_pack as pack

from . import carry
from .base import TapCount

TICK_MS = 40
HURRY = 1.3
POKE_VY = -5.0
SPRING_K = 0.25
SPRING_DAMP = 0.7
EVENT_MIN, EVENT_MAX = 0.9, 4.0
FAINT_SEC = 2.6     # 기절해 있는 시간
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
        self._taps = TapCount()
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
        if self.mode == "기절":  # 뻗어 있는 동안은 받기만 하고 아무 일 없음
            return
        if self.mode == "자리비움":  # 누른 사람이 곧 돌아온 사람이다
            self.set_away(False)
            return
        if self._taps.tap(now):
            self._faint()
            return
        self.vy += POKE_VY
        self.target = None
        self.mode = "" if self.mode == "복귀" else self.mode
        self._play("놀람", busy=True)

    def hold(self, x: float, y: float) -> None:
        if self.mode in ("기절", "끌림", "자리비움") or not self._hit(x, y):
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
            self._play("끌림", 3600, busy=True)
        self._touched = self.now()
        nx, bottom = x + self._grab_off[0], y + self._grab_off[1]
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
        if self._carry is None or carry.inside(self.c, nx, bottom - self.height / 2):
            # 바 위에 놓았다: 그 자리에 내려앉아 통통 튀고 제자리로 종종걸음
            self._land()
            cw, ch = self._area()
            lo, hi = self.w / 2, cw - self.w / 2
            self.x = min(max(nx, lo), hi) if hi > lo else nx
            self.y = min(max(bottom, float(self.height)), float(ch)) - self.y1
            self.mode = "복귀"
            self.busy = False
            self.until = 0
            self.target = self.home_x
            # 멀리 끌었으면 그만큼 빨리 걸어 RETURN_SEC 안에 닿는다
            ticks = RETURN_SEC * 1000 / TICK_MS
            self._speed = max(RETURN_MIN, abs(self.home_x - self.x) / ticks)
            return
        # 바 밖에 놓았다: 그 자리에서 제자리로 날아온다
        self.mode = "날기"
        self.target = None
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
        self._play("인사", WELCOME_SEC, busy=True)

    # -------------------------------------------------- 사용량
    def set_mood(self, mood: str) -> None:
        if mood == self._mood:
            return
        self._mood = mood
        if self.mode:  # 기절·끌림·복귀·자리비움 중이면 그 일을 마친 뒤 새 기분으로
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

    def _avoid(self, motion: str) -> list:
        """최근에 튼 후보들 (피할 것). 후보가 n 개면 최근 n//2 개(적어도 하나는 남긴다)."""
        n = len(pack.candidates(self.name, motion, self.root))
        keep = max(0, min(n - 1, n // 2))
        return self._recent.get(motion, [])[-keep:] if keep else []

    def _play(self, motion: str, seconds: float | None = None, busy: bool = False) -> None:
        clip = pack.pick_clip(self.name, motion, self.root, avoid=self._avoid(motion))
        if clip is None:
            return
        if clip != self.clip or motion != self.motion:
            self.clip, self.motion = clip, motion
            hist = self._recent.setdefault(motion, [])
            hist.append(clip.key)
            del hist[:-pack.MAX_PER_MOTION]
            self._refresh_frames()
            self.fi = 0
            self.left_ms = self.frames[0][1] if self.frames else 200
        if seconds is None:
            total = sum(ms for _, ms in self.frames) / 1000 if len(self.frames) > 1 else 1.6
            seconds = max(EVENT_MIN, min(EVENT_MAX, total))
        self.until = self.now() + seconds
        self.busy = busy
        self._dirty = True

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
        if abs(self.x - self.home_x) > 2 and random.random() < 0.5:
            self.target = self.home_x  # 거닐다가 집으로 돌아온다
            return
        r = random.random()
        if now - self._touched > bored and r < 0.2 and pack.clips(self.name, "딴짓", self.root):
            self._play("딴짓", busy=True)
        elif r < 0.2 + wave and pack.clips(self.name, "인사", self.root):
            self._play("인사", busy=True)
        elif r < 0.2 + wave + stroll and hi > lo:
            self.target = random.uniform(lo, hi)
        else:
            self._play("서기", random.uniform(*idle))

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
        self.mode = "기절"
        self.held = False
        self.target = None
        self.vy = 0.0
        self._play("기절", FAINT_SEC, busy=True)

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
            if now >= self.until:  # 깨어난다: 털고 일어나 폴짝
                self.mode = ""
                self.vy += POKE_VY * 0.8
                self._play("놀람", busy=True)
                dirty = True
        elif self.mode == "끌림" or self.held:
            pass
        elif self.target is not None and not self.busy:
            d = self.target - self.x
            if abs(d) <= speed:
                self.x, self.target = self.target, None
                self.until = 0
                if self.mode == "복귀":
                    self.mode = ""
            else:
                self._face(1 if d > 0 else -1)
                walk = ("허둥" if self._mood == "허둥" and self.mode != "복귀"
                        and pack.clips(self.name, "허둥", self.root) else "걷기")
                if self.motion != walk:
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
        if done:
            self._land()
            self.mode = ""
            self.x, self.y = self.home_x, 0.0
            self.vy = POKE_VY * 0.7
            self._play("놀람", busy=True)
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
