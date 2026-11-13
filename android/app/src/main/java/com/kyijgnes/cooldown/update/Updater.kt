package com.kyijgnes.cooldown.update

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Toast
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 새 버전 APK 를 받아 **시스템 설치 화면을 바로 띄운다.**
 *
 * 1. 릴리스의 APK 를 `cacheDir/update/` 로 받는다(받은 게 있으면 다시 안 받는다).
 * 2. 받은 파일이 정말 이 앱의 더 높은 버전인지 확인한다(덜 받은 파일이면 설치 화면을 안 띄운다).
 * 3. 「출처를 알 수 없는 앱」 허용이 없으면 그 설정 화면으로 보내고, 돌아오면(`resume`) 이어서 깐다.
 * 4. 설치는 시스템이 사람에게 묻고 한다. 서명이 다르면 시스템이 거절한다.
 *
 * APK 가 릴리스에 없으면 릴리스 페이지를 브라우저로 연다(예전 방식).
 */
object Updater {

    /** 받는 중이면 0..100, 아니면 -1. 화면이 단추 글자에 쓴다. */
    @Volatile
    var progress: Int = -1
        private set

    private val running = AtomicBoolean(false)
    private val main = Handler(Looper.getMainLooper())

    /** 설정 화면(출처를 알 수 없는 앱)에 다녀오는 중. 돌아오면 한 번만 이어 간다. */
    private var awaitingPermission = false

    fun label(ver: String): String =
        if (progress >= 0) "새 버전 $ver 받는 중 $progress%" else "새 버전 $ver 받기"

    /** 단추를 눌렀다. `onChange` 는 단추 글자를 다시 그릴 때(메인 스레드) 부른다. */
    fun start(act: Activity, onChange: () -> Unit) {
        val app = act.applicationContext
        val ver = NewVersion.pending(app) ?: return
        ready(app)?.let {
            install(act, it)
            return
        }
        val url = NewVersion.apkUrl(app)
        if (url.isEmpty()) {
            openPage(act)
            return
        }
        if (!running.compareAndSet(false, true)) return
        progress = 0
        onChange()
        Thread {
            val f = download(app, url, File(ApkProvider.dir(app), "claude-cooldown-$ver.apk")) { p ->
                if (p != progress) {
                    progress = p
                    main.post(onChange)
                }
            }
            val ok = f != null && isUpgrade(app, f)
            if (f != null && !ok) f.delete()
            main.post {
                progress = -1
                running.set(false)
                onChange()
                when {
                    !ok -> Toast.makeText(app, "새 버전을 받지 못했어요", Toast.LENGTH_SHORT).show()
                    !act.isFinishing && !act.isDestroyed -> install(act, f!!)
                }
            }
        }.start()
    }

    /** 화면이 다시 보일 때(`onResume`). 설정에서 허용하고 돌아왔으면 설치를 이어 간다. */
    fun resume(act: Activity) {
        if (!awaitingPermission) return
        awaitingPermission = false
        if (!act.packageManager.canRequestPackageInstalls()) return   // 허용 안 함: 그만둔다
        ready(act.applicationContext)?.let { install(act, it) }
    }

    /** 새 버전이 없으면(이미 깔았으면) 받아 둔 파일을 지운다. 작업 스레드에서 불러도 된다. */
    fun cleanup(ctx: Context) {
        if (NewVersion.pending(ctx) != null || running.get()) return
        ApkProvider.dir(ctx).listFiles()?.forEach { it.delete() }
    }

    private fun install(act: Activity, f: File) {
        if (!act.packageManager.canRequestPackageInstalls()) {
            awaitingPermission = true
            try {
                act.startActivity(
                    Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${act.packageName}"))
                )
            } catch (e: Exception) {
                awaitingPermission = false
                openPage(act)
            }
            return
        }
        val i = Intent(Intent.ACTION_VIEW)
            .setDataAndType(ApkProvider.uriFor(act, f), ApkProvider.MIME)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        try {
            act.startActivity(i)
        } catch (e: Exception) {
            openPage(act)
        }
    }

    private fun openPage(act: Activity) {
        try {
            act.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(NewVersion.PAGE)))
        } catch (e: Exception) {
            Toast.makeText(act, "브라우저를 못 열었어요", Toast.LENGTH_SHORT).show()
        }
    }

    /** 받아 둔 새 버전 APK. 없거나 쓸 수 없으면 null. */
    private fun ready(ctx: Context): File? {
        val ver = NewVersion.pending(ctx) ?: return null
        val f = File(ApkProvider.dir(ctx), "claude-cooldown-$ver.apk")
        return if (f.isFile && isUpgrade(ctx, f)) f else null
    }

    /** 이 앱(같은 패키지)이고 지금 깔린 것보다 versionCode 가 높은가. 덜 받은 파일은 여기서 걸린다. */
    private fun isUpgrade(ctx: Context, f: File): Boolean = try {
        val pm = ctx.packageManager
        val apk = pm.getPackageArchiveInfo(f.path, 0)
        val mine = pm.getPackageInfo(ctx.packageName, 0)
        apk != null && apk.packageName == ctx.packageName && code(apk) > code(mine)
    } catch (e: Exception) {
        false
    }

    @Suppress("DEPRECATION")
    private fun code(p: android.content.pm.PackageInfo): Long =
        if (android.os.Build.VERSION.SDK_INT >= 28) p.longVersionCode else p.versionCode.toLong()

    /** 받아서 `target` 으로 옮긴다. 실패하면 null(반쯤 받은 파일은 남기지 않는다). */
    private fun download(ctx: Context, url: String, target: File, onPct: (Int) -> Unit): File? {
        val dir = target.parentFile ?: return null
        dir.mkdirs()
        dir.listFiles()?.forEach { it.delete() }   // 옛 버전 파일까지 비운다
        val part = File(dir, target.name + ".part")
        var conn: HttpURLConnection? = null
        return try {
            conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 15_000
                readTimeout = 30_000
                instanceFollowRedirects = true   // github.com → objects.githubusercontent.com
                setRequestProperty("User-Agent", "claude-cooldown")
            }
            if (conn.responseCode != 200) return null
            val total = conn.contentLengthLong
            var got = 0L
            conn.inputStream.use { input ->
                part.outputStream().use { out ->
                    val buf = ByteArray(64 * 1024)
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        got += n
                        if (total > 0) onPct((got * 100 / total).toInt().coerceIn(0, 100))
                    }
                }
            }
            if (total > 0 && got != total) return null
            if (!part.renameTo(target)) return null
            target
        } catch (e: Exception) {
            null
        } finally {
            conn?.disconnect()
            if (part.exists()) part.delete()
        }
    }
}
