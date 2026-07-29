package com.kyijgnes.cooldown

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import com.kyijgnes.cooldown.notify.NotifyController
import com.kyijgnes.cooldown.widget.SmallWidget
import com.kyijgnes.cooldown.widget.WideWidget
import com.kyijgnes.cooldown.work.ResetAlarm

/**
 * 값을 가져오고, 모든 화면(홈 위젯·상태바 알림·라이브 배경화면)을 한 번에 다시 그린다.
 * 화면을 새로 만들면 여기 `renderAll` 에만 한 줄 더한다.
 */
object Refresher {

    /** 서버에 물어본다. **블로킹** — 반드시 백그라운드 스레드에서 부를 것. */
    fun refresh(ctx: Context): Boolean {
        val app = ctx.applicationContext
        if (!Store.paired(app)) {
            Store.saveError(app, "PC 연결 필요")
            renderAll(app)
            return false
        }
        val ok = when (val r = Relay.fetch(Store.url(app), Store.key(app))) {
            is Relay.Result.Ok -> {
                Store.save(app, r.snapshot)
                true
            }
            is Relay.Result.Err -> {
                // 값은 지우지 않는다 — 잠깐 안 될 때마다 숫자가 사라지면 정작 궁금한 걸 못 본다
                Store.saveError(app, r.text)
                false
            }
        }
        renderAll(app)
        ResetAlarm.schedule(app)
        return ok
    }

    /**
     * 저장된 값으로만 다시 그린다 (네트워크 없음). 초기화 시각이 지났을 때도 이걸 부른다.
     * 라이브 배경화면은 여기 없다 — 보이는 동안 스스로 매 프레임 다시 그린다.
     */
    fun renderAll(ctx: Context) {
        val app = ctx.applicationContext
        updateWidgets(app)
        NotifyController.update(app)
    }

    private fun updateWidgets(ctx: Context) {
        val mgr = AppWidgetManager.getInstance(ctx) ?: return
        for (cls in listOf(SmallWidget::class.java, WideWidget::class.java)) {
            val ids = try {
                mgr.getAppWidgetIds(ComponentName(ctx, cls))
            } catch (e: Exception) {
                continue
            }
            if (ids.isEmpty()) continue
            val provider = cls.getDeclaredConstructor().newInstance()
            ids.forEach { provider.draw(ctx, mgr, it) }
        }
    }
}
