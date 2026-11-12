"""메인 화면 처음 자리(`cooldown_main.main_spot`) 단위 테스트. 화면·tk 없이 돈다."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WIN = os.path.join(os.path.dirname(HERE), "windows")
sys.path.insert(0, WIN)
sys.path.insert(0, os.path.dirname(WIN))

from cooldown_main import main_spot  # noqa: E402

W, H = 620, 560
WORK = (0, 0, 1920, 1040)  # 아래에 작업표시줄 40px


def inside(x, y, work=WORK):
    return x >= work[0] and y >= work[1] and x + W <= work[2] and y + H <= work[3]


def overlap(x, y, wid):
    return x < wid[0] + wid[2] and x + W > wid[0] and y < wid[1] + wid[3] and y + H > wid[1]


def test_widget_on_right_goes_left():
    wid = (1700, 100, 200, 120)
    x, y = main_spot(wid, WORK, (W, H))
    assert x + W <= wid[0] and inside(x, y) and not overlap(x, y, wid)


def test_widget_on_left_goes_right():
    wid = (40, 100, 200, 120)
    x, y = main_spot(wid, WORK, (W, H))
    assert x >= wid[0] + wid[2] and inside(x, y)


def test_widget_near_bottom_is_clamped_above_taskbar():
    wid = (1700, 980, 200, 50)
    x, y = main_spot(wid, WORK, (W, H))
    assert inside(x, y) and not overlap(x, y, wid)


def test_wide_bar_at_bottom_goes_above():
    wid = (600, 1000, 700, 36)
    x, y = main_spot(wid, WORK, (W, H))
    assert y + H <= wid[1] and inside(x, y)


def test_wide_bar_at_top_goes_below():
    wid = (600, 4, 700, 36)
    x, y = main_spot(wid, WORK, (W, H))
    assert y >= wid[1] + wid[3] and inside(x, y)


def test_taskbar_on_left_edge_work_area():
    work = (60, 0, 1920, 1080)  # 작업표시줄이 왼쪽
    wid = (80, 200, 200, 100)
    x, y = main_spot(wid, work, (W, H))
    assert inside(x, y, work) and not overlap(x, y, wid)


def test_second_monitor_with_negative_origin():
    work = (-1920, 0, 0, 1040)
    wid = (-300, 200, 250, 100)
    x, y = main_spot(wid, work, (W, H))
    assert inside(x, y, work) and not overlap(x, y, wid)


def test_taskbar_on_right_edge():
    work = (0, 0, 1860, 1080)
    wid = (1600, 300, 220, 100)
    x, y = main_spot(wid, work, (W, H))
    assert inside(x, y, work) and not overlap(x, y, wid)


def test_work_area_smaller_than_window_pins_top_left():
    work = (0, 0, 800, 500)
    wid = (300, 100, 200, 100)
    x, y = main_spot(wid, work, (W, H))
    assert y == 0 and x >= 0


def test_widget_in_middle_still_fits():
    wid = (900, 400, 220, 120)
    x, y = main_spot(wid, WORK, (W, H))
    assert inside(x, y) and not overlap(x, y, wid)
