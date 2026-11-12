"""
공룡 점프 — 클로디가 공룡으로 변신해 달리는 미니게임의 **규칙** (Tk 없음)
======================================================================
크롬이 인터넷이 끊기면 띄우는 그 공룡 게임을 그대로 옮겼다. 클로디를 **아주 오래 꾹 누르면**
(끝까지 납작해진 뒤로도 더) 공룡으로 변신하고, **창을 새로 띄우지 않고 그 자리가 판이 된다**
(PC 는 위젯 자체가, 폰은 앱 첫 화면의 게이지 자리가). 모자라면 판 크기만큼 늘어난다.

- **그림표(도트)·수치·규칙이 전부 여기 한 곳이다.** 그리는 쪽(PC `windows/cooldown_dino_view.py`,
  폰 `dino/DinoView.kt`)은 여기서 정한 것을 옮겨 그리기만 한다.
  ★ 폰은 이 파일을 **생성기**(`android/art/make_claudi_icon.py`)로 읽어 그림표와 수치를
  `DinoSpec.kt` 로 뽑는다. 수치·그림을 고쳤으면 그 스크립트를 다시 돌린다.
  규칙(아래 `Game`)은 `DinoGame.kt` 가 손으로 옮긴 것이라 **고치면 거기도 같이 고친다.**
- 수치는 크롬 원본(Runner·Trex·Obstacle config)에서 왔다. 판이 600×150 이고 한 프레임이
  1/60초인 것도 같다. 달라진 것만 적는다:
  · 판 너비는 바뀔 수 있다(`Game(width=)`, PC 위젯 판은 위젯 너비 · 최소 `MIN_W`).
  · 공룡이 조금 작다(38px, 크롬 47px). 머리가 **클로디 머리**(9칸, 모서리 깎음)라서.
  · 충돌은 상자가 아니라 **도트 칸끼리**(`hits`) 본다. 그림이 도트 표라 그대로 쓰면 된다.
  · 새는 높이가 셋(`BIRD_LIFTS`) — 낮은 것은 뛰어넘고, 가운데는 숙이거나 뛰고, 높은 것은 지나간다.
    폰은 가운데를 뺀 둘(`BIRD_LIFTS_TOUCH`, `touch=True`) — 크롬도 휴대폰에선 그렇다.
- 크롬에 없는 것(11-11): 낮↔밤이 1.5초에 걸쳐 서서히 바뀐다(`night_mix`) · 보호막(`SHIELD`, 땅에
  놓인 것은 달려서·뜬 것은 뛰어서 먹고 한 번 막아 준다) · 날개(`WING`, 먹으면 공룡 등에 날개가 붙고
  공중에서 뛰기를 **누르고 있는 동안 활공**한다. 모두 `GLIDE_FRAMES` 만큼 쓰면 사라진다, 11-12).
  ★ 폰(`DinoGame.kt`·`DinoBoard.kt`)은 아직 옛 2단 점프다(공중에서 손을 뗀 뒤 다시 탭). 활공은 PC 만 옮겼고,
    폰이 읽는 `WING_ON`·`WING_AT` 은 그래서 남겨 둔다.
- 그리는 쪽이 이펙트를 터뜨릴 수 있게 판에서 일어난 일을 `Game.events` 에 적는다(뛰기·착지·부딪힘…).
- 한 걸음(`step`)이 1/60초다. 그리는 쪽은 흐른 시간만큼 `step` 을 불러 맞춘다.
- 난수는 `random.Random(seed)` 하나만 쓴다. 같은 씨앗이면 같은 판이 나온다(확인용).

확인: `python pc/cooldown_dino.py` — 알아서 뛰는 공룡으로 판을 몇 번 돌려 점수를 본다.
"""

from __future__ import annotations

import random

# ---------------------------------------------------------------- 판
FPS = 60                # step 한 번 = 1/60초
W, H = 600, 150         # 판 크기 (px) — 크롬과 같다. 폰은 이 판을 화면 너비에 맞춰 늘린다
MIN_W = 460             # PC 위젯이 판이 될 때 이보다 좁으면 넓힌다 — 장애물이 보이고 닿기까지 틈이 모자라다
                        # (넓은 슬림 바 460 이 그대로 들어간다. 좁은 바·카드는 넓어진다)
GROUND = 138            # 발이 닿는 선 (y)
U = 2                   # 도트 한 칸 (px) — 위젯의 클로디와 같은 칸
DINO_X = 40             # 공룡 그림 왼쪽 끝 (꼬리 끝)

# ---------------------------------------------------------------- 달리기
SPEED0 = 6.0            # 처음 속도 (px/프레임)
SPEED_MAX = 13.0
ACCEL = 0.001           # 프레임마다 이만큼 빨라진다 (6 → 13 까지 약 2분)
CLEAR_FRAMES = 180      # 시작하고 이만큼(3초)은 장애물이 없다
SCORE_COEF = 0.025      # 달린 거리 × 이것 = 점수

# ---------------------------------------------------------------- 뛰기
# 누르고 있는 동안은 높이 오르고, 일찍 떼면 낮게 뛴다(크롬과 같다).
GRAVITY = 0.6
JUMP_V = 10.0           # 뛰어오르는 속도 (+ 지금 속도/10)
DROP_V = 5.0            # 떼면 오르는 속도를 여기까지 꺾는다
MIN_JUMP = 30           # 떼도 이만큼은 오른다 (px)
MAX_JUMP = 63           # 누르고 있어도 이 높이에서 오르기를 꺾는다
FAST_DROP = 3           # 뛰는 중에 ↓ 를 누르면 이 배로 빨리 떨어진다

