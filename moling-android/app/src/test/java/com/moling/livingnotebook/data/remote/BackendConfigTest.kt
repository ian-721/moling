package com.moling.livingnotebook.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class BackendConfigTest {
    @Test
    fun debugBuildUsesLocalHttpAndKeepsVisionOff() {
        assertTrue(BackendConfig.BASE_URL.startsWith("http://"))
        assertFalse(BackendConfig.ENABLE_VISION_FALLBACK_FOR_DEV)
    }

    @Test
    fun releaseUrlRequiresHttps() {
        BackendConfig.requireSecureReleaseUrl("https://api.moling.app")
        assertThrows(IllegalArgumentException::class.java) {
            BackendConfig.requireSecureReleaseUrl("http://example.com")
        }
    }

    @Test
    fun baseUrlHasNoTrailingSlash() {
        assertEquals(BackendConfig.BASE_URL.trimEnd('/'), BackendConfig.BASE_URL)
    }

    @Test
    fun networkErrorsMapToSafeMessages() {
        val client = NotebookApiClient("https://api.moling.app")
        assertEquals(
            "\u56de\u5e94\u592a\u9891\u7e41\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5",
            client.parseFailure(429, "").reason
        )
        assertEquals(
            "\u6a21\u578b\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528",
            client.parseFailure(503, "").reason
        )
    }
}
