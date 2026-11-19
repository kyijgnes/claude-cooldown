"""
캐릭터 마당 — 작업표시줄 바 오른쪽 마당 칸에서 캐릭터 여럿이 따로 놀고 서로 반응한다.

그림은 `cooldown_pack`(사용자 PC 의 `~/.claude_cooldown_pack/<캐릭터>/<동작>/`).
클로디(`claudi.py`)와 같은 약속(`home`·`start`·`react`·`hold`·`let_go`·`absorbed`·`to_local`·
`on_morph`·`unmorph`)을 지켜서 스킨은 `self.claudi` 이름 그대로 부른다. 공룡 변신은 없다.

하는 일
- 각자 걷다 멈추고(서기), 오래 서 있으면 딴짓을 한다. 걷는 쪽으로 그림을 뒤집는다.
- 둘이 마주치면 멈춰 서로 보고 인사한다(같은 짝은 `MEET_COOLDOWN` 동안 다시 안 함).
- 하나를 누르면 폴짝 뛰며 놀라고, 옆 친구들이 그쪽을 돌아보며 놀란다.
- 길게 누르면 눌려 있다가 놓으면 튀어 오른다.
- 사용량: 80% 넘으면 허둥지둥 빨리 다니고, 한도가 차면 가운데로 모여 잔다.
  5시간 한도가 풀리면 다 같이 폴짝 뛰며 축하한다. 연결이 끊기면 그 자리에 선다.
"""

from __future__ import annotations

import random
import time
import tkinter as tk

import cooldown_pack as pack

TICK_MS = 40
WALK = 0.55  # 걷는 속도 (px/걸음)
HURRY = 1.5  # 허둥댈 때 걷는 속도
POKE_VY = -5.0
SPRING_K = 0.25
SPRING_DAMP = 0.7
MEET_COOLDOWN = 18.0  # 같은 짝이 다시 인사하기까지 (초)
LOOK_RANGE = 2.2  # 눌린 친구를 돌아보는 거리 (그림 높이의 배)
IDLE_MIN, IDLE_MAX = 1.5, 5.0  # 한 번 서 있는 시간 (초)
BORED_AFTER = 40.0  # 아무도 안 건드린 지 이만큼이면 가끔 딴짓
EVENT_MIN, EVENT_MAX = 0.9, 4.0  # 잠깐 동작 길이 범위 (초)
TAG = "yard"


class Actor:
    """마당의 캐릭터 하나."""

    def __init__(self, yard: Yard, name: str, x: float):
        self.yard = yard
        self.name = name
        self.right = pack.faces_right(name, yard.root)
        self.x = x
        self.dir = random.choice((-1, 1))
        self.target: float | None = None
        self.motion = ""
        self.path: str | None = None
        self.frames: list = []
        self.fi = 0
        self.left_ms = 0.0
        self.until = 0.0  # 이 시각까지 지금 동작을 유지 (잠깐 동작·서기)
        self.busy = False  # 잠깐 동작 중이면 참 (걷기·인사로 안 끊긴다)
        self.y = 0.0
        self.vy = 0.0
        self.held = False
        self.item = None
        self.w = yard.height  # 그림을 읽으면 실제 폭으로 바뀐다

    # ---- 그림
    def play(self, motion: str, seconds: float | None = None, busy: bool = False) -> None:
        """동작 하나를 튼다. seconds 를 주면 그 뒤 풀린다(없으면 그림 한 바퀴)."""
        path = pack.pick(self.name, motion, self.yard.root,
                         avoid=self.path if motion == self.motion else None)
        if path is None:
            return
        if path != self.path or motion != self.motion:
            self.path, self.motion = path, motion
            self.frames, self.fi = self._frames(), 0
            self.left_ms = self.frames[0][1] if self.frames else 200
        if seconds is None:
            total = sum(ms for _, ms in self.frames) / 1000 if len(self.frames) > 1 else 1.6
            seconds = max(EVENT_MIN, min(EVENT_MAX, total))
        self.until = time.monotonic() + seconds
        self.busy = busy

    def face(self, d: int) -> None:
        if d and d != self.dir:
            self.dir = d
            self.frames = self._frames()

    def _frames(self) -> list:
        if self.path is None:
            return []
        flip = (self.dir > 0) != self.right
        frames = self.yard.frames(self.path, flip)
        if frames:
            self.w = frames[0][0].width()
        return frames

    def image(self):
        return self.frames[self.fi % len(self.frames)][0] if self.frames else None

    def advance(self, ms: float) -> bool:
        """그림 프레임을 넘긴다. 넘겼으면 참."""
        if len(self.frames) < 2:
            return False
        self.left_ms -= ms
        moved = False
        while self.left_ms <= 0:
            self.fi = (self.fi + 1) % len(self.frames)
            self.left_ms += self.frames[self.fi][1]
            moved = True
        return moved

    def hit(self, x: float, y: float) -> bool:
        y1 = self.yard.y1 + self.y
        return abs(x - self.x) <= self.w / 2 + 2 and y1 - self.yard.height - 2 <= y <= y1 + 2


