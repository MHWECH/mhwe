package services.mhwe.buchfuehrung.export

import android.content.Context
import android.content.Intent
import services.mhwe.buchfuehrung.util.Belege
import java.io.File

/** Oeffnet das Android-Teilen-Fenster fuer eine erzeugte Export-Datei. */
object Teilen {

    fun datei(context: Context, datei: File, betreff: String) {
        val uri = Belege.teilbareUri(context, datei)
        val typ = if (datei.extension.equals("pdf", ignoreCase = true)) {
            "application/pdf"
        } else {
            "text/csv"
        }
        val senden = Intent(Intent.ACTION_SEND).apply {
            type = typ
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, betreff)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        val auswahl = Intent.createChooser(senden, "Export teilen oder speichern")
        auswahl.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(auswahl)
    }
}
