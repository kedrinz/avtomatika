package ru.avtomatika.notifytotelegram.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
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
    private var screenOnReceiver: ScreenOnReceiver? = null

    override fun onListenerConnected() {
        super.onListenerConnected()
        startForegroundIfNeeded()
        // Пинг по AlarmManager — срабатывает даже при выключенном экране и в Doze
        PingReceiver.scheduleNext(applicationContext, PingReceiver.FIRST_DELAY_MS)
        registerScreenOnReceiver()
    }

    private fun registerScreenOnReceiver() {
        if (screenOnReceiver != null) return
        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_SCREEN_ON)
            addAction(Intent.ACTION_USER_PRESENT)
        }
        screenOnReceiver = ScreenOnReceiver()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(screenOnReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(screenOnReceiver, filter)
        }
    }

    override fun onDestroy() {
        screenOnReceiver?.let { try { unregisterReceiver(it) } catch (_: Exception) { } }
        screenOnReceiver = null
        PingReceiver.cancel(applicationContext)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            stopForeground(STOP_FOREGROUND_REMOVE)
        }
        super.onDestroy()
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
        val resultText = sequenceOf(text, bigText, subText).firstOrNull { !it.isNullOrBlank() } ?: ""
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
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channelId = "notify_forward_channel"
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(
                channelId,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply { setShowBadge(true) }
        )
        val intent = Intent(this, MainActivity::class.java)
        val pi = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle(getString(R.string.notification_foreground_title))
            .setContentText(getString(R.string.notification_foreground_text))
            .setSmallIcon(R.drawable.ic_launcher)
            .setContentIntent(pi)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            startForeground(FOREGROUND_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(FOREGROUND_ID, notification)
        }
    }

    companion object {
        private const val FOREGROUND_ID = 1001
    }
}
