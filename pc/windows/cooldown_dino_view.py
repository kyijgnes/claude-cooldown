"""
공룡 점프 판 — `cooldown_dino.Game` 을 Tk 캔버스에 그린다
=========================================================
규칙은 `pc/cooldown_dino.py` 한 곳이고 여기서는 **그리기와 누르기만** 한다.
**창을 새로 띄우지 않는다** — 앱이 위젯 본체를 잠깐 치우고 그 자리에 `DinoBoard` 를 얹는다
(`App.open_dino`). 판이 위젯보다 크면 위젯이 판만큼 늘어났다가, 닫으면 돌아간다.

- **키는 캔버스가 받는다**(판이 포커스를 쥔다). 창(root)에 걸면 판을 닫은 뒤에도 남는다.
- 판을 누른 것은 **여기서 끝낸다**(`"break"`). 창에 걸린 끌기·새로고침·클로디 놀이까지
  올라가면 누를 때마다 위젯이 끌려 다닌다.
- 닫는 길: 왼쪽 위 ✕ · Esc · 기다림/부딪힘/멈춤으로 20초(`IDLE_EXIT`) 그대로 두기.
- **매 프레임 지우고 다시 그린다.** 도트 그림은 줄마다 이어진 칸을 한 덩이로 그리므로
  (`cooldown_dino.runs`) 가장 붐빌 때도 도형이 300개 안쪽이다.
- **한 걸음은 1/60초로 고정**하고, 흐른 시간만큼 걸음을 밟은 뒤 한 번 그린다. 윈도우의 기본
  타이머는 15.6ms 눈금이라 `after(16)` 이 16ms 와 31ms 를 오간다 — 판이 떠 있는 동안만
  `timeBeginPeriod(1)` 로 눈금을 1ms 로 당긴다(닫으면 되돌린다).
- **포커스를 잃으면 멈춘다.** 딴 창을 누른 사이 혼자 달리다 부딪혀 있으면 억울하다.
- 색은 테마(`P`)를 따르고, 밤(700점마다 12초)에는 판만 반대 테마로 뒤집는다(크롬과 같다).
- **이펙트는 전부 여기 것이다**(규칙은 모른다). 판이 `Game.events` 에 적은 일을 걸음마다 읽어 먼지·파편·
  바람 줄기·반짝이를 터뜨린다. 알갱이는 `MAX_PARTICLES` 를 넘지 않고(넘으면 오래된 것부터 버린다),
  캔버스는 매 프레임 통째로 지우므로 남는 도형이 없다. 색은 팔레트 칸 이름으로 들고 있다가 그릴 때 읽어
  밤으로 넘어가는 중에도 같이 바뀐다. 부딪히면 몇 프레임 **멈췄다가**(`HIT_STOP`) 흔들린다.

혼자 띄워 보기: `python pc/windows/cooldown_dino_view.py [너비]`
그림으로 남기기: `python pc/windows/cooldown_dino_view.py shot out.png [프레임] [light|dark] [over] [w=460]`
"""

from __future__ import annotations

import ctypes
import math
import os
import random
import sys
import time
import tkinter as tk
import tkinter.font as tkfont

HERE = os.path.dirname(os.path.abspath(__file__))
if __name__ == "__main__":
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.dirname(HERE))

import cooldown_dino as dino  # noqa: E402
from skins.base import DARK, KR, LIGHT, NUM, P  # noqa: E402

STEP = 1.0 / dino.FPS
MAX_CATCH_UP = 5      # 한 번에 밟는 걸음의 상한 — 창을 끌던 사이 몇 초가 흘러도 순간이동하지 않게
HINT = "스페이스 · 클릭 점프    ↓ 숙이기"
PAUSED = "일시 정지 · 눌러서 이어 하기"

# ---------------------------------------------------------------- 이펙트
MAX_PARTICLES = 72    # 알갱이 상한 — 넘으면 오래된 것부터 버린다
HIT_STOP = 6          # 부딪힌 순간 이만큼(0.1초) 판이 멎는다. 보호막이 막을 땐 `BREAK_STOP`
BREAK_STOP = 3
SHAKE = (22, 6)       # 부딪힘: 흔들리는 프레임 · 처음 폭(px). 폭은 0 으로 줄어든다
BREAK_SHAKE = (8, 3)
GAUGE_W = 26          # 공룡 머리 위 활공 게이지 너비 (px)
OVER_TEXT = "GAME OVER"
# 색 — 팔레트 칸 이름 하나, 또는 (칸, 칸, 섞는 정도). 새 색은 두지 않고 있는 칸을 섞어 쓴다.
C_DUST = ("label", "bg", 0.15)     # 먼지
C_WIND = ("title", "bg", 0.6)      # 바람 줄기
C_GROOVE = ("title", "bg", 0.5)    # 깃털 사이 결
C_FLASH = ("bg", "title", 0.14)    # 부딪힌 순간 판 바탕


