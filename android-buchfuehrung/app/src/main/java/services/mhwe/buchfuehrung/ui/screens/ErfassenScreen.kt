package services.mhwe.buchfuehrung.ui.screens

import android.app.DatePickerDialog
import android.content.Intent
import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.text.KeyboardOptions
import services.mhwe.buchfuehrung.data.BuchungsTyp
import services.mhwe.buchfuehrung.ui.BuchViewModel
import services.mhwe.buchfuehrung.util.Belege
import services.mhwe.buchfuehrung.util.Betrag
import services.mhwe.buchfuehrung.util.Datum
import java.time.LocalDate

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun ErfassenScreen(
    viewModel: BuchViewModel,
    buchungId: Long,
    onFertig: () -> Unit,
    modifier: Modifier = Modifier
) {
    val kontext = LocalContext.current
    val einnahmeKategorien by viewModel.einnahmenKategorien.collectAsState()
    val ausgabeKategorien by viewModel.ausgabenKategorien.collectAsState()

    var typ by remember { mutableStateOf(BuchungsTyp.AUSGABE) }
    var betragText by remember { mutableStateOf("") }
    var datum by remember { mutableStateOf(Datum.heute()) }
    var kategorie by remember { mutableStateOf("") }
    var text by remember { mutableStateOf("") }
    var zahlungsart by remember { mutableStateOf("") }
    var mwstText by remember { mutableStateOf("") }
    var belegDatei by remember { mutableStateOf<String?>(null) }
    var fehler by remember { mutableStateOf<String?>(null) }
    var loeschenGefragt by remember { mutableStateOf(false) }
    var kategorieMenu by remember { mutableStateOf(false) }
    var neueKategorieDialog by remember { mutableStateOf(false) }
    var wartendeBelegDatei by remember { mutableStateOf<String?>(null) }

    val kategorienDerWahl = if (typ == BuchungsTyp.EINNAHME) einnahmeKategorien else ausgabeKategorien

    LaunchedEffect(buchungId) {
        if (buchungId != 0L) {
            viewModel.buchungLaden(buchungId)?.let { vorhanden ->
                typ = vorhanden.typ
                betragText = Betrag.formatieren(vorhanden.betragRappen)
                datum = vorhanden.datum
                kategorie = vorhanden.kategorie
                text = vorhanden.text
                zahlungsart = vorhanden.zahlungsart
                mwstText = if (vorhanden.mwstProzent > 0) vorhanden.mwstProzent.toString() else ""
                belegDatei = vorhanden.belegDatei
            }
        }
    }

    val kameraStart = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { erfolg ->
        val name = wartendeBelegDatei
        if (erfolg && name != null && Belege.existiert(kontext, name)) {
            belegDatei = name
        } else if (name != null) {
            Belege.loeschen(kontext, name)
        }
        wartendeBelegDatei = null
    }

    val galerieStart = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            viewModel.belegAusGalerie(uri) { name ->
                if (name != null) belegDatei = name else fehler = "Bild konnte nicht übernommen werden."
            }
        }
    }

    Column(
        modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            SegmentedButton(
                selected = typ == BuchungsTyp.AUSGABE,
                onClick = {
                    typ = BuchungsTyp.AUSGABE
                    if (kategorie !in ausgabeKategorien) kategorie = ""
                },
                shape = SegmentedButtonDefaults.itemShape(index = 0, count = 2)
            ) { Text("Ausgabe") }
            SegmentedButton(
                selected = typ == BuchungsTyp.EINNAHME,
                onClick = {
                    typ = BuchungsTyp.EINNAHME
                    if (kategorie !in einnahmeKategorien) kategorie = ""
                },
                shape = SegmentedButtonDefaults.itemShape(index = 1, count = 2)
            ) { Text("Einnahme") }
        }

        OutlinedTextField(
            value = betragText,
            onValueChange = { betragText = it; fehler = null },
            label = { Text("Betrag") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            modifier = Modifier.fillMaxWidth()
        )

        OutlinedTextField(
            value = Datum.formatieren(datum),
            onValueChange = {},
            readOnly = true,
            label = { Text("Datum") },
            modifier = Modifier
                .fillMaxWidth()
                .clickable { zeigeDatumsWahl(kontext, datum) { datum = it } }
        )
        TextButton(onClick = { zeigeDatumsWahl(kontext, datum) { datum = it } }) {
            Text("Datum ändern")
        }

        Box {
            OutlinedTextField(
                value = kategorie,
                onValueChange = { kategorie = it },
                label = { Text("Kategorie") },
                singleLine = true,
                trailingIcon = {
                    Icon(
                        Icons.Default.ArrowDropDown,
                        contentDescription = "Kategorie wählen",
                        modifier = Modifier.clickable { kategorieMenu = true }
                    )
                },
                modifier = Modifier.fillMaxWidth()
            )
            DropdownMenu(expanded = kategorieMenu, onDismissRequest = { kategorieMenu = false }) {
                kategorienDerWahl.forEach { name ->
                    DropdownMenuItem(
                        text = { Text(name) },
                        onClick = {
                            kategorie = name
                            kategorieMenu = false
                        }
                    )
                }
                HorizontalDivider()
                DropdownMenuItem(
                    text = { Text("Neue Kategorie …") },
                    onClick = {
                        kategorieMenu = false
                        neueKategorieDialog = true
                    }
                )
            }
        }

        OutlinedTextField(
            value = text,
            onValueChange = { text = it },
            label = { Text("Text / Bemerkung") },
            modifier = Modifier.fillMaxWidth()
        )

        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedTextField(
                value = zahlungsart,
                onValueChange = { zahlungsart = it },
                label = { Text("Zahlungsart") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
            OutlinedTextField(
                value = mwstText,
                onValueChange = { mwstText = it },
                label = { Text("MwSt %") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.weight(1f)
            )
        }

        Text("Beleg", style = MaterialTheme.typography.titleSmall)
        val aktuellerBeleg = belegDatei
        if (aktuellerBeleg != null && Belege.existiert(kontext, aktuellerBeleg)) {
            val bild = remember(aktuellerBeleg) {
                val optionen = BitmapFactory.Options().apply { inSampleSize = 4 }
                BitmapFactory.decodeFile(Belege.datei(kontext, aktuellerBeleg).absolutePath, optionen)
            }
            if (bild != null) {
                Image(
                    bitmap = bild.asImageBitmap(),
                    contentDescription = "Belegfoto",
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(180.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .clickable { belegOeffnen(kontext, aktuellerBeleg) }
                )
            }
            OutlinedButton(onClick = { belegDatei = null }) {
                Icon(Icons.Default.Delete, contentDescription = null)
                Text("  Beleg entfernen")
            }
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                FilledTonalButton(
                    onClick = {
                        val name = Belege.neuerDateiname()
                        wartendeBelegDatei = name
                        kameraStart.launch(Belege.zielFuerKamera(kontext, name))
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Default.CameraAlt, contentDescription = null)
                    Text("  Foto")
                }
                FilledTonalButton(
                    onClick = { galerieStart.launch("image/*") },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(Icons.Default.PhotoLibrary, contentDescription = null)
                    Text("  Galerie")
                }
            }
        }

        fehler?.let {
            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
        }

        Button(
            onClick = {
                val rappen = Betrag.parsen(betragText)
                when {
                    rappen == null || rappen <= 0L -> fehler = "Bitte einen gültigen Betrag eingeben."
                    kategorie.isBlank() -> fehler = "Bitte eine Kategorie wählen."
                    else -> viewModel.buchungSpeichern(
                        id = buchungId,
                        datum = datum,
                        betragRappen = rappen,
                        typ = typ,
                        kategorie = kategorie.trim(),
                        text = text,
                        belegDatei = belegDatei,
                        zahlungsart = zahlungsart,
                        mwstProzent = mwstText.replace(",", ".").toDoubleOrNull() ?: 0.0,
                        fertig = onFertig
                    )
                }
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(if (buchungId == 0L) "Buchung speichern" else "Änderungen speichern")
        }

        if (buchungId != 0L) {
            OutlinedButton(
                onClick = { loeschenGefragt = true },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Buchung löschen")
            }
        }

        Box(Modifier.height(40.dp))
    }

    if (loeschenGefragt) {
        AlertDialog(
            onDismissRequest = { loeschenGefragt = false },
            title = { Text("Buchung löschen?") },
            text = { Text("Die Buchung und ein allfälliges Belegfoto werden entfernt.") },
            confirmButton = {
                TextButton(onClick = {
                    loeschenGefragt = false
                    viewModel.buchungLoeschenNachId(buchungId, onFertig)
                }) { Text("Löschen") }
            },
            dismissButton = {
                TextButton(onClick = { loeschenGefragt = false }) { Text("Abbrechen") }
            }
        )
    }

    if (neueKategorieDialog) {
        var name by remember { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { neueKategorieDialog = false },
            title = { Text("Neue Kategorie") },
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
                    kategorie = name.trim()
                    neueKategorieDialog = false
                }) { Text("Anlegen") }
            },
            dismissButton = {
                TextButton(onClick = { neueKategorieDialog = false }) { Text("Abbrechen") }
            }
        )
    }
}

private fun zeigeDatumsWahl(
    kontext: android.content.Context,
    aktuell: Long,
    onWahl: (Long) -> Unit
) {
    val tag = Datum.alsLocalDate(aktuell)
    DatePickerDialog(
        kontext,
        { _, jahr, monatNullBasiert, tagImMonat ->
            onWahl(LocalDate.of(jahr, monatNullBasiert + 1, tagImMonat).toEpochDay())
        },
        tag.year,
        tag.monthValue - 1,
        tag.dayOfMonth
    ).show()
}

private fun belegOeffnen(kontext: android.content.Context, dateiname: String) {
    val uri = Belege.teilbareUri(kontext, Belege.datei(kontext, dateiname))
    val anzeigen = Intent(Intent.ACTION_VIEW).apply {
        setDataAndType(uri, "image/jpeg")
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
    runCatching { kontext.startActivity(anzeigen) }
}
