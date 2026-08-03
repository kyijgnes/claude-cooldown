package com.kyijgnes.cooldown.wallpaper

/**
 * 클로디 도트 그림표 — **`android/art/make_claudi_icon.py` 가 만든다. 손으로 고치지 말 것.**
 * 원본은 데스크탑 위젯 `windows/skins/slim.py` 의 표이고, 앱 아이콘(`ic_claudi.xml`)도
 * 같은 원본에서 나온다. 모양을 바꾸려면 slim.py 를 고치고 스크립트를 다시 돌린다.
 *
 * 좌표는 '몇 번째 칸'이다 — 가로 0..8 이 머리, 그 밖 -1/9 가 팔.
 * 세로 0..5 가 머리, 6·7 이 다리와 발. 눈은 바탕색으로 파낸다.
 */
object MascotSprite {

    val HEAD = arrayOf(
        "..#####..",
        ".#######.",
        "#########",
        "#########",
        "#########",
        ".#######.",
    )

    val LEGS = arrayOf(
        "..#...#..",
        ".##...##.",
    )

    /** 기절했을 때 — 다리가 벌어져 주저앉는다. */
    val LEGS_WIDE = arrayOf(
        ".#.....#.",
        "##.....##",
    )

    /** 달려올 때 — 다리가 모였다. 평소 다리(`LEGS`)와 번갈아 쓰면 발을 바꾸는 것으로 보인다. */
    val LEGS_RUN = arrayOf(
        "...#.#...",
        "..##.##..",
    )

    /** 팔 한 칸의 자리 — **왼팔 기준**, 오른팔은 `8 - col` 로 뒤집어 쓴다. -1 번쩍 / 0 옆 / 1 늘어뜨림 */
    val ARM = mapOf(
        -1 to intArrayOf(-1, 3),
        0 to intArrayOf(-1, 4),
        1 to intArrayOf(0, 5),
    )

    /** 표정별 눈 칸 (col, row 가 번갈아 들어 있다). */
    val EYES = mapOf(
        "idle" to intArrayOf(2, 2, 3, 2, 2, 3, 3, 3, 5, 2, 6, 2, 5, 3, 6, 3),
        "blink" to intArrayOf(2, 3, 3, 3, 5, 3, 6, 3),
        "grin" to intArrayOf(1, 3, 2, 3, 3, 3, 5, 3, 6, 3, 7, 3),
        "surprise" to intArrayOf(1, 2, 2, 2, 3, 2, 1, 3, 2, 3, 3, 3, 5, 2, 6, 2, 7, 2, 5, 3, 6, 3, 7, 3),
        "focus" to intArrayOf(2, 3, 3, 3, 3, 2, 5, 3, 6, 3, 5, 2),
        "side" to intArrayOf(1, 2, 2, 2, 1, 3, 2, 3),
        "faint" to intArrayOf(1, 2, 3, 2, 2, 3, 1, 4, 3, 4, 5, 2, 7, 2, 6, 3, 5, 4, 7, 4),
    )

    /**
     * 노트북을 두드리는 **길게 뻗은 팔** 두 자세 (col, row 가 번갈아). 번갈아 그리면
     * 손이 오르내린다. 기본 팔(`ARM`)은 한 칸뿐이라 노트북에 안 닿는다.
     */
    val TYPE_ARM = arrayOf(
        intArrayOf(-1, 4, -2, 5, -3, 6),
        intArrayOf(-1, 4, -2, 4, -3, 5),
    )

    /**
     * 낮잠 z — ★ **3×3 으로 줄이지 말 것.** 가운데 칸이 정확히 한가운데라 대각선이
     * 안 보여 I(工)로 읽힌다. 4×4 라야 z 가 된다(데스크탑에서 실제로 겪고 고쳤다).
     */
    val NAP_Z = arrayOf(
        "####",
        "..#.",
        ".#..",
        "####",
    )

    // ── 노트북 (몸 한가운데 기준 **칸 단위**) ──
    // ★★ 이것만은 도트 격자를 안 쓴다 — 그 해상도로는 무슨 모양을 해도 판때기였다.
    //    **다각형 둘(왼쪽으로 기운 덮개 + 오른쪽으로 뻗는 얇은 받침)** 이면 바로 노트북이 된다.
    /** 받침(키보드) — 왼쪽 x, 윗 y, 오른쪽 x, 아랫 y */
    val LAP_BASE = floatArrayOf(-12f, 3f, -4f, 4.5f)

    /** 덮개 — 위가 왼쪽으로 기운 평행사변형 (x, y 가 번갈아) */
    val LAP_LID = floatArrayOf(-11f, 3f, -6f, 3f, -7.5f, -2.5f, -12.5f, -2.5f)

    /** 노트북까지 한 그림이 되게 몸을 오른쪽으로 물리는 양 (칸) */
    const val TYPE_SHIFT = 4f

    const val COLS = 9
    val ROWS = HEAD.size + LEGS.size
}
