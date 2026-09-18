package services.mhwe.buchfuehrung.ui

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import services.mhwe.buchfuehrung.data.AppDatabase
import services.mhwe.buchfuehrung.data.Buchung
import services.mhwe.buchfuehrung.data.BuchungsTyp
import services.mhwe.buchfuehrung.data.Kategorie
import services.mhwe.buchfuehrung.data.Mandant
import services.mhwe.buchfuehrung.data.StandardKategorien
import services.mhwe.buchfuehrung.export.CsvExport
import services.mhwe.buchfuehrung.export.PdfExport
import services.mhwe.buchfuehrung.util.Belege
import services.mhwe.buchfuehrung.util.Datum
import java.io.File
import java.time.LocalDate

/** 0 bedeutet: ganzes Jahr statt eines einzelnen Monats. */
const val GANZES_JAHR = 0

@OptIn(ExperimentalCoroutinesApi::class)
class BuchViewModel(anwendung: Application) : AndroidViewModel(anwendung) {

    private val datenbank = AppDatabase.hole(anwendung)
    private val mandantDao = datenbank.mandantDao()
    private val buchungDao = datenbank.buchungDao()
    private val kategorieDao = datenbank.kategorieDao()
    private val einstellungen =
        anwendung.getSharedPreferences("buchfuehrung", Context.MODE_PRIVATE)

    val mandanten: StateFlow<List<Mandant>> = mandantDao.alle()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    private val gewaehlterMandantId = MutableStateFlow(einstellungen.getLong("mandant", 0L))

