package com.moling.livingnotebook.data

import android.content.Context
import com.moling.livingnotebook.data.auth.AndroidKeystoreTokenStore
import com.moling.livingnotebook.data.auth.AuthSessionRepository
import com.moling.livingnotebook.data.local.MolingDatabase
import com.moling.livingnotebook.data.remote.BackendConfig
import com.moling.livingnotebook.data.remote.NotebookApiClient
import com.moling.livingnotebook.settings.SettingsRepository

class MolingAppContainer(context: Context) {
    val settingsRepository = SettingsRepository(context)
    private val database = MolingDatabase.get(context)
    val notebookRepository = NotebookRepository(database)
    val replyOutboxRepository = ReplyOutboxRepository(database)
    val apiClient = NotebookApiClient(BackendConfig.BASE_URL)
    val authSessionRepository = AuthSessionRepository(
        api = apiClient,
        tokenStore = AndroidKeystoreTokenStore(context),
        settingsRepository = settingsRepository
    )
    val profileRepository = ProfileRepository(
        auth = authSessionRepository,
        api = apiClient,
        settings = settingsRepository
    )
}
