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
        "faint" to intArrayOf(1, 2, 3, 2, 2, 3, 1, 4, 3, 4, 5, 2, 7, 2, 6, 3, 5, 4, 7, 4),
    )

    const val COLS = 9
    val ROWS = HEAD.size + LEGS.size
}