    val aktiverMandant: StateFlow<Mandant?> =
        combine(mandanten, gewaehlterMandantId) { liste, id ->
            liste.firstOrNull { it.id == id } ?: liste.firstOrNull()
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    private val gewaehltesJahr = MutableStateFlow(LocalDate.now().year)
    private val gewaehlterMonat = MutableStateFlow(LocalDate.now().monthValue)

    val jahr: StateFlow<Int> = gewaehltesJahr
    val monat: StateFlow<Int> = gewaehlterMonat

    val zeitraumTitel: StateFlow<String> =
        combine(gewaehltesJahr, gewaehlterMonat) { j, m ->
            if (m == GANZES_JAHR) "$j" else "${Datum.monatsname(m)} $j"
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val buchungen: StateFlow<List<Buchung>> =
        combine(aktiverMandant, gewaehltesJahr, gewaehlterMonat) { m, j, mo -> Triple(m, j, mo) }
            .flatMapLatest { (mandant, j, mo) ->
                if (mandant == null) {
                    flowOf(emptyList())
                } else {
                    val (von, bis) =
                        if (mo == GANZES_JAHR) Datum.jahresGrenzen(j) else Datum.monatsGrenzen(j, mo)
                    buchungDao.imZeitraum(mandant.id, von, bis)
                }
            }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val kategorien: StateFlow<List<Kategorie>> = kategorieDao.alle()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val einnahmenKategorien: StateFlow<List<String>> = kategorien
        .map { liste -> liste.filter { it.typ == BuchungsTyp.EINNAHME }.map { it.name } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val ausgabenKategorien: StateFlow<List<String>> = kategorien
        .map { liste -> liste.filter { it.typ == BuchungsTyp.AUSGABE }.map { it.name } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    /** Summe der Einnahmen im gewaehlten Zeitraum, in Rappen. */
    val summeEinnahmen: StateFlow<Long> = buchungen
        .map { liste -> liste.filter { it.typ == BuchungsTyp.EINNAHME }.sumOf { it.betragRappen } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0L)

    val summeAusgaben: StateFlow<Long> = buchungen
        .map { liste -> liste.filter { it.typ == BuchungsTyp.AUSGABE }.sumOf { it.betragRappen } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0L)

    val saldo: StateFlow<Long> = buchungen
        .map { liste -> liste.sumOf { it.vorzeichenBetrag } }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0L)

    init {
        viewModelScope.launch {
            if (kategorieDao.anzahl() == 0) {
                kategorieDao.einfuegenAlle(StandardKategorien.alle())
            }
            if (mandantDao.anzahl() == 0) {
                val id = mandantDao.einfuegen(Mandant(name = "Privat"))
                mandantWaehlen(id)
            } else if (gewaehlterMandantId.value == 0L) {
                mandantDao.erster()?.let { mandantWaehlen(it.id) }
            }
        }
    }

    // ── Mandanten ────────────────────────────────────────────────────────────

    fun mandantWaehlen(id: Long) {
        gewaehlterMandantId.value = id
        einstellungen.edit().putLong("mandant", id).apply()
    }

    fun mandantAnlegen(name: String, waehrung: String, notiz: String) {
        if (name.isBlank()) return
        viewModelScope.launch {
            val id = mandantDao.einfuegen(
                Mandant(name = name.trim(), waehrung = waehrung.trim().ifBlank { "CHF" }, notiz = notiz.trim())
            )
            mandantWaehlen(id)
        }
    }

    fun mandantAendern(mandant: Mandant) {
        viewModelScope.launch { mandantDao.aktualisieren(mandant) }
    }

    /** Loescht den Mandanten samt Buchungen und den dazugehoerenden Belegfotos. */
    fun mandantLoeschen(mandant: Mandant) {
        viewModelScope.launch {
            val kontext = getApplication<Application>()
            val (von, bis) = -100_000L to 100_000L
            buchungDao.listeFuerExport(mandant.id, von, bis).forEach { buchung ->
                buchung.belegDatei?.let { Belege.loeschen(kontext, it) }
            }
            mandantDao.loeschen(mandant)
            if (gewaehlterMandantId.value == mandant.id) {
                mandantWaehlen(mandantDao.erster()?.id ?: 0L)
            }
        }
    }

    // ── Zeitraum ─────────────────────────────────────────────────────────────

    fun jahrSetzen(wert: Int) {
        gewaehltesJahr.value = wert
    }

    fun monatSetzen(wert: Int) {
        gewaehlterMonat.value = wert
    }

    // ── Buchungen ────────────────────────────────────────────────────────────

    suspend fun buchungLaden(id: Long): Buchung? = buchungDao.nachId(id)

    fun buchungSpeichern(
        id: Long,
        datum: Long,
        betragRappen: Long,
        typ: BuchungsTyp,
        kategorie: String,
        text: String,
        belegDatei: String?,
        zahlungsart: String,
        mwstProzent: Double,
        fertig: () -> Unit = {}
    ) {
        val mandant = aktiverMandant.value ?: return
        viewModelScope.launch {
            val alterBeleg = if (id != 0L) buchungDao.nachId(id)?.belegDatei else null
            buchungDao.speichern(
                Buchung(
                    id = id,
                    mandantId = mandant.id,
                    datum = datum,
                    betragRappen = betragRappen,
                    typ = typ,
                    kategorie = kategorie,
                    text = text.trim(),
                    belegDatei = belegDatei,
                    zahlungsart = zahlungsart.trim(),
                    mwstProzent = mwstProzent
                )
            )
            if (alterBeleg != null && alterBeleg != belegDatei) {
                belegAufraeumen(alterBeleg)
            }
            fertig()
        }
    }

    fun buchungLoeschenNachId(id: Long, fertig: () -> Unit = {}) {
        viewModelScope.launch {
            buchungDao.nachId(id)?.let { buchung ->
                buchungDao.loeschen(buchung)
                buchung.belegDatei?.let { belegAufraeumen(it) }
            }
            fertig()
        }
    }

    fun buchungLoeschen(buchung: Buchung) {
        viewModelScope.launch {
            buchungDao.loeschen(buchung)
            buchung.belegDatei?.let { belegAufraeumen(it) }
        }
    }

    /** Loescht ein Belegfoto nur, wenn keine Buchung mehr darauf zeigt. */
    private suspend fun belegAufraeumen(dateiname: String) {
        if (buchungDao.anzahlMitBeleg(dateiname) == 0) {
            Belege.loeschen(getApplication(), dateiname)
        }
    }

    fun belegAusGalerie(quelle: Uri, fertig: (String?) -> Unit) {
        viewModelScope.launch {
            fertig(Belege.ausGalerieKopieren(getApplication(), quelle))
        }
    }

    // ── Kategorien ───────────────────────────────────────────────────────────

    fun kategorieAnlegen(name: String, typ: BuchungsTyp) {
        if (name.isBlank()) return
        viewModelScope.launch { kategorieDao.einfuegen(Kategorie(name = name.trim(), typ = typ)) }
    }

    fun kategorieLoeschen(kategorie: Kategorie) {
        viewModelScope.launch { kategorieDao.loeschen(kategorie) }
    }

    // ── Export ───────────────────────────────────────────────────────────────

    fun exportieren(alsPdf: Boolean, fertig: (File?) -> Unit) {
        val mandant = aktiverMandant.value ?: run { fertig(null); return }
        viewModelScope.launch {
            val (von, bis) = if (gewaehlterMonat.value == GANZES_JAHR) {
                Datum.jahresGrenzen(gewaehltesJahr.value)
            } else {
                Datum.monatsGrenzen(gewaehltesJahr.value, gewaehlterMonat.value)
            }
            val liste = buchungDao.listeFuerExport(mandant.id, von, bis)
            if (liste.isEmpty()) {
                fertig(null)
                return@launch
            }
            val titel = zeitraumTitel.value
            val kontext = getApplication<Application>()
            val datei = if (alsPdf) {
                PdfExport.erzeugen(kontext, mandant, liste, titel)
            } else {
                CsvExport.erzeugen(kontext, mandant, liste, titel)
            }
            fertig(datei)
        }
    }
}
