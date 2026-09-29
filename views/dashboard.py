# views/dashboard.py
from datetime import datetime
import flet as ft


class DashboardView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app
        self.accent_color = getattr(self.app, "association", {}).get("accent_color", "#1E3A8A")
        self.selected_sport_id = "all"

        # --- CONTRÔLEURS DYNAMIQUES ---
        self.txt_saison_titre = ft.Text(
            f"Analyse visuelle de la saison {getattr(self.app, 'saison_active', '')}",
            size=13,
            color=ft.colors.GREY_400
        )
        self.txt_nb_membres = ft.Text("0", size=28, weight=ft.FontWeight.BOLD)
        self.txt_solde_global = ft.Text("0.00 €", size=28, weight=ft.FontWeight.BOLD)
        self.txt_nb_structures = ft.Text("0", size=28, weight=ft.FontWeight.BOLD)
        self.lbl_kpi_structures = ft.Text("Structure", size=13, color=ft.colors.GREY_300)

        # Filtre par Sport
        self.dd_sports = ft.Dropdown(
            label="Choisir un sport / section",
            value="all",
            width=240,
            options=[],
            on_change=self._on_sport_changed,
            border_color=ft.colors.GREY_700,
            content_padding=10
        )

        # Conteneurs Graphiques (Camemberts)
        self.chart_genre_container = ft.Container(expand=True)
        self.chart_categories_container = ft.Container(expand=True)
        self.chart_statut_container = ft.Container(expand=True)
        self.chart_paiement_container = ft.Container(expand=True)

        # Zone de détails dynamique (Équipes vs Grades vs Sections)
        self.lbl_details_gauche = ft.Text("🎯 Ventilation", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200)
        self.details_distribution_column = ft.Column(spacing=8, expand=True)
        self.recent_activities_column = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        # Construction de l'interface
        self._build_ui()
        self.refresh_dashboard_data()

    def did_mount(self):
        """Rafraîchit les données automatiquement quand la vue est affichée."""
        self.refresh_dashboard_data()

    def _build_ui(self):
        nom_asso = getattr(self.app, "association", {}).get("nom", "CLUB")
        self.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                # En-tête
                ft.Row([
                    ft.Row([
                        ft.Icon(ft.icons.DASHBOARD_ROUNDED, size=30, color=self.accent_color),
                        ft.Column([
                            ft.Text(f"Tableau de Bord - {nom_asso}", size=22, weight=ft.FontWeight.BOLD),
                            self.txt_saison_titre,
                        ], spacing=2)
                    ]),
                    self.dd_sports
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Divider(color=ft.colors.GREY_800),

                # 1. Cartes KPIs
                ft.Row(
                    controls=[
                        self.create_kpi_card(ft.Text("👥 Adhérents Actifs", size=13, color=ft.colors.GREY_300), self.txt_nb_membres, "Inscrits enregistrés", ft.colors.BLUE_900),
                        self.create_kpi_card(ft.Text("💳 Trésorerie Périmètre", size=13, color=ft.colors.GREY_300), self.txt_solde_global, "Solde comptable", ft.colors.GREEN_900),
                        self.create_kpi_card(self.lbl_kpi_structures, self.txt_nb_structures, "Structures actives", ft.colors.PURPLE_900),
                    ],
                    spacing=15,
                    wrap=True
                ),

                # 2. Graphiques
                ft.Row(
                    controls=[
                        self.create_chart_card("🚻 Genre (H / F)", self.chart_genre_container),
                        self.create_chart_card("🏆 Tranches d'Âge", self.chart_categories_container),
                        self.create_chart_card("🔄 Inscriptions", self.chart_statut_container),
                        self.create_chart_card("💰 Modes de Règlement", self.chart_paiement_container),
                    ],
                    spacing=15,
                    wrap=True
                ),

                # 3. Détails
                ft.Row(
                    controls=[
                        # Colonne Gauche : Adaptative (Équipes / Niveaux / Sports)
                        ft.Container(
                            content=ft.Column([
                                self.lbl_details_gauche,
                                ft.Divider(color=ft.colors.GREY_800),
                                self.details_distribution_column
                            ]),
                            bgcolor="#1F2937",
                            padding=15,
                            border_radius=10,
                            expand=1,
                            height=260
                        ),
                        # Colonne Droite : Activités
                        ft.Container(
                            content=ft.Column([
                                ft.Text("🔔 Dernières opérations", size=16, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                                ft.Divider(color=ft.colors.GREY_800),
                                self.recent_activities_column
                            ]),
                            bgcolor="#1F2937",
                            padding=15,
                            border_radius=10,
                            expand=1,
                            height=260
                        ),
                    ],
                    spacing=15,
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.START
                )
            ]
        )

    def _on_sport_changed(self, e):
        self.selected_sport_id = self.dd_sports.value
        self.refresh_dashboard_data()

    def _get_selected_sport_info(self):
        """Retourne les informations du sport actuellement sélectionné."""
        if self.selected_sport_id == "all":
            return None
        for s in getattr(self.app, "sports", []):
            s_id = str(s.get("id", s.get("nom"))) if isinstance(s, dict) else str(s)
            if s_id == str(self.selected_sport_id):
                return s if isinstance(s, dict) else {"nom": s, "type": "mixte"}
        return None

    def refresh_dashboard_data(self):
        saison = getattr(self.app, "saison_active", "")
        self.txt_saison_titre.value = f"Analyse visuelle de la saison {saison}"

        # 1. Mise à jour dynamique du Dropdown des sports
        sports_list = getattr(self.app, "sports", [])
        dropdown_options = [ft.dropdown.Option("all", "Tous les sports")]

        for s in sports_list:
            if isinstance(s, dict):
                s_id = str(s.get("id", s.get("nom")))
                s_nom = str(s.get("nom", "Sport"))
                s_type = str(s.get("type", "")).capitalize()
                label = f"{s_nom} ({s_type})" if s_type else s_nom
            else:
                s_id = str(s)
                label = str(s)
            dropdown_options.append(ft.dropdown.Option(s_id, label))

        self.dd_sports.options = dropdown_options
        self.dd_sports.value = self.selected_sport_id

        # 2. Filtrage du périmètre
        membres_filtres = self._filtrer_donnees(getattr(self.app, "membres", []))
        cotisations_filtrees = self._filtrer_donnees(getattr(self.app, "cotisations", []))
        finances_filtrees = self._filtrer_donnees(getattr(self.app, "finances", []))

        # 3. Calculs des KPIs généraux
        nb_membres = len(membres_filtres)
        self.txt_nb_membres.value = str(nb_membres)

        total_recettes = sum(
            float(c.get("montant", 0))
            for c in cotisations_filtrees
            if c.get("statut") in ["Encaissé / Validé", "Validé", "Encaissé", "Payé"]
        )
        for op in finances_filtrees:
            m = float(op.get("montant", 0))
            total_recettes += m if op.get("type") == "Recette" else -m

        self.txt_solde_global.value = f"{total_recettes:.2f} €"
        self.txt_solde_global.color = ft.colors.GREEN_400 if total_recettes >= 0 else ft.colors.RED_400

        # KPI 3 : S'adapte au mode (Nombre d'équipes ou Nombre de sections)
        sport_info = self._get_selected_sport_info()
        type_sport = sport_info.get("type", "mixte") if sport_info else "global"

        if type_sport == "collectif":
            self.lbl_kpi_structures.value = "⚽ Équipes engagées"
            equipes = set(m.get("equipe", m.get("groupe", "Non assigné")) for m in membres_filtres)
            self.txt_nb_structures.value = str(len(equipes)) if membres_filtres else "0"
        elif type_sport == "individuel":
            self.lbl_kpi_structures.value = "🥋 Niveaux / Catégories"
            niveaux = set(m.get("grade", m.get("niveau", "Débutant")) for m in membres_filtres)
            self.txt_nb_structures.value = str(len(niveaux)) if membres_filtres else "0"
        else:
            self.lbl_kpi_structures.value = "🏋️ Sections Sportives"
            self.txt_nb_structures.value = str(len(sports_list))

        # 4. Camemberts généraux (Genre, Âge, Statut, Paiements)
        self._remplir_camemberts(membres_filtres, cotisations_filtrees)

        # 5. Colonne de gauche (Générique Individuel / Collectif / Multi-sports)
        self._remplir_details_gauche(membres_filtres, type_sport)

        # 6. Activités récentes
        self._remplir_activites(cotisations_filtrees, finances_filtrees)

        if self.page:
            self.update()

    def _remplir_details_gauche(self, membres, type_sport):
        """Affiche la répartition adaptée au type de sport sélectionné."""
        self.details_distribution_column.controls.clear()

        if self.selected_sport_id == "all":
            self.lbl_details_gauche.value = "🎯 Répartition par Discipline"
            repartition = {}
            for m in membres:
                sport_nom = m.get("nom_sport", m.get("sport", "Général"))
                repartition[sport_nom] = repartition.get(sport_nom, 0) + 1
        elif type_sport == "collectif":
            self.lbl_details_gauche.value = "⚽ Effectifs par Équipe / Groupe"
            repartition = {}
            for m in membres:
                eq = m.get("equipe", m.get("groupe", "Sans équipe"))
                repartition[eq] = repartition.get(eq, 0) + 1
        else:  # Individuel ou Autre
            self.lbl_details_gauche.value = "🥋 Répartition par Niveau / Grade"
            repartition = {}
            for m in membres:
                niv = m.get("grade", m.get("niveau", "Non renseigné"))
                repartition[niv] = repartition.get(niv, 0) + 1

        if not repartition:
            self.details_distribution_column.controls.append(
                ft.Text("Aucune donnée disponible.", italic=True, color=ft.colors.GREY_500, size=12)
            )
            return

        total = len(membres) if membres else 1
        for label, count in list(repartition.items())[:5]:
            pct = count / total
            self.details_distribution_column.controls.append(
                ft.Row([
                    ft.Text(label, width=120, size=11, no_wrap=True),
                    ft.ProgressBar(value=pct, expand=True, color=self.accent_color, bgcolor=ft.colors.GREY_800),
                    ft.Text(str(count), width=30, text_align=ft.TextAlign.RIGHT, size=11, weight=ft.FontWeight.BOLD)
                ], spacing=8)
            )

    def _filtrer_donnees(self, liste_elements, cle_sport="sport_id"):
        if self.selected_sport_id == "all":
            return liste_elements
        res = []
        for item in liste_elements:
            valeur = item.get(cle_sport, item.get("sport", item.get("nom_sport")))
            if str(valeur) == str(self.selected_sport_id):
                res.append(item)
        return res

    def _remplir_camemberts(self, membres, cotisations):
        # Genre
        h = sum(1 for m in membres if str(m.get("sexe", "")).upper() in ["H", "M", "HOMME", "MASCULIN"])
        f = sum(1 for m in membres if str(m.get("sexe", "")).upper() in ["F", "FEMME", "FEMININ"])
        self.chart_genre_container.content = self.generate_mini_pie_chart([
            ("Hommes", h, ft.colors.BLUE_500),
            ("Femmes", f, ft.colors.PINK_400)
        ])

        # Tranches d'âge génériques
        cats = {"Moins de 10 ans": 0, "10-17 ans": 0, "Seniors (18-50)": 0, "Vétérans (50+)": 0}
        annee = datetime.now().year
        for m in membres:
            dob = m.get("date_naissance")
            if dob:
                try:
                    parts = str(dob).replace("/", "-").split("-")
                    a_naiss = int(parts[0]) if len(parts[0]) == 4 else int(parts[-1])
                    age = annee - a_naiss
                    if age < 10: cats["Moins de 10 ans"] += 1
                    elif 10 <= age < 18: cats["10-17 ans"] += 1
                    elif 18 <= age <= 50: cats["Seniors (18-50)"] += 1
                    else: cats["Vétérans (50+)"] += 1
                except (ValueError, IndexError):
                    pass

        palette = [ft.colors.LIGHT_BLUE_400, ft.colors.AMBER_400, ft.colors.TEAL_400, ft.colors.PURPLE_400]
        data_cats = [(k, v, palette[i]) for i, (k, v) in enumerate(cats.items()) if v > 0]
        self.chart_categories_container.content = self.generate_mini_pie_chart(data_cats)

        # Mode de paiement
        modes = {}
        for c in cotisations:
            m = c.get("mode", "Autre")
            modes[m] = modes.get(m, 0) + 1
        cols = [ft.colors.INDIGO_400, ft.colors.ORANGE_400, ft.colors.GREEN_400, ft.colors.PURPLE_400]
        data_modes = [(k, v, cols[i % len(cols)]) for i, (k, v) in enumerate(modes.items())]
        self.chart_paiement_container.content = self.generate_mini_pie_chart(data_modes)

        # Inscriptions
        nouveaux = sum(1 for m in membres if m.get("est_nouveau", False) or "nouveau" in str(m.get("statut", "")).lower())
        anciens = len(membres) - nouveaux
        self.chart_statut_container.content = self.generate_mini_pie_chart([
            ("Anciens", anciens, ft.colors.TEAL_400),
            ("Nouveaux", nouveaux, ft.colors.AMBER_500)
        ])

    def _remplir_activites(self, cotisations, finances):
        self.recent_activities_column.controls.clear()
        flux = [f"💰 {c.get('membre', 'Membre')} : {c.get('montant', 0)}€ ({c.get('mode', 'Paiement')})" for c in reversed(cotisations[-3:])]
        for f in reversed(finances[-3:]):
            ico = "📈" if f.get("type") == "Recette" else "📉"
            flux.append(f"{ico} {f.get('libelle', 'Opération')} : {f.get('montant', 0)}€")

        if not flux:
            self.recent_activities_column.controls.append(
                ft.Text("Aucun mouvement récent.", italic=True, color=ft.colors.GREY_500, size=12)
            )
        else:
            for act in flux[:4]:
                self.recent_activities_column.controls.append(
                    ft.Container(content=ft.Text(act, size=11), padding=6, bgcolor=ft.colors.GREY_900, border_radius=5)
                )

    def create_kpi_card(self, control_title, control_value, subtitle, bg_color):
        return ft.Container(
            content=ft.Column([
                control_title,
                control_value,
                ft.Text(subtitle, size=11, color=ft.colors.GREY_400, italic=True)
            ], spacing=3, alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=bg_color,
            padding=15,
            border_radius=10,
            width=260,
            height=110
        )

    def create_chart_card(self, titre, conteneur_chart):
        return ft.Container(
            content=ft.Column([
                ft.Text(titre, size=15, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                ft.Divider(color=ft.colors.GREY_800),
                conteneur_chart
            ], spacing=10),
            bgcolor="#1F2937",
            padding=15,
            border_radius=10,
            width=270,
            height=210
        )

    def generate_mini_pie_chart(self, items):
        total = sum(val for _, val, _ in items)
        if total == 0:
            return ft.Text("Aucune donnée enregistrée", size=12, italic=True, color=ft.colors.GREY_500)

        sections, legend_items = [], []
        for label, val, color in items:
            if val > 0:
                pct = (val / total) * 100
                sections.append(
                    ft.PieChartSection(
                        value=val,
                        title=f"{val}",
                        title_style=ft.TextStyle(size=10, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                        color=color,
                        radius=22
                    )
                )
                legend_items.append(
                    ft.Row([
                        ft.Container(width=10, height=10, bgcolor=color, border_radius=5),
                        ft.Text(f"{label}: {val} ({pct:.0f}%)", size=11, color=ft.colors.GREY_300)
                    ], spacing=6)
                )

        return ft.Row([
            ft.PieChart(sections=sections, sections_space=2, center_space_radius=18, width=85, height=85, expand=False),
            ft.Column(controls=legend_items, spacing=4, alignment=ft.MainAxisAlignment.CENTER, scroll=ft.ScrollMode.AUTO)
        ], spacing=15, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)