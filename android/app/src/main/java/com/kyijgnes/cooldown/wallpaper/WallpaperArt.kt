package com.kyijgnes.cooldown.wallpaper

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.Limit
import com.kyijgnes.cooldown.Look
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.Snapshot
import com.kyijgnes.cooldown.WallpaperGrab
import kotlin.math.max
import kotlin.math.min

/**
 * 배경화면 **그리기만** 한다 — 화면·수명 관리는 CooldownWallpaperService 가 맡는다.
 * (데스크탑에서 앱과 스킨을 나눈 것과 같은 결. 폰 없이 테스트로 그림을 뽑아 볼 수 있다)
 *
 * 두 겹이다: **배경**(쓰던 배경화면·고른 사진, 없으면 밋밋한 바다색)과
 * 그 위에 뜨는 **미터기 판**. 무엇을 어디에 그릴지는 `Look.Values` 로 받는다 —
 * 이 파일은 설정을 직접 안 읽는다(꾸미기 화면이 '저장 전' 값으로 미리보기를 그려야 하기 때문).
 */
object WallpaperArt {

    private val REGULAR: Typeface = Typeface.create("sans-serif", Typeface.NORMAL)
    private val MEDIUM: Typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)




    // ── 미터기 판 (모든 값이 판 너비 u 의 비율. 크기를 키워도 구도가 안 무너진다) ──
    private const val BLOCK_W = 0.82f        // 판 너비 ÷ 화면 너비 (크기 1.0 일 때)

    /**
     * @param look   지금 그릴 값 한 벌. 꾸미기 화면은 **저장 전 값**을 넘겨 미리보기를 그린다.
     * @param mascot 클로디를 그릴 상태 뭉치. 상태를 들고 있으므로 **그리는 쪽이 하나씩 갖고**
     *               넘겨 준다(이 파일은 상태를 안 갖는다). null 이면 안 그린다.
     */
    fun render(
        ctx: Context, c: Canvas, snap: Snapshot, now: Long,
        look: Look.Values = Look.read(ctx), mascot: Mascot? = null, locked: Boolean = true,
    ) {
        val p = Palette(ctx)
        val w = c.width.toFloat()
        val h = c.height.toFloat()

        // 배경 — 상어(별도 앱의 그림) → 사진 → 그것도 없으면 밋밋한 바다색
        val shark = look.scene == Look.SHARK
        if (shark) drawSea(c, w, h, p)
        val drawn = when {
            shark -> SharkPack.draw(ctx, c, w, h, now, locked, p, look.seaSize, look.seaX, look.seaY)
            else -> drawPhoto(ctx, c, w, h, look)
        }
        if (!drawn && !shark) drawSea(c, w, h, p)

        drawMeter(ctx, c, w, h, snap, now, p, look)

        // ★ 클로디는 **미터기 판 위에** 그린다 — 판 안쪽에 앉혀 두므로 뒤로 가면 가려진다.
        //   자리 비움·축하 폭죽이 화면 크기를 알아야 해서 `step` 에도 그릴 자리를 넘긴다.
        if (look.mascot && mascot != null) {
            val cx = look.mascotX * w
            val cy = look.mascotY * h
            val u = mascotCell(w)
            mascot.step(cx, cy, u, w, h)
            // 뒤 셋(초록·빨강·흰빛)은 완주 축하 폭죽에만 쓴다
            mascot.draw(c, cx, cy, u, p.coral, p.bg, p.amber, p.label,
                p.green, p.red, p.title)
        }
    }

    // ---------------------------------------------------------------- 배경

    /** 클로디 도트 한 칸(px). 화면 너비 기준이라 어느 폰에서나 같은 비율로 보인다. */
    fun mascotCell(w: Float): Float = w / 95f

    /** 누른 자리가 클로디 위인가 — 배경화면 터치와 꾸미기 화면 끌기가 같은 판정을 쓴다. */
    fun hitsMascot(w: Float, h: Float, look: Look.Values, mascot: Mascot, x: Float, y: Float) =
        look.mascot && mascot.hits(look.mascotX * w, look.mascotY * h, mascotCell(w), x, y)

    /** 배경으로 쓸 그림이 없을 때의 밋밋한 바탕. 밝게는 단색, 어둡게는 위아래로 깊어진다. */
    private fun drawSea(c: Canvas, w: Float, h: Float, p: Palette) {
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

    /** 고른 사진(또는 쓰던 배경화면)을 화면에 꽉 차게. 못 읽으면 false — 부르는 쪽이 상어로 내려간다. */
    private fun drawPhoto(ctx: Context, c: Canvas, w: Float, h: Float, look: Look.Values): Boolean {
        if (look.scene == Look.SHARK) return false
        val bmp = photoFor(ctx, photoUri(ctx, look)) ?: return false
        c.drawBitmap(bmp, null, photoRect(bmp, w, h, look), Paint(Paint.FILTER_BITMAP_FLAG))
        return true
    }

    /**
     * 어떤 그림을 배경으로 쓸지 — **고른 사진이 없으면 폰에 걸려 있던 배경화면**을 쓴다.
     * 아무것도 안 고른 사람에게 쓰던 배경 그대로 + 미터기가 보이는 게 기본이다.
     */
    private fun photoUri(ctx: Context, look: Look.Values): String =
        look.photo.ifEmpty { WallpaperGrab.saved(ctx) }

    /** 짧은 쪽을 화면에 맞춰 꽉 채우고, 남는 쪽은 사용자가 끌어 둔 자리로 자른다. */
    private fun photoRect(bmp: Bitmap, w: Float, h: Float, look: Look.Values): RectF {
        val s = max(w / bmp.width, h / bmp.height)
        val dw = bmp.width * s
        val dh = bmp.height * s
        val left = -(dw - w) * look.bgX
        val top = -(dh - h) * look.bgY
        return RectF(left, top, left + dw, top + dh)
    }

    // ---------------------------------------------------------------- 미터기 판

    /**
     * 미터기 판이 놓이는 자리. **화면 밖으로 못 나간다** — 끌다가 넘겨도 여기서 잡는다.
     * (끌기는 언제나 이 '이미 잡힌 자리'에서 시작하므로 되돌릴 때 먹통 구간이 안 생긴다)
     */
    fun meterRect(w: Float, h: Float, look: Look.Values): RectF {
        val pad = w * 0.03f
        // 글자 크기도 판 너비에서 나오므로, 판이 화면을 넘으면 글자가 통째로 잘린다
        val u = min(w * BLOCK_W * look.meterSize, w - pad * 2f)
        val bh = blockHeight(look.meter, u)
        val cx = pin(look.meterX * w, pad + u / 2f, w - pad - u / 2f)
        val cy = pin(look.meterY * h, pad + bh / 2f, h - pad - bh / 2f)
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
        ctx: Context, c: Canvas, w: Float, h: Float, snap: Snapshot, now: Long,
        p: Palette, look: Look.Values,
    ) {
        if (look.meter == Look.NONE) return
        val r = meterRect(w, h, look)

        if (look.plateOn) {
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

        when (look.meter) {
            Look.RINGS -> drawRings(c, r, snap, now, p)
            Look.NUMBERS -> drawNumbers(c, r, snap, now, p)
            else -> drawBars(c, r, snap, now, p)
        }
    }

    /** 막대 두 줄. `[5시간] [47%] [━━게이지━━] [2시간 07분 후]` */
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
            val span = if (i == 0) Limit.FIVE_SPAN_MS else Limit.WEEK_SPAN_MS
            GaugeRenderer.drawBar(
                c, RectF(r.left, barTop, r.right, barTop + u * 0.0219f), limit.pct, p,
                limit.dueFraction(now, span),
            )
        }
    }

    /** 링 둘 — 시계 옆에 두면 숫자가 덜 겹친다. */
    private fun drawRings(c: Canvas, r: RectF, snap: Snapshot, now: Long, p: Palette) {
        val u = r.width()
        val d = u * 0.40f
        val cell = u / 2f

        listOf(snap.five, snap.week).forEachIndexed { i, limit ->
            val cx = r.left + cell * (i + 0.5f)
            val span = if (i == 0) Limit.FIVE_SPAN_MS else Limit.WEEK_SPAN_MS
            GaugeRenderer.drawArc(
                c, RectF(cx - d / 2f, r.top, cx + d / 2f, r.top + d), limit.pct, p, d * 0.10f,
                limit.dueFraction(now, span),
            )

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
    fun hitsMeter(w: Float, h: Float, look: Look.Values, x: Float, y: Float): Boolean {
        if (look.meter == Look.NONE) return false
        val r = meterRect(w, h, look)
        val grab = r.width() * 0.06f
        return x >= r.left - grab && x <= r.right + grab &&
            y >= r.top - grab && y <= r.bottom + grab
    }

    /** 미터기 판을 끈 만큼 옮긴 값. 자리 계산은 `meterRect` 한 곳에만 있다. */
    fun dragMeter(w: Float, h: Float, look: Look.Values, dx: Float, dy: Float): Look.Values {
        val r = meterRect(w, h, look)
        return look.withMeterPos((r.centerX() + dx) / w, (r.centerY() + dy) / h)
    }

    /** 배경을 끈 만큼 옮긴 값 — 상어면 상어가, 사진이면 잘려 나간 쪽이 따라온다. */
    fun dragBg(ctx: Context, w: Float, h: Float, look: Look.Values, dx: Float, dy: Float): Look.Values {
        if (look.scene == Look.SHARK) return look.withBg(look.bgX + dx / w, look.bgY + dy / h)
        val bmp = photoFor(ctx, photoUri(ctx, look)) ?: return look
        val r = photoRect(bmp, w, h, look)
        val overW = r.width() - w
        val overH = r.height() - h
        return look.withBg(
            if (overW > 1f) -(r.left + dx) / overW else look.bgX,
            if (overH > 1f) -(r.top + dy) / overH else look.bgY,
        )
    }

    // ---------------------------------------------------------------- 사진 읽기

    private var photoKey = ""
    private var photo: Bitmap? = null

    /**
     * 고른 사진. **주소가 같으면 다시 안 읽는다** — 16fps 로 다시 그리는 화면이라
     * 매 프레임 디코딩하면 폰이 뜨거워진다.
     *
     * ★ 캐시 키에 **캔버스 크기를 넣지 말 것.** 색을 재려고 96×211 로 작게 한 번 그리는
     *   길(`onComputeColors`)이 있어서, 크기를 키로 쓰면 그릴 때마다 큰 사진을 다시 읽는다.
     *   크기는 화면 해상도로 한 번만 정하고, 캔버스가 작으면 그릴 때 줄이면 그만이다.
     */
    private fun photoFor(ctx: Context, uri: String): Bitmap? {
        if (uri.isEmpty()) return null
        // ★★ **주소만으로 캐시하면 안 된다.** 쓰던 배경화면은 늘 같은 파일 이름
        //   (`phone_wallpaper.png`)에 덮어써서, 배경을 바꿔도 주소가 그대로다 —
        //   그러면 **배경화면 그리는 프로세스가 옛 그림을 계속 쓴다**(실제로 그랬다).
        //   파일이 마지막으로 바뀐 때를 키에 섞어 내용이 바뀌면 다시 읽게 한다.
        val key = "$uri|${stampOf(uri)}"
        if (key == photoKey && photo != null) return photo
        val dm = ctx.resources.displayMetrics
        photoKey = key
        photo = decodePhoto(ctx, uri, dm.widthPixels, dm.heightPixels)
        return photo
    }

    /** 파일이면 마지막으로 바뀐 때. 고른 사진(content://)은 주소가 바뀌니 0 이면 된다. */
    private fun stampOf(uri: String): Long = try {
        if (uri.startsWith("file://")) {
            java.io.File(android.net.Uri.parse(uri).path ?: "").lastModified()
        } else {
            0L
        }
    } catch (e: Exception) {
        0L
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
        null   // 지운 사진·권한 만료 — 상어 바다로 내려간다
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

    /** 사진을 바꾸면 캐시를 버린다(주소가 같아도 내용이 다를 수 있다). */
    fun forgetPhoto() {
        photoKey = ""
        photo = null
    }
}
