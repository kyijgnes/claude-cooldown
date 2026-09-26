package com.kyijgnes.cooldown

import android.content.Context
import android.graphics.Canvas
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import com.kyijgnes.cooldown.wallpaper.Mascot

/**
 * 앱 첫 화면 제목 옆에 사는 클로디 — 배경화면·꾸미기와 같은 `Mascot` 이다(노는 규칙이 같다).
 *
 * 공룡 점프로 들어가는 길은 배경화면과 같다 — **마구 두드려 기절시키면 알이 굴러 나오고,
 *   톡톡 깨면** 아래 게이지 자리가 판이 된다(`mascot.onHatch` 를 화면이 걸어 둔다).
 *   (처음엔 '아주 오래 꾹' 이었다가 2026-09-26 에 알로 바꿨다. 홈 화면에서 앱을 안 열고 하려고)
 * - 30fps 로 굴린다(`Mascot` 의 프레임 수가 30fps 기준이다). 화면이 안 보이면 멈춘다(`pause`).
 * - 칸 크기는 3dp — 뷰 아래쪽에 앉히고 위는 뛰어오를 자리로 비워 둔다.
 */
class ClaudiView(ctx: Context, attrs: AttributeSet? = null) : View(ctx, attrs) {

    val mascot = Mascot()
    private val pal = Palette(ctx)
    private val u = 3f * ctx.resources.displayMetrics.density
    private var running = false
    private var holding = false
    private var lastStep = 0L
    private val tick = Runnable { invalidate() }

    fun resume() {
        running = true
        if (!mascot.dino) mascot.rest()   // 공룡 점프 중이면 그대로 (판을 접을 때 돌아온다)
        lastStep = System.nanoTime()
        invalidate()
    }

    fun pause() {
        running = false
        removeCallbacks(tick)
        if (holding) { holding = false; mascot.cancel() }
    }

    private fun cx() = width - 8f * u
    private fun cy() = height - 5f * u

    override fun onDraw(c: Canvas) {
        if (running) {
            // 30fps 로 걸음을 밟는다 — 늦었으면 두 걸음까지 따라잡는다
            val now = System.nanoTime()
            var n = 0
            while (now - lastStep >= FRAME_NS && n < 2) {
                mascot.step(cx(), cy(), u, width.toFloat(), height.toFloat())
                lastStep += FRAME_NS
                n++
            }
            if (now - lastStep >= FRAME_NS) lastStep = now
            postDelayed(tick, FRAME_MS)
        }
        mascot.draw(c, cx(), cy(), u, pal.coral, pal.bg, pal.amber, pal.label, pal.green, pal.red, pal.title)
    }

    override fun onTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                if (mascot.hitsEgg(cx(), cy(), u, ev.x, ev.y)) {   // 알부터 — 클로디 곁이라 겹칠 수 있다
                    mascot.crackEgg()
                    return true
                }
                holding = mascot.hits(cx(), cy(), u, ev.x, ev.y)
                if (!holding) return false
                parent?.requestDisallowInterceptTouchEvent(true)   // 누르고 있는 동안 스크롤이 채 가지 않게
                mascot.press()
            }
            MotionEvent.ACTION_UP -> if (holding) {
                holding = false
                mascot.release()
                performClick()
            }
            MotionEvent.ACTION_CANCEL -> if (holding) {
                holding = false
                mascot.cancel()
            }
        }
        return true
    }

    override fun performClick(): Boolean = super.performClick()

    /** 테스트 — 폰 없이 몇 걸음 굴려 그림을 뽑는다. */
    fun stepForPreview(frames: Int) {
        repeat(frames) { mascot.step(cx(), cy(), u, width.toFloat(), height.toFloat()) }
    }

    private companion object {
        const val FRAME_MS = 33L
        const val FRAME_NS = 33_333_333L
    }
}
