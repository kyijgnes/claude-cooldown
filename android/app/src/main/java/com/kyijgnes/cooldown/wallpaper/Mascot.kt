package com.kyijgnes.cooldown.wallpaper

import android.graphics.Canvas
import android.graphics.Paint
import kotlin.math.abs
import kotlin.math.sin

/**
 * 배경화면에 사는 클로디 — 데스크탑 위젯(`windows/skins/slim.py`)의 도트 친구를 폰으로 옮겼다.
 * 그림표는 생성기가 만든 `MascotSprite`(같은 원본)를 쓰고, **여기는 움직임만** 맡는다.
 *
 * 상태(튀는 속도·표정 남은 프레임)를 들고 있으므로 **그리는 쪽마다 하나씩** 만든다
 * (배경화면 엔진 하나, 꾸미기 미리보기 하나). `WallpaperArt` 는 상태를 안 갖는다.
 *
 * ★ **터치는 배경화면이 직접 받는다** — 런처가 흘려 준 좌표가 클로디 위면 `poke()`.
 *   홈 화면에서 빈 곳을 누르면 반응하고, 아이콘·위젯 위를 누르면 그쪽이 먹으므로 안 온다.
 */
class Mascot {

    private var t = 0
    private var yoff = 0f      // 위아래 용수철 — 눌리면 튀어 오른다
    private var vy = 0f
    private var surprise = 0   // 콕 찔려 눈이 커진 프레임
    private var blink = 0
    private var nextBlink = 60

    /** 한 프레임. 배경화면·미리보기가 그리기 직전에 부른다. */
    fun step() {
        t++
        vy += -SPRING_K * yoff
        vy *= 1f - SPRING_DAMP
        yoff = (yoff + vy).coerceIn(-14f, 9f)
        if (surprise > 0) surprise--
        if (blink > 0) {
            blink--
        } else if (--nextBlink <= 0) {
            blink = 3
            nextBlink = 60 + (t % 90)   // 규칙적이지 않게 (난수 없이도 흩어진다)
        }
    }

    /** 콕 찔렸다 — 펄쩍 뛰고 눈이 동그래진다. */
    fun poke() {
        vy -= JUMP
        surprise = SURPRISE_FRAMES
    }

    /** 누른 자리가 클로디 위인가. `u` 는 칸 크기(px). */
    fun hits(cx: Float, cy: Float, u: Float, x: Float, y: Float): Boolean {
        val halfW = (MascotSprite.COLS / 2f + 2f) * u   // 팔까지
        val halfH = MascotSprite.ROWS / 2f * u
        return abs(x - cx) <= halfW + u && abs(y - (cy + yoff)) <= halfH + u
    }

    /**
     * 그린다. `cx`,`cy` 는 한가운데, `u` 는 칸 크기(px), `color` 는 몸 색,
     * `bg` 는 눈을 파낼 색(뒤가 사진이면 살짝 어두운 색을 넘긴다).
     */
    fun draw(c: Canvas, cx: Float, cy: Float, u: Float, color: Int, bg: Int) {
        val breathe = 1f + 0.045f * sin(t * 0.09f)
        val ux = u * breathe
        val uy = u * breathe
        val y = cy + yoff + sin(t * 0.12f) * u * 0.35f

        val speed = abs(vy) + abs(yoff)
        val expr = when {
            surprise > 0 -> "surprise"
            speed > 1.2f -> "grin"
            blink > 0 -> "blink"
            else -> "idle"
        }
        val arm = if (surprise > 0 || speed > 1.2f) -1 else 0

        val x0 = cx - MascotSprite.COLS / 2f * ux
        val y0 = y - MascotSprite.ROWS / 2f * uy
        val paint = Paint().apply { this.color = color }

        fun cell(col: Int, row: Int, span: Int, p: Paint) {
            val left = x0 + col * ux
            val top = y0 + row * uy
            c.drawRect(left, top, left + span * ux, top + uy, p)
        }

        // 팔 — 왼쪽 그대로, 오른쪽은 좌우로 뒤집어서
        val a = MascotSprite.ARM[arm] ?: MascotSprite.ARM[0]!!
        cell(a[0], a[1], 1, paint)
        cell(MascotSprite.COLS - 1 - a[0], a[1], 1, paint)

        // 머리·다리 — 이어진 칸은 한 덩이로
        paintRows(MascotSprite.HEAD, 0, ::cell, paint)
        paintRows(MascotSprite.LEGS, MascotSprite.HEAD.size, ::cell, paint)

        // 눈은 파낸다
        val hole = Paint().apply { this.color = bg }
        val eyes = MascotSprite.EYES[expr] ?: MascotSprite.EYES["idle"]!!
        var i = 0
        while (i < eyes.size) {
            cell(eyes[i], eyes[i + 1], 1, hole)
            i += 2
        }
    }

    private inline fun paintRows(
        rows: Array<String>, top: Int, cell: (Int, Int, Int, Paint) -> Unit, p: Paint,
    ) {
        for ((r, line) in rows.withIndex()) {
            var col = 0
            while (col < line.length) {
                if (line[col] != '#') {
                    col++
                    continue
                }
                var run = 1
                while (col + run < line.length && line[col + run] == '#') run++
                cell(col, top + r, run, p)
                col += run
            }
        }
    }

    private companion object {
        const val SPRING_K = 0.20f
        const val SPRING_DAMP = 0.14f
        const val JUMP = 4.5f
        const val SURPRISE_FRAMES = 12
    }
}
