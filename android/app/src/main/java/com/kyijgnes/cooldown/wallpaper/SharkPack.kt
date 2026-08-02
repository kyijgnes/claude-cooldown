package com.kyijgnes.cooldown.wallpaper

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.PorterDuff
import android.graphics.PorterDuffColorFilter
import android.net.Uri
import com.kyijgnes.cooldown.Palette
import kotlin.math.PI
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * **깔려 있으면 쓰는 배경 테마 — 상어.**
 *
 * 라이브 배경화면은 폰에 **하나만** 걸린다. 그래서 '상어 배경 + 사용량 미터기'를 같이 보려면
 * 둘 중 하나가 상대를 그려야 한다 — 우리가 상어를 그린다.
 *
 * ★ **그림은 이 앱에 없다.** 갤럭시 테마 원본이라 공개 앱에 넣을 수 없어서, 별도 앱
 *   `com.kyijgnes.sharkwallpaper`(비공개)가 갖고 있고 여기서 **읽어만 온다.**
 *   그 앱이 없으면 이 테마는 아예 안 보인다(고르는 칸에도 안 뜬다).
 * ★ 배치·박자(883ms 왕복, 물방울 1440/1600/1920ms)는 원본 테마 실측값이다.
 */
object SharkPack {

    const val AUTHORITY = "com.kyijgnes.sharkwallpaper.art"

    // ── 원본 테마 좌표계 (360×640dp 캔버스) ────────────────────────────────
    private const val CANVAS_W = 360f
    private const val ART_BOTTOM = 431.5f
    private const val SHARK_CX = 184.25f
    private const val SHARK_CY = 348f
    private const val SHARK_W = 110f
    private const val DIVE = 16.486f
    private const val SWIM_MS = 883L
    private const val SHADOW_CX = 181f
    private const val SHADOW_CY = 417.625f
    private const val SHADOW_W = 52f
    private const val SHADOW_H = 21.25f
    private const val SHADOW_GROW = 0.3f

    private var checked = false
    private var present = false
    private val art = HashMap<String, Bitmap?>()
    private var tinted: PorterDuffColorFilter? = null
    private var tintOf = 0

    /** 상어 앱이 깔려 있나 — 고르는 칸에 '상어'를 띄울지 여기서 갈린다. */
    fun installed(ctx: Context): Boolean {
        if (!checked) {
            checked = true
            present = try {
                ctx.packageManager.resolveContentProvider(AUTHORITY, 0) != null
            } catch (e: Exception) {
                false
            }
        }
        return present
    }

    /** 앱을 깔거나 지운 뒤 다시 보게 한다. */
    fun forget() {
        checked = false
        art.clear()
    }

    /**
     * 상어 바다 한 장. 그림을 못 읽으면(앱이 없거나 막혔으면) **false** — 부르는 쪽이
     * 다른 배경으로 내려간다.
     */
    fun draw(
        ctx: Context, c: Canvas, w: Float, h: Float, now: Long, locked: Boolean,
        p: Palette, size: Float, cxRatio: Float, cyRatio: Float,
    ): Boolean {
        val bmp = sharkArt(ctx, locked) ?: return false

        val k = size * min(w / CANVAS_W, h / ART_BOTTOM)
        val ox = cxRatio * w - SHARK_CX * k
        val oy = cyRatio * h - SHARK_CY * k

        drawBubbles(c, k, ox, oy, now, p)

        val t = swing(now)
        val grow = 1f + SHADOW_GROW * t
        val sw = SHADOW_W * k * grow / 2f
        val sh = SHADOW_H * k * grow / 2f
        val scx = ox + SHADOW_CX * k
        val scy = oy + SHADOW_CY * k
        c.drawOval(
            RectF(scx - sw, scy - sh, scx + sw, scy + sh),
            Paint(Paint.ANTI_ALIAS_FLAG).apply { color = p.sharkShadow },
        )

        val bw = SHARK_W * k
        val bh = bw * bmp.height / bmp.width
        val cx = ox + SHARK_CX * k
        val cy = oy + (SHARK_CY + DIVE * t) * k
        c.drawBitmap(
            bmp, null,
            RectF(cx - bw / 2f, cy - bh / 2f, cx + bw / 2f, cy + bh / 2f),
            artPaint(p.sharkTint),
        )
        return true
    }

    /** 883ms 에 걸쳐 0 → 1, 다시 883ms 에 걸쳐 1 → 0 (원본 repeatMode=REVERSE·선형). */
    private fun swing(now: Long): Float {
        val phase = (now % (SWIM_MS * 2)).toFloat() / SWIM_MS
        return if (phase <= 1f) phase else 2f - phase
    }

    /**
     * 물방울 다섯 덩이. 원본은 제자리에서 프레임만 도는 그림이라 **떠오르지 않는다** —
     * 크기·투명도만 흔들린다. 주기가 서로 안 나누어떨어져 다섯이 절대 같은 박자로 안 논다.
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

    private class Drop(val dx: Float, val dy: Float, val r: Float, val ring: Boolean = false)
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

    /** **잠겨 있으면 입을 다물고, 풀면 벌린다.** 그림은 상어 앱에서 한 번만 읽어 둔다. */
    private fun sharkArt(ctx: Context, locked: Boolean): Bitmap? {
        val name = if (locked) "shark" else "shark_open"
        if (art.containsKey(name)) return art[name]
        val bmp = try {
            ctx.contentResolver.openInputStream(Uri.parse("content://$AUTHORITY/$name")).use {
                BitmapFactory.decodeStream(it)
            }
        } catch (e: Exception) {
            null
        } catch (e: OutOfMemoryError) {
            null
        }
        art[name] = bmp
        return bmp
    }

    /** 어둡게에서는 곱하기로 상어를 깊은 바다색까지 내린다. 흰색이면 원본 그대로. */
    private fun artPaint(tint: Int): Paint {
        if (tint != tintOf) {
            tintOf = tint
            tinted = if (tint == -1) null else PorterDuffColorFilter(tint, PorterDuff.Mode.MULTIPLY)
        }
        return Paint(Paint.FILTER_BITMAP_FLAG).apply { colorFilter = tinted }
    }
}
