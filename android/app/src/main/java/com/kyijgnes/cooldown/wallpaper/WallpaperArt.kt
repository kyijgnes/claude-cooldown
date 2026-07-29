package com.kyijgnes.cooldown.wallpaper

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.PorterDuffColorFilter
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.Limit
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.Snapshot
import kotlin.math.PI
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * 배경화면 **그리기만** 한다 — 화면·수명 관리는 CooldownWallpaperService 가 맡는다.
 * (데스크탑에서 앱과 스킨을 나눈 것과 같은 결. 폰 없이 테스트로 그림을 뽑아 볼 수 있다)
 *
 * 결: 사용자가 폰에서 쓰던 **파란 상어 바다**. 상어 그림·배치·박자는 그 테마에서 그대로
 * 가져왔다(아래 dp 값은 원본 `animation.xml` 실측치. 출처는 클로드 디자인 프로젝트
 * `Shark Wallpaper Request` 의 `theme_package/`).
 * 위쪽은 상어가 헤엄치는 바다(잠금화면 시계·알림 자리), 아래 1/3 에만 게이지를 둔다.
 */
object WallpaperArt {

    private val REGULAR: Typeface = Typeface.create("sans-serif", Typeface.NORMAL)
    private val MEDIUM: Typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)

    /** 폰 원본 배경화면과 같은 **입 벌린** 상어. 다문 얼굴로 바꾸려면 `R.drawable.shark`. */
    private val SHARK_ART = R.drawable.shark_open

    // ── 원본 테마 좌표계 (360×640dp 캔버스) ────────────────────────────────
    private const val CANVAS_W = 360f
    private const val ART_BOTTOM = 431.5f    // 그림자가 1.3배로 커졌을 때의 아랫변

    private const val SHARK_CX = 184.25f     // 상어 칸 한가운데
    private const val SHARK_CY = 348f
    private const val SHARK_W = 110f
    private const val DIVE = 16.486f         // 883ms 동안 내려가는 거리
    private const val SWIM_MS = 883L         // 상어·그림자 한쪽 방향 시간

    private const val SHADOW_CX = 181f       // 그림자는 제자리에서 커지기만 한다
    private const val SHADOW_CY = 417.625f
    private const val SHADOW_W = 52f
    private const val SHADOW_H = 21.25f
    private const val SHADOW_GROW = 0.3f     // 상어가 다 내려가면 1.3배

    // ── 게이지 자리 (화면 높이 비율) ──────────────────────────────────────
    private const val ROW_TOP = 0.63f
    private const val ROW_GAP = 0.11f
    private const val LABEL_UP = 0.035f      // '클로드 쿨다운' 글자를 첫 줄 위로 올린 만큼

    fun render(ctx: Context, c: Canvas, snap: Snapshot, now: Long) {
        val p = Palette(ctx)
        val w = c.width.toFloat()
        val h = c.height.toFloat()

        drawBackdrop(c, w, h, p)

        // 바다 그림은 게이지 윗변까지만 쓴다. 안 들어가면 통째로 줄여 가운데 놓는다.
        val artBottom = h * (ROW_TOP - LABEL_UP) - w * 0.045f
        val k = min(w / CANVAS_W, artBottom / ART_BOTTOM)
        val ox = (w - CANVAS_W * k) / 2f
        val oy = (artBottom - ART_BOTTOM * k) / 2f

        drawBubbles(c, k, ox, oy, now, p)
        drawShark(ctx, c, k, ox, oy, now, p)

        val pad = w * 0.09f
        val top = h * ROW_TOP

        c.drawText("클로드 쿨다운", pad, top - h * LABEL_UP, paint(w * 0.033f, p.faint, REGULAR))

        listOf(snap.five, snap.week).forEachIndexed { i, limit ->
            drawRow(c, limit, now, pad, top + h * ROW_GAP * i, w, p)
        }
    }

    private fun drawBackdrop(c: Canvas, w: Float, h: Float, p: Palette) {
        // 원본은 단색 바다다(밝게). 어둡게에서만 위아래로 깊어진다.
        val sea = Paint().apply {
            shader = LinearGradient(
                0f, 0f, 0f, h,
                intArrayOf(p.seaTop, p.seaBottom),
                floatArrayOf(0f, 0.7f),
                Shader.TileMode.CLAMP,
            )
        }
        c.drawRect(0f, 0f, w, h, sea)
    }

    /**
     * 상어와 그림자. **883ms 왕복 하나로 둘 다 몬다** —
     * 상어가 16.5dp 내려가는 동안 그림자가 1.3배로 커진다(원본과 같은 박자).
     */
    private fun drawShark(
        ctx: Context, c: Canvas, k: Float, ox: Float, oy: Float, now: Long, p: Palette,
    ) {
        val t = swing(now)  // 0 → 1 → 0

        val grow = 1f + SHADOW_GROW * t
        val sw = SHADOW_W * k * grow / 2f
        val sh = SHADOW_H * k * grow / 2f
        val scx = ox + SHADOW_CX * k
        val scy = oy + SHADOW_CY * k
        c.drawOval(
            RectF(scx - sw, scy - sh, scx + sw, scy + sh),
            Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.sharkShadow },
        )

        val bmp = sharkArt(ctx)
        val bw = SHARK_W * k
        val bh = bw * bmp.height / bmp.width
        val cx = ox + SHARK_CX * k
        val cy = oy + (SHARK_CY + DIVE * t) * k
        c.drawBitmap(
            bmp,
            null,
            RectF(cx - bw / 2f, cy - bh / 2f, cx + bw / 2f, cy + bh / 2f),
            artPaint(p.sharkTint),
        )
    }

    /** 883ms 에 걸쳐 0 → 1, 다시 883ms 에 걸쳐 1 → 0 (원본 repeatMode=REVERSE·선형). */
    private fun swing(now: Long): Float {
        val phase = (now % (SWIM_MS * 2)).toFloat() / SWIM_MS
        return if (phase <= 1f) phase else 2f - phase
    }

    /**
     * 물방울 다섯 덩이. 원본은 제자리에서 프레임만 도는 그림이라 **떠오르지 않는다** —
     * 크기·투명도만 흔들린다. 주기 1440/1600/1920ms 가 서로 안 나누어떨어져
     * 다섯이 절대 같은 박자로 안 논다. **이 어긋남이 자연스러움의 핵심이라 그대로 둔다.**
     */
    private fun drawBubbles(c: Canvas, k: Float, ox: Float, oy: Float, now: Long, p: Palette) {
        val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.bubble }
        val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            style = Paint.Style.STROKE
            color = p.bubble
        }
        for (cl in CLUSTERS) {
            val phase = (now % cl.periodMs).toFloat() / cl.periodMs
            cl.drops.forEachIndexed { i, d ->
                val a = 2.0 * PI * (phase + i * 0.31f)
                val r = d.r * k * (1f + 0.16f * sin(a).toFloat())
                val x = ox + (cl.cx + d.dx) * k
                val y = oy + (cl.cy + d.dy) * k + 1.4f * k * sin(a + 1.1).toFloat()
                val alpha = (185 + 60 * sin(a + 2.2)).toInt()
                if (d.ring) {
                    ring.alpha = alpha
                    ring.strokeWidth = max(0.7f * k, r * 0.26f)
                    c.drawCircle(x, y, r, ring)
                } else {
                    fill.alpha = alpha
                    c.drawCircle(x, y, r, fill)
                }
            }
        }
    }

    /** 물방울 한 알 — 덩이 한가운데 기준 dp 오프셋·반지름, `ring` 이면 속이 빈 동그라미. */
    private class Drop(val dx: Float, val dy: Float, val r: Float, val ring: Boolean = false)

    /** 원본 `component_4`~`8` 의 60×60dp 칸 — 위치와 주기는 실측치, 알 배치는 원본 그림을 따랐다. */
    private class Cluster(
        val cx: Float, val cy: Float, val periodMs: Long, val drops: List<Drop>,
    )

    private val CLUSTERS = listOf(
        Cluster(
            91.25f, 199.5f, 1920L,
            listOf(Drop(-8f, -6f, 3.1f, ring = true), Drop(7f, 2f, 1.7f), Drop(2f, 12f, 1.2f)),
        ),
        Cluster(
            273.25f, 142.5f, 1440L,
            listOf(Drop(6f, -8f, 2.6f), Drop(-7f, 3f, 1.9f, ring = true), Drop(9f, 10f, 1.3f, ring = true)),
        ),
        Cluster(
            109.25f, 300.75f, 1920L,
            listOf(Drop(-9f, 4f, 2.8f, ring = true), Drop(5f, -7f, 2.1f), Drop(10f, 9f, 1.4f)),
        ),
        Cluster(
            254.75f, 293.75f, 1440L,
            listOf(Drop(8f, 5f, 2.4f, ring = true), Drop(-6f, -6f, 1.8f), Drop(-2f, 11f, 1.2f, ring = true)),
        ),
        Cluster(
            170.75f, 50.5f, 1600L,
            listOf(Drop(-5f, -4f, 2.2f), Drop(8f, 6f, 1.6f, ring = true), Drop(-9f, 9f, 1.1f)),
        ),
    )

    // 상어 비트맵과 물들이기 필터는 한 번만 만든다 (16fps 로 계속 다시 그린다)
    private var art: Bitmap? = null
    private var tinted: PorterDuffColorFilter? = null
    private var tintOf = 0

    private fun sharkArt(ctx: Context): Bitmap =
        art ?: BitmapFactory.decodeResource(ctx.resources, SHARK_ART).also { art = it }

    /** 어둡게에서는 곱하기로 상어를 깊은 바다색까지 내린다. 흰색이면 원본 그대로. */
    private fun artPaint(tint: Int): Paint {
        if (tint != tintOf) {
            tintOf = tint
            tinted = if (tint == -1) null else PorterDuffColorFilter(tint, PorterDuff.Mode.MULTIPLY)
        }
        return Paint(Paint.FILTER_BITMAP_FLAG).apply { colorFilter = tinted }
    }

    private fun drawRow(
        c: Canvas, limit: Limit, now: Long, pad: Float, top: Float, w: Float, p: Palette,
    ) {
        c.drawText(limit.label, pad, top, paint(w * 0.036f, p.label, REGULAR))

        val pctBase = top + w * 0.082f
        val pctPt = paint(w * 0.085f, if (limit.pct == null) p.faint else p.title, MEDIUM)
        c.drawText(limit.pctText(), pad, pctBase, pctPt)

        // 배경화면은 보이는 동안 매 프레임 다시 그리므로 남은 시간을 상대 시간으로 써도 안 틀린다
        val leftPt = paint(w * 0.036f, p.faint, REGULAR)
        val left = limit.leftText(now)
        c.drawText(left, w - pad - leftPt.measureText(left), pctBase, leftPt)

        val barTop = pctBase + w * 0.030f
        GaugeRenderer.drawBar(c, RectF(pad, barTop, w - pad, barTop + w * 0.018f), limit.pct, p)
    }

    private fun paint(size: Float, color: Int, face: Typeface) =
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = size
            this.color = color
            typeface = face
        }
}
