package com.moling.livingnotebook.data.local

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class RoomMigrationTest {
    @Test
    fun migration1To2PreservesOutboxAndPassesRoomSchemaValidation() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val name = "migration-1-2.db"
        context.deleteDatabase(name)
        val path = context.getDatabasePath(name)
        path.parentFile?.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(path, null).use { legacy ->
            legacy.execSQL(
                "CREATE TABLE pages (pageId TEXT NOT NULL PRIMARY KEY, " +
                    "createdAt INTEGER NOT NULL, updatedAt INTEGER NOT NULL, " +
                    "state TEXT NOT NULL)"
            )
            legacy.execSQL(
                "CREATE TABLE strokes (strokeId TEXT NOT NULL PRIMARY KEY, " +
                    "pageId TEXT NOT NULL, strokeOrder INTEGER NOT NULL, " +
                    "pointsJson TEXT NOT NULL, color INTEGER NOT NULL, " +
                    "width REAL NOT NULL, createdAt INTEGER NOT NULL, " +
                    "state TEXT NOT NULL, FOREIGN KEY(pageId) REFERENCES " +
                    "pages(pageId) ON UPDATE NO ACTION ON DELETE CASCADE)"
            )
            legacy.execSQL(
                "CREATE INDEX index_strokes_pageId ON strokes(pageId)"
            )
            legacy.execSQL(
                "CREATE UNIQUE INDEX index_strokes_pageId_strokeOrder " +
                    "ON strokes(pageId, strokeOrder)"
            )
            legacy.execSQL(
                "CREATE TABLE notebook_turns (turnId TEXT NOT NULL PRIMARY KEY, " +
                    "pageId TEXT NOT NULL, requestId TEXT NOT NULL, " +
                    "recognizedText TEXT NOT NULL, recognitionSource TEXT NOT NULL, " +
                    "aiReply TEXT, replyMode TEXT, safetyLevel TEXT, " +
                    "state TEXT NOT NULL, createdAt INTEGER NOT NULL, " +
                    "updatedAt INTEGER NOT NULL, FOREIGN KEY(pageId) REFERENCES " +
                    "pages(pageId) ON UPDATE NO ACTION ON DELETE CASCADE)"
            )
            legacy.execSQL(
                "CREATE INDEX index_notebook_turns_pageId ON notebook_turns(pageId)"
            )
            legacy.execSQL(
                "CREATE UNIQUE INDEX index_notebook_turns_requestId " +
                    "ON notebook_turns(requestId)"
            )
            legacy.execSQL(
                "CREATE TABLE reply_outbox (requestId TEXT NOT NULL PRIMARY KEY, " +
                    "pageId TEXT NOT NULL, strokeIdsJson TEXT NOT NULL, " +
                    "state TEXT NOT NULL, attemptCount INTEGER NOT NULL, " +
                    "lastErrorCategory TEXT, nextRetryAt INTEGER, " +
                    "createdAt INTEGER NOT NULL, updatedAt INTEGER NOT NULL, " +
                    "FOREIGN KEY(pageId) REFERENCES pages(pageId) " +
                    "ON UPDATE NO ACTION ON DELETE CASCADE)"
            )
            legacy.execSQL(
                "CREATE INDEX index_reply_outbox_pageId ON reply_outbox(pageId)"
            )
            legacy.execSQL(
                "CREATE INDEX index_reply_outbox_state ON reply_outbox(state)"
            )
            legacy.execSQL(
                "CREATE TABLE room_master_table " +
                    "(id INTEGER PRIMARY KEY, identity_hash TEXT)"
            )
            legacy.execSQL(
                "INSERT INTO room_master_table VALUES " +
                    "(42, 'e446ac8b7105a0cf45d66dc4aa7f1564')"
            )
            legacy.execSQL("INSERT INTO pages VALUES ('page', 1, 1, 'ACTIVE')")
            legacy.execSQL(
                "INSERT INTO strokes VALUES " +
                    "('stroke', 'page', 1, '[]', 1, 2.0, 1, 'ACTIVE')"
            )
            legacy.execSQL(
                "INSERT INTO notebook_turns VALUES " +
                    "('turn', 'page', 'request-old', '旧文本', 'mlkit', " +
                    "NULL, NULL, NULL, 'READY_TO_SEND', 1, 1)"
            )
            legacy.execSQL(
                "INSERT INTO reply_outbox VALUES " +
                    "('request-old', 'page', '[\"stroke\"]', " +
                    "'READY_TO_SEND', 0, NULL, NULL, 1, 1)"
            )
            legacy.version = 1
        }

        val room = Room.databaseBuilder(context, MolingDatabase::class.java, name)
            .addMigrations(MolingDatabase.MIGRATION_1_2)
            .allowMainThreadQueries()
            .build()
        room.openHelper.writableDatabase.query(
            "SELECT recognizedText, recognitionSource, recentContext, " +
                "deepMode, payloadFrozen, isReplayable " +
                "FROM reply_outbox WHERE requestId='request-old'"
        ).use { cursor ->
            cursor.moveToFirst()
            assertEquals("旧文本", cursor.getString(0))
            assertEquals("mlkit", cursor.getString(1))
            assertEquals(null, cursor.getString(2))
            assertEquals(0, cursor.getInt(3))
            assertEquals(1, cursor.getInt(4))
            assertEquals(1, cursor.getInt(5))
        }
        val dao = room.notebookDao()
        kotlinx.coroutines.runBlocking {
            assertEquals("page", dao.page("page")?.pageId)
            assertEquals(listOf("stroke"), dao.strokes("page").map { it.strokeId })
            assertEquals("旧文本", dao.turns("page").single().recognizedText)
            assertEquals("request-old", dao.pendingOutbox("page")?.requestId)
        }
        room.close()
        context.deleteDatabase(name)
    }
}
