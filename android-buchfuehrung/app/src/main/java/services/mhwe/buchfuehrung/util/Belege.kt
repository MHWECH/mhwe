package services.mhwe.buchfuehrung.util

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File

/** Verwaltet die Belegfotos im app-internen Speicher (filesDir/belege). */
object Belege {

    private fun ordner(context: Context): File =
        File(context.filesDir, "belege").apply { mkdirs() }

    fun datei(context: Context, dateiname: String): File =
        File(ordner(context), dateiname)

    fun neuerDateiname(): String = "beleg_${System.currentTimeMillis()}.jpg"

    /** Leere Zieldatei fuer die Kamera anlegen und als FileProvider-Uri zurueckgeben. */
    fun zielFuerKamera(context: Context, dateiname: String): Uri {
        val ziel = datei(context, dateiname)
        ziel.parentFile?.mkdirs()
        if (!ziel.exists()) ziel.createNewFile()
        return teilbareUri(context, ziel)
    }

    /** Ein aus der Galerie gewaehltes Bild in den App-Speicher kopieren. */
    fun ausGalerieKopieren(context: Context, quelle: Uri): String? {
        val dateiname = neuerDateiname()
        val ziel = datei(context, dateiname)
        return try {
            context.contentResolver.openInputStream(quelle)?.use { eingang ->
                ziel.outputStream().use { ausgang -> eingang.copyTo(ausgang) }
            } ?: return null
            dateiname
        } catch (e: Exception) {
            ziel.delete()
            null
        }
    }

    fun loeschen(context: Context, dateiname: String) {
        datei(context, dateiname).delete()
    }

    fun existiert(context: Context, dateiname: String): Boolean =
        datei(context, dateiname).let { it.exists() && it.length() > 0 }

    fun teilbareUri(context: Context, datei: File): Uri =
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", datei)

    /** Ordner fuer erzeugte Exportdateien (CSV/PDF). */
    fun exportOrdner(context: Context): File =
        File(context.cacheDir, "export").apply { mkdirs() }
}
