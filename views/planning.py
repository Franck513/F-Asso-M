# views/planning.py
import flet as ft
import datetime

class PlanningView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app  # Accès à main.py[cite: 4]
        
        if hasattr(self.app, "association"):
            self.accent_color = self.app.association.get("accent_color", "#2B719E")
        else:
            self.accent_color = "#2B719E"

        self.editing_id = None

        if not hasattr(self.app, "planning_general") or not isinstance(self.app.planning_general, dict):
            self.app.planning_general = {}

        # --- COMPOSANTS DU FORMULAIRE DE SAISIE ---
        self.dropdown_jour = ft.Dropdown(
            label="Jour de la semaine",
            width=160,
            options=[
                ft.dropdown.Option("Lundi"),
                ft.dropdown.Option("Mardi"),
                ft.dropdown.Option("Mercredi"),
                ft.dropdown.Option("Jeudi"),
                ft.dropdown.Option("Vendredi"),
                ft.dropdown.Option("Samedi"),
                ft.dropdown.Option("Dimanche"),
            ],
            value="Lundi"
        )
        
        self.input_titre = ft.TextField(label="Nom du cours / Section", expand=True, hint_text="Ex: Cours Adulte, Section Enfants, Fitness...")
        self.input_debut = ft.TextField(label="Début (HH:MM)", width=110, value="18:30")
        self.input_fin = ft.TextField(label="Fin (HH:MM)", width=110, value="20:00")
        self.input_categorie = ft.TextField(label="Public / Public visé", width=180, hint_text="Ex: Tous niveaux, Compétiteurs...")
        self.input_lieu = ft.TextField(label="Lieu / Salle", width=180, value="Salle Principale")

        # Boutons d'action
        self.btn_action = ft.ElevatedButton(
            text="Ajouter au planning",
            icon=ft.icons.ADD,
            bgcolor=self.accent_color,
            color=ft.colors.WHITE,
            height=45,
            on_click=self.valider_formulaire
        )
        
        self.btn_annuler = ft.TextButton(
            text="Annuler",
            icon=ft.icons.CLOSE,
            icon_color=ft.colors.RED_400,
            visible=False,
            on_click=self.annuler_modification
        )

        # --- ZONE D'AFFICHAGE DU PLANNING ---
        self.planning_container = ft.Column(spacing=15, expand=True)

        # Chargement initial de la grille hebdomadaire
        self.load_planning()

        # --- ARCHITECTURE DE LA VUE ---
        self.titre_formulaire = ft.Text("Ajouter un créneau récurrent", size=16, weight=ft.FontWeight.BOLD)
        
        self.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                # En-tête
                ft.Row([
                    ft.Icon(ft.icons.CALENDAR_MONTH, size=30, color=self.accent_color),
                    ft.Text("Planning Général Hebdomadaire (Cours Récurrents)", size=24, weight=ft.FontWeight.BOLD),
                ]),
                ft.Divider(),

                # Formulaire
                self.titre_formulaire,
                ft.Column([
                    ft.Row([self.dropdown_jour, self.input_titre], spacing=15),
                    ft.Row([self.input_debut, self.input_fin, self.input_categorie, self.input_lieu], spacing=15),
                    ft.Row([self.btn_annuler, self.btn_action], alignment=ft.MainAxisAlignment.END, spacing=15),
                ], spacing=12),
                
                ft.Divider(),

                # Affichage des jours
                ft.Text("Emploi du temps de la semaine", size=18, weight=ft.FontWeight.BOLD),
                self.planning_container
            ]
        )

    def load_planning(self):
        """Organise et affiche le planning trié par jour et par heure."""
        self.planning_container.controls.clear()

        jours_semaine = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        
        if not self.app.planning_general:
            self.planning_container.controls.append(
                ft.Container(
                    content=ft.Text("Aucun cours n'est enregistré dans le planning général.", italic=True, color=ft.colors.GREY_500),
                    padding=20
                )
            )
            return

        for jour in jours_semaine:
            creneaux_du_jour = [
                (id_c, c) for id_c, c in self.app.planning_general.items() if c.get("jour") == jour
            ]
            
            if not creneaux_du_jour:
                continue

            creneaux_du_jour.sort(key=lambda x: x[1].get("debut", "00:00"))

            jour_box = ft.Column(spacing=8)
            jour_box.controls.append(
                ft.Container(
                    content=ft.Text(jour.upper(), size=14, weight=ft.FontWeight.BOLD, color=self.accent_color),
                    margin=ft.margin.only(top=10)
                )
            )

            for id_c, cours in creneaux_du_jour:
                line = ft.Container(
                    bgcolor="#1F2937",
                    padding=12,
                    border_radius=8,
                    content=ft.Row([
                        ft.Container(
                            content=ft.Text(f"{cours.get('debut')} - {cours.get('fin')}", size=13, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                            width=110
                        ),
                        ft.VerticalDivider(color=ft.colors.GREY_700),
                        ft.Container(
                            content=ft.Text(cours.get("titre", "").upper(), size=14, weight=ft.FontWeight.BOLD),
                            expand=2
                        ),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.PEOPLE_ALT_OUTLINED, size=14, color=ft.colors.GREY_400),
                                ft.Text(cours.get("categorie", "Tous"), size=13, color=ft.colors.GREY_300)
                            ]),
                            expand=1
                        ),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.icons.PLACE_OUTLINED, size=14, color=ft.colors.GREY_400),
                                ft.Text(cours.get("lieu", "Salle"), size=13, color=ft.colors.GREY_400, italic=True)
                            ]),
                            expand=1
                        ),
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.EDIT,
                                icon_color=ft.colors.BLUE_300,
                                icon_size=18,
                                tooltip="Modifier ce créneau",
                                on_click=lambda e, idx=id_c: self.charger_modification(idx)
                            ),
                            ft.IconButton(
                                icon=ft.icons.DELETE_OUTLINE,
                                icon_color=ft.colors.RED_300,
                                icon_size=18,
                                tooltip="Supprimer ce créneau",
                                on_click=lambda e, idx=id_c: self.supprimer_creneau(idx)
                            )
                        ], spacing=0)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
                jour_box.controls.append(line)

            self.planning_container.controls.append(jour_box)

    # ============================================================
    # ⚙️ LOGIQUE ACTIONS (CRUD)
    # ============================================================

    def charger_modification(self, id_c):
        """Passe le formulaire supérieur en mode Édition."""
        if id_c not in self.app.planning_general:
            return
        
        cours = self.app.planning_general[id_c]
        self.editing_id = id_c
        
        self.dropdown_jour.value = cours.get("jour", "Lundi")
        self.input_titre.value = cours.get("titre", "")
        self.input_debut.value = cours.get("debut", "18:30")
        self.input_fin.value = cours.get("fin", "20:00")
        self.input_categorie.value = cours.get("categorie", "")
        self.input_lieu.value = cours.get("lieu", "")
        
        self.titre_formulaire.value = "✏️ Modifier le créneau sélectionné"
        self.titre_formulaire.color = ft.colors.BLUE_300
        self.btn_action.text = "Enregistrer les modifications"
        self.btn_action.icon = ft.icons.SAVE
        self.btn_annuler.visible = True
        
        self.update()

    def annuler_modification(self, e=None):
        """Vide le formulaire et repasse en mode Ajout normal."""
        self.editing_id = None
        self.input_titre.value = ""
        self.input_debut.value = "18:30"
        self.input_fin.value = "20:00"
        self.input_categorie.value = ""
        self.input_lieu.value = "Salle Principale"
        
        self.titre_formulaire.value = "Ajouter un créneau récurrent"
        self.titre_formulaire.color = None
        self.btn_action.text = "Ajouter au planning"
        self.btn_action.icon = ft.icons.ADD
        self.btn_annuler.visible = False
        
        self.update()

    def valider_formulaire(self, e):
        """Valide et pousse les données dans le JSON global."""
        if not self.input_titre.value:
            return

        donnees_creneau = {
            "jour": self.dropdown_jour.value,
            "titre": self.input_titre.value,
            "debut": self.input_debut.value,
            "fin": self.input_fin.value,
            "categorie": self.input_categorie.value if self.input_categorie.value else "Tous",
            "lieu": self.input_lieu.value if self.input_lieu.value else "Salle Principale"
        }

        if self.editing_id:
            self.app.planning_general[self.editing_id] = donnees_creneau
        else:
            id_c = f"plan_{int(datetime.datetime.now().timestamp())}"
            self.app.planning_general[id_c] = donnees_creneau

        self.app.save_data()
        self.annuler_modification()
        self.load_planning()
        self.update()

    def supprimer_creneau(self, id_c):
        """Efface un créneau du planning récurrent."""
        if id_c in self.app.planning_general:
            del self.app.planning_general[id_c]
            self.app.save_data()
            
            if self.editing_id == id_c:
                self.annuler_modification()
                
            self.load_planning()
            self.update()