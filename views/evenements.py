# views/evenements.py
import flet as ft
from datetime import datetime

class EvenementsView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app  # Accès à ClubSportifApp
        
        # Cible 'association' pour la couleur de ton club
        self.accent_color = self.app.association.get("accent_color", "#1E3A8A")
        self.editing_id = None

        # Sécurité pour initialiser le dictionnaire s'il est vide
        if not isinstance(self.app.evenements, dict):
            self.app.evenements = {}

        # --- LIGNE 1 DU FORMULAIRE : TITRE & TYPE ---
        self.input_titre = ft.TextField(label="Nom de l'événement", expand=True, hint_text="Ex: Tournoi régional, Entraînement exceptionnel...")
        self.dropdown_type = ft.Dropdown(
            label="Type d'événement",
            width=220,
            options=[
                ft.dropdown.Option("🏃 Cours Régulier"),
                ft.dropdown.Option("🏅 Évaluation / Niveau"),
                ft.dropdown.Option("🏆 Compétition"),
                ft.dropdown.Option("🏟️ Stage / Séminaire"),
                ft.dropdown.Option("📢 Événement Club / AG"),
            ],
            value="🏃 Cours Régulier"
        )

        # --- LIGNE 2 DU FORMULAIRE : DATE, HEURE & LIEU ---
        self.input_date = ft.TextField(label="Date (JJ/MM/AAAA)", width=150, value=datetime.now().strftime("%d/%m/%Y"))
        self.input_heure = ft.TextField(label="Heure (HH:MM)", width=110, value="18:30")
        self.input_lieu = ft.TextField(label="Lieu / Salle", expand=True, value="Salle Principale")

        # --- LIGNE 3 : LES BOUTONS D'ACTION ---
        self.btn_action = ft.ElevatedButton(
            text="Ajouter l'événement",
            icon=ft.icons.ADD,
            bgcolor=self.accent_color,
            color=ft.colors.WHITE,
            height=45,
            on_click=self.valider_formulaire
        )
        
        self.btn_annuler = ft.TextButton(
            text="Annuler la modification",
            icon=ft.icons.CLOSE,
            icon_color=ft.colors.RED_400,
            visible=False,
            on_click=self.annuler_modification
        )

        # --- FILTRES D'AFFICHAGE ---
        self.current_filter = "Tous"
        self.filter_buttons = ft.Row([
            ft.Text("Filtrer : ", size=14, weight=ft.FontWeight.BOLD),
            ft.TextButton("Tous", on_click=lambda e: self.set_filter("Tous"), style=ft.ButtonStyle(color=ft.colors.WHITE)),
            ft.TextButton("🏃 Cours", on_click=lambda e: self.set_filter("🏃 Cours Régulier")),
            ft.TextButton("🏅 Évaluations", on_click=lambda e: self.set_filter("🏅 Évaluation / Niveau")),
            ft.TextButton("🏆 Compets", on_click=lambda e: self.set_filter("🏆 Compétition")),
            ft.TextButton("🏟️ Stages", on_click=lambda e: self.set_filter("🏟️ Stage / Séminaire")),
        ], spacing=10, wrap=True)

        # --- GRILLE D'AFFICHAGE DES CARTES ---
        self.events_grid = ft.Row(wrap=True, spacing=20, alignment=ft.MainAxisAlignment.START)

        # Chargement initial des cartes
        self.load_events()

        # --- MISE EN PAGE GLOBALE ---
        self.titre_formulaire = ft.Text("Ajouter un nouvel événement", size=16, weight=ft.FontWeight.BOLD)
        
        self.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                # En-tête de la page
                ft.Row([
                    ft.Icon(ft.icons.EVENT_AVAILABLE_ROUNDED, size=30, color=self.accent_color),
                    ft.Text("Gestion des Événements du Club", size=24, weight=ft.FontWeight.BOLD),
                ]),
                ft.Divider(),

                # Bloc Formulaire
                self.titre_formulaire,
                ft.Column([
                    ft.Row([self.input_titre, self.dropdown_type], spacing=15),
                    ft.Row([self.input_date, self.input_heure, self.input_lieu], spacing=15),
                    ft.Row([self.btn_annuler, self.btn_action], alignment=ft.MainAxisAlignment.END, spacing=15),
                ], spacing=12),
                
                ft.Divider(),

                # Filtres et Grille de résultats
                self.filter_buttons,
                self.events_grid
            ]
        )

    def load_events(self):
        """Génère les cartes d'événements à partir du dictionnaire 'evenements'."""
        self.events_grid.controls.clear()

        if not self.app.evenements:
            self.events_grid.controls.append(
                ft.Container(
                    content=ft.Text("Aucun événement enregistré pour le moment.", italic=True, color=ft.colors.GREY_500),
                    padding=20
                )
            )
            return

        liste_evenements = list(self.app.evenements.items())
        liste_evenements.reverse() # Du plus récent au plus ancien

        compteur_affiches = 0
        for ev_id, ev in liste_evenements:
            type_ev = ev.get("type", "🏃 Cours Régulier")
            
            if self.current_filter != "Tous" and type_ev != self.current_filter:
                continue
            
            compteur_affiches += 1
            border_color = ft.colors.BLUE_400
            if "Évaluation" in type_ev: border_color = ft.colors.AMBER_400
            elif "Compétition" in type_ev: border_color = ft.colors.RED_400
            elif "Stage" in type_ev: border_color = ft.colors.PURPLE_400
            elif "Événement" in type_ev: border_color = ft.colors.GREEN_400

            card = ft.Container(
                width=280,
                bgcolor="#1F2937",
                padding=15,
                border_radius=10,
                border=ft.border.only(left=ft.border.BorderSide(4, border_color)),
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Text(type_ev, size=11, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.colors.GREY_800,
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=5
                        ),
                        ft.Row([
                            ft.IconButton(
                                icon=ft.icons.EDIT,
                                icon_color=ft.colors.BLUE_200,
                                icon_size=18,
                                tooltip="Modifier cet événement",
                                on_click=lambda e, id_ev=ev_id: self.charger_modification(id_ev)
                            ),
                            ft.IconButton(
                                icon=ft.icons.DELETE_OUTLINE,
                                icon_color=ft.colors.RED_300,
                                icon_size=18,
                                tooltip="Supprimer cet événement",
                                on_click=lambda e, id_ev=ev_id: self.supprimer_evenement(id_ev)
                            )
                        ], spacing=0)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    
                    ft.Text(ev.get("titre", "").upper(), size=15, weight=ft.FontWeight.BOLD, max_lines=2),
                    ft.Row([
                        ft.Icon(ft.icons.DATE_RANGE, size=16, color=ft.colors.GREY_400),
                        ft.Text(f"{ev.get('date')} à {ev.get('heure')}", size=13, color=ft.colors.GREY_300),
                    ], spacing=5),
                    ft.Row([
                        ft.Icon(ft.icons.PLACE, size=16, color=ft.colors.GREY_400),
                        ft.Text(ev.get("lieu", "Salle"), size=12, color=ft.colors.GREY_400, italic=True),
                    ], spacing=5),
                ], spacing=8)
            )
            self.events_grid.controls.append(card)

        if compteur_affiches == 0 and self.current_filter != "Tous":
            self.events_grid.controls.append(
                ft.Container(
                    content=ft.Text(f"Aucun événement trouvé pour la catégorie '{self.current_filter}'", italic=True, color=ft.colors.GREY_500),
                    padding=20
                )
            )

    def set_filter(self, filter_name):
        self.current_filter = filter_name
        self.load_events()
        self.update()

    # ============================================================
    # ⚙️ LOGIQUE ACTIONS (AJOUTER / MODIFIER / SUPPRIMER)
    # ============================================================

    def charger_modification(self, ev_id):
        """Bascule le formulaire du haut en mode 'Édition'"""
        if ev_id not in self.app.evenements:
            return
        
        ev = self.app.evenements[ev_id]
        self.editing_id = ev_id
        
        self.input_titre.value = ev.get("titre", "")
        self.dropdown_type.value = ev.get("type", "🏃 Cours Régulier")
        self.input_date.value = ev.get("date", "")
        self.input_heure.value = ev.get("heure", "")
        self.input_lieu.value = ev.get("lieu", "")
        
        self.titre_formulaire.value = "✏️ Modifier l'événement sélectionné"
        self.titre_formulaire.color = ft.colors.BLUE_300
        self.btn_action.text = "Enregistrer les modifications"
        self.btn_action.icon = ft.icons.SAVE
        self.btn_annuler.visible = True
        
        self.update()

    def annuler_modification(self, e=None):
        """Réinitialise les champs et repasse en mode 'Ajout'"""
        self.editing_id = None
        self.input_titre.value = ""
        self.input_date.value = datetime.now().strftime("%d/%m/%Y")
        self.input_heure.value = "18:30"
        self.input_lieu.value = "Salle Principale"
        self.dropdown_type.value = "🏃 Cours Régulier"
        
        self.titre_formulaire.value = "Ajouter un nouvel événement"
        self.titre_formulaire.color = None
        self.btn_action.text = "Ajouter l'événement"
        self.btn_action.icon = ft.icons.ADD
        self.btn_annuler.visible = False
        
        self.update()

    def valider_formulaire(self, e):
        """Valide et enregistre dans le dictionnaire principal."""
        if not self.input_titre.value:
            return

        donnees_evenement = {
            "titre": self.input_titre.value,
            "type": self.dropdown_type.value,
            "date": self.input_date.value,
            "heure": self.input_heure.value,
            "lieu": self.input_lieu.value
        }

        if self.editing_id:
            self.app.evenements[self.editing_id] = donnees_evenement
        else:
            ev_id = f"evt_{int(datetime.now().timestamp())}"
            self.app.evenements[ev_id] = donnees_evenement

        self.app.save_data()
        self.annuler_modification()
        self.load_events()
        self.update()

    def supprimer_evenement(self, ev_id):
        if ev_id in self.app.evenements:
            del self.app.evenements[ev_id]
            self.app.save_data()
            
            if self.editing_id == ev_id:
                self.annuler_modification()
                
            self.load_events()
            self.update()