package com.moling.livingnotebook.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [
        PageEntity::class,
        StrokeEntity::class,
        NotebookTurnEntity::class,
        ReplyOutboxEntity::class
    ],
    version = 1,
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
                ).build().also { instance = it }
            }
    }
}
