package com.kyijgnes.cooldown.dino

import android.app.Activity
import android.content.Context
import android.graphics.Canvas
import android.graphics.Rect
import android.os.Bundle
import android.view.MotionEvent
import android.view.View
import com.kyijgnes.cooldown.widget.WidgetClaudi

/**
 * 홈 위젯에서 알을 깼을 때 — **홈 화면 위에 투명하게 떠서 위젯이 있던 줄에 판을 깐다.**
 * 위젯은 그림 한 장이라 게임을 못 돌린다. 그래서 창을 하나 띄우되 바탕을 비워 두어, 판만 위젯
 * 자리에 보이고 나머지는 홈 화면 그대로다(배경화면을 쓰는 사람은 이게 필요 없다 — 배경화면이 판을 그린다).
 *
 * - 판 자리는 누른 클로디 칸의 화면 위치(`intent.sourceBounds`)에서 온다. 없으면 화면 40% 자리.
 * - 화면 어디를 눌러도 뛴다. 닫기: 판 왼쪽 위 ✕ · 뒤로 가기 · 20초 그대로 · 홈이나 딴 앱으로 가기.
 * - 떠 있는 동안 위젯의 클로디는 판 속에 들어가 비어 있고(`away`), 닫으면 평소로 돌아온다.
 * - 최근 앱 목록에 안 남고(`excludeFromRecents`) 앱 본체와 다른 작업으로 뜬다(`taskAffinity=""`).
 */
class DinoOverlayActivity : Activity() {

    private lateinit var view: OverlayView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences(DINO_PREFS, MODE_PRIVATE)
        view = OverlayView(this, prefs.getInt(DINO_BEST, 0), intent?.sourceBounds)
        view.board.onBest = { best -> prefs.edit().putInt(DINO_BEST, best).apply() }
        view.board.onExit = { view.post { finish() } }   // 그리는 중에 닫지 않게 한 박자 뒤로
        setContentView(view)
        WidgetClaudi.setAll(this, "away")   // 클로디는 판 속으로
    }

    override fun onResume() {
        super.onResume()
        view.resume()
    }

    override fun onPause() {
        view.pause()
        super.onPause()
    }

    /** 홈 버튼이나 딴 앱으로 가면 판을 접는다 — 투명한 창이 뒤에 남아 있으면 헷갈린다. */
    override fun onStop() {
        super.onStop()
        if (!isFinishing) finish()
    }

    override fun onDestroy() {
        WidgetClaudi.setAll(this, "idle")   // 클로디가 위젯으로 돌아온다
        super.onDestroy()
    }

    override fun finish() {
        super.finish()
        @Suppress("DEPRECATION")
        overridePendingTransition(0, 0)
    }

    private companion object {
        const val DINO_PREFS = "dino"   // 배경화면·앱 첫 화면과 같은 최고 기록
        const val DINO_BEST = "best"
    }
}

/** 투명한 판 한 줄 — `anchor`(누른 위젯 칸, 화면 좌표)의 세로 한가운데에 판을 깐다. */
class OverlayView(ctx: Context, best: Int, private val anchor: Rect?) : View(ctx) {

    val board = DinoBoard(ctx, best)
    private val loc = IntArray(2)

    init {
        keepScreenOn = true
        isClickable = true
    }

    fun resume() {
        board.resume()
        postInvalidateOnAnimation()
    }

    fun pause() {
        board.pause()
        invalidate()
    }

    /** 판 위끝 — 위젯이 있던 줄 한가운데, 화면 밖으로 안 나가게. */
    fun top(): Float {
        val bh = board.heightFor(width.toFloat())
        getLocationOnScreen(loc)
        val cy = anchor?.let { it.exactCenterY() - loc[1] } ?: (height * 0.4f)
        return (cy - bh / 2f).coerceIn(0f, (height - bh).coerceAtLeast(0f))
    }

    override fun onDraw(c: Canvas) {
        board.advance()
        board.paint(c, top(), width.toFloat())
        if (board.active) postInvalidateOnAnimation()
    }

    override fun onTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> { board.down(ev.x, ev.y); postInvalidateOnAnimation() }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> { board.up(); performClick() }
        }
        return true
    }

    override fun performClick(): Boolean = super.performClick()
}
