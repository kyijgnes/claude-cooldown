package com.kyijgnes.cooldown

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import com.kyijgnes.cooldown.wallpaper.Buddy
import com.kyijgnes.cooldown.wallpaper.Mascot
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.security.MessageDigest
import java.util.zip.ZipInputStream

/**
 * 캐릭터팩 — PC 에서 만든 「폰으로 보낼 캐릭터팩」(zip)을 가져와 **앱 안에만** 둔다(2026-11-22).
 *
 * 그림은 남의 것이라 APK·서버·공개 저장소에 안 들어간다. 사용자가 PC 메인 화면 > 위젯 모양 >
 * 「폰으로 보낼 팩 만들기」로 zip 을 만들고 카톡·USB 로 옮겨 옵션 > 「캐릭터팩 가져오기」로 고른다.
 * PC 가 효과까지 장면으로 구워 넣으므로(`pc/cooldown_pack_export.py`) 폰은 틀기만 한다.
 *
 *     filesDir/buddy/<캐릭터 열쇠>/캐릭터.json   PC 폰팩.json 의 캐릭터 하나 (그림 이름만 이 폴더 것으로)
 *     filesDir/buddy/<캐릭터 열쇠>/<해시>.webp    장면 묶음 그림
 *
 * - 고른 캐릭터는 `prefs("buddy").active`. 비었거나 없는 이름이면 클로디.
 * - ★ 남이 만든 파일을 받는 길이라 다 의심한다: 아는 이름의 파일만(`c<n>/<16 hex>.webp`·폰팩.json),
 *   크기 한도, 그림은 크기를 열어 보고 적힌 칸 수와 맞는지까지. 하나라도 틀리면 아무것도 안 남긴다.
 * - 동작 이름은 PC 폴더 이름 그대로 읽고, 폰이 모르는 이름은 버린다(`Buddy.MOTIONS`).
 */
object BuddyPack {
    const val CLAUDI = "클로디"
    const val MAX_CHARS = 8
    private const val FORMAT = 1
    private const val MANIFEST = "폰팩.json"
    private const val MAX_TOTAL = 150L * 1024 * 1024
    private const val MAX_ENTRY = 24L * 1024 * 1024
    private const val MAX_ENTRIES = 3000
    private const val MAX_SIDE = 4096
    private const val MAX_FRAMES = 96
    private const val PREFS = "buddy"
    private const val K_ACTIVE = "active"
    private const val K_STAMP = "stamp"
    private val PIC = Regex("""c\d{1,2}/[0-9a-f]{16}\.webp""")

    class PackError(msg: String) : Exception(msg)

    private fun prefs(ctx: Context) = ctx.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun root(ctx: Context): File = File(ctx.applicationContext.filesDir, "buddy")

    /** 넣어 둔 캐릭터 이름들 (이름 순). */
    fun names(ctx: Context): List<String> =
        (root(ctx).listFiles() ?: emptyArray()).filter { it.isDirectory && !it.name.startsWith("_") }
            .mapNotNull { dir -> readChar(dir)?.name }.sorted()

    /** 고른 캐릭터 이름. 클로디면 null. */
    fun active(ctx: Context): String? {
        val name = prefs(ctx).getString(K_ACTIVE, null) ?: return null
        return name.takeIf { it != CLAUDI && File(dirOf(ctx, it), "캐릭터.json").isFile }
    }

    fun setActive(ctx: Context, name: String?) {
        prefs(ctx).edit().putString(K_ACTIVE, name ?: CLAUDI).putLong(K_STAMP, System.nanoTime()).apply()
    }

    /** 바뀐 것을 알아채는 지문 — 고르거나 가져오거나 빼면 바뀐다. 그리는 쪽이 매 프레임 본다. */
    fun stamp(ctx: Context): Long = prefs(ctx).getLong(K_STAMP, 0L)

    private fun touch(ctx: Context) = prefs(ctx).edit().putLong(K_STAMP, System.nanoTime()).apply()

    fun remove(ctx: Context, name: String) {
        dirOf(ctx, name).deleteRecursively()
        if (prefs(ctx).getString(K_ACTIVE, null) == name) setActive(ctx, null) else touch(ctx)
    }

    private fun dirOf(ctx: Context, name: String) = File(root(ctx), keyOf(name))

    private fun keyOf(name: String): String {
        val d = MessageDigest.getInstance("SHA-1").digest(name.toByteArray(Charsets.UTF_8))
        return d.take(8).joinToString("") { "%02x".format(it) }
    }

    // ---------------------------------------------------------------- 읽기

