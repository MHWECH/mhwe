package services.mhwe.buchfuehrung.export

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import services.mhwe.buchfuehrung.data.Buchung
import services.mhwe.buchfuehrung.data.BuchungsTyp
import services.mhwe.buchfuehrung.data.Mandant
import services.mhwe.buchfuehrung.util.Belege
import services.mhwe.buchfuehrung.util.Betrag
import services.mhwe.buchfuehrung.util.Datum
import java.io.File
import java.time.LocalDate
import java.time.format.DateTimeFormatter

/** Erzeugt ein A4-Journal als PDF - ohne externe Bibliothek, nur mit Android-Bordmitteln. */
object PdfExport {

    private const val SEITE_BREITE = 595
    private const val SEITE_HOEHE = 842
    private const val RAND = 36f
    private const val ZEILE = 15f
    private const val UNTERKANTE = 790f

    private const val X_DATUM = RAND
    private const val X_KATEGORIE = 100f
    private const val X_TEXT = 215f
    private const val X_BELEG = 400f
    private const val X_EINNAHME = 480f
    private const val X_AUSGABE = 559f

    fun erzeugen(
        context: Context,
        mandant: Mandant,
        buchungen: List<Buchung>,
        titel: String
    ): File {
        val dokument = PdfDocument()
        val normal = textPinsel(8.5f, false)
        val fett = textPinsel(8.5f, true)
        val rechts = textPinsel(8.5f, false).apply { textAlign = Paint.Align.RIGHT }
        val rechtsFett = textPinsel(8.5f, true).apply { textAlign = Paint.Align.RIGHT }
        val linie = Paint().apply { strokeWidth = 0.6f; color = 0xFF9E9E9E.toInt() }

        var seitenNr = 1
        var seite = dokument.startPage(seitenBeschreibung(seitenNr))
        var y = kopf(seite.canvas, mandant, titel, seitenNr)

        for (buchung in buchungen) {
            if (y > UNTERKANTE) {
                fuss(seite.canvas, seitenNr)
                dokument.finishPage(seite)
                seitenNr++
                seite = dokument.startPage(seitenBeschreibung(seitenNr))
                y = kopf(seite.canvas, mandant, titel, seitenNr)
            }
            val leinwand = seite.canvas
            leinwand.drawText(Datum.formatieren(buchung.datum), X_DATUM, y, normal)
            leinwand.drawText(kuerzen(buchung.kategorie, normal, X_TEXT - X_KATEGORIE - 6f), X_KATEGORIE, y, normal)
            leinwand.drawText(kuerzen(buchung.text, normal, X_BELEG - X_TEXT - 6f), X_TEXT, y, normal)
            if (buchung.belegDatei != null) {
                leinwand.drawText("Foto", X_BELEG, y, normal)
            }
            if (buchung.typ == BuchungsTyp.EINNAHME) {
                leinwand.drawText(Betrag.formatieren(buchung.betragRappen), X_EINNAHME, y, rechts)
            } else {
                leinwand.drawText(Betrag.formatieren(buchung.betragRappen), X_AUSGABE, y, rechts)
            }
            y += ZEILE
        }

        // Summenblock
        if (y > UNTERKANTE - 70f) {
            fuss(seite.canvas, seitenNr)
            dokument.finishPage(seite)
            seitenNr++
            seite = dokument.startPage(seitenBeschreibung(seitenNr))
            y = kopf(seite.canvas, mandant, titel, seitenNr)
        }
        val einnahmen = buchungen.filter { it.typ == BuchungsTyp.EINNAHME }.sumOf { it.betragRappen }
        val ausgaben = buchungen.filter { it.typ == BuchungsTyp.AUSGABE }.sumOf { it.betragRappen }

        y += 6f
        seite.canvas.drawLine(RAND, y - 10f, X_AUSGABE, y - 10f, linie)
        seite.canvas.drawText("Total ${buchungen.size} Buchungen", X_DATUM, y + 4f, fett)
        seite.canvas.drawText(Betrag.formatieren(einnahmen), X_EINNAHME, y + 4f, rechtsFett)
        seite.canvas.drawText(Betrag.formatieren(ausgaben), X_AUSGABE, y + 4f, rechtsFett)

        y += 22f
        seite.canvas.drawText("Saldo (Einnahmen minus Ausgaben)", X_DATUM, y, fett)
        seite.canvas.drawText(
            "${Betrag.formatieren(einnahmen - ausgaben)} ${mandant.waehrung}",
            X_AUSGABE, y, rechtsFett
        )

        fuss(seite.canvas, seitenNr)
        dokument.finishPage(seite)

        val datei = File(Belege.exportOrdner(context), "${CsvExport.dateiBasis(mandant, titel)}.pdf")
        datei.outputStream().use { dokument.writeTo(it) }
        dokument.close()
        return datei
    }

    private fun seitenBeschreibung(nummer: Int) =
        PdfDocument.PageInfo.Builder(SEITE_BREITE, SEITE_HOEHE, nummer).create()

    /** Zeichnet Titelzeile und Tabellenkopf, gibt das Start-Y der ersten Datenzeile zurueck. */
    private fun kopf(leinwand: Canvas, mandant: Mandant, titel: String, seitenNr: Int): Float {
        val titelPinsel = textPinsel(14f, true)
        val klein = textPinsel(8f, false).apply { color = 0xFF616161.toInt() }
        val kopfPinsel = textPinsel(8.5f, true)
        val kopfRechts = textPinsel(8.5f, true).apply { textAlign = Paint.Align.RIGHT }
        val linie = Paint().apply { strokeWidth = 0.8f; color = 0xFF424242.toInt() }

        leinwand.drawText(mandant.name, RAND, 52f, titelPinsel)
        leinwand.drawText("Journal $titel", RAND, 68f, klein)
        leinwand.drawText(
            "Erstellt am ${LocalDate.now().format(DateTimeFormatter.ofPattern("dd.MM.yyyy"))}",
            RAND, 80f, klein
        )

        var y = 104f
        leinwand.drawText("Datum", X_DATUM, y, kopfPinsel)
        leinwand.drawText("Kategorie", X_KATEGORIE, y, kopfPinsel)
        leinwand.drawText("Text", X_TEXT, y, kopfPinsel)
        leinwand.drawText("Beleg", X_BELEG, y, kopfPinsel)
        leinwand.drawText("Einnahme", X_EINNAHME, y, kopfRechts)
        leinwand.drawText("Ausgabe", X_AUSGABE, y, kopfRechts)
        y += 5f
        leinwand.drawLine(RAND, y, X_AUSGABE, y, linie)
        return y + 14f
    }

    private fun fuss(leinwand: Canvas, seitenNr: Int) {
        val klein = textPinsel(7.5f, false).apply {
            color = 0xFF9E9E9E.toInt()
            textAlign = Paint.Align.RIGHT
        }
        leinwand.drawText("Seite $seitenNr", X_AUSGABE, 820f, klein)
    }

    private fun textPinsel(groesse: Float, fett: Boolean) = Paint().apply {
        isAntiAlias = true
        textSize = groesse
        color = 0xFF000000.toInt()
        typeface = Typeface.create(Typeface.SANS_SERIF, if (fett) Typeface.BOLD else Typeface.NORMAL)
    }

    private fun kuerzen(text: String, pinsel: Paint, maxBreite: Float): String {
        if (text.isEmpty() || pinsel.measureText(text) <= maxBreite) return text
        var ende = pinsel.breakText(text, true, maxBreite - pinsel.measureText("…"), null)
        if (ende <= 0) ende = 1
        return text.substring(0, ende.coerceAtMost(text.length)) + "…"
    }
}
