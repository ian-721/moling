package com.moling.livingnotebook.ui.components

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun InkToolbar(
    onClear: () -> Unit,
    onUndo: () -> Unit,
    onRespond: () -> Unit,
    isLoading: Boolean = false,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 32.dp, vertical = 16.dp),
        horizontalArrangement = Arrangement.SpaceEvenly
    ) {
        TextButton(onClick = onClear) { Text("清空") }
        TextButton(onClick = onUndo) { Text("撤销") }
        TextButton(onClick = onRespond, enabled = !isLoading) {
            Text(if (isLoading) "聆听中..." else "回应")
        }
    }
}
