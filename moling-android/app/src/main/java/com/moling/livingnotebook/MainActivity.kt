package com.moling.livingnotebook

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.ui.Modifier
import com.moling.livingnotebook.ui.NotebookPageScreen
import com.moling.livingnotebook.ui.theme.MolingTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MolingTheme {
                Scaffold(modifier = Modifier.fillMaxSize()) { innerPadding ->
                    NotebookPageScreen(modifier = Modifier.padding(innerPadding))
                }
            }
        }
    }
}
