# Полный список действий для сборки APK

## Вариант 0: Через GitHub (без Android Studio и SDK на вашем ПК)

Сборка выполняется на серверах GitHub — на компьютере не нужны ни Android Studio, ни SDK.

### Шаг 1. Создать репозиторий на GitHub
1. Зайдите на https://github.com и войдите в аккаунт.
2. Нажмите **New repository**. Имя любое (например `avtomatika`). Создайте репозиторий (можно без README).

### Шаг 2. Загрузить проект
- Установите [Git](https://git-scm.com/) (если ещё нет).
- В папке проекта (например `C:\Users\ks\Desktop\projects\avtomatika`) откройте терминал и выполните:
  ```bash
  git init
  git add .
  git commit -m "Initial"
  git branch -M main
  git remote add origin https://github.com/ВАШ_ЛОГИН/ИМЯ_РЕПОЗИТОРИЯ.git
  git push -u origin main
  ```
  Подставьте свой логин и имя репозитория.

### Шаг 3. Запустить сборку
1. На GitHub откройте репозиторий.
2. Вкладка **Actions** → слева выберите workflow **Build APK** → кнопка **Run workflow** → **Run workflow**.
3. Дождитесь зелёной галочки (обычно 5–10 минут).

### Шаг 4. Скачать APK
1. В том же запуске workflow нажмите на завершённое задание (job).
2. Внизу страницы в блоке **Artifacts** появится **app-debug** — нажмите на него, чтобы скачать архив с `app-debug.apk`.
3. Распакуйте архив и установите **app-debug.apk** на телефон.

Повторная сборка: снова **Actions → Build APK → Run workflow**.

---

## Вариант 1: Через Android Studio (рекомендуется)

### Шаг 1. Установить Android Studio
- Скачайте с https://developer.android.com/studio и установите.
- При первом запуске пройдите мастер настройки (установятся SDK и эмулятор при необходимости).

### Шаг 2. Открыть проект
1. Запустите Android Studio.
2. **File → Open** (или «Open» на стартовом экране).
3. Укажите папку **`avtomatika\android-app`** (именно папку `android-app`, где лежат `build.gradle.kts` и `app`).
4. Нажмите **OK**. Дождитесь синхронизации Gradle (первый раз может занять несколько минут).

### Шаг 3. Собрать APK
- **Debug (для теста):** меню **Build → Build Bundle(s) / APK(s) → Build APK(s)**.  
  Внизу появится уведомление — можно **Locate** (открыть папку с APK).
- **Release:** **Build → Generate Signed Bundle / APK… → APK** → создать/выбрать keystore → выбрать release → **Finish**.

### Шаг 4. Где лежит APK
- Debug: `android-app\app\build\outputs\apk\debug\app-debug.apk`
- Release: `android-app\app\build\outputs\apk\release\app-release.apk`

---

## Вариант 2: Через командную строку (без Android Studio)

### Шаг 1. Установить необходимое
- **JDK 17** (например Amazon Corretto 17 или OpenJDK 17).
- **Android SDK** — можно поставить через Android Studio (только SDK) или командой:
  - `sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"`
- Переменная окружения **ANDROID_HOME** = путь к SDK (например `C:\Users\ИМЯ\AppData\Local\Android\Sdk`).

### Шаг 2. Создать Gradle Wrapper (если нет файлов gradlew)
В папке **`android-app`** выполните (нужен установленный Gradle 8.x):

```bash
gradle wrapper --gradle-version=8.2
```

Появятся `gradlew.bat`, `gradlew` и папка `gradle\wrapper`.

Если Gradle не установлен — откройте проект в Android Studio один раз и соберите его; после этого wrapper создастся автоматически и можно будет собирать из командной строки через `gradlew.bat`.

### Шаг 3. Перейти в папку проекта
```bash
cd C:\Users\ks\Desktop\projects\avtomatika\android-app
```

### Шаг 4. Собрать Debug APK
```bash
gradlew.bat assembleDebug
```

Или Release:
```bash
gradlew.bat assembleRelease
```

### Шаг 5. Результат
- Debug: `app\build\outputs\apk\debug\app-debug.apk`
- Release: `app\build\outputs\apk\release\app-release.apk`

---

## Установка APK на телефон

1. Скопируйте `app-debug.apk` (или `app-release.apk`) на телефон (USB, мессенджер, облако).
2. На телефоне откройте файл APK.
3. Разрешите установку из неизвестных источников для выбранного приложения/источника, если система запросит.
4. Нажмите «Установить».

Либо по USB с включённой отладкой по USB:
```bash
adb install app\build\outputs\apk\debug\app-debug.apk
```

---

## Краткий чек-лист (Android Studio)

| № | Действие |
|---|----------|
| 1 | Установить Android Studio |
| 2 | Open → папка `android-app` |
| 3 | Дождаться синхронизации Gradle |
| 4 | Build → Build Bundle(s) / APK(s) → Build APK(s) |
| 5 | Взять APK из `app\build\outputs\apk\debug\app-debug.apk` |
| 6 | Скопировать на телефон и установить |
