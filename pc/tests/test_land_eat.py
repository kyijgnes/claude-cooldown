"""
라운드 9 (11-22 사용자 요청 다섯):
- 쳐다보기는 커서를 가까이 `WATCH_LOOK`(2초) 머물러야, 갸웃은 몸 위에 `HOVER_SEC`(4초) 가만히 두어야.
  그 전에는 하던 그림 그대로.
- 기절(흔들기 3단계)·헤롱은 넘어지지 않는다: 제자리에서 비틀댄 뒤 뛰어 돌아간다.
- 던지면 날아감 하나에 버둥(움직이는 그림에도 덧입힘). 부딪혀도 꽈당으로 안 바꾼다.
- 땅에 닿으면 헉헉 `PANT_SEC` 숨 고르고 뛰어 돌아간다. 꽈당은 화면 위쪽에서 떨어졌을 때만.
- 사용량 막대 위에 놓으면 먹기 그림(칸이 비었을 때만 냠냠).
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
from skins.buddy import (EAT_SEC, FAINT_SEC, HOVER_SEC, PANT_SEC, TICK_MS,  # noqa: E402
                         WATCH_LOOK, Buddy)

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)
BASE = ("서기", "걷기", "뛰기", "놀람", "끌림", "점프", "인사", "축하", "잠", "딴짓")


def _png(path, color, size=(20, 24)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(3, size[0] - 3):
        for y in range(4, size[1]):
            im.putpixel((x, y), color)
    im.save(path)


def _anim(path, durs):
    """장면마다 몸 높이가 다른 움직이는 그림."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frames = []
    for i in range(len(durs)):
        im = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
        for x in range(3, 17):
            for y in range(2 + i, 24):
                im.putpixel((x, y), ((37 * i) % 255, 120, 200, 255))
        frames.append(im)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=list(durs), loop=0)


def make_pack(root, motions):
    for i, m in enumerate(motions):
        _png(os.path.join(root, CHAR, m, "1.png"), ((29 * i) % 255, 120, 200, 255))
    return root


def _body(w=20, h=40):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for x in range(4, w - 4):
        for y in range(2, h):
            im.putpixel((x, y), (90, 160, 230, 255))
    return im


def _box(im):
    l, t, r, b = im.getbbox()
    return b - t, r - l


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


@pytest.fixture
def base(tmp_path):
    return make_pack(str(tmp_path), BASE)


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


def run(b, clock, seconds, each=None, tick=TICK_MS):
    for _ in range(int(round(seconds * 1000 / tick))):
        clock.t += tick / 1000
        b.step()
        if each:
            each()


def seen(b, clock, seconds):
    got = []
    run(b, clock, seconds, lambda: got.append(b.motion) if not got or got[-1] != b.motion else None)
    return got


def spot(b):
    return b.x, b.y1 + b.y - b.height / 2


def mid(b):
    return b.c.winfo_rootx() + b.x, b.c.winfo_rooty() + b.y1 + b.y - b.height / 2


def throw_right(b, clock, step, up=300):
    x, y = spot(b)
    assert b.catch(x, y)
    for i in range(6):
        clock.t += 0.02
        b.drag(x + step * i, y - up)
    b.put_down()


def drop_on_gauge(b):
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(150, y)
    b.put_down()


def yums(b):
    return [i for i in b.c.find_withtag("buddy_fx") if b.c.itemcget(i, "text") == "냠"]


# ------------------------------------------------------------------ 1. 쳐다보기는 몇 초 머문 뒤
def test_watch_times_and_labels():
    assert WATCH_LOOK >= 1.5 and HOVER_SEC >= WATCH_LOOK + 1.5       # 둘이 겹치지 않게 떨어져 있다
    assert "2초" in pack.MOTION_LABELS["쳐다보기"] and "4초" in pack.MOTION_LABELS["갸웃"]


def test_passing_cursor_does_not_look(tkroot, base):
    """커서가 잠깐(WATCH_LOOK 안) 가까이 왔다 가면 쳐다보기 없이 하던 그림 그대로."""
    b, clock = make(tkroot, base)
    cx, cy = mid(b)
    pos = {"p": (cx - 50, cy)}
    b.pointer = lambda: pos["p"]
    got = seen(b, clock, WATCH_LOOK - 0.4)
    assert got == ["서기"] and b.mode == ""
    pos["p"] = (cx + 600, cy)
    run(b, clock, 0.3)
    pos["p"] = (cx - 50, cy)
    got = seen(b, clock, WATCH_LOOK - 0.4)                        # 다시 와도 시간은 처음부터 센다
    assert "쳐다보기" not in got


