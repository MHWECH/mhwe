package services.mhwe.buchfuehrung.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import services.mhwe.buchfuehrung.ui.BuchViewModel
import services.mhwe.buchfuehrung.ui.BuchungsZeile
import services.mhwe.buchfuehrung.ui.ZeitraumWaehler

@Composable
fun BuchungenScreen(
    viewModel: BuchViewModel,
    onBuchungKlick: (Long) -> Unit,
    modifier: Modifier = Modifier
) {
    val mandant by viewModel.aktiverMandant.collectAsState()
    val jahr by viewModel.jahr.collectAsState()
    val monat by viewModel.monat.collectAsState()
    val titel by viewModel.zeitraumTitel.collectAsState()
    val buchungen by viewModel.buchungen.collectAsState()
    var suche by remember { mutableStateOf("") }

    val gefiltert = remember(buchungen, suche) {
        if (suche.isBlank()) {
            buchungen
        } else {
            val begriff = suche.trim().lowercase()
            buchungen.filter {
                it.kategorie.lowercase().contains(begriff) ||
                    it.text.lowercase().contains(begriff) ||
                    it.zahlungsart.lowercase().contains(begriff)
            }
        }
    }

    Column(modifier.fillMaxSize()) {
        ZeitraumWaehler(
            jahr = jahr,
            monat = monat,
            titel = titel,
            onJahr = viewModel::jahrSetzen,
            onMonat = viewModel::monatSetzen,
            modifier = Modifier.padding(horizontal = 8.dp)
        )
        OutlinedTextField(
            value = suche,
            onValueChange = { suche = it },
            label = { Text("Suchen") },
            singleLine = true,
            leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
            trailingIcon = {
                if (suche.isNotEmpty()) {
                    IconButton(onClick = { suche = "" }) {
                        Icon(Icons.Default.Close, contentDescription = "Suche löschen")
                    }
                }
            },
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)
        )
        if (gefiltert.isEmpty()) {
            Text(
                if (suche.isBlank()) {
                    "Keine Buchungen in diesem Zeitraum."
                } else {
                    "Nichts gefunden für \"$suche\"."
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(16.dp)
            )
        } else {
            LazyColumn(Modifier.fillMaxSize()) {
                items(gefiltert, key = { it.id }) { buchung ->
                    BuchungsZeile(
                        buchung = buchung,
                        waehrung = mandant?.waehrung ?: "CHF",
                        onKlick = { onBuchungKlick(buchung.id) }
                    )
                    HorizontalDivider()
                }
                item { Column(Modifier.padding(40.dp)) {} }
            }
        }
    }
}
