package com.kyijgnes.cooldown.update

import android.content.Context
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * 쿨다운 **자기 자신의** 새 버전 확인 (2026-11-11, 11-13 부터 APK 받기까지). PC `pc/cooldown_newver.py` 와 같은 결.
 *
 * - GitHub 공개 API `releases/latest` 의 `tag_name` 과 APK 자산 주소만 읽는다. 보내는 것은 없다.
 * - 앱을 켤 때는 `EVERY` 에 한 번만 묻고, 하루 한 번은 `UpdateWorker` 가 묻는다. 답은 저장해 두고 쓴다.
 * - 네트워크가 안 되면 조용히 넘어간다(저장해 둔 답을 그대로 둔다).
 * - 받기·깔기는 `Updater` 가 한다.
 */
object NewVersion {
    private const val API = "https://api.github.com/repos/kyijgnes/claude-cooldown/releases/latest"
    const val PAGE = "https://github.com/kyijgnes/claude-cooldown/releases/latest"
    private const val EVERY = 3600 * 1000L
    private const val PREFS = "newver"
    private const val AT = "checked_at"
    private const val LATEST = "latest"
    private const val APK = "apk_url"
    private const val NOTIFIED = "notified"

    data class Release(val version: String, val apkUrl: String)

    fun mine(ctx: Context): String = try {
        ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: ""
    } catch (e: Exception) {
        ""
    }

    /** 받을 새 버전 번호("0.46"). 없거나 모르면 null. 저장해 둔 답만 본다(네트워크 없음). */
    fun pending(ctx: Context): String? {
        val latest = prefs(ctx).getString(LATEST, "") ?: ""
        return if (Versions.isNewer(latest, mine(ctx))) latest else null
    }

    /** 새 버전 APK 주소. 릴리스에 APK 가 안 붙었으면 빈 문자열. */
    fun apkUrl(ctx: Context): String = prefs(ctx).getString(APK, "") ?: ""

    /**
     * 때가 됐으면(또는 `force`) 물어서 저장한다. **작업 스레드에서** 부를 것.
     * 답을 받았으면 true, 안 물었거나 못 받았으면 false.
     */
    fun refresh(ctx: Context, force: Boolean = false): Boolean {
        val p = prefs(ctx)
        val now = System.currentTimeMillis()
        if (!force && now - p.getLong(AT, 0L) < EVERY) return false
        val rel = fetch() ?: return false
        p.edit().putLong(AT, now).putString(LATEST, rel.version).putString(APK, rel.apkUrl).apply()
        return true
    }

    /** 아직 알림으로 안 알린 새 버전이면 그 번호. 알렸으면 `markNotified`. */
    fun toNotify(ctx: Context): String? {
        val ver = pending(ctx) ?: return null
        return if (prefs(ctx).getString(NOTIFIED, "") == ver) null else ver
    }

    fun markNotified(ctx: Context, ver: String) {
        prefs(ctx).edit().putString(NOTIFIED, ver).apply()
    }

    /** `releases/latest` 응답 본문 → 버전·APK 주소. 버전을 못 읽으면 null. */
    fun parse(body: String): Release? = try {
        val o = JSONObject(body)
        val ver = Versions.fromTag(o.optString("tag_name"))
        if (ver.isEmpty()) {
            null
        } else {
            val list = o.optJSONArray("assets")
            val assets = (0 until (list?.length() ?: 0)).mapNotNull { i ->
                val a = list!!.optJSONObject(i) ?: return@mapNotNull null
                a.optString("name") to a.optString("browser_download_url")
            }
            Release(ver, Versions.pickApk(assets) ?: "")
        }
    } catch (e: Exception) {
        null
    }

    private fun fetch(): Release? {
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(API).openConnection() as HttpURLConnection).apply {
                connectTimeout = 10_000
                readTimeout = 10_000
                setRequestProperty("Accept", "application/vnd.github+json")
                setRequestProperty("User-Agent", "claude-cooldown")
            }
            if (conn.responseCode != 200) return null
            parse(conn.inputStream.bufferedReader().use { it.readText() })
        } catch (e: Exception) {
            null
        } finally {
            conn?.disconnect()
        }
    }

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
