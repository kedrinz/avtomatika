package ru.avtomatika.notifytotelegram.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.PowerManager

/**
 * При включении экрана или разблокировке сразу отправляет пинг,
 * чтобы устройство быстрее отображалось онлайн.
 */
class ScreenOnReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        if (action != android.content.Intent.ACTION_SCREEN_ON &&
            action != android.content.Intent.ACTION_USER_PRESENT
        ) return
        val pm = context.getSystemService(Context.POWER_SERVICE) as? PowerManager ?: return
        val wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "evateam:screen_on").apply {
            acquire(15_000)
        }
        try {
            PingHelper.doPing(context)
        } finally {
            if (wl.isHeld) wl.release()
        }
    }
}
