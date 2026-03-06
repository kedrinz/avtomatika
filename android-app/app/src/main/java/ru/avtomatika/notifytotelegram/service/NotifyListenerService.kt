package ru.avtomatika.notifytotelegram.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import ru.avtomatika.notifytotelegram.R
import ru.avtomatika.notifytotelegram.data.Settings
import ru.avtomatika.notifytotelegram.ui.MainActivity

class NotifyListenerService : NotificationListenerService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val sender by lazy { NotificationSender(applicationContext) }

    override fun onListenerConnected() {
        super.onListenerConnected()
        startForegroundIfNeeded()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null) return
        val settings = Settings(applicationContext)
        if (!settings.isConfigured()) return
        val packages = settings.getMonitoredPackages()
        if (packages.isEmpty() || sbn.packageName !in packages) return
        scope.launch {
            try {
                val (title, text) = extractNotification(sbn)
                if (title.isBlank() && text.isBlank()) return@launch
                val senderName = title
                if (!settings.isSenderAllowed(senderName)) return@launch
                sender.send(
                    serverUrl = settings.getServerUrl(),
                    deviceToken = settings.getDeviceToken(),
                    packageName = sbn.packageName,
                    appName = resolveAppName(sbn.packageName),
                    sender = senderName,
                    title = title,
                    text = text
                )
            } catch (_: Exception) {
                // защита от ошибок — тихо игнорируем сбой одной отправки
            }
        }
    }

    private fun extractNotification(sbn: StatusBarNotification): Pair<String, String> {
        val n = sbn.notification ?: return "" to ""
        val extras = n.extras ?: return "" to ""
        val title = extras.getCharSequence(android.app.Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = extras.getCharSequence(android.app.Notification.EXTRA_TEXT)?.toString() ?: ""
        val subText = extras.getCharSequence(android.app.Notification.EXTRA_SUB_TEXT)?.toString()
        val bigText = extras.getCharSequence(android.app.Notification.EXTRA_BIG_TEXT)?.toString()
        val resultTitle = title.ifBlank { n.tickerText?.toString() ?: "" }
        val resultText = sequenceOf(text, bigText, subText).firstOrNull { !it.isBlank() } ?: ""
        return resultTitle to resultText
    }

    private fun resolveAppName(packageName: String): String {
        return try {
            val pm = packageManager
            val ai = pm.getApplicationInfo(packageName, 0)
            pm.getApplicationLabel(ai).toString()
        } catch (_: Exception) {
            packageName
        }
    }

    private fun startForegroundIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return
        val channelId = "notify_forward_channel"
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(
                    channelId,
                    "Пересылка уведомлений",
                    NotificationManager.IMPORTANCE_LOW
                )
            )
        }
        val intent = Intent(this, MainActivity::class.java)
        val pi = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("Уведомления в Telegram")
            .setContentText("Сервис активен")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
        startForeground(FOREGROUND_ID, notification)
    }

    override fun onDestroy() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE)
        }
        super.onDestroy()
    }

    companion object {
        private const val FOREGROUND_ID = 1001
    }
}
