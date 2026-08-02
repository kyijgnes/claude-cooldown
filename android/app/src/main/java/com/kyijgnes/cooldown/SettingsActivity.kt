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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        pairHead = findViewById(R.id.pair_head)
        url = findViewById(R.id.url)
        key = findViewById(R.id.key)
        notify = findViewById(R.id.notify)

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
    }

    override fun onResume() {
        super.onResume()
        show()
    }

    private fun show() {
        // 지금 어떤 상태인지를 칸 이름에 그대로 적는다 (설명 문단 대신)
        pairHead.text = if (Store.paired(this)) "PC 연결됨" else "PC 연결 — 먼저 하세요"
        url.setText(Store.url(this))
        key.setText(Store.key(this))
        notify.isChecked = Store.notifyOn(this)
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
