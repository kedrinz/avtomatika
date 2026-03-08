package ru.avtomatika.notifytotelegram.service

import android.content.Context
import android.util.Log
import ru.avtomatika.notifytotelegram.data.Settings

/** Общая логика пинга: отправить запрос на сервер. */
object PingHelper {

    private const val TAG = "PingHelper"

    /** Отправляет пинг на сервер, если настройки заданы. Ничего не планирует. */
    fun doPing(context: Context): Boolean {
        val settings = Settings(context)
        if (!settings.isConfigured()) return false
        val url = settings.getServerUrl()
        val token = settings.getDeviceToken()
        if (url.isBlank() || token.isBlank()) return false
        return try {
            NotificationSender(context).ping(url, token)
            true
        } catch (e: Exception) {
            Log.w(TAG, "Ping failed", e)
            false
        }
    }
}