    /** 고른 캐릭터를 읽는다 (없으면 null = 클로디). 같은 지문이면 읽어 둔 것을 쓴다. */
    fun current(ctx: Context): Buddy.Character? {
        val st = stamp(ctx)
        val cached = cache
        if (cached != null && cached.first == st) return cached.second
        val name = active(ctx)
        val got = name?.let { readChar(dirOf(ctx, it)) }
        cache = st to got
        return got
    }

    @Volatile private var cache: Pair<Long, Buddy.Character?>? = null

    private fun readChar(dir: File): Buddy.Character? = try {
        Buddy.Character.parse(JSONObject(File(dir, "캐릭터.json").readText()), dir)
    } catch (e: Exception) {
        null
    }

    /**
     * 그리는 쪽(배경화면·첫 화면·꾸미기·위젯)이 그리기 전에 부른다 — 고른 캐릭터를 클로디 자리에
     * 세우고(클로디면 비우고) 사용량으로 기분을 맞춘다.
     */
    fun sync(ctx: Context, mascot: Mascot, raw: Snapshot? = null, now: Long = System.currentTimeMillis()) {
        val ch = current(ctx)
        if (mascot.buddy?.character !== ch) mascot.buddy = ch?.let { Buddy(it) }
        if (ch != null && (raw != null || now - mascot.moodAt >= MOOD_EVERY_MS || now < mascot.moodAt)) {
            mascot.mood = moodOf(raw ?: Store.snapshot(ctx), now)
            mascot.moodAt = now
        }
    }

    /** 사용량 → 기분: 한도 다 참 `잠` · 80% 넘음 `허둥` · 5시간 한도가 막 풀림 `풀림:<시각>` · 그 밖 "". */
    fun moodOf(raw: Snapshot, now: Long): String {
        val five = raw.five.resetAt
        // 폰은 PC 가 새 값을 보낼 때까지 지난 창의 값을 들고 있다. 그 창이 끝난 지 10분 안이면 막 풀린 것
        if (five != null && now >= five && now - five <= JUST_RESET_MS && (raw.five.pct ?: 0f) > 0f) {
            return "풀림:$five"
        }
        val s = raw.settled(now)
        val worst = listOfNotNull(s.five.pct, s.week.pct).maxOrNull() ?: 0f
        return when {
            worst >= 99.5f -> "잠"
            worst >= 80f -> "허둥"
            else -> ""
        }
    }

    private const val JUST_RESET_MS = 10 * 60_000L
    private const val MOOD_EVERY_MS = 5_000L

    // ---------------------------------------------------------------- 가져오기

    /** zip 을 가져온다. 가져온 캐릭터 이름들을 돌려준다(고른 캐릭터는 안 바꾼다). */
    fun import(ctx: Context, uri: Uri): List<String> {
        val input = ctx.contentResolver.openInputStream(uri) ?: throw PackError("파일을 못 읽음")
        return input.use { importStream(ctx, it) }
    }

    fun importStream(ctx: Context, input: InputStream): List<String> {
        val base = root(ctx)
        base.mkdirs()
        val tmp = File(base, "_가져오는 중 ${System.nanoTime()}")
        try {
            tmp.mkdirs()
            val manifest = unzip(input, tmp)
            val chars = plan(manifest, tmp)
            val have = names(ctx).toSet()
            val after = have + chars.map { it.first }
            if (after.size > MAX_CHARS) throw PackError("캐릭터는 ${MAX_CHARS}명까지 · 하나 빼고 가져오기")
            for ((name, obj) in chars) {
                val staging = File(tmp, "_" + keyOf(name))
                staging.mkdirs()
                val motions = obj.getJSONObject("동작")
                for (m in motions.keys()) {
                    val list = motions.getJSONArray(m)
                    for (i in 0 until list.length()) {
                        val e = list.getJSONObject(i)
                        val src = File(tmp, e.getString("그림"))
                        val leaf = src.name
                        val dst = File(staging, leaf)
                        if (!dst.exists()) src.copyTo(dst)
                        e.put("그림", leaf)
                    }
                }
                File(staging, "캐릭터.json").writeText(obj.toString())
                val final = dirOf(ctx, name)
                final.deleteRecursively()   // 같은 이름은 새것으로 바꾼다
                if (!staging.renameTo(final)) throw PackError("저장 못 함")
            }
            touch(ctx)
            return chars.map { it.first }
        } finally {
            tmp.deleteRecursively()
        }
    }

