# Android BLE Notification Integration Guide

이 문서는 Raspberry Pi BLE Notify 송신을 Android 앱에서 수신하고 배너 알림으로 표시하는 **Android Studio 실습형 구현 가이드**입니다.
Android 소스는 별도 레포지토리에서 관리하는 것을 전제로 작성했습니다.

## 0) 먼저 답변: Android Studio로 하면 되나요?

네. Android 앱 구현은 **Android Studio**로 진행하는 것이 표준입니다.
이 가이드는 Android Studio 기준으로 `프로젝트 생성 -> 코드 배치 -> 권한 처리 -> BLE 수신 -> 알림 표시 -> 실기 검증` 순서로 구성되어 있습니다.

## 1) 권장 개발 환경 (2026-05 기준)

- Android Studio: **Panda 4 (2025.3.4) stable 이상**
- Android Gradle Plugin (AGP): **9.2.x**
- Gradle: **9.4.1**
- JDK: **17**
- compileSdk: **36 or 36.1 대응 환경**
- 언어: **Kotlin**
- 최소 SDK(minSdk): **26 이상 권장**

이 조합을 권장하는 이유:
- 최신 BLE/권한 정책(특히 Android 12+, 13+) 반영이 수월함
- Android Studio와 AGP 호환성 표 기준으로 충돌 가능성 감소
- JDK 17이 AGP 9.x 기본 요구사항과 정렬됨

## 2) BLE Contract (Pi ↔ Android)

- Service UUID: `f82d9a22-3dc9-430e-875d-583c9ced1904`
- Notify Characteristic UUID: `2c5bba85-ac1c-46c2-a8d3-db389101a028`
- Payload: UTF-8 JSON
- Direction: Pi -> Android notify only. The Pi server does not implement an Android -> Pi request/response handshake.

```json
{
  "event": "BIN_FULL",
  "message": "분류함 비움 필요",
  "ts": "2026-05-04T12:34:56.123456+00:00"
}
```

- `event` allowed values:
  - `BIN_FULL`
  - `OUTPUT_EXCEPTION`

## 3) Android Studio에서 새 프로젝트 만들기

1. Android Studio 실행
2. `New Project` 선택
3. 템플릿: `Empty Activity`
4. 설정 예시
   - Name: `EcoSortBleClient`
   - Package name: `com.example.blealerts`
   - Language: `Kotlin`
   - Minimum SDK: `API 26` 이상
5. 생성 후 Gradle Sync 완료 대기

## 4) 파일 배치 위치

아래 파일을 Android 앱 모듈(app) 기준으로 배치합니다.

- `app/src/main/AndroidManifest.xml`
- `app/src/main/java/com/example/blealerts/BleClient.kt`
- `app/src/main/java/com/example/blealerts/NotificationHelper.kt`
- `app/src/main/java/com/example/blealerts/MainActivity.kt`

## 5) Gradle 설정 체크리스트

`app/build.gradle.kts` 확인:

```kotlin
android {
    namespace = "com.example.blealerts"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.example.blealerts"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
}
```

- 이미 생성된 프로젝트면 대부분 포함되어 있습니다.
- Sync 에러가 나면 JDK가 17인지 먼저 확인하세요.

## 6) AndroidManifest.xml 템플릿

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-feature android:name="android.hardware.bluetooth_le" android:required="true" />

    <!-- Android 12+ -->
    <uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
    <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />

    <!-- Android 11 이하 호환 -->
    <uses-permission android:name="android.permission.BLUETOOTH" android:maxSdkVersion="30" />
    <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" android:maxSdkVersion="30" />
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" android:maxSdkVersion="30" />

    <!-- Android 13+ 알림 권한 -->
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.Light.NoActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

## 7) NotificationHelper.kt 템플릿

```kotlin
package com.example.blealerts

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

class NotificationHelper(private val context: Context) {
    private val channelId = "waste-alert-channel"

    fun ensureChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "Waste Alerts",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Raspberry Pi BLE alerts"
            }
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    fun showAlert(title: String, message: String) {
        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(android.R.drawable.stat_notify_more)
            .setContentTitle(title)
            .setContentText(message)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()

        NotificationManagerCompat.from(context)
            .notify(System.currentTimeMillis().toInt(), notification)
    }
}
```

## 8) BleClient.kt 템플릿

