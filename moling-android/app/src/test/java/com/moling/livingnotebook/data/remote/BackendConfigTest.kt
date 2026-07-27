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
        BackendConfig.requireSecureReleaseUrl("https://release.invalid")
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
        val client = NotebookApiClient("https://release.invalid")
        assertEquals(
            "\u56de\u5e94\u592a\u9891\u7e41\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5",
            client.parseFailure(429, "").reason
        )
        assertEquals(
            "\u6a21\u578b\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528",
            client.parseFailure(503, "").reason
        )
    }

    @Test
    fun onlyTransient409IsRetryable() {
        val client = NotebookApiClient("https://release.invalid")
        fun failure(code: String) = client.parseFailure(
            409,
            """{"detail":{"code":"$code","message":"conflict"}}"""
        )

        assertEquals("request_in_progress", failure("request_in_progress").code)
        assertTrue(failure("request_in_progress").retryable)
        assertFalse(failure("idempotency_conflict").retryable)
        assertFalse(failure("request_permanently_failed").retryable)
        assertFalse(failure("request_attempt_limit_exceeded").retryable)
        assertFalse(failure("request_outcome_unknown").retryable)
    }
}
