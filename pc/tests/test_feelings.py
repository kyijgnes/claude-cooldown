"""
감정 묶음 (11-20 넷째): 슬픔·당황·먹기·부끄럼·신남·심심 — 팩 약속(한도·빌리기)과 엔진에서 나오는 때.

그림은 코드로 만든다(공개 저장소).
"""

from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "windows"))

import tkinter as tk  # noqa: E402

from PIL import Image  # noqa: E402

import cooldown_pack as pack  # noqa: E402
from skins import buddy as buddy_mod  # noqa: E402
from skins import carry, wins  # noqa: E402
from skins.base import set_palette  # noqa: E402
from skins.buddy import FLUSTER_SEC, GIVEUP_SEC, SAD_SEC, TICK_MS, Buddy  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)
FEELINGS = ("슬픔", "당황", "먹기", "부끄럼", "신남", "심심")


def _png(path, color):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
    for x in range(3, 17):
        for y in range(4, 24):
            im.putpixel((x, y), color)
    im.save(path)


def make_pack(root, motions):
    for i, m in enumerate(motions):
        _png(os.path.join(root, CHAR, m, "1.png"), ((23 * i) % 255, 120, 200, 255))
    return root


@pytest.fixture(scope="module")
def tkroot():
    r = tk.Tk()
    r.withdraw()
    set_palette("dark")
    yield r
    r.destroy()


@pytest.fixture(autouse=True)
def calm_world(monkeypatch):
    monkeypatch.setattr(carry, "button_down", lambda: True)
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: None)
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 3000.0, 3000.0))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(tkroot, root):
    c = tk.Canvas(tkroot, width=W, height=H)
    clock = Clock()
    b = Buddy(c, BOX, CHAR, root=root)
    b.now = clock
    b._last = b._touched = clock.t
    b._play("서기", 3.0)
    return b, clock


def run(b, clock, seconds, each=None):
    for _ in range(int(round(seconds * 1000 / TICK_MS))):
        clock.t += TICK_MS / 1000
        b.step()
        if each:
            each()


def seen(b, clock, seconds):
    got = []
    run(b, clock, seconds, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    return got


def spot(b):
    return b.x, b.y1 + b.y - b.height / 2


BASE = ("서기", "걷기", "뛰기", "놀람", "끌림", "점프", "인사", "축하", "잠", "딴짓")


@pytest.fixture
def base(tmp_path):
    return make_pack(str(tmp_path), BASE)


# ------------------------------------------------------------------ 팩 약속
def test_feelings_group_limits_labels():
    assert dict(pack.GROUPS)["감정"] == FEELINGS
    assert pack.MOTIONS[-6:] == FEELINGS
    for m in FEELINGS:
        assert pack.limit(m) == 4
        assert pack.MOTION_LABELS[m] and "—" not in pack.MOTION_LABELS[m]
        assert m in pack.DEFAULT_FX
    assert pack.FALLBACK["슬픔"][:2] == ("잠", "포기")
    assert pack.FALLBACK["당황"][:2] == ("허둥", "놀람")
    assert pack.FALLBACK["먹기"][:2] == ("딴짓", "축하")
    assert pack.FALLBACK["부끄럼"][:2] == ("인사", "서기")
    assert pack.FALLBACK["신남"][:2] == ("축하", "점프")
    assert pack.FALLBACK["심심"][:2] == ("딴짓", "서기")


@pytest.mark.parametrize("motion,have,want", [
    ("슬픔", ("잠", "포기", "서기"), "잠"),
    ("슬픔", ("포기", "서기"), "포기"),
    ("당황", ("허둥", "놀람"), "허둥"),
    ("당황", ("놀람", "서기"), "놀람"),
    ("먹기", ("딴짓", "축하"), "딴짓"),
    ("먹기", ("축하", "서기"), "축하"),
    ("부끄럼", ("인사", "서기"), "인사"),
    ("부끄럼", ("서기",), "서기"),
    ("신남", ("축하", "점프"), "축하"),
    ("신남", ("점프", "서기"), "점프"),
    ("심심", ("딴짓", "서기"), "딴짓"),
    ("심심", ("서기",), "서기"),
])
def test_empty_feeling_borrows(tmp_path, motion, have, want):
    root = make_pack(str(tmp_path), have)
    got = pack.pick_clip(CHAR, motion, root)
    assert os.sep + want + os.sep in got.files[0]
    assert got.effect == pack.DEFAULT_FX[motion][0]
    assert not pack.own(CHAR, motion, root)


def test_feeling_pack_roundtrip(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    make_pack(a, ("서기",) + FEELINGS)
    f = pack.export_pack(CHAR, str(tmp_path / ("x" + pack.PACK_SUFFIX)), a)
    pack.import_pack(f, b)
    for m in FEELINGS:
        assert pack.own(CHAR, m, b)


# ------------------------------------------------------------------ 슬픔
def test_sad_after_giving_up(tkroot, base):
    b, clock = make(tkroot, base)
    for _ in range(80):
        b.react(*spot(b))
        run(b, clock, 0.12)
        if b.mode == "포기":
            break
    assert b.mode == "포기"
    run(b, clock, GIVEUP_SEC + 0.1)
    assert b.mode == "" and b.motion == "슬픔"


def test_sad_before_sleep_when_full(tkroot, base):
    b, clock = make(tkroot, base)
    b.set_mood("잠")
    assert b.motion == "슬픔"
    got = seen(b, clock, SAD_SEC + 3.5)
    assert "잠" in got                                              # 슬퍼한 뒤 잔다


def test_sad_after_hard_wall_hit(tkroot, base, monkeypatch):
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 900.0, 3000.0))
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    for i in range(6):
        clock.t += 0.02
        b.drag(x + 90 * i, y - 200)                                # 오른쪽 벽으로 세게
    b.put_down()
    assert b.mode == "던짐"
    got = seen(b, clock, 4.0)
    assert "슬픔" in got
    n = 0
    while b.mode != "" and n < 300:
        clock.t += TICK_MS / 1000
        b.step()
        n += 1
    assert b.mode == "" and b._carry is None


