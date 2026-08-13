package com.kyijgnes.cooldown

import android.Manifest
import android.app.Activity
import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.CompoundButton
import android.widget.EditText
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.kyijgnes.cooldown.notify.NotifyController
import com.kyijgnes.cooldown.widget.WideWidget

/**
 * 옵션 — PC 연결과 표시 설정. 홈은 지금 값만 보여 주고, 손댈 것은 전부 여기 있다.
 *
 * **PC 연결이 맨 위**다. 연결이 안 돼 있으면 나머지가 다 소용없기 때문이고,
 * 홈에서도 연결 전에는 [PC 연결하기] 가 이 화면으로 곧장 보낸다.
 */
class SettingsActivity : Activity() {

    private lateinit var pairHead: TextView
    private lateinit var url: EditText
    private lateinit var key: EditText
    private lateinit var notify: Switch
    private lateinit var remote: Switch
    private lateinit var remoteState: TextView
    // 화면이 보여 주고 있는 값으로 스위치를 맞출 때는 리스너가 돌면 안 된다 —
    // 안 그러면 '읽어서 맞춘 것' 이 '사람이 누른 것' 으로 처리돼 서버에 도로 쓴다.
    private var remoteQuiet = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        pairHead = findViewById(R.id.pair_head)
        url = findViewById(R.id.url)
        key = findViewById(R.id.key)
        notify = findViewById(R.id.notify)
        remote = findViewById(R.id.remote)
        remoteState = findViewById(R.id.remote_state)

        findViewById<Button>(R.id.scan).setOnClickListener { scan() }
        findViewById<Button>(R.id.save).setOnClickListener { save() }
        // 배경화면은 꾸미기 화면 하나로 간다 — 거기서 모양을 보고 저장하면 그때 실제로 걸린다
        findViewById<Button>(R.id.wallpaper).setOnClickListener {
            startActivity(Intent(this, CustomizeActivity::class.java))
        }
        findViewById<Button>(R.id.widget).setOnClickListener { pinWidget() }

        notify.setOnCheckedChangeListener { _: CompoundButton, on: Boolean ->
            Store.setNotifyOn(this, on)
            if (on) askNotificationPermission()
            NotifyController.update(this)
        }

        remote.setOnCheckedChangeListener { _: CompoundButton, on: Boolean ->
            if (remoteQuiet) return@setOnCheckedChangeListener
            setRemote(on)
        }
    }

    override fun onResume() {
        super.onResume()
        show()
        askRemote()
    }

    private fun show() {
        // 지금 어떤 상태인지를 칸 이름에 그대로 적는다 (설명 문단 대신)
        pairHead.text = if (Store.paired(this)) "PC 연결됨" else "PC 연결 — 먼저 하세요"
        url.setText(Store.url(this))
        key.setText(Store.key(this))
        notify.isChecked = Store.notifyOn(this)
    }

    // ---------------------------------------------------------------- 클로드 코드 원격

    /**
     * PC 위젯이 `claude rc` 를 들고 있어야 폰에서 새 세션이 열린다. 그걸 여기서 켜고 끈다.
     *
     * ★ **곧바로 켜지지 않는다** — 우리는 릴레이에 '이렇게 해 달라' 를 적어 둘 뿐이고,
     *   PC 위젯이 2분마다 그걸 읽어 따라간다. 그래서 누른 직후 상태 줄은 `PC 에 전하는 중`
     *   이고, 실제로 켜지면 그때 `PC 대기 중` 으로 바뀐다. 거짓말을 하지 않으려는 것이다.
     */
    private fun setRemote(on: Boolean) {
        val base = Store.url(this)
        val k = Store.key(this)
        if (base.isEmpty() || k.length != 32) {
            toast("PC 연결을 먼저 하세요")
            showRemote(null, sending = false)
            return
        }
        showRemote(null, sending = true)
        Thread {
            val ok = RemoteRelay.setWant(base, k, on)
            runOnUiThread { if (!ok) toast("PC 에 전하지 못했어요") }
            if (ok) askRemote()
        }.start()
    }

    /** 릴레이에서 지금 상태를 읽어 스위치·상태 줄을 맞춘다. */
    private fun askRemote() {
        val base = Store.url(this)
        val k = Store.key(this)
        if (base.isEmpty() || k.length != 32) {
            showRemote(null, sending = false)
            return
        }
        Thread {
            val st = RemoteRelay.fetch(base, k)
            runOnUiThread { showRemote(st, sending = false) }
        }.start()
    }

    private fun showRemote(st: RemoteRelay.Status?, sending: Boolean) {
        remoteQuiet = true
        remote.isChecked = st?.want == "on"
        remoteQuiet = false

        // 상태 줄은 **한 줄 명사형**. 무엇이 잘못됐나가 아니라 지금 어떤가를 적는다.
        remoteState.text = when {
            sending -> "PC 에 전하는 중"
            st == null -> if (Store.paired(this)) "PC 상태 모름" else "PC 연결 — 먼저 하세요"
            st.state == "fail" -> "PC 에서 못 켰어요"
            st.stale -> "PC 응답 없음 (위젯 꺼짐)"
            st.state == "on" -> "PC 대기 중"
            st.want == "on" -> "PC 에 전하는 중"  // 원하는 건 켜기인데 PC 가 아직 안 따라왔다
            else -> "PC 꺼둠"
        }
    }

    // ---------------------------------------------------------------- PC 연결

    private fun save() {
        val u = Store.normalizeUrl(url.text.toString())
        val k = key.text.toString().trim()
        if (u.isEmpty()) {
            toast("서버 주소를 알아볼 수 없어요")
            return
        }
        if (k.length != 32) {
            toast("키는 32자리예요")
            return
        }
        Store.setPair(this, u, k)
        show()
        refresh()
    }

    private fun scan() {
        val options = GmsBarcodeScannerOptions.Builder()
            .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
            .build()
        GmsBarcodeScanning.getClient(this, options).startScan()
            .addOnSuccessListener { code ->
                val raw = code.rawValue ?: return@addOnSuccessListener
                if (Store.applyPairUri(this, android.net.Uri.parse(raw))) {
                    show()
                    refresh()
                } else {
                    toast("클로드 쿨다운 QR 이 아니에요")
                }
            }
            .addOnFailureListener { toast("QR 을 못 읽었어요 — 아래에 직접 넣어 주세요") }
    }

    private fun refresh() {
        Thread { Refresher.refresh(this) }.start()
    }

    // ---------------------------------------------------------------- 위젯 넣기

    /**
     * **홈 화면에 위젯을 바로 얹어 준다** — 런처가 '추가할까요?' 를 물어보는 화면을 띄운다.
     * 홈 화면을 길게 눌러 위젯 목록에서 찾는 길을 안내 문구로 적는 대신 버튼 하나로 만든다.
     * 넣어 주는 건 넓은 게이지(4×1). 작은 것은 위젯 목록에 그대로 있다.
     */
    private fun pinWidget() {
        val mgr = getSystemService(AppWidgetManager::class.java)
        val wide = ComponentName(this, WideWidget::class.java)
        if (mgr != null && mgr.isRequestPinAppWidgetSupported) {
            mgr.requestPinAppWidget(wide, null, null)
        } else {
            toast("이 런처는 바로 넣기를 지원하지 않아요")
        }
    }

    // ---------------------------------------------------------------- 권한

    private fun askNotificationPermission() {
        if (Build.VERSION.SDK_INT < 33) return
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
            == PackageManager.PERMISSION_GRANTED
        ) return
        requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        NotifyController.update(this)
        show()
    }

    private fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()
}
