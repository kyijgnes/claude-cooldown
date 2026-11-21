"""
v0.60 을 써 본 사용자 말 셋 (11-21):
「놀람은 누를 때마다 재생. 놀람이 원래 이모지 진행속도보다 많이 느리다. 드래그해서 날아갈 때는 기절 말고
다른 게 낫다. 흔들어서 기절이랑 부딪히거나 땅에 떨어져서 쓰러지는 거랑 분리.」

- 움직이는 그림 빠르기: 파일에 든 장면 길이와 실제로 넘어가는 시간을 재어 대조한다 (WebP·GIF).
  옛 `read_frames` 는 WebP 장면 길이를 한 장씩 밀려 읽고 첫 장을 100ms 로 두었다.
- 놀람: 누를 때마다 처음부터 한 번, 떼자마자.
- 던지기: 나는 동안 날아감만, 기절 그림은 안 나온다. (11-22: 부딪혀도 꽈당 없이 날아감, 닿으면 헉헉. `test_land_eat.py`)
- 높은 데서 떨어뜨리기: 떨어지는 동안 허우적, 닿으면 꽈당.

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
from skins.buddy import KAPOW_LIE, STREAK_GAP, TICK_MS, Buddy  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)
BASE = ("서기", "걷기", "뛰기", "놀람", "끌림", "점프", "인사", "축하", "잠", "딴짓", "기절")
# 서로 다른 장면 길이 (첫 장이 짧고 끝에 긴 멈춤): 밀려 읽으면 첫 장 100ms·끝 멈춤이 사라진다
DURS = [20, 20, 40, 40, 60, 60, 80, 300]


def _png(path, color):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
    for x in range(3, 17):
        for y in range(4, 24):
            im.putpixel((x, y), color)
    im.save(path)


def _anim(path, durs):
    """장면마다 몸 높이가 다른 움직이는 그림 (장면이 서로 달라 합쳐지지 않는다)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frames = []
    for i in range(len(durs)):
        im = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
        for x in range(3, 17):
            for y in range(2 + i, 24):
                im.putpixel((x, y), ((37 * i) % 255, 120, 200, 255))
        frames.append(im)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=list(durs), loop=0,
                   disposal=2 if path.endswith(".gif") else 0)


def make_pack(root, motions):
    for i, m in enumerate(motions):
        _png(os.path.join(root, CHAR, m, "1.png"), ((29 * i) % 255, 120, 200, 255))
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


def tap(b):
    b.react(*spot(b))
    b.tap_up()


# ------------------------------------------------------------------ 움직이는 그림 빠르기
@pytest.mark.parametrize("ext", ["webp", "gif"])
def test_read_frames_keeps_each_frame_duration(tmp_path, ext):
    p = str(tmp_path / f"a.{ext}")
    _anim(p, DURS)
    with Image.open(p) as im:  # 파일에 실제로 든 장면 길이 (Pillow 가 읽은 것과 상관없이 대조할 기준)
        assert im.n_frames == len(DURS)
    got = [ms for _, ms in pack.read_frames(p)]
    assert got == DURS                                   # 한 장씩 밀리지 않고, 첫 장이 100ms 가 아니다
    fitted = pack.fit_frames(pack.read_frames(p), 40)
    assert [ms for _, ms in fitted] == DURS              # 크기를 맞춰도 길이는 그대로 (최소 간격으로 안 늘어남)


def test_frame_ms_floor_and_zero():
    assert pack.frame_ms(None) == pack.FRAME_ZERO_MS == pack.frame_ms(0)
    assert pack.frame_ms(10) == 10 and pack.frame_ms(3) == pack.FRAME_MIN_MS
    assert pack.frame_ms(59.6) == 60


@pytest.mark.parametrize("ext", ["webp", "gif"])
@pytest.mark.parametrize("tick", [TICK_MS, 47, 16])
def test_playback_time_matches_file(tkroot, tmp_path, ext, tick):
    """바 캐릭터가 실제로 장면을 넘기는 시간 = 파일에 든 길이. 틱(앱은 40ms, 윈도우에선 46ms 쯤)이
    장면보다 길어도 사이 장면을 건너뛸 뿐 늦어지지 않는다."""
    root = make_pack(str(tmp_path), ("서기",))
    _anim(os.path.join(root, CHAR, "축하", f"a.{ext}"), DURS)
    b, clock = make(tkroot, root)
    b._play("축하", 60, busy=True, restart=True)
    assert [ms for _, ms in b.frames] == DURS
    wraps = []
    last = {"fi": b.fi}

    def look():
        if b.fi < last["fi"]:
            wraps.append(clock.t)
        last["fi"] = b.fi

    run(b, clock, 6.0, look, tick=tick)
    cycle = sum(DURS) / 1000
    laps = [y - x for x, y in zip(wraps, wraps[1:])]
    assert len(laps) >= 5
    assert sum(laps) / len(laps) == pytest.approx(cycle, abs=0.01)       # 바퀴당 평균이 파일 길이 그대로
    assert all(abs(lap - cycle) <= tick / 1000 + 1e-6 for lap in laps)  # 한 바퀴도 틱 하나 넘게 안 어긋난다