# ---------------------------------------------------------------- 장애물
GAP_COEF = 0.6
GAP_MAX = 1.5           # 틈은 최소 틈의 1~1.5배 사이
MAX_GROUP = 3           # 선인장은 셋까지 붙어 나온다
MAX_DUP = 2             # 같은 종류는 셋 연달아 안 나온다
BIRD_LIFTS = (0, 22, 42)  # 새 그림 아래끝의 높이 — 뛰어넘기 · 숙이거나 뛰기 · 그냥 지나감
# 폰(손가락)에서는 가운데 높이를 뺀다 — 크롬도 휴대폰에선 새가 두 높이뿐이다(숙일 단추가 없어서).
BIRD_LIFTS_TOUCH = (0, 42)
BIRD_WOBBLE = 0.8       # 새는 제 속도가 조금씩 다르다 (±)

# ---------------------------------------------------------------- 그 밖
IDLE_EXIT = 20 * FPS    # 기다림·부딪힘·멈춤으로 이만큼(20초) 아무도 안 누르면 판을 접고 돌아간다
OVER_WAIT = 45          # 부딪힌 뒤 이만큼(0.75초)은 누르기를 안 받는다 (눌러 대다 바로 다시 시작되지 않게)
RUN_BEAT = 5            # 이 프레임마다 발을 바꾼다 (12fps)
FLAP_BEAT = 10          # 새가 날갯짓을 바꾸는 프레임
BLINK_EVERY = (120, 300)  # 기다리는 동안 눈 깜빡이는 사이 (프레임)
FLASH_EVERY = 100       # 이 점수마다 점수가 반짝인다
FLASH_FRAMES = 60
NIGHT_EVERY = 700       # 이 점수마다 밤이 온다
NIGHT_FRAMES = 720      # 밤은 12초
NIGHT_FADE = 90         # 낮↔밤이 이만큼(1.5초)에 걸쳐 서서히 바뀐다 (밤 12초 안에서 앞뒤로)

# ---------------------------------------------------------------- 활공 (11-12, 그 전에는 2단 점프)
# **날개 아이템**을 먹으면 공룡 등에 날개가 붙는다. 공중에서 내려오기 시작할 때 뛰기를 **누르고 있으면**
# 날개를 펴고 천천히 미끄러져 내려온다. 떼면 바로 끝나 보통대로 떨어지고, 다시 누르면 남은 만큼 또 편다.
# 날개 하나로 모두 `GLIDE_FRAMES` 만큼 활공하면 날개가 사라진다(여러 번에 나눠 써도 된다).
# 놓이는 자리·먹는 법은 보호막과 같다(`ITEM_LIFTS`).
GLIDE_FRAMES = 132      # 날개 하나의 활공 한도 (2.2초)
GLIDE_FALL = 0.7        # 활공 중 떨어지는 속도 (px/프레임 = 초당 42px. 그냥 떨어지면 내려앉을 때 초당 600px 안팎)
GLIDE_EASE = 0.3        # 떨어지던 속도를 프레임마다 이만큼씩 활공 속도로 당긴다 (떨어지다 펴면 0.2초쯤에 잡힌다)
GLIDE_LOW = 0.25        # 남은 활공이 이 아래면 그리는 쪽이 경고로 깜빡인다
CEILING = 4             # 공룡 그림 위끝이 이 y 보다 위로는 못 간다
FLAP_FRAMES = 4         # 날개를 달고 뛰어오르는 동안 이 프레임마다 팔락인다
GLIDE_BEAT = 9          # 활공 중 깃털 끝이 이 프레임마다 살짝 흔들린다

# ---------------------------------------------------------------- 아이템: 보호막 · 날개 (11-11)
# 장애물 사이 틈 한가운데에 가끔 놓인다. 땅에 놓인 것은 **그냥 달려서**(뛰면 지나친다),
# 공중에 뜬 것은 **뛰어서** 먹는다. 판에는 한 번에 하나만 놓이고, 이미 가진 것은 안 나온다.
#   보호막: 들고 있으면 한 번 부딪혀도 그 장애물이 부서지고 계속 달린다.
#   날개: 공중에서 누르고 있으면 활공 (모두 `GLIDE_FRAMES`).
ITEM_CHANCE = 0.14      # 장애물을 하나 놓을 때마다 이 확률로 그 뒤 틈에 아이템을 놓는다
ITEM_FROM = 100         # 이 점수부터 나온다
ITEM_LIFTS = (0, 44)    # 그림 아래끝이 땅에서 뜬 높이 — 달려서 먹기 · 뛰어서 먹기
SHIELD_GRACE = 40       # 막아 준 뒤 이만큼은 안 부딪힌다 (깜빡인다)
CLOUD_MAX = 6
CLOUD_GAP = (100, 400)
CLOUD_SKY = (32, 72)    # 구름이 뜨는 높이 (y) — 점수 글자(위 30px)와 안 겹치게
CLOUD_SPEED = 0.2       # 달리는 속도의 이만큼으로 흐른다

