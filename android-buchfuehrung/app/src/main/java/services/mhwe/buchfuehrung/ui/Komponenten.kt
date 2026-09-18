package services.mhwe.buchfuehrung.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Photo
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import services.mhwe.buchfuehrung.data.Buchung
import services.mhwe.buchfuehrung.data.BuchungsTyp
import services.mhwe.buchfuehrung.data.Mandant
import services.mhwe.buchfuehrung.ui.theme.betragsFarbe
import services.mhwe.buchfuehrung.util.Betrag
import services.mhwe.buchfuehrung.util.Datum

@Composable
fun MandantWaehler(
    mandanten: List<Mandant>,
    aktiver: Mandant?,
    onWahl: (Long) -> Unit,
    modifier: Modifier = Modifier
) {
    var offen by remember { mutableStateOf(false) }
    Box(modifier) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .clip(RoundedCornerShape(8.dp))
                .clickable(enabled = mandanten.size > 1) { offen = true }
                .padding(horizontal = 4.dp, vertical = 2.dp)
        ) {
            Text(
                text = aktiver?.name ?: "Kein Mandant",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            if (mandanten.size > 1) {
                Icon(Icons.Default.ArrowDropDown, contentDescription = "Mandant wechseln")
            }
        }
        DropdownMenu(expanded = offen, onDismissRequest = { offen = false }) {
            mandanten.forEach { mandant ->
                DropdownMenuItem(
                    text = { Text(mandant.name) },
                    onClick = {
                        onWahl(mandant.id)
                        offen = false
                    }
                )
            }
        }
    }
}

@Composable
fun ZeitraumWaehler(
    jahr: Int,
    monat: Int,
    titel: String,
    onJahr: (Int) -> Unit,
    onMonat: (Int) -> Unit,
    modifier: Modifier = Modifier
) {
    var offen by remember { mutableStateOf(false) }
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        IconButton(onClick = { zurueck(jahr, monat, onJahr, onMonat) }) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Zurück")
        }
        Box {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable { offen = true }
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(titel, style = MaterialTheme.typography.titleMedium)
                Icon(Icons.Default.ArrowDropDown, contentDescription = "Zeitraum wählen")
            }
            DropdownMenu(expanded = offen, onDismissRequest = { offen = false }) {
                DropdownMenuItem(
                    text = { Text("Ganzes Jahr $jahr") },
                    onClick = {
                        onMonat(GANZES_JAHR)
                        offen = false
                    }
                )
                HorizontalDivider()
                (1..12).forEach { m ->
                    DropdownMenuItem(
                        text = { Text("${Datum.monatsname(m)} $jahr") },
                        onClick = {
                            onMonat(m)
                            offen = false
                        }
                    )
                }
                HorizontalDivider()
                DropdownMenuItem(
                    text = { Text("Jahr ${jahr - 1}") },
                    onClick = {
                        onJahr(jahr - 1)
                        offen = false
                    }
                )
                DropdownMenuItem(
                    text = { Text("Jahr ${jahr + 1}") },
                    onClick = {
                        onJahr(jahr + 1)
                        offen = false
                    }
                )
            }
        }
        IconButton(onClick = { vor(jahr, monat, onJahr, onMonat) }) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Vorwärts")
        }
    }
}

private fun zurueck(jahr: Int, monat: Int, onJahr: (Int) -> Unit, onMonat: (Int) -> Unit) {
    when {
        monat == GANZES_JAHR -> onJahr(jahr - 1)
        monat == 1 -> {
            onJahr(jahr - 1)
            onMonat(12)
        }
        else -> onMonat(monat - 1)
    }
}

private fun vor(jahr: Int, monat: Int, onJahr: (Int) -> Unit, onMonat: (Int) -> Unit) {
    when {
        monat == GANZES_JAHR -> onJahr(jahr + 1)
        monat == 12 -> {
            onJahr(jahr + 1)
            onMonat(1)
        }
        else -> onMonat(monat + 1)
    }
}

@Composable
fun SummenKarte(
    beschriftung: String,
    betragRappen: Long,
    waehrung: String,
    farbe: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(
                beschriftung,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                "${Betrag.formatieren(betragRappen)} $waehrung",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = farbe
            )
        }
    }
}

@Composable
fun BuchungsZeile(
    buchung: Buchung,
    waehrung: String,
    onKlick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val istEinnahme = buchung.typ == BuchungsTyp.EINNAHME
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onKlick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Surface(
            color = if (istEinnahme) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.errorContainer
            },
            shape = RoundedCornerShape(6.dp),
            modifier = Modifier.width(4.dp).height(38.dp)
        ) {}
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(
                buchung.kategorie,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    Datum.formatieren(buchung.datum) +
                        if (buchung.text.isNotBlank()) " · ${buchung.text}" else "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        if (buchung.belegDatei != null) {
            Icon(
                Icons.Default.Photo,
                contentDescription = "Beleg vorhanden",
                modifier = Modifier.size(16.dp).padding(end = 2.dp),
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Text(
            text = "${if (istEinnahme) "+" else "−"}${Betrag.formatieren(buchung.betragRappen)}",
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.SemiBold,
            color = betragsFarbe(istEinnahme),
            modifier = Modifier.padding(start = 8.dp)
        )
    }
}

/** Waagrechter Balken fuer die Auswertung. */
@Composable
fun Balken(anteil: Float, farbe: Color, modifier: Modifier = Modifier) {
    Box(
        modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(RoundedCornerShape(3.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Box(
            Modifier
                .fillMaxWidth(anteil.coerceIn(0f, 1f))
                .height(6.dp)
                .clip(RoundedCornerShape(3.dp))
                .background(farbe)
        )
    }
}
