package ru.avtomatika.notifytotelegram.data

import android.content.Context
import android.content.SharedPreferences

class Settings(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun getServerUrl(): String = prefs.getString(KEY_SERVER_URL, "")?.trim() ?: ""
    fun setServerUrl(url: String) = prefs.edit().putString(KEY_SERVER_URL, url.trim()).apply()

    fun getDeviceToken(): String = prefs.getString(KEY_DEVICE_TOKEN, "")?.trim() ?: ""
    fun setDeviceToken(token: String) = prefs.edit().putString(KEY_DEVICE_TOKEN, token.trim()).apply()

    fun getMonitoredPackages(): Set<String> =
        prefs.getStringSet(KEY_PACKAGES, emptySet()) ?: emptySet()

    fun setMonitoredPackages(packages: Set<String>) =
        prefs.edit().putStringSet(KEY_PACKAGES, packages).apply()

    fun getAllowedSenders(): Set<String> =
        prefs.getStringSet(KEY_ALLOWED_SENDERS, emptySet()) ?: emptySet()

    fun setAllowedSenders(senders: Set<String>) =
        prefs.edit().putStringSet(KEY_ALLOWED_SENDERS, senders).apply()

    fun addAllowedSender(sender: String) {
        val set = getAllowedSenders().toMutableSet()
        if (sender.isNotBlank()) set.add(sender.trim())
        setAllowedSenders(set)
    }

    fun removeAllowedSender(sender: String) {
        val set = getAllowedSenders().toMutableSet()
        set.remove(sender)
        setAllowedSenders(set)
    }

    /** Проверяет, нужно ли пересылать уведомление от данного отправителя. title обычно = имя/номер отправителя. */
    fun isSenderAllowed(senderTitle: String): Boolean {
        val allowed = getAllowedSenders()
        if (allowed.isEmpty()) return true
        val normalized = senderTitle.trim().lowercase()
        return allowed.any { it.trim().lowercase() in normalized || normalized.contains(it.trim().lowercase()) }
    }

    fun addMonitoredPackage(pkg: String) {
        val set = getMonitoredPackages().toMutableSet()
        if (pkg.isNotBlank()) set.add(pkg.trim())
        setMonitoredPackages(set)
    }

    fun removeMonitoredPackage(pkg: String) {
        val set = getMonitoredPackages().toMutableSet()
        set.remove(pkg)
        setMonitoredPackages(set)
    }

    fun isConfigured(): Boolean {
        val url = getServerUrl()
        val token = getDeviceToken()
        if (url.isBlank() || token.isBlank()) return false
        return url.startsWith("http://") || url.startsWith("https://")
    }

    companion object {
        private const val PREFS_NAME = "notify_to_telegram"
        private const val KEY_SERVER_URL = "server_url"
        private const val KEY_DEVICE_TOKEN = "device_token"
        private const val KEY_PACKAGES = "monitored_packages"
        private const val KEY_ALLOWED_SENDERS = "allowed_senders"
    }
}
