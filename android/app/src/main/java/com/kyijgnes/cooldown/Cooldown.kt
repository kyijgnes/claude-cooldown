package com.kyijgnes.cooldown

import org.json.JSONObject
import java.util.Calendar
import java.util.Locale

/**
 * 사용량 값과 그 표시 규칙. 화면(위젯·알림·배경화면)은 전부 여기 문자열을 쓴다.
 *
 * 데스크탑 cooldown_core.py 와 같은 규칙:
 *   · 퍼센트는 0~100 스케일 (100 을 곱하지 않는다)
 *   · 값이 없으면 null — '--' 로 그린다
 */

/** 한도 하나. pct 가 null 이면 이 계정에 그 한도가 없거나 아직 모른다. */
data class Limit(val label: String, val pct: Float?, val resetAt: Long?) {

    /**
     * **초기화 시각이 지났으면 0% 로 본다.**
     *
     * PC 가 꺼져 있어도 폰이 스스로 맞추는 핵심 규칙이다 — 창은 시간이 지나면
     * 반드시 풀리고, 그 뒤로는 다시 쓰기 전까지 0% 다. 옛 퍼센트를 그대로 두면
     * 폰이 며칠씩 틀린 숫자를 붙들고 있게 된다.
     */
    fun settled(now: Long): Limit =
        if (resetAt != null && resetAt <= now) copy(pct = 0f, resetAt = null) else this

    /** '47%' / '--' */
    fun pctText(): String = pct?.let { "${Math.round(it)}%" } ?: "--"

    /**
     * '17:32 초기화' / '내일 09:00 초기화' / '7/31 09:00 초기화' / '사용 전'.
     *
     * 남은 시간(2시간 07분 후)이 아니라 **절대 시각**을 쓴다. 위젯은 15분에 한 번만
     * 갱신되므로 상대 시간을 적으면 화면이 그새 틀려 버린다. 절대 시각은 안 틀린다.
     */
    fun whenText(now: Long): String {
        if (resetAt == null) return "사용 전"
        val at = Calendar.getInstance().apply { timeInMillis = resetAt }
        val today = Calendar.getInstance().apply { timeInMillis = now }
        val hm = String.format(
            Locale.KOREA, "%02d:%02d",
            at.get(Calendar.HOUR_OF_DAY), at.get(Calendar.MINUTE)
        )
        val days = dayDiff(today, at)
        val head = when {
            days <= 0L -> ""
            days == 1L -> "내일 "
            else -> "${at.get(Calendar.MONTH) + 1}/${at.get(Calendar.DAY_OF_MONTH)} "
        }
        return "$head$hm 초기화"
    }

    /** '2시간 07분 후' — 초 단위로 다시 그리는 배경화면에서만 쓴다. */
    fun leftText(now: Long): String {
        if (resetAt == null) return "사용 전"
        val secs = (resetAt - now) / 1000
        if (secs <= 0) return "곧 초기화"
        val mins = (secs / 60).toInt()
        return when {
            mins >= 1440 -> "${mins / 1440}일 ${(mins % 1440) / 60}시간 후"
            mins >= 60 -> String.format(Locale.KOREA, "%d시간 %02d분 후", mins / 60, mins % 60)
            else -> "${mins}분 후"
        }
    }

    private fun dayDiff(from: Calendar, to: Calendar): Long {
        val a = from.clone() as Calendar
        val b = to.clone() as Calendar
        for (c in listOf(a, b)) {
            c.set(Calendar.HOUR_OF_DAY, 0)
            c.set(Calendar.MINUTE, 0)
            c.set(Calendar.SECOND, 0)
            c.set(Calendar.MILLISECOND, 0)
        }
        return Math.round((b.timeInMillis - a.timeInMillis) / 86_400_000.0).toLong()
    }
}

/**
 * 한 번 읽어온 사용량 전체.
 *
 * @param updatedAt PC 가 마지막으로 올린 시각
 * @param stale     PC 가 20분 넘게 안 올렸다 (서버가 알려 준다) — 꺼져 있다는 뜻
 */
data class Snapshot(
    val five: Limit,
    val week: Limit,
    val updatedAt: Long,
    val stale: Boolean,
) {
    /** 지금 시각 기준으로 초기화를 반영한 값. 화면은 반드시 이걸 그린다. */
    fun settled(now: Long) = copy(five = five.settled(now), week = week.settled(now))

    /** 둘 중 더 급한 쪽 — 상태바 아이콘 숫자처럼 하나만 보여 줄 때. */
    fun worst(): Limit = if ((week.pct ?: -1f) > (five.pct ?: -1f)) week else five

    /**
     * 값이 오래됐으면 '얼마나 오래됐는지'. 안 오래됐으면 빈 문자열.
     *
     * 'PC 꺼짐' 이라고 단정하지 않는다 — PC 가 켜져 있어도 위젯이 안 떠 있거나
     * 보내기가 꺼져 있으면 똑같이 값이 안 올라온다. 원인을 짐작해 적으면
     * 오히려 엉뚱한 데를 보게 된다. 사실(몇 분 전 값인지)만 적는다.
     */
    fun ageText(now: Long): String {
        if (!stale || updatedAt == 0L) return ""
        val mins = ((now - updatedAt) / 60_000L).coerceAtLeast(0L)
        return when {
            mins >= 1440 -> "PC 값 ${mins / 1440}일 전"
            mins >= 60 -> "PC 값 ${mins / 60}시간 전"
            else -> "PC 값 ${mins}분 전"
        }
    }

    companion object {
        val EMPTY = Snapshot(Limit("5시간", null, null), Limit("주간", null, null), 0L, true)

        /** 릴레이 서버 응답(server/app/api/cooldown/route.ts 의 GET) 을 읽는다. */
        fun parse(body: String): Snapshot? = try {
            val o = JSONObject(body)
            val five = Limit("5시간", o.pct("five_hour_pct"), o.iso("five_hour_reset"))
            val week = Limit("주간", o.pct("seven_day_pct"), o.iso("seven_day_reset"))
            // 필드 이름만 바뀌어도 예외 없이 전부 null 이 된다 — 그건 고장이지 빈 값이 아니다
            if (five.pct == null && week.pct == null) null
            else Snapshot(
                five = five,
                week = week,
                updatedAt = o.iso("updated_at") ?: System.currentTimeMillis(),
                stale = o.optBoolean("stale", false),
            )
        } catch (e: Exception) {
            null
        }

        private fun JSONObject.pct(name: String): Float? {
            if (isNull(name)) return null
            val v = optDouble(name, Double.NaN)
            return if (v.isNaN()) null else v.toFloat().coerceIn(0f, 100f)
        }

        /** '2026-07-29T13:20:00+00:00' → epoch millis. 못 읽으면 null. */
        private fun JSONObject.iso(name: String): Long? {
            val raw = optString(name).takeIf { it.isNotEmpty() && it != "null" } ?: return null
            return parseIso(raw)
        }

        fun parseIso(raw: String): Long? = try {
            // API 26 이상이면 java.time 을 그대로 쓸 수 있다 (오프셋·Z 둘 다 처리)
            java.time.OffsetDateTime.parse(raw.replace(" ", "T")).toInstant().toEpochMilli()
        } catch (e: Exception) {
            try {
                java.time.LocalDateTime.parse(raw.replace(" ", "T"))
                    .toInstant(java.time.ZoneOffset.UTC).toEpochMilli()
            } catch (e2: Exception) {
                null
            }
        }
    }
}
