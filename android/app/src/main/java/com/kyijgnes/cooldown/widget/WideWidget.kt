package com.kyijgnes.cooldown.widget

import android.content.Context
import android.graphics.Bitmap
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.Snapshot

/** 5시간·주간 두 줄 게이지. */
class WideWidget : BaseWidget() {
    override val fallbackDp = Pair(250, 70)

    override fun render(ctx: Context, wPx: Int, hPx: Int, snap: Snapshot, now: Long): Bitmap =
        GaugeRenderer.wide(ctx, wPx, hPx, snap, now, card = false)
}
