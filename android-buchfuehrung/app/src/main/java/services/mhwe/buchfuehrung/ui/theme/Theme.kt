package services.mhwe.buchfuehrung.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Gruen = Color(0xFF0F5132)
val GruenHell = Color(0xFF2E7D52)
val Rot = Color(0xFFB3261E)
val RotHell = Color(0xFFE57373)

private val HellesSchema = lightColorScheme(
    primary = Gruen,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFCDEBDA),
    onPrimaryContainer = Color(0xFF042314),
    secondary = Color(0xFF4E6355),
    background = Color(0xFFF7F9F7),
    surface = Color.White,
    error = Rot
)

private val DunklesSchema = darkColorScheme(
    primary = Color(0xFF7FD3A5),
    onPrimary = Color(0xFF00391F),
    primaryContainer = Color(0xFF175339),
    onPrimaryContainer = Color(0xFFCDEBDA),
    secondary = Color(0xFFB4CCBC),
    background = Color(0xFF101410),
    surface = Color(0xFF1A1F1B),
    error = RotHell
)

/** Farbe fuer Betraege: Einnahmen gruen, Ausgaben rot. */
@Composable
fun betragsFarbe(istEinnahme: Boolean): Color {
    val dunkel = isSystemInDarkTheme()
    return when {
        istEinnahme && dunkel -> Color(0xFF7FD3A5)
        istEinnahme -> GruenHell
        dunkel -> RotHell
        else -> Rot
    }
}

@Composable
fun BuchfuehrungTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DunklesSchema else HellesSchema,
        content = content
    )
}