```kotlin
package com.example.blealerts

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothGattService
import android.bluetooth.BluetoothManager
import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.util.UUID

class BleClient(
    context: Context,
    private val notificationHelper: NotificationHelper
) {
    private val bluetoothManager = context.getSystemService(BluetoothManager::class.java)
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager?.adapter
    private var gatt: BluetoothGatt? = null

    private val serviceUuid = UUID.fromString("f82d9a22-3dc9-430e-875d-583c9ced1904")
    private val notifyUuid = UUID.fromString("2c5bba85-ac1c-46c2-a8d3-db389101a028")
    private val cccdUuid = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

    @SuppressLint("MissingPermission")
    fun connect(device: BluetoothDevice) {
        disconnect()
        gatt = device.connectGatt(null, false, object : BluetoothGattCallback() {
            override fun onConnectionStateChange(gatt: BluetoothGatt, status: Int, newState: Int) {
                when (newState) {
                    BluetoothGatt.STATE_CONNECTED -> {
                        Log.i("BleClient", "Connected. Discovering services...")
                        gatt.discoverServices()
                    }
                    BluetoothGatt.STATE_DISCONNECTED -> {
                        Log.i("BleClient", "Disconnected. Closing stale GATT.")
                        closeGatt(gatt)
                    }
                }
            }

            override fun onServicesDiscovered(gatt: BluetoothGatt, status: Int) {
                if (status != BluetoothGatt.GATT_SUCCESS) {
                    Log.e("BleClient", "Service discovery failed. status=$status")
                    disconnect()
                    return
                }

                val service: BluetoothGattService = gatt.getService(serviceUuid) ?: run {
                    Log.e("BleClient", "Service UUID not found")
                    disconnect()
                    return
                }
                val characteristic: BluetoothGattCharacteristic =
                    service.getCharacteristic(notifyUuid) ?: run {
                        Log.e("BleClient", "Notify characteristic UUID not found")
                        disconnect()
                        return
                    }

                gatt.setCharacteristicNotification(characteristic, true)
                val descriptor: BluetoothGattDescriptor? = characteristic.getDescriptor(cccdUuid)
                descriptor?.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                if (descriptor != null) {
                    gatt.writeDescriptor(descriptor)
                    Log.i("BleClient", "CCCD write requested")
                } else {
                    Log.e("BleClient", "CCCD descriptor not found")
                    disconnect()
                }
            }

            override fun onCharacteristicChanged(
                gatt: BluetoothGatt,
                characteristic: BluetoothGattCharacteristic
            ) {
                if (characteristic.uuid != notifyUuid) return

                val raw = characteristic.value?.toString(Charsets.UTF_8) ?: return
                runCatching {
                    val json = JSONObject(raw)
                    val event = json.optString("event", "UNKNOWN")
                    val message = json.optString("message", "No message")
                    val title = when (event) {
                        "BIN_FULL" -> "분류함 가득 참"
                        "OUTPUT_EXCEPTION" -> "출력 장치 예외"
                        else -> "EcoSort 알림"
                    }
                    notificationHelper.showAlert(title, message)
                    Log.i("BleClient", "Notification shown. event=$event")
                }.onFailure {
                    Log.e("BleClient", "Invalid BLE payload: $raw", it)
                }
            }
        })
    }

    @SuppressLint("MissingPermission")
    fun disconnect() {
        gatt?.disconnect()
        gatt?.close()
        gatt = null
    }

    private fun closeGatt(closedGatt: BluetoothGatt) {
        if (gatt == closedGatt) {
            closedGatt.close()
            gatt = null
        } else {
            closedGatt.close()
        }
    }

    fun isBluetoothReady(): Boolean {
        return bluetoothAdapter?.isEnabled == true
    }
}
```

## 9) MainActivity 연결 예시 (초기화 + 권한 + connect 호출 지점)

아래 코드는 "권한 처리 흐름"과 "BleClient.connect(device) 호출 위치"를 보여주는 샘플입니다.
실제 장치 스캔/선택 UI는 프로젝트 UX에 맞춰 별도 구현하세요.

```kotlin
package com.example.blealerts

import android.Manifest
import android.bluetooth.BluetoothDevice
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {
    private lateinit var notificationHelper: NotificationHelper
    private lateinit var bleClient: BleClient

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
            val granted = result.values.all { it }
            if (granted) {
                startBleFlow()
            } else {
                // UX 분기: 권한 거부 시 안내 메시지/설정 이동 유도
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        notificationHelper = NotificationHelper(this)
        notificationHelper.ensureChannel()

        bleClient = BleClient(this, notificationHelper)

        requestRuntimePermissionsIfNeeded()
    }

    private fun requestRuntimePermissionsIfNeeded() {
        val permissions = mutableListOf<String>()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions += Manifest.permission.BLUETOOTH_SCAN
            permissions += Manifest.permission.BLUETOOTH_CONNECT
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions += Manifest.permission.POST_NOTIFICATIONS
        }

        val notGranted = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (notGranted.isEmpty()) {
            startBleFlow()
        } else {
            permissionLauncher.launch(notGranted.toTypedArray())
        }
    }

    private fun startBleFlow() {
        if (!bleClient.isBluetoothReady()) {
            // UX 분기: 블루투스 켜기 안내
            return
        }

        // TODO: 실제 스캔/선택 로직에서 Raspberry Pi BluetoothDevice 획득
        val targetDevice: BluetoothDevice? = null

        if (targetDevice != null) {
            bleClient.connect(targetDevice)
        }
    }
}
```

