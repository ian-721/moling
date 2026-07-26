package com.moling.livingnotebook.settings

import org.junit.Assert.assertEquals
import org.junit.Test

class MolingSettingsTest {
    @Test
    fun invalidAssistantNameFallsBackToMoling() {
        assertEquals(DEFAULT_ASSISTANT_NAME, normalizeAssistantName("  "))
        assertEquals(DEFAULT_ASSISTANT_NAME, normalizeAssistantName("\n"))
    }

    @Test
    fun validAssistantNameIsPreserved() {
        assertEquals("\u8001g", normalizeAssistantName("  \u8001g  "))
    }
}