def _blend(a: str, b: str, t: float) -> str:
    """색 두 개(#rrggbb)를 t(0=a, 1=b) 만큼 섞는다."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


class _Mixed:
    """낮↔밤 사이의 색 한 벌 — 팔레트 두 벌을 칸마다 섞는다(읽을 때 계산)."""

    def __init__(self, a, b, t: float) -> None:
        self._a, self._b, self._t = a, b, t

    def __getattr__(self, name: str) -> str:
        return _blend(getattr(self._a, name), getattr(self._b, name), self._t)


class DinoBoard:
    """판 하나 — `parent` 에 `width`×`H` 캔버스를 얹는다.

    `on_best(점수)` 는 최고 기록을 넘긴 판이 끝날 때 한 번, `on_exit()` 는 닫을 때 한 번 불린다
    (✕ · Esc · 오래 그대로 둠). 판을 실제로 치우는 것은 부른 쪽(앱)이 한다.
    """

    def __init__(self, parent: tk.Misc, width: int = dino.W, best: int = 0, on_best=None,
                 on_exit=None, seed: int | None = None) -> None:
        self.on_best = on_best
        self.on_exit = on_exit
        self.game = dino.Game(seed=seed, best=best, width=width)
        self.w = width
        self.c = tk.Canvas(parent, width=width, height=dino.H, bg=P.bg,
                           highlightthickness=0, bd=0, cursor="hand2", takefocus=1)
        self.paused = False
        self._saved_over = False
        self._alive = True
        self._last = time.perf_counter()
        self._acc = 0.0
        self._idle = 0.0          # 기다림·부딪힘·멈춤으로 흐른 초 — `IDLE_EXIT` 넘으면 닫는다
        self._fine_timer = False
        self._close_hot = False   # ✕ 위에 마우스가 있다 (밝게 그린다)
        self._hi_w = tkfont.Font(font=(NUM, 11)).measure("HI 00000")  # 보호막 표시를 그 왼쪽에
        # 이펙트 — 알갱이: [종류, x, y, vx, vy, 남은, 처음, 크기, 색, 중력]
        self._rng = random.Random(seed)
        self._parts: list[list] = []
        self._fx_t = 0            # 이펙트 걸음 수 (판이 멎은 동안은 안 흐른다)
        self._freeze = 0          # 판이 멎어 있을 남은 프레임
        self._flash = 0           # 부딪힌 번쩍임 남은 프레임
        self._flash_at = (0.0, 0.0)
        self._shake = (0, 0, 0)   # 남은 · 전체 · 폭
        self._over_k = 0          # 부딪히고(멎은 뒤) 흐른 프레임 — 글자가 떨어지는 박자
        self._pop = 0             # 점수 이정표에서 숫자가 커져 있을 남은 프레임
        stars = random.Random(width)
        self._stars = [(stars.randrange(8, max(9, width - 8)), stars.randrange(30, 84), stars.randrange(40))
                       for _ in range(max(6, width // 50))]
        self._bind()
        self._timer_fine(True)
        self.c.bind("<Destroy>", lambda e: self.close() if e.widget is self.c else None)
        self.draw()
        self.c.after(int(STEP * 1000), self._loop)

    # -------------------------------------------------- 누르기
    def _bind(self) -> None:
        c = self.c
        for key in ("<KeyPress-space>", "<KeyPress-Up>"):
            c.bind(key, lambda _e: self._press_jump())
        for key in ("<KeyRelease-space>", "<KeyRelease-Up>"):
            c.bind(key, lambda _e: self._keep(self.game.release_jump))
        c.bind("<KeyPress-Down>", lambda _e: self._keep(self.game.press_duck))
        c.bind("<KeyRelease-Down>", lambda _e: self._keep(self.game.release_duck))
        c.bind("<Escape>", lambda _e: self._exit())
        # ★ 누른 것은 여기서 끝낸다 — 창에 걸린 끌기·새로고침으로 올라가면 위젯이 끌려 다닌다
        c.bind("<Button-1>", self._click)
        c.bind("<B1-Motion>", lambda _e: "break")
        c.bind("<ButtonRelease-1>", lambda _e: (self.game.release_jump(), "break")[1])
        c.bind("<Motion>", self._hover)
        c.bind("<Leave>", lambda _e: self._hover(None))
        c.bind("<FocusOut>", lambda _e: self._focus_lost())

    def focus(self) -> None:
        """판이 키를 받게 포커스를 쥔다 (띄운 직후 앱이 부른다)."""
        try:
            self.c.focus_force()
        except tk.TclError:
            pass

    def _keep(self, fn) -> str:
        self._idle = 0.0
        fn()
        return "break"

    def _on_close(self, x: float, y: float) -> bool:
        return x < dino.CLOSE_HIT and y < dino.CLOSE_HIT

    def _click(self, e) -> str:
        self.focus()
        if self._on_close(e.x, e.y):
            self._exit()
        else:
            self._press_jump()
        return "break"

    def _hover(self, e) -> None:
        hot = e is not None and self._on_close(e.x, e.y)
        if hot != self._close_hot:
            self._close_hot = hot
            self.c.configure(cursor="arrow" if hot else "hand2")

    def _press_jump(self) -> str:
        self._idle = 0.0
        if self.paused:            # 멈춘 판을 누르면 이어서 — 그 누르기로 뛰지는 않는다
            self.paused = False
            self._last = time.perf_counter()
            return "break"
        if self.game.state == "over" and self.game.over_t >= dino.OVER_WAIT:
            self._saved_over = False
        self.game.press_jump()
        return "break"

    def _focus_lost(self) -> None:
        """딴 창으로 가면 멈춘다. 포커스가 판 안에서 옮겨 다니는 것은 무시한다."""
        def check():
            if not self._alive:
                return
            try:
                foc = self.c.focus_displayof()
            except (KeyError, tk.TclError):
                foc = None
            if foc is not self.c and self.game.state == "run":
                self.paused = True
                self.game.release_jump()
                self.game.release_duck()
        try:
            self.c.after(120, check)
        except tk.TclError:
            pass

    def _exit(self) -> str:
        if self._alive and self.on_exit is not None:
            self.c.after_idle(self.on_exit)   # 이 콜백 안에서 캔버스를 치우지 않게 한 박자 뒤로
        return "break"

    # -------------------------------------------------- 돌리기
    def _timer_fine(self, on: bool) -> None:
        """윈도우 타이머 눈금을 1ms 로 (판이 떠 있는 동안만)."""
        if on == self._fine_timer:
            return
        try:
            winmm = ctypes.windll.winmm
            (winmm.timeBeginPeriod if on else winmm.timeEndPeriod)(1)
            self._fine_timer = on
        except (AttributeError, OSError):
            pass

    def close(self) -> None:
        self._alive = False
        self._timer_fine(False)

    def _loop(self) -> None:
        if not self._alive:
            return
        now = time.perf_counter()
        dt = now - self._last
        self._acc += dt
        self._last = now
        g = self.game
        if self.paused or g.state != "run":   # 아무도 안 놀고 있다 — 오래 그대로면 접는다
            self._idle += dt
            if self._idle * dino.FPS >= dino.IDLE_EXIT:
                self._exit()
                return
        if self.paused:
            self._acc = 0.0
        else:
            n = 0
            while self._acc >= STEP and n < MAX_CATCH_UP:
                self._tick()
                self._acc -= STEP
                n += 1
            if n == MAX_CATCH_UP:
                self._acc = 0.0
        if g.state == "over" and not self._saved_over:
            self._saved_over = True
            if g.new_best and self.on_best:
                self.on_best(g.best)
        try:
            self.draw()
            wait = max(1, int((STEP - self._acc) * 1000))
            self.c.after(wait, self._loop)
        except tk.TclError:   # 판이 치워졌다
            self.close()

    # -------------------------------------------------- 이펙트
    def _tick(self) -> None:
        """한 걸음(1/60초) — 판을 밟고, 일어난 일로 이펙트를 터뜨리고, 알갱이를 한 박자 옮긴다."""
        g = self.game
        if self._flash > 0:
            self._flash -= 1
        if self._freeze > 0:          # 부딪힌 순간 — 판도 알갱이도 멎는다
            self._freeze -= 1
            return
        was = g.state
        g.step()
        if g.state == "run" and (was != "run" or g.run_t <= 1):   # 새 판 — 지난 판의 것을 치운다
            self._parts.clear()
            self._shake = (0, 0, 0)
            self._over_k = 0
        events, g.events[:] = list(g.events), []
        for ev in events:
            self._on_event(*ev)
        self._fx_step()

    def _spawn(self, kind, x, y, vx, vy, life, size, color, grav=0.0) -> None:
        self._parts.append([kind, x, y, vx, vy, life, life, size, color, grav])
        if len(self._parts) > MAX_PARTICLES:
            del self._parts[:len(self._parts) - MAX_PARTICLES]

    def _dust(self, n: int, power: float, back: bool = False) -> None:
        """발밑 먼지 — `back` 이면 뒤로만(박차고 뛸 때), 아니면 양옆으로(내려앉을 때)."""
        r = self._rng
        feet = dino.DINO_X + 16
        for _ in range(n):
            side = -1 if back or r.random() < 0.6 else 1
            self._spawn("sq", feet + side * r.uniform(2, 12), dino.GROUND - 4,
                        side * r.uniform(0.8, 1.6 + power * 2) - (0.6 if back else 0),
                        -r.uniform(0.2, 0.6 + power * 0.8), r.randint(14, 24), 4, C_DUST, 0.03)

    def _stars_at(self, x, y, n: int, color, speed: float = 2.2) -> None:
        r = self._rng
        for i in range(n):
            a = 2 * math.pi * (i + r.uniform(-0.2, 0.2)) / n
            v = speed * r.uniform(0.7, 1.2)
            self._spawn("star", x, y, v * math.cos(a), v * math.sin(a), r.randint(14, 22), 2, color)

    def _feathers(self, x, y, n: int) -> None:
        r = self._rng
        for _ in range(n):
            self._spawn("feather", x + r.uniform(-12, 8), y + r.uniform(-8, 6), -r.uniform(0.4, 1.8),
                        -r.uniform(0.0, 1.2), r.randint(36, 56), 4, "title", 0.035)

    def _debris(self, ob, n: int, near=None) -> None:
        """장애물 도트가 조각나 튄다 — `near` 가 있으면 그 둘레 칸만(부딪힌 자리), 없으면 통째로."""
        r = self._rng
        cells = list(ob.hit_runs())
        if near is not None:
            cells.sort(key=lambda c: (c[0] + c[2] / 2 - near[0]) ** 2 + (c[1] - near[1]) ** 2)
            cells = cells[:n]
        elif len(cells) > n:
            cells = r.sample(cells, n)
        color = "label" if ob.kind == "bird" else "green"
        for x, y, w, _h in cells:
            self._spawn("sq", x + w / 2, y, r.uniform(-1.0, 4.5), -r.uniform(1.0, 5.0),
                        r.randint(28, 46), r.choice((2, 4, 4)), color, 0.4)

    def _on_event(self, name, *a) -> None:
        g, r = self.game, self._rng
        if name == "jump":
            self._dust(3, 0.6, back=True)
        elif name == "land":           # 세게 떨어질수록 먼지가 많다 — 활공으로 내려앉으면 살짝만
            power = min(1.0, a[0] / 12)
            self._dust(3 + round(power * 7), power)
        elif name == "glide":          # 날개를 편 순간 — 바람이 한 번 훅
            for _ in range(4):
                self._wind(burst=True)
        elif name == "wing_out":
            self._feathers(a[0], a[1], 6)
        elif name == "item":
            kind, x, y = a
            self._stars_at(x, y, 7, "amber" if kind == "shield" else "title")
        elif name == "score":
            self._pop = 12
            self._stars_at(self.w - 34, 22, 5, "sub", 1.6)
        elif name == "break":          # 보호막이 막았다 — 장애물이 통째로 부서진다
            ob = a[0]
            self._debris(ob, 20)
            self._stars_at(ob.x + ob.w / 2, ob.y + ob.h / 2, 6, "amber", 3.0)
            self._freeze = BREAK_STOP
            self._shake = (BREAK_SHAKE[0], *BREAK_SHAKE)
        elif name == "crash":
            ob, x, y = a
            self._debris(ob, 14, near=(x, y))
            for _ in range(6):         # 공룡 쪽으로도 코랄 조각이 튄다
                self._spawn("sq", x, y, -r.uniform(0.5, 3.5), -r.uniform(0.5, 4.0), r.randint(20, 34), 2,
                            "mascot", 0.35)
            if g.wing:
                self._feathers(dino.DINO_X + 10, g.dino_y + 16, 5)
            if g.new_best:
                self._stars_at(self.w - 70 - self._hi_w / 2, 22, 8, "amber", 2.0)
            self._freeze = HIT_STOP
            self._flash = HIT_STOP + 3
            self._flash_at = (x, y)
            self._shake = (SHAKE[0], *SHAKE)

    def _wind(self, burst: bool = False) -> None:
        g, r = self.game, self._rng
        self._spawn("line", dino.DINO_X + r.uniform(-14, 34), g.dino_y + r.uniform(2, 34),
                    -(g.speed * 0.8 + r.uniform(2, 5) + (3 if burst else 0)), 0.0, r.randint(10, 18),
                    r.choice((8, 12, 16, 22)), C_WIND)

    def _fx_step(self) -> None:
        g, r = self.game, self._rng
        self._fx_t += 1
        t = self._fx_t
        if self._pop > 0:
            self._pop -= 1
        if self._shake[0] > 0:
            self._shake = (self._shake[0] - 1, *self._shake[1:])
        self._over_k = self._over_k + 1 if g.state == "over" else 0
        if g.state == "run":
            if g.gliding:
                if t % 3 == 0:
                    self._wind()
                if t % 2 == 0:         # 깃털 끝에서 흘러나오는 자국
                    self._spawn("sq", dino.DINO_X - 18, g.dino_y + 16 + r.choice((0, 2)), -g.speed * 0.6, 0.1,
                                r.randint(8, 12), 2, C_GROOVE)
                if g.glide_left < dino.GLIDE_LOW and t % 9 == 0:   # 얼마 안 남았다 — 깃털이 빠진다
                    self._feathers(dino.DINO_X - 4, g.dino_y + 18, 1)
            elif not g.jumping and t % 7 == 0:                     # 달리는 발끝의 흙
                self._spawn("sq", dino.DINO_X + r.uniform(6, 14), dino.GROUND - 2, -r.uniform(1.0, 2.4),
                            -r.uniform(0.3, 1.1), r.randint(8, 13), 2, C_DUST, 0.06)
        keep = []
        for p in self._parts:
            p[1] += p[3]
            p[2] += p[4]
            p[4] += p[9]
            p[5] -= 1
            if p[0] == "sq" and p[9] > 0.2 and p[2] > dino.GROUND - p[7]:   # 파편은 땅에서 한 번 튄다
                p[2] = dino.GROUND - p[7]
                p[4] *= -0.35
                p[3] *= 0.6
            elif p[0] == "feather":
                p[4] = min(p[4], 0.55)                 # 깃털은 천천히 내려앉는다
                if p[2] > dino.GROUND - 3:
                    p[2], p[3], p[4] = dino.GROUND - 3, p[3] * 0.8, 0.0
            if p[5] > 0 and -30 < p[1] < self.w + 30:
                keep.append(p)
        self._parts = keep

    def _draw_parts(self, col, lines: bool) -> None:
        """알갱이 — 바람 줄기(`lines`)는 공룡 **뒤에**, 나머지는 앞에 그리려고 두 번에 나눠 부른다."""
        c, u = self.c, dino.U
        for kind, x, y, _vx, _vy, life, life0, sz, color, _g in self._parts:
            if (kind == "line") != lines:
                continue
            fill = col(color)
            old = life * 2 < life0          # 수명 절반을 넘기면 작아진다
            if kind == "sq":
                s = u if old else sz
                bx, by = round(x / u) * u, round(y / u) * u
                c.create_rectangle(bx, by, bx + s, by + s, fill=fill, width=0)
            elif kind == "line":
                n = sz * life / life0
                c.create_rectangle(x, round(y), x + n, round(y) + 1, fill=fill, width=0)
            elif kind == "star":            # 네 방향 반짝이 — 늙으면 가운데 점만
                bx, by = round(x / u) * u, round(y / u) * u
                if old:
                    c.create_rectangle(bx, by, bx + u, by + u, fill=fill, width=0)
                else:
                    c.create_rectangle(bx - u, by, bx + 2 * u, by + u, fill=fill, width=0)
                    c.create_rectangle(bx, by - u, bx + u, by + 2 * u, fill=fill, width=0)
            else:                           # 깃털 — 좌우로 살랑이며 떨어진다
                bx = round((x + 3 * math.sin((life + sz) * 0.22)) / u) * u
                by = round(y / u) * u
                c.create_rectangle(bx, by, bx + 2 * u, by + u, fill=fill, width=0)
                c.create_rectangle(bx + 2 * u, by - u, bx + 3 * u, by, fill=fill, width=0)

    # -------------------------------------------------- 그리기
    def _colors(self):
        """판에 쓸 색 한 벌 — 지금 테마(`P`), 밤이면 반대 테마. 바뀔 때는 두 벌을 섞어 서서히."""
        mix = self.game.night_mix
        if mix <= 0:
            return P
        other = LIGHT if P.bg == DARK.bg else DARK
        if mix >= 1:
            return other
        return _Mixed(P, other, mix)

    def draw(self) -> None:
        c, g, w = self.c, self.game, self.w
        pal = self._colors()
        cache: dict = {}

        def col(spec) -> str:
            """색 — 팔레트 칸 이름, 또는 (칸, 칸, 섞는 정도). 한 프레임 안에서는 한 번만 계산한다."""
            got = cache.get(spec)
            if got is None:
                got = cache[spec] = (getattr(pal, spec) if isinstance(spec, str)
                                     else _blend(getattr(pal, spec[0]), getattr(pal, spec[1]), spec[2]))
            return got

        flash = self._flash > 0 and g.state == "over"
        bg = col(C_FLASH) if flash else pal.bg
        if c.cget("bg") != bg:
            c.configure(bg=bg)
        c.delete("all")
        # 밤하늘 별 — 밤이 든 만큼만 떠오르고, 제각기 깜빡인다
        mix = g.night_mix
        if mix > 0:
            star = _blend(pal.bg, pal.title, 0.55 * mix)
            for x, y, phase in self._stars:
                if (g.t // 20 + phase) % 5:
                    c.create_rectangle(x, y, x + 2, y + 2, fill=star, width=0)
        # 구름 — 판보다 흐리게, 제일 뒤에
        for x, y in g.clouds:
            self._art(dino.CLOUD, x, y, pal.track)
        # 땅 — 선 하나와 흘러가는 자갈 (흔들릴 때 끝이 안 비게 양옆으로 넉넉히)
        c.create_rectangle(-10, dino.GROUND - 1, w + 10, dino.GROUND, fill=pal.label, width=0)
        for x, depth, pw in g.pebbles:
            xi = round(x)
            c.create_rectangle(xi, dino.GROUND + depth, xi + pw, dino.GROUND + depth + 1,
                               fill=pal.faint, width=0)
        # 장애물
        for ob in g.obstacles:
            color = pal.label if ob.kind == "bird" else pal.green
            for art, x, y, flip in ob.parts():
                self._art(art, x, y, color, flip)
                if ob.kind == "bird":
                    ex, ey = dino.BIRD_EYE[ob.frame % 2]
                    self._cells(((ex, ey),), x, y, bg)
        # 아이템 — 판 위에 놓인 것. 눈에 띄게 위아래로 살짝 떠 있는다.
        sw, sh = dino.size(dino.SHIELD)
        for x, lift, kind in g.items:
            art = dino.ITEM_ART[kind]
            y = dino.GROUND - lift - dino.size(art)[1] - (2 if lift and (g.t // 16) % 2 else 0)
            self._art(art, x, y, self._item_color(kind, pal))
            if kind == "wing":
                self._art(dino.WING_GROOVE, x, y, col(C_GROOVE))
        self._draw_parts(col, lines=True)
        # 공룡 — 막아 준 뒤 안 부딪히는 동안은 깜빡인다. 부딪히면 뒤로 움찔한다.
        pose = g.pose
        dx, dy = dino.DINO_X, g.dino_y
        if g.state == "over" and self._freeze <= 0:
            k = self._over_k
            dx -= round(4 * min(1.0, k / 5))
            if k < 14 and g.h <= 0:
                dy -= round(5 * math.sin(math.pi * k / 14))
        if g.shield_blink:
            self._art(dino.POSES[pose], dx, dy, pal.title if flash and self._flash > 3 else P.mascot)
            eyes = (dino.DUCK_EYE if pose.startswith("duck") else dino.DINO_EYE)[g.eye]
            self._cells(eyes, dx, dy, bg)
            # 날개 — 몸 **앞에**. 달릴 땐 접고, 뛰어오르며 퍼덕이고, 활공 중엔 펼친 채 살짝 일렁인다.
            #   활공이 얼마 안 남으면 깃털이 흐려졌다 돌아왔다 한다.
            wp = g.wing_pose
            if wp is not None:
                rows, groove, (wx, wy) = dino.WING_BACK[wp]
                if g.gliding:
                    wy += round(math.sin(g.t * 0.3))
                low = g.gliding and g.glide_left < dino.GLIDE_LOW and (g.t // 4) % 2
                self._art(rows, dx + wx, dy + wy, col(C_GROOVE) if low else pal.title)
                if not low:
                    self._art(groove, dx + wx, dy + wy, col(C_GROOVE))
        self._draw_parts(col, lines=False)
        # 들고 있는 보호막 — 공룡 둘레를 도는 점선 고리. 막아 준 순간엔 고리가 터지며 퍼진다.
        dw, dh = dino.size(dino.POSES[pose])
        cx, cy = dx + dw / 2, dy + dh / 2 - 3   # 고리 아래끝이 땅 줄에 걸치게 조금 위로
        if g.shield and g.state != "over":
            self._ring(cx, cy, dino.SHIELD_RING_R, pal.amber, g.t // 3)
        elif g.broke > 0:
            grow = (dino.SHIELD_GRACE - g.broke) * 1.2
            if (g.broke // 3) % 2 == 0:
                self._ring(cx, cy, dino.SHIELD_RING_R + grow, pal.amber, 0)
        # 부딪힌 자리 — 여덟 방향으로 터지는 섬광 (판이 멎어 있는 동안)
        if flash:
            self._burst(*self._flash_at, HIT_STOP + 3 - self._flash, pal.title)
        # 활공 게이지 — 날개를 달고 떠 있는 동안 머리 위에. 얼마 안 남으면 빨갛게 깜빡인다.
        if g.wing and g.jumping and g.state == "run":
            self._gauge(dx + 8, dy - 9, GAUGE_W, g.glide_left, pal)
        # 흔들기 — 여기까지 그린 것(판)만. 점수·단추는 가만히 둔다.
        left, total, amp = self._shake
        if left > 0 and self._freeze <= 0:
            a = amp * left / total
            c.move("all", round(self._rng.uniform(-a, a)), round(self._rng.uniform(-a, a) * 0.6))
        # 닫기 ✕ — 왼쪽 위 구석
        self._art(dino.CLOSE, *dino.CLOSE_AT, pal.title if self._close_hot else pal.faint)
        # 점수 — 오른쪽 위 (HI 최고 · 지금). 100점을 넘는 순간 숫자가 한 번 커진다.
        text = f"{g.shown_score:05d}" if g.score_visible else ""
        pop = self._pop
        c.create_text(w - 12, 14 - (2 if pop > 6 else 0), text=text, anchor="ne",
                      fill=pal.title if pop else pal.sub,
                      font=(NUM, 13 if pop > 6 else 12 if pop else 11, "bold"))
        if g.best > 0 or g.state == "over":
            c.create_text(w - 70, 14, text=f"HI {g.best:05d}", anchor="ne",
                          fill=pal.amber if g.new_best and g.state == "over" else pal.label,
                          font=(NUM, 11, "bold" if g.new_best and g.state == "over" else "normal"))
        # 들고 있는 것 — 점수 왼쪽에 작은 표시. 날개 밑에는 남은 활공.
        if g.state == "run":
            hi = self._hi_w if g.best > 0 else 0
            x = w - 70 - hi - 10
            if g.shield:
                x -= sw
                self._art(dino.SHIELD, x, 7, pal.amber)
                x -= 6
            if g.wing:
                ww, wh = dino.size(dino.WING)
                x -= ww
                self._art(dino.WING, x, 3, self._item_color("wing", pal))
                self._art(dino.WING_GROOVE, x, 3, col(C_GROOVE))
                self._gauge(x, 3 + wh + 2, ww, g.glide_left, pal)
        if self.paused:
            c.create_text(w / 2, 56, text=PAUSED, fill=pal.title, font=(KR, 10, "bold"))
        elif g.state == "ready":
            c.create_text(w / 2, 56, text=HINT, fill=pal.label, font=(KR, 9))
        elif g.state == "over" and self._freeze <= 0:
            # 글자가 하나씩 떨어져 내려앉고, 다시 누를 수 있게 되면 화살표가 켜진다
            k = self._over_k
            step_x = 15
            x0 = w / 2 - step_x * (len(OVER_TEXT) - 1) / 2
            for i, ch in enumerate(OVER_TEXT):
                at = k - i * 2
                if ch == " " or at < 0:
                    continue
                drop = -16 * (1 - min(1.0, at / 6)) ** 2 + (2 if 6 <= at < 9 else 0)
                c.create_text(x0 + i * step_x, 50 + round(drop), text=ch, fill=pal.title,
                              font=(NUM, 12, "bold"))
            rw, _ = dino.size(dino.RESTART)
            ready = g.over_t >= dino.OVER_WAIT
            lift = 2 if ready and g.over_t < dino.OVER_WAIT + 5 else 0
            self._art(dino.RESTART, w / 2 - rw / 2, 68 - lift, pal.title if ready else pal.line)

    def _art(self, rows, x, y, color, flip=False) -> None:
        """도트 그림 한 장 — 줄마다 이어진 칸을 한 덩이로. 칸이 정수 픽셀에 맞게 한 번만 반올림."""
        bx, by = round(x), round(y)
        for rx, ry, rw, rh in dino._art_runs(rows, flip):
            self.c.create_rectangle(bx + rx, by + ry, bx + rx + rw, by + ry + rh,
                                    fill=color, width=0)

    @staticmethod
    def _item_color(kind: str, pal) -> str:
        """보호막은 금색, 날개는 글자색. 선인장 초록과 안 헷갈리게."""
        return pal.amber if kind == "shield" else pal.title

    def _gauge(self, x, y, width, left: float, pal) -> None:
        """남은 활공 막대 — 빈 칸 위에 남은 만큼. `GLIDE_LOW` 아래면 빨갛게 깜빡인다."""
        x, y = round(x), round(y)
        self.c.create_rectangle(x, y, x + width, y + 3, fill=pal.gauge, width=0)
        low = left < dino.GLIDE_LOW
        if left > 0 and not (low and (self.game.t // 5) % 2):
            fill = max(2, round(width * left))
            self.c.create_rectangle(x, y, x + fill, y + 3, fill=pal.red if low else pal.title, width=0)

    def _burst(self, cx, cy, k: int, color) -> None:
        """부딪힌 자리의 섬광 — 가운데 덩이와 여덟 방향 점이 프레임마다 밖으로 번진다."""
        u = dino.U
        bx, by = round(cx / u) * u, round(cy / u) * u
        if k < 4:
            self.c.create_rectangle(bx - 2 * u, by - u, bx + 2 * u, by + u, fill=color, width=0)
            self.c.create_rectangle(bx - u, by - 2 * u, bx + u, by + 2 * u, fill=color, width=0)
        for i in range(8):
            a = math.pi * i / 4
            for r in (8 + k * 3, 14 + k * 4):
                x = round((cx + r * math.cos(a)) / u) * u
                y = round((cy + r * 0.8 * math.sin(a)) / u) * u
                self.c.create_rectangle(x, y, x + u, y + u, fill=color, width=0)

    def _ring(self, cx, cy, r, color, turn: int) -> None:
        """도트 점선 고리 — 반지름 r, `turn` 만큼 돌려서(돌아가 보이게)."""
        u = dino.U
        n = max(16, int(r * 1.5))            # 고리 둘레의 점 수
        ry = r * 0.82                        # 위아래로 조금 납작하게 (공룡이 옆으로 길다)
        for i in range(n):
            if (i + turn) % 4 == 0:          # 넷에 하나는 비워 점선으로 (돌아 보인다)
                continue
            a = 2 * math.pi * i / n
            x = round((cx + r * math.cos(a)) / u) * u
            y = round((cy + ry * math.sin(a)) / u) * u
            self.c.create_rectangle(x, y, x + u, y + u, fill=color, width=0)

    def _cells(self, cells, x, y, color) -> None:
        """낱칸 몇 개 (눈 파내기)."""
        bx, by = round(x), round(y)
        u = dino.U
        for col, row in cells:
            self.c.create_rectangle(bx + col * u, by + row * u, bx + col * u + u, by + row * u + u,
                                    fill=color, width=0)


# ---------------------------------------------------------------- 혼자 띄워 보기
def _main() -> None:
    import cooldown_env

    cooldown_env.heal_self()
    from skins.base import set_palette

    args = sys.argv[1:]
    shot = bool(args) and args[0] == "shot"
    theme = next((a for a in args if a in ("light", "dark")), "auto")
    width = next((int(a[2:]) for a in args if a.startswith("w=")), dino.W)
    if not shot and args and args[0].isdigit():
        width = int(args[0])
    set_palette(theme)
    root = tk.Tk()
    root.title("공룡 점프")
    root.configure(bg=P.bg)
    board = DinoBoard(root, width=width, best=0, seed=3 if shot else None,
                      on_exit=root.destroy)
    board.c.pack()
    board.focus()
    if not shot:
        root.mainloop()
        return
    # 그림으로 남기기 — 알아서 뛰는 공룡으로 몇 프레임 돌린 뒤 캡처
    out = args[1]
    frames = int(args[2]) if len(args) > 2 and args[2].isdigit() else 0
    g = board.game
    board._alive = False
    if frames:
        g.press_jump()
        g.release_jump()
        for _ in range(frames):
            if g.state != "run":
                break
            dino._bot(g)
            g.step()
    if "over" in args and g.state == "run":
        g._crash()
    board.draw()
    root.attributes("-topmost", True)
    root.update()
    time.sleep(0.4)
    from PIL import ImageGrab

    x, y = board.c.winfo_rootx(), board.c.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + width, y + dino.H)).save(out)
    print(out, g.state, g.score, flush=True)
    root.destroy()
    os._exit(0)


if __name__ == "__main__":
    _main()
