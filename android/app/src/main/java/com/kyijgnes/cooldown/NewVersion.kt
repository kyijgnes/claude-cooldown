package com.kyijgnes.cooldown

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * 쿨다운 **자기 자신의** 새 버전 알림 (2026-11-11). PC `pc/cooldown_newver.py` 와 같은 결.
 *
 * - 알리기까지만 한다. 받기·깔기는 사람이 한다(릴리스 페이지를 브라우저로 연다).
 * - GitHub 공개 API `releases/latest` 의 `tag_name` 한 칸만 읽는다. 보내는 것은 없다.
 * - 앱을 켤 때마다 묻지 않고 `EVERY` 에 한 번만 묻고, 답은 저장해 두었다가 쓴다.
 */
object NewVersion {
    private const val API = "https://api.github.com/repos/kyijgnes/claude-cooldown/releases/latest"
    const val PAGE = "https://github.com/kyijgnes/claude-cooldown/releases/latest"
    private const val EVERY = 6 * 3600 * 1000L
    private const val PREFS = "newver"
    private const val AT = "checked_at"
    private const val LATEST = "latest"

    fun mine(ctx: Context): String = try {
        ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: ""
    } catch (e: Exception) {
        ""
    }

    /** 받을 새 버전 번호("0.40") — 없거나 모르면 null. 저장해 둔 답만 본다(네트워크 없음). */
    fun pending(ctx: Context): String? {
        val latest = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(LATEST, "") ?: ""
        return if (isNewer(latest, mine(ctx))) latest else null
    }

    /** 때가 됐으면 물어서 저장한다. **작업 스레드에서** 부를 것. 물었으면 true. */
    fun refresh(ctx: Context): Boolean {
        val prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val now = System.currentTimeMillis()
        if (now - prefs.getLong(AT, 0L) < EVERY) return false
        val latest = fetch() ?: return false
        prefs.edit().putLong(AT, now).putString(LATEST, latest).apply()
        return true
    }

    private fun fetch(): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(API).openConnection() as HttpURLConnection).apply {
                connectTimeout = 10_000
                readTimeout = 10_000
                setRequestProperty("Accept", "application/vnd.github+json")
                setRequestProperty("User-Agent", "claude-cooldown")
            }
            if (conn.responseCode != 200) return null
            val body = conn.inputStream.bufferedReader().use { it.readText() }
            JSONObject(body).optString("tag_name").trimStart('v', 'V').ifEmpty { null }
        } catch (e: Exception) {
            null
        } finally {
            conn?.disconnect()
        }
    }

    fun isNewer(latest: String, mine: String): Boolean {
        if (latest.isEmpty() || mine.isEmpty()) return false
        val a = Regex("\\d+").findAll(latest).map { it.value.toInt() }.toList()
        val b = Regex("\\d+").findAll(mine).map { it.value.toInt() }.toList()
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }
}
