package com.kyijgnes.cooldown

import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL

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
