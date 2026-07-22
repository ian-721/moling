package com.moling.livingnotebook.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.moling.livingnotebook.settings.FontOption
import com.moling.livingnotebook.settings.MolingSettings
import com.moling.livingnotebook.settings.PaperBackgroundOption
import com.moling.livingnotebook.settings.ReplyFontSizeOption

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun SettingsSheet(
    settings: MolingSettings,
    fontOptions: List<FontOption>,
    onReplyFontSizeChange: (ReplyFontSizeOption) -> Unit,
    onFontChange: (String?) -> Unit,
    onPaperBackgroundChange: (PaperBackgroundOption) -> Unit,
    onShowDebugInfoChange: (Boolean) -> Unit,
    onDismiss: () -> Unit
) {
    val availableFontPaths = fontOptions.mapNotNull { it.assetPath }.toSet()
    val selectedFontAssetPath = settings.selectedFontAssetPath
        ?.takeIf { it in availableFontPaths }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp)
                .padding(bottom = 28.dp)
        ) {
            Text(
                text = "\u8bbe\u7f6e",
                style = MaterialTheme.typography.titleLarge
            )
            Spacer(modifier = Modifier.height(18.dp))

            SettingSection(title = "\u58a8\u5b57\u5927\u5c0f") {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    ReplyFontSizeOption.entries.forEach { option ->
                        FilterChip(
                            selected = settings.replyFontSize == option,
                            onClick = { onReplyFontSizeChange(option) },
                            label = { Text("${option.label} ${option.sizeSp}sp") }
                        )
                    }
                }
            }

            SettingSection(title = "AI \u56de\u590d\u5b57\u4f53") {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    fontOptions.forEach { option ->
                        FilterChip(
                            selected = selectedFontAssetPath == option.assetPath,
                            onClick = { onFontChange(option.assetPath) },
                            label = { Text(option.displayName) }
                        )
                    }
                }
            }

            SettingSection(title = "\u7eb8\u8272") {
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    PaperBackgroundOption.entries.forEach { option ->
                        FilterChip(
                            selected = settings.paperBackground == option,
                            onClick = { onPaperBackgroundChange(option) },
                            label = { Text(option.label) }
                        )
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "\u8bc6\u522b\u75d5\u8ff9",
                        style = MaterialTheme.typography.titleMedium
                    )
                    Text(
                        text = "\u663e\u793a\u8bc6\u522b\u6765\u6e90\u548c\u8bc6\u522b\u6587\u672c",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Switch(
                    checked = settings.showDebugInfo,
                    onCheckedChange = onShowDebugInfoChange
                )
            }
        }
    }
}

@Composable
private fun SettingSection(
    title: String,
    content: @Composable () -> Unit
) {
    Column(modifier = Modifier.padding(bottom = 22.dp)) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(bottom = 10.dp)
        )
        content()
    }
}
