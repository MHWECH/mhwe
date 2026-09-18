package services.mhwe.buchfuehrung.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import services.mhwe.buchfuehrung.data.Buchung
import services.mhwe.buchfuehrung.data.BuchungsTyp
import services.mhwe.buchfuehrung.ui.Balken
import services.mhwe.buchfuehrung.ui.BuchViewModel
import services.mhwe.buchfuehrung.ui.ZeitraumWaehler
import services.mhwe.buchfuehrung.ui.theme.betragsFarbe
import services.mhwe.buchfuehrung.util.Betrag

private data class KategorieSumme(val name: String, val summe: Long)

@Composable
fun AuswertungScreen(
    viewModel: BuchViewModel,
    modifier: Modifier = Modifier
) {
    val mandant by viewModel.aktiverMandant.collectAsState()
    val jahr by viewModel.jahr.collectAsState()
    val monat by viewModel.monat.collectAsState()
    val titel by viewModel.zeitraumTitel.collectAsState()
    val buchungen by viewModel.buchungen.collectAsState()
    val waehrung = mandant?.waehrung ?: "CHF"

    val ausgaben = remember(buchungen) { summieren(buchungen, BuchungsTyp.AUSGABE) }
    val einnahmen = remember(buchungen) { summieren(buchungen, BuchungsTyp.EINNAHME) }

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
        if (buchungen.isEmpty()) {
            item {
                Text(
                    "Für diesen Zeitraum gibt es noch nichts auszuwerten.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp)
                )
            }
        }
        abschnitt("Ausgaben nach Kategorie", ausgaben, waehrung, false)
        abschnitt("Einnahmen nach Kategorie", einnahmen, waehrung, true)
        item { Column(Modifier.padding(40.dp)) {} }
    }
}

private fun summieren(buchungen: List<Buchung>, typ: BuchungsTyp): List<KategorieSumme> =
    buchungen.filter { it.typ == typ }
        .groupBy { it.kategorie }
        .map { (name, liste) -> KategorieSumme(name, liste.sumOf { it.betragRappen }) }
        .sortedByDescending { it.summe }

private fun androidx.compose.foundation.lazy.LazyListScope.abschnitt(
    ueberschrift: String,
    eintraege: List<KategorieSumme>,
    waehrung: String,
    istEinnahme: Boolean
) {
    if (eintraege.isEmpty()) return
    val gesamt = eintraege.sumOf { it.summe }.coerceAtLeast(1L)
    item {
        Text(
            ueberschrift,
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 18.dp, bottom = 6.dp)
        )
    }
    items(eintraege.size, key = { "$ueberschrift-${eintraege[it].name}" }) { index ->
        val eintrag = eintraege[index]
        val anteil = eintrag.summe.toFloat() / gesamt.toFloat()
        Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(eintrag.name, style = MaterialTheme.typography.bodyMedium)
                Text(
                    "${Betrag.formatieren(eintrag.summe)} $waehrung",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
            Balken(
                anteil = anteil,
                farbe = betragsFarbe(istEinnahme),
                modifier = Modifier.padding(top = 6.dp)
            )
            Text(
                "${Math.round(anteil * 100)} %",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
    }
}
