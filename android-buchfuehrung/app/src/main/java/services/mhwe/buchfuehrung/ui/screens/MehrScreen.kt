package services.mhwe.buchfuehrung.ui.screens

import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.PictureAsPdf
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import services.mhwe.buchfuehrung.data.BuchungsTyp
import services.mhwe.buchfuehrung.data.Mandant
import services.mhwe.buchfuehrung.export.Teilen
import services.mhwe.buchfuehrung.ui.BuchViewModel

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun MehrScreen(
    viewModel: BuchViewModel,
    modifier: Modifier = Modifier
) {
    val kontext = LocalContext.current
    val mandanten by viewModel.mandanten.collectAsState()
    val aktiver by viewModel.aktiverMandant.collectAsState()
    val kategorien by viewModel.kategorien.collectAsState()
    val zeitraum by viewModel.zeitraumTitel.collectAsState()

    var neuerMandantDialog by remember { mutableStateOf(false) }
    var zuLoeschen by remember { mutableStateOf<Mandant?>(null) }
    var neueKategorieTyp by remember { mutableStateOf<BuchungsTyp?>(null) }

    Column(
        modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // ── Export ───────────────────────────────────────────────────────────
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Export", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "Zeitraum: $zeitraum · Mandant: ${aktiver?.name ?: "–"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 2.dp, bottom = 12.dp)
                )
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    FilledTonalButton(
                        onClick = {
                            viewModel.exportieren(alsPdf = false) { datei ->
                                if (datei == null) {
                                    Toast.makeText(kontext, "Keine Buchungen im Zeitraum", Toast.LENGTH_SHORT).show()
                                } else {
                                    Teilen.datei(kontext, datei, "Buchhaltung $zeitraum")
                                }
                            }
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.Description, contentDescription = null)
                        Text("  CSV")
                    }
                    FilledTonalButton(
                        onClick = {
                            viewModel.exportieren(alsPdf = true) { datei ->
                                if (datei == null) {
                                    Toast.makeText(kontext, "Keine Buchungen im Zeitraum", Toast.LENGTH_SHORT).show()
                                } else {
                                    Teilen.datei(kontext, datei, "Buchhaltung $zeitraum")
                                }
                            }
                        },
                        modifier = Modifier.weight(1f)
                    ) {
                        Icon(Icons.Default.PictureAsPdf, contentDescription = null)
                        Text("  PDF")
                    }
                }
            }
        }

        // ── Mandanten ────────────────────────────────────────────────────────
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("Mandanten", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    IconButton(onClick = { neuerMandantDialog = true }) {
                        Icon(Icons.Default.Add, contentDescription = "Mandant hinzufügen")
                    }
                }
                Text(
                    "Jeder Mandant hat eine eigene, getrennte Buchhaltung.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                mandanten.forEach { mandant ->
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = mandant.id == aktiver?.id,
                            onClick = { viewModel.mandantWaehlen(mandant.id) }
                        )
                        Column(Modifier.weight(1f)) {
                            Text(mandant.name, style = MaterialTheme.typography.bodyLarge)
                            Text(
                                mandant.waehrung + if (mandant.notiz.isNotBlank()) " · ${mandant.notiz}" else "",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        if (mandanten.size > 1) {
                            IconButton(onClick = { zuLoeschen = mandant }) {
                                Icon(Icons.Default.Delete, contentDescription = "Mandant löschen")
                            }
                        }
                    }
                }
            }
        }

        // ── Kategorien ───────────────────────────────────────────────────────
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Kategorien", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                listOf(BuchungsTyp.AUSGABE, BuchungsTyp.EINNAHME).forEach { typ ->
                    Row(
                        Modifier.fillMaxWidth().padding(top = 10.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            if (typ == BuchungsTyp.AUSGABE) "Ausgaben" else "Einnahmen",
                            style = MaterialTheme.typography.labelLarge
                        )
                        TextButton(onClick = { neueKategorieTyp = typ }) { Text("Hinzufügen") }
                    }
                    kategorien.filter { it.typ == typ }.forEach { kategorie ->
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(kategorie.name, style = MaterialTheme.typography.bodyMedium)
                            IconButton(onClick = { viewModel.kategorieLoeschen(kategorie) }) {
                                Icon(Icons.Default.Delete, contentDescription = "Kategorie löschen")
                            }
                        }
                    }
                    HorizontalDivider()
                }
            }
        }

        // ── Info ─────────────────────────────────────────────────────────────
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text("Über die App", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(
                    "Alle Daten bleiben auf diesem Gerät. Die App hat keine Internet-Berechtigung " +
                        "und sendet nichts irgendwohin. Belege werden app-intern gespeichert und " +
                        "beim Löschen der Buchung mitgelöscht.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 6.dp)
                )
                AssistChip(
                    onClick = {},
                    label = { Text("Offline · keine Internet-Berechtigung") },
                    modifier = Modifier.padding(top = 10.dp)
                )
            }
        }
    }

    if (neuerMandantDialog) {
        var name by remember { mutableStateOf("") }
        var waehrung by remember { mutableStateOf("CHF") }
        var notiz by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { neuerMandantDialog = false },
            title = { Text("Neuer Mandant") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = name,
                        onValueChange = { name = it },
                        label = { Text("Name") },
                        singleLine = true
                    )
                    OutlinedTextField(
                        value = waehrung,
                        onValueChange = { waehrung = it },
                        label = { Text("Währung") },
                        singleLine = true
                    )
                    OutlinedTextField(
                        value = notiz,
                        onValueChange = { notiz = it },
                        label = { Text("Notiz (optional)") },
                        singleLine = true
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.mandantAnlegen(name, waehrung, notiz)
                    neuerMandantDialog = false
                }) { Text("Anlegen") }
            },
            dismissButton = {
                TextButton(onClick = { neuerMandantDialog = false }) { Text("Abbrechen") }
            }
        )
    }

    zuLoeschen?.let { mandant ->
        AlertDialog(
            onDismissRequest = { zuLoeschen = null },
            title = { Text("\"${mandant.name}\" löschen?") },
            text = { Text("Alle Buchungen und Belege dieses Mandanten werden unwiderruflich gelöscht. Vorher exportieren!") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.mandantLoeschen(mandant)
                    zuLoeschen = null
                }) { Text("Löschen") }
            },
            dismissButton = {
                TextButton(onClick = { zuLoeschen = null }) { Text("Abbrechen") }
            }
        )
    }

    neueKategorieTyp?.let { typ ->
        var name by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { neueKategorieTyp = null },
            title = { Text(if (typ == BuchungsTyp.AUSGABE) "Neue Ausgaben-Kategorie" else "Neue Einnahmen-Kategorie") },
            text = {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    singleLine = true
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.kategorieAnlegen(name, typ)
                    neueKategorieTyp = null
                }) { Text("Anlegen") }
            },
            dismissButton = {
                TextButton(onClick = { neueKategorieTyp = null }) { Text("Abbrechen") }
            }
        )
    }
}
