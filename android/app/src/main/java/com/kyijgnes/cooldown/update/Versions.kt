package com.kyijgnes.cooldown.update

/**
 * 버전 번호 다루기 — 안드로이드를 안 쓰는 순수 함수만 둔다(`VersionsTest` 가 그대로 시험한다).
 */
object Versions {

    /** 태그 `v0.46` → `0.46`. 앞의 v 만 깎는다. */
    fun fromTag(tag: String): String = tag.trim().trimStart('v', 'V')

    /**
     * `latest` 가 `mine` 보다 새로우면 true. 숫자 마디끼리 차례로 비교한다(`0.10` > `0.9`).
     * 모자란 마디는 0 으로 친다(`0.45` = `0.45.0`). 어느 쪽이든 비었거나 숫자가 없으면 false
     * (모르면 업데이트하라고 하지 않는다).
     */
    fun isNewer(latest: String, mine: String): Boolean {
        val a = parts(latest)
        val b = parts(mine)
        if (a.isEmpty() || b.isEmpty()) return false
        for (i in 0 until maxOf(a.size, b.size)) {
            val x = a.getOrElse(i) { 0 }
            val y = b.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    /**
     * 릴리스 자산(이름, 받는 주소) 가운데 폰에 깔 APK 하나를 고른다.
     * 워크플로가 붙이는 `claude-cooldown-v0.46.apk` 를 먼저, 없으면 아무 `.apk`. 없으면 null.
     */
    fun pickApk(assets: List<Pair<String, String>>): String? {
        val apks = assets.filter { it.first.endsWith(".apk", ignoreCase = true) && it.second.startsWith("https://") }
        return (apks.firstOrNull { it.first.startsWith("claude-cooldown", ignoreCase = true) } ?: apks.firstOrNull())
            ?.second
    }

    private fun parts(v: String): List<Int> =
        Regex("\\d+").findAll(v).mapNotNull { it.value.toIntOrNull() }.toList()
}