    /** zip 을 풀어 폰팩.json 을 낸다. 모르는 파일·큰 파일이 있으면 거절. */
    private fun unzip(input: InputStream, into: File): JSONObject {
        var manifest: JSONObject? = null
        var total = 0L
        var count = 0
        try {
            ZipInputStream(input.buffered()).use { z ->
                while (true) {
                    val entry = z.nextEntry ?: break
                    if (entry.isDirectory) continue
                    if (++count > MAX_ENTRIES) throw PackError("파일이 너무 많은 팩")
                    val name = entry.name
                    val bytes = readCapped(z)
                    total += bytes.size
                    if (total > MAX_TOTAL) throw PackError("팩이 너무 큼")
                    when {
                        name == MANIFEST -> manifest = try {
                            JSONObject(String(bytes, Charsets.UTF_8))
                        } catch (e: Exception) {
                            throw PackError("팩 정보가 깨짐")
                        }
                        PIC.matches(name) -> File(into, name).apply { parentFile?.mkdirs() }.writeBytes(bytes)
                        name == "팩.json" ->   // PC 끼리 주고받는 캐릭터팩 (그림이 안 구워진 것)
                            throw PackError("PC 의 「폰으로 보낼 팩 만들기」로 만든 파일이 아님")
                        else -> throw PackError("팩 안에 모르는 파일")
                    }
                }
            }
        } catch (e: PackError) {
            throw e
        } catch (e: Exception) {
            throw PackError("캐릭터팩 파일이 아님")
        }
        return manifest ?: throw PackError("PC 의 「폰으로 보낼 팩 만들기」로 만든 파일이 아님")
    }

    private fun readCapped(z: ZipInputStream): ByteArray {
        val out = java.io.ByteArrayOutputStream()
        val buf = ByteArray(64 * 1024)
        var left = MAX_ENTRY
        while (true) {
            val n = z.read(buf)
            if (n < 0) break
            left -= n
            if (left < 0) throw PackError("그림 한 장이 너무 큼")
            out.write(buf, 0, n)
        }
        return out.toByteArray()
    }

    /** 폰팩.json 을 걸러 [(이름, 캐릭터 JSON)] 을 낸다. 그림은 크기까지 맞는지 본다. */
    private fun plan(m: JSONObject, dir: File): List<Pair<String, JSONObject>> {
        val fmt = m.optInt("형식", -1)
        if (fmt < 1) throw PackError("팩 정보가 깨짐")
        if (fmt > FORMAT) throw PackError("더 새 버전에서 만든 팩 · 앱 업데이트 필요")
        val arr = m.optJSONArray("캐릭터") ?: throw PackError("팩 정보가 깨짐")
        val out = ArrayList<Pair<String, JSONObject>>()
        for (i in 0 until arr.length()) {
            val c = arr.optJSONObject(i) ?: continue
            val name = c.optString("이름").trim().filter { it.code >= 32 && it !in "\\/:*?\"<>|" }.trim()
            if (name.isEmpty() || name == CLAUDI || name.startsWith("_")) continue
            val folder = c.optString("폴더")
            val motions = c.optJSONObject("동작") ?: continue
            val keep = JSONObject()
            for (mo in motions.keys()) {
                if (mo !in Buddy.MOTIONS) continue   // 폰이 모르는 동작은 버린다
                val list = motions.optJSONArray(mo) ?: continue
                val good = JSONArray()
                for (k in 0 until list.length()) {
                    val e = list.optJSONObject(k) ?: continue
                    if (checkClip(e, folder, dir)) good.put(e)
                }
                if (good.length() > 0) keep.put(mo, good)
            }
            if (keep.length() == 0) continue
            out.add(name to JSONObject().put("이름", name)
                .put("보는 쪽", if (c.optString("보는 쪽") == "왼쪽") "왼쪽" else "오른쪽").put("동작", keep))
        }
        if (out.isEmpty()) throw PackError("그림 없는 팩")
        if (out.map { it.first }.toSet().size != out.size) throw PackError("이름이 겹치는 캐릭터가 든 팩")
        return out
    }

    private fun checkClip(e: JSONObject, folder: String, dir: File): Boolean {
        val pic = e.optString("그림")
        if (!PIC.matches(pic) || !pic.startsWith("$folder/")) return false
        val w = e.optInt("폭"); val h = e.optInt("높이"); val cols = e.optInt("열")
        val ms = e.optJSONArray("ms") ?: return false
        val n = ms.length()
        if (w !in 1..MAX_SIDE || h !in 1..MAX_SIDE || cols !in 1..MAX_FRAMES || n !in 1..MAX_FRAMES) return false
        for (k in 0 until n) if (ms.optInt(k, -1) !in 1..60_000) return false
        val loop = e.optInt("되감기", 0)
        if (loop !in 0 until n) e.put("되감기", 0)
        val f = File(dir, pic)
        if (!f.isFile) return false
        val o = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(f.path, o)
        val rows = (n + cols - 1) / cols
        return o.outWidth >= w * minOf(cols, n) && o.outHeight >= h * rows
    }
}
