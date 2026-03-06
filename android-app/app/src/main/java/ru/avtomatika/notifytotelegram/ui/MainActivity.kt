package ru.avtomatika.notifytotelegram.ui

import android.content.ComponentName
import android.content.Intent
import android.os.Bundle
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
        refreshPackageList()
        refreshSenderList()
        updateListenerStatus()
        findViewById<MaterialButton>(R.id.btnEnableListener).setOnClickListener { openListenerSettings() }
        findViewById<MaterialButton>(R.id.btnSaveConfig).setOnClickListener { saveConfig() }
        findViewById<MaterialButton>(R.id.btnAddPackage).setOnClickListener { addPackage() }
        findViewById<MaterialButton>(R.id.btnAddSender).setOnClickListener { addSender() }
    }

    override fun onResume() {
        super.onResume()
        updateListenerStatus()
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
