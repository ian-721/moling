import java.net.URI

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
}

val debugBackendUrl = providers.gradleProperty("MOLING_DEBUG_BACKEND_URL")
    .orElse("http://10.0.2.2:8000")
val releaseBackendUrlProperty = providers.gradleProperty("MOLING_RELEASE_BACKEND_URL")
val releaseBackendUrl = releaseBackendUrlProperty.orElse("https://release.invalid")

fun quoted(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

val releaseSigningValues = mapOf(
    "storeFile" to providers.environmentVariable("MOLING_KEYSTORE_PATH").orNull,
    "storePassword" to providers.environmentVariable("MOLING_KEYSTORE_PASSWORD").orNull,
    "keyAlias" to providers.environmentVariable("MOLING_KEY_ALIAS").orNull,
    "keyPassword" to providers.environmentVariable("MOLING_KEY_PASSWORD").orNull
)
val releaseSigningConfigured = releaseSigningValues.values.all { !it.isNullOrBlank() }
require(
    releaseSigningValues.values.all { it.isNullOrBlank() } || releaseSigningConfigured
) {
    "Release signing is partially configured. Set all MOLING_KEYSTORE_* variables or none."
}

android {
    namespace = "com.moling.livingnotebook"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.moling.livingnotebook"
        minSdk = 26
        targetSdk = 36
        versionCode = 800
        versionName = "0.8.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        if (releaseSigningConfigured) {
            create("molingRelease") {
                storeFile = file(releaseSigningValues.getValue("storeFile")!!)
                storePassword = releaseSigningValues.getValue("storePassword")
                keyAlias = releaseSigningValues.getValue("keyAlias")
                keyPassword = releaseSigningValues.getValue("keyPassword")
                enableV1Signing = true
                enableV2Signing = true
                enableV3Signing = true
                enableV4Signing = true
            }
        }
    }

    buildTypes {
        debug {
            buildConfigField("String", "BACKEND_BASE_URL", quoted(debugBackendUrl.get()))
            buildConfigField("Boolean", "ENABLE_VISION_FALLBACK", "false")
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        release {
            val productionUrl = releaseBackendUrl.get()
            val productionUri = runCatching { URI(productionUrl) }.getOrNull()
            require(
                productionUri != null &&
                    productionUri.scheme.equals("https", ignoreCase = true) &&
                    !productionUri.host.isNullOrBlank() &&
                    productionUri.rawUserInfo == null &&
                    productionUri.rawQuery == null &&
                    productionUri.rawFragment == null
            ) {
                "MOLING_RELEASE_BACKEND_URL must be a valid HTTPS URL without credentials, query, or fragment"
            }
            if (releaseSigningConfigured) {
                require(releaseBackendUrlProperty.isPresent) {
                    "A signed Release requires an explicit MOLING_RELEASE_BACKEND_URL"
                }
                require(!productionUri!!.host.endsWith(".invalid", ignoreCase = true)) {
                    "A signed Release cannot use the reserved .invalid hostname"
                }
            }
            buildConfigField("String", "BACKEND_BASE_URL", quoted(productionUrl))
            buildConfigField("Boolean", "ENABLE_VISION_FALLBACK", "false")
            manifestPlaceholders["usesCleartextTraffic"] = "false"
            if (releaseSigningConfigured) {
                signingConfig = signingConfigs.getByName("molingRelease")
            }
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
    arg("room.generateKotlin", "true")
}

dependencies {
    // ML Kit Digital Ink Recognition; models are downloaded by Google Play Services.
    implementation("com.google.mlkit:digital-ink-recognition:19.0.0")
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.4")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.4")
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)
    testImplementation(libs.junit)
    testImplementation(libs.androidx.room.testing)
    testImplementation("org.robolectric:robolectric:4.16.1")
    testImplementation("androidx.test:core:1.6.1")
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}
