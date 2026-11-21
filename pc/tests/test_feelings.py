"""
감정 묶음 빼기 (11-21 사용자: 각종 감정이 언제 쓰이는지 모르겠다, 상호작용 그림으로) 와
1모션 원칙 (상호작용 하나가 끝날 때까지 그 그림 하나).

감정 폴더(슬픔·당황·부끄럼·신남·심심)가 팩에 남아 있어도 안 쓰이고 오류가 없어야 한다.
먹기는 11-22 에 상호작용(사용량 막대 위에 놓음)으로 되살렸다: 옛 먹기 폴더가 그대로 쓰인다.
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
from skins import carry, wins  # noqa: E402
from skins.base import set_palette  # noqa: E402
from skins.buddy import GIVEUP_SEC, TICK_MS, WATCH_LOOK, Buddy  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)
OLD_FEELINGS = ("슬픔", "당황", "부끄럼", "신남", "심심")
BASE = ("서기", "걷기", "뛰기", "놀람", "끌림", "점프", "인사", "축하", "잠", "딴짓")


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


def changes(b, clock, seconds):
    """그 동안 바뀐 그림 차례 (이어진 같은 것은 하나로)."""
    got = []
    run(b, clock, seconds, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    return got


def spot(b):
    return b.x, b.y1 + b.y - b.height / 2


def mid(b):
    return b.c.winfo_rootx() + b.x, b.c.winfo_rooty() + b.y1 - b.height / 2


def tap(b):
    b.react(*spot(b))
    b.tap_up()


@pytest.fixture
def base(tmp_path):
    return make_pack(str(tmp_path), BASE)


@pytest.fixture
def with_feelings(tmp_path):
    """옛 팩: 감정 폴더가 그대로 남아 있다."""
    return make_pack(str(tmp_path / "팩"), BASE + OLD_FEELINGS + ("먹기",))


# ------------------------------------------------------------------ 팩 약속
def test_feelings_gone_from_pack():
    for m in OLD_FEELINGS:
        assert m not in pack.MOTIONS and m not in pack.LIMITS and m not in pack.MOTION_LABELS
        assert m not in pack.FALLBACK and m not in pack.DEFAULT_FX
        assert all(m not in fb for fb in pack.FALLBACK.values())     # 빌리는 길에도 없다
    assert "감정" not in dict(pack.GROUPS)


def test_old_feeling_folders_are_ignored(with_feelings):
    root = with_feelings
    assert pack.characters(root) == [CHAR]
    for m in OLD_FEELINGS:
        assert os.path.isdir(os.path.join(root, CHAR, m))            # 지우지는 않는다
    for m in pack.MOTIONS:                                           # 어느 동작도 감정 그림을 고르지 않는다
        for _ in range(5):
            got = pack.pick_clip(CHAR, m, root)
            assert got is not None and not any(os.sep + f + os.sep in got.files[0] for f in OLD_FEELINGS)


def test_old_feeling_folders_round_trip(with_feelings, tmp_path):
    path = pack.export_pack(CHAR, str(tmp_path / "시험떡.캐릭터팩.zip"), with_feelings)
    dest = str(tmp_path / "받는 곳")
    os.makedirs(dest)
    assert pack.import_pack(path, dest) == CHAR                     # 모르는 동작 폴더는 건너뛴다
    assert not any(os.path.isdir(os.path.join(dest, CHAR, m)) for m in OLD_FEELINGS)


# ------------------------------------------------------------------ 감정으로 나오던 자리
def test_no_feeling_ever_plays(tkroot, with_feelings):
    """감정 그림이 있어도 어떤 일로도 안 나온다 (잡힘·한도·포기·자리비움·축하·오래 둠·커서·먹기)."""
    b, clock = make(tkroot, with_feelings)
    got = set()
    watch = lambda: got.add(b.motion)  # noqa: E731
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x - 30, y)
    run(b, clock, 1.0, watch)
    b.put_down()
    run(b, clock, 3.0, watch)
    b.set_mood("잠")
    run(b, clock, 3.0, watch)
    b.set_mood("여유")
    for _ in range(60):
        tap(b)
        run(b, clock, 0.12, watch)
    run(b, clock, GIVEUP_SEC + 2.0, watch)
    b.set_away(True)
    run(b, clock, 10.0, watch)
    b.set_away(False)
    b.celebrate()
    b._touched = clock.t - 5000
    run(b, clock, 40.0, watch)
    cx, cy = mid(b)
    b.pointer = lambda: (cx - 40, cy)
    run(b, clock, 10.0, watch)
    assert not got & set(OLD_FEELINGS)
    assert not hasattr(b, "note_usage")                               # 사용량 급등 당황도 없앴다


def test_old_eat_folder_is_used_again(tkroot, with_feelings, tmp_path):
    """옛 먹기 폴더는 되살린 먹기 칸으로 쓰인다 (막대 위에 놓으면 그 그림, 내보내기·넣기에도 실린다)."""
    assert "먹기" in pack.INTERACT and pack.own(CHAR, "먹기", with_feelings)
    b, clock = make(tkroot, with_feelings)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(150, y)
    b.put_down()
    assert b.mode == "냠냠" and b.motion == "먹기"
    path = pack.export_pack(CHAR, str(tmp_path / "먹기.캐릭터팩.zip"), with_feelings)
    dest = str(tmp_path / "먹기 받는 곳")
    os.makedirs(dest)
    assert pack.import_pack(path, dest) == CHAR
    assert os.path.isdir(os.path.join(dest, CHAR, "먹기"))


# ------------------------------------------------------------------ 1모션
def test_drag_start_shows_only_drag(tkroot, base):
    """누르는 순간 놀람·눌림이 비치지 않고, 끌기로 판정되면 곧바로 끌림."""
    b, clock = make(tkroot, base)
    got = []
    x, y = spot(b)
    b.react(x, y)                                                     # 앱 _press
    assert b.catch(x, y)
    run(b, clock, 0.2, lambda: got.append(b.motion))
    b.drag(x - 20, y)                                                  # 앱 _drag (DRAG_SLOP 넘음)
    run(b, clock, 1.0, lambda: got.append(b.motion))
    assert set(got[:5]) == {"서기"} and set(got[5:]) == {"끌림"}
    b.put_down()
    run(b, clock, 0.2)
    assert b._pending is None and b.motion != "놀람"                 # 놓은 뒤에도 받아 둔 누르기가 안 튀어나온다


def test_long_press_then_drag_shows_no_press_picture(tkroot, base):
    """앱이 꾹 누름을 알린 직후 끌기 시작하면 눌림도 안 비친다."""
    b, clock = make(tkroot, base)
    x, y = spot(b)
    b.react(x, y)
    b.catch(x, y)
    run(b, clock, 0.34)
    b.hold(x, y)
    got = []
    run(b, clock, 0.12, lambda: got.append(b.motion))
    b.drag(x - 20, y)
    run(b, clock, 0.4, lambda: got.append(b.motion))
    assert "눌림" not in got and "놀람" not in got and got[-1] == "끌림"


def test_long_press_is_press_only(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    b.react(x, y)
    run(b, clock, 0.34)
    b.hold(x, y)
    got = changes(b, clock, 1.5)
    b.let_go()
    b.tap_up()
    got += changes(b, clock, 0.5)
    assert got[:2] == ["서기", "눌림"] and "놀람" not in got         # 놓아도 눌림 그대로 튕긴다


def test_single_tap_is_one_surprise(tkroot, base):
    b, clock = make(tkroot, base)
    tap(b)
    got = [b.motion] + changes(b, clock, 3.0)
    assert got[:2] == ["놀람", "놀람"] and got.count("놀람") == 2 and got[2] != "놀람"   # 놀람 한 번 뒤 평소


def test_tap_surprises_at_once(tkroot, base):
    """떼자마자 놀람 (두 번 누르기를 기다리지 않는다, 11-21 사용자: 놀람이 느리다)."""
    b, clock = make(tkroot, base)
    tap(b)
    assert b.motion == "놀람" and b.fi == 0


def test_watch_waits_for_cursor_to_leave_after_tap(tkroot, base):
    """누른 손이 곧 커서라 놀람이 끝나자마자 쳐다보기가 섞이지 않는다. 한 번 떠났다 오면 본다."""
    b, clock = make(tkroot, base)
    cx, cy = mid(b)
    pos = {"p": (cx, cy)}
    b.pointer = lambda: pos["p"]
    tap(b)
    got = set()
    run(b, clock, 4.0, lambda: got.add(b.motion))
    assert "놀람" in got and not got & {"쳐다보기", "갸웃", "간지럼"}
    pos["p"] = (cx + 500, cy)
    run(b, clock, 0.2)
    pos["p"] = (cx + 40, cy)
    run(b, clock, WATCH_LOOK + 0.5)
    assert b.motion == "쳐다보기"


def test_watch_tilt_when_resting_on_body(tkroot, base):
    """몸 위에 가만히 머물면 갸웃 하나 (쳐다보기를 거치지 않는다)."""
    b, clock = make(tkroot, base)
    cx, cy = mid(b)
    b.pointer = lambda: (cx + 2, cy)
    assert changes(b, clock, 6.0) == ["서기", "갸웃"]


def test_rub_upgrades_look_once(tkroot, base):
    b, clock = make(tkroot, base)
    cx, cy = mid(b)
    pos = {"p": (cx - 50, cy)}
    b.pointer = lambda: pos["p"]
    run(b, clock, WATCH_LOOK + 0.4)
    assert b.motion == "쳐다보기"
    got = []
    for i in range(30):
        pos["p"] = (cx + (8 if i % 2 else -8), cy)
        got += changes(b, clock, 0.08)
    got += changes(b, clock, 2.4)                                      # 문지른 뒤 가만있어도 간지럼 그대로
    got = [m for i, m in enumerate(got) if i == 0 or got[i - 1] != m]
    assert got[-1] == "간지럼" and got.count("간지럼") == 1 and "갸웃" not in got


def test_mood_change_waits_for_interaction(tkroot, base):
    b, clock = make(tkroot, base)
    tap(b)
    run(b, clock, 0.5)
    assert b.motion == "놀람"
    b.set_mood("허둥")
    run(b, clock, 0.2)
    assert b.motion == "놀람"                                         # 기분이 바뀌어도 누르기 반응을 끊지 않는다


def test_perch_keeps_one_picture(tkroot, base, monkeypatch):
    b, clock = make(tkroot, base)
    monkeypatch.setattr(wins, "rect_of", lambda h: (0, 0, 800, 600))
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 400)
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: (1, (0, 0, 800, 600)))
    b.put_down()
    assert b.mode == "앉음"
    clip = b.clip
    assert changes(b, clock, 30.0) == ["앉기"] and b.clip == clip    # 빌린 그림(인사)도 바꿔 가며 틀지 않는다


def test_faint_wakes_without_surprise(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    b.catch(x, y)
    b.drag(x - 80, y)
    b._shake.energy, b._shake.t, b._shake.stage = 40.0, clock.t, 3
    b.drag(x - 80, y)
    assert b.motion == "기절"
    b.put_down()
    got = changes(b, clock, 8.0)
    assert got[0] == "기절" and "놀람" not in got