def test_long_last_frame_stays_last(tkroot, tmp_path):
    """끝에 긴 멈춤이 있는 그림: 멈춤은 마지막 장면에 (밀려 읽으면 첫 장으로 옮겨 갔다)."""
    root = make_pack(str(tmp_path), ("서기",))
    _anim(os.path.join(root, CHAR, "축하", "a.webp"), DURS)
    b, clock = make(tkroot, root)
    b._play("축하", 60, busy=True, restart=True)
    run(b, clock, sum(DURS[:-1]) / 1000 + 0.05, tick=10)
    assert b.fi == len(DURS) - 1
    run(b, clock, 0.2, tick=10)
    assert b.fi == len(DURS) - 1                          # 300ms 동안 마지막 장면에 머문다


# ------------------------------------------------------------------ 놀람: 누를 때마다 처음부터
def test_surprise_restarts_on_every_tap(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE)
    os.remove(os.path.join(root, CHAR, "놀람", "1.png"))
    _anim(os.path.join(root, CHAR, "놀람", "a.webp"), DURS)
    b, clock = make(tkroot, root)
    for gap in (0.5, 0.7, 0.45):                         # 띄엄띄엄 (두 번 누르기 아님)
        tap(b)
        assert b.motion == "놀람" and b.fi == 0          # 떼자마자, 처음 장면부터
        run(b, clock, 0.25)
        assert b.fi > 0
        run(b, clock, gap - 0.25)
    tap(b)
    run(b, clock, 0.25)
    tap(b)
    assert b.motion == "놀람" and b.fi == 0              # 놀람 도중에 또 눌러도 처음부터


def test_surprise_plays_once_then_rests_on_last_frame(tkroot, tmp_path):
    root = make_pack(str(tmp_path), BASE)
    os.remove(os.path.join(root, CHAR, "놀람", "1.png"))
    _anim(os.path.join(root, CHAR, "놀람", "a.webp"), [30] * 6)
    b, clock = make(tkroot, root)
    tap(b)
    fis = []
    run(b, clock, STREAK_GAP - 0.1, lambda: fis.append(b.fi), tick=10)
    assert b.motion == "놀람"
    assert fis == sorted(fis) and fis[-1] == 5          # 되감지 않고 한 번만, 끝 장면에서 멈춘다


def test_double_tap_still_hops_mash_stays_surprise(tkroot, base):
    b, clock = make(tkroot, base)
    tap(b)
    clock.t += 0.2
    tap(b)
    got = seen(b, clock, 0.6)
    assert got[0] == "놀람" and "깡충" in got             # 두 번 눌러 멈추면 깡충 (깡충 칸이 비면 점프를 빌린다)
    b2, clock2 = make(tkroot, base)
    got = []
    for _ in range(5):
        tap(b2)
        got.append(b2.motion)
        got += seen(b2, clock2, 0.15)
    assert "깡충" not in got and set(got) <= {"놀람", "짜증"}  # 빠른 연타는 놀람 (단계가 오르면 짜증)


# ------------------------------------------------------------------ 던지기 · 꽈당 · 기절 분리
def throw_right(b, clock, step, up=200):
    x, y = spot(b)
    assert b.catch(x, y)
    for i in range(6):
        clock.t += 0.02
        b.drag(x + step * i, y - up)
    b.put_down()


def test_fallback_keeps_faint_and_bonk_apart(tmp_path):
    root = make_pack(str(tmp_path), ("서기", "놀람", "기절"))
    bonk = pack.pick_clip(CHAR, "꽈당", root, stable=True)
    assert os.sep + "놀람" + os.sep in bonk.files[0] and bonk.effect == "쓰러짐"
    root2 = make_pack(str(tmp_path / "b"), ("서기", "꽈당"))
    faint = pack.pick_clip(CHAR, "기절", root2, stable=True)
    assert os.sep + "꽈당" + os.sep not in faint.files[0]
    assert "꽈당" not in pack.FALLBACK["기절"] and "기절" not in pack.FALLBACK["꽈당"]