# ---------------------------------------------------------------- 그림 (도트 표)
# `#` 한 칸이 U px. 방향은 전부 **오른쪽을 본다**(달리는 쪽).
#
# 공룡 — **머리가 클로디 머리다**(9칸, 위 모서리 깎음). 크롬 공룡의 몸·꼬리·팔에 클로디
# 머리를 얹었다. 눈은 표에 없고 `DINO_EYE` 칸을 바탕색으로 파낸다(클로디 `EYES` 와 같은 결).
DINO_BODY = (
    "............#####..",
    "...........#######.",
    "..........#########",
    "..........#########",
    "..........#########",
    "..........#########",
    "..........######...",
    "#........#######...",
    "#.......#########..",
    "##.....#########.#.",
    "###...##########...",
    "###############....",
    ".#############.....",
    "..###########......",
    "...#########.......",
    "....#######........",
)
DINO_LEGS = {
    "stand": ("....###..###.......", "....##....##.......", "....##....##......."),
    "run1": ("....###..###.......", "....##.....##......", "...........##......"),
    "run2": ("....###..###.......", "....##....##.......", "....##............."),
}
# 숙이기 — 납작하게 엎드려 머리를 앞으로 내민다
DINO_DUCK = (
    "........................#####..",
    "#......................#######.",
    "##.......############.#########",
    ".###..#########################",
    "..#############################",
    "...##########################..",
    "....#######################....",
)
DINO_DUCK_LEGS = {
    "duck1": ("......###.....###..............", "......##......##..............."),
    "duck2": ("......###.....###..............", ".......##.....##..............."),
}
# 눈 — (칸, 줄). 서 있을 때와 숙였을 때 자리가 다르다.
DINO_EYE = {
    "open": ((12, 2), (13, 2), (12, 3), (13, 3)),
    "blink": ((12, 3), (13, 3)),
    "dead": ((11, 2), (13, 2), (12, 3), (11, 4), (13, 4)),   # X
}
DUCK_EYE = {
    "open": ((25, 2), (26, 2), (25, 3), (26, 3)),
    "blink": ((25, 3), (26, 3)),
    "dead": ((24, 1), (26, 1), (25, 2), (24, 3), (26, 3)),
}

# 선인장 — 작은 것(8×17)과 큰 것(12×25). 여럿이 붙어 나올 땐 하나 걸러 좌우를 뒤집는다.
CACTUS_S = (
    "...##...",
    "..####..",
    "..####..",
    "..####.#",
    "#.####.#",
    "#.####.#",
    "#.######",
    "#.#####.",
    "######..",
    ".#####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
    "..####..",
)
CACTUS_L = (
    ".....##.....",
    "....####....",
    "....####....",
    "....####....",
    "....####..#.",
    "....####.###",
    "##..####.###",
    "##..####.###",
    "##..####.###",
    "##..####.###",
    "##..####.###",
    "##..#######.",
    "##..######..",
    "##..####....",
    "########....",
    ".#######....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
    "....####....",
)
# 새 — 날개를 올렸다 내렸다. 두 장의 높이를 같게(10줄) 잡아 `BIRD_LIFTS` 가 그림 아래끝을 가리킨다.
# 눈은 `BIRD_EYE` 칸을 바탕색으로 파낸다.
BIRD = (
    (
        "......#...............",
        "......##..............",
        "......###.............",
        "......####............",
        "....#######...........",
        "..###########.........",
        "##############........",
        "..#################...",
        ".......#############..",
        "........#########.....",
    ),
    (
        "......................",
        "......................",
        "......................",
        "....#######...........",
        "..###########.........",
        "##############........",
        "..#################...",
        ".......#############..",
        "......#####...........",
        "......###.............",
    ),
)
BIRD_EYE = ((4, 6), (4, 5))   # 장마다 눈 자리 (날개를 내린 장은 몸이 한 줄 위다)

# 보호막 — 판 위에 놓인 것(먹을 것). 들고 있으면 공룡 둘레에 `SHIELD_RING` 이 돈다.
SHIELD = (
    "..#####..",
    ".#######.",
    "####.####",
    "###...###",
    "####.####",
    ".#######.",
    "..#####..",
    "...###...",
    "....#....",
)
SHIELD_RING_R = 26      # 들고 있을 때 공룡 둘레 고리의 반지름 (px)

# 날개 — 판 위에 놓인 것. 오른쪽 위가 어깨, 깃털이 왼쪽 아래로 빗살처럼 뻗는다(🪽).
# `+` 는 깃털 사이 결 — PC 는 그 칸을 조금 어둡게 덧칠하고(`WING_GROOVE`), 폰은 `WING` 한 색으로 그린다.
_WING_ITEM = (
    "..........#####.",
    ".......#########",
    ".....###########",
    "...#############",
    "..##############",
    ".######+###+####",
    "######+###+###+#",
    "#####+###+###+##",
    "####+###+###+##.",
    "##.+###+###+##..",
    "#..###.###.##...",
    "...##..##..#....",
    "...#...#........",
)


