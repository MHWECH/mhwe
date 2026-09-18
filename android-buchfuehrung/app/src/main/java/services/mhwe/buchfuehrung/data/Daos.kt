package services.mhwe.buchfuehrung.data

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

@Dao
interface MandantDao {
    @Query("SELECT * FROM mandanten ORDER BY name COLLATE NOCASE")
    fun alle(): Flow<List<Mandant>>

    @Query("SELECT COUNT(*) FROM mandanten")
    suspend fun anzahl(): Int

    @Query("SELECT * FROM mandanten ORDER BY id LIMIT 1")
    suspend fun erster(): Mandant?

    @Insert
    suspend fun einfuegen(mandant: Mandant): Long

    @Update
    suspend fun aktualisieren(mandant: Mandant)

    @Delete
    suspend fun loeschen(mandant: Mandant)
}

@Dao
interface BuchungDao {
    @Query(
        "SELECT * FROM buchungen WHERE mandantId = :mandantId " +
            "AND datum BETWEEN :vonTag AND :bisTag ORDER BY datum DESC, id DESC"
    )
    fun imZeitraum(mandantId: Long, vonTag: Long, bisTag: Long): Flow<List<Buchung>>

    @Query(
        "SELECT * FROM buchungen WHERE mandantId = :mandantId " +
            "AND datum BETWEEN :vonTag AND :bisTag ORDER BY datum ASC, id ASC"
    )
    suspend fun listeFuerExport(mandantId: Long, vonTag: Long, bisTag: Long): List<Buchung>

    @Query("SELECT * FROM buchungen WHERE id = :id")
    suspend fun nachId(id: Long): Buchung?

    @Query("SELECT COUNT(*) FROM buchungen WHERE belegDatei = :dateiname")
    suspend fun anzahlMitBeleg(dateiname: String): Int

    @Upsert
    suspend fun speichern(buchung: Buchung): Long

    @Delete
    suspend fun loeschen(buchung: Buchung)
}

@Dao
interface KategorieDao {
    @Query("SELECT * FROM kategorien WHERE typ = :typ ORDER BY name COLLATE NOCASE")
    fun nachTyp(typ: BuchungsTyp): Flow<List<Kategorie>>

    @Query("SELECT * FROM kategorien ORDER BY typ, name COLLATE NOCASE")
    fun alle(): Flow<List<Kategorie>>

    @Query("SELECT COUNT(*) FROM kategorien")
    suspend fun anzahl(): Int

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun einfuegen(kategorie: Kategorie): Long

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun einfuegenAlle(kategorien: List<Kategorie>)

    @Delete
    suspend fun loeschen(kategorie: Kategorie)
}
