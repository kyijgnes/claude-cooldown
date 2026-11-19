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
- 끌기: 캐릭터 위에서 눌러 끌면 **창이 아니라 캐릭터가** 위젯 안에서 마우스를 따라간다(끌림).
  놓으면 떨어져 통통 튀며 제자리로 종종걸음쳐 돌아간다.
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
        self.path: str | None = None
        self.frames: list = []
        self.fi = 0
        self.left_ms = 0.0
        self.until = 0.0
        self.busy = False
        self.y = 0.0
        self.vy = 0.0
        self.held = False
        # 지금 하는 큰 일: "" 평소 · "기절" · "끌림" · "복귀"(놓아서 돌아가는 중) · "자리비움"
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
        if not self._hit(x, y):
            return False
        self._grab_off = (self.x - x, (self.y1 + self.y) - y)
        return True

    def drag(self, x: float | None, y: float | None) -> None:
        if x is None or y is None or self.mode == "기절":
            return
        if self.mode != "끌림":
            self.mode = "끌림"
            self.held = False
            self.target = None
            self._played = True
            self._play("끌림", 3600, busy=True)
        self._touched = self.now()
        cw, ch = self._area()
        lo, hi = self.w / 2, cw - self.w / 2
        nx = x + self._grab_off[0]
        nx = min(max(nx, lo), hi) if hi > lo else nx
        if abs(nx - self.x) > 0.5:
            self._face(1 if nx > self.x else -1)
        self.x = nx
        bottom = y + self._grab_off[1]
        bottom = min(max(bottom, float(self.height)), float(ch))
        self.y = bottom - self.y1
        self.vy = 0.0
        self._dirty = True

    def put_down(self) -> None:
        if self.mode != "끌림":
            return
        self.mode = "복귀"
        self.busy = False
        self.until = 0
        self.target = self.home_x
        # 멀리 끌었으면 그만큼 빨리 걸어 RETURN_SEC 안에 닿는다
        ticks = RETURN_SEC * 1000 / TICK_MS
        self._speed = max(RETURN_MIN, abs(self.home_x - self.x) / ticks)

    # -------------------------------------------------- 자리비움 (PC 입력 없음)
    def set_away(self, away: bool) -> None:
        if away:
            if self.mode in ("기절", "끌림"):
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
    def _frames_for(self, path: str, flip: bool) -> list:
        key = (path, flip)
        if key not in self._cache:
            from PIL import Image, ImageTk
            try:
                raw = pack.load_frames(path, self.height, width=self.max_w)
            except Exception:  # 깨진 그림 하나 때문에 위젯이 죽으면 안 된다
                raw = []
            if flip:
                raw = [(im.transpose(Image.FLIP_LEFT_RIGHT), ms) for im, ms in raw]
            self._cache[key] = [(ImageTk.PhotoImage(im, master=self.c), ms) for im, ms in raw]
        return self._cache[key]

    def _refresh_frames(self) -> None:
        if self.path:
            self.frames = self._frames_for(self.path, (self.dir > 0) != self.right)
            if self.frames:
                self.w = self.frames[0][0].width()

    def _play(self, motion: str, seconds: float | None = None, busy: bool = False) -> None:
        path = pack.pick(self.name, motion, self.root,
                         avoid=self.path if motion == self.motion else None)
        if path is None:
            return
        if path != self.path or motion != self.motion:
            self.path, self.motion = path, motion
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
        if x is None or y is None:
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
            self.fi = (self.fi + 1) % len(self.frames)
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
                if under:
                    canvas.tag_lower(item)  # 알림 칸에서는 글자 아래에 깐다
                else:
                    canvas.tag_raise(item)
            except tk.TclError:
                pass
