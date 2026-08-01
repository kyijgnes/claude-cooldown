package com.kyijgnes.cooldown.notify

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.os.Build
import com.kyijgnes.cooldown.GaugeRenderer
import com.kyijgnes.cooldown.MainActivity
import com.kyijgnes.cooldown.Palette
import com.kyijgnes.cooldown.R
import com.kyijgnes.cooldown.Snapshot
import com.kyijgnes.cooldown.Store

/**
 * 상태바·잠금화면·AOD 에 늘 떠 있는 알림.
 *
 * 세 가지가 한 알림으로 해결된다:
 *   · **상태바** — 작은 아이콘에 숫자를 그려 넣는다 (배터리 % 처럼 보인다)
 *   · **잠금화면** — VISIBILITY_PUBLIC 이라 내용까지 보인다
 *   · **AOD / Now Bar** — 안드로이드 16 의 라이브 업데이트로 승격되면 펼쳐서 표시된다
 *
 * 남은 시간은 **크로노미터**에 맡긴다 (setUsesChronometer + setChronometerCountDown).
 * 시스템이 1초마다 스스로 줄여 주므로 우리가 주기적으로 다시 그릴 필요가 없다 —
 * 배터리를 안 쓰면서도 화면은 늘 맞다.
 */
object NotifyController {
    private const val CHANNEL = "cooldown"
    private const val ID = 1

    /** 옛 판에서 잠깐 썼던 '상태바 없이' 채널 — 지우고 다닌다(안 지우면 설정에 남는다). */
    private const val CHANNEL_DEAD = "cooldown_quiet"
    private const val ID_DEAD = 2

    fun update(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        nm.cancel(ID_DEAD)
        nm.deleteNotificationChannel(CHANNEL_DEAD)
        if (!Store.notifyOn(ctx)) {
            nm.cancel(ID)
            return
        }
        ensureChannel(ctx, nm)

        val now = System.currentTimeMillis()
        val snap = Store.snapshot(ctx).settled(now)
        val p = Palette(ctx)
        val five = snap.five
        val week = snap.week

        val open = PendingIntent.getActivity(
            ctx, 0,
            Intent(ctx, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val b = Notification.Builder(ctx, CHANNEL)
            .setSmallIcon(Icon.createWithBitmap(GaugeRenderer.statusIcon(five.pct)))
            .setContentTitle("5시간 ${five.pctText()}   주간 ${week.pctText()}")
            .setContentText(bodyText(snap, now))
            .setContentIntent(open)
            .setOngoing(true)
            .setShowWhen(false)
            .setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_PROGRESS)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setColor(p.tone(five.pct))

        // 초기화까지 남은 시간은 시스템이 세게 한다 (창이 있을 때만)
        five.resetAt?.let {
            b.setWhen(it).setShowWhen(true).setUsesChronometer(true).setChronometerCountDown(true)
        }

        val pct = five.pct?.let { Math.round(it) } ?: 0
        if (Build.VERSION.SDK_INT >= 36) {
            // 안드로이드 16 라이브 업데이트 — 진행바가 있어야 상태바 칩·AOD·Now Bar 로 승격된다
            b.setStyle(
                Notification.ProgressStyle()
                    .setProgress(pct)
                    .setProgressSegments(
                        listOf(Notification.ProgressStyle.Segment(100).setColor(p.tone(five.pct)))
                    )
            )
            // 상태바 칩에 들어가는 짧은 글 — 좁으니 숫자만
            b.setShortCriticalText(five.pctText())
            requestPromotion(b)
        } else {
            // 그 아래 버전엔 승격이 없다. 상태바는 숫자 아이콘, 알림은 옛 진행바로.
            b.setProgress(100, pct, false)
        }

        nm.notify(ID, b.build())
    }

    fun cancel(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        nm.cancel(ID)
        nm.cancel(ID_DEAD)
    }

    /** 지금 기기가 라이브 업데이트(상태바 칩·AOD)를 띄워 줄 수 있는가. */
    fun canPromote(ctx: Context): Boolean {
        if (Build.VERSION.SDK_INT < 36) return false
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return false
        return nm.canPostPromotedNotifications()
    }

    private fun bodyText(snap: Snapshot, now: Long): String {
        if (snap.updatedAt == 0L) return "PC 연결 필요"
        val base = "주간 ${snap.week.whenText(now)}"
        val age = snap.ageText(now)
        return if (age.isEmpty()) base else "$base · $age"
    }

    /**
     * 안드로이드 16.0 에는 '승격해 달라'고 **직접 요청하는 API 가 없다** — 진행바가 있는
     * 상시 알림이면 시스템이 알아서 올린다. 그 뒤 버전에서 생긴
     * `requestPromotedOngoing()` 은 있으면 쓰도록 리플렉션으로 부른다
     * (compileSdk 를 올리지 않고도 새 기기에서 확실히 승격되게).
     */
    private fun requestPromotion(b: Notification.Builder) {
        if (Build.VERSION.SDK_INT < 36) return
        try {
            val m = Notification.Builder::class.java
                .getMethod("requestPromotedOngoing", Boolean::class.javaPrimitiveType)
            m.invoke(b, true)
        } catch (e: Exception) {
            // 이 버전엔 없다 — 자동 승격에 맡긴다
        }
    }

    private fun ensureChannel(ctx: Context, nm: NotificationManager) {
        if (nm.getNotificationChannel(CHANNEL) != null) return
        val ch = NotificationChannel(
            CHANNEL,
            ctx.getString(R.string.channel_name),
            // 조용해야 하지만 너무 낮으면 상태바·잠금화면에서 접힌다 — 소리만 끈다.
            // ★ MIN 으로 내리지 말 것 — 삼성 잠금화면·AOD 에서도 통째로 사라진다(실기 확인).
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            setSound(null, null)
            enableVibration(false)
            enableLights(false)
            setShowBadge(false)
            lockscreenVisibility = Notification.VISIBILITY_PUBLIC
        }
        nm.createNotificationChannel(ch)
    }
}
