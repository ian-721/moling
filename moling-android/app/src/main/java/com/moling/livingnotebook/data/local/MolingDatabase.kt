package com.moling.livingnotebook.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

@Database(
    entities = [
        PageEntity::class,
        StrokeEntity::class,
        NotebookTurnEntity::class,
        ReplyOutboxEntity::class
    ],
    version = 2,
    exportSchema = true
)
abstract class MolingDatabase : RoomDatabase() {
    abstract fun notebookDao(): NotebookDao

    companion object {
        @Volatile
        private var instance: MolingDatabase? = null

        fun get(context: Context): MolingDatabase =
            instance ?: synchronized(this) {
                instance ?: Room.databaseBuilder(
                    context.applicationContext,
                    MolingDatabase::class.java,
                    "moling_notebook.db"
                ).addMigrations(MIGRATION_1_2)
                    .build()
                    .also { instance = it }
            }

        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "ALTER TABLE reply_outbox ADD COLUMN " +
                        "recognizedText TEXT NOT NULL DEFAULT ''"
                )
                db.execSQL(
                    "ALTER TABLE reply_outbox ADD COLUMN " +
                        "recognitionSource TEXT NOT NULL DEFAULT ''"
                )
                db.execSQL(
                    "ALTER TABLE reply_outbox ADD COLUMN recentContext TEXT"
                )
                db.execSQL(
                    "ALTER TABLE reply_outbox ADD COLUMN " +
                        "deepMode INTEGER NOT NULL DEFAULT 0"
                )
                db.execSQL(
                    "ALTER TABLE reply_outbox ADD COLUMN " +
                        "payloadFrozen INTEGER NOT NULL DEFAULT 0"
                )
                db.execSQL(
                    "ALTER TABLE reply_outbox ADD COLUMN " +
                        "isReplayable INTEGER NOT NULL DEFAULT 1"
                )
                db.execSQL(
                    "UPDATE reply_outbox SET " +
                        "recognizedText = COALESCE((" +
                        "SELECT recognizedText FROM notebook_turns " +
                        "WHERE notebook_turns.requestId = reply_outbox.requestId" +
                        "), ''), " +
                        "recognitionSource = COALESCE((" +
                        "SELECT recognitionSource FROM notebook_turns " +
                        "WHERE notebook_turns.requestId = reply_outbox.requestId" +
                        "), '')"
                )
                db.execSQL(
                    "UPDATE reply_outbox SET payloadFrozen = 1 " +
                        "WHERE recognizedText <> ''"
                )
            }
        }
    }
}
