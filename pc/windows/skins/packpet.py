"""
팩 친구 — 클로디 대신 **캐릭터 팩 그림**(`cooldown_pack`)을 세운다.

클로디(`claudi.py`)와 같은 약속을 지킨다: `home`·`start`·`react`·`hold`·`let_go`·
`absorbed`·`to_local`·`on_morph`·`unmorph`. 그래서 스킨은 둘 중 무엇이 오든 똑같이 부른다.

- 늘 서 있는 그림은 사용량(`set_mood`)이 정한다: 여유·빠듯·한도·오류.
- 일이 생기면 잠깐 다른 장면을 튼다: 콕(누름)·꾹(길게 누름)·초기화·심심(한참 가만히).
  잠깐 장면은 한 바퀴(움직이는 그림) 또는 `EVENT_MS`(멈춘 그림) 돌고 늘 그림으로 돌아온다.
- 누르면 클로디처럼 용수철로 폴짝 뛴다(`SPRING_K`·`SPRING_DAMP`). 몸을 좌우로 흔들지 않는다.
- 공룡 변신은 없다(`on_morph` 는 받아만 두고 안 부른다).
"""

from __future__ import annotations

import random
import tkinter as tk

import cooldown_pack as pack

FRAME_MS = 40  # 물리 한 걸음 (그림 프레임은 그림 파일의 시간대로 넘긴다)
EVENT_MS = 1600  # 멈춘 그림 잠깐 장면 길이
POKE_VY = -5.5  # 콕 한 번에 위로 튀는 속도 (px/걸음)
SPRING_K = 0.22
SPRING_DAMP = 0.72
IDLE_MIN, IDLE_MAX = 40_000, 90_000  # 이만큼 가만있으면 심심 장면
HOLD_SINK = 3  # 꾹 누르는 동안 내려앉는 깊이 (px)
TAG = "packpet"


