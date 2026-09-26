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
 * 홈 화면에서 알을 깼을 때 — **홈 화면 위에 투명하게 떠서 판만 그린다.** 배경화면에서 깼든 홈 위젯에서
 * 깼든 같은 화면이다.
 *
 * ★ 왜 투명한 화면인가: 배경화면은 **런처가 길게 누르기를 채 간다** — 점프를 조금만 길게 눌러도 홈 화면
 *   편집 메뉴가 떴다(2026-09-26 실사용). 이 화면은 손가락이 끝까지 우리 것이라 누르고 있어도 된다.
 *   위젯은 애초에 그림 한 장이라 게임을 못 돌린다. 바탕을 비워 두어 판 말고는 홈 화면 그대로다.
 *
 * - 판 자리: 배경화면에서 왔으면 **미터기 자리**(`EXTRA_TOP`), 위젯에서 왔으면 **누른 칸의 줄**(`sourceBounds`).
 * - 들어오는 장면: 알에서 깬 공룡이 서 있던 곳(`EXTRA_FROM`, 위젯은 칸 자리에서 어림)에서 폴짝 판으로.
 * - 화면 어디를 눌러도 뛴다. 닫기: 판 왼쪽 위 ✕ · 뒤로 가기 · 20초 그대로 · 홈이나 딴 앱으로 가기.
 * - 최근 앱 목록에 안 남고(`excludeFromRecents`) 앱 본체와 다른 작업으로 뜬다(`taskAffinity=""`).
 */
class DinoOverlayActivity : Activity() {

    private lateinit var view: OverlayView
    private var fromWidget = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        fromWidget = intent?.getStringExtra(DinoHost.EXTRA_SOURCE) == "widget"
        val prefs = getSharedPreferences(DINO_PREFS, MODE_PRIVATE)
        val anchor = intent?.sourceBounds
        val top = intent?.getFloatExtra(DinoHost.EXTRA_TOP, Float.NaN)?.takeUnless { it.isNaN() }
        val from = intent?.getFloatArrayExtra(DinoHost.EXTRA_FROM) ?: anchor?.let {
            // 위젯 — 알은 클로디 칸 오른쪽 아래쯤에 있다 (칸 그림은 `WidgetClaudi.bitmap`)
            floatArrayOf(it.left + it.width() * 0.75f, it.exactCenterY() + it.width() * 0.25f, it.width() / 46f)
        }
        view = OverlayView(this, prefs.getInt(DINO_BEST, 0), anchor, top, from)
        view.board.onBest = { best -> prefs.edit().putInt(DINO_BEST, best).apply() }
        view.board.onExit = { view.post { finish() } }   // 그리는 중에 닫지 않게 한 박자 뒤로
        view.board.onIntroDone = { DinoHost.boardSettled = true }
        setContentView(view)
        DinoHost.boardSettled = from == null
        DinoHost.overlayUp = true
        if (fromWidget) WidgetClaudi.setAll(this, "away")   // 위젯의 클로디는 판 속으로
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
        DinoHost.overlayUp = false
        DinoHost.boardSettled = false
        DinoHost.onClosed?.invoke()          // 배경화면의 클로디가 돌아온다
        DinoHost.onClosed = null
        if (fromWidget) WidgetClaudi.setAll(this, "idle")
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

/**
 * 투명한 판 한 줄. 자리는 `boardTop`(화면 좌표, 배경화면 미터기 자리) → 없으면 `anchor`(누른 위젯 칸)의
 * 세로 한가운데 → 그것도 없으면 화면 40%. `from`(화면 좌표) 이 있으면 거기서 공룡이 뛰어들며 열린다.
 */
class OverlayView(
    ctx: Context, best: Int,
    private val anchor: Rect?, private val boardTop: Float? = null, from: FloatArray? = null,
) : View(ctx) {

    val board = DinoBoard(ctx, best)
    private val loc = IntArray(2)
    private var introFrom = from

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

    /** 판 위끝 (이 뷰 좌표) — 화면 밖으로 안 나가게. */
    fun top(): Float {
        val bh = board.heightFor(width.toFloat())
        getLocationOnScreen(loc)
        val t = when {
            boardTop != null -> boardTop - loc[1]
            anchor != null -> anchor.exactCenterY() - loc[1] - bh / 2f
            else -> height * 0.4f - bh / 2f
        }
        return t.coerceIn(0f, (height - bh).coerceAtLeast(0f))
    }

    override fun onDraw(c: Canvas) {
        introFrom?.let {                       // 첫 장 — 알 자리를 이 뷰 좌표로 옮겨 들어오는 장면을 건다
            getLocationOnScreen(loc)
            board.startIntro(it[0] - loc[0], it[1] - loc[1], it[2])
            introFrom = null
        }
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
