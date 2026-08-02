package com.kyijgnes.cooldown.widget

import android.content.Context
import android.graphics.Bitmap
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.Snapshot

/** 5시간·주간 두 줄 게이지. */
class WideWidget : BaseWidget() {
    override val fallbackDp = Pair(250, 70)

    /**
     * ★ **세로로 늘려도 게이지는 4×1 비율을 지킨다.** 칸 높이를 그대로 쓰면 4×2 에서
     * 글자·막대가 두 배로 부풀어 딴 위젯이 된다 — 남는 자리는 비워 두고 가운데 정렬한다
     * (판을 위젯 안에서 그리므로 위아래 여백은 투명하게 남는다).
     */
    override fun render(ctx: Context, wPx: Int, hPx: Int, snap: Snapshot, now: Long): Bitmap =
        GaugeRenderer.wide(
            ctx, wPx, minOf(hPx, (wPx * 0.30f).toInt()).coerceAtLeast(60), snap, now, card = false,
        )
}
