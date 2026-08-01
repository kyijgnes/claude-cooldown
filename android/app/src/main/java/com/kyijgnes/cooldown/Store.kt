package com.kyijgnes.cooldown

import android.content.Context
import android.net.Uri

/**
 * 설정과 마지막 값. 위젯·알림이 아무 스레드에서나 바로 읽어야 해서
 * SharedPreferences 를 쓴다 (DataStore 는 코루틴이 필요해 위젯에서 불편하다).
 */
object Store {
    private const val FILE = "cooldown"

    private const val K_URL = "url"
    private const val K_KEY = "key"
    private const val K_NOTIFY = "notify"
    private const val K_FIVE_PCT = "five_pct"
    private const val K_FIVE_RESET = "five_reset"
    private const val K_WEEK_PCT = "week_pct"
    private const val K_WEEK_RESET = "week_reset"
    private const val K_UPDATED = "updated"
    private const val K_STALE = "stale"
    private const val K_ERROR = "error"
    private const val K_FETCHED = "fetched"

    private const val NONE = Long.MIN_VALUE

    private fun prefs(ctx: Context) =
        ctx.applicationContext.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    // ---------------------------------------------------------------- 연결

    /** 서버 주소 (끝에 /api/cooldown 없이). */
    fun url(ctx: Context): String = prefs(ctx).getString(K_URL, "") ?: ""

    fun key(ctx: Context): String = prefs(ctx).getString(K_KEY, "") ?: ""

    fun paired(ctx: Context): Boolean = url(ctx).isNotEmpty() && key(ctx).length == 32

    fun setPair(ctx: Context, url: String, key: String) {
        prefs(ctx).edit().putString(K_URL, normalizeUrl(url)).putString(K_KEY, key.trim()).apply()
    }

    /**
     * 'myapp.vercel.app' / 'https://myapp.vercel.app/' / '.../api/cooldown' 을
     * 같은 값으로 정돈한다. cooldown_push.normalize_url 과 같은 규칙.
     */
    fun normalizeUrl(raw: String): String {
        var text = raw.trim().trimEnd('/')
        if (text.isEmpty()) return ""
        if (!text.contains("://")) text = "https://$text"
        val uri = Uri.parse(text)
        val scheme = uri.scheme?.lowercase()
        if ((scheme != "http" && scheme != "https") || uri.authority.isNullOrEmpty()) return ""
        var path = (uri.path ?: "").trimEnd('/')
        if (path.endsWith(Relay.PATH)) path = path.dropLast(Relay.PATH.length)
        return "$scheme://${uri.authority}$path"
    }

    /**
     * QR·링크로 들어온 claudecooldown://pair?url=..&key=.. 를 읽는다.
     * 넣을 게 있으면 true.
     */
    fun applyPairUri(ctx: Context, uri: Uri?): Boolean {
        if (uri == null || uri.scheme != "claudecooldown") return false
        val url = normalizeUrl(uri.getQueryParameter("url") ?: "")
        val key = (uri.getQueryParameter("key") ?: "").trim()
        if (url.isEmpty() || key.length != 32) return false
        setPair(ctx, url, key)
        return true
    }

    // ---------------------------------------------------------------- 표시 설정

    /**
     * 상태바·잠금화면·AOD 는 **한 알림 하나**라서 따로 못 켜고 끈다 — 실기로 확인했다.
     * 상태바 아이콘을 없애는 유일한 손잡이(채널 중요도 `MIN`)를 쓰면 삼성 잠금화면이
     * 그 알림을 통째로 감춰서 셋이 같이 사라진다. 그래서 스위치도 하나다.
     */
    fun notifyOn(ctx: Context): Boolean = prefs(ctx).getBoolean(K_NOTIFY, true)

    fun setNotifyOn(ctx: Context, on: Boolean) {
        prefs(ctx).edit().putBoolean(K_NOTIFY, on).apply()
    }

    // ---------------------------------------------------------------- 마지막 값

    fun snapshot(ctx: Context): Snapshot {
        val p = prefs(ctx)
        if (!p.contains(K_UPDATED)) return Snapshot.EMPTY
        return Snapshot(
            five = Limit("5시간", p.pct(K_FIVE_PCT), p.stamp(K_FIVE_RESET)),
            week = Limit("주간", p.pct(K_WEEK_PCT), p.stamp(K_WEEK_RESET)),
            updatedAt = p.getLong(K_UPDATED, 0L),
            stale = p.getBoolean(K_STALE, false),
        )
    }

    fun save(ctx: Context, snap: Snapshot) {
        prefs(ctx).edit()
            .putFloat(K_FIVE_PCT, snap.five.pct ?: Float.NaN)
            .putLong(K_FIVE_RESET, snap.five.resetAt ?: NONE)
            .putFloat(K_WEEK_PCT, snap.week.pct ?: Float.NaN)
            .putLong(K_WEEK_RESET, snap.week.resetAt ?: NONE)
            .putLong(K_UPDATED, snap.updatedAt)
            .putBoolean(K_STALE, snap.stale)
            .putLong(K_FETCHED, System.currentTimeMillis())
            .remove(K_ERROR)
            .apply()
    }

    /**
     * 마지막 오류. **값은 지우지 않는다** — 잠깐 안 될 때마다 숫자가 사라지면
     * 정작 궁금한 걸 못 본다 (데스크탑 위젯과 같은 규칙).
     */
    fun saveError(ctx: Context, text: String) {
        prefs(ctx).edit().putString(K_ERROR, text)
            .putLong(K_FETCHED, System.currentTimeMillis()).apply()
    }

    fun error(ctx: Context): String = prefs(ctx).getString(K_ERROR, "") ?: ""

    /** 폰이 마지막으로 서버에 물어본 시각. 0 이면 아직 없음. */
    fun fetchedAt(ctx: Context): Long = prefs(ctx).getLong(K_FETCHED, 0L)

    private fun android.content.SharedPreferences.pct(k: String): Float? {
        val v = getFloat(k, Float.NaN)
        return if (v.isNaN()) null else v
    }

    private fun android.content.SharedPreferences.stamp(k: String): Long? {
        val v = getLong(k, NONE)
        return if (v == NONE) null else v
    }
}