class PackPet:
    def __init__(self, canvas: tk.Canvas, box: tuple[float, float, float, float],
                 height: int | None = None, width: int | None = None,
                 root: str = pack.PACK_DIR):
        self.c = canvas
        self.root = root
        self.x0, self.y0, self.x1, self.y1 = box
        self.cx = (self.x0 + self.x1) / 2
        conf = pack.settings(root)
        room = int(self.y1 - self.y0)
        want = int(conf.get("높이") or height or room - 8)  # 위로 폴짝 뛸 틈을 남긴다
        self.height = max(12, min(room, want))  # 바보다 크면 잘리므로 바 높이까지만
        self.width = width  # 그림이 넘으면 안 되는 폭 (바의 틈)
        self.speed = float(conf.get("속도") or 1.0)
        self.hit_r = self.height * 0.6
        self.on_morph = None  # 앱이 걸어 두지만 쓰지 않는다 (공룡 변신 없음)

        self._mood = "여유"
        self._event: str | None = None
        self._clip_path: str | None = None
        self._frames: list = []  # [(PhotoImage, ms)]
        self._fi = 0
        self._cache: dict[str, list] = {}
        self._played = False
        self._held = False
        self._y = 0.0  # 제자리에서 위로 뜬 거리 (음수=위)
        self._vy = 0.0
        self._gen = 0
        self._item = None
        self._idle_after = None

    # -------------------------------------------------- 약속 (스킨이 부르는 것)
    def home(self, cx: float, cy: float | None = None) -> None:
        self.cx = cx

    def to_local(self, widget: tk.Misc, x: float | None, y: float | None):
        if x is None or y is None:
            return None, None
        top = self.c.winfo_toplevel()
        return (x - (self.c.winfo_rootx() - top.winfo_rootx()),
                y - (self.c.winfo_rooty() - top.winfo_rooty()))

    def start(self) -> None:
        self._gen += 1
        self._play(self._mood)
        self._step(self._gen)
        self._frame(self._gen)
        self._arm_idle()

    def absorbed(self) -> bool:
        played, self._played = self._played, False
        return played

    def react(self, x: float | None = None, y: float | None = None) -> None:
        if x is None or not self._hit(x, y):
            self._vy += POKE_VY * 0.3  # 딴 데를 누르면 살짝 통통만
            return
        self._played = True
        self._vy += POKE_VY
        self._flash("콕")

    def hold(self, x: float, y: float) -> None:
        if not self._hit(x, y):
            return
        self._played = True
        self._held = True
        self._flash("꾹", hold=True)

    def let_go(self) -> None:
        if not self._held:
            return
        self._held = False
        self._vy += POKE_VY * 1.2  # 눌렸다 놓이면 튕겨 오른다
        self._event = None
        self._play(self._mood)

    def unmorph(self) -> None:
        pass

    # -------------------------------------------------- 사용량이 정하는 것
    def set_mood(self, mood: str) -> None:
        if mood == self._mood:
            return
        self._mood = mood
        if self._event is None:
            self._play(mood)

    def celebrate(self) -> None:
        """5시간 한도가 초기화됐을 때."""
        self._vy += POKE_VY * 1.4
        self._flash("초기화")

    # -------------------------------------------------- 속
    def _hit(self, x: float, y: float) -> bool:
        cy = self.y1 - self.height / 2 + self._y
        return (x - self.cx) ** 2 + (y - cy) ** 2 <= self.hit_r ** 2

    def _frames_for(self, path: str) -> list:
        if path not in self._cache:
            from PIL import ImageTk
            try:
                raw = pack.load_frames(path, self.height, self.speed, self.width)
            except Exception:  # 깨진 그림 하나 때문에 위젯이 죽으면 안 된다
                raw = []
            self._cache[path] = [(ImageTk.PhotoImage(im, master=self.c), ms) for im, ms in raw]
        return self._cache[path]

    def _play(self, state: str) -> bool:
        path = pack.pick(state, self.root, avoid=self._clip_path)
        frames = self._frames_for(path) if path else []
        if not frames:
            return False
        self._clip_path, self._frames, self._fi = path, frames, 0
        self._draw()
        return True

    def _flash(self, state: str, hold: bool = False) -> None:
        if not self._play(state):
            return
        self._event = state
        self._arm_idle()
        if hold:
            return  # 꾹은 놓을 때(let_go)까지 그대로
        # 움직이는 그림은 한 바퀴, 멈춘 그림은 EVENT_MS
        total = sum(ms for _, ms in self._frames) if len(self._frames) > 1 else EVENT_MS
        gen, clip = self._gen, self._clip_path
        self.c.after(max(600, min(total, 6000)), lambda: self._end_event(gen, clip))

    def _end_event(self, gen: int, clip: str | None) -> None:
        if gen != self._gen or self._held or clip != self._clip_path:
            return
        self._event = None
        self._play(self._mood)

    def _arm_idle(self) -> None:
        if self._idle_after is not None:
            self.c.after_cancel(self._idle_after)
        self._idle_after = self.c.after(random.randint(IDLE_MIN, IDLE_MAX), self._bored)

    def _bored(self) -> None:
        self._idle_after = None
        if not self.c.winfo_exists():
            return
        if self._event is None and pack.clips("심심", self.root):
            self._flash("심심")
        self._arm_idle()

    def _draw(self) -> None:
        if not self._frames:
            return
        img = self._frames[self._fi % len(self._frames)][0]
        x, y = self.cx, self.y1 + self._y + (HOLD_SINK if self._held else 0)
        if self._item is None or not self.c.type(self._item):
            self._item = self.c.create_image(x, y, image=img, anchor="s", tags=TAG)
        else:
            self.c.itemconfigure(self._item, image=img)
            self.c.coords(self._item, x, y)
        self.c.tag_raise(TAG)

    def _frame(self, gen: int) -> None:
        if gen != self._gen or not self.c.winfo_exists():
            return
        ms = 200
        if len(self._frames) > 1:
            self._fi = (self._fi + 1) % len(self._frames)
            ms = self._frames[self._fi][1]
            self._draw()
        self.c.after(ms, lambda: self._frame(gen))

    def _step(self, gen: int) -> None:
        if gen != self._gen or not self.c.winfo_exists():
            return
        moving = abs(self._y) > 0.05 or abs(self._vy) > 0.05
        if moving:
            self._vy = (self._vy - self._y * SPRING_K) * SPRING_DAMP
            self._y += self._vy
            # 바 위로 뚫고 나가지 않게: 그림 꼭대기가 바 위끝에 닿으면 멈춘다
            top_room = (self.y1 - self.y0) - self.height
            if self._y < -top_room:
                self._y, self._vy = -top_room, 0.0
            self._draw()
        self.c.after(FRAME_MS, lambda: self._step(gen))
