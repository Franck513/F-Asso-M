# views/materiel.py
import flet as ft

class MaterielView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app  # Accès à main.py (self.app.materiel)
        self.accent_color = self.app.association.get("accent_color", "#1E3A8A")

        # --- COMPOSANTS DU FORMULAIRE ---
        self.input_nom = ft.TextField(
            label="Nom de l'équipement", 
            width=300, 
            hint_text="Ex: Ballons, Cônes, Chronomètre, Maillots..."
        )
        self.input_quantite = ft.TextField(
            label="Quantité", 
            value="1", 
            width=100, 
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.dropdown_cat = ft.Dropdown(
            label="Catégorie",
            width=250,
            options=[
                ft.dropdown.Option("🛡️ Protections et Sécurité"),
                ft.dropdown.Option("🎯 Matériel d'entraînement / Pédagogique"),
                ft.dropdown.Option("🏟️ Aménagement / Infrastructure"),
                ft.dropdown.Option("🩹 Pharmacie / Premier Secours"),
            ],
            value="🎯 Matériel d'entraînement / Pédagogique"
        )
        
        self.dropdown_etat = ft.Dropdown(
            label="État",
            width=180,
            options=[
                ft.dropdown.Option("Neuf"),
                ft.dropdown.Option("Bon état"),
                ft.dropdown.Option("Usé (À surveiller)"),
                ft.dropdown.Option("⚠️ À remplacer / HS"),
            ],
            value="Neuf"
        )

        # --- TABLEAU D'INVENTAIRE ---
        self.table_materiel = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Équipement")),
                ft.DataColumn(ft.Text("Catégorie")),
                ft.DataColumn(ft.Text("Quantité")),
                ft.DataColumn(ft.Text("État")),
                ft.DataColumn(ft.Text("Action")),
            ],
            rows=[]
        )

        self.load_materiel()

        # --- ARCHITECTURE DE LA VUE ---
        self.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                # En-tête
                ft.Row([
                    ft.Icon(ft.icons.INVENTORY_ROUNDED, size=30, color=self.accent_color),
                    ft.Text("Inventaire du Matériel & Équipement", size=24, weight=ft.FontWeight.BOLD),
                ]),
                ft.Divider(),

                # Formulaire d'ajout
                ft.Text("Enregistrer du nouveau matériel", size=16, weight=ft.FontWeight.BOLD),
                ft.Row(
                    controls=[
                        self.input_nom,
                        self.dropdown_cat,
                        self.input_quantite,
                        self.dropdown_etat,
                        ft.FloatingActionButton(
                            icon=ft.icons.ADD,
                            on_click=self.ajouter_materiel,
                            bgcolor=self.accent_color
                        )
                    ],
                    spacing=10,
                    wrap=True
                ),
                ft.Divider(),

                # Liste du stock
                ft.Text("État des stocks du club", size=16, weight=ft.FontWeight.BOLD),
                self.table_materiel
            ]
        )

    def load_materiel(self):
        """Charge la liste du matériel depuis l'état global."""
        self.table_materiel.rows.clear()
        
        for index, item in enumerate(self.app.materiel):
            etat = item.get("etat", "Bon état")
            
            # Choix de la couleur selon l'usure du matériel
            color_etat = ft.colors.WHITE
            if "⚠️" in etat or "remplacer" in etat:
                color_etat = ft.colors.RED_400
            elif "Usé" in etat:
                color_etat = ft.colors.ORANGE_400
            elif "Neuf" in etat:
                color_etat = ft.colors.GREEN_400

            self.table_materiel.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.get("nom", "").upper(), weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(item.get("categorie", ""))),
                        ft.DataCell(ft.Text(item.get("quantite", "1"))),
                        ft.DataCell(ft.Text(etat, color=color_etat)),
                        ft.DataCell(
                            ft.IconButton(
                                icon=ft.icons.DELETE_OUTLINE,
                                icon_color=ft.colors.RED_300,
                                on_click=lambda e, idx=index: self.supprimer_materiel(idx)
                            )
                        ),
                    ]
                )
            )

    def ajouter_materiel(self, e):
        if not self.input_nom.value:
            return

        nouveau_stock = {
            "nom": self.input_nom.value,
            "categorie": self.dropdown_cat.value,
            "quantite": self.input_quantite.value,
            "etat": self.dropdown_etat.value
        }

        self.app.materiel.append(nouveau_stock)
        self.app.save_data()

        # Reset champ
        self.input_nom.value = ""
        self.input_quantite.value = "1"

        self.load_materiel()
        self.update()

    def supprimer_materiel(self, idx):
        if 0 <= idx < len(self.app.materiel):
            self.app.materiel.pop(idx)
            self.app.save_data()
            self.load_materiel()
            self.update()