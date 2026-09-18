package services.mhwe.buchfuehrung.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import services.mhwe.buchfuehrung.ui.screens.AuswertungScreen
import services.mhwe.buchfuehrung.ui.screens.BuchungenScreen
import services.mhwe.buchfuehrung.ui.screens.ErfassenScreen
import services.mhwe.buchfuehrung.ui.screens.MehrScreen
import services.mhwe.buchfuehrung.ui.screens.UebersichtScreen

private data class Reiter(val route: String, val beschriftung: String, val symbol: ImageVector)

private val reiter = listOf(
    Reiter("uebersicht", "Übersicht", Icons.Default.Home),
    Reiter("buchungen", "Buchungen", Icons.AutoMirrored.Filled.List),
    Reiter("auswertung", "Auswertung", Icons.Default.BarChart),
    Reiter("mehr", "Mehr", Icons.Default.MoreHoriz)
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BuchfuehrungApp() {
    val navigation = rememberNavController()
    val viewModel: BuchViewModel = viewModel()
    val mandanten by viewModel.mandanten.collectAsState()
    val aktiver by viewModel.aktiverMandant.collectAsState()

    val eintrag by navigation.currentBackStackEntryAsState()
    val route = eintrag?.destination?.route ?: "uebersicht"
    val istErfassen = route.startsWith("erfassen")

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    if (istErfassen) {
                        Text("Buchung")
                    } else {
                        MandantWaehler(
                            mandanten = mandanten,
                            aktiver = aktiver,
                            onWahl = viewModel::mandantWaehlen
                        )
                    }
                },
                navigationIcon = {
                    if (istErfassen) {
                        IconButton(onClick = { navigation.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Zurück")
                        }
                    }
                }
            )
        },
        bottomBar = {
            if (!istErfassen) {
                NavigationBar {
                    reiter.forEach { r ->
                        NavigationBarItem(
                            selected = route == r.route,
                            onClick = {
                                if (route != r.route) {
                                    navigation.navigate(r.route) {
                                        popUpTo("uebersicht") { saveState = true }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }
                            },
                            icon = { Icon(r.symbol, contentDescription = r.beschriftung) },
                            label = { Text(r.beschriftung) }
                        )
                    }
                }
            }
        },
        floatingActionButton = {
            if (route == "uebersicht" || route == "buchungen") {
                FloatingActionButton(onClick = { navigation.navigate("erfassen/0") }) {
                    Icon(Icons.Default.Add, contentDescription = "Buchung erfassen")
                }
            }
        }
    ) { innenAbstand ->
        NavHost(
            navController = navigation,
            startDestination = "uebersicht",
            modifier = Modifier.padding(innenAbstand)
        ) {
            composable("uebersicht") {
                UebersichtScreen(
                    viewModel = viewModel,
                    onBuchungKlick = { id -> navigation.navigate("erfassen/$id") },
                    onAlleBuchungen = { navigation.navigate("buchungen") }
                )
            }
            composable("buchungen") {
                BuchungenScreen(
                    viewModel = viewModel,
                    onBuchungKlick = { id -> navigation.navigate("erfassen/$id") }
                )
            }
            composable("auswertung") {
                AuswertungScreen(viewModel = viewModel)
            }
            composable("mehr") {
                MehrScreen(viewModel = viewModel)
            }
            composable(
                route = "erfassen/{id}",
                arguments = listOf(navArgument("id") { type = NavType.LongType })
            ) { eintragMitId ->
                ErfassenScreen(
                    viewModel = viewModel,
                    buchungId = eintragMitId.arguments?.getLong("id") ?: 0L,
                    onFertig = { navigation.popBackStack() }
                )
            }
        }
    }
}