class Yard:
    def __init__(self, canvas: tk.Canvas, box: tuple[float, float, float, float],
                 root: str = pack.PACK_DIR):
        self.c = canvas
        self.root = root
        self.x0, self.y0, self.x1, self.y1 = box
        self.height = max(16, int(self.y1 - self.y0) - 2)
        self.max_w = int(self.height * 1.6)
        self.on_morph = None  # 앱이 걸어 두지만 쓰지 않는다
        self._cache: dict = {}
        self._played = False
        self._gen = 0
        self._mood = "여유"
        self._met: dict = {}
        self._touched = time.monotonic()
        names = pack.characters(root)
        span = (self.x1 - self.x0) / (len(names) + 1)
        self.actors = [Actor(self, n, self.x0 + span * (i + 1)) for i, n in enumerate(names)]

    # -------------------------------------------------- 약속
    def home(self, cx: float, cy: float | None = None) -> None:
        pass

    def to_local(self, widget: tk.Misc, x: float | None, y: float | None):
        if x is None or y is None:
            return None, None
        top = self.c.winfo_toplevel()
        return (x - (self.c.winfo_rootx() - top.winfo_rootx()),
                y - (self.c.winfo_rooty() - top.winfo_rooty()))

    def start(self) -> None:
        for a in self.actors:
            a.play("서기", random.uniform(IDLE_MIN, IDLE_MAX))
        self._gen += 1
        self._last = time.monotonic()
        self._tick(self._gen)

    def absorbed(self) -> bool:
        played, self._played = self._played, False
        return played

    def react(self, x: float | None = None, y: float | None = None) -> None:
        a = self._at(x, y)
        if a is None:
            return
        self._played = True
        self._touched = time.monotonic()
        a.vy += POKE_VY
        a.target = None
        a.play("놀람", busy=True)
        self._raise(a)
        # 옆 친구들이 돌아보며 놀란다 (조금 늦게 — 소리를 듣고 돌아보는 것처럼)
        for b in self.actors:
            if b is not a and abs(b.x - a.x) <= self.height * LOOK_RANGE and not b.held:
                self.c.after(160, lambda b=b, a=a: self._startle(b, a))

    def hold(self, x: float, y: float) -> None:
        a = self._at(x, y)
        if a is None:
            return
        self._played = True
        self._touched = time.monotonic()
        a.held = True
        a.target = None
        a.play("눌림", 3600, busy=True)
        self._raise(a)

    def let_go(self) -> None:
        for a in self.actors:
            if a.held:
                a.held = False
                a.vy += POKE_VY * 1.2
                a.play("놀람", busy=True)

    def unmorph(self) -> None:
        pass

    # -------------------------------------------------- 사용량
    def set_mood(self, mood: str) -> None:
        if mood == self._mood:
            return
        self._mood = mood
        for a in self.actors:
            a.target = None
            a.until = 0  # 지금 동작을 끊고 새 분위기로 바로 다시 고른다
            a.busy = False

    def celebrate(self) -> None:
        for i, a in enumerate(self.actors):
            self.c.after(i * 140, lambda a=a: self._cheer(a))

    def _cheer(self, a: Actor) -> None:
        a.vy += POKE_VY * 1.3
        a.target = None
        a.play("축하", 2.6, busy=True)

    # -------------------------------------------------- 속
    def frames(self, path: str, flip: bool) -> list:
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

    def _at(self, x, y) -> Actor | None:
        if x is None or y is None:
            return None
        hits = [a for a in self.actors if a.hit(x, y)]
        return min(hits, key=lambda a: abs(a.x - x)) if hits else None

    def _startle(self, b: Actor, a: Actor) -> None:
        if b.held:
            return
        b.face(1 if a.x > b.x else -1)
        b.target = None
        b.play("놀람", 1.0, busy=True)

    def _raise(self, a: Actor) -> None:
        if a.item is not None:
            self.c.tag_raise(a.item)

    def _bounds(self, a: Actor) -> tuple[float, float]:
        return self.x0 + a.w / 2 + 1, self.x1 - a.w / 2 - 1

    def _choose(self, a: Actor, now: float) -> None:
        """지금 동작이 끝났다 — 분위기에 맞춰 다음 할 일을 고른다."""
        lo, hi = self._bounds(a)
        if self._mood == "잠":
            spot = self._sleep_spot(a)
            if abs(a.x - spot) > 2:
                a.target = spot
            else:
                a.play("잠", 3.0)
            return
        if self._mood == "오류":
            a.play("서기", 2.0)
            return
        if (now - self._touched > BORED_AFTER and random.random() < 0.25
                and pack.clips(a.name, "딴짓", self.root)):
            a.play("딴짓", busy=True)
            return
        if self._mood == "허둥" and hi > lo:  # 허둥댈 땐 서 있지 않고 계속 뛰어다닌다
            a.target = random.uniform(lo, hi)
            return
        if random.random() < 0.6 and hi > lo:
            a.target = random.uniform(lo, hi)
        else:
            a.play("서기", random.uniform(IDLE_MIN, IDLE_MAX))

    def _sleep_spot(self, a: Actor) -> float:
        """한도가 차면 가운데로 모여 나란히 잔다."""
        n = len(self.actors)
        i = self.actors.index(a)
        mid = (self.x0 + self.x1) / 2
        gap = self.height * 0.75
        lo, hi = self._bounds(a)
        return max(lo, min(hi, mid + (i - (n - 1) / 2) * gap))

    def _meet(self, now: float) -> None:
        """걷던 둘이 부딪칠 만큼 가까우면 멈춰 서로 보고 인사한다."""
        for i, a in enumerate(self.actors):
            for b in self.actors[i + 1:]:
                if a.busy or b.busy or a.held or b.held or self._mood != "여유":
                    continue
                if a.target is None and b.target is None:
                    continue  # 둘 다 서 있으면 그냥 둔다
                if abs(a.x - b.x) > (a.w + b.w) / 2 * 0.85:
                    continue
                key = (a.name, b.name)
                if now - self._met.get(key, -1e9) < MEET_COOLDOWN:
                    continue
                self._met[key] = now
                for me, you in ((a, b), (b, a)):
                    me.target = None
                    me.face(1 if you.x > me.x else -1)
                    me.play("인사", 1.8, busy=True)

    def _tick(self, gen: int) -> None:
        if gen != self._gen or not self.c.winfo_exists():
            return
        now = time.monotonic()
        dt = (now - self._last) * 1000
        self._last = now
        self._meet(now)
        speed = HURRY if self._mood == "허둥" else WALK
        for a in self.actors:
            dirty = a.advance(dt)
            # 폴짝 (용수철)
            if abs(a.y) > 0.05 or abs(a.vy) > 0.05:
                a.vy = (a.vy - a.y * SPRING_K) * SPRING_DAMP
                a.y = max(a.y + a.vy, -(self.y1 - self.y0) * 0.35)
                dirty = True
            if a.held:
                pass
            elif a.target is not None and not a.busy:
                d = a.target - a.x
                if abs(d) <= speed:
                    a.x, a.target = a.target, None
                    a.until = 0
                else:
                    a.face(1 if d > 0 else -1)
                    walk = "허둥" if self._mood == "허둥" and pack.clips(a.name, "허둥", self.root) else "걷기"
                    if a.motion != walk:
                        a.play(walk, 60)
                    a.x += speed if d > 0 else -speed
                dirty = True
            elif now >= a.until:
                a.busy = False
                self._choose(a, now)
                dirty = True
            if dirty or a.item is None:
                self._draw(a)
        self.c.after(TICK_MS, lambda: self._tick(gen))

    def _draw(self, a: Actor) -> None:
        img = a.image()
        if img is None:
            return
        x, y = a.x, self.y1 + a.y + (2 if a.held else 0)
        if a.item is None or not self.c.type(a.item):
            a.item = self.c.create_image(x, y, image=img, anchor="s", tags=TAG)
        else:
            self.c.itemconfigure(a.item, image=img)
            self.c.coords(a.item, x, y)
