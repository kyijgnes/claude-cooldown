package com.kyijgnes.cooldown.widget

import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.Snapshot

/**
 * 5시간·주간 두 줄 게이지 + 오른쪽 끝 클로디 칸.
 * 클로디를 톡톡 하면 뻗고 곁에 공룡알 → 알을 깨면 위젯 자리가 공룡 점프 판이 된다(`WidgetClaudi`).
 */
class WideWidget : BaseWidget() {
    override val fallbackDp = Pair(250, 70)
    override val layout = R.layout.widget_wide
    override val claudiDp = 64

    /**
     * ★ **세로로 늘려도 게이지는 4×1 비율을 지킨다.** 칸 높이를 그대로 쓰면 4×2 에서
     * 글자·막대가 두 배로 부풀어 딴 위젯이 된다 — 남는 자리는 비워 두고 가운데 정렬한다
     * (판을 위젯 안에서 그리므로 위아래 여백은 투명하게 남는다).
     */
    override fun render(ctx: Context, wPx: Int, hPx: Int, snap: Snapshot, now: Long): Bitmap =
        GaugeRenderer.wide(
            ctx, wPx, minOf(hPx, (wPx * 0.30f).toInt()).coerceAtLeast(60), snap, now, card = false,
        )

    /** 클로디 칸을 누른 방송 — 한 장 다시 그린다. 그 밖은 여느 위젯처럼. */
    override fun onReceive(ctx: Context, intent: Intent) {
        if (intent.action == WidgetClaudi.ACTION_TAP) {
            val id = intent.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID)
            if (id != AppWidgetManager.INVALID_APPWIDGET_ID) {
                WidgetClaudi.tap(ctx, id)
                draw(ctx, AppWidgetManager.getInstance(ctx), id)
            }
            return
        }
        super.onReceive(ctx, intent)
    }
}
