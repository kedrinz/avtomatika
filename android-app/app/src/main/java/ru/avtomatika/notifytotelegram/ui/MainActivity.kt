package ru.avtomatika.notifytotelegram.ui

import android.content.ComponentName
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.button.MaterialButton
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import ru.avtomatika.notifytotelegram.R
import ru.avtomatika.notifytotelegram.data.Settings
import ru.avtomatika.notifytotelegram.service.NotifyListenerService

class MainActivity : AppCompatActivity() {

    private lateinit var settings: Settings
    private lateinit var etServerUrl: TextInputEditText
    private lateinit var etDeviceToken: TextInputEditText
    private lateinit var etPackage: TextInputEditText
    private lateinit var listPackages: LinearLayout
    private lateinit var statusListener: android.widget.TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        settings = Settings(this)
        etServerUrl = findViewById(R.id.etServerUrl)
        etDeviceToken = findViewById(R.id.etDeviceToken)
        etPackage = findViewById(R.id.etPackage)
        listPackages = findViewById(R.id.listPackages)
        statusListener = findViewById(R.id.statusListener)
        loadConfig()
        refreshPackageList()
        updateListenerStatus()
        findViewById<MaterialButton>(R.id.btnEnableListener).setOnClickListener { openListenerSettings() }
        findViewById<MaterialButton>(R.id.btnSaveConfig).setOnClickListener { saveConfig() }
        findViewById<MaterialButton>(R.id.btnAddPackage).setOnClickListener { addPackage() }
    }

    override fun onResume() {
        super.onResume()
        updateListenerStatus()
    }

    private fun updateListenerStatus() {
        val enabled = isNotificationServiceEnabled()
        statusListener.text = if (enabled) "Включено" else "Выключено"
        statusListener.setTextColor(
            if (enabled) getColor(android.R.color.holo_green_dark)
            else getColor(android.R.color.holo_red_dark)
        )
    }

    private fun isNotificationServiceEnabled(): Boolean {
        val pkg = packageName
        val flat = android.provider.Settings.Secure.getString(
            contentResolver,
            android.provider.Settings.Secure.ENABLED_NOTIFICATION_LISTENERS
        ) ?: return false
        for (part in flat.split(":")) {
            val cn = ComponentName.unflattenFromString(part) ?: continue
            if (cn.packageName == pkg) return true
        }
        return false
    }

    private fun openListenerSettings() {
        try {
            startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
        } catch (_: Exception) {
            Toast.makeText(this, "Не удалось открыть настройки", Toast.LENGTH_SHORT).show()
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
                Toast.makeText(this, "Введите URL сервера", Toast.LENGTH_SHORT).show()
                return
            }
            !url.startsWith("http://") && !url.startsWith("https://") -> {
                Toast.makeText(this, "URL должен начинаться с http:// или https://", Toast.LENGTH_SHORT).show()
                return
            }
            token.isBlank() -> {
                Toast.makeText(this, "Введите токен устройства из бота", Toast.LENGTH_SHORT).show()
                return
            }
        }
        settings.setServerUrl(url)
        settings.setDeviceToken(token)
        Toast.makeText(this, "Сохранено", Toast.LENGTH_SHORT).show()
    }

    private fun addPackage() {
        val pkg = etPackage.text?.toString()?.trim() ?: ""
        if (pkg.isBlank()) {
            Toast.makeText(this, "Введите имя пакета (например com.whatsapp)", Toast.LENGTH_SHORT).show()
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
            }
            val text = android.widget.TextView(this).apply {
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply {
                    setMargins(0, 0, 8, 0)
                }
                setText(pkg)
                setSingleLine()
                ellipsize = TextUtils.TruncateAt.MIDDLE
            }
            val remove = MaterialButton(this).apply {
                text = "✕"
                setOnClickListener { removePackage(pkg) }
            }
            row.addView(text)
            row.addView(remove)
            listPackages.addView(row)
        }
    }

    private fun removePackage(pkg: String) {
        MaterialAlertDialogBuilder(this)
            .setTitle("Удалить?")
            .setMessage(pkg)
            .setPositiveButton("Удалить") { _, _ ->
                settings.removeMonitoredPackage(pkg)
                refreshPackageList()
            }
            .setNegativeButton("Отмена", null)
            .show()
    }
}
