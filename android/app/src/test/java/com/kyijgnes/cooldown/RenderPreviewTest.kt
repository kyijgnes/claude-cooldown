package com.kyijgnes.cooldown

import android.graphics.Bitmap
import android.graphics.Canvas
import android.view.View
import com.kyijgnes.cooldown.wallpaper.WallpaperArt
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * 폰 없이 화면 그림을 PNG 로 뽑는다 — `gradlew testDebugUnitTest` 후
 * `app/build/미리보기/` 를 열어 보면 된다. 값 규칙(초기화 보정)도 여기서 확인한다.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34])
class RenderPreviewTest {

    private val out = File("build/미리보기").apply { mkdirs() }
    private val now = 1_753_800_000_000L  // 고정 시각 — 그림이 매번 같게

    private fun snap(five: Float?, week: Float?, stale: Boolean = false) = Snapshot(
        five = Limit("5시간", five, now + 2 * 3600_000L + 7 * 60_000L),
        week = Limit("주간", week, now + 3 * 86_400_000L + 4 * 3600_000L),
        updatedAt = now - 60_000L,
        stale = stale,
    )

    private fun save(bmp: Bitmap, name: String) {
        File(out, name).outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    /** 꾸미기 값 한 벌로 배경화면 한 장. `locked` 는 잠금화면(상어가 입을 다문 쪽). */
    private fun wallpaper(
        ctx: android.content.Context, name: String, locked: Boolean = true,
        look: Look.Values = SEA, at: Long = now,
    ) {
        val bmp = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        WallpaperArt.render(ctx, Canvas(bmp), snap(37f, 62f), at, look, locked)
        save(bmp, "$name.png")
    }

    /** 사진을 안 고른 기본값은 상어 바다로 내려간다 — 그림으로 확인할 땐 대놓고 상어 바다로. */
    private val SEA = Look.DEFAULT.copy(scene = Look.SEA)

    @Test
    fun `위젯과 배경화면 그림을 남긴다`() {
        val ctx = RuntimeEnvironment.getApplication()

        // 넓은 위젯 — 보통 / 최악(100%·긴 글자) / 값 없음.
        // ★ 홈 위젯은 **판 없이(card=false)** 배경화면 위에 바로 얹힌다 — 실제와 같게 그린다.
        //   글자에 바탕색 후광이 둘러져 있는지 그림으로 확인할 것(어두운 배경화면 대비).
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(37f, 62f), now, card = false), "넓은위젯_보통.png")
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(100f, 100f), now, card = false), "넓은위젯_가득.png")
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(null, null), now, card = false), "넓은위젯_값없음.png")
        save(
            GaugeRenderer.wide(ctx, 720, 260, snap(37f, 62f, stale = true), now, card = false),
            "넓은위젯_PC꺼짐.png",
        )
        // 앱 화면은 판을 깐 쪽을 쓴다
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(37f, 62f), now), "앱화면_게이지.png")

        // 작은 위젯
        save(GaugeRenderer.small(ctx, 300, snap(37f, 62f), now, card = false), "작은위젯.png")
        save(GaugeRenderer.small(ctx, 300, snap(93f, 12f), now, card = false), "작은위젯_임박.png")

        // 상태바 아이콘 (실제로는 24dp 로 줄어든다)
        save(GaugeRenderer.statusIcon(7f), "상태바_7.png")
        save(GaugeRenderer.statusIcon(47f), "상태바_47.png")
        save(GaugeRenderer.statusIcon(100f), "상태바_100.png")
        save(GaugeRenderer.statusIcon(null), "상태바_값없음.png")

        // 라이브 배경화면 (FHD+ 세로) — 상어가 제일 위일 때와 다 내려갔을 때
        wallpaper(ctx, "배경화면")
        wallpaper(ctx, "배경화면_내려감", at = now + 883L)
        // 잠금이 풀리면 상어가 입을 벌린다
        wallpaper(ctx, "배경화면_잠금해제", locked = false)

        // 꾸미기 — 고를 수 있는 것들을 한 장씩 (CustomizeActivity 의 선택지와 같은 순서)
        wallpaper(ctx, "꾸미기_링", look = SEA.copy(meter = Look.RINGS))
        wallpaper(ctx, "꾸미기_숫자만", look = SEA.copy(meter = Look.NUMBERS))
        wallpaper(ctx, "꾸미기_미터기없음", look = SEA.copy(meter = Look.NONE))
        wallpaper(ctx, "꾸미기_글씨뒤판", look = SEA.withPlate(true))
        wallpaper(
            ctx, "꾸미기_크게_위로",
            look = SEA.copy(meterSize = Look.METER_MAX, seaSize = Look.ART_MAX)
                .withMeterPos(0.5f, 0.28f).withBg(0.5f, 0.7f),
        )
        wallpaper(
            ctx, "꾸미기_작게_구석",
            // 화면 밖으로 못 나간다 — 모서리에 붙는다
            look = SEA.copy(meter = Look.NUMBERS, meterSize = Look.METER_MIN).withMeterPos(0f, 1f),
        )
        // 사진을 못 읽으면(안 골랐거나 지웠거나) 빈 파랑이 아니라 상어 바다로 내려간다
        wallpaper(ctx, "꾸미기_사진못읽음", look = Look.DEFAULT.copy(photo = "content://없는것/1"))

        // 앱 아이콘 — 런처가 달라는 크기가 제각각이라 두 크기로 뽑아 비율을 확인한다
        for (size in listOf(432, 144)) {
            ctx.getDrawable(R.mipmap.ic_launcher)?.let { icon ->
                val ic = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
                icon.setBounds(0, 0, size, size)
                icon.draw(Canvas(ic))
                save(ic, "앱아이콘_$size.png")
            }
        }

        // 어둡게 (깊은 바다) — 상어 그림은 한 장이라 shark_tint 로 물들여 내린다
        RuntimeEnvironment.setQualifiers("+night")
        val dark = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        WallpaperArt.render(
            RuntimeEnvironment.getApplication(), Canvas(dark), snap(37f, 62f), now, SEA, true,
        )
        save(dark, "배경화면_어둡게.png")
        RuntimeEnvironment.setQualifiers("+notnight")
    }

    /**
     * **위젯 고르는 화면에 뜨는 그림**(`previewLayout`)을 폰 없이 본다.
     * 실제 위젯 레이아웃은 런타임에 채우는 빈 ImageView 라 그대로 걸면 빈 칸이 된다 —
     * 그래서 미리보기 전용 레이아웃을 따로 두고, 여기서 비어 보이지 않는지 확인한다.
     */
    @Test
    @Config(sdk = [34], qualifiers = "w360dp-h780dp-xxhdpi")
    fun `위젯 고르는 화면 그림을 남긴다`() {
        for ((layout, w, h, name) in listOf(
            Quad(R.layout.widget_preview_wide, 900, 240, "위젯미리보기_넓은"),
            Quad(R.layout.widget_preview_small, 240, 240, "위젯미리보기_작은"),
        )) {
            val ctx = RuntimeEnvironment.getApplication()
            val view = android.view.LayoutInflater.from(ctx).inflate(layout, null)
            view.measure(
                View.MeasureSpec.makeMeasureSpec(w, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(h, View.MeasureSpec.EXACTLY),
            )
            view.layout(0, 0, w, h)
            val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
            view.draw(Canvas(bmp))
            save(bmp, "$name.png")
        }
    }

    private data class Quad(val layout: Int, val w: Int, val h: Int, val name: String)

    /**
     * 꾸미기 화면 자체도 폰 없이 본다 — 미리보기 판·선택지가 한 화면에 들어오는지.
     * 미리보기 크기가 화면 크기에서 나오므로 **진짜 폰 해상도(1080×2340)로 재야** 뜻이 있다.
     */
    @Test
    @Config(sdk = [34], qualifiers = "w360dp-h780dp-xxhdpi")
    fun `꾸미기 화면 그림을 남긴다`() {
        // 기본은 '내 사진'인데 테스트엔 사진이 없다 — 상어 바다로 두고 칸을 다 보이게 한다
        Look.write(RuntimeEnvironment.getApplication(), SEA)
        val controller = Robolectric.buildActivity(CustomizeActivity::class.java).setup()
        val root = controller.get().window.decorView
        val w = 1080
        val h = 2340
        root.measure(
            View.MeasureSpec.makeMeasureSpec(w, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(h, View.MeasureSpec.EXACTLY),
        )
        root.layout(0, 0, w, h)
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        root.draw(Canvas(bmp))
        save(bmp, "꾸미기화면.png")
        controller.pause().destroy()
    }

    @Test
    fun `초기화 시각이 지나면 0퍼센트로 본다`() {
        val past = Limit("5시간", 47f, now - 1_000L)
        val settled = past.settled(now)
        assertEquals(0f, settled.pct)
        assertNull(settled.resetAt)  // 창이 없으니 '사용 전'
        assertEquals("사용 전", settled.whenText(now))

        // 아직 안 지났으면 그대로 둔다
        val live = Limit("5시간", 47f, now + 60_000L)
        assertEquals(47f, live.settled(now).pct)
    }

    @Test
    fun `서버 응답을 읽는다`() {
        val body = """
            {"five_hour_pct":7.0,"five_hour_reset":"2026-07-29T22:19:59+00:00",
             "seven_day_pct":55.0,"seven_day_reset":"2026-08-01T00:00:00+00:00",
             "updated_at":"2026-07-29T13:00:00.000Z","stale":false,"age_min":1}
        """.trimIndent()
        val s = Snapshot.parse(body)!!
        assertEquals(7f, s.five.pct)
        assertEquals(55f, s.week.pct)
        assertEquals(false, s.stale)
        assertEquals(1785363599000L, s.five.resetAt)  // 2026-07-29T22:19:59Z

        // 필드 이름이 바뀌면 '빈 값' 이 아니라 '고장' 이다
        assertNull(Snapshot.parse("""{"fiveHourPct":7.0}"""))
    }

    @Test
    fun `주소를 정돈한다`() {
        assertEquals("https://a.vercel.app", Store.normalizeUrl("a.vercel.app"))
        assertEquals("https://a.vercel.app", Store.normalizeUrl("https://a.vercel.app/"))
        assertEquals("https://a.vercel.app", Store.normalizeUrl("https://a.vercel.app/api/cooldown"))
        assertEquals("", Store.normalizeUrl("  "))
        assertEquals("", Store.normalizeUrl("ftp://a"))
    }
}
