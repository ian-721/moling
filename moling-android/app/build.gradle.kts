plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

val debugBackendUrl = providers.gradleProperty("MOLING_DEBUG_BACKEND_URL")
    .orElse("http://10.0.2.2:8000")
val releaseBackendUrl = providers.gradleProperty("MOLING_RELEASE_BACKEND_URL")
    .orElse("https://api.moling.app")

fun quoted(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

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
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            buildConfigField("String", "BACKEND_BASE_URL", quoted(debugBackendUrl.get()))
            buildConfigField("Boolean", "ENABLE_VISION_FALLBACK", "false")
            manifestPlaceholders["usesCleartextTraffic"] = "true"
        }
        release {
            val productionUrl = releaseBackendUrl.get()
            require(productionUrl.startsWith("https://")) {
                "MOLING_RELEASE_BACKEND_URL must use HTTPS"
            }
            buildConfigField("String", "BACKEND_BASE_URL", quoted(productionUrl))
            buildConfigField("Boolean", "ENABLE_VISION_FALLBACK", "false")
            manifestPlaceholders["usesCleartextTraffic"] = "false"
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
    testImplementation(libs.junit)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
    debugImplementation(libs.androidx.compose.ui.tooling)
}
