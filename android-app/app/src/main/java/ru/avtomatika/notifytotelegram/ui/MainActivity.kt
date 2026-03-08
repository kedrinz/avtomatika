package ru.avtomatika.notifytotelegram.ui

import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.core.content.ContextCompat
import android.text.TextUtils
import android.view.WindowManager
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import com.google.android.material.button.MaterialButton
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import ru.avtomatika.notifytotelegram.R
import ru.avtomatika.notifytotelegram.data.Settings
import ru.avtomatika.notifytotelegram.service.NotificationSender

class MainActivity : AppCompatActivity() {

    private lateinit var settings: Settings
    private lateinit var etServerUrl: TextInputEditText
    private lateinit var etDeviceToken: TextInputEditText
    private lateinit var etPackage: TextInputEditText
    private lateinit var etSender: TextInputEditText
    private lateinit var listPackages: LinearLayout
    private lateinit var listSenders: LinearLayout
    private lateinit var statusListener: android.widget.TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        settings = Settings(this)
        etServerUrl = findViewById(R.id.etServerUrl)
        etDeviceToken = findViewById(R.id.etDeviceToken)
        etPackage = findViewById(R.id.etPackage)
        etSender = findViewById(R.id.etSender)
        listPackages = findViewById(R.id.listPackages)
        listSenders = findViewById(R.id.listSenders)
        statusListener = findViewById(R.id.statusListener)
        loadConfig()
        ensureDefaultPackage()
        refreshPackageList()
        refreshSenderList()
        updateListenerStatus()
        findViewById<MaterialButton>(R.id.btnEnableListener).setOnClickListener { openListenerSettings() }
        findViewById<MaterialButton>(R.id.btnAppDetails).setOnClickListener { openAppDetailsSettings() }
        findViewById<MaterialButton>(R.id.btnBattery).setOnClickListener { openBatterySettings() }
        findViewById<MaterialButton>(R.id.btnSaveConfig).setOnClickListener { saveConfig() }
        findViewById<MaterialButton>(R.id.btnScanQr).setOnClickListener { scanQr() }
        findViewById<MaterialButton>(R.id.btnAddPackage).setOnClickListener { addPackage() }
        findViewById<MaterialButton>(R.id.btnAddSender).setOnClickListener { addSender() }
        val switchKeepScreenOn = findViewById<SwitchCompat>(R.id.switchKeepScreenOn)
        switchKeepScreenOn.isChecked = settings.getKeepScreenOn()
        switchKeepScreenOn.setOnCheckedChangeListener { _, isChecked ->
            settings.setKeepScreenOn(isChecked)
            applyKeepScreenOn(isChecked)
        }
    }

    override fun onResume() {
        super.onResume()
        updateListenerStatus()
        applyKeepScreenOn(settings.getKeepScreenOn())
        // Если настройки сохранены — пинг, чтобы устройство отображалось онлайн в боте
        val url = settings.getServerUrl()
        val token = settings.getDeviceToken()
        if (url.isNotBlank() && token.isNotBlank() && (url.startsWith("http://") || url.startsWith("https://"))) {
            pingServer(url, token, showToast = false)
        }
    }

    private fun applyKeepScreenOn(enable: Boolean) {
        if (enable) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private val qrLauncher = registerForActivityResult(ScanContract()) { result ->
        if (result.contents == null) return@registerForActivityResult
        val parts = result.contents.split("\n")
        if (parts.size >= 3 && parts[0].trim().equals("EVATEAM", ignoreCase = true)) {
            val url = parts[1].trim()
            val token = parts[2].trim()
            if (url.isNotBlank() && token.isNotBlank()) {
                settings.setServerUrl(url)
                settings.setDeviceToken(token)
                etServerUrl.setText(url)
                etDeviceToken.setText(token)
                Toast.makeText(this, getString(R.string.toast_qr_saved), Toast.LENGTH_SHORT).show()
                pingServer(url, token)
            } else {
                Toast.makeText(this, getString(R.string.toast_qr_invalid), Toast.LENGTH_SHORT).show()
            }
        } else {
            Toast.makeText(this, getString(R.string.toast_qr_invalid), Toast.LENGTH_SHORT).show()
        }
    }

    private val requestCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) launchQrScanner() else Toast.makeText(this, "Нужен доступ к камере для сканирования", Toast.LENGTH_SHORT).show()
    }

    private fun scanQr() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M &&
            ContextCompat.checkSelfPermission(this, android.Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestCamera.launch(android.Manifest.permission.CAMERA)
            return
        }
        launchQrScanner()
    }

    private fun launchQrScanner() {
        qrLauncher.launch(
            ScanOptions().setPrompt(getString(R.string.step2_scan_qr)).setBeepEnabled(true)
        )
    }

    /** В фоне отправляет пинг на сервер, чтобы в боте устройство отобразилось как «подключено». */
    private fun pingServer(serverUrl: String, deviceToken: String, showToast: Boolean = true) {
        Thread {
            try {
                NotificationSender(this).ping(serverUrl, deviceToken)
                if (showToast) {
                    runOnUiThread {
                        Toast.makeText(this, getString(R.string.toast_ping_ok), Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                if (showToast) {
                    runOnUiThread {
                        Toast.makeText(this, getString(R.string.toast_ping_fail), Toast.LENGTH_LONG).show()
                    }
                }
            }
        }.start()
    }


    private fun updateListenerStatus() {
        val enabled = isNotificationServiceEnabled()
        statusListener.text = if (enabled) getString(R.string.step1_status_on) else getString(R.string.step1_status_off)
        statusListener.setTextColor(
            if (enabled) getColor(android.R.color.holo_green_dark)
            else getColor(android.R.color.holo_red_dark)
        )
    }

    private fun isNotificationServiceEnabled(): Boolean {
        val pkg = packageName
        val flat = android.provider.Settings.Secure.getString(
            contentResolver,
            "enabled_notification_listeners"
        ) ?: return false
        for (part in flat.split(":")) {
            val cn = ComponentName.unflattenFromString(part) ?: continue
            if (cn.packageName == pkg) return true
        }
        return false
    }

    private fun openListenerSettings() {
        try {
            startActivity(Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            MaterialAlertDialogBuilder(this)
                .setTitle(getString(R.string.step1_dialog_all_notifications_title))
                .setMessage(getString(R.string.step1_dialog_all_notifications_message))
                .setPositiveButton(android.R.string.ok, null)
                .show()
        } catch (_: Exception) {
            Toast.makeText(this, "Не удалось открыть настройки", Toast.LENGTH_SHORT).show()
        }
    }

    /** Открывает экран «О приложении» в настройках системы — там на многих телефонах есть меню ⋮ с пунктом «Доступ ко всем уведомлениям». */
    private fun openAppDetailsSettings() {
        try {
            val intent = Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:$packageName")
            }
            startActivity(intent)
            Toast.makeText(this, "В правом верхнем углу нажмите ⋮ (три точки)", Toast.LENGTH_LONG).show()
        } catch (_: Exception) {
            Toast.makeText(this, "Не удалось открыть настройки приложения", Toast.LENGTH_SHORT).show()
        }
    }

    private fun openBatterySettings() {
        try {
            val intent = Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = Uri.parse("package:$packageName")
            }
            startActivity(intent)
            Toast.makeText(this, "Откройте настройки. Выберите EVATEAM и разрешите работу в фоне (отключите оптимизацию батареи).", Toast.LENGTH_LONG).show()
        } catch (_: Exception) {
            try {
                startActivity(Intent(android.provider.Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                Toast.makeText(this, "Откройте настройки батареи и отключите оптимизацию для EVATEAM.", Toast.LENGTH_LONG).show()
            } catch (_: Exception) {
                Toast.makeText(this, "Откройте настройки батареи и отключите оптимизацию для EVATEAM", Toast.LENGTH_LONG).show()
            }
        }
    }

    /** По умолчанию добавляем приложение «Сообщения» для SMS, если список пуст. */
    private fun ensureDefaultPackage() {
        if (settings.getMonitoredPackages().isEmpty()) {
            settings.addMonitoredPackage("com.google.android.apps.messaging")
        }
    }

    private fun loadConfig() {
        etServerUrl.setText(settings.getServerUrl())
        etDeviceToken.setText(settings.getDeviceToken())
    }

    private fun saveConfig() {
        val url = etServerUrl.text?.toString()?.trim() ?: ""
        val token = etDeviceToken.text?.toString()?.trim() ?: ""
        when {
            url.isBlank() -> {
                Toast.makeText(this, getString(R.string.toast_enter_url), Toast.LENGTH_SHORT).show()
                return
            }
            !url.startsWith("http://") && !url.startsWith("https://") -> {
                Toast.makeText(this, getString(R.string.toast_bad_url), Toast.LENGTH_SHORT).show()
                return
            }
            token.isBlank() -> {
                Toast.makeText(this, getString(R.string.toast_enter_token), Toast.LENGTH_SHORT).show()
                return
            }
        }
        settings.setServerUrl(url)
        settings.setDeviceToken(token)
        Toast.makeText(this, getString(R.string.toast_saved), Toast.LENGTH_SHORT).show()
        pingServer(url, token)
    }

    private fun addPackage() {
        val pkg = etPackage.text?.toString()?.trim() ?: ""
        if (pkg.isBlank()) {
            Toast.makeText(this, getString(R.string.toast_enter_package), Toast.LENGTH_SHORT).show()
            return
        }
        settings.addMonitoredPackage(pkg)
        etPackage.text?.clear()
        refreshPackageList()
        Toast.makeText(this, "Добавлено: $pkg", Toast.LENGTH_SHORT).show()
    }

    private fun refreshPackageList() {
        listPackages.removeAllViews()
        for (pkg in settings.getMonitoredPackages().sorted()) {
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                setPadding(0, resources.getDimensionPixelSize(R.dimen.list_item_margin), 0, resources.getDimensionPixelSize(R.dimen.list_item_margin))
            }
            val label = android.widget.TextView(this).apply {
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply {
                    setMargins(0, 0, 8, 0)
                }
                setText(pkg)
                setSingleLine()
                ellipsize = TextUtils.TruncateAt.MIDDLE
            }
            val removeBtn = MaterialButton(this).apply {
                setText("✕")
                setOnClickListener { removePackage(pkg) }
            }
            row.addView(label)
            row.addView(removeBtn)
            listPackages.addView(row)
        }
    }

    private fun removePackage(pkg: String) {
        MaterialAlertDialogBuilder(this)
            .setTitle(getString(R.string.dialog_remove))
            .setMessage(pkg)
            .setPositiveButton(getString(R.string.btn_remove)) { _, _ ->
                settings.removeMonitoredPackage(pkg)
                refreshPackageList()
            }
            .setNegativeButton(getString(R.string.btn_cancel), null)
            .show()
    }

    private fun addSender() {
        val s = etSender.text?.toString()?.trim() ?: ""
        if (s.isBlank()) {
            Toast.makeText(this, getString(R.string.toast_enter_sender), Toast.LENGTH_SHORT).show()
            return
        }
        settings.addAllowedSender(s)
        etSender.text?.clear()
        refreshSenderList()
        Toast.makeText(this, "Добавлено: $s", Toast.LENGTH_SHORT).show()
    }

    private fun refreshSenderList() {
        listSenders.removeAllViews()
        for (s in settings.getAllowedSenders().sorted()) {
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                setPadding(0, resources.getDimensionPixelSize(R.dimen.list_item_margin), 0, resources.getDimensionPixelSize(R.dimen.list_item_margin))
            }
            val label = android.widget.TextView(this).apply {
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { setMargins(0, 0, 8, 0) }
                setText(s)
                setSingleLine()
                ellipsize = TextUtils.TruncateAt.MIDDLE
            }
            val removeBtn = MaterialButton(this).apply {
                setText("✕")
                setOnClickListener { removeSender(s) }
            }
            row.addView(label)
            row.addView(removeBtn)
            listSenders.addView(row)
        }
    }

    private fun removeSender(sender: String) {
        MaterialAlertDialogBuilder(this)
            .setTitle(getString(R.string.dialog_remove_sender))
            .setMessage(sender)
            .setPositiveButton(getString(R.string.btn_remove)) { _, _ ->
                settings.removeAllowedSender(sender)
                refreshSenderList()
            }
            .setNegativeButton(getString(R.string.btn_cancel), null)
            .show()
    }
}
