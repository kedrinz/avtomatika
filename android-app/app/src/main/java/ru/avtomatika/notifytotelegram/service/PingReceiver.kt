package ru.avtomatika.notifytotelegram.service

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.PowerManager
import android.util.Log
import ru.avtomatika.notifytotelegram.data.Settings

/**
 * Принимает будильник от AlarmManager, отправляет пинг на сервер и планирует следующий.
 * Работает даже при выключенном экране и в режиме Doze — устройство не будет считаться оффлайн.
 */
class PingReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != ACTION_PING) return
        val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager ?: return
        val wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "evateam:ping").apply {
            acquire(30_000) // макс 30 сек на пинг
        }
        try {
            val settings = Settings(context)
            if (!settings.isConfigured()) return
            val url = settings.getServerUrl()
            val token = settings.getDeviceToken()
            if (url.isBlank() || token.isBlank()) return
            try {
                NotificationSender(context).ping(url, token)
            } catch (e: Exception) {
                Log.w(TAG, "Ping failed", e)
            }
            scheduleNext(context)
        } finally {
            if (wl.isHeld) wl.release()
        }
    }

    companion object {
        private const val TAG = "PingReceiver"
        const val ACTION_PING = "ru.avtomatika.notifytotelegram.PING"
        private const val REQUEST_CODE = 2001
        const val FIRST_DELAY_MS = 30_000L   // первый пинг через 30 сек
        private const val INTERVAL_MS = 60_000L     // далее каждую минуту

        fun scheduleNext(context: Context, delayMs: Long = INTERVAL_MS) {
            val am = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
            val intent = Intent(context, PingReceiver::class.java).apply { action = ACTION_PING }
            val pi = PendingIntent.getBroadcast(
                context, REQUEST_CODE, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val triggerAt = System.currentTimeMillis() + delayMs
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (!am.canScheduleExactAlarms()) {
                    am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
                    return
                }
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, triggerAt, pi)
            } else {
                @Suppress("DEPRECATION")
                am.setExact(AlarmManager.RTC_WAKEUP, triggerAt, pi)
            }
        }

        fun cancel(context: Context) {
            val am = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
            val intent = Intent(context, PingReceiver::class.java).apply { action = ACTION_PING }
            val pi = PendingIntent.getBroadcast(
                context, REQUEST_CODE, intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            am.cancel(pi)
        }
    }
}