def test_bonk_bakes_fall_lie_and_rise(tmp_path):
    root = make_pack(str(tmp_path), ("서기", "놀람"))
    clip = pack.pick_clip(CHAR, "꽈당", root, stable=True)
    frames, loop_from = pack.load_clip(clip, 40, 80)
    n = pack.rise_steps(clip)
    assert n == pack.DIZZY_UP and len(frames) == pack.fx_count("쓰러짐") + n
    assert 0 < loop_from < len(frames) - n               # 누운 장면에서 돈다, 일어나는 장면은 끝에
    first, last = frames[0][0], frames[-1][0]
    assert last.width == first.width                      # 다 일어나면 처음처럼 선다 (돌린 자국 1~2px 은 봐준다)
    assert all(abs(p - q) <= 2 for p, q in zip(last.getbbox(), first.getbbox()))
    lying = frames[loop_from][0].getbbox()
    assert (lying[2] - lying[0]) > (lying[3] - lying[1])  # 누워 있다 (가로가 길다)


def test_bonk_borrowing_animated_surprise_still_falls(tmp_path):
    root = make_pack(str(tmp_path), ("서기",))
    _anim(os.path.join(root, CHAR, "놀람", "a.webp"), DURS)
    clip = pack.pick_clip(CHAR, "꽈당", root, stable=True)
    frames, _ = pack.load_clip(clip, 40, 80)
    assert pack.rise_steps(clip) and len(frames) > len(DURS)   # 움직이는 놀람을 빌려도 첫 장을 쓰러뜨린다
    own = pack.Clip(os.path.join(root, CHAR, "꽈당", "x.webp"), [os.path.join(root, CHAR, "놀람", "a.webp")],
                    "쓰러짐", 2)
    frames, _ = pack.load_clip(own, 40, 80)
    assert len(frames) == len(DURS) and not pack.rise_steps(own)   # 제 것인 움직이는 꽈당은 그대로 튼다


def test_throw_flies_only_flying_never_faint(tkroot, base):
    """던져서 나는 동안은 날아감 하나. 기절 그림이 있어도 안 나온다. 땅에 닿으면 헉헉 뒤 뛰기 (11-22)."""
    b, clock = make(tkroot, base)
    throw_right(b, clock, 26, up=300)
    assert b.mode == "던짐" and b.motion == "날아감"
    got = seen(b, clock, 6.0)
    assert got[:3] == ["날아감", "헉헉", "뛰기"] and "기절" not in got and "꽈당" not in got


def test_hard_hit_keeps_flying_no_bonk(tkroot, base, monkeypatch):
    """벽에 세게 부딪혀도 꽈당으로 안 바꾸고 날아감 그대로, 닿으면 헉헉 (11-22)."""
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 900.0, 3000.0))
    b, clock = make(tkroot, base)
    throw_right(b, clock, 90)                            # 4500px/초: 오른쪽 벽에 쾅
    got = seen(b, clock, 6.0)
    assert got[:3] == ["날아감", "헉헉", "뛰기"] and "꽈당" not in got and "기절" not in got


def test_high_drop_bonk_shows_rise_frames_before_leaving(tkroot, base):
    """꽈당(화면 위쪽에서 떨어짐): 누워 있는 동안은 일어나는 장면을 안 틀고, 다 거친 뒤 떠난다."""
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x + 300, y - 2500)
    b.put_down()
    while b.mode == "던짐":
        run(b, clock, 0.04)
    assert b.mode == "꽈당"
    n = pack.rise_steps(b.clip)
    assert n and b._cut == n and b.fi < len(b.frames) - n
    run(b, clock, 0.5)
    total = len(b.frames)
    shown = set()
    while b.mode == "꽈당":
        run(b, clock, 0.02, tick=20)
        if b.motion == "꽈당":
            shown.add(b.fi)
    assert set(range(total - n, total)) <= shown          # 일어나는 장면을 다 거친 뒤 떠난다


def test_high_drop_flails_then_bonks(tkroot, base):
    b, clock = make(tkroot, base)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x + 300, y - 2500)                            # 화면 위쪽 높은 곳 (화면 -3000~3000)
    b.put_down()
    assert b.mode == "던짐" and b.motion == "허우적"
    got = seen(b, clock, 6.0)
    assert got[:3] == ["허우적", "꽈당", "뛰기"] and "기절" not in got   # 떨어지는 동안 허우적, 닿으면 꽈당
    assert b.mode == "" and b._carry is None


def test_shake_three_still_faints(tkroot, base):
    """기절은 흔들기 3단계 그대로 (꽈당이 안 끼어든다)."""
    b, clock = make(tkroot, base)
    x, y = spot(b)
    b.catch(x, y)
    b.drag(x - 80, y)
    b._shake.energy, b._shake.t, b._shake.stage = 40.0, clock.t, 3
    b.drag(x - 80, y)
    assert b.motion == "기절"
    b.put_down()
    got = seen(b, clock, 6.0)
    assert got[0] == "기절" and "꽈당" not in got and "날아감" not in got
