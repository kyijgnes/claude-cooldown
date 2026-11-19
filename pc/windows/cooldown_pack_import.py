"""
캐릭터팩 만들기 — 바 캐릭터를 만들고 동작마다 그림을 **한 장씩 골라** 넣는 창.

    python cooldown_pack_import.py          혼자 띄우기
    앱: 메인 화면 > 위젯 모양 > [캐릭터팩 만들기](이름 창부터) · [그림 고치기]
        (바에 세울 한 명은 「바 캐릭터」에서 고른다. 팩 파일 넣기·내보내기는 메인 화면 단추)

위: 캐릭터 이름 단추들 + [+ 캐릭터]. 고른 캐릭터의 동작 아홉 줄(서기·걷기·인사·…),
줄마다 넣은 그림 작은 그림 + [+]. [+] → 「파일에서 고르기」(그대로 복사, 움직임 유지) 또는
「화면에서 따오기」(네모로 골라 찍고, 미리 보기에서 바탕 지우기·움직임 담기).
아래: 그림이 보는 쪽(걷는 쪽에 맞춰 뒤집을 때 씀) · [이 캐릭터 빼기].

★ 한 번에 한 장이다. 동작마다 `MAX_PER_MOTION`(6)장까지. 묶음째 받거나 다른 프로그램의
  저장 파일을 뒤지는 기능은 넣지 않는다(사용자 지시 11-19: 필요한 일부만 골라 넣기).
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
from skins.base import KR, P  # noqa: E402

THUMB = 40
BGS = ((0, "끔"), (12, "약하게"), (28, "보통"), (48, "강하게"))
CAPTURES = ((0, "멈춘 그림"), (2, "2초 담기"), (4, "4초 담기"))
GRAB_MS = 70  # 움직임 담을 때 한 장 간격
BAR_H = 40  # 미리 보기의 바 그림 높이


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
        chars = pack.all_characters(root)
        self.char = chars[0] if chars else None
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
        tk.Label(self.body, text=f"캐릭터 {pack.MAX_CHARS}명까지 · 동작마다 {pack.MAX_PER_MOTION}장까지"
                 " · 빈 동작은 서기 그림 사용",
                 bg=P.bg, fg=P.faint, font=(KR, 9), anchor="w").pack(fill="x", pady=(0, 8))
        self._chips()
        if self.char is None:
            tk.Label(self.body, text="캐릭터 없음 · [+ 캐릭터]로 이름부터 정하기", bg=P.bg,
                     fg=P.sub, font=(KR, 10), anchor="w").pack(fill="x", pady=16)
        else:
            if not any(pack.clips(self.char, m, self.root_dir) for m in pack.MOTIONS):
                tk.Label(self.body, text=f"{self.char} · 서기 그림 한 장부터 넣기", bg=P.bg,
                         fg=P.green, font=(KR, 10, "bold"), anchor="w").pack(fill="x", pady=(0, 4))
            for motion in pack.MOTIONS:
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

    def _pick_char(self, name: str) -> None:
        self.char = name
        self._render()

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
        name = tk.Frame(row, bg=P.bg, width=200, height=THUMB + 4)
        name.pack(side="left")
        name.pack_propagate(False)
        tk.Label(name, text=motion, bg=P.bg, fg=P.title, font=(KR, 10, "bold"),
                 anchor="w").pack(side="left")
        tk.Label(name, text=pack.MOTION_LABELS[motion], bg=P.bg, fg=P.faint, font=(KR, 8),
                 anchor="w").pack(side="left", padx=(6, 0))
        files = pack.clips(self.char, motion, self.root_dir)
        for path in files:
            self._thumb(row, path)
        if len(files) < pack.MAX_PER_MOTION:
            add = tk.Label(row, text="+", bg=P.track, fg=P.sub, font=(KR, 14),
                           width=3, cursor="hand2")
            add.pack(side="left", padx=2, ipady=4)
            add.bind("<Button-1>", lambda e, m=motion, w=add: self._add_menu(m, w))

    def _thumb(self, row: tk.Frame, path: str) -> None:
        from PIL import ImageTk

        try:
            frames = pack.load_frames(path, THUMB - 4, width=THUMB - 4)
        except Exception:
            frames = []
        cell = tk.Frame(row, bg=P.track, width=THUMB, height=THUMB + 4)
        cell.pack(side="left", padx=2)
        cell.pack_propagate(False)
        if frames:
            img = ImageTk.PhotoImage(frames[0][0], master=self.win)
            self._thumbs.append(img)
            tk.Label(cell, image=img, bg=P.track).pack(expand=True)
        else:
            tk.Label(cell, text="?", bg=P.track, fg=P.red).pack(expand=True)
        x = tk.Label(cell, text="✕", bg=P.track, fg=P.faint, font=(KR, 7), cursor="hand2")
        x.place(relx=1.0, x=-1, y=0, anchor="ne")
        x.bind("<Button-1>", lambda e, p=path: self._delete(p))

    def _delete(self, path: str) -> None:
        pack.delete_clip(path, self.root_dir)
        self._changed()

    def _add_menu(self, motion: str, widget: tk.Widget) -> None:
        m = tk.Menu(self.win, tearoff=0)
        m.add_command(label="파일에서 고르기", command=lambda: self._from_file(motion))
        m.add_command(label="화면에서 따오기", command=lambda: self._from_screen(motion))
        m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def _changed(self) -> None:
        self._render()
        if self.on_change:
            self.on_change()

    def close(self) -> None:
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
