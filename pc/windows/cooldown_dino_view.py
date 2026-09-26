"""
공룡 점프 판 — `cooldown_dino.Game` 을 Tk 캔버스에 그린다
=========================================================
규칙은 `pc/cooldown_dino.py` 한 곳이고 여기서는 **그리기와 누르기만** 한다.
앱은 팝업(`_open_panel`) 안에 `DinoBoard` 하나를 얹는다(`App.open_dino`).

- **매 프레임 지우고 다시 그린다.** 도트 그림은 줄마다 이어진 칸을 한 덩이로 그리므로
  (`cooldown_dino.runs`) 가장 붐빌 때도 도형이 300개 안쪽이다.
- **한 걸음은 1/60초로 고정**하고, 흐른 시간만큼 걸음을 밟은 뒤 한 번 그린다. 윈도우의 기본
  타이머는 15.6ms 눈금이라 `after(16)` 이 16ms 와 31ms 를 오간다 — 판이 떠 있는 동안만
  `timeBeginPeriod(1)` 로 눈금을 1ms 로 당긴다(닫으면 되돌린다).
- **포커스를 잃으면 멈춘다.** 딴 창을 누른 사이 혼자 달리다 부딪혀 있으면 억울하다.
- 색은 테마(`P`)를 따르고, 밤(700점마다 12초)에는 판만 반대 테마로 뒤집는다(크롬과 같다).

혼자 띄워 보기: `python pc/windows/cooldown_dino_view.py`
그림으로 남기기: `python pc/windows/cooldown_dino_view.py shot out.png [프레임] [light|dark] [over]`
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
if __name__ == "__main__":
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.dirname(HERE))

import cooldown_dino as dino  # noqa: E402
from skins.base import DARK, KR, LIGHT, NUM, P  # noqa: E402
from skins.claudi import MASCOT_COLOR  # noqa: E402

STEP = 1.0 / dino.FPS
MAX_CATCH_UP = 5      # 한 번에 밟는 걸음의 상한 — 창을 끌던 사이 몇 초가 흘러도 순간이동하지 않게
HINT = "스페이스 · 클릭 점프    ↓ 숙이기"


class DinoBoard:
    """판 하나. `top` 에 키를 걸고 `parent` 에 캔버스를 얹는다.

    `on_best(점수)` 는 최고 기록을 넘긴 판이 끝날 때 한 번 불린다(앱이 저장한다).
    """

    def __init__(self, top: tk.Misc, parent: tk.Misc, best: int = 0, on_best=None,
                 seed: int | None = None) -> None:
        self.top = top
        self.on_best = on_best
        self.game = dino.Game(seed=seed, best=best)
        self.c = tk.Canvas(parent, width=dino.W, height=dino.H, bg=P.bg,
                           highlightthickness=0, bd=0, cursor="hand2")
        self.paused = False
        self._saved_over = False
        self._alive = True
        self._last = time.perf_counter()
        self._acc = 0.0
        self._fine_timer = False
        self._bind()
        self._timer_fine(True)
        self.c.bind("<Destroy>", lambda e: self.close() if e.widget is self.c else None)
        self.draw()
        self.c.after(int(STEP * 1000), self._loop)

    # -------------------------------------------------- 누르기
    def _bind(self) -> None:
        t = self.top
        for key in ("<KeyPress-space>", "<KeyPress-Up>"):
            t.bind(key, lambda _e: self._press_jump())
        for key in ("<KeyRelease-space>", "<KeyRelease-Up>"):
            t.bind(key, lambda _e: self.game.release_jump())
        t.bind("<KeyPress-Down>", lambda _e: self.game.press_duck())
        t.bind("<KeyRelease-Down>", lambda _e: self.game.release_duck())
        self.c.bind("<Button-1>", lambda _e: self._press_jump())
        self.c.bind("<ButtonRelease-1>", lambda _e: self.game.release_jump())
        t.bind("<FocusIn>", lambda _e: self._focus(True), add="+")
        t.bind("<FocusOut>", lambda _e: self._focus(False), add="+")

    def _press_jump(self) -> None:
        if self.paused:            # 멈춘 판을 누르면 이어서 — 그 누르기로 뛰지는 않는다
            self.paused = False
            self._last = time.perf_counter()
            return
        if self.game.state == "over" and self.game.over_t >= dino.OVER_WAIT:
            self._saved_over = False
        self.game.press_jump()

    def _focus(self, on: bool) -> None:
        """딴 창으로 가면 멈춘다. 포커스가 판 안에서 옮겨 다니는 것은 무시한다."""
        def check():
            try:
                foc = self.top.focus_displayof()
            except (KeyError, tk.TclError):
                foc = None
            inside = foc is not None and foc.winfo_toplevel() is self.top
            if not inside and self.game.state == "run":
                self.paused = True
                self.game.release_jump()
                self.game.release_duck()
        if not on:
            try:
                self.top.after(120, check)
            except tk.TclError:
                pass

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
        self._acc += now - self._last
        self._last = now
        if self.paused:
            self._acc = 0.0
        else:
            n = 0
            while self._acc >= STEP and n < MAX_CATCH_UP:
                self.game.step()
                self._acc -= STEP
                n += 1
            if n == MAX_CATCH_UP:
                self._acc = 0.0
        g = self.game
        if g.state == "over" and not self._saved_over:
            self._saved_over = True
            if g.new_best and self.on_best:
                self.on_best(g.best)
        try:
            self.draw()
            wait = max(1, int((STEP - self._acc) * 1000))
            self.c.after(wait, self._loop)
        except tk.TclError:   # 판이 닫혔다
            self.close()

    # -------------------------------------------------- 그리기
    def _colors(self):
        """판에 쓸 색 한 벌 — 지금 테마(`P`), 밤이면 반대 테마."""
        pal = P
        if self.game.night > 0:
            pal = LIGHT if P.bg == DARK.bg else DARK
        return pal

    def draw(self) -> None:
        c, g = self.c, self.game
        pal = self._colors()
        if c.cget("bg") != pal.bg:
            c.configure(bg=pal.bg)
        c.delete("all")
        # 구름 — 판보다 흐리게, 제일 뒤에
        for x, y in g.clouds:
            self._art(dino.CLOUD, x, y, pal.track)
        # 땅 — 선 하나와 흘러가는 자갈
        c.create_rectangle(0, dino.GROUND - 1, dino.W, dino.GROUND, fill=pal.label, width=0)
        for x, depth, w in g.pebbles:
            xi = round(x)
            c.create_rectangle(xi, dino.GROUND + depth, xi + w, dino.GROUND + depth + 1,
                               fill=pal.faint, width=0)
        # 장애물
        for ob in g.obstacles:
            color = pal.label if ob.kind == "bird" else pal.green
            for art, x, y, flip in ob.parts():
                self._art(art, x, y, color, flip)
                if ob.kind == "bird":
                    col, row = dino.BIRD_EYE[ob.frame % 2]
                    self._cells(((col, row),), x, y, pal.bg)
        # 공룡
        pose = g.pose
        self._art(dino.POSES[pose], dino.DINO_X, g.dino_y, MASCOT_COLOR)
        eyes = (dino.DUCK_EYE if pose.startswith("duck") else dino.DINO_EYE)[g.eye]
        self._cells(eyes, dino.DINO_X, g.dino_y, pal.bg)
        # 점수 — 오른쪽 위 (HI 최고 · 지금)
        text = f"{g.shown_score:05d}" if g.score_visible else ""
        c.create_text(dino.W - 12, 14, text=text, anchor="ne", fill=pal.sub,
                      font=(NUM, 11, "bold"))
        if g.best > 0 or g.state == "over":
            c.create_text(dino.W - 70, 14, text=f"HI {g.best:05d}", anchor="ne",
                          fill=pal.label, font=(NUM, 11))
        if g.state == "ready":
            c.create_text(dino.W / 2, 56, text=HINT, fill=pal.label, font=(KR, 9))
        elif g.state == "over":
            c.create_text(dino.W / 2, 50, text="G A M E   O V E R", fill=pal.title,
                          font=(NUM, 12, "bold"))
            rw, _ = dino.size(dino.RESTART)
            self._art(dino.RESTART, dino.W / 2 - rw / 2, 68, pal.title)
        if self.paused:
            c.create_text(dino.W / 2, 56, text="일시 정지 · 눌러서 이어 하기",
                          fill=pal.title, font=(KR, 10, "bold"))

    def _art(self, rows, x, y, color, flip=False) -> None:
        """도트 그림 한 장 — 줄마다 이어진 칸을 한 덩이로. 칸이 정수 픽셀에 맞게 한 번만 반올림."""
        bx, by = round(x), round(y)
        for rx, ry, rw, rh in dino._art_runs(rows, flip):
            self.c.create_rectangle(bx + rx, by + ry, bx + rx + rw, by + ry + rh,
                                    fill=color, width=0)

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
    set_palette(theme)
    root = tk.Tk()
    root.title("공룡 점프")
    root.configure(bg=P.bg)
    frame = tk.Frame(root, bg=P.bg, padx=18, pady=14)
    frame.pack()
    board = DinoBoard(root, frame, best=0, seed=3 if shot else None)
    board.c.pack()
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
    ImageGrab.grab(bbox=(x, y, x + dino.W, y + dino.H)).save(out)
    print(out, g.state, g.score)
    root.destroy()
    os._exit(0)


if __name__ == "__main__":
    _main()