def test_sad_sometimes_when_away_long(tkroot, base, monkeypatch):
    b, clock = make(tkroot, base)
    b.set_away(True)
    monkeypatch.setattr(buddy_mod.random, "random", lambda: 0.0)
    run(b, clock, 4.0)
    assert b.motion == "자리비움" or b.motion != "슬픔"            # 처음엔 그냥 자리비움
    clock.t += buddy_mod.AWAY_SAD
    b._last = clock.t
    b.until = 0
    run(b, clock, 0.2)
    assert b.motion == "슬픔"


# ------------------------------------------------------------------ 당황
def test_fluster_when_caught(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 300)
    assert b.motion == "당황"
    run(b, clock, FLUSTER_SEC + 0.1)
    assert b.mode == "끌림" and b.motion == "끌림"


def test_fluster_on_usage_jump(tkroot, base):
    b, clock = make(tkroot, base)
    b.note_usage(20.0)
    clock.t += 120
    b.note_usage(24.0)
    assert b.motion != "당황"                                       # 조금 오르는 건 괜찮다
    clock.t += 120
    b.note_usage(31.0)
    assert b.motion == "당황"
    b, clock = make(tkroot, base)
    b.note_usage(20.0)
    clock.t += 3600
    b.note_usage(40.0)
    assert b.motion != "당황"                                       # 천천히 오른 건 아니다


# ------------------------------------------------------------------ 먹기
def test_gauge_eat_uses_eat_picture(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE + ("먹기",))
    b, clock = make(tkroot, root)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(120, y)
    b.put_down()
    assert b.mode == "냠냠" and b.motion == "먹기"


def test_snack_time_only_with_own_picture(tkroot, tmp_path, base, monkeypatch):
    monkeypatch.setattr(buddy_mod, "SNACK_P", 1.0)
    b, clock = make(tkroot, base)
    b.until = 0
    got = seen(b, clock, 6.0)
    assert "먹기" not in got                                        # 먹기 그림이 없으면 간식 시간도 없다
    root = make_pack(str(tmp_path / "eat"), BASE + ("먹기",))
    b, clock = make(tkroot, root)
    b.until = 0
    got = seen(b, clock, 0.5)
    assert "먹기" in got


# ------------------------------------------------------------------ 부끄럼
def test_shy_when_rubbed(tkroot, base):
    b, clock = make(tkroot, base)
    b.until = clock.t + 100
    cx = b.c.winfo_rootx() + b.x
    cy = b.c.winfo_rooty() + b.y1 - b.height / 2
    path = [cx - 8, cx + 8] * 4
    pos = {"p": (cx, cy)}
    b.pointer = lambda: pos["p"]
    for px in path:
        pos["p"] = (px, cy)
        run(b, clock, 0.08)
    assert b.motion == "부끄럼"


def test_hover_without_rub_is_not_shy_right_away(tkroot, base):
    b, clock = make(tkroot, base)
    b.until = clock.t + 100
    cx = b.c.winfo_rootx() + b.x
    cy = b.c.winfo_rooty() + b.y1 - b.height / 2
    b.pointer = lambda: (cx + 2, cy)
    run(b, clock, 1.0)
    assert b.motion != "부끄럼"


# ------------------------------------------------------------------ 신남
def test_excited_after_double_jump(tkroot, base):
    b, clock = make(tkroot, base)
    b.react(*spot(b))
    clock.t += 0.2
    b.react(*spot(b))
    assert b.motion == "점프"
    got = seen(b, clock, 1.5)
    assert "신남" in got


def test_excited_after_celebrate(tkroot, base):
    b, clock = make(tkroot, base)
    b.celebrate()
    assert b.motion == "축하"
    got = seen(b, clock, 3.2)
    assert "신남" in got


# ------------------------------------------------------------------ 심심
def test_bored_after_long_untouched(tkroot, base, monkeypatch):
    b, clock = make(tkroot, base)
    monkeypatch.setattr(buddy_mod.random, "random", lambda: 0.1)
    b.x = b.home_x
    clock.t += buddy_mod.BORED_LONG + 5
    b._last = clock.t
    b.until = 0
    run(b, clock, 0.1)
    assert b.motion == "심심"
    b2, clock2 = make(tkroot, base)
    b2.x = b2.home_x
    clock2.t += 100
    b2._last = clock2.t
    b2.until = 0
    run(b2, clock2, 0.1)
    assert b2.motion == "딴짓"                                      # 덜 오래면 그냥 딴짓
