import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.util.Base64
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// ── 릴리스 서명 키 ────────────────────────────────────────────────────────
// **친구에게 나눠주는 APK 는 항상 같은 키로 서명돼야 한다.** 서명이 달라지면 폰이
// 업데이트를 거부하고("앱이 설치되지 않음") 지웠다 깔아야 해서 페어링도 다시 해야 한다.
// 예전엔 release 도 디버그 키로 서명했는데, 디버그 키는 PC 마다 다르고 CI 는 매번
// 새 VM 이라 **빌드할 때마다 서명이 바뀌었다.**
//
// 키를 찾는 두 갈래:
//   내 PC → android/keystore.properties        (저장소에 안 올라간다)
//   CI    → COOLDOWN_KEYSTORE_B64 환경변수      (GitHub Secret. 이게 키의 백업도 된다)
// 둘 다 없으면 디버그 키로 떨어진다 — 클론만 한 사람도 빌드는 되게. 대신 경고를 띄운다.
val keyProps = Properties().apply {
    val f = rootProject.file("keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

val keyPath: String? = keyProps.getProperty("storeFile")
val keyB64: String? = System.getenv("COOLDOWN_KEYSTORE_B64")
val keyStoreFile: File? = when {
    keyPath != null -> rootProject.file(keyPath)
    !keyB64.isNullOrBlank() -> layout.buildDirectory.file("cooldown-release.jks").get().asFile.apply {
        parentFile.mkdirs()
        // 스크립트 안에서 `java` 는 Gradle 의 java 확장이라 패키지 이름으로 못 쓴다 — 위에서 import 한다
        writeBytes(Base64.getMimeDecoder().decode(keyB64))
    }
    else -> null
}
// ★ 이름을 storePassword/keyPassword 로 짓지 말 것 — 아래 signingConfigs 블록 안에서는
//   그게 SigningConfig 자신의 속성이라, 내 변수인 줄 알고 쓰면 null 이 들어간다.
val keyStorePw: String? = keyProps.getProperty("storePassword")
    ?: System.getenv("COOLDOWN_KEYSTORE_PASSWORD")
val keyAliasName: String = keyProps.getProperty("keyAlias") ?: "cooldown"
val keyAliasPw: String? = keyProps.getProperty("keyPassword") ?: keyStorePw
val signRelease = keyStoreFile != null && keyStoreFile.exists() && !keyStorePw.isNullOrBlank()

if (!signRelease) {
    logger.warn(
        "⚠ 서명 키가 없어 release 도 디버그 키로 서명한다. " +
            "나눠줄 APK 는 이러면 안 된다 — 빌드할 때마다 서명이 달라져 업데이트가 막힌다.",
    )
}

android {
    namespace = "com.kyijgnes.cooldown"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.kyijgnes.cooldown"
        minSdk = 26
        targetSdk = 36
        // ★ 나눠주기 전에 versionCode 를 올릴 것. 안 올리면 폰이 업데이트인지 구별을 못 한다.
        versionCode = 12
        versionName = "0.12"
    }

    signingConfigs {
        if (signRelease) {
            create("release") {
                storeFile = keyStoreFile
                storePassword = keyStorePw
                keyAlias = keyAliasName
                keyPassword = keyAliasPw
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // 스토어에 올리지 않고 APK 를 직접 나눠 준다 — 위에서 찾은 고정 키로 서명한다.
            signingConfig = signingConfigs.getByName(if (signRelease) "release" else "debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        unitTests {
            isIncludeAndroidResources = true
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    // 15분 주기 갱신 + 재부팅 후 복구. 이거 하나면 되므로 다른 androidx 는 안 쓴다.
    implementation("androidx.work:work-runtime:2.11.2")
    // QR 스캔. 카메라 권한 없이 Play 서비스가 대신 찍어 준다 (없으면 직접 입력으로 넘어간다)
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")

    // 화면 그림을 폰 없이 PNG 로 뽑아 보는 용도 (RenderPreviewTest)
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.16.1")
}
