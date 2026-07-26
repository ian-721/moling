package com.moling.livingnotebook.data

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.moling.livingnotebook.data.local.LocalRequestState
import com.moling.livingnotebook.data.local.MolingDatabase
import com.moling.livingnotebook.drawing.Stroke
import com.moling.livingnotebook.drawing.StrokePoint
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class LocalPersistenceTest {
    private lateinit var database: MolingDatabase
    private lateinit var notebook: NotebookRepository
    private lateinit var outbox: ReplyOutboxRepository

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        database = Room.inMemoryDatabaseBuilder(
            context,
            MolingDatabase::class.java
        ).allowMainThreadQueries().build()
        notebook = NotebookRepository(database) { 1_000L }
        outbox = ReplyOutboxRepository(database) { 1_000L }
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun strokeRoundTripPreservesCoordinatesTimestampAndPressure() = runBlocking {
        val stroke = Stroke(
            id = "stroke-one",
            points = listOf(
                StrokePoint(1.5f, 2.5f, timestamp = 42L, pressure = 0.7f)
            ),
            color = 123L,
            width = 4.5f
        )
        notebook.persistStroke("page", stroke)

        val restored = notebook.restore("page").strokes.single()
        assertEquals(stroke, restored)
        assertEquals(1, database.openHelper.readableDatabase.version)
    }

    @Test
    fun successIsPersistedBeforeAbsorbAndOnlySnapshotStrokesAreDeleted() =
        runBlocking {
            val sent = stroke("sent")
            notebook.persistStroke("page", sent)
            outbox.createSnapshot("request-one", "page", listOf(sent.id))
            outbox.markRecognized("request-one", "旧内容", "mlkit")
            outbox.markSending("request-one")

            val writtenDuringReply = stroke("new")
            notebook.persistStroke("page", writtenDuringReply)
            outbox.markSucceeded(
                "request-one",
                "回应",
                "execution",
                "normal"
            )
            assertEquals(
                "回应",
                notebook.restore("page").latestReply
            )

            outbox.absorb("request-one")
            val restored = notebook.restore("page")
            assertEquals(listOf("new"), restored.strokes.map { it.id })
            assertTrue(restored.turns.any { it.aiReply == "回应" })
        }

    @Test
    fun failureAndProcessRestartKeepStrokesAndRequestIdForRetry() = runBlocking {
        val failedStroke = stroke("failed")
        notebook.persistStroke("page", failedStroke)
        outbox.createSnapshot("same-request", "page", listOf(failedStroke.id))
        outbox.markRecognized("same-request", "内容", "mlkit")
        outbox.markSending("same-request")

        // restore() converts interrupted SENDING to a retryable durable outbox.
        assertNotNull(notebook.restore("page"))
        val pending = outbox.pending("page")
        assertEquals("same-request", pending?.requestId)
        assertEquals(LocalRequestState.RETRYABLE_FAILED, pending?.state)
        assertEquals(listOf("failed"), notebook.restore("page").strokes.map { it.id })

        outbox.markFailure(
            "same-request",
            "network_error",
            retryable = true
        )
        assertEquals(listOf("failed"), notebook.restore("page").strokes.map { it.id })
    }

    @Test
    fun undoAndClearAreBackedByDatabase() = runBlocking {
        notebook.persistStroke("page", stroke("one"))
        notebook.persistStroke("page", stroke("two"))
        assertEquals("two", notebook.undo("page"))
        assertEquals(listOf("one"), notebook.restore("page").strokes.map { it.id })
        notebook.clearEditable("page")
        assertTrue(notebook.restore("page").strokes.isEmpty())
    }

    private fun stroke(id: String) = Stroke(
        id = id,
        points = listOf(StrokePoint(1f, 2f, timestamp = 3L, pressure = 0.5f))
    )
}