def _split(rows: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`+` 가 섞인 그림표를 (통짜 그림, 결만 남긴 그림) 둘로. 결 그림의 칸은 `#` 로 바꿔 `runs` 가 읽게."""
    solid = tuple(r.replace("+", "#") for r in rows)
    groove = tuple("".join("#" if ch == "+" else "." for ch in r) for r in rows)
    return solid, groove


WING, WING_GROOVE = _split(_WING_ITEM)
# 공룡 등에 붙는 날개 (폰 전용, 옛 2단 점프 그림) — PC 는 아래 `WING_BACK` 을 쓴다.
# [0] 내림(어깨가 오른쪽 위, 깃털이 아래로) · [1] 올림(위아래 뒤집어 깃털 끝이 위로).
_WING_SMALL = (
    ".......###.",
    ".....######",
    "...########",
    ".##########",
    "###########",
    "##.########",
    "#..#.######",
    "...#..#.##.",
    "......#....",
)
WING_ON = (_WING_SMALL, tuple(reversed(_WING_SMALL)))
# 공룡 그림 왼쪽 위에서 날개 그림 왼쪽 위까지 (px) — 그림마다. 어깨가 등(9칸째·7줄째) 언저리에 오게.
WING_AT = ((-6, 10), (0, -4))
ITEM_ART = {"shield": SHIELD, "wing": WING}

# 등 날개 (PC, 11-12) — 자세마다 한 장. `#` 깃털 · `+` 깃털 사이 결(조금 어둡게). 몸 **앞에** 그린다
# (우리 쪽 어깨에 붙은 날개라 어깨가 몸을 덮는다). 어느 장이든 어깨는 오른쪽 끝, 깃털 끝은 왼쪽(뒤).
#   fold 달릴 때 등에 접어 붙임 · up/down 뛰어오르며 퍼덕임 · glide1/2 펼친 채 깃털 끝만 흔들림
# 값: (통짜 그림, 결 그림, 공룡 그림 왼쪽 위에서 날개 그림 왼쪽 위까지 (dx, dy) px)
_WING_BACK = {
    "fold": ((
        "....#####.",
        "..########",
        ".###+###+#",
        "###+###+##",
        "##+###+##.",
        "#+.##+.#..",
    ), (-6, 12)),
    "up": ((
        "#..#..#....",
        "##.##.##...",
        "+##+##+##..",
        ".+##+##+##.",
        "..+########",
        "...########",
        "....#######",
        "......#####",
        "........###",
    ), (-2, 0)),
    "down": ((
        "........###",
        "......#####",
        "....#######",
        "...########",
        "..+########",
        ".+##+##+##.",
        "+##+##+##..",
        "##.##.##...",
        "#..#..#....",
    ), (-4, 14)),
    "glide1": ((
        "..........######..",
        "......###########.",
        "...###############",
        ".#####+###+###+###",
        "#####+###+###+###.",
        ".###+.##+.##+.##..",
        "..#+..#+..#+..#...",
    ), (-20, 8)),
    "glide2": ((
        "..........######..",
        "......###########.",
        "..################",
        "######+###+###+###",
        ".####+###+###+###.",
        "..##+.##+.##+.##..",
        "...+...+...+......",
    ), (-20, 8)),
}
WING_BACK = {k: (*_split(rows), at) for k, (rows, at) in _WING_BACK.items()}

CLOUD = (
    "......####......",
    "....########....",
    "..############..",
    "################",
)

# 공룡알 — **폰에서 게임으로 들어가는 문**(2026-09-26). 폰은 홈 화면에서 길게 누르기를 런처가
# 채 가므로, 클로디를 **마구 두드려 기절시키면 깨어날 때 알이 굴러 나오고**, 알을 톡톡 두드려
# 깨면(`EGG_CRACKS` 단계 뒤 한 번 더) 공룡이 나와 판이 된다. PC 는 '아주 오래 꾹' 그대로다.
# 칸: `o` 테두리 · `#` 껍데기 · `*` 코랄 점. 금은 테두리 색으로 칸을 덮어 그린다(지그재그로 번진다).
EGG = (
    "...ooo...",
    "..o###o..",
    "..o#*#o..",
    ".o#####o.",
    ".o*###*o.",
    "o#######o",
    "o###*###o",
    "o#*####*o",
    "o#######o",
    ".o##*##o.",
    "..ooooo..",
)
EGG_CRACKS = (
    ((1, 5), (2, 6), (3, 5)),               # 한 번 두드림 — 왼쪽에 금
    ((4, 6), (5, 5), (6, 6), (7, 5)),       # 두 번 — 금이 가로질러 번진다 (세 번째에 깨진다)
)
EGG_SPLIT = 6           # 깨질 때 이 줄 위(뚜껑)가 튀어 오르고 아래(밑동)는 남는다

# 닫기 — 판 왼쪽 위 구석. 글자 대신 도트 ✕ (누르는 자리는 `CLOSE_HIT` 로 넉넉히)
CLOSE = (
    "#...#",
    ".#.#.",
    "..#..",
    ".#.#.",
    "#...#",
)
CLOSE_AT = (10, 10)     # 그림 왼쪽 위 (px)
CLOSE_HIT = 30          # 판 왼쪽 위에서 이만큼(px) 안을 누르면 닫는다

# 다시 하기 — 둥근 화살표
RESTART = (
    "...#####...",
    "..#.....#..",
    ".#.......#.",
    "#.........#",
    "#..........",
    "#.......###",
    "#........##",
    ".#......#.#",
    "..#.....#..",
    "...#####...",
)


def runs(rows: tuple[str, ...], flip: bool = False) -> list[tuple[int, int, int, int]]:
    """도트 표를 **줄마다 이어진 칸 덩이**로 — `(x, y, w, h)` px. 그리기와 충돌이 같이 쓴다.

    한 칸씩 그리면 도형이 세 배다. 경계 식이 같으므로 그림은 한 픽셀도 안 달라진다."""
    out = []
    width = max(len(r) for r in rows)
    for r, line in enumerate(rows):
        line = line.ljust(width, ".")
        if flip:
            line = line[::-1]
        c = 0
        while c < width:
            if line[c] != "#":
                c += 1
                continue
            n = 1
            while c + n < width and line[c + n] == "#":
                n += 1
            out.append((c * U, r * U, n * U, U))
            c += n
    return out


def size(rows: tuple[str, ...]) -> tuple[int, int]:
    """그림 크기 (px)."""
    return max(len(r) for r in rows) * U, len(rows) * U


# 공룡 자세마다의 그림 — 충돌도 이걸로 본다
POSES = {
    "stand": DINO_BODY + DINO_LEGS["stand"],
    "run1": DINO_BODY + DINO_LEGS["run1"],
    "run2": DINO_BODY + DINO_LEGS["run2"],
    "duck1": DINO_DUCK + DINO_DUCK_LEGS["duck1"],
    "duck2": DINO_DUCK + DINO_DUCK_LEGS["duck2"],
}
_POSE_RUNS = {k: runs(v) for k, v in POSES.items()}

# 장애물 종류 — 크롬 Obstacle.types 를 옮긴 것
#   min_gap: 틈 계산의 바탕 · multi: 이 속도를 넘어야 여럿 붙어 나온다 · min_speed: 이 속도부터 나온다
KINDS = {
    "cactus": {"art": (CACTUS_S,), "min_gap": 120, "multi": 4.0, "min_speed": 0.0},
    "cactus_big": {"art": (CACTUS_L,), "min_gap": 120, "multi": 7.0, "min_speed": 0.0},
    "bird": {"art": BIRD, "min_gap": 150, "multi": 999.0, "min_speed": 8.5},
}


class Obstacle:
    """판 위의 장애물 하나(선인장 여럿이 붙은 무리도 하나다)."""

    def __init__(self, kind: str, x: float, count: int, lift: int, wobble: float, gap: int):
        self.kind = kind
        self.x = x
        self.count = count       # 붙어 나온 개수 (새는 늘 1)
        self.lift = lift         # 그림 아래끝이 땅에서 뜬 높이 (새만)
        self.wobble = wobble     # 제 속도 보탬 (새만)
        self.gap = gap           # 다음 장애물까지 띄울 틈
        self.frame = 0           # 새 날갯짓 (0/1)
        self.follow = False      # 다음 장애물을 이미 불렀나
        art = KINDS[kind]["art"][0]
        self.one_w, self.h = size(art)
        self.w = self.one_w * count

    @property
    def y(self) -> float:
        """그림 위끝."""
        return GROUND - self.lift - self.h

    def parts(self):
        """그릴 조각들 — `(그림 표, x, y, 뒤집기)`. 선인장 무리는 하나 걸러 뒤집는다."""
        arts = KINDS[self.kind]["art"]
        art = arts[self.frame % len(arts)]
        for i in range(self.count):
            yield art, self.x + i * self.one_w, self.y, i % 2 == 1

    def hit_runs(self):
        for art, x, y, flip in self.parts():
            for rx, ry, rw, rh in _art_runs(art, flip):
                yield x + rx, y + ry, rw, rh


_RUN_CACHE: dict = {}


def _art_runs(art, flip):
    key = (id(art), flip)
    if key not in _RUN_CACHE:
        _RUN_CACHE[key] = runs(art, flip)
    return _RUN_CACHE[key]


class Game:
    """한 판. 상태는 셋 — `ready`(기다림) · `run`(달리는 중) · `over`(부딪힘).

    누르기: `press_jump`/`release_jump`(스페이스·↑·클릭·탭), `press_duck`/`release_duck`(↓).
    `step()` 한 번이 1/60초. 그리는 쪽은 `pose`·`dino_y`·`obstacles`·`clouds`·`score`… 를 읽는다.

    `events` 는 판에서 방금 일어난 일 — 그리는 쪽이 걸음마다 읽고 비운다(이펙트용, 규칙은 안 읽는다):
    `("jump",)` · `("land", 떨어지던 속도)` · `("glide",)` 활공 시작 · `("wing_out", x, y)` 날개를 다 씀 ·
    `("item", 종류, x, y)` 먹음 · `("break", 장애물)` 보호막이 막음 · `("crash", 장애물, x, y)` · `("score", 점수)`.
    """

    def __init__(self, seed: int | None = None, best: int = 0, touch: bool = False,
                 width: int = W):
        self.rng = random.Random(seed)
        self.w = width                 # 판 너비 — 장애물·구름이 여기서 나온다(높이는 늘 H)
        self.best = int(best)
        self.lifts = BIRD_LIFTS_TOUCH if touch else BIRD_LIFTS
        self.t = 0
        self.events: list[tuple] = []
        self._reset()
        self.state = "ready"

    # -------------------------------------------------- 판 새로
    def _reset(self) -> None:
        self.state = "run"
        self.speed = SPEED0
        self.distance = 0.0
        self.run_t = 0             # 이 판에서 달린 프레임
        self.h = 0.0               # 공룡이 땅에서 뜬 높이 (px, 위가 +)
        self.vy = 0.0              # 오르는 속도 (위가 +)
        self.jumping = False
        self.reached_min = False
        self.fast_drop = False
        self.holding = False       # 뛰기를 누르고 있다
        self.down = False          # ↓ 를 누르고 있다
        self.ducking = False       # 숙이고 있다 (땅에서 ↓)
        self.obstacles: list[Obstacle] = []
        self.history: list[str] = []   # 최근에 나온 종류 (같은 것 셋 연달아 금지)
        self.over_t = 0
        self.flash = 0             # 점수 반짝임 남은 프레임
        self.flash_score = 0
        self.night = 0             # 밤 남은 프레임
        self.blink = 0
        self.next_blink = self.rng.randint(*BLINK_EVERY)
        self.new_best = False
        self.items: list[list] = []   # 판 위 아이템 — [x, 땅에서 뜬 높이, "shield"|"wing"]
        self.wing = False          # 날개를 가졌다 (공중에서 누르고 있으면 활공)
        self.glide = 0             # 남은 활공 (프레임) — 날개를 먹으면 `GLIDE_FRAMES`, 0 이 되면 날개가 사라진다
        self.gliding = False       # 지금 활공 중
        self.hit_xy = (0.0, 0.0)   # 마지막으로 부딪힌 자리 (판 좌표)
        self.shield = False        # 보호막을 들고 있다
        self.grace = 0             # 막아 준 뒤 안 부딪히는 남은 프레임
        self.broke = 0             # 막아 준 순간 반짝임 남은 프레임
        self.clouds: list[list[float]] = [[self.rng.uniform(self.w * 0.3, self.w), self.rng.uniform(*CLOUD_SKY)]]
        self.cloud_gap = self.rng.uniform(*CLOUD_GAP)
        # 땅의 자갈 — (x, 땅 아래 깊이, 폭). 흘러가다 왼쪽으로 빠지면 오른쪽에서 다시 나온다.
        self.pebbles = [[self.rng.uniform(0, self.w), self.rng.choice((2, 4, 6)), self.rng.choice((2, 2, 4))]
                        for _ in range(18)]

    # -------------------------------------------------- 누르기
    def press_jump(self) -> None:
        if self.state == "ready":        # 첫 누르기 — 뛰어오르며 출발
            self._reset()
            self._jump()
        elif self.state == "run":
            if not self.jumping and not self.ducking:
                self._jump()
            # 공중에서 누르면 — 날개가 있으면 `_step_jump` 가 내려오는 동안 활공으로 잡는다
        elif self.state == "over" and self.over_t >= OVER_WAIT:
            self._reset()                # 다시 하기 — 뛰지 않고 그냥 달린다(크롬과 같다)
        self.holding = True

    def release_jump(self) -> None:
        self.holding = False
        if self.jumping:
            self._end_jump()

    def press_duck(self) -> None:
        self.down = True
        if self.state != "run":
            return
        if self.jumping:              # 공중이면 빨리 떨어진다 (내려앉으면 그대로 숙인다)
            if not self.fast_drop:
                self.fast_drop = True
                self.vy = -1.0
        else:
            self.ducking = True

    def release_duck(self) -> None:
        self.down = False
        self.ducking = False
        self.fast_drop = False

    def _jump(self) -> None:
        self.jumping = True
        self.reached_min = False
        self.fast_drop = False
        self.vy = JUMP_V + self.speed / 10
        self._say("jump")

    def _say(self, *event) -> None:
        """그리는 쪽에 알릴 일 하나. 아무도 안 읽어도(확인용 판) 쌓이지 않게 끝 몇 개만 둔다."""
        self.events.append(event)
        if len(self.events) > 16:
            del self.events[:-16]

    def _end_jump(self) -> None:
        if self.reached_min and self.vy > DROP_V:
            self.vy = DROP_V

    # -------------------------------------------------- 한 걸음
    def step(self) -> None:
        self.t += 1
        if self.state == "ready":
            self._step_blink()
            return
        if self.state == "over":
            self.over_t += 1
            return
        self.run_t += 1
        if self.jumping:
            self._step_jump()
        else:
            self.gliding = False
        if self.speed < SPEED_MAX:
            self.speed = min(SPEED_MAX, self.speed + ACCEL)
        self.distance += self.speed
        self._step_obstacles()
        self._step_items()
        self._step_scenery()
        before = self.flash_score
        self.flash_score = self.score // FLASH_EVERY * FLASH_EVERY
        if self.flash_score > before and self.flash_score > 0:
            self.flash = FLASH_FRAMES
            self._say("score", self.flash_score)
            if self.flash_score % NIGHT_EVERY == 0:
                self.night = NIGHT_FRAMES
        elif self.flash > 0:
            self.flash -= 1
        if self.night > 0:
            self.night -= 1
        if self.broke > 0:
            self.broke -= 1
        if self.grace > 0:
            self.grace -= 1
            return
        hit = self._collides()
        if hit is not None:
            if self.shield:          # 보호막이 막는다 — 그 장애물은 부서지고 계속 달린다
                self.shield = False
                self.grace = SHIELD_GRACE
                self.broke = SHIELD_GRACE
                self.obstacles.remove(hit)
                self._say("break", hit)
            else:
                self._crash()
                self._say("crash", hit, *self.hit_xy)

    def _step_jump(self) -> None:
        # 활공 — 날개가 있고, 내려오는 중이고, 뛰기를 누르고 있는 동안. 떨어지는 속도를 `GLIDE_FALL` 로 당긴다.
        glide = (self.wing and self.holding and not self.fast_drop and self.vy <= 0 and self.glide > 0)
        if glide and not self.gliding:
            self._say("glide")
        self.gliding = glide
        if glide:
            self.vy += (-GLIDE_FALL - self.vy) * GLIDE_EASE
            self.h += self.vy
            self.glide -= 1
            if self.glide <= 0:    # 다 썼다 — 날개가 사라지고 여기서부터 그냥 떨어진다
                self.wing = False
                self.gliding = False
                dw, dh = size(POSES["stand"])
                self._say("wing_out", DINO_X + dw / 2 - 6, GROUND - self.h - dh / 2)
        else:
            self.h += self.vy * (FAST_DROP if self.fast_drop else 1)
            self.vy -= GRAVITY
        rise = self.h
        top = GROUND - self.h - size(POSES["stand"])[1]
        if top < CEILING:          # 판 위끝 — 머리를 박고 내려온다
            self.h = GROUND - CEILING - size(POSES["stand"])[1]
            self.vy = min(self.vy, 0.0)
        if rise > MIN_JUMP or self.fast_drop:
            self.reached_min = True
        if rise > MAX_JUMP or self.fast_drop:
            self._end_jump()
        elif not self.holding:
            self._end_jump()
        if self.h <= 0:           # 내려앉았다 — ↓ 를 누른 채면 그대로 숙인다
            self._say("land", -self.vy * (FAST_DROP if self.fast_drop else 1))
            self.h = 0.0
            self.vy = 0.0
            self.jumping = False
            self.fast_drop = False
            self.gliding = False
            self.ducking = self.down

    def _step_blink(self) -> None:
        if self.blink > 0:
            self.blink -= 1
            return
        self.next_blink -= 1
        if self.next_blink <= 0:
            self.blink = 8
            self.next_blink = self.rng.randint(*BLINK_EVERY)

    def _step_obstacles(self) -> None:
        for ob in self.obstacles:
            ob.x -= self.speed + ob.wobble
            if ob.kind == "bird" and self.t % FLAP_BEAT == 0:
                ob.frame ^= 1
        self.obstacles = [ob for ob in self.obstacles if ob.x + ob.w > 0]
        if self.run_t < CLEAR_FRAMES:
            return
        last = self.obstacles[-1] if self.obstacles else None
        if last is None:
            self._add_obstacle()
        elif not last.follow and last.x + last.w + last.gap < self.w:
            last.follow = True
            self._add_obstacle()

    def _add_obstacle(self) -> None:
        kinds = [k for k, v in KINDS.items() if self.speed >= v["min_speed"]]
        for _ in range(10):
            kind = self.rng.choice(kinds)
            recent = self.history[-MAX_DUP:]
            if len(recent) == MAX_DUP and all(k == kind for k in recent):
                continue
            break
        spec = KINDS[kind]
        count = self.rng.randint(1, MAX_GROUP) if self.speed > spec["multi"] else 1
        lift, wobble = 0, 0.0
        if kind == "bird":
            lift = self.rng.choice(self.lifts)
            wobble = self.rng.choice((-BIRD_WOBBLE, BIRD_WOBBLE))
        one_w, _ = size(spec["art"][0])
        min_gap = round(one_w * count * self.speed + spec["min_gap"] * GAP_COEF)
        gap = self.rng.randint(min_gap, round(min_gap * GAP_MAX))
        ob = Obstacle(kind, float(self.w), count, lift, wobble, gap)
        self.obstacles.append(ob)
        self.history = (self.history + [kind])[-MAX_DUP:]
        # 아이템 — 이 장애물 뒤 틈 한가운데. 판에 이미 있으면 안 놓고, 가진 것은 고르지 않는다.
        if not self.items and self.score >= ITEM_FROM and self.rng.random() < ITEM_CHANCE:
            kinds = [k for k in ITEM_ART if not (k == "shield" and self.shield)
                     and not (k == "wing" and self.wing)]
            if kinds:
                kind = self.rng.choice(kinds)
                iw, _ = size(ITEM_ART[kind])
                self.items.append([ob.x + ob.w + gap / 2 - iw / 2,
                                   float(self.rng.choice(ITEM_LIFTS)), kind])

    def _step_items(self) -> None:
        """아이템이 흘러가다 공룡에 닿으면 먹는다(칸끼리 겹치면)."""
        keep = []
        for it in self.items:
            iw, ih = size(ITEM_ART[it[2]])
            it[0] -= self.speed
            if it[0] + iw <= 0:
                continue
            x, y = it[0], GROUND - it[1] - ih
            if self._touches(x, y, iw, ih):
                if it[2] == "shield":
                    self.shield = True
                else:
                    self.wing = True
                    self.glide = GLIDE_FRAMES
                self._say("item", it[2], x + iw / 2, y + ih / 2)
                continue
            keep.append(it)
        self.items = keep

    def _touches(self, x: float, y: float, w: float, h: float) -> bool:
        dx0, dy0 = DINO_X, self.dino_y
        dw, dh = size(POSES[self.pose])
        if x >= dx0 + dw or x + w <= dx0 or y >= dy0 + dh or y + h <= dy0:
            return False
        return any(x < mx + mw and mx < x + w and y < my + mh and my < y + h
                   for mx, my, mw, mh in self.dino_runs())

    def _step_scenery(self) -> None:
        drift = self.speed * CLOUD_SPEED
        for c in self.clouds:
            c[0] -= drift
        cw, _ = size(CLOUD)
        self.clouds = [c for c in self.clouds if c[0] + cw > 0]
        last = self.clouds[-1] if self.clouds else None
        if len(self.clouds) < CLOUD_MAX and (last is None or last[0] < self.w - self.cloud_gap):
            self.clouds.append([float(self.w), self.rng.uniform(*CLOUD_SKY)])
            self.cloud_gap = self.rng.uniform(*CLOUD_GAP)
        for p in self.pebbles:
            p[0] -= self.speed
            if p[0] + p[2] < 0:
                p[0] += self.w + self.rng.uniform(0, 40)
                p[1] = self.rng.choice((2, 4, 6))
                p[2] = self.rng.choice((2, 2, 4))

    # -------------------------------------------------- 부딪힘
    def dino_runs(self):
        """지금 자세의 도트 덩이 — 판 좌표."""
        top = self.dino_y
        for rx, ry, rw, rh in _POSE_RUNS[self.pose]:
            yield DINO_X + rx, top + ry, rw, rh

    def _collides(self) -> Obstacle | None:
        """부딪힌 장애물 (없으면 None)."""
        dx0, dy0 = DINO_X, self.dino_y
        dw, dh = size(POSES[self.pose])
        mine = None
        for ob in self.obstacles:
            # 먼저 그림 테두리끼리 — 안 겹치면 칸을 볼 것도 없다
            if ob.x >= dx0 + dw or ob.x + ob.w <= dx0 or ob.y >= dy0 + dh or ob.y + ob.h <= dy0:
                continue
            if mine is None:
                mine = list(self.dino_runs())
            for ox, oy, ow, oh in ob.hit_runs():
                for mx, my, mw, mh in mine:
                    if ox < mx + mw and mx < ox + ow and oy < my + mh and my < oy + oh:
                        # 겹친 자리 한가운데 — 그리는 쪽이 여기서 파편을 터뜨린다
                        self.hit_xy = ((max(ox, mx) + min(ox + ow, mx + mw)) / 2,
                                       (max(oy, my) + min(oy + oh, my + mh)) / 2)
                        return ob
        return None

    def _crash(self) -> None:
        self.state = "over"
        self.over_t = 0
        self.jumping = False
        self.holding = False
        self.ducking = False
        self.fast_drop = False
        self.gliding = False
        if self.score > self.best:
            self.best = self.score
            self.new_best = True

    # -------------------------------------------------- 그리는 쪽이 읽는 것
    @property
    def score(self) -> int:
        return int(self.distance * SCORE_COEF)

    @property
    def pose(self) -> str:
        """지금 자세 — POSES 의 열쇠."""
        if self.state != "run" or self.jumping:
            return "stand"
        beat = (self.run_t // RUN_BEAT) % 2
        if self.ducking:
            return "duck2" if beat else "duck1"
        return "run2" if beat else "run1"

    @property
    def eye(self) -> str:
        if self.state == "over":
            return "dead"
        if self.state == "ready" and self.blink > 0:
            return "blink"
        return "open"

    @property
    def dino_y(self) -> float:
        """공룡 그림 위끝."""
        return GROUND - self.h - size(POSES[self.pose])[1]

    @property
    def night_mix(self) -> float:
        """밤이 든 정도 0~1 — 밤 들 때 `NIGHT_FADE` 동안 0→1, 끝날 때 1→0 으로 서서히."""
        if self.night <= 0:
            return 0.0
        into = NIGHT_FRAMES - self.night          # 밤이 시작되고 흐른 프레임
        return max(0.0, min(1.0, into / NIGHT_FADE, self.night / NIGHT_FADE))

    @property
    def wing_pose(self) -> str | None:
        """등 날개 그림(`WING_BACK` 의 열쇠) — 없으면 None.

        달릴 때는 접고(`fold`), 뛰어오르는 동안 퍼덕이고(`up`↔`down`), 활공 중엔 펼친 채 깃털 끝만
        흔들리고(`glide1`↔`glide2`), 활공 없이 떨어질 땐 치켜든다(`up`)."""
        if self.state != "run" or not self.wing or self.pose.startswith("duck"):
            return None
        if not self.jumping:
            return "fold"
        if self.gliding:
            return "glide2" if (self.t // GLIDE_BEAT) % 2 else "glide1"
        if self.vy > 0:
            return "down" if (self.t // FLAP_FRAMES) % 2 else "up"
        return "up"

    @property
    def glide_left(self) -> float:
        """남은 활공 0~1 (날개가 없으면 0)."""
        return self.glide / GLIDE_FRAMES if self.wing else 0.0

    @property
    def shield_blink(self) -> bool:
        """막아 준 뒤 안 부딪히는 동안 공룡이 깜빡인다 (보이면 참)."""
        return self.grace <= 0 or (self.grace // 4) % 2 == 0

    @property
    def shown_score(self) -> int:
        """화면에 적을 점수 — 100점을 넘길 때마다 그 숫자에서 반짝인다(크롬과 같다)."""
        return self.flash_score if self.flash > 0 else self.score

    @property
    def score_visible(self) -> bool:
        """반짝이는 동안 켜졌다 꺼졌다 한다 (1/4초마다)."""
        return self.flash <= 0 or (self.flash // 15) % 2 == 0


# ---------------------------------------------------------------- 확인
def _bot(g: Game) -> None:
    """알아서 뛰는 공룡 — 가까운 장애물을 보고 뛰거나 숙인다(규칙이 이길 만한지 보는 용도)."""
    ahead = [ob for ob in g.obstacles if ob.x + ob.w > DINO_X]
    if not ahead:
        g.release_duck()
        return
    ob = ahead[0]
    dist = ob.x - (DINO_X + size(POSES["stand"])[0])
    if ob.kind == "bird" and ob.lift >= BIRD_LIFTS[2]:
        g.release_duck()
        return
    if ob.kind == "bird" and ob.lift == BIRD_LIFTS[1]:
        if dist < g.speed * 6:
            g.press_duck()
        return
    g.release_duck()
    if 0 < dist < g.speed * 9 and not g.jumping:
        g.press_jump()
    elif g.jumping and g.h > MAX_JUMP - 8:
        g.release_jump()


def _selftest(rounds: int = 8) -> None:
    import statistics

    scores = []
    for seed in range(rounds):
        g = Game(seed=seed)
        g.press_jump()
        g.release_jump()
        while g.state == "run" and g.run_t < FPS * 60 * 4:
            _bot(g)
            g.step()
        scores.append(g.score)
        print(f"씨앗 {seed}: {g.score}점 · 속도 {g.speed:.1f} · {g.run_t / FPS:.0f}초"
              + (" · 끝까지 달림" if g.state == "run" else ""))
    print(f"평균 {statistics.mean(scores):.0f}점")


if __name__ == "__main__":
    _selftest()
