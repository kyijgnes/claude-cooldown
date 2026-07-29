package com.kyijgnes.cooldown

import android.graphics.Bitmap
import android.graphics.Canvas
import com.kyijgnes.cooldown.wallpaper.WallpaperArt
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
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

    @Test
    fun `위젯과 배경화면 그림을 남긴다`() {
        val ctx = RuntimeEnvironment.getApplication()

        // 넓은 위젯 — 보통 / 최악(100%·긴 글자) / 값 없음
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(37f, 62f), now), "넓은위젯_보통.png")
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(100f, 100f), now), "넓은위젯_가득.png")
        save(GaugeRenderer.wide(ctx, 1080, 300, snap(null, null), now), "넓은위젯_값없음.png")
        save(GaugeRenderer.wide(ctx, 720, 260, snap(37f, 62f, stale = true), now), "넓은위젯_PC꺼짐.png")

        // 작은 위젯
        save(GaugeRenderer.small(ctx, 300, snap(37f, 62f), now), "작은위젯.png")
        save(GaugeRenderer.small(ctx, 300, snap(93f, 12f), now), "작은위젯_임박.png")

        // 상태바 아이콘 (실제로는 24dp 로 줄어든다)
        save(GaugeRenderer.statusIcon(7f), "상태바_7.png")
        save(GaugeRenderer.statusIcon(100f), "상태바_100.png")
        save(GaugeRenderer.statusIcon(null), "상태바_값없음.png")

        // 라이브 배경화면 (FHD+ 세로)
        val wall = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        WallpaperArt.render(ctx, Canvas(wall), snap(37f, 62f), now, 12L)
        save(wall, "배경화면.png")
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
