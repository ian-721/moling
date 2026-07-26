package com.moling.livingnotebook.settings

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import java.io.IOException
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map

private val Context.molingSettingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "moling_settings"
)

class SettingsRepository(context: Context) {
    private val dataStore = context.applicationContext.molingSettingsDataStore

    val settings: Flow<MolingSettings> = dataStore.data
        .catch { error ->
            if (error is IOException) {
                emit(androidx.datastore.preferences.core.emptyPreferences())
            } else {
                throw error
            }
        }
        .map { preferences ->
            MolingSettings(
                replyFontSize = ReplyFontSizeOption.fromStoredValue(
                    preferences[Keys.ReplyFontSize]
                ),
                selectedFontAssetPath = preferences[Keys.SelectedFontAssetPath]
                    ?.takeIf { it.isNotBlank() && it != FontOption.Default.id },
                paperBackground = PaperBackgroundOption.fromStoredValue(
                    preferences[Keys.PaperBackground]
                ),
                showDebugInfo = preferences[Keys.ShowDebugInfo] ?: true,
                assistantName = normalizeAssistantName(preferences[Keys.AssistantName]),
                installationId = preferences[Keys.InstallationId]
            )
        }

    suspend fun setReplyFontSize(option: ReplyFontSizeOption) {
        dataStore.edit { preferences ->
            preferences[Keys.ReplyFontSize] = option.name
        }
    }

    suspend fun setSelectedFontAssetPath(assetPath: String?) {
        dataStore.edit { preferences ->
            if (assetPath.isNullOrBlank() || assetPath == FontOption.Default.id) {
                preferences.remove(Keys.SelectedFontAssetPath)
            } else {
                preferences[Keys.SelectedFontAssetPath] = assetPath
            }
        }
    }

    suspend fun setPaperBackground(option: PaperBackgroundOption) {
        dataStore.edit { preferences ->
            preferences[Keys.PaperBackground] = option.name
        }
    }

    suspend fun setShowDebugInfo(show: Boolean) {
        dataStore.edit { preferences ->
            preferences[Keys.ShowDebugInfo] = show
        }
    }

    suspend fun setAssistantName(name: String?) {
        dataStore.edit { preferences ->
            preferences[Keys.AssistantName] = normalizeAssistantName(name)
        }
    }

    suspend fun getOrCreateInstallationId(): String {
        var resolved = ""
        dataStore.edit { preferences ->
            resolved = preferences[Keys.InstallationId].orEmpty()
            if (resolved.isBlank()) {
                resolved = UUID.randomUUID().toString()
                preferences[Keys.InstallationId] = resolved
            }
        }
        return resolved
    }

    suspend fun rotateInstallationId(): String {
        val installationId = UUID.randomUUID().toString()
        dataStore.edit { preferences ->
            preferences[Keys.InstallationId] = installationId
        }
        return installationId
    }

    suspend fun clearIdentityProfile() {
        dataStore.edit { preferences ->
            preferences.remove(Keys.AssistantName)
        }
    }

    private object Keys {
        val ReplyFontSize = stringPreferencesKey("reply_font_size")
        val SelectedFontAssetPath = stringPreferencesKey("selected_font_asset_path")
        val PaperBackground = stringPreferencesKey("paper_background")
        val ShowDebugInfo = booleanPreferencesKey("show_debug_info")
        val AssistantName = stringPreferencesKey("assistant_name")
        val InstallationId = stringPreferencesKey("installation_id")
    }
}
