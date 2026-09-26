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

혼자 띄워 보기: `python pc/windows/cooldown_dino_view.py [너비]`
그림으로 남기기: `python pc/windows/cooldown_dino_view.py shot out.png [프레임] [light|dark] [over] [w=460]`
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
PAUSED = "일시 정지 · 눌러서 이어 하기"


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
                g.step()
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

    # -------------------------------------------------- 그리기
    def _colors(self):
        """판에 쓸 색 한 벌 — 지금 테마(`P`), 밤이면 반대 테마."""
        pal = P
        if self.game.night > 0:
            pal = LIGHT if P.bg == DARK.bg else DARK
        return pal

    def draw(self) -> None:
        c, g, w = self.c, self.game, self.w
        pal = self._colors()
        if c.cget("bg") != pal.bg:
            c.configure(bg=pal.bg)
        c.delete("all")
        # 구름 — 판보다 흐리게, 제일 뒤에
        for x, y in g.clouds:
            self._art(dino.CLOUD, x, y, pal.track)
        # 땅 — 선 하나와 흘러가는 자갈
        c.create_rectangle(0, dino.GROUND - 1, w, dino.GROUND, fill=pal.label, width=0)
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
                    col, row = dino.BIRD_EYE[ob.frame % 2]
                    self._cells(((col, row),), x, y, pal.bg)
        # 공룡
        pose = g.pose
        self._art(dino.POSES[pose], dino.DINO_X, g.dino_y, MASCOT_COLOR)
        eyes = (dino.DUCK_EYE if pose.startswith("duck") else dino.DINO_EYE)[g.eye]
        self._cells(eyes, dino.DINO_X, g.dino_y, pal.bg)
        # 닫기 ✕ — 왼쪽 위 구석
        self._art(dino.CLOSE, *dino.CLOSE_AT, pal.title if self._close_hot else pal.faint)
        # 점수 — 오른쪽 위 (HI 최고 · 지금)
        text = f"{g.shown_score:05d}" if g.score_visible else ""
        c.create_text(w - 12, 14, text=text, anchor="ne", fill=pal.sub,
                      font=(NUM, 11, "bold"))
        if g.best > 0 or g.state == "over":
            c.create_text(w - 70, 14, text=f"HI {g.best:05d}", anchor="ne",
                          fill=pal.label, font=(NUM, 11))
        if self.paused:
            c.create_text(w / 2, 56, text=PAUSED, fill=pal.title, font=(KR, 10, "bold"))
        elif g.state == "ready":
            c.create_text(w / 2, 56, text=HINT, fill=pal.label, font=(KR, 9))
        elif g.state == "over":
            c.create_text(w / 2, 50, text="G A M E   O V E R", fill=pal.title,
                          font=(NUM, 12, "bold"))
            rw, _ = dino.size(dino.RESTART)
            self._art(dino.RESTART, w / 2 - rw / 2, 68, pal.title)

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
