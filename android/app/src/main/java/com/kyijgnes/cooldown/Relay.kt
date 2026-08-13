package com.kyijgnes.cooldown

import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import org.json.JSONObject

/**
 * 릴레이 서버에서 사용량을 읽어 온다. GET 하나뿐이라 표준 HttpURLConnection 으로 충분하다.
 *
 * 오류 문구는 **짧은 한국어 명사형** — 위젯의 좁은 칸에 그대로 나간다.
 */
object Relay {
    const val PATH = "/api/cooldown"
    private const val TIMEOUT = 15_000

    sealed interface Result {
        data class Ok(val snapshot: Snapshot) : Result
        data class Err(val text: String) : Result
    }

    fun fetch(base: String, key: String): Result {
        if (base.isEmpty() || key.length != 32) return Result.Err("연결 안 됨")

        var conn: HttpURLConnection? = null
        try {
            conn = (URL("$base$PATH?key=$key").openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = TIMEOUT
                readTimeout = TIMEOUT
                setRequestProperty("Accept", "application/json")
                useCaches = false
            }
            val code = conn.responseCode
            if (code == 400) return Result.Err("키 오류")
            if (code == 404) return Result.Err("PC 기록 없음")
            if (code >= 400) return Result.Err("서버 오류 $code")

            val body = conn.inputStream.bufferedReader().use { it.readText() }
            val snap = Snapshot.parse(body) ?: return Result.Err("형식 변경")
            return Result.Ok(snap)
        } catch (e: SocketTimeoutException) {
            return Result.Err("응답 없음")
        } catch (e: IOException) {
            return Result.Err("연결 실패")
        } catch (e: Exception) {
            return Result.Err("연결 실패")
        } finally {
            conn?.disconnect()
        }
    }
}

/**
 * 클로드 코드 원격 대기를 **폰에서 켜고 끈다.**
 *
 * 사용량([Relay])과 방향이 반대다 — 이쪽은 폰이 '이렇게 해 달라(want)' 를 쓰고,
 * PC 위젯이 그걸 읽어 `claude rc` 를 띄우거나 끈다. PC 는 '지금 상태(state)' 를 적어 두고
 * 폰은 그걸 읽어 화면에 보여 준다.
 *
 * ★ 명령 큐가 아니라 **원하는 상태**다 — PC 가 꺼져 있을 때 눌러도 증발하지 않고,
 *   다음에 PC 가 켜지면 그대로 따라간다.
 * ★ **PC 가 곧바로 따르지는 않는다** — 위젯이 2분마다 물어보므로 그만큼 걸린다.
 *   (주기를 줄이면 릴레이 무료 한도를 태운다. server/README.md)
 */
object RemoteRelay {
    const val PATH = "/api/remote"
    private const val TIMEOUT = 15_000

    /** want·state 는 "on"/"off"(state 는 "fail" 도), 모르면 null. */
    data class Status(val want: String?, val state: String?, val stale: Boolean)

    /** 지금 무엇을 원했고 PC 가 어떤 상태인지. 못 읽으면 null. */
    fun fetch(base: String, key: String): Status? {
        if (base.isEmpty() || key.length != 32) return null

        var conn: HttpURLConnection? = null
        try {
            conn = (URL("$base$PATH?key=$key").openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                connectTimeout = TIMEOUT
                readTimeout = TIMEOUT
                setRequestProperty("Accept", "application/json")
                useCaches = false
            }
            if (conn.responseCode >= 400) return null
            val o = JSONObject(conn.inputStream.bufferedReader().use { it.readText() })
            return Status(
                // 서버가 JSON null 을 주면 optString 이 "null" 이라는 **글자**를 준다 — 걸러낸다
                want = o.optString("want").takeIf { it.isNotEmpty() && it != "null" },
                state = o.optString("state").takeIf { it.isNotEmpty() && it != "null" },
                stale = o.optBoolean("stale", true),
            )
        } catch (e: SocketTimeoutException) {
            return null
        } catch (e: IOException) {
            return null
        } catch (e: Exception) {
            return null
        } finally {
            conn?.disconnect()
        }
    }

    /** '켜 줘'/'꺼 줘' 를 적어 둔다. 성공했으면 true. */
    fun setWant(base: String, key: String, on: Boolean): Boolean {
        if (base.isEmpty() || key.length != 32) return false

        var conn: HttpURLConnection? = null
        try {
            conn = (URL("$base$PATH").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = TIMEOUT
                readTimeout = TIMEOUT
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
                useCaches = false
            }
            val body = JSONObject()
                .put("key", key)
                .put("want", if (on) "on" else "off")
                .toString()
            conn.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            return conn.responseCode < 400
        } catch (e: Exception) {
            return false
        } finally {
            conn?.disconnect()
        }
    }
}
