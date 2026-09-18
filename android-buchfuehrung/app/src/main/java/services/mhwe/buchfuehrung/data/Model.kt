package services.mhwe.buchfuehrung.data

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey
import androidx.room.TypeConverter

/** Einnahme oder Ausgabe. Der Betrag wird immer positiv gespeichert. */
enum class BuchungsTyp {
    EINNAHME,
    AUSGABE;

    val bezeichnung: String
        get() = if (this == EINNAHME) "Einnahme" else "Ausgabe"
}

/** Ein Mandant ist eine getrennte Buchhaltung, z.B. "Privat" oder eine Firma. */
@Entity(tableName = "mandanten")
data class Mandant(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val waehrung: String = "CHF",
    val notiz: String = ""
)

@Entity(
    tableName = "buchungen",
    foreignKeys = [
        ForeignKey(
            entity = Mandant::class,
            parentColumns = ["id"],
            childColumns = ["mandantId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("mandantId"), Index("datum")]
)
data class Buchung(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val mandantId: Long,
    /** Datum als Tage seit 1970-01-01 (LocalDate.toEpochDay). */
    val datum: Long,
    /** Betrag in Rappen/Cent, immer positiv. Das Vorzeichen ergibt sich aus [typ]. */
    val betragRappen: Long,
    val typ: BuchungsTyp,
    val kategorie: String,
    val text: String = "",
    /** Dateiname des Belegfotos in filesDir/belege, oder null. */
    val belegDatei: String? = null,
    val zahlungsart: String = "",
    val mwstProzent: Double = 0.0
) {
    /** Betrag mit Vorzeichen: Ausgaben negativ. */
    val vorzeichenBetrag: Long
        get() = if (typ == BuchungsTyp.EINNAHME) betragRappen else -betragRappen
}

@Entity(
    tableName = "kategorien",
    indices = [Index(value = ["name", "typ"], unique = true)]
)
data class Kategorie(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val typ: BuchungsTyp
)

class Converters {
    @TypeConverter
    fun typZuText(typ: BuchungsTyp): String = typ.name

    @TypeConverter
    fun textZuTyp(wert: String): BuchungsTyp = BuchungsTyp.valueOf(wert)
}
