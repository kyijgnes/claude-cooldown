"""클로디 앱 아이콘(`res/drawable/ic_claudi.xml`)을 **데스크탑 위젯의 도트 표에서 그대로** 뽑는다.

    python android/art/make_claudi_icon.py

`windows/skins/slim.py` 의 HEAD·LEGS·ARM·EYES 를 그대로 읽어 벡터 path 로 옮기므로,
마스코트 모양을 고칠 때는 **slim.py 표만 고치고 이 스크립트를 다시 돌리면** 폰이 따라온다.
(손으로 xml 을 고치지 말 것 — 다음 실행에서 덮어써진다)

판 크기는 적응형 아이콘 규격인 108. 한가운데는 (54,54)이고, 원으로 잘리는 런처에서도
안 잘리도록 **지름 66 원 안**에 들어가게 칸 크기를 잡았다(아래 CELL 주석).
★ 눈은 흰 도형이 아니라 **evenOdd 로 뚫은 구멍**이다 — 그래야 단색(monochrome) 아이콘에서도
  얼굴이 남는다(흰색으로 칠하면 통째로 물들어 사라진다).
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pc", "windows"))
sys.path.insert(0, os.path.join(ROOT, "pc"))

from skins.slim import (  # noqa: E402
    ARM,
    EYES,
    HEAD,
    LAP_BASE,
    LAP_LID,
    LEGS,
    LEGS_RUN,
    LEGS_WIDE,
    MASCOT_COLOR,
    MASCOT_U,
    NAP_Z,
    TYPE_ARM,
    TYPE_SHIFT,
)

OUT = os.path.join(ROOT, "android", "app", "src", "main", "res", "drawable", "ic_claudi.xml")
OUT_KT = os.path.join(ROOT, "android", "app", "src", "main", "java", "com", "kyijgnes",
                      "cooldown", "wallpaper", "MascotSprite.kt")

# 칸 크기 — 팔 끝 칸의 바깥 모서리까지가 반지름 33(지름 66) 안에 들어야 한다.
#   팔은 가로 끝 칸(중심에서 5.5칸)이고 세로로는 한가운데 근처(1칸)라
#   sqrt((5.5*C)^2 + (1*C)^2) < 33  →  C < 5.9
CELL = 5.8
MID = 54.0
COLS = (-1, 9)          # 팔이 뻗는 바깥 칸 (가로 전체는 -1..9 = 11칸)
ROWS = len(HEAD) + len(LEGS)


def x(col: float) -> float:
    return MID + (col - 4.5) * CELL   # 가로 한가운데는 칸 4.5 (=-1..9 의 중간)


def y(row: float) -> float:
    return MID + (row - ROWS / 2) * CELL


def rect(col: float, row: float, span: int = 1) -> str:
    """칸 하나(또는 이어진 여러 칸)를 닫힌 사각형 subpath 로."""
    x0, y0 = x(col), y(row)
    x1, y1 = x(col + span), y(row + 1)
    return (f"M{x0:.2f},{y0:.2f} L{x1:.2f},{y0:.2f} "
            f"L{x1:.2f},{y1:.2f} L{x0:.2f},{y1:.2f} Z")


def runs(lines: tuple[str, ...], top: int) -> list[str]:
    """줄마다 이어진 칸을 한 덩이로 — path 가 짧아지고 경계에 실금이 안 생긴다."""
    out = []
    for r, line in enumerate(lines):
        col = 0
        while col < len(line):
            if line[col] != "#":
                col += 1
                continue
            n = 1
            while col + n < len(line) and line[col + n] == "#":
                n += 1
            out.append(rect(col, top + r, n))
            col += n
    return out




def main() -> None:
    parts: list[str] = []
    for col, row in ARM[0]:                       # 팔은 옆으로 내린 자세
        parts.append(rect(col, row))
        parts.append(rect(8 - col, row))          # 오른팔은 좌우 뒤집기
    parts += runs(HEAD, 0)
    parts += runs(LEGS, len(HEAD))
    holes = [rect(col, row) for col, row in EYES["idle"]]

    body = "\n            ".join(parts + holes)
    xml = XML_HEAD.format(cell=CELL, color=MASCOT_COLOR, body=body)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(xml)
    write_kotlin()
    print(f"만듦: {OUT}")
    print(f"만듦: {OUT_KT}")
    print(f"  칸 {CELL} · 가로 {11 * CELL:.1f} · 세로 {ROWS * CELL:.1f} (108 판, 안전 원 66)")


XML_HEAD = '''<?xml version="1.0" encoding="utf-8"?>
<!-- 클로디 — 데스크탑 위젯 슬림 바에 사는 도트 마스코트(`windows/skins/slim.py`).

     ★ 이 파일은 **`android/art/make_claudi_icon.py` 가 만든다. 손으로 고치지 말 것.**
       모양을 바꾸려면 slim.py 의 HEAD/LEGS/ARM/EYES 표를 고치고 스크립트를 다시 돌린다.

     몸통도 입도 없이 큰 머리에 짧은 팔 둘·다리 둘. 표정은 눈으로만 낸다.
     한가운데 (54,54), 칸 {cell}. 팔 끝까지 **지름 66 원 안**이라 원으로 잘리는 런처에서도
     안 잘린다. ★ 눈은 흰 도형이 아니라 **evenOdd 로 뚫은 구멍**이다 — 그래야 단색
     아이콘에서도 얼굴이 남는다(흰색으로 칠하면 통째로 물들어 사라진다). -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">

    <path
        android:fillColor="{color}"
        android:fillType="evenOdd"
        android:pathData="{body}" />
</vector>
'''


def kt_rows(lines) -> str:
    return ",\n        ".join('"%s"' % r for r in lines)


def kt_cells(cells) -> str:
    return ", ".join("%d, %d" % (c, r) for c, r in cells)


def kt_cellsf(cells) -> str:
    """px 로 적힌 자리를 **칸 단위**로 옮긴다 — 폰은 칸 크기가 화면마다 달라서
    px 를 그대로 쓰면 작은 화면에선 노트북만 커진다."""
    return ", ".join("%gf" % (v / MASCOT_U) for v in cells)


def write_kotlin() -> None:
    """배경화면 마스코트가 쓸 같은 표를 코틀린으로도 뽑는다 — PC·폰이 안 어긋나게."""
    eyes = "\n".join(
        '        "%s" to intArrayOf(%s),' % (k, kt_cells(v)) for k, v in EYES.items()
    )
    arms = "\n".join(
        "        %d to intArrayOf(%s)," % (k, kt_cells(v)) for k, v in sorted(ARM.items())
    )
    type_arm = "\n".join("        intArrayOf(%s)," % kt_cells(pose) for pose in TYPE_ARM)
    lid = kt_cellsf([v for point in LAP_LID for v in point])
    kt = KT_TEMPLATE.format(
        head=kt_rows(HEAD), legs=kt_rows(LEGS), legs_wide=kt_rows(LEGS_WIDE),
        legs_run=kt_rows(LEGS_RUN), nap_z=kt_rows(NAP_Z), arms=arms, eyes=eyes,
        type_arm=type_arm, lap_base=kt_cellsf(LAP_BASE), lap_lid=lid,
        type_shift="%gf" % (TYPE_SHIFT / MASCOT_U),
        last_head=len(HEAD) - 1, leg_row=len(HEAD), foot_row=len(HEAD) + 1,
    )
    with open(OUT_KT, "w", encoding="utf-8") as f:
        f.write(kt)


KT_TEMPLATE = '''package com.kyijgnes.cooldown.wallpaper

/**
 * 클로디 도트 그림표 — **`android/art/make_claudi_icon.py` 가 만든다. 손으로 고치지 말 것.**
 * 원본은 데스크탑 위젯 `windows/skins/slim.py` 의 표이고, 앱 아이콘(`ic_claudi.xml`)도
 * 같은 원본에서 나온다. 모양을 바꾸려면 slim.py 를 고치고 스크립트를 다시 돌린다.
 *
 * 좌표는 '몇 번째 칸'이다 — 가로 0..8 이 머리, 그 밖 -1/9 가 팔.
 * 세로 0..{last_head} 가 머리, {leg_row}·{foot_row} 이 다리와 발. 눈은 바탕색으로 파낸다.
 */
object MascotSprite {{

    val HEAD = arrayOf(
        {head},
    )

    val LEGS = arrayOf(
        {legs},
    )

    /** 기절했을 때 — 다리가 벌어져 주저앉는다. */
    val LEGS_WIDE = arrayOf(
        {legs_wide},
    )

    /** 달려올 때 — 다리가 모였다. 평소 다리(`LEGS`)와 번갈아 쓰면 발을 바꾸는 것으로 보인다. */
    val LEGS_RUN = arrayOf(
        {legs_run},
    )

    /** 팔 한 칸의 자리 — **왼팔 기준**, 오른팔은 `8 - col` 로 뒤집어 쓴다. -1 번쩍 / 0 옆 / 1 늘어뜨림 */
    val ARM = mapOf(
{arms}
    )

    /** 표정별 눈 칸 (col, row 가 번갈아 들어 있다). */
    val EYES = mapOf(
{eyes}
    )

    /**
     * 노트북을 두드리는 **길게 뻗은 팔** 두 자세 (col, row 가 번갈아). 번갈아 그리면
     * 손이 오르내린다. 기본 팔(`ARM`)은 한 칸뿐이라 노트북에 안 닿는다.
     */
    val TYPE_ARM = arrayOf(
{type_arm}
    )

    /**
     * 낮잠 z — ★ **3×3 으로 줄이지 말 것.** 가운데 칸이 정확히 한가운데라 대각선이
     * 안 보여 I(工)로 읽힌다. 4×4 라야 z 가 된다(데스크탑에서 실제로 겪고 고쳤다).
     */
    val NAP_Z = arrayOf(
        {nap_z},
    )

    // ── 노트북 (몸 한가운데 기준 **칸 단위**) ──
    // ★★ 이것만은 도트 격자를 안 쓴다 — 그 해상도로는 무슨 모양을 해도 판때기였다.
    //    **다각형 둘(왼쪽으로 기운 덮개 + 오른쪽으로 뻗는 얇은 받침)** 이면 바로 노트북이 된다.
    /** 받침(키보드) — 왼쪽 x, 윗 y, 오른쪽 x, 아랫 y */
    val LAP_BASE = floatArrayOf({lap_base})

    /** 덮개 — 위가 왼쪽으로 기운 평행사변형 (x, y 가 번갈아) */
    val LAP_LID = floatArrayOf({lap_lid})

    /** 노트북까지 한 그림이 되게 몸을 오른쪽으로 물리는 양 (칸) */
    const val TYPE_SHIFT = {type_shift}

    const val COLS = 9
    val ROWS = HEAD.size + LEGS.size
}}
'''


main()
