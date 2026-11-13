package com.kyijgnes.cooldown.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** 버전 비교·APK 고르기 (순수 함수) */
class VersionsTest {

    @Test
    fun 새_버전만_새롭다() {
        assertTrue(Versions.isNewer("0.46", "0.45"))
        assertTrue(Versions.isNewer("1.0", "0.99"))
        assertTrue(Versions.isNewer("0.10", "0.9"))      // 글자 순서가 아니라 숫자로
        assertTrue(Versions.isNewer("0.45.1", "0.45"))
        assertFalse(Versions.isNewer("0.45", "0.45"))
        assertFalse(Versions.isNewer("0.45.0", "0.45"))
        assertFalse(Versions.isNewer("0.44", "0.45"))
        assertFalse(Versions.isNewer("0.9", "0.10"))
    }

    @Test
    fun 모르면_새롭지_않다() {
        assertFalse(Versions.isNewer("", "0.45"))
        assertFalse(Versions.isNewer("0.46", ""))
        assertFalse(Versions.isNewer("latest", "0.45"))
        assertFalse(Versions.isNewer("99999999999999", "0.45"))   // 너무 큰 숫자는 못 읽은 것으로
    }

    @Test
    fun 태그의_v를_깎는다() {
        assertEquals("0.46", Versions.fromTag("v0.46"))
        assertEquals("0.46", Versions.fromTag(" V0.46 "))
        assertEquals("0.46", Versions.fromTag("0.46"))
    }

    @Test
    fun 쿨다운_APK를_고른다() {
        val zip = "claude-cooldown-v0.46.zip" to "https://x/zip"
        val apk = "claude-cooldown-v0.46.apk" to "https://x/apk"
        val other = "other.apk" to "https://x/other"
        assertEquals("https://x/apk", Versions.pickApk(listOf(zip, other, apk)))
        assertEquals("https://x/other", Versions.pickApk(listOf(zip, other)))
        assertNull(Versions.pickApk(listOf(zip)))
        assertNull(Versions.pickApk(listOf("a.apk" to "http://x/plain")))   // https 만
        assertNull(Versions.pickApk(emptyList()))
    }
}

/** 릴리스 응답 읽기 — org.json 이 있어야 해서 Robolectric 으로 돈다 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class ReleaseParseTest {

    @Test
    fun 태그와_APK_주소를_읽는다() {
        val body = """
            {"tag_name":"v0.46","assets":[
              {"name":"claude-cooldown-v0.46.zip","browser_download_url":"https://github.com/a.zip"},
              {"name":"claude-cooldown-v0.46.apk","browser_download_url":"https://github.com/a.apk"}]}
        """.trimIndent()
        assertEquals(NewVersion.Release("0.46", "https://github.com/a.apk"), NewVersion.parse(body))
    }

    @Test
    fun APK가_없어도_버전은_읽는다() {
        assertEquals(NewVersion.Release("0.46", ""), NewVersion.parse("""{"tag_name":"v0.46"}"""))
    }

    @Test
    fun 엉터리는_null() {
        assertNull(NewVersion.parse("not json"))
        assertNull(NewVersion.parse("""{"message":"Not Found"}"""))
    }
}
