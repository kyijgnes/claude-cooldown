package com.kyijgnes.cooldown.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Bundle
import android.widget.RemoteViews
import com.kyijgnes.cooldown.MainActivity
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.Snapshot
import com.kyijgnes.cooldown.Store

/**
 * 홈 위젯 공통. 내용은 그림 한 장이라 위젯마다 `render` 만 다르다.
 * 넓은 위젯은 오른쪽 끝에 **클로디 칸**이 하나 더 있다(`claudiDp`, 공룡 점프로 가는 문 — `WidgetClaudi`).
 *
 * 남은 시간을 '2시간 07분 후' 로 적지 않고 **초기화 시각**으로 적는 이유:
 * 위젯은 길면 30분에 한 번 갱신되므로 상대 시간은 금방 틀린 값이 된다.
 */
abstract class BaseWidget : AppWidgetProvider() {

    /** 이 위젯이 그리는 그림. */
    abstract fun render(ctx: Context, wPx: Int, hPx: Int, snap: Snapshot, now: Long): Bitmap

    /** 위젯 칸이 이 dp 보다 작다고 나오면 이 값을 쓴다 (처음 놓았을 때 0 이 온다). */
    protected abstract val fallbackDp: Pair<Int, Int>

    /** 위젯 틀. 넓은 위젯은 오른쪽에 클로디 칸이 있는 틀을 쓴다. */
    protected open val layout: Int = R.layout.widget

    /** 오른쪽 클로디 칸 폭(dp, 틀의 `@id/claudi` 와 같게). 0 이면 클로디가 없다(작은 위젯). */
    protected open val claudiDp: Int = 0

    override fun onUpdate(ctx: Context, mgr: AppWidgetManager, ids: IntArray) {
        ids.forEach { draw(ctx, mgr, it) }
    }

    override fun onAppWidgetOptionsChanged(
        ctx: Context,
        mgr: AppWidgetManager,
        id: Int,
        newOptions: Bundle?,
    ) {
        draw(ctx, mgr, id)
    }

    fun draw(ctx: Context, mgr: AppWidgetManager, id: Int) {
        val (wDp, hDp) = sizeDp(mgr, id)
        val density = ctx.resources.displayMetrics.density
        var wPx = ((wDp - claudiDp) * density).toInt().coerceIn(72, 1440)
        var hPx = (hDp * density).toInt().coerceIn(72, 720)
        var slotPx = (claudiDp * density).toInt()

        // ★★ **그림이 크면 위젯이 통째로 빈 칸이 된다.** RemoteViews 로 넘길 수 있는 양이
        //   1MB 남짓이라, 4×1 을 4×2 로 늘리면(가로 960 × 세로 450 = 1.7MB) `updateAppWidget`
        //   이 거부당한다 — 예전엔 그 예외를 조용히 삼켜서 **미터기가 사라진 것처럼** 보였다.
        //   그래서 넓이×높이 총량을 먼저 줄인다(클로디 칸까지 합쳐서). 비율은 그대로라 `fitCenter` 로 다시 커진다.
        val over = (wPx + slotPx).toLong() * hPx / MAX_PIXELS.toDouble()
        if (over > 1.0) {
            val k = kotlin.math.sqrt(over)
            wPx = (wPx / k).toInt().coerceAtLeast(72)
            hPx = (hPx / k).toInt().coerceAtLeast(72)
            slotPx = (slotPx / k).toInt()
        }

        val now = System.currentTimeMillis()
        val snap = Store.snapshot(ctx).settled(now)
        val views = RemoteViews(ctx.packageName, layout)
        views.setImageViewBitmap(R.id.canvas, render(ctx, wPx, hPx, snap, now))
        views.setOnClickPendingIntent(R.id.canvas, openApp(ctx))
        if (claudiDp > 0 && slotPx > 0) {
            // 클로디는 게이지와 같은 높이에 선다 (넓은 위젯은 세로로 늘려도 게이지가 4×1 비율이다)
            val slotH = minOf(hPx, (wPx * 0.30f).toInt()).coerceAtLeast(60)
            val state = WidgetClaudi.read(ctx, id, now)
            views.setImageViewBitmap(R.id.claudi, WidgetClaudi.bitmap(ctx, slotPx, slotH, state))
            views.setOnClickPendingIntent(R.id.claudi, WidgetClaudi.tapIntent(ctx, id, state))
        }
        try {
            mgr.updateAppWidget(id, views)
        } catch (e: Exception) {
            // 그래도 거부당하면 까닭을 남긴다 — 조용히 삼키면 '미터기가 없어졌다'로만 보인다
            android.util.Log.w(TAG, "위젯 그림을 못 넘겼다 (${wPx}x$hPx): $e")
        }
    }

    private fun sizeDp(mgr: AppWidgetManager, id: Int): Pair<Int, Int> {
        val o = try {
            mgr.getAppWidgetOptions(id)
        } catch (e: Exception) {
            null
        }
        val w = o?.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 0) ?: 0
        val h = o?.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0) ?: 0
        return Pair(
            if (w > 0) w else fallbackDp.first,
            if (h > 0) h else fallbackDp.second,
        )
    }

    private companion object {
        const val TAG = "cooldown-widget"

        /** 한 장에 담을 수 있는 점 수. ARGB 4바이트라 230,000 점 ≒ 900KB (한계는 1MB 남짓). */
        const val MAX_PIXELS = 230_000
    }

    private fun openApp(ctx: Context): PendingIntent = PendingIntent.getActivity(
        ctx, 0,
        Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )
}
