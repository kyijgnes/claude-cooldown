"""바 캐릭터·클로디 상호작용(11-20) 상태 전이 시험. 가짜 시계·가짜 입력으로 돈다.

연타 → 기절 → 깨어남 · 끌기 → 놓기 → 제자리 · 입력 없음 → 자리비움 → 반기기 · 사용량 네 단계.
그림 팩은 임시 폴더에 직접 만든다(사용자 팩은 안 읽는다). tk 창은 띄우지 않는다(withdraw).
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PC = os.path.dirname(HERE)
sys.path.insert(0, PC)
sys.path.insert(0, os.path.join(PC, "windows"))

import tkinter as tk  # noqa: E402

import pytest  # noqa: E402
from PIL import Image  # noqa: E402

import cooldown_pack as pack  # noqa: E402
from skins.base import AwayWatch, TapCount, char_mood, set_palette  # noqa: E402
from skins.buddy import FAINT_SEC, RETURN_SEC, TICK_MS, Buddy  # noqa: E402
from skins.claudi import Claudi  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)


def _png(path, color):
    im = Image.new("RGBA", (20, 24), (0, 0, 0, 0))
    for x in range(3, 17):
        for y in range(4, 24):
            im.putpixel((x, y), color)
    im.save(path)


@pytest.fixture(scope="module")
def packdir():
    d = tempfile.mkdtemp(prefix="cd_pack_")
    for i, motion in enumerate(("서기", "걷기", "놀람", "인사", "끌림", "자리비움")):
        os.makedirs(os.path.join(d, CHAR, motion))
        _png(os.path.join(d, CHAR, motion, "1.png"), (40 * i, 120, 200, 255))
    return d   # 「기절」은 일부러 비워 둔다 (FALLBACK 으로 빌리는지 본다)


@pytest.fixture(scope="module")
def tkroot():
    r = tk.Tk()
    r.withdraw()
    set_palette("dark")
    yield r
    r.destroy()


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_buddy(tkroot, packdir):
    c = tk.Canvas(tkroot, width=W, height=H)
    clock = Clock()
    b = Buddy(c, BOX, CHAR, root=packdir)
    b.now = clock
    b._last = clock.t
    b._touched = clock.t
    b._play("서기", 3.0)
    return b, clock


def run(b, clock, seconds):
    for _ in range(int(seconds * 1000 / TICK_MS)):
        clock.t += TICK_MS / 1000
        b.step()


def spot(b):
    """캐릭터 한가운데 (캔버스 좌표)."""
    return b.x, b.y1 + b.y - b.height / 2


# ------------------------------------------------------------------ 팩 동작 이름
def test_new_motion_names():
    for m in ("기절", "끌림", "자리비움"):
        assert m in pack.MOTIONS and pack.MOTION_LABELS[m] and m in pack.FALLBACK


def test_missing_faint_borrows(packdir):
    got = pack.pick(CHAR, "기절", packdir)
    assert got is not None and os.sep + "서기" + os.sep in got  # 잠·눌림도 없으니 서기를 빌린다


# ------------------------------------------------------------------ 사용량 단계
def test_mood_steps():
    assert char_mood(10, 20) == "여유"
    assert char_mood(60, 10) == "보통"
    assert char_mood(10, 85) == "허둥"
    assert char_mood(100, 40) == "잠"
    assert char_mood(None, None) == "여유"


def test_tapcount_window():
    t = TapCount(6, 2.0)
    assert not any(t.tap(s * 0.5) for s in range(6))   # 0.5초 간격 6번 = 2.5초에 걸침 → 아님
    t = TapCount(6, 2.0)
    hits = [t.tap(10 + s * 0.3) for s in range(6)]     # 1.5초 안에 6번 → 6번째에 연타
    assert hits == [False] * 5 + [True]


# ------------------------------------------------------------------ 바 캐릭터
def test_buddy_tap_faint_and_wake(tkroot, packdir):
    b, clock = make_buddy(tkroot, packdir)
    for _ in range(5):
        b.react(*spot(b))
        clock.t += 0.25
        b.step()
    assert b.mode == ""                     # 다섯 번까지는 놀람만
    b.react(*spot(b))
    assert b.mode == "기절" and b.motion == "기절"
    assert b.absorbed()                     # 논 것이다 (새로고침 아님)
    b.react(*spot(b))                       # 뻗어 있는 동안 눌러도 그대로
    assert b.mode == "기절"
    run(b, clock, FAINT_SEC + 0.2)
    assert b.mode == ""                     # 깨어났다


def test_buddy_slow_taps_never_faint(tkroot, packdir):
    b, clock = make_buddy(tkroot, packdir)
    for _ in range(12):
        b.react(*spot(b))
        run(b, clock, 0.6)
    assert b.mode == ""


def test_buddy_drag_and_return(tkroot, packdir):
    b, clock = make_buddy(tkroot, packdir)
    home = b.home_x
    x, y = spot(b)
    assert not b.catch(x - 120, y)           # 캐릭터 밖: 끌면 창이 움직인다
    assert b.catch(x, y)
    b.drag(x - 150, y)
    assert b.mode == "끌림" and b.motion == "끌림"
    assert abs(b.x - (home - 150)) < 1
    b.drag(-500, y + 400)                    # 위젯 밖으로 끌어도 안에 가둔다
    assert b.x == pytest.approx(b.w / 2)
    assert b.y1 + b.y <= H
    run(b, clock, 1.0)
    assert b.mode == "끌림"                  # 손에 잡혀 있는 동안은 그대로
    b.put_down()
    assert b.mode == "복귀"
    ticks = 0
    while b.mode == "복귀":                   # 제자리에 닿는 순간 평소로 돌아간다
        clock.t += TICK_MS / 1000
        b.step()
        ticks += 1
        assert ticks * TICK_MS / 1000 <= RETURN_SEC + 0.3
    assert b.x == pytest.approx(home)


def test_buddy_away_and_welcome(tkroot, packdir):
    b, clock = make_buddy(tkroot, packdir)
    idle = [0.0]
    watch = AwayWatch(lambda: idle[0], after=300)
    assert watch.poll() is None
    idle[0] = 299
    assert watch.poll() is None
    idle[0] = 301
    assert watch.poll() is True
    b.x = b.home_x - 60                       # 거닐던 중이었다
    b.set_away(True)
    run(b, clock, 10)
    assert b.mode == "자리비움" and b.motion == "자리비움" and b.x == pytest.approx(b.home_x)
    run(b, clock, 30)
    assert b.mode == "자리비움"                # 돌아올 때까지 그대로
    assert watch.poll() is None
    idle[0] = 0.5
    assert watch.poll() is False
    b.set_away(False)
    assert b.mode == "" and b.motion == "인사"


def test_buddy_mood_shows(tkroot, packdir):
    b, clock = make_buddy(tkroot, packdir)
    b.set_mood("잠")
    b.x = b.home_x + 30
    run(b, clock, 8)
    assert b.x == pytest.approx(b.home_x) and b.motion in ("잠", "서기")  # 잠 그림이 없으면 서기를 빌린다
    b.set_mood("허둥")
    walking = 0
    for _ in range(100):
        clock.t += TICK_MS / 1000
        b.step()
        walking += b.target is not None
    assert walking >= 90                      # 쉬지 않고 오간다


# ------------------------------------------------------------------ 클로디
def frames(cl, n):
    for _ in range(n):
        cl._animate(cl.c, cl._anim_gen)


def make_claudi(tkroot):
    c = tk.Canvas(tkroot, width=W, height=H)
    cl = Claudi(c, (10, 0, 450, H))
    cl.home(330)
    cl.start()
    return cl


def test_claudi_drag_and_return(tkroot):
    cl = make_claudi(tkroot)
    assert not cl.catch(cl.cx - 80, cl.cy)
    assert cl.catch(cl.cx, cl.cy)
    cl.drag(cl.cx - 200, cl.cy - 10)
    assert cl._grabbed and cl._bx == pytest.approx(-200)
    cl.drag(-999, cl.cy - 10)                   # 바 왼쪽 끝에 걸린다
    assert cl.cx + cl._bx == pytest.approx(5.5 * cl.u)
    frames(cl, 30)
    assert cl._grabbed                        # 잡혀 있는 동안 제자리로 안 돌아간다
    cl.put_down()
    assert not cl._grabbed
    assert cl._yoff == pytest.approx(-10)     # 끌어 올린 높이에서 떨어진다
    frames(cl, 80)
    assert cl._bx == 0.0 and abs(cl._yoff) < 4   # 제자리 (혼자 하는 폴짝은 봐준다)


def test_claudi_away_naps_until_back(tkroot):
    cl = make_claudi(tkroot)
    frames(cl, 5)
    cl.set_away(True)
    assert cl._act == "nap"
    frames(cl, 700)                           # 딴짓 낮잠(최대 400프레임)보다 길게
    assert cl._act == "nap"
    cl.set_away(False)
    assert cl._act == "" and cl._wave > 0     # 깨어나 손 흔들어 반긴다
    frames(cl, 100)
    assert cl._act != "nap"


def test_claudi_full_limit_naps(tkroot):
    cl = make_claudi(tkroot)
    cl.set_mood("잠")
    frames(cl, 250)                           # 하던 잔동작이 끝나면 곧 존다
    assert cl._act == "nap"
    cl.set_mood("여유")
    assert cl._act == ""
