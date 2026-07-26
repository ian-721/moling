package com.moling.livingnotebook.data.remote

import com.moling.livingnotebook.BuildConfig
import java.net.URI

object BackendConfig {
    val BASE_URL: String = BuildConfig.BACKEND_BASE_URL.trimEnd('/')

    val ENABLE_VISION_FALLBACK_FOR_DEV: Boolean =
        BuildConfig.DEBUG && BuildConfig.ENABLE_VISION_FALLBACK

    fun requireSecureReleaseUrl(url: String) {
        val parsed = URI(url)
        require(parsed.scheme.equals("https", ignoreCase = true) && !parsed.host.isNullOrBlank()) {
            "Release backend URL must be a valid HTTPS URL"
        }
    }

    init {
        if (!BuildConfig.DEBUG) {
            requireSecureReleaseUrl(BASE_URL)
        }
    }
}