def test_look_after_cursor_stays(tkroot, base):
    b, clock = make(tkroot, base)
    cx, cy = mid(b)
    b.pointer = lambda: (cx - 50, cy)
    run(b, clock, WATCH_LOOK - 0.2)
    assert b.motion == "서기"                                      # 아직 하던 그림
    run(b, clock, 0.4)
    assert b.motion == "쳐다보기" and b.mode == "봄"


def test_still_on_body_tilts_not_looks(tkroot, base):
    """몸 위에 가만히: 2초에 쳐다보기로 새지 않고 HOVER_SEC 에 갸웃 하나."""
    b, clock = make(tkroot, base)
    cx, cy = mid(b)
    b.pointer = lambda: (cx + 1, cy)
    got = seen(b, clock, HOVER_SEC - 0.3)
    assert got == ["서기"]
    got = seen(b, clock, 0.6)
    assert got[-1] == "갸웃" and "쳐다보기" not in got


def test_moving_on_body_looks_after_watch_time(tkroot, base):
    b, clock = make(tkroot, base)
    cx, cy = mid(b)
    t0 = clock.t

    def wander():                                               # 몸 위에서 0.45초마다 자리를 옮긴다 (문지르기는 아님)
        return cx + (-6, 0, 6)[int((clock.t - t0) / 0.45) % 3], cy
    b.pointer = wander
    got = seen(b, clock, WATCH_LOOK + 0.5)
    assert got[-1] == "쳐다보기" and "갸웃" not in got


# ------------------------------------------------------------------ 2. 기절은 안 넘어짐
@pytest.mark.parametrize("motion", ["헤롱", "기절"])
def test_dizzy_effect_never_lies_down(motion):
    im = _body()
    fx, power = pack.DEFAULT_FX[motion]
    assert fx == "헤롱"
    frames, loop_from = pack.bake([im], fx, power)
    tall, _ = _box(im)
    for f, _ in frames:
        assert _box(f)[0] >= tall * 0.9                             # 누운 꼴(키가 폭만큼 줄어듦)이 없다
    assert loop_from == 0
    assert sum(ms for _, ms in frames) / 1000 == pytest.approx(FAINT_SEC, abs=0.05)


def test_faint_stays_in_place_then_runs_home(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    b.catch(x, y)
    b.drag(x - 80, y)
    b._shake.energy, b._shake.t, b._shake.stage = 40.0, clock.t, 3
    b.drag(x - 80, y)
    assert b.motion == "기절"
    b.put_down()
    assert b.mode == "기절" and b.clip.effect == "헤롱"
    assert b.until - clock.t == pytest.approx(FAINT_SEC, abs=0.05)
    got = seen(b, clock, FAINT_SEC + 0.3)
    assert got[0] == "기절" and "꽈당" not in got and got[-1] == "뛰기"


# ------------------------------------------------------------------ 3. 버둥대며 날아감
def test_fly_default_is_flutter():
    assert pack.DEFAULT_FX["날아감"][0] == "버둥" and "버둥" in pack.EFFECTS
    frames, _ = pack.bake([_body(20, 30)], "버둥", 2)
    assert len(frames) == pack.fx_count("버둥", 2) >= 4
    assert len({f.tobytes() for f, _ in frames}) == len(frames)       # 장면마다 다르게 뒤튼다
    assert max(ms for _, ms in frames) <= 80                          # 빠르게 허우적댄다


def test_flutter_on_animated_fly(tmp_path):
    """움직이는 날아감 그림에도 버둥을 덧입힌다 (장면 길이는 그대로)."""
    root = make_pack(str(tmp_path), ("서기",))
    _anim(os.path.join(root, CHAR, "날아감", "a.webp"), [60, 60, 60, 60])
    clip = pack.pick_clip(CHAR, "날아감", root, stable=True)
    assert clip.effect == "버둥"
    raw = pack.read_frames(clip.files[0])
    got, _ = pack.clip_frames(clip)
    assert len(got) == len(raw) and [ms for _, ms in got] == [ms for _, ms in raw]
    assert got[0][0].size != raw[0][0].size                          # 뒤틀 판에 놓았다
    still = pack.Clip(clip.key + "*", clip.files, "없음", 2)
    assert pack.clip_frames(still)[0][0][0].size == raw[0][0].size   # 효과 「없음」이면 그대로


def test_wall_hit_keeps_fly_picture(tkroot, base, monkeypatch):
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 900.0, 3000.0))
    b, clock = make(tkroot, base)
    throw_right(b, clock, 90)                                        # 오른쪽 벽에 쾅
    flying = set()
    run(b, clock, 6.0, lambda: flying.add(b.motion) if b.mode == "던짐" else None)
    assert flying == {"날아감"}                                       # 부딪혀도 나는 동안 날아감 하나


