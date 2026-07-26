package com.moling.livingnotebook.viewmodel

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Test

class RequestStateTest {
    @Test
    fun staleResponseCannotReplaceActiveRequest() {
        assertTrue(shouldApplyResponse("current", "current"))
        assertFalse(shouldApplyResponse("current", "older"))
        assertFalse(shouldApplyResponse(null, "older"))
    }

    @Test
    fun recentContextUsesCurrentAssistantNameInsteadOfHardcodedDefault() {
        val context = formatRecentContext(
            listOf(NotebookTurn("用户内容", "回应")),
            "小墨"
        )
        assertEquals("我写：用户内容\n小墨：回应", context)
        assertFalse(context!!.contains("墨灵："))
    }
}
