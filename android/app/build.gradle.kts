import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.kyijgnes.cooldown"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.kyijgnes.cooldown"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // 스토어에 올리지 않고 APK 를 직접 나눠 준다 — 디버그 키로 서명해 둔다.
            signingConfig = signingConfigs.getByName("debug")
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
