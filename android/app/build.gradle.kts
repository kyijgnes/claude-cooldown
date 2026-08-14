import org.jetbrains.kotlin.gradle.dsl.JvmTarget
import java.util.Base64
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// ?? 由대━???쒕챸 ??????????????????????????????????????????????????????????
// **移쒓뎄?먭쾶 ?섎닠二쇰뒗 APK ????긽 媛숈? ?ㅻ줈 ?쒕챸?쇱빞 ?쒕떎.** ?쒕챸???щ씪吏硫??곗씠
// ?낅뜲?댄듃瑜?嫄곕??섍퀬("?깆씠 ?ㅼ튂?섏? ?딆쓬") 吏?좊떎 源붿븘???댁꽌 ?섏뼱留곷룄 ?ㅼ떆 ?댁빞 ?쒕떎.
// ?덉쟾??release ???붾쾭洹??ㅻ줈 ?쒕챸?덈뒗?? ?붾쾭洹??ㅻ뒗 PC 留덈떎 ?ㅻⅤ怨?CI ??留ㅻ쾲
// ??VM ?대씪 **鍮뚮뱶???뚮쭏???쒕챸??諛붾뚯뿀??**
//
// ?ㅻ? 李얜뒗 ??媛덈옒:
//   ??PC ??android/keystore.properties        (??μ냼?????щ씪媛꾨떎)
//   CI    ??COOLDOWN_KEYSTORE_B64 ?섍꼍蹂??     (GitHub Secret. ?닿쾶 ?ㅼ쓽 諛깆뾽???쒕떎)
// ?????놁쑝硫??붾쾭洹??ㅻ줈 ?⑥뼱吏꾨떎 ???대줎留????щ엺??鍮뚮뱶???섍쾶. ???寃쎄퀬瑜??꾩슫??
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
        // ?ㅽ겕由쏀듃 ?덉뿉??`java` ??Gradle ??java ?뺤옣?대씪 ?⑦궎吏 ?대쫫?쇰줈 紐??대떎 ???꾩뿉??import ?쒕떎
        writeBytes(Base64.getMimeDecoder().decode(keyB64))
    }
    else -> null
}
// ???대쫫??storePassword/keyPassword 濡?吏볦? 留?寃????꾨옒 signingConfigs 釉붾줉 ?덉뿉?쒕뒗
//   洹멸쾶 SigningConfig ?먯떊???띿꽦?대씪, ??蹂?섏씤 以??뚭퀬 ?곕㈃ null ???ㅼ뼱媛꾨떎.
val keyStorePw: String? = keyProps.getProperty("storePassword")
    ?: System.getenv("COOLDOWN_KEYSTORE_PASSWORD")
val keyAliasName: String = keyProps.getProperty("keyAlias") ?: "cooldown"
val keyAliasPw: String? = keyProps.getProperty("keyPassword") ?: keyStorePw
val signRelease = keyStoreFile != null && keyStoreFile.exists() && !keyStorePw.isNullOrBlank()

if (!signRelease) {
    logger.warn(
        "???쒕챸 ?ㅺ? ?놁뼱 release ???붾쾭洹??ㅻ줈 ?쒕챸?쒕떎. " +
            "?섎닠以?APK ???대윭硫????쒕떎 ??鍮뚮뱶???뚮쭏???쒕챸???щ씪???낅뜲?댄듃媛 留됲엺??",
    )
}

android {
    namespace = "com.kyijgnes.cooldown"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.kyijgnes.cooldown"
        minSdk = 26
        targetSdk = 36
        // ???섎닠二쇨린 ?꾩뿉 versionCode 瑜??щ┫ 寃? ???щ━硫??곗씠 ?낅뜲?댄듃?몄? 援щ퀎??紐??쒕떎.
        versionCode = 17
        versionName = "0.17"
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
            // ?ㅽ넗?댁뿉 ?щ━吏 ?딄퀬 APK 瑜?吏곸젒 ?섎닠 以?????꾩뿉??李얠? 怨좎젙 ?ㅻ줈 ?쒕챸?쒕떎.
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
    // 15遺?二쇨린 媛깆떊 + ?щ?????蹂듦뎄. ?닿굅 ?섎굹硫??섎?濡??ㅻⅨ androidx ?????대떎.
    implementation("androidx.work:work-runtime:2.11.2")
    // QR ?ㅼ틪. 移대찓??沅뚰븳 ?놁씠 Play ?쒕퉬?ㅺ? ???李띿뼱 以??(?놁쑝硫?吏곸젒 ?낅젰?쇰줈 ?섏뼱媛꾨떎)
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")

    // ?붾㈃ 洹몃┝?????놁씠 PNG 濡?戮묒븘 蹂대뒗 ?⑸룄 (RenderPreviewTest)
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.16.1")
}
