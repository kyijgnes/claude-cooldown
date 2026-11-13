package com.kyijgnes.cooldown.update

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequest
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import com.kyijgnes.cooldown.MainActivity
import com.kyijgnes.cooldown.R
import java.util.concurrent.TimeUnit

/**
 * 하루 한 번 새 버전을 묻고, 새로 나왔으면 **한 번만** 알린다(버전마다 한 번).
 * 알림을 누르면 앱이 열리면서 곧장 받기를 시작한다(`ACTION`).
 */
class UpdateWorker(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {

    override fun doWork(): Result {
        val ctx = applicationContext
        NewVersion.refresh(ctx, force = true)   // 못 물어도 조용히 넘어간다(다음 날 다시 온다)
        NewVersion.toNotify(ctx)?.let { ver ->
            notify(ctx, ver)
            NewVersion.markNotified(ctx, ver)
        }
        return Result.success()
    }

    companion object {
        const val ACTION = "com.kyijgnes.cooldown.UPDATE"
        private const val WORK = "cooldown-update-check"
        private const val CHANNEL = "update"
        private const val ID = 3

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequest.Builder(UpdateWorker::class.java, 24, TimeUnit.HOURS)
                .setConstraints(
                    Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
                )
                .build()
            WorkManager.getInstance(ctx)
                .enqueueUniquePeriodicWork(WORK, ExistingPeriodicWorkPolicy.KEEP, req)
        }

        /** 새 버전을 깔았거나 받기 시작했으면 알림을 거둔다. */
        fun clear(ctx: Context) {
            ctx.getSystemService(NotificationManager::class.java)?.cancel(ID)
        }

        private fun notify(ctx: Context, ver: String) {
            val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
            if (nm.getNotificationChannel(CHANNEL) == null) {
                nm.createNotificationChannel(
                    NotificationChannel(CHANNEL, "새 버전", NotificationManager.IMPORTANCE_DEFAULT)
                )
            }
            val open = PendingIntent.getActivity(
                ctx, ID,
                Intent(ctx, MainActivity::class.java)
                    .setAction(ACTION)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            val n = Notification.Builder(ctx, CHANNEL)
                .setSmallIcon(R.drawable.ic_launcher_mono)
                .setContentTitle("클로드 쿨다운 새 버전 $ver")
                .setContentText("눌러서 받기")
                .setContentIntent(open)
                .setAutoCancel(true)
                .build()
            try {
                nm.notify(ID, n)
            } catch (e: SecurityException) {
                // 알림 권한이 없으면 그만둔다(앱을 열면 첫 화면 단추로 보인다)
            }
        }
    }
}
