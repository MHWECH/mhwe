package services.mhwe.buchfuehrung.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import services.mhwe.buchfuehrung.ui.Balken
import services.mhwe.buchfuehrung.ui.BuchViewModel
import services.mhwe.buchfuehrung.ui.BuchungsZeile
import services.mhwe.buchfuehrung.ui.SummenKarte
import services.mhwe.buchfuehrung.ui.ZeitraumWaehler
import services.mhwe.buchfuehrung.ui.theme.betragsFarbe
import services.mhwe.buchfuehrung.util.Betrag

@Composable
fun UebersichtScreen(
    viewModel: BuchViewModel,
    onBuchungKlick: (Long) -> Unit,
    onAlleBuchungen: () -> Unit,
    modifier: Modifier = Modifier
) {
    val mandant by viewModel.aktiverMandant.collectAsState()
    val jahr by viewModel.jahr.collectAsState()
    val monat by viewModel.monat.collectAsState()
    val titel by viewModel.zeitraumTitel.collectAsState()
    val buchungen by viewModel.buchungen.collectAsState()
    val einnahmen by viewModel.summeEinnahmen.collectAsState()
    val ausgaben by viewModel.summeAusgaben.collectAsState()
    val saldo by viewModel.saldo.collectAsState()
    val waehrung = mandant?.waehrung ?: "CHF"

    LazyColumn(modifier.fillMaxSize()) {
        item {
            ZeitraumWaehler(
                jahr = jahr,
                monat = monat,
                titel = titel,
                onJahr = viewModel::jahrSetzen,
                onMonat = viewModel::monatSetzen,
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
            )
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                SummenKarte(
                    beschriftung = "Einnahmen",
                    betragRappen = einnahmen,
                    waehrung = waehrung,
                    farbe = betragsFarbe(true),
                    modifier = Modifier.weight(1f)
                )
                SummenKarte(
                    beschriftung = "Ausgaben",
                    betragRappen = ausgaben,
                    waehrung = waehrung,
                    farbe = betragsFarbe(false),
                    modifier = Modifier.weight(1f)
                )
            }
        }
        item {
            Card(Modifier.fillMaxWidth().padding(16.dp)) {
                Column(Modifier.padding(16.dp)) {
                    Text("Saldo", style = MaterialTheme.typography.labelMedium)
                    Text(
                        "${Betrag.formatieren(saldo, mitVorzeichen = true)} $waehrung",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        color = betragsFarbe(saldo >= 0)
                    )
                    val gesamt = (einnahmen + ausgaben).coerceAtLeast(1L)
                    Text(
                        "Anteil Ausgaben an allen Bewegungen",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 10.dp, bottom = 4.dp)
                    )
                    Balken(
                        anteil = ausgaben.toFloat() / gesamt.toFloat(),
                        farbe = betragsFarbe(false)
                    )
                }
            }
        }
        item {
            Row(
                Modifier.fillMaxWidth().padding(start = 16.dp, end = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    "Letzte Buchungen",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(top = 14.dp)
                )
                TextButton(onClick = onAlleBuchungen) { Text("Alle") }
            }
        }
        if (buchungen.isEmpty()) {
            item {
                Text(
                    "Noch keine Buchungen in diesem Zeitraum. Tippe auf das Plus, um die erste zu erfassen.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp)
                )
            }
        } else {
            items(buchungen.take(8), key = { it.id }) { buchung ->
                BuchungsZeile(
                    buchung = buchung,
                    waehrung = waehrung,
                    onKlick = { onBuchungKlick(buchung.id) }
                )
                HorizontalDivider()
            }
        }
        item { Column(Modifier.padding(40.dp)) {} }
    }
}