# ------------------------------------------------------------------ 4. 헉헉
def test_pant_slot_in_pack():
    assert "헉헉" in pack.INTERACT and pack.limit("헉헉") == 1
    assert pack.MOTION_LABELS["헉헉"] and pack.DEFAULT_FX["헉헉"][0] == "숨쉬기"
    fb = pack.FALLBACK["헉헉"]
    assert fb[-1] == "서기" and "기절" not in fb and "꽈당" not in fb


def test_throw_lands_pants_then_runs_home(tkroot, base):
    b, clock = make(tkroot, base)
    throw_right(b, clock, 26)
    while b.mode == "던짐":
        run(b, clock, 0.04)
    assert b.mode == "헉헉" and b.motion == "헉헉" and b._carry is not None
    at = b._carry.at
    run(b, clock, PANT_SEC - 0.2)
    assert b.mode == "헉헉" and b._carry.at == pytest.approx(at)     # 그 자리에서 숨 고름
    b.react(*spot(b))
    b.tap_up()
    assert b.mode == "헉헉"                                          # 누르기는 받기만
    run(b, clock, 0.4)
    assert b.mode == "날기" and b.motion == "뛰기"                    # 뛰어 돌아온다
    run(b, clock, carry.RUN_MAX + 0.3)
    assert b.mode == "" and b._carry is None


def test_own_pant_picture_used(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE + ("헉헉",))
    b, clock = make(tkroot, root)
    throw_right(b, clock, 26)
    while b.mode == "던짐":
        run(b, clock, 0.04)
    assert b.motion == "헉헉" and os.sep + "헉헉" + os.sep in b.clip.files[0]


def test_perch_hop_off_does_not_pant(tkroot, base, monkeypatch):
    rect = (400, -500, 1200, 100)
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: (9, rect))
    monkeypatch.setattr(wins, "rect_of", lambda h: rect)
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 400)
    b.put_down()
    assert b.mode == "앉음"
    b._hop_off()
    got = seen(b, clock, 6.0)
    assert "헉헉" not in got                                         # 앉은 창에서 내려온 건 던진 게 아니다


def test_high_drop_still_bonks_not_pants(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x + 300, y - 2500)
    b.put_down()
    got = seen(b, clock, 6.0)
    assert got[:2] == ["허우적", "꽈당"] and "헉헉" not in got


# ------------------------------------------------------------------ 5. 먹기
def test_eat_slot_in_pack():
    assert "먹기" in pack.INTERACT and pack.limit("먹기") == 1
    assert pack.MOTION_LABELS["먹기"] == "사용량 막대 위에 놓음"
    assert pack.DEFAULT_FX["먹기"] == ("통통", 1)


def test_gauge_drop_plays_eat_picture(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE + ("먹기",))
    b, clock = make(tkroot, root)
    drop_on_gauge(b)
    assert b.mode == "냠냠" and b.motion == "먹기" and os.sep + "먹기" + os.sep in b.clip.files[0]
    got = seen(b, clock, EAT_SEC - 0.2)
    assert got == ["먹기"] and not yums(b)                           # 먹는 동안 먹기 하나, 글자 없음
    got = seen(b, clock, 0.4 + carry.RUN_MAX)
    assert "뛰기" in got and b.mode == ""                             # 다 먹고 뛰어 돌아간다


def test_gauge_drop_animated_eat_plays_as_is(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE)
    _anim(os.path.join(root, CHAR, "먹기", "a.webp"), [50, 50, 50, 50])
    b, clock = make(tkroot, root)
    drop_on_gauge(b)
    assert b.motion == "먹기" and len(b.frames) == 4                 # 움직이는 그림은 그대로


def test_gauge_drop_without_eat_chews_stand(tkroot, base):
    b, clock = make(tkroot, base)
    drop_on_gauge(b)
    assert b.mode == "냠냠" and b.motion == "냠냠" and b.clip is None  # 먹기 칸이 비었을 때만 냠냠
    run(b, clock, 0.2)
    assert yums(b)
