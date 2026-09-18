package services.mhwe.buchfuehrung

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import services.mhwe.buchfuehrung.ui.BuchfuehrungApp
import services.mhwe.buchfuehrung.ui.theme.BuchfuehrungTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            BuchfuehrungTheme {
                BuchfuehrungApp()
            }
        }
    }
}
