package com.moling.livingnotebook.data

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.moling.livingnotebook.data.local.LocalRequestState
import com.moling.livingnotebook.data.local.MolingDatabase
import com.moling.livingnotebook.drawing.Stroke
import com.moling.livingnotebook.drawing.StrokePoint
import com.moling.livingnotebook.viewmodel.NotebookViewModel
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
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
        assertEquals(2, database.openHelper.readableDatabase.version)
    }

    @Test
    fun successIsPersistedBeforeAbsorbAndOnlySnapshotStrokesAreDeleted() =
        runBlocking {
            val sent = stroke("sent")
            notebook.persistStroke("page", sent)
            outbox.createSnapshot("request-one", "page", listOf(sent.id))
            outbox.markRecognized(
                "request-one",
                "旧内容",
                "mlkit",
                "原上下文",
                false
            )
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
        outbox.markRecognized(
            "same-request",
            "内容",
            "mlkit",
            "冻结上下文",
            false
        )
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
    fun processRestartReturnsInterruptedStrokesToEditableState() = runBlocking {
        val interrupted = stroke("interrupted")
        notebook.persistStroke("page", interrupted)
        outbox.createSnapshot("restart-request", "page", listOf(interrupted.id))
        outbox.markRecognized(
            "restart-request",
            "内容",
            "mlkit",
            null,
            false
        )
        outbox.markSending("restart-request")

        notebook.restore("page")

        assertEquals("interrupted", notebook.undo("page"))
        assertTrue(notebook.restore("page").strokes.isEmpty())
        assertEquals(
            LocalRequestState.RETRYABLE_FAILED,
            outbox.pending("page")?.state
        )
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

    @Test
    fun pendingWriteBarrierProtectsSnapshot() = runBlocking {
        val gate = CompletableDeferred<Unit>()
        val delayed = NotebookRepository(
            database,
            clock = { 1_000L },
            beforeStrokeWrite = { gate.await() }
        )
        val queued = delayed.enqueueStroke("page", stroke("queued"))
        val snapshot = async(Dispatchers.Default) {
            delayed.awaitPendingStrokeWrites().getOrThrow()
            outbox.createSnapshot("queued-request", "page", listOf("queued"))
        }
        assertFalse(queued.isCompleted)
        assertFalse(snapshot.isCompleted)

        gate.complete(Unit)
        queued.await().getOrThrow()
        snapshot.await()
        assertEquals(
            listOf("queued"),
            delayed.restore("page").strokes.map { it.id }
        )
    }

    @Test
    fun immediateUndoWaitsForPendingWriteThenRemovesNewestStroke() = runBlocking {
        val gate = CompletableDeferred<Unit>()
        val delayed = NotebookRepository(
            database,
            beforeStrokeWrite = { gate.await() }
        )
        delayed.enqueueStroke("page", stroke("undo-pending"))
        val undoing = async(Dispatchers.Default) {
            delayed.awaitPendingStrokeWrites().getOrThrow()
            delayed.undo("page")
        }
        assertFalse(undoing.isCompleted)
        gate.complete(Unit)
        assertEquals("undo-pending", undoing.await())
        assertTrue(delayed.restore("page").strokes.isEmpty())
    }

    @Test
    fun immediateClearWaitsForPendingWriteThenClearsIt() = runBlocking {
        val gate = CompletableDeferred<Unit>()
        val delayed = NotebookRepository(
            database,
            beforeStrokeWrite = { gate.await() }
        )
        delayed.enqueueStroke("page", stroke("clear-pending"))
        val clearing = async(Dispatchers.Default) {
            delayed.awaitPendingStrokeWrites().getOrThrow()
            delayed.clearEditable("page")
        }
        assertFalse(clearing.isCompleted)
        gate.complete(Unit)
        clearing.await()
        assertTrue(delayed.restore("page").strokes.isEmpty())
    }

    @Test
    fun endStrokeThenImmediateReplyWaitsForDurableStroke() = runBlocking {
        val gate = CompletableDeferred<Unit>()
        val delayed = NotebookRepository(
            database,
            clock = { 1_000L },
            beforeStrokeWrite = { gate.await() }
        )
        val viewModel = NotebookViewModel(delayed, outbox, "page")
        viewModel.beginStroke(1f, 2f)
        viewModel.appendPoint(3f, 4f)
        viewModel.endStroke()

        val preparing = async(Dispatchers.Default) { viewModel.prepareReply() }
        assertFalse(preparing.isCompleted)
        gate.complete(Unit)
        val prepared = preparing.await()
        assertNotNull(prepared)
        assertEquals(
            prepared?.strokeIds,
            database.notebookDao().strokes("page").map { it.strokeId }
        )
    }

    @Test
    fun failedStrokeWriteBlocksSnapshotInsteadOfPretendingItPersisted() {
        runBlocking {
            val failed = NotebookRepository(
                database,
                beforeStrokeWrite = { error("disk full") }
            )
            failed.enqueueStroke("page", stroke("lost")).await()
            assertTrue(failed.awaitPendingStrokeWrites().isFailure)
            assertThrows(IllegalArgumentException::class.java) {
                runBlocking {
                    outbox.createSnapshot(
                        "must-not-send",
                        "page",
                        listOf("lost")
                    )
                }
            }
        }
    }

    @Test
    fun retryPayloadRemainsFrozenAcrossContextChangesAndRestart() = runBlocking {
        notebook.persistStroke("page", stroke("frozen"))
        outbox.createSnapshot("frozen-request", "page", listOf("frozen"))
        outbox.markRecognized(
            "frozen-request",
            "第一次识别",
            "mlkit",
            "改名前的上下文",
            true
        )
        outbox.markSending("frozen-request")
        outbox.markFailure("frozen-request", "network_error", retryable = true)

        val retry = ReplyOutboxRepository(database) { 9_999L }.pending("page")
        assertEquals("frozen-request", retry?.requestId)
        assertEquals("第一次识别", retry?.recognizedText)
        assertEquals("mlkit", retry?.recognitionSource)
        assertEquals("改名前的上下文", retry?.recentContext)
        assertEquals(true, retry?.deepMode)
        assertEquals(true, retry?.payloadFrozen)
    }

    @Test
    fun permanentFailureAllowsNewUserActionWithNewRequestId() = runBlocking {
        notebook.persistStroke("page", stroke("retry-new-id"))
        outbox.createSnapshot(
            "permanent-request",
            "page",
            listOf("retry-new-id")
        )
        outbox.markFailure(
            "permanent-request",
            "idempotency_conflict",
            retryable = false
        )
        assertEquals(null, outbox.pending("page"))

        outbox.createSnapshot(
            "new-user-action",
            "page",
            listOf("retry-new-id")
        )
        assertEquals("new-user-action", outbox.pending("page")?.requestId)
    }

    private fun stroke(id: String) = Stroke(
        id = id,
        points = listOf(StrokePoint(1f, 2f, timestamp = 3L, pressure = 0.5f))
    )
}
