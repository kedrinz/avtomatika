package ru.avtomatika.notifytotelegram.service

import android.content.Context
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class NotificationSender(private val context: Context) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun send(
        serverUrl: String,
        deviceToken: String,
        packageName: String,
        appName: String,
        title: String,
        text: String
    ) {
        val url = "$serverUrl/api/notify".replace(Regex("/+$"), "")
        val body = JSONObject().apply {
            put("device_token", deviceToken)
            put("package", packageName)
            put("app_name", appName)
            put("title", title)
            put("text", text)
        }.toString()
        val request = Request.Builder()
            .url(url)
            .post(body.toRequestBody("application/json; charset=utf-8".toMediaType()))
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw Exception("HTTP ${response.code}")
            }
        }
    }
}
