"""
캐릭터팩 만들기 — 바 캐릭터를 만들고 동작마다 그림을 **한 장씩 골라** 넣는 창.

    python cooldown_pack_import.py          혼자 띄우기
    앱: 메인 화면 > 위젯 모양 > [캐릭터팩 만들기](이름 창부터) · [그림 고치기]
        (바에 세울 한 명은 「바 캐릭터」에서 고른다. 팩 파일 넣기·내보내기는 메인 화면 단추)

위: 캐릭터 이름 단추들 + [+ 캐릭터]. 그 아래 동작 묶음 단추 다섯(평소·이동·상호작용·상태·감정, `pack.GROUPS`.
동작이 스물셋이라 한 화면에 다 펴면 창이 화면보다 길어진다)과 고른 묶음의 동작 줄들,
줄마다 넣은 그림 작은 그림 + [+]. [+] → 「폴더에서 고르기」(폴더 하나를 열어 그 안 그림을 작은 그림
격자로 펼쳐 보고 한 장씩 골라 넣기, 이 캐릭터의 다른 동작에 이미 넣은 그림은 표시),
「파일에서 고르기」(그대로 복사, 움직임 유지), 「화면에서 따오기」(네모로 골라 찍고, 미리 보기에서
바탕 지우기·움직임 담기). 작은 그림을 누르면 위 「크게 보기」 칸에 바 높이로 돌려 보이고, 거기서
효과(`pack.EFFECTS` 열 가지)·세기 1~3 을 고르면 그 동작 폴더 `움직임.json` 에 적는다.
★ 작은 그림·고르기 격자·크게 보기는 바와 **같은 코드**(`pack.load_clip`, 폭은 `buddy` 와 같은 셈)로
  구운 장면을 돌린다(`Shelf`: 한 번 굽고 창이 살아 있는 동안 둔다, 줄 세워 하나씩 굽는다 ·
  `Animator`: 창 하나에 타이머 하나, 창을 닫으면 멈춘다).
아래: 그림이 보는 쪽(걷는 쪽에 맞춰 뒤집을 때 씀) · [이 캐릭터 빼기].

★ 한 번에 한 장이다. 후보 수는 동작마다 한도가 다르다(`pack.LIMITS`: 누르면 나오는 동작 2 · 상태 4 ·
  평소 16, 이어 붙이기 묶음은 한 개). 묶음째 받거나 다른 프로그램의 저장 파일을 뒤지는 기능은
  넣지 않는다(사용자 지시 11-19: 필요한 일부만 골라 넣기). 묶음·효과는 동작 폴더의 `움직임.json` 이
  정하고, 여기서는 묶음을 그림 하나처럼(첫 장 + 장 수) 보여 주고 지운다. 그림을 지우면
  `움직임.json` 의 그 이름도 걷어 낸다(`pack.delete_candidate`).
★ 화면 좌표: 이 앱은 배율 인식을 안 켜서 Tk 좌표는 논리 픽셀이고, `ImageGrab` 은 실제 픽셀을
  준다. 그래서 **먼저 화면 전체를 찍고 그 그림 위에서 고르게** 한 뒤 비율로 되돌린다.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.dirname(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import cooldown_env  # noqa: E402

cooldown_env.heal_self()  # ★ tkinter 보다 먼저 — 물려받은 남의 Tcl 경로를 걷어낸다

import tkinter as tk  # noqa: E402
from tkinter import filedialog  # noqa: E402

import cooldown_pack as pack  # noqa: E402
from skins.base import DARK, KR, LIGHT, P  # noqa: E402
from skins.buddy import WIDE_FX, WIDE_K  # noqa: E402

THUMB = 40
THUMB_W = 48  # 작은 그림 칸 폭 (바 그림은 높이보다 넓다)
THUMBS_PER_LINE = 8  # 평소 동작은 16개까지라 두 줄로 접는다
BGS = ((0, "끔"), (12, "약하게"), (28, "보통"), (48, "강하게"))
CAPTURES = ((0, "멈춘 그림"), (2, "2초 담기"), (4, "4초 담기"))
GRAB_MS = 70  # 움직임 담을 때 한 장 간격
BAR_H = 40  # 미리 보기의 바 그림 높이
TICK_MS = 30  # 움직이는 미리보기 타이머 (창 하나에 하나)
PICK_CELL, PICK_PIC = 58, 46  # 폴더에서 고르기 격자 칸·그림 높이
PICK_COLS, PICK_ROWS = 8, 4
POWERS = ((1, "1"), (2, "2"), (3, "3"))


def bar_width(clip, height: int) -> int:
    """바 캐릭터(`buddy.Buddy._raw_for`)와 같은 폭 셈: 높이 1.4 배, 눕거나 도는 효과는 더 넓게."""
    return int(int(height * 1.4) * (WIDE_K if clip.effect in WIDE_FX else 1))


def _alive(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


class Shelf:
    """후보 → 바 크기로 구운 장면 ([(PhotoImage, ms)], 되감을 자리). 한 번 구운 것은 창이 살아 있는
    동안 둔다. 굽기는 줄을 세워 after 로 하나씩 해서, 그림이 많아도 창이 멎지 않는다."""

    def __init__(self, win: tk.Misc):
        self.win = win
        self.done: dict = {}
        self.queue: list = []
        self._job = None

    def get(self, clip, height: int, widget: tk.Widget, ready, fit: int | None = None) -> None:
        """`fit` 를 주면 폭을 그 안으로 줄인다(작은 칸에 그림이 잘리지 않게, 바의 폭 한도와 같은 셈)."""
        key = (clip, height, fit)
        if key in self.done:
            ready(*self.done[key])
            return
        self.queue.append((key, widget, ready))
        self._kick()

    def _kick(self) -> None:
        if self._job is None and self.queue:
            try:
                self._job = self.win.after(1, self._work)
            except tk.TclError:
                self.queue.clear()

    def _work(self) -> None:
        self._job = None
        while self.queue:
            key, widget, ready = self.queue.pop(0)
            if not _alive(widget):
                continue  # 다시 그리며 없어진 칸 (새 칸이 따로 줄을 선다)
            if key not in self.done:
                self.done[key] = self.bake(*key)
            ready(*self.done[key])
            break
        self._kick()

    def bake(self, clip, height: int, fit: int | None = None):
        from PIL import ImageTk

        try:
            width = bar_width(clip, height)
            raw, loop_from = pack.load_clip(clip, height, min(width, fit) if fit else width)
        except Exception:  # 깨진 그림 하나 때문에 창이 죽으면 안 된다
            raw, loop_from = [], 0
        return [(ImageTk.PhotoImage(im, master=self.win), ms) for im, ms in raw], loop_from

    def forget(self, height: int, keep=()) -> None:
        """그 높이로 구운 것 가운데 `keep` 에 없는 후보를 버린다(고르기 격자 쪽을 넘길 때)."""
        keep = set(keep)
        for key in [k for k in self.done if k[1] == height and k[0] not in keep]:
            del self.done[key]

    def stop(self) -> None:
        self.queue.clear()
        if self._job is not None:
            try:
                self.win.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None


class Animator:
    """그림 칸(Label)들을 장면마다 갈아 끼운다. 창 하나에 타이머 하나. 칸이 없어지면 저절로 뺀다.
    장면 넘기기는 바(`buddy._advance`)와 같다: 장면 ms 만큼 머물고, 끝에 닿으면 되감을 자리로."""

    def __init__(self, win: tk.Misc):
        self.win = win
        self.items: dict = {}
        self._job = None
        self._t = 0.0

    def show(self, label: tk.Label, frames, loop_from: int = 0) -> None:
        if not _alive(label):
            return
        key = str(label)
        if not frames:
            label.configure(image="", text="?", fg=P.red)
            self.items.pop(key, None)
            return
        label.configure(image=frames[0][0], text="")
        if len(frames) < 2:
            self.items.pop(key, None)
            return
        self.items[key] = [label, frames, loop_from if loop_from < len(frames) else 0, 0, frames[0][1]]
        if self._job is None:
            self._t = time.monotonic()
            self._job = self.win.after(TICK_MS, self._tick)

    def frame_of(self, label) -> int:
        it = self.items.get(str(label))
        return it[3] if it else 0

    def _tick(self) -> None:
        self._job = None
        now = time.monotonic()
        dt = min(1000.0, (now - self._t) * 1000)
        self._t = now
        for key, it in list(self.items.items()):
            label, frames, loop_from, fi, left = it
            if not _alive(label):
                del self.items[key]
                continue
            left -= dt
            moved = False
            while left <= 0:
                fi += 1
                if fi >= len(frames):
                    fi = loop_from
                left += frames[fi][1]
                moved = True
            it[3], it[4] = fi, left
            if moved:
                label.configure(image=frames[fi][0])
        if self.items:
            try:
                self._job = self.win.after(TICK_MS, self._tick)
            except tk.TclError:
                self.items.clear()

    def stop(self) -> None:
        self.items.clear()
        if self._job is not None:
            try:
                self.win.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None


def segment(parent, options, current, pick) -> tk.Frame:
    """붙은 단추 줄 (고른 것은 초록). options: [(값, 글)]."""
    box = tk.Frame(parent, bg=P.line, padx=1, pady=1)
    for i, (value, text) in enumerate(options):
        on = value == current
        b = tk.Label(box, text=text, bg=P.green if on else P.bg,
                     fg=P.bg if on else P.sub, font=(KR, 9, "bold" if on else "normal"),
                     padx=7, pady=2, cursor="hand2")
        b.pack(side="left", padx=(0 if i == 0 else 1, 0))
        b.bind("<Button-1>", lambda e, v=value: pick(v))
    return box


def bar_tiles(parent, owner, clip) -> tk.Frame:
    """바에 선 모습 두 칸(어두운 바·밝은 바), 바 높이 그대로 돌린다."""
    tiles = tk.Frame(parent, bg=parent["bg"])
    for i, theme in enumerate((DARK, LIGHT)):
        tile = tk.Frame(tiles, bg=theme.bg, width=int(BAR_H * 1.4 * WIDE_K) + 16, height=BAR_H + 8)
        tile.pack(side="left", padx=(0 if i == 0 else 6, 0))
        tile.pack_propagate(False)
        lab = tk.Label(tile, bg=theme.bg, bd=0)
        lab.pack(side="bottom", pady=(0, 2))
        owner.shelf.get(clip, BAR_H, lab, lambda f, lf, w=lab: owner.anim.show(w, f, lf))
    return tiles


def fx_rows(parent, clip, pick, moving: bool | None = None) -> None:
    """효과 열 가지 · 세기 1~3 줄. 움직이는 그림(여러 장)은 효과가 안 먹으므로 줄 대신 한 줄 글."""
    if moving is None:
        moving = len(clip.files) == 1 and pack.is_moving(clip.files[0])
    if moving:
        tk.Label(parent, text="움직이는 그림 · 효과 없이 그대로 재생", bg=parent["bg"], fg=P.sub,
                 font=(KR, 9), anchor="w").pack(fill="x", pady=(6, 0))
        return
    for label, options, cur, make in (
            ("효과", [(e, e) for e in pack.EFFECTS], clip.effect, lambda v: (v, clip.power)),
            ("세기", POWERS, clip.power, lambda v: (clip.effect, v))):
        row = tk.Frame(parent, bg=parent["bg"])
        row.pack(fill="x", pady=(6 if label == "효과" else 3, 0))
        tk.Label(row, text=label, bg=parent["bg"], fg=P.sub, font=(KR, 9), width=4,
                 anchor="w").pack(side="left")
        segment(row, options, cur, lambda v, mk=make: pick(*mk(v))).pack(side="left")


def virtual_screen() -> tuple[int, int, int, int]:
    """가상 화면(모니터 전부) 왼쪽 위·폭·높이 — 이 프로세스 좌표(논리 픽셀)."""
    g = ctypes.windll.user32.GetSystemMetrics
    return g(76), g(77), g(78), g(79)


def grab_all():
    from PIL import ImageGrab

    return ImageGrab.grab(all_screens=True)


class PackImport:
    """그림 넣기 창. `master` 가 있으면 그 위의 Toplevel, 없으면 혼자 Tk."""

    def __init__(self, master: tk.Misc | None = None, root: str = pack.PACK_DIR,
                 on_change=None):
        self.root_dir = root
        self.on_change = on_change
        self.win = tk.Toplevel(master) if master is not None else tk.Tk()
        self.win.title("캐릭터팩 만들기")
        self.win.configure(bg=P.bg)
        self.win.resizable(False, False)
        self._thumbs: list = []
        self.anim = Animator(self.win)
        self.shelf = Shelf(self.win)
        self.sel_key: str | None = None  # 크게 보기 칸에 띄운 후보 (key)
        self.last_folder: str | None = None
        self.picker: FolderPick | None = None
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        chars = pack.all_characters(root)
        self.char = chars[0] if chars else None
        self.group = pack.GROUPS[0][0]  # 펼쳐 보는 동작 묶음
        self.body = tk.Frame(self.win, bg=P.bg, padx=16, pady=12)
        self.body.pack(fill="both", expand=True)
        self._render()

    # -------------------------------------------------- 목록
    def _render(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        self._thumbs = []
        tk.Label(self.body, text="캐릭터팩 만들기", bg=P.bg, fg=P.title,
                 font=(KR, 12, "bold"), anchor="w").pack(fill="x")
        tk.Label(self.body, text=f"캐릭터 {pack.MAX_CHARS}명까지 · 줄 끝 숫자는 넣은 수/넣을 수 있는 수"
                 " · 빈 동작은 비슷한 동작 그림 사용",
                 bg=P.bg, fg=P.faint, font=(KR, 9), anchor="w").pack(fill="x", pady=(0, 8))
        self._chips()
        if self.char is None:
            tk.Label(self.body, text="캐릭터 없음 · [+ 캐릭터]로 이름부터 정하기", bg=P.bg,
                     fg=P.sub, font=(KR, 10), anchor="w").pack(fill="x", pady=16)
        else:
            if not any(pack.clips(self.char, m, self.root_dir) for m in pack.MOTIONS):
                tk.Label(self.body, text=f"{self.char} · 서기 그림 한 장부터 넣기", bg=P.bg,
                         fg=P.green, font=(KR, 10, "bold"), anchor="w").pack(fill="x", pady=(0, 4))
            self._groups()
            self._viewer()
            for motion in dict(pack.GROUPS)[self.group]:
                self._row(motion)
            self._char_foot()
        foot = tk.Frame(self.body, bg=P.bg)
        foot.pack(fill="x", pady=(10, 0))
        tk.Label(foot, text=self.root_dir, bg=P.bg, fg=P.faint, font=(KR, 8),
                 anchor="w").pack(side="left")
        self._button(foot, "닫기", self.close).pack(side="right")

    def _chips(self) -> None:
        bar = tk.Frame(self.body, bg=P.bg)
        bar.pack(fill="x", pady=(0, 8))
        chars = pack.all_characters(self.root_dir)
        for name in chars:
            on = name == self.char
            b = tk.Label(bar, text=name, bg=P.green if on else P.track,
                         fg=P.bg if on else P.sub, font=(KR, 10, "bold" if on else "normal"),
                         padx=12, pady=4, cursor="hand2")
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e, n=name: self._pick_char(n))
        if len(chars) < pack.MAX_CHARS:
            self._button(bar, "+ 캐릭터", self._new_char).pack(side="left")

    def _groups(self) -> None:
        """동작 묶음 단추 (평소 · 이동 · 상호작용 · 상태 · 감정)."""
        seg = tk.Frame(self.body, bg=P.line, padx=1, pady=1)
        seg.pack(anchor="w", pady=(0, 6))
        for i, (title, _motions) in enumerate(pack.GROUPS):
            on = title == self.group
            b = tk.Label(seg, text=title, bg=P.green if on else P.track,
                         fg=P.bg if on else P.sub, font=(KR, 9, "bold" if on else "normal"),
                         padx=12, pady=3, cursor="hand2")
            b.pack(side="left", padx=(0 if i == 0 else 1, 0))
            b.bind("<Button-1>", lambda e, t=title: self._pick_group(t))

    def _pick_group(self, title: str) -> None:
        self.group = title
        self.sel_key = None
        self._render()

    def _pick_char(self, name: str) -> None:
        self.char = name
        self.sel_key = None
        self._render()

    # -------------------------------------------------- 크게 보기 · 효과 고르기
    def _selected(self):
        """크게 보기 칸에 띄울 (동작, 후보). 지금 묶음 안에서 고른 것만."""
        if self.sel_key is None or self.char is None:
            return None
        for motion in dict(pack.GROUPS)[self.group]:
            for c in pack.all_candidates(self.char, motion, self.root_dir):
                if c.key == self.sel_key:
                    return motion, c
        return None

    def _viewer(self) -> None:
        box = tk.Frame(self.body, bg=P.track, padx=10, pady=8)
        box.pack(fill="x", pady=(0, 6))
        got = self._selected()
        if got is None:
            tk.Label(box, text="크게 보기 · 그림을 누르면 바 높이로 움직여 보임", bg=P.track,
                     fg=P.faint, font=(KR, 9), anchor="w").pack(fill="x")
            return
        motion, clip = got
        bar_tiles(box, self, clip).pack(side="left")
        side = tk.Frame(box, bg=P.track)
        side.pack(side="left", fill="x", expand=True, padx=(12, 0))
        name = os.path.basename(clip.files[0])
        if len(clip.files) > 1:
            name = f"{clip.key.split('|')[-1]} · {len(clip.files)}장 이어 붙이기"
        tk.Label(side, text=f"{motion} · {name}", bg=P.track, fg=P.title,
                 font=(KR, 9, "bold"), anchor="w").pack(fill="x")
        fx_rows(side, clip, lambda fx, pw, c=clip: self._set_fx(c, fx, pw))

    def _select(self, clip) -> None:
        self.sel_key = None if self.sel_key == clip.key else clip.key
        self._render()

    def _set_fx(self, clip, effect: str, power: int) -> None:
        if pack.set_clip_fx(clip, effect, power, self.root_dir):
            self._changed()

    def _new_char(self) -> None:
        """이름 한 칸짜리 작은 창. 만들면 그 캐릭터의 동작 줄이 바로 열린다(이름 → 그림 한 흐름)."""
        if len(pack.all_characters(self.root_dir)) >= pack.MAX_CHARS:
            return
        top = tk.Toplevel(self.win)
        top.title("새 캐릭터")
        top.configure(bg=P.bg)
        top.resizable(False, False)
        top.transient(self.win)
        box = tk.Frame(top, bg=P.bg, padx=16, pady=12)
        box.pack()
        tk.Label(box, text="캐릭터 이름", bg=P.bg, fg=P.title, font=(KR, 10),
                 anchor="w").pack(fill="x")
        entry = tk.Entry(box, font=(KR, 11), width=18, bg=P.track, fg=P.title,
                         insertbackground=P.title, relief="flat")
        entry.pack(fill="x", pady=(4, 8), ipady=3)
        entry.focus_set()

        def ok(_e=None):
            try:
                name = pack.add_character(entry.get(), self.root_dir)
            except ValueError:
                return
            top.destroy()
            self.char = name
            self._changed()

        row = tk.Frame(box, bg=P.bg)
        row.pack(fill="x")
        self._button(row, "만들기", ok, primary=True).pack(side="right")
        self._button(row, "그만두기", top.destroy).pack(side="right", padx=(0, 6))
        entry.bind("<Return>", ok)
        top.bind("<Escape>", lambda e: top.destroy())
        # 그냥 두면 화면 왼쪽 위 아무 데나 뜬다(11-20 지적) — 이 창 한가운데 위에 띄운다
        top.update_idletasks()
        w, h = top.winfo_reqwidth(), top.winfo_reqheight()
        x = self.win.winfo_rootx() + (self.win.winfo_width() - w) // 2
        y = self.win.winfo_rooty() + 60
        top.geometry(f"+{max(0, x)}+{max(0, y)}")
        top.lift()
        entry.focus_set()

    def _char_foot(self) -> None:
        row = tk.Frame(self.body, bg=P.bg)
        row.pack(fill="x", pady=(8, 0))
        tk.Label(row, text="그림이 보는 쪽", bg=P.bg, fg=P.title, font=(KR, 10),
                 anchor="w").pack(side="left")
        right = pack.faces_right(self.char, self.root_dir)
        seg = tk.Frame(row, bg=P.line, padx=1, pady=1)
        seg.pack(side="left", padx=(10, 0))
        for i, (text, val) in enumerate((("왼쪽", "왼쪽"), ("오른쪽", "오른쪽"))):
            on = (val == "오른쪽") == right
            b = tk.Label(seg, text=text, bg=P.green if on else P.track, fg=P.bg if on else P.sub,
                         font=(KR, 9, "bold" if on else "normal"), padx=10, pady=3, cursor="hand2")
            b.pack(side="left", padx=(0 if i == 0 else 1, 0))
            b.bind("<Button-1>", lambda e, v=val: self._set_face(v))
        self._button(row, "이 캐릭터 빼기", self._drop_char).pack(side="right")
        if any(pack.clips(self.char, m, self.root_dir) for m in pack.MOTIONS):
            self._button(row, "내보내기", self._export).pack(side="right", padx=(0, 6))
        self.note = tk.Label(self.body, text="", bg=P.bg, fg=P.sub, font=(KR, 9), anchor="w")
        self.note.pack(fill="x")

    def _export(self) -> None:
        """이 캐릭터를 팩 파일 하나로 저장(`<이름>.캐릭터팩.zip`)."""
        dest = filedialog.asksaveasfilename(
            parent=self.win, title=f"{self.char} 내보내기",
            initialfile=self.char + pack.PACK_SUFFIX, defaultextension=pack.PACK_SUFFIX,
            filetypes=[("캐릭터팩", "*" + pack.PACK_SUFFIX)])
        if not dest:
            return
        if not dest.lower().endswith(pack.PACK_SUFFIX):
            dest = os.path.splitext(dest)[0] + pack.PACK_SUFFIX
        try:
            pack.export_pack(self.char, dest, self.root_dir)
            self.note.configure(text=f"「{self.char}」 내보냄 · {os.path.basename(dest)}", fg=P.sub)
        except pack.PackError as e:
            self.note.configure(text=f"내보내지 못함: {e}", fg=P.red)
        except OSError:
            self.note.configure(text="내보내지 못함: 그 자리에 저장 못 함", fg=P.red)

    def _set_face(self, val: str) -> None:
        pack.set_char_setting(self.char, "보는 쪽", val, self.root_dir)
        self._changed()

    def _drop_char(self) -> None:
        # 지우지 않고 이름 앞에 _ 를 붙여 빼 둔다 (폴더에서 _ 를 떼면 돌아온다)
        pack.remove_character(self.char, self.root_dir)
        chars = pack.all_characters(self.root_dir)
        self.char = chars[0] if chars else None
        self._changed()

    def _row(self, motion: str) -> None:
        row = tk.Frame(self.body, bg=P.bg)
        row.pack(fill="x", pady=2)
        name = tk.Frame(row, bg=P.bg, width=220, height=THUMB + 4)
        name.pack(side="left")
        name.pack_propagate(False)
        tk.Label(name, text=motion, bg=P.bg, fg=P.title, font=(KR, 10, "bold"),
                 anchor="w").pack(side="left")
        tk.Label(name, text=pack.MOTION_LABELS[motion], bg=P.bg, fg=P.faint, font=(KR, 8),
                 anchor="w").pack(side="left", padx=(6, 0))
        cands = pack.all_candidates(self.char, motion, self.root_dir)
        tk.Label(name, text=f"{len(cands)}/{pack.limit(motion)}", bg=P.bg, fg=P.faint,
                 font=(KR, 8), anchor="e").pack(side="right", padx=(0, 6))
        grid = tk.Frame(row, bg=P.bg)
        grid.pack(side="left")
        cells = [lambda g, c=c: self._thumb(g, c) for c in cands]
        if pack.room_left(self.char, motion, self.root_dir) > 0:
            cells.append(lambda g, m=motion: self._add_cell(g, m))
        for i, make in enumerate(cells):
            w = make(grid)
            w.grid(row=i // THUMBS_PER_LINE, column=i % THUMBS_PER_LINE, padx=2, pady=1)

    def _add_cell(self, grid: tk.Frame, motion: str) -> tk.Widget:
        add = tk.Label(grid, text="+", bg=P.track, fg=P.sub, font=(KR, 14),
                       width=3, cursor="hand2")
        add.bind("<Button-1>", lambda e, m=motion, w=add: self._add_menu(m, w))
        return add

    def _thumb(self, grid: tk.Frame, clip) -> tk.Widget:
        on = clip.key == self.sel_key
        cell = tk.Frame(grid, bg=P.green if on else P.track, width=THUMB_W, height=THUMB + 4)
        cell.pack_propagate(False)
        pic = tk.Label(cell, bg=P.track, bd=0, cursor="hand2")
        pic.pack(expand=True, fill="both", padx=2 if on else 0, pady=2 if on else 0)
        self.shelf.get(clip, THUMB - 6, pic, lambda f, lf, w=pic: self.anim.show(w, f, lf),
                       fit=THUMB_W - 6)
        for w in (cell, pic):
            w.bind("<Button-1>", lambda e, c=clip: self._select(c))
        if len(clip.files) > 1:  # 이어 붙이기 묶음: 첫 장 + 장 수
            tk.Label(cell, text=f"{len(clip.files)}장", bg=P.track, fg=P.sub,
                     font=(KR, 7)).place(x=1, rely=1.0, y=-1, anchor="sw")
        x = tk.Label(cell, text="✕", bg=P.track, fg=P.faint, font=(KR, 7), cursor="hand2")
        x.place(relx=1.0, x=-1, y=0, anchor="ne")
        x.bind("<Button-1>", lambda e, c=clip: self._delete(c))
        return cell

    def _delete(self, clip) -> None:
        pack.delete_candidate(clip, self.root_dir)
        self._changed()

    def _add_menu(self, motion: str, widget: tk.Widget) -> None:
        m = tk.Menu(self.win, tearoff=0)
        m.add_command(label="폴더에서 고르기", command=lambda: self._from_folder(motion))
        m.add_command(label="파일에서 고르기", command=lambda: self._from_file(motion))
        m.add_command(label="화면에서 따오기", command=lambda: self._from_screen(motion))
        m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def _changed(self) -> None:
        self._render()
        if self.on_change:
            self.on_change()

    def close(self) -> None:
        if self.picker is not None:
            self.picker.close()
        self.anim.stop()
        self.shelf.stop()
        self.win.destroy()

    def _button(self, parent, text, command, primary=False) -> tk.Label:
        b = tk.Label(parent, text=text, bg=P.green if primary else P.track,
                     fg=P.bg if primary else P.sub, font=(KR, 9, "bold" if primary else "normal"),
                     padx=12, pady=4, cursor="hand2")
        b.bind("<Button-1>", lambda e: command())
        return b

    # -------------------------------------------------- 가져오기
    def _from_file(self, motion: str) -> None:
        # 한 장만 고른다 (여러 장 고르기는 일부러 막는다). 파일은 다시 굽지 않고 그대로 복사한다 —
        # 움직이는 webp·gif 의 움직임과 투명이 그대로 산다.
        path = filedialog.askopenfilename(
            parent=self.win, title=f"{self.char} · {motion} 그림 고르기",
            filetypes=[("그림", "*.png *.gif *.webp *.apng")])
        if not path:
            return
        try:
            pack.read_frames(path)  # 읽히는 그림인지만 본다
            pack.add_file(self.char, motion, path, self.root_dir)
        except Exception:
            return
        self._changed()

    def _from_folder(self, motion: str, folder: str | None = None) -> None:
        if folder is None:
            folder = filedialog.askdirectory(parent=self.win, title=f"{self.char} · {motion} 그림 폴더 고르기",
                                             initialdir=self.last_folder or os.path.expanduser("~"))
        if not folder:
            return
        self.last_folder = folder
        if self.picker is not None:
            self.picker.close()
        self.picker = FolderPick(self, motion, folder)

    def _from_screen(self, motion: str) -> None:
        self.win.withdraw()
        self.win.after(300, lambda: self._snap(motion))

    def _snap(self, motion: str) -> None:
        shot = grab_all()
        Picker(self, shot, lambda rect: self._picked(motion, shot, rect))

    def _picked(self, motion: str, shot, rect) -> None:
        self.win.deiconify()
        if rect is None:
            return
        Preview(self, motion, [(shot.crop(rect), 100)], rect=rect)


class FolderPick:
    """폴더 하나의 그림을 격자로 펼쳐 움직여 보이고, 한 장씩 골라 지금 동작에 넣는다.
    이 캐릭터의 다른 동작에 이미 넣은 그림(내용이 같은 것)은 「○○에 있음」으로 표시하고 안 넣는다.
    묶음째 넣는 단추는 없다(사용자 지시 11-19: 필요한 것만 골라 넣기)."""

    def __init__(self, owner: PackImport, motion: str, folder: str):
        self.owner, self.motion, self.folder = owner, motion, folder
        self.char = owner.char
        self.files = pack.folder_pictures(folder)
        self.page = 0
        self.sel: str | None = None
        self.fx: dict = {}  # 파일 → (효과, 세기) 고른 것
        self._digests: dict = {}
        self.top = tk.Toplevel(owner.win)
        self.top.title(f"{self.char} · {motion} · 폴더에서 고르기")
        self.top.configure(bg=P.bg)
        self.top.resizable(False, False)
        self.top.transient(owner.win)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.top.bind("<Escape>", lambda e: self.close())
        self._render()

    @property
    def pages(self) -> int:
        per = PICK_COLS * PICK_ROWS
        return max(1, (len(self.files) + per - 1) // per)

    def _shown(self) -> list[str]:
        per = PICK_COLS * PICK_ROWS
        return self.files[self.page * per:(self.page + 1) * per]

    def _digest(self, path: str):
        if path not in self._digests:
            self._digests[path] = pack.file_digest(path)
        return self._digests[path]

    def clip_for(self, path: str):
        """이 그림을 지금 동작에 넣으면 바에서 틀 후보 (고른 효과, 안 골랐으면 동작 기본 효과)."""
        fx, power = self.fx.get(path) or pack.DEFAULT_FX.get(self.motion, ("없음", 2))
        return pack.Clip(path, [path], fx, power)

    def _render(self) -> None:
        for w in self.top.winfo_children():
            w.destroy()
        o = self.owner
        used = pack.used_pictures(self.char, o.root_dir)
        room = pack.room_left(self.char, self.motion, o.root_dir)
        have = len(pack.all_candidates(self.char, self.motion, o.root_dir))
        body = tk.Frame(self.top, bg=P.bg, padx=16, pady=12)
        body.pack()
        head = tk.Frame(body, bg=P.bg)
        head.pack(fill="x")
        tk.Label(head, text=f"{self.char} · {self.motion} · {pack.MOTION_LABELS[self.motion]}", bg=P.bg,
                 fg=P.title, font=(KR, 11, "bold"), anchor="w").pack(side="left")
        tk.Label(head, text=f"넣은 수 {have}/{pack.limit(self.motion)}", bg=P.bg,
                 fg=P.faint if room else P.amber, font=(KR, 9)).pack(side="right")
        path_row = tk.Frame(body, bg=P.bg)
        path_row.pack(fill="x", pady=(2, 8))
        tk.Label(path_row, text=f"{self.folder} · 그림 {len(self.files)}장", bg=P.bg, fg=P.faint,
                 font=(KR, 8), anchor="w").pack(side="left")
        o._button(path_row, "다른 폴더", lambda: o._from_folder(self.motion)).pack(side="right")
        grid = tk.Frame(body, bg=P.bg)
        grid.pack(anchor="w")
        shown = self._shown()
        o.shelf.forget(PICK_PIC, keep=[self.clip_for(p) for p in shown])
        if not shown:
            tk.Label(grid, text="이 폴더에 그림(png·gif·webp) 없음", bg=P.bg, fg=P.sub,
                     font=(KR, 10)).pack(pady=20)
        for i, path in enumerate(shown):
            self._cell(grid, path, used.get(self._digest(path))).grid(
                row=i // PICK_COLS, column=i % PICK_COLS, padx=2, pady=2)
        if self.pages > 1:
            nav = tk.Frame(body, bg=P.bg)
            nav.pack(pady=(6, 0))
            if self.page > 0:
                o._button(nav, "앞 쪽", lambda: self._go(-1)).pack(side="left")
            tk.Label(nav, text=f"{self.page + 1}/{self.pages}쪽", bg=P.bg, fg=P.sub,
                     font=(KR, 9), padx=10).pack(side="left")
            if self.page < self.pages - 1:
                o._button(nav, "다음 쪽", lambda: self._go(1)).pack(side="left")
        self._viewer(body, used, room)

    def _cell(self, grid, path: str, used_in: str | None) -> tk.Widget:
        on = path == self.sel
        back = P.gauge if used_in else P.track
        cell = tk.Frame(grid, bg=P.green if on else back, width=PICK_CELL, height=PICK_CELL)
        cell.pack_propagate(False)
        pic = tk.Label(cell, bg=back, bd=0, cursor="hand2")
        pic.pack(expand=True, fill="both", padx=2 if on else 0, pady=2 if on else 0)
        self.owner.shelf.get(self.clip_for(path), PICK_PIC, pic,
                             lambda f, lf, w=pic: self.owner.anim.show(w, f, lf), fit=PICK_CELL - 6)
        if used_in:
            tk.Label(cell, text=f"{used_in}에 있음", bg=back, fg=P.amber,
                     font=(KR, 7)).place(x=2, rely=1.0, y=-2, anchor="sw")
        for w in (cell, pic):
            w.bind("<Button-1>", lambda e, p=path: self._select(p))
            w.bind("<Double-Button-1>", lambda e, p=path: self._add(p))
        return cell

    def _viewer(self, body, used: dict, room: int) -> None:
        box = tk.Frame(body, bg=P.track, padx=10, pady=8)
        box.pack(fill="x", pady=(10, 0))
        foot = tk.Frame(body, bg=P.bg)
        foot.pack(fill="x", pady=(10, 0))
        self.owner._button(foot, "닫기", self.close).pack(side="right")
        if self.sel is None:
            tk.Label(box, text="크게 보기 · 그림을 누르면 바 높이로 움직여 보임", bg=P.track,
                     fg=P.faint, font=(KR, 9), anchor="w").pack(fill="x")
            return
        clip = self.clip_for(self.sel)
        bar_tiles(box, self.owner, clip).pack(side="left")
        side = tk.Frame(box, bg=P.track)
        side.pack(side="left", fill="x", expand=True, padx=(12, 0))
        tk.Label(side, text=os.path.basename(self.sel), bg=P.track, fg=P.title,
                 font=(KR, 9, "bold"), anchor="w").pack(fill="x")
        fx_rows(side, clip, lambda fx, pw: self._set_fx(fx, pw))
        used_in = used.get(self._digest(self.sel))
        if used_in:
            text, ok = f"{used_in}에 이미 넣은 그림", False
        elif room <= 0:
            text, ok = f"{self.motion} 꽉 참 ({pack.limit(self.motion)}개)", False
        else:
            text, ok = f"{self.motion}에 넣기", True
        if ok:
            self.owner._button(foot, text, lambda: self._add(self.sel), primary=True).pack(
                side="right", padx=(0, 6))
        else:
            tk.Label(foot, text=text, bg=P.bg, fg=P.amber, font=(KR, 9)).pack(side="right", padx=(0, 10))

    def _go(self, d: int) -> None:
        self.page = max(0, min(self.pages - 1, self.page + d))
        self._render()

    def _select(self, path: str) -> None:
        self.sel = None if self.sel == path else path
        self._render()

    def _set_fx(self, effect: str, power: int) -> None:
        if self.sel is not None:
            self.fx[self.sel] = (effect, power)
            self._render()

    def _add(self, path: str | None) -> None:
        o = self.owner
        if path is None or pack.room_left(self.char, self.motion, o.root_dir) <= 0:
            return
        if self._digest(path) in pack.used_pictures(self.char, o.root_dir):
            return  # 겹쳐 넣지 않는다
        try:
            pack.read_frames(path)  # 읽히는 그림인지만 본다
            clip = self.clip_for(path)
            moving = pack.is_moving(path)
            pack.add_file(self.char, self.motion, path, o.root_dir,
                          effect=None if moving else clip.effect, power=clip.power)
        except Exception:
            return
        self.sel = None
        o._changed()
        self._render()

    def close(self) -> None:
        if self.owner.picker is self:
            self.owner.picker = None
        self.owner.shelf.forget(PICK_PIC)
        try:
            self.top.destroy()
        except tk.TclError:
            pass


class Picker:
    """화면 전체 그림 위에서 네모를 끌어 고른다. Esc·우클릭이면 그만둔다."""

    def __init__(self, owner: PackImport, shot, done):
        from PIL import ImageEnhance, ImageTk

        self.done = done
        vx, vy, vw, vh = virtual_screen()
        self.k = shot.width / vw  # 실제 픽셀 / 논리 픽셀
        self.top = tk.Toplevel(owner.win)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.geometry(f"{vw}x{vh}+{vx}+{vy}")
        view = ImageEnhance.Brightness(shot.resize((vw, vh))).enhance(0.6)
        self.dim = ImageTk.PhotoImage(view, master=self.top)
        self.c = tk.Canvas(self.top, width=vw, height=vh, highlightthickness=0, cursor="crosshair")
        self.c.pack()
        self.c.create_image(0, 0, image=self.dim, anchor="nw")
        self.c.create_text(vw // 2, 30, text="이모티콘 둘레를 네모로 끌기 · Esc 그만두기",
                           fill="white", font=(KR, 14, "bold"))
        self.start = None
        self.c.bind("<ButtonPress-1>", self._down)
        self.c.bind("<B1-Motion>", self._move)
        self.c.bind("<ButtonRelease-1>", self._up)
        self.c.bind("<Button-3>", lambda e: self._finish(None))
        self.top.bind("<Escape>", lambda e: self._finish(None))
        self.top.focus_force()

    def _down(self, e) -> None:
        self.start = (e.x, e.y)

    def _move(self, e) -> None:
        if not self.start:
            return
        x0, y0 = self.start
        self.c.delete("sel")
        l, t, r, b = min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)
        self.c.create_rectangle(l, t, r, b, outline="#3fb950", width=2, tags="sel")

    def _up(self, e) -> None:
        if not self.start:
            return
        x0, y0 = self.start
        l, t, r, b = min(x0, e.x), min(y0, e.y), max(x0, e.x), max(y0, e.y)
        if r - l < 6 or b - t < 6:
            self.start = None
            self.c.delete("sel")
            return
        k = self.k
        self._finish((round(l * k), round(t * k), round(r * k), round(b * k)))

    def _finish(self, rect) -> None:
        self.top.destroy()
        self.done(rect)


class Preview:
    """따온 그림 미리 보기: 바탕 지우기·움직임 담기를 고르고 [넣기]."""

    def __init__(self, owner: PackImport, motion: str, frames, rect):
        self.owner, self.act, self.rect = owner, motion, rect
        self.char = owner.char
        self.raw = frames  # [(RGBA 또는 RGB, ms)] 바탕 지우기 전
        self.tol = 28 if rect else 0  # 화면에서 딴 것은 채팅방 바탕이 묻어 오므로 기본 '보통'
        self.motion = 0
        self.top = tk.Toplevel(owner.win)
        self.top.title(f"{self.char} · {motion} 그림 넣기")
        self.top.configure(bg=P.bg)
        self.top.resizable(False, False)
        self.top.transient(owner.win)
        self._gen = 0
        self._imgs: list = []
        self._build()

    def _build(self) -> None:
        for w in self.top.winfo_children():
            w.destroy()
        body = tk.Frame(self.top, bg=P.bg, padx=16, pady=12)
        body.pack()
        tk.Label(body, text=f"{self.char} · {self.act} · {pack.MOTION_LABELS[self.act]}", bg=P.bg, fg=P.title,
                 font=(KR, 11, "bold"), anchor="w").pack(fill="x")
        self.view = tk.Canvas(body, width=300, height=150, bg=P.bg, highlightthickness=0)
        self.view.pack(pady=(8, 8))
        self._row(body, "바탕 지우기", BGS, self.tol, self._set_tol)
        if self.rect is not None:
            self._row(body, "움직임", CAPTURES, self.motion, self._set_motion)
        self.info = tk.Label(body, text="", bg=P.bg, fg=P.faint, font=(KR, 9), anchor="w")
        self.info.pack(fill="x", pady=(4, 0))
        foot = tk.Frame(body, bg=P.bg)
        foot.pack(fill="x", pady=(10, 0))
        self.owner._button(foot, "넣기", self._save, primary=True).pack(side="right")
        self.owner._button(foot, "그만두기", self.top.destroy).pack(side="right", padx=(0, 6))
        self._show()

    def _row(self, parent, label, options, current, pick) -> None:
        row = tk.Frame(parent, bg=P.bg)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg=P.bg, fg=P.title, font=(KR, 10), width=9,
                 anchor="w").pack(side="left")
        box = tk.Frame(row, bg=P.line, padx=1, pady=1)
        box.pack(side="right")
        for i, (value, text) in enumerate(options):
            on = value == current
            b = tk.Label(box, text=text, bg=P.green if on else P.track,
                         fg=P.bg if on else P.sub, font=(KR, 9, "bold" if on else "normal"),
                         padx=10, pady=3, cursor="hand2")
            b.pack(side="left", padx=(0 if i == 0 else 1, 0))
            b.bind("<Button-1>", lambda e, v=value: pick(v))

    def _set_tol(self, v: int) -> None:
        self.tol = v
        self._build()

    def _set_motion(self, seconds: int) -> None:
        self.motion = seconds
        if seconds:
            self._record(seconds)
        else:
            self.raw = self.raw[:1]
            self._build()

    def _record(self, seconds: int) -> None:
        """같은 자리를 seconds 초 동안 찍어 움직임을 담는다(이 창들은 잠깐 숨긴다)."""
        self.top.withdraw()
        self.owner.win.withdraw()
        self.top.update()
        time.sleep(0.25)
        frames, end, last = [], time.time() + seconds, time.time()
        while time.time() < end:
            shot = grab_all().crop(self.rect)
            now = time.time()
            if frames:
                frames[-1] = (frames[-1][0], int((now - last) * 1000))
            frames.append((shot, GRAB_MS))
            last = now
            time.sleep(max(0.0, GRAB_MS / 1000 - (time.time() - now)))
        self.raw = pack.dedupe([(f.convert("RGBA"), ms) for f, ms in frames])
        self.owner.win.deiconify()
        self.top.deiconify()
        self._build()

    def _frames(self):
        return [(pack.remove_bg(f, self.tol), ms) for f, ms in self.raw]

    def _show(self) -> None:
        """큰 그림(바둑판 위) + 바 크기 그림(어두운·밝은 바탕)을 움직여 보여 준다."""
        from PIL import Image, ImageTk

        from skins.base import DARK, LIGHT

        frames = self._frames()
        big = pack.fit_frames(frames, 120, width=150)
        bar = pack.fit_frames(frames, BAR_H, width=BAR_H)
        board = Image.new("RGBA", (150, 120), (0, 0, 0, 0))
        for y in range(0, 120, 10):
            for x in range(0, 150, 10):
                c = (200, 200, 200, 255) if (x + y) // 10 % 2 else (240, 240, 240, 255)
                board.paste(c, (x, y, x + 10, y + 10))
        shown = []
        for (b, ms), (s, _) in zip(big, bar):
            pic = Image.new("RGBA", (300, 150), (0, 0, 0, 0))
            back = board.copy()
            back.alpha_composite(b, ((150 - b.width) // 2, 120 - b.height))
            pic.paste(back, (0, 15))
            for i, color in enumerate((DARK.bg, LIGHT.bg)):  # 바에 앉은 모습, 어둡게·밝게
                tile = Image.new("RGBA", (60, 48), color)
                tile.alpha_composite(s, ((60 - s.width) // 2, 48 - s.height - 2))
                pic.paste(tile, (200, 20 + i * 62))
            shown.append((ImageTk.PhotoImage(pic, master=self.top), ms))
        self._imgs = shown
        n = len(shown)
        self.info.configure(text=f"{n}장짜리 움직이는 그림" if n > 1 else "멈춘 그림")
        self._gen += 1
        self._tick(self._gen, 0)

    def _tick(self, gen: int, i: int) -> None:
        if gen != self._gen or not self.view.winfo_exists() or not self._imgs:
            return
        img, ms = self._imgs[i % len(self._imgs)]
        self.view.delete("all")
        self.view.create_image(0, 0, image=img, anchor="nw")
        if len(self._imgs) > 1:
            self.view.after(ms, lambda: self._tick(gen, i + 1))

    def _save(self) -> None:
        try:
            pack.save_clip(self.char, self.act, self._frames(), self.owner.root_dir)
        except ValueError:
            pass
        self.top.destroy()
        self.owner._changed()


if __name__ == "__main__":
    PackImport().win.mainloop()
