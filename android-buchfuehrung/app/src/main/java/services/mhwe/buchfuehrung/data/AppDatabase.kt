package services.mhwe.buchfuehrung.data

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(
    entities = [Mandant::class, Buchung::class, Kategorie::class],
    version = 1,
    exportSchema = false
)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {

    abstract fun mandantDao(): MandantDao
    abstract fun buchungDao(): BuchungDao
    abstract fun kategorieDao(): KategorieDao

    companion object {
        @Volatile
        private var instanz: AppDatabase? = null

        fun hole(context: Context): AppDatabase = instanz ?: synchronized(this) {
            instanz ?: Room.databaseBuilder(
                context.applicationContext,
                AppDatabase::class.java,
                "buchfuehrung.db"
            ).build().also { instanz = it }
        }
    }
}

/** Kategorien, mit denen die App beim ersten Start startet. */
object StandardKategorien {
    val einnahmen = listOf(
        "Lohn", "Miete/Mietzins", "Zinsen", "Verkauf", "Rückerstattung", "Übriges"
    )
    val ausgaben = listOf(
        "Miete/Hypothek", "Nebenkosten", "Versicherungen", "Krankenkasse",
        "Lebensmittel", "Gesundheit", "Transport/ÖV", "Telefon/Internet",
        "Steuern", "Unterhalt/Reparatur", "Gebühren", "Übriges"
    )

    fun alle(): List<Kategorie> =
        einnahmen.map { Kategorie(name = it, typ = BuchungsTyp.EINNAHME) } +
            ausgaben.map { Kategorie(name = it, typ = BuchungsTyp.AUSGABE) }
}
