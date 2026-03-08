package ru.avtomatika.notifytotelegram.service

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.PowerManager
import ru.avtomatika.notifytotelegram.data.Settings
import ru.avtomatika.notifytotelegram.ui.MainActivity
import ru.avtomatika.notifytotelegram.ui.WakePingActivity

/**
 * Принимает будильник от AlarmManager, отправляет пинг на сервер и планирует следующий.
 * Используется setAlarmClock() — не троттлится в Doze при выключенном экране.
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
            // По желанию включаем экран перед пингом, чтобы устройство не уходило в офлайн
            if (settings.getWakeScreenOnPing()) {
                val wake = Intent(context, WakePingActivity::class.java)
                wake.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_USER_ACTION or Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS)
                try {
                    context.startActivity(wake)
                } catch (_: Exception) { }
            }
            PingHelper.doPing(context)
            scheduleNext(context)
        } finally {
            if (wl.isHeld) wl.release()
        }
    }

    companion object {
        private const val TAG = "PingReceiver" // for PingHelper logs
        const val ACTION_PING = "ru.avtomatika.notifytotelegram.PING"
        private const val REQUEST_CODE = 2001
        private const val REQUEST_CODE_SHOW = 2002
        const val FIRST_DELAY_MS = 30_000L   // первый пинг через 30 сек
        private const val INTERVAL_MS = 60_000L     // далее каждую минуту

        fun scheduleNext(context: Context, delayMs: Long = INTERVAL_MS) {
            val am = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager ?: return
            val triggerAt = System.currentTimeMillis() + delayMs
            val operation = Intent(context, PingReceiver::class.java).apply { action = ACTION_PING }
            val operationPi = PendingIntent.getBroadcast(
                context, REQUEST_CODE, operation,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            // setAlarmClock() не троттлится в Doze — пинги идут каждую минуту даже при выключенном экране
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                val showIntent = Intent(context, MainActivity::class.java).apply { flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP }
                val showPi = PendingIntent.getActivity(
                    context, REQUEST_CODE_SHOW, showIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
                val info = AlarmManager.AlarmClockInfo(triggerAt, showPi)
                am.setAlarmClock(info, operationPi)
            } else {
                @Suppress("DEPRECATION")
                am.setExact(AlarmManager.RTC_WAKEUP, triggerAt, operationPi)
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
