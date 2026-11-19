"""
바 캐릭터 — 클로디 자리에 사용자가 고른 캐릭터 **한 명**을 세운다.

그림은 `cooldown_pack`(사용자 PC 의 `~/.claude_cooldown_pack/<캐릭터>/<동작>/`), 고른 한 명은
`cooldown_pack.active()`. 클로디(`claudi.py`)와 같은 약속(`home`·`start`·`react`·`hold`·`let_go`·
`absorbed`·`to_local`·`on_morph`·`unmorph`)을 지켜서 스킨은 `self.claudi` 이름 그대로 부른다.

- 바 본체 캔버스와 **알림 칸 캔버스(`mirror`)에 같은 그림을 겹쳐 그린다.** 알림 칸은 tk 의 따로 된
  캔버스라 본체 그림이 그 밑으로 숨기 때문이다. 알림 칸에서는 그림을 글자 **아래**에 깔고, 글자는
  스킨이 바탕색 테두리를 둘러 읽히게 한다(11-20 사용자 지시: 알림과 조금 겹쳐도 됨, 대신 구분되게).
- 집(`home`)에서 주로 쉬고, 이따금 상자 안을 조금 거닐다 돌아온다. 오래 가만두면 딴짓, 가끔 손 흔들기(인사).
- 누르면 폴짝 뛰며 놀람, 길게 누르면 눌림, 놓으면 튀어 오름.
- 사용량: 80% 넘으면 허둥지둥 오가고, 한도면 집에서 잠, 5시간 한도가 풀리면 축하, 오류면 집에서 섬.
"""

from __future__ import annotations

import random
import time
import tkinter as tk

import cooldown_pack as pack

TICK_MS = 40
WALK = 0.45
HURRY = 1.3
POKE_VY = -5.0
SPRING_K = 0.25
SPRING_DAMP = 0.7
IDLE_MIN, IDLE_MAX = 2.5, 7.0  # 한 번 쉬는 시간 (초)
STROLL = 0.35  # 쉬다가 거닐러 나갈 확률
WAVE = 0.12  # 쉬다가 손 흔들 확률
BORED_AFTER = 40.0  # 아무도 안 건드린 지 이만큼이면 가끔 딴짓
EVENT_MIN, EVENT_MAX = 0.9, 4.0
TAG = "buddy"


class Buddy:
    def __init__(self, canvas: tk.Canvas, box: tuple[float, float, float, float],
                 name: str, max_w: int | None = None, root: str = pack.PACK_DIR):
        self.c = canvas
        self.root = root
        self.name = name
        self.x0, self.y0, self.x1, self.y1 = box
        self.height = max(16, int(self.y1 - self.y0) - 2)
        self.max_w = max_w or int(self.height * 1.4)
        self.right = pack.faces_right(name, root)
        self.on_morph = None  # 앱이 걸어 두지만 쓰지 않는다 (공룡 변신 없음)
        self.mirror: tk.Canvas | None = None  # 알림 칸 — 같은 그림을 겹쳐 그린다
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
        self.w = self.height
        self._mood = "여유"
        self._cache: dict = {}
        self._played = False
        self._gen = 0
        self._touched = time.monotonic()
        self._items: dict = {}

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
        self._play("서기", random.uniform(IDLE_MIN, IDLE_MAX))
        self._gen += 1
        self._last = time.monotonic()
        self._tick(self._gen)

    def absorbed(self) -> bool:
        played, self._played = self._played, False
        return played

    def react(self, x: float | None = None, y: float | None = None) -> None:
        if not self._hit(x, y):
            return
        self._played = True
        self._touched = time.monotonic()
        self.vy += POKE_VY
        self.target = None
        self._play("놀람", busy=True)

    def hold(self, x: float, y: float) -> None:
        if not self._hit(x, y):
            return
        self._played = True
        self._touched = time.monotonic()
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

    # -------------------------------------------------- 사용량
    def set_mood(self, mood: str) -> None:
        if mood == self._mood:
            return
        self._mood = mood
        self.target = None
        self.until = 0  # 지금 동작을 끊고 새 분위기로 바로 다시 고른다
        self.busy = False

    def celebrate(self) -> None:
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
        self.until = time.monotonic() + seconds
        self.busy = busy

    def _face(self, d: int) -> None:
        if d and d != self.dir:
            self.dir = d
            self._refresh_frames()

    def _hit(self, x, y) -> bool:
        if x is None or y is None:
            return False
        bottom = self.y1 + self.y
        return abs(x - self.x) <= self.w / 2 + 2 and bottom - self.height - 2 <= y <= bottom + 2

    # -------------------------------------------------- 움직임
    def _bounds(self) -> tuple[float, float]:
        return self.x0 + self.w / 2, self.x1 - self.w / 2

    def _choose(self, now: float) -> None:
        lo, hi = self._bounds()
        if self._mood == "잠":
            if abs(self.x - self.home_x) > 2:
                self.target = self.home_x
            else:
                self._play("잠", 3.0)
            return
        if self._mood == "오류":
            if abs(self.x - self.home_x) > 2:
                self.target = self.home_x
            else:
                self._play("서기", 2.0)
            return
        if self._mood == "허둥" and hi > lo:  # 허둥댈 땐 쉬지 않고 오간다
            self.target = random.uniform(lo, hi)
            return
        if abs(self.x - self.home_x) > 2 and random.random() < 0.5:
            self.target = self.home_x  # 거닐다가 집으로 돌아온다
            return
        r = random.random()
        if now - self._touched > BORED_AFTER and r < 0.2 and pack.clips(self.name, "딴짓", self.root):
            self._play("딴짓", busy=True)
        elif r < 0.2 + WAVE and pack.clips(self.name, "인사", self.root):
            self._play("인사", busy=True)
        elif r < 0.2 + WAVE + STROLL and hi > lo:
            self.target = random.uniform(lo, hi)
        else:
            self._play("서기", random.uniform(IDLE_MIN, IDLE_MAX))

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

    def _tick(self, gen: int) -> None:
        if gen != self._gen or not self.c.winfo_exists():
            return
        now = time.monotonic()
        dt = (now - self._last) * 1000
        self._last = now
        dirty = self._advance(dt)
        if abs(self.y) > 0.05 or abs(self.vy) > 0.05:
            self.vy = (self.vy - self.y * SPRING_K) * SPRING_DAMP
            self.y = max(self.y + self.vy, -(self.y1 - self.y0) * 0.35)
            dirty = True
        speed = HURRY if self._mood == "허둥" else WALK
        if self.held:
            pass
        elif self.target is not None and not self.busy:
            d = self.target - self.x
            if abs(d) <= speed:
                self.x, self.target = self.target, None
                self.until = 0
            else:
                self._face(1 if d > 0 else -1)
                walk = "허둥" if self._mood == "허둥" and pack.clips(self.name, "허둥", self.root) else "걷기"
                if self.motion != walk:
                    self._play(walk, 60)
                self.x += speed if d > 0 else -speed
            dirty = True
        elif now >= self.until:
            self.busy = False
            self._choose(now)
            dirty = True
        if dirty or not self._items:
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
