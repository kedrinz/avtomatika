package ru.avtomatika.notifytotelegram.ui

import android.app.KeyguardManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import androidx.appcompat.app.AppCompatActivity
import ru.avtomatika.notifytotelegram.R

/**
 * Кратковременно включает экран при пинге (по будильнику), чтобы устройство не уходило в офлайн.
 * Разблокировать экран приложение не может — это запрещено ОС.
 */
class WakePingActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
            val km = getSystemService(KEYGUARD_SERVICE) as? KeyguardManager
            km?.requestDismissKeyguard(this, null)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(
                WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                    WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON or
                    WindowManager.LayoutParams.FLAG_DISMISS_KEYGUARD
            )
        }
        setContentView(R.layout.activity_wake_ping)
        // Закрыть сразу после того, как экран включился — пинг уже идёт из PingReceiver
        window.decorView.postDelayed({ finish() }, 800)
    }
}
