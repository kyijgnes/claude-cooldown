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
import com.kyijgnes.cooldown.Look
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
 * 두 겹이다: **배경**(상어 바다 / 바다색만 / 내 사진)과 그 위에 뜨는 **미터기 판**.
 * 무엇을 어디에 그릴지는 `Look` 이 갖고 있고, 고르는 화면은 `CustomizeActivity` 다.
 *
 * 상어 그림·배치·박자는 폰에 깔려 있던 갤럭시 테마에서 그대로 가져왔다(아래 dp 값은
 * 원본 `animation.xml` 실측치. 출처는 클로드 디자인 프로젝트 `Shark Wallpaper Request`
 * 의 `theme_package/`).
 */
object WallpaperArt {

    private val REGULAR: Typeface = Typeface.create("sans-serif", Typeface.NORMAL)
    private val MEDIUM: Typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)

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

    // ── 미터기 판 (모든 값이 판 너비 u 의 비율. 크기를 키워도 구도가 안 무너진다) ──
    private const val BLOCK_W = 0.82f        // 판 너비 ÷ 화면 너비 (크기 1.0 일 때)

    fun render(ctx: Context, c: Canvas, snap: Snapshot, now: Long) {
        val p = Palette(ctx)
        val w = c.width.toFloat()
        val h = c.height.toFloat()
        val scene = Look.scene(ctx)

        if (scene != Look.PHOTO || !drawPhoto(ctx, c, w, h)) drawSea(c, w, h, p)

        if (scene == Look.SEA) {
            // 원본 360×640dp 캔버스를 **상어 한가운데가 정해진 자리에 오도록** 얹는다 —
            // 물방울·그림자까지 한 덩어리로 따라와서 크기를 바꿔도 구도가 안 무너진다
            val k = artScale(ctx, w, h)
            val ox = Look.artX(ctx) * w - SHARK_CX * k
            val oy = Look.artY(ctx) * h - SHARK_CY * k
            drawBubbles(c, k, ox, oy, now, p)
            drawShark(ctx, c, k, ox, oy, now, p)
        }

        drawMeter(ctx, c, w, h, snap, now, p)
    }

    // ---------------------------------------------------------------- 배경

    private fun drawSea(c: Canvas, w: Float, h: Float, p: Palette) {
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

    /** 고른 사진을 화면에 꽉 차게. 못 읽으면 false — 부르는 쪽이 바다로 내려간다. */
    private fun drawPhoto(ctx: Context, c: Canvas, w: Float, h: Float): Boolean {
        val bmp = photoFor(ctx, w.toInt(), h.toInt()) ?: return false
        val r = photoRect(ctx, bmp, w, h)
        c.drawBitmap(bmp, null, r, Paint(Paint.FILTER_BITMAP_FLAG))
        return true
    }

    /** 짧은 쪽을 화면에 맞춰 꽉 채우고, 남는 쪽은 사용자가 끌어 둔 자리(artX/artY)로 자른다. */
    private fun photoRect(ctx: Context, bmp: Bitmap, w: Float, h: Float): RectF {
        val s = max(w / bmp.width, h / bmp.height)
        val dw = bmp.width * s
        val dh = bmp.height * s
        val left = -(dw - w) * Look.artX(ctx)
        val top = -(dh - h) * Look.artY(ctx)
        return RectF(left, top, left + dw, top + dh)
    }

    // ---------------------------------------------------------------- 상어

    private fun artScale(ctx: Context, w: Float, h: Float) =
        Look.artSize(ctx) * min(w / CANVAS_W, h / ART_BOTTOM)

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
    private var artOf = 0
    private var tinted: PorterDuffColorFilter? = null
    private var tintOf = 0

    /**
     * 입 다문 얼굴이 기본이다 — 폰 원본이 그랬고, 잇몸도 살짝 핑크다
     * (`art/paint_gums.py` 로 칠해 넣었다). 입 벌린 쪽은 꾸미기에서 고를 수 있다.
     */
    private fun sharkArt(ctx: Context): Bitmap {
        val id = if (Look.mouth(ctx) == Look.OPEN) R.drawable.shark_open else R.drawable.shark
        val cached = art
        if (cached != null && artOf == id) return cached
        artOf = id
        return BitmapFactory.decodeResource(ctx.resources, id).also { art = it }
    }

    /** 어둡게에서는 곱하기로 상어를 깊은 바다색까지 내린다. 흰색이면 원본 그대로. */
    private fun artPaint(tint: Int): Paint {
        if (tint != tintOf) {
            tintOf = tint
            tinted = if (tint == -1) null else PorterDuffColorFilter(tint, PorterDuff.Mode.MULTIPLY)
        }
        return Paint(Paint.FILTER_BITMAP_FLAG).apply { colorFilter = tinted }
    }

    // ---------------------------------------------------------------- 미터기 판

    /**
     * 미터기 판이 놓이는 자리. **화면 밖으로 못 나간다** — 끌다가 넘겨도 여기서 잡는다.
     * (끌기는 언제나 이 '이미 잡힌 자리'에서 시작하므로 되돌릴 때 먹통 구간이 안 생긴다)
     */
    fun meterRect(ctx: Context, w: Float, h: Float): RectF {
        val pad = w * 0.03f
        // 글자 크기도 판 너비에서 나오므로, 판이 화면을 넘으면 글자가 통째로 잘린다
        val u = min(w * BLOCK_W * Look.meterSize(ctx), w - pad * 2f)
        val bh = blockHeight(Look.meter(ctx), u)
        val cx = pin(Look.meterX(ctx) * w, pad + u / 2f, w - pad - u / 2f)
        val cy = pin(Look.meterY(ctx) * h, pad + bh / 2f, h - pad - bh / 2f)
        return RectF(cx - u / 2f, cy - bh / 2f, cx + u / 2f, cy + bh / 2f)
    }

    /** 판이 화면보다 크면 가둘 수가 없다 — 그럴 땐 가운데. */
    private fun pin(v: Float, lo: Float, hi: Float) =
        if (lo > hi) (lo + hi) / 2f else v.coerceIn(lo, hi)

    private fun blockHeight(style: String, u: Float): Float = when (style) {
        Look.RINGS -> u * 0.532f
        Look.NUMBERS -> u * 0.514f
        Look.NONE -> 0f
        else -> u * 0.586f
    }

    private fun drawMeter(
        ctx: Context, c: Canvas, w: Float, h: Float, snap: Snapshot, now: Long, p: Palette,
    ) {
        val style = Look.meter(ctx)
        if (style == Look.NONE) return
        val r = meterRect(ctx, w, h)

        if (Look.plate(ctx)) {
            // 판은 글자 둘레로 좀 더 넓게. 미터기를 모서리까지 끌어도 화면 밖으로는 안 나간다
            val pad = r.width() * 0.055f
            val plate = RectF(
                max(r.left - pad, 0f), max(r.top - pad, 0f),
                min(r.right + pad, w), min(r.bottom + pad, h),
            )
            c.drawRoundRect(
                plate, pad * 1.4f, pad * 1.4f,
                Paint(Paint.ANTI_ALIAS_FLAG).apply {
                    color = (0xC4 shl 24) or (p.bg and 0xFFFFFF)
                },
            )
        }

        when (style) {
            Look.RINGS -> drawRings(c, r, snap, now, p)
            Look.NUMBERS -> drawNumbers(c, r, snap, now, p)
            else -> drawBars(c, r, snap, now, p)
        }
    }

    /** 막대 두 줄 — 꾸미기 전과 같은 모양. `[5시간] [47%] ... [2시간 07분 남음]` */
    private fun drawBars(c: Canvas, r: RectF, snap: Snapshot, now: Long, p: Palette) {
        val u = r.width()
        c.drawText("클로드 쿨다운", r.left, r.top + u * 0.045f, paint(u * 0.040f, p.faint, REGULAR))

        listOf(snap.five, snap.week).forEachIndexed { i, limit ->
            val top = r.top + u * (0.1374f + 0.29f * i)
            c.drawText(limit.label, r.left, top, paint(u * 0.044f, p.label, REGULAR))

            val pctBase = top + u * 0.100f
            val pctPt = paint(u * 0.104f, if (limit.pct == null) p.faint else p.title, MEDIUM)
            c.drawText(limit.pctText(), r.left, pctBase, pctPt)

            // 배경화면은 보이는 동안 매 프레임 다시 그리므로 남은 시간을 상대 시간으로 써도 안 틀린다
            val leftPt = paint(u * 0.044f, p.faint, REGULAR)
            val left = limit.leftText(now)
            c.drawText(left, r.right - leftPt.measureText(left), pctBase, leftPt)

            val barTop = pctBase + u * 0.0366f
            GaugeRenderer.drawBar(c, RectF(r.left, barTop, r.right, barTop + u * 0.0219f), limit.pct, p)
        }
    }

    /** 링 둘 — 시계 옆에 두면 숫자가 덜 겹친다. */
    private fun drawRings(c: Canvas, r: RectF, snap: Snapshot, now: Long, p: Palette) {
        val u = r.width()
        val d = u * 0.40f
        val cell = u / 2f

        listOf(snap.five, snap.week).forEachIndexed { i, limit ->
            val cx = r.left + cell * (i + 0.5f)
            GaugeRenderer.drawArc(c, RectF(cx - d / 2f, r.top, cx + d / 2f, r.top + d), limit.pct, p, d * 0.10f)

            val numPt = paint(d * 0.30f, if (limit.pct == null) p.faint else p.title, MEDIUM)
            center(c, limit.pctText(), cx, r.top + d * 0.52f, numPt)
            center(c, limit.label, cx, r.top + d + u * 0.040f, paint(u * 0.045f, p.label, REGULAR))
            center(c, limit.leftText(now), cx, r.top + d + u * 0.095f, paint(u * 0.038f, p.faint, REGULAR))
        }
    }

    /** 숫자만 — 게이지 없이 크게. 잠금화면 시계 아래에 두면 깔끔하다. */
    private fun drawNumbers(c: Canvas, r: RectF, snap: Snapshot, now: Long, p: Palette) {
        val u = r.width()
        listOf(snap.five, snap.week).forEachIndexed { i, limit ->
            val labelBase = r.top + u * (0.046f + 0.30f * i)
            c.drawText(limit.label, r.left, labelBase, paint(u * 0.046f, p.label, REGULAR))

            val pctBase = labelBase + u * 0.158f
            val pctPt = paint(u * 0.158f, if (limit.pct == null) p.faint else p.title, MEDIUM)
            c.drawText(limit.pctText(), r.left, pctBase, pctPt)

            val leftPt = paint(u * 0.044f, p.faint, REGULAR)
            val left = limit.leftText(now)
            c.drawText(left, r.right - leftPt.measureText(left), pctBase, leftPt)
        }
    }

    private fun center(c: Canvas, text: String, cx: Float, base: Float, pt: Paint) {
        c.drawText(text, cx - pt.measureText(text) / 2f, base, pt)
    }

    private fun paint(size: Float, color: Int, face: Typeface) =
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            textSize = size
            this.color = color
            typeface = face
        }

    // ---------------------------------------------------------------- 끌어서 옮기기

    /** 손가락이 미터기 판을 짚었는가. 아니면 배경을 끄는 것으로 본다. */
    fun hitsMeter(ctx: Context, w: Float, h: Float, x: Float, y: Float): Boolean {
        if (Look.meter(ctx) == Look.NONE) return false
        val r = meterRect(ctx, w, h)
        val grab = r.width() * 0.06f
        return x >= r.left - grab && x <= r.right + grab &&
            y >= r.top - grab && y <= r.bottom + grab
    }

    /** 미터기 판을 끈 만큼 옮긴다. 자리 계산은 `meterRect` 한 곳에만 있다. */
    fun dragMeter(ctx: Context, w: Float, h: Float, dx: Float, dy: Float) {
        val r = meterRect(ctx, w, h)
        Look.setMeterPos(ctx, (r.centerX() + dx) / w, (r.centerY() + dy) / h)
    }

    /** 배경을 끈 만큼 옮긴다 — 상어면 상어가, 사진이면 잘려 나간 쪽이 따라온다. */
    fun dragArt(ctx: Context, w: Float, h: Float, dx: Float, dy: Float) {
        when (Look.scene(ctx)) {
            Look.SEA -> Look.setArtPos(ctx, Look.artX(ctx) + dx / w, Look.artY(ctx) + dy / h)
            Look.PHOTO -> {
                val bmp = photoFor(ctx, w.toInt(), h.toInt()) ?: return
                val r = photoRect(ctx, bmp, w, h)
                val overW = r.width() - w
                val overH = r.height() - h
                Look.setArtPos(
                    ctx,
                    if (overW > 1f) -(r.left + dx) / overW else Look.artX(ctx),
                    if (overH > 1f) -(r.top + dy) / overH else Look.artY(ctx),
                )
            }
        }
    }

    // ---------------------------------------------------------------- 사진 읽기

    private var photoKey = ""
    private var photo: Bitmap? = null

    /**
     * 고른 사진. **키가 같으면 다시 안 읽는다** — 16fps 로 다시 그리는 화면이라
     * 매 프레임 디코딩하면 폰이 뜨거워진다. 못 읽었으면 null 을 캐시해 되묻지 않는다.
     */
    private fun photoFor(ctx: Context, w: Int, h: Int): Bitmap? {
        val uri = Look.photo(ctx)
        if (uri.isEmpty()) return null
        val key = "$uri@${w}x$h"
        if (key == photoKey) return photo
        photoKey = key
        photo = decodePhoto(ctx, uri, w, h)
        return photo
    }

    private fun decodePhoto(ctx: Context, uri: String, w: Int, h: Int): Bitmap? = try {
        val target = android.net.Uri.parse(uri)
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        ctx.contentResolver.openInputStream(target).use { BitmapFactory.decodeStream(it, null, bounds) }
        val opts = BitmapFactory.Options().apply {
            inSampleSize = sampleSize(bounds.outWidth, bounds.outHeight, w, h)
        }
        ctx.contentResolver.openInputStream(target).use { BitmapFactory.decodeStream(it, null, opts) }
    } catch (e: Exception) {
        null   // 지운 사진·권한 만료 — 바다로 내려간다
    } catch (e: OutOfMemoryError) {
        null   // 배경화면이 통째로 죽느니 바다를 보여 준다
    }

    /**
     * 몇 분의 1 로 줄여 읽을지. 잘라 쓸 만큼은 남기되, **화면 넓이의 3배를 넘기지 않는다** —
     * 폰 사진은 4000×3000 이 흔한데(48MB) 배경화면 프로세스는 그만한 메모리를 못 받는다.
     */
    private fun sampleSize(srcW: Int, srcH: Int, w: Int, h: Int): Int {
        if (srcW <= 0 || srcH <= 0 || w <= 0 || h <= 0) return 1
        var s = 1
        while (srcW / (s * 2) >= w && srcH / (s * 2) >= h) s *= 2
        val cap = 3L * w * h
        while (srcW.toLong() / s * (srcH / s) > cap) s *= 2
        return s
    }

    /** 꾸미기 화면에서 사진을 바꾸면 캐시를 버린다(주소가 같아도 내용이 다를 수 있다). */
    fun forgetPhoto() {
        photoKey = ""
        photo = null
    }
}
