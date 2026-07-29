package com.kyijgnes.cooldown

import android.content.Context

/**
 * 색 한 벌. values/colors.xml(밝게) 과 values-night/colors.xml(어둡게) 에서 오므로
 * 시스템 다크 모드를 그냥 따라간다.
 *
 * 임계값 50/80 은 데스크탑 위젯(skins/base.py tone)과 같다.
 */
class Palette(ctx: Context) {
    val bg = ctx.getColor(R.color.bg)
    val title = ctx.getColor(R.color.title)
    val label = ctx.getColor(R.color.label)
    val sub = ctx.getColor(R.color.sub)
    val faint = ctx.getColor(R.color.faint)
    val track = ctx.getColor(R.color.track)
    val line = ctx.getColor(R.color.line)
    val green = ctx.getColor(R.color.green)
    val amber = ctx.getColor(R.color.amber)
    val red = ctx.getColor(R.color.red)
    val coral = ctx.getColor(R.color.coral)

    /** 여유 초록 / 보통 노랑 / 임박 빨강. 값을 모르면 흐린 색. */
    fun tone(pct: Float?): Int = when {
        pct == null -> faint
        pct < 50f -> green
        pct < 80f -> amber
        else -> red
    }
}
