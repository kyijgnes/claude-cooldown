"""
바 캐릭터 놀이 (11-20 넷째): 가속 복귀 · 안팎 같은 시간 셈 · 던지기(중력·튕김) · 창 제목 줄에 앉기 ·
사용량 막대 위 냠냠 · 두 번 누르기 점프 · 휠 빙글(많이 돌리면 기절) · 커서 쳐다보기 · 그림 여백 걷기.

그림은 코드로 만든다(공개 저장소). 창 찾기는 가짜로 바꿔 끼운다.
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
from skins.buddy import EAT_SEC, PERCH_SEC, SPIN_FAINT, TICK_MS, Buddy  # noqa: E402

CHAR = "시험떡"
W, H = 460, 48
BOX = (300, 0, 450, H)


def _png(path, color, size=(20, 24)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(3, size[0] - 3):
        for y in range(4, size[1]):
            im.putpixel((x, y), color)
    im.save(path)


@pytest.fixture(scope="module")
def tkroot():
    r = tk.Tk()
    r.withdraw()
    set_palette("dark")
    yield r
    r.destroy()


@pytest.fixture
def basic(tmp_path):
    root = str(tmp_path)
    for i, m in enumerate(("서기", "걷기", "뛰기", "놀람", "끌림", "점프", "인사", "축하")):
        _png(os.path.join(root, CHAR, m, "1.png"), (30 * i, 120, 200, 255))
    return root


@pytest.fixture(autouse=True)
def calm_world(monkeypatch):
    """단추는 눌린 채, 진짜 창에는 안 앉고, 화면은 넉넉히 (시험 캔버스는 화면 0,0 에 있다)."""
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


def spot(b):
    return b.x, b.y1 + b.y - b.height / 2


def drag_to(b, clock, pts, dt=0.03):
    for px, py in pts:
        clock.t += dt
        b.drag(px, py)


# ------------------------------------------------------------------ 돌아가기: 가속 · 안팎 같은 셈
def test_return_time_one_rule():
    rt = carry.return_time
    assert rt(0) == carry.RUN_MIN and rt(5000) == carry.RUN_MAX     # 아래·위 한도
    assert rt(100) < rt(200) < rt(400)                              # 멀수록 오래
    assert rt(200) == pytest.approx(1.4, abs=0.05)                  # 바 안 빠르기 (옛 1.4초) 기준
    f = carry.Flight((0.0, 0.0), (300.0, 400.0), 0.0, ease="in")    # 바 밖도 같은 셈
    assert f.dur == pytest.approx(rt(500))


def test_flight_ease_in_straight():
    f = carry.Flight((100.0, 900.0), (700.0, 300.0), 0.0, ease="in")
    pts = [f.at(i * 0.04) for i in range(int(f.dur / 0.04) + 2)]
    assert pts[-1] == (700.0, 300.0, True)
    for x, y, _ in pts:
        assert abs((x - 100) * (300 - 900) - (y - 900) * (700 - 100)) < 1e-6 * 600 * 600
    xs = [x for x, _, _ in pts]
    steps = [b - a for a, b in zip(xs, xs[1:]) if b - a > 0]
    assert steps == sorted(steps)                                   # 처음엔 천천히 나중엔 빠르게
    assert steps[-1] > 4 * steps[0]


def test_inside_run_accelerates_with_run_picture(tkroot, basic):
    b, clock = make(tkroot, basic)
    home = b.home_x
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x + 60, y)
    b.put_down()
    assert b.mode == "복귀"
    xs, motions = [], []
    n = 0
    while b.mode == "복귀" and n < 100:
        clock.t += TICK_MS / 1000
        b.step()
        xs.append(b.x)
        motions.append(b.motion)
        n += 1
    assert n * TICK_MS / 1000 <= carry.return_time(60) + 0.05
    assert b.mode == "" and b.x == pytest.approx(home)
    moving = [abs(b2 - a) for a, b2 in zip(xs, xs[1:]) if abs(b2 - a) > 1e-9]
    assert moving[0] < moving[-1] / 3                               # 가속
    assert "뛰기" in motions and "걷기" not in motions               # 뛰기 그림으로


def test_inside_and_outside_take_same_time(tkroot, basic):
    """같은 거리면 바 안에서 놓든 밖에서 놓든 같은 시간에 닿는다."""
    times = []
    for dy in (0, -600):
        b, clock = make(tkroot, basic)
        x, y = spot(b)
        assert b.catch(x, y)
        b.drag(x + 70, y + dy)
        if dy:   # 바 밖은 위로만 떨어진 거리라 옆 거리와 같게 맞춘다
            b._carry.move(*carry.screen_of(b.c, b.home_x + 70, b.y1))
        b.put_down()
        t0, n = clock.t, 0
        while b.mode in ("복귀", "날기") and n < 200:
            clock.t += TICK_MS / 1000
            b.step()
            n += 1
        times.append(clock.t - t0)
    assert times[0] == pytest.approx(times[1], abs=0.1)


# ------------------------------------------------------------------ 던지기
def test_throw_bounces_and_comes_home(tkroot, basic):
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    drag_to(b, clock, [(x - 200 + 60 * i, y - 300 - 60 * i) for i in range(6)], dt=0.02)  # 3000px/초 휙
    b.put_down()
    assert b.mode == "던짐" and b._toss["vx"] > 1100
    ys, bounces = [], []
    run(b, clock, 4.0, lambda: (ys.append(b._toss["y"]) if b._toss else None,
                                bounces.append(b._toss["bounces"]) if b._toss else None))
    floor = carry.screen_of(b.c, b.home_x, b.y1)[1]
    assert min(ys) < ys[0]                                          # 위로 날아갔다가
    assert max(ys) == pytest.approx(floor)                          # 바 높이 바닥에 닿고
    assert max(bounces) >= 1                                        # 튕겼다
    run(b, clock, 3.0 + carry.RUN_MAX)                                # 넉넉한 시험 화면이라 오래 난다
    assert b.mode == "" and b._carry is None and b.x == pytest.approx(b.home_x)


def test_throw_hits_wall(tkroot, basic, monkeypatch):
    monkeypatch.setattr(wins, "screen_box", lambda w: (-3000.0, -3000.0, 1200.0, 3000.0))
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    drag_to(b, clock, [(x + 80 * i, y - 300) for i in range(6)], dt=0.02)   # 오른쪽으로 세게
    b.put_down()
    assert b.mode == "던짐"
    seen = []
    run(b, clock, 2.0, lambda: seen.append(b._toss["vx"]) if b._toss else None)
    assert any(v < 0 for v in seen)                                 # 오른쪽 벽에 튕겨 돌아섰다


def test_slow_release_is_not_a_throw(tkroot, basic):
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    drag_to(b, clock, [(x - 10 * i, y - 300 - 5 * i) for i in range(10)])   # 초당 370px
    b.put_down()
    assert b.mode == "날기"


# ------------------------------------------------------------------ 창 제목 줄에 앉기
def test_perch_on_title_bar_then_fall_when_window_moves(tkroot, basic, monkeypatch):
    rect = [400, -500, 1200, 100]   # 시험 바는 화면 맨 위(0)에 있어 그보다 위 창
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: (77, tuple(rect)))
    monkeypatch.setattr(wins, "rect_of", lambda h: tuple(rect) if h == 77 else None)
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 400)
    b.put_down()
    assert b.mode == "앉음" and b.motion == "인사"
    assert b._carry.at[1] == pytest.approx(-499)                     # 창 위 테두리에 섰다
    run(b, clock, 5.0)
    assert b.mode == "앉음"
    rect[0] += 50                                                   # 창을 옮겼다
    run(b, clock, 0.3)
    assert b.mode == "던짐" and b._toss["vx"] == 0                   # 떨어진다
    run(b, clock, 6.0)
    assert b.mode == "" and b._carry is None


def test_perch_click_or_timeout_hops_down(tkroot, basic, monkeypatch):
    rect = (400, 300, 1200, 900)
    monkeypatch.setattr(wins, "title_bar_at", lambda sx, sy: (5, rect))
    monkeypatch.setattr(wins, "rect_of", lambda h: rect)
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 400)
    b.put_down()
    b._hop_off()                                                    # 누르면 폴짝 내려온다
    assert b.mode == "던짐" and b._toss["vy"] < 0
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(x, y - 400)
    b.put_down()
    run(b, clock, PERCH_SEC + 0.5)
    assert b.mode in ("던짐", "날기", "")


def test_title_bar_pick():
    wins_list = [(1, (100, 100, 900, 700)), (2, (0, 0, 1900, 1000))]
    assert wins.pick(wins_list, 500, 110)[0] == 1                    # 맨 앞 창 제목 줄
    assert wins.pick(wins_list, 500, 92)[0] == 1                     # 조금 위에서 놓아도
    assert wins.pick(wins_list, 500, 400) is None                    # 몸통에 놓으면 안 앉음 (뒤 창도 안 봄)
    assert wins.pick(wins_list, 50, 10)[0] == 2                      # 앞 창 밖이면 뒤 창
    assert wins.pick(wins_list, 104, 110) is None                    # 창 끝 모서리는 안 앉음


# ------------------------------------------------------------------ 냠냠
def test_drop_on_gauge_eats_then_runs_home(tkroot, basic):
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    assert b.catch(x, y)
    b.drag(150, y)                                                  # 캐릭터 칸 왼쪽 = 사용량 막대 위
    b.put_down()
    assert b.mode == "냠냠" and b.motion == "냠냠" and len(b.frames) > 4
    run(b, clock, 1.0)
    assert b.c.find_withtag("buddy_fx")                             # 「냠」 글자가 오른다
    assert b.c.itemcget(b.c.find_withtag("buddy_fx")[0], "text") == "냠"
    run(b, clock, EAT_SEC)
    assert not b.c.find_withtag("buddy_fx")
    assert b.motion in ("축하", "뛰기")
    run(b, clock, 1.3 + carry.RUN_MAX)
    assert b.mode == "" and b.x == pytest.approx(b.home_x)


# ------------------------------------------------------------------ 두 번 누르기 · 휠
def test_double_tap_jumps(tkroot, basic):
    b, clock = make(tkroot, basic)
    b.react(*spot(b))
    assert b.motion == "놀람"
    clock.t += 0.2
    b.react(*spot(b))
    assert b.motion == "점프" and b.vy < -10
    clock.t += 1.0
    b.react(*spot(b))
    assert b.motion == "놀람"                                        # 띄엄띄엄은 그냥 누르기


def test_wheel_spins_and_too_much_faints(tkroot, basic):
    b, clock = make(tkroot, basic)
    assert not b.c.find_withtag("x")
    b.wheel(b.x + 200, 5, 120)                                      # 캐릭터 밖: 아무 일 없음
    assert b.motion == "서기"
    b.wheel(*spot(b), 120)
    assert b.motion == "빙글" and len(b.frames) >= 10 and b.clip is None
    run(b, clock, 2.0)
    assert b.motion != "빙글"                                       # 다 돌고 평소로
    for _ in range(SPIN_FAINT):
        clock.t += 0.1
        b.wheel(*spot(b), -120)
    assert b.mode == "기절"


# ------------------------------------------------------------------ 쳐다보기
def test_looks_at_cursor_and_waves(tkroot, basic):
    b, clock = make(tkroot, basic)
    b.dir = 1
    b._refresh_frames()
    cx = b.c.winfo_rootx() + b.x
    cy = b.c.winfo_rooty() + b.y1 - b.height / 2
    b.pointer = lambda: (cx - 50, cy)
    b.until = clock.t + 100                                         # 다른 일은 안 하게
    run(b, clock, 0.3)
    assert b.dir == -1                                              # 왼쪽 커서를 본다
    run(b, clock, 3.0)
    assert b.motion == "인사"
    b.pointer = lambda: (cx + 500, cy)
    b.until = clock.t + 100
    b.dir = -1
    run(b, clock, 0.3)
    assert b.dir == -1                                              # 멀면 상관 안 함


# ------------------------------------------------------------------ 그림 여백 걷기
def test_content_box_ignores_far_specks_and_faint():
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    for x in range(80, 120):
        for y in range(90, 160):
            im.putpixel((x, y), (200, 100, 50, 255))
    im.putpixel((3, 3), (0, 0, 0, 255))                             # 멀리 떨어진 점 하나
    for x in range(0, 200):
        im.putpixel((x, 199), (0, 0, 0, 12))                        # 아주 옅은 그림자 줄
    assert im.getbbox() == (0, 3, 200, 200)                         # 옛 방식이면 판 전체
    assert pack.content_box([im]) == (80, 90, 120, 160)
    fitted = pack.fit_frames([(im, 100)], 40)
    assert fitted[0][0].size == (round(40 * 40 / 70), 40)            # 캐릭터가 높이를 꽉 채운다


def test_content_box_spans_all_frames():
    a = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    b = a.copy()
    for x in range(10, 40):
        for y in range(50, 100):
            a.putpixel((x, y), (255, 0, 0, 255))
            b.putpixel((x + 50, y - 40), (255, 0, 0, 255))
    assert pack.content_box([a, b]) == (10, 10, 90, 100)            # 움직이는 그림은 합친 테두리


def test_halo_on_dark_bar(tkroot, basic):
    im = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    im.putpixel((5, 5), (0, 0, 0, 255))
    out = pack.halo(im)
    assert out.getpixel((4, 5))[3] > 0 and out.getpixel((4, 5))[:3] == (255, 255, 255)
    assert out.getpixel((5, 5)) == (0, 0, 0, 255)
    b, _ = make(tkroot, basic)
    assert b._halo                                                   # 어두운 바면 켠다


def test_carry_is_bigger_while_held(tkroot, basic):
    b, clock = make(tkroot, basic)
    x, y = spot(b)
    small = b.frames[0][0].height()
    assert b.catch(x, y)
    b.drag(x, y - 400)
    b._draw()
    img = b._carry.canvas.itemcget(b._carry.canvas.find_withtag("buddy")[0], "image")
    assert tkroot.tk.call("image", "height", img) > small