## 10) 권한 거부/재요청 UX 분기 기준

- 최초 거부: "BLE 알림 수신을 위해 권한이 필요합니다" 안내 후 재요청
- 영구 거부("다시 묻지 않음"): 앱 설정 화면 이동 버튼 제공
- `POST_NOTIFICATIONS` 거부: BLE 연결은 수행하되 배너 대신 인앱 상태 표시

## 11) BLE 실기 테스트 절차 (실제 기기 필수)

에뮬레이터는 BLE 하드웨어/GATT 동작 검증에 제한이 있어, **실제 Android 기기**에서 테스트하세요.

1. Pi 쪽 준비
   - BLE 광고가 켜져 있는지 확인
   - Service UUID/Characteristic UUID가 문서값과 일치하는지 확인
   - Notify characteristic이 실제로 update 되는지 확인
2. Android 기기 준비
   - 블루투스 ON
   - 앱 권한 허용
   - 앱 실행 후 연결 절차 진입
3. 연결 확인
   - Logcat에서 `Connected. Discovering services...` 확인
   - `CCCD write requested` 확인
4. 이벤트 확인
   - Pi에서 `BIN_FULL` 이벤트 발생
   - Android 배너 "분류함 가득 참" 표시 확인
   - Pi에서 `OUTPUT_EXCEPTION` 이벤트 발생
   - Android 배너 "출력 장치 예외" 표시 확인

## 12) Logcat 디버깅 포인트

- 필터 태그:
  - `BleClient`
  - `BluetoothGatt`
- 핵심 확인 로그:
  - 연결 성공/해제 이벤트
  - 서비스/특성 탐색 성공 여부
  - CCCD write 성공 여부
  - 수신 payload 원문
  - JSON 파싱 실패 stack trace

## 13) 자주 발생하는 실패와 즉시 점검 항목

1. 권한 허용했는데 연결이 안 됨
   - Android 12+에서 `BLUETOOTH_CONNECT` 런타임 승인 여부 재확인
2. 연결은 되는데 알림이 안 뜸
   - `POST_NOTIFICATIONS` 승인 여부 확인
   - `ensureChannel()` 호출 시점 확인
3. Service/Characteristic 못 찾음
   - UUID 오타 확인
   - Pi가 동일 GATT 프로파일로 광고 중인지 확인
4. payload 파싱 실패
   - Pi payload가 UTF-8 JSON인지 확인
   - `event`, `message`, `ts` 키 포함 확인

## 14) 수동 테스트 시나리오 (재연 가능)

1. 정상 이벤트 2종
   - `BIN_FULL`, `OUTPUT_EXCEPTION` 각각 1회 송신 후 배너 확인
2. 권한 거부 시나리오
   - 권한 거부 -> 재요청 -> 허용 후 연결 성공 확인
3. 알림 권한만 거부
   - BLE 수신은 되지만 배너 제한되는 UX 확인
4. 비정상 payload
   - 문자열/잘못된 JSON 송신 시 앱 크래시 없음 확인
5. 앱 재실행
   - 재실행 후 채널 재사용 및 수신/배너 정상 확인

## 15) 최종 Acceptance 기준

- 실제 Android 기기에서 Pi 이벤트 `BIN_FULL`, `OUTPUT_EXCEPTION` 모두 배너로 표시된다.
- 검증 증적은 최소 아래를 포함한다.
  - 앱 화면 캡처 2장(이벤트별 1장)
  - Logcat 캡처 2장(CCCD write, 수신/표시)
  - 테스트 날짜/기기 모델/OS 버전 기록

## 16) 공식 참고 링크

- Android Studio 릴리스/호환성 표: <https://developer.android.com/studio/releases>
- Android Gradle Plugin 9.2 호환성(Gradle/JDK): <https://developer.android.com/build/releases/agp-9-2-0-release-notes>
