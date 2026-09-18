package services.mhwe.buchfuehrung.util

import java.math.BigDecimal
import java.math.RoundingMode
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter
import kotlin.math.abs

/**
 * Geldbetraege werden ueberall als ganze Rappen/Cent (Long) gerechnet.
 * So gibt es keine Rundungsfehler wie bei Double.
 */
object Betrag {

    /** 123456 -> "1'234.56" (Schweizer Schreibweise). */
    fun formatieren(rappen: Long, mitVorzeichen: Boolean = false): String {
        val negativ = rappen < 0
        val absolut = abs(rappen)
        val franken = absolut / 100
        val rest = absolut % 100
        val gruppiert = gruppieren(franken)
        val zahl = "$gruppiert.${rest.toString().padStart(2, '0')}"
        return when {
            negativ -> "-$zahl"
            mitVorzeichen && rappen > 0 -> "+$zahl"
            else -> zahl
        }
    }

    /** Eingabe des Benutzers lesen: "1'234.56", "1234,56", "1234" ... */
    fun parsen(eingabe: String): Long? {
        val bereinigt = eingabe.trim()
            .replace("'", "")
            .replace("’", "")
            .replace(" ", "")
            .replace(" ", "")
            .replace(",", ".")
        if (bereinigt.isEmpty()) return null
        return try {
            BigDecimal(bereinigt)
                .setScale(2, RoundingMode.HALF_UP)
                .movePointRight(2)
                .toLong()
        } catch (e: NumberFormatException) {
            null
        }
    }

    private fun gruppieren(wert: Long): String {
        val text = wert.toString()
        if (text.length <= 3) return text
        val ergebnis = StringBuilder()
        var zaehler = 0
        for (i in text.lastIndex downTo 0) {
            ergebnis.append(text[i])
            zaehler++
            if (zaehler % 3 == 0 && i > 0) ergebnis.append('\'')
        }
        return ergebnis.reverse().toString()
    }
}

object Datum {

    private val anzeige: DateTimeFormatter = DateTimeFormatter.ofPattern("dd.MM.yyyy")
    private val dateiname: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd")

    val monatsnamen = listOf(
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember"
    )

    fun heute(): Long = LocalDate.now().toEpochDay()

    fun formatieren(epochTag: Long): String =
        LocalDate.ofEpochDay(epochTag).format(anzeige)

    fun fuerDateiname(epochTag: Long): String =
        LocalDate.ofEpochDay(epochTag).format(dateiname)

    fun alsLocalDate(epochTag: Long): LocalDate = LocalDate.ofEpochDay(epochTag)

    /** Erster und letzter Tag eines Monats (monat = 1..12). */
    fun monatsGrenzen(jahr: Int, monat: Int): Pair<Long, Long> {
        val ym = YearMonth.of(jahr, monat)
        return ym.atDay(1).toEpochDay() to ym.atEndOfMonth().toEpochDay()
    }

    /** Erster und letzter Tag eines Jahres. */
    fun jahresGrenzen(jahr: Int): Pair<Long, Long> =
        LocalDate.of(jahr, 1, 1).toEpochDay() to LocalDate.of(jahr, 12, 31).toEpochDay()

    fun monatsname(monat: Int): String = monatsnamen[monat - 1]
}
