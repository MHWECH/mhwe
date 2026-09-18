package services.mhwe.buchfuehrung.export

import android.content.Context
import services.mhwe.buchfuehrung.data.Buchung
import services.mhwe.buchfuehrung.data.BuchungsTyp
import services.mhwe.buchfuehrung.data.Mandant
import services.mhwe.buchfuehrung.util.Belege
import services.mhwe.buchfuehrung.util.Betrag
import services.mhwe.buchfuehrung.util.Datum
import java.io.File

/**
 * Schreibt die Buchungen als CSV mit Semikolon als Trennzeichen.
 * Das UTF-8-BOM sorgt dafuer, dass Excel die Umlaute richtig anzeigt.
 */
object CsvExport {

    private const val TRENNER = ';'
    private const val BOM = "﻿"

    fun erzeugen(
        context: Context,
        mandant: Mandant,
        buchungen: List<Buchung>,
        titel: String
    ): File {
        val datei = File(Belege.exportOrdner(context), "${dateiBasis(mandant, titel)}.csv")
        val text = buildString {
            append(BOM)
            zeile(
                "Datum", "Typ", "Kategorie", "Text", "Zahlungsart",
                "Einnahme", "Ausgabe", "MwSt %", "Beleg"
            )
            for (b in buchungen) {
                val betrag = rohBetrag(b.betragRappen)
                zeile(
                    Datum.formatieren(b.datum),
                    b.typ.bezeichnung,
                    b.kategorie,
                    b.text,
                    b.zahlungsart,
                    if (b.typ == BuchungsTyp.EINNAHME) betrag else "",
                    if (b.typ == BuchungsTyp.AUSGABE) betrag else "",
                    if (b.mwstProzent > 0) formatProzent(b.mwstProzent) else "",
                    b.belegDatei ?: ""
                )
            }
            val einnahmen = buchungen.filter { it.typ == BuchungsTyp.EINNAHME }.sumOf { it.betragRappen }
            val ausgaben = buchungen.filter { it.typ == BuchungsTyp.AUSGABE }.sumOf { it.betragRappen }
            zeile("", "", "", "", "", "", "", "", "")
            zeile("", "Total", "", "", "", rohBetrag(einnahmen), rohBetrag(ausgaben), "", "")
            zeile("", "Saldo", "", "", "", rohBetrag(einnahmen - ausgaben), "", "", "")
        }
        datei.writeText(text, Charsets.UTF_8)
        return datei
    }

    /** Betrag ohne Tausendertrennzeichen - so rechnet Excel damit weiter. */
    private fun rohBetrag(rappen: Long): String {
        val negativ = rappen < 0
        val absolut = if (negativ) -rappen else rappen
        val zahl = "${absolut / 100}.${(absolut % 100).toString().padStart(2, '0')}"
        return if (negativ) "-$zahl" else zahl
    }

    private fun formatProzent(wert: Double): String =
        if (wert % 1.0 == 0.0) wert.toInt().toString() else wert.toString()

    private fun StringBuilder.zeile(vararg felder: String) {
        append(felder.joinToString(TRENNER.toString()) { maskieren(it) })
        append("\r\n")
    }

    private fun maskieren(feld: String): String =
        if (feld.contains(TRENNER) || feld.contains('"') || feld.contains('\n') || feld.contains('\r')) {
            "\"" + feld.replace("\"", "\"\"") + "\""
        } else {
            feld
        }

    fun dateiBasis(mandant: Mandant, titel: String): String {
        val roh = "Buchhaltung_${mandant.name}_$titel"
        return roh.replace(Regex("[^A-Za-z0-9._-]+"), "_").trim('_')
    }

    /** Wird auch vom PDF-Export gebraucht - deshalb hier oeffentlich. */
    fun betragLesbar(rappen: Long): String = Betrag.formatieren(rappen)
}
