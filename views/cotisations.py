from datetime import datetime
import flet as ft


class CotisationsView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app

        self.accent_color = self.app.association.get("accent_color", "#1E3A8A")
        self.editing_index = None

        # --- CHARGEMENT OU INITIALISATION DES TARIFS CONFIGURÉS ---
        if "tarifs" not in self.app.association:
            self.app.association["tarifs"] = {
                "u12": 100.0,
                "u18": 130.0,
                "adult": 160.0,
            }

        tarifs = self.app.association["tarifs"]

        # --- CHAMPS DE CONFIGURATION DES TARIFS DE BASE ---
        self.input_tarif_u12 = ft.TextField(
            label="Tarif -12 ans (€)",
            value=str(tarifs.get("u12", 100.0)),
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.input_tarif_u18 = ft.TextField(
            label="Tarif -18 ans (€)",
            value=str(tarifs.get("u18", 130.0)),
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        self.input_tarif_adult = ft.TextField(
            label="Tarif +18 ans (€)",
            value=str(tarifs.get("adult", 160.0)),
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.panel_config_tarifs = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.icons.SETTINGS_ROUNDED,
                                size=20,
                                color=self.accent_color,
                            ),
                            ft.Text(
                                "Configuration des Tarifs de Base",
                                weight=ft.FontWeight.BOLD,
                                size=14,
                            ),
                        ]
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Container(
                                self.input_tarif_u12, col={"sm": 12, "md": 3}
                            ),
                            ft.Container(
                                self.input_tarif_u18, col={"sm": 12, "md": 3}
                            ),
                            ft.Container(
                                self.input_tarif_adult, col={"sm": 12, "md": 3}
                            ),
                            ft.Container(
                                ft.ElevatedButton(
                                    "Enregistrer les tarifs",
                                    icon=ft.icons.SAVE,
                                    bgcolor=self.accent_color,
                                    color=ft.colors.WHITE,
                                    on_click=self.sauvegarder_tarifs_config,
                                    height=45,
                                ),
                                col={"sm": 12, "md": 3},
                            ),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=10,
            ),
            bgcolor="#1F2937",
            padding=15,
            border_radius=10,
        )

        # --- COMPOSANTS DU FORMULAIRE ---
        self.dropdown_membre = ft.Dropdown(
            label="Sélectionner l'Adhérent",
            expand=True,
            hint_text="Choisissez un adhérent...",
            on_change=self.on_membre_selectionne,
        )

        self.txt_info_age = ft.Text(
            "Sélectionnez un adhérent pour détecter la catégorie et le tarif.",
            italic=True,
            color=ft.colors.GREY_400,
            size=12,
        )

        self.dropdown_rang_famille = ft.Dropdown(
            label="Tarif Famille / Rang foyer",
            expand=True,
            options=[
                ft.dropdown.Option("1er membre (0% remise)"),
                ft.dropdown.Option("2ème membre (-10% remise)"),
                ft.dropdown.Option("3ème membre et + (-20% remise)"),
            ],
            value="1er membre (0% remise)",
            on_change=self.recalculer_montant_auto,
        )

        self.input_montant = ft.TextField(
            label="Montant (€)",
            value="150.00",
            expand=True,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.dropdown_mode = ft.Dropdown(
            label="Mode de paiement",
            expand=True,
            options=[
                ft.dropdown.Option("Chèque(s)"),
                ft.dropdown.Option("Espèces"),
                ft.dropdown.Option("Virement"),
                ft.dropdown.Option("Pass'Sport"),
                ft.dropdown.Option("ANCV / Coupons Sport"),
            ],
            value="Chèque(s)",
            on_change=self.on_mode_paiement_changed,
        )

        self.dropdown_statut = ft.Dropdown(
            label="Statut",
            expand=True,
            options=[
                ft.dropdown.Option("Encaissé / Validé"),
                ft.dropdown.Option("En attente d'encaissement"),
                ft.dropdown.Option("Incomplet / Partiel"),
            ],
            value="Encaissé / Validé",
        )

        # --- CHAMPS SUPPLÉMENTAIRES (Chèque / Pass'Sport) ---
        self.input_num_cheque = ft.TextField(label="N° de Chèque", expand=True)
        self.input_banque = ft.TextField(label="Banque", expand=True)
        self.input_num_pass_sport = ft.TextField(
            label="N° Pass'Sport", expand=True
        )

        self.container_details_paiement = ft.ResponsiveRow(
            spacing=10, visible=True
        )
        self.mettre_a_jour_champs_details()

        # Boutons d'action du formulaire
        self.btn_enregistrer = ft.ElevatedButton(
            "Valider le règlement",
            icon=ft.icons.ADD_ROUNDED,
            bgcolor=self.accent_color,
            color=ft.colors.WHITE,
            on_click=self.enregistrer_reglement,
            height=45,
        )
        self.btn_annuler_modif = ft.TextButton(
            text="Annuler", visible=False, on_click=self.annuler_modification
        )

        # --- STATISTIQUES EN EN-TÊTE ---
        self.txt_total_encasse = ft.Text(
            "0 €", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN
        )
        self.txt_total_attente = ft.Text(
            "0 €", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.ORANGE
        )

        # --- TABLEAU DES COTISATIONS ---
        self.table_cotisations = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Adhérent")),
                ft.DataColumn(ft.Text("Formule / Remise")),
                ft.DataColumn(ft.Text("Montant")),
                ft.DataColumn(ft.Text("Mode & Détails")),
                ft.DataColumn(ft.Text("Statut")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[],
        )

        self.operations_table_container = ft.Container(
            bgcolor="#1F2937",
            padding=15,
            border_radius=10,
            height=420,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Row(
                        scroll=ft.ScrollMode.ALWAYS,
                        controls=[self.table_cotisations],
                    )
                ],
            ),
        )

        # --- INITIALISATION ET CHARGEMENT ---
        self.refresh_membres_dropdown()
        self.load_cotisations_data()

        # --- ARCHITECTURE DE LA VUE (SCROLL VERTICAL GLOBAL) ---
        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=15,
            controls=[
                ft.Row(
                    [
                        ft.Icon(
                            ft.icons.MONEY_ROUNDED,
                            size=30,
                            color=self.accent_color,
                        ),
                        ft.Text(
                            "Suivi des Cotisations & Licences",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ]
                ),
                ft.Divider(height=5),
                ft.ResponsiveRow(
                    columns=12,
                    spacing=15,
                    controls=[
                        ft.Container(
                            col={"sm": 12, "md": 4},
                            bgcolor="#1F2937",
                            padding=15,
                            border_radius=10,
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Synthèse des Règlements",
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.colors.BLUE_200,
                                    ),
                                    self.create_stat_card(
                                        "Total Encaissé",
                                        self.txt_total_encasse,
                                        ft.icons.CHECK_CIRCLE,
                                        ft.colors.GREEN_900,
                                    ),
                                    self.create_stat_card(
                                        "En attente / Tiroir",
                                        self.txt_total_attente,
                                        ft.icons.PENDING_ACTIONS,
                                        ft.colors.ORANGE_900,
                                    ),
                                ],
                                spacing=10,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ),
                        ft.Container(
                            col={"sm": 12, "md": 8},
                            bgcolor="#1F2937",
                            padding=15,
                            border_radius=10,
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Enregistrer / Modifier un règlement",
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.colors.BLUE_200,
                                    ),
                                    ft.Divider(color=ft.colors.GREY_800),
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(
                                                self.dropdown_membre,
                                                col={"sm": 12, "md": 12},
                                            ),
                                        ]
                                    ),
                                    self.txt_info_age,
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(
                                                self.dropdown_rang_famille,
                                                col={"sm": 12, "md": 6},
                                            ),
                                            ft.Container(
                                                self.input_montant,
                                                col={"sm": 12, "md": 6},
                                            ),
                                        ]
                                    ),
                                    ft.ResponsiveRow(
                                        [
                                            ft.Container(
                                                self.dropdown_mode,
                                                col={"sm": 12, "md": 6},
                                            ),
                                            ft.Container(
                                                self.dropdown_statut,
                                                col={"sm": 12, "md": 6},
                                            ),
                                        ]
                                    ),
                                    self.container_details_paiement,
                                    ft.Row(
                                        [
                                            self.btn_annuler_modif,
                                            self.btn_enregistrer,
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                        spacing=10,
                                    ),
                                ],
                                spacing=10,
                            ),
                        ),
                    ],
                ),
                self.panel_config_tarifs,
                ft.Divider(height=5),
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(
                                    ft.icons.HISTORY_ROUNDED,
                                    size=20,
                                    color=self.accent_color,
                                ),
                                ft.Text(
                                    "Historique des règlements reçus",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Text(
                            "◄ Glissez de gauche à droite sur le tableau ►",
                            size=12,
                            italic=True,
                            color=ft.colors.GREY_400,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.operations_table_container,
            ],
        )

    def sauvegarder_tarifs_config(self, e):
        try:
            self.app.association["tarifs"] = {
                "u12": float(self.input_tarif_u12.value or 100),
                "u18": float(self.input_tarif_u18.value or 130),
                "adult": float(self.input_tarif_adult.value or 160),
            }
            self.app.save_data()
            self.recalculer_montant_auto(None)
            self.show_snack("✅ Tarifs mis à jour avec succès !")
        except ValueError:
            self.show_snack(
                "⚠️ Veuillez saisir des montants valides.", is_error=True
            )

    def calculer_age(self, date_str):
        if not date_str:
            return None
        formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
        for fmt in formats:
            try:
                birth = datetime.strptime(str(date_str).strip(), fmt)
                today = datetime.today()
                return (
                    today.year
                    - birth.year
                    - ((today.month, today.day) < (birth.month, birth.day))
                )
            except ValueError:
                continue
        return None

    def obtenir_categorie_et_tarif_base(self, age):
        tarifs = self.app.association.get(
            "tarifs", {"u12": 100.0, "u18": 130.0, "adult": 160.0}
        )
        if age is None:
            return "+18 ans", float(tarifs.get("adult", 160.0))
        if age < 12:
            return "-12 ans", float(tarifs.get("u12", 100.0))
        elif age < 18:
            return "-18 ans", float(tarifs.get("u18", 130.0))
        else:
            return "+18 ans", float(tarifs.get("adult", 160.0))

    def on_membre_selectionne(self, e):
        self.recalculer_montant_auto(None)

    def recalculer_montant_auto(self, e):
        if not self.dropdown_membre.value:
            return

        key_selected = self.dropdown_membre.value
        membre = next(
            (
                m
                for m in self.app.membres
                if f"{m.get('nom', '').strip()} {m.get('prenom', '').strip()}".strip()
                == key_selected
            ),
            None,
        )

        if not membre:
            return

        age = self.calculer_age(membre.get("date_naissance"))
        cat, tarif_base = self.obtenir_categorie_et_tarif_base(age)

        str_age = f"{age} ans" if age is not None else "Inconnu"
        self.txt_info_age.value = f"🎂 Âge détecté : {str_age}  ➜  Catégorie {cat} (Tarif de base : {tarif_base:.2f} €)"

        rang = self.dropdown_rang_famille.value
        taux_remise = 0.0
        if "2ème membre" in rang:
            taux_remise = 0.10
        elif "3ème membre" in rang:
            taux_remise = 0.20

        montant_final = tarif_base * (1.0 - taux_remise)
        self.input_montant.value = f"{montant_final:.2f}"
        self.update()

    def create_stat_card(self, title, text_control, icon, bg_color):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=30, color=ft.colors.WHITE),
                    ft.Column(
                        [
                            ft.Text(title, size=11, color=ft.colors.GREY_400),
                            text_control,
                        ],
                        spacing=1,
                    ),
                ]
            ),
            bgcolor=bg_color,
            padding=10,
            border_radius=8,
            width=250,
        )

    def refresh_membres_dropdown(self):
        options = []
        for m in self.app.membres:
            nom = m.get("nom", "").strip()
            prenom = m.get("prenom", "").strip()
            full_name = f"{nom} {prenom}".strip()
            licence = m.get("licence") or m.get("licence") or "N/A"
            options.append(
                ft.dropdown.Option(
                    key=full_name, text=f"{nom.upper()} {prenom} (Licence: {licence})"
                )
            )

        self.dropdown_membre.options = options
        if not self.app.membres:
            self.dropdown_membre.hint_text = (
                "⚠️ Créez d'abord des adhérents dans l'onglet Dédié"
            )

    def on_mode_paiement_changed(self, e):
        self.mettre_a_jour_champs_details()
        self.update()

    def mettre_a_jour_champs_details(self):
        mode = self.dropdown_mode.value
        self.container_details_paiement.controls.clear()

        if mode == "Chèque(s)":
            self.container_details_paiement.visible = True
            self.container_details_paiement.controls.extend(
                [
                    ft.Container(
                        self.input_num_cheque, col={"sm": 12, "md": 6}
                    ),
                    ft.Container(self.input_banque, col={"sm": 12, "md": 6}),
                ]
            )
        elif mode == "Pass'Sport":
            self.container_details_paiement.visible = True
            self.container_details_paiement.controls.append(
                ft.Container(
                    self.input_num_pass_sport, col={"sm": 12, "md": 12}
                )
            )
        else:
            self.container_details_paiement.visible = False

    def load_cotisations_data(self):
        self.table_cotisations.rows.clear()
        total_encasse = 0.0
        total_attente = 0.0

        for index, c in enumerate(reversed(self.app.cotisations)):
            real_index = len(self.app.cotisations) - 1 - index

            montant = float(c.get("montant", 0))
            statut = c.get("statut")
            mode = c.get("mode")
            formule_info = c.get("formule_info", "Tarif Standard")

            mode_details = mode or ""
            if mode == "Chèque(s)" and (c.get("num_cheque") or c.get("banque")):
                mode_details += f" (N°: {c.get('num_cheque', '-')}, Banque: {c.get('banque', '-')})"
            elif mode == "Pass'Sport" and c.get("num_pass_sport"):
                mode_details += f" (N°: {c.get('num_pass_sport', '-')})"

            if statut == "Encaissé / Validé":
                total_encasse += montant
                badge_color = ft.colors.GREEN_400
            elif statut == "En attente d'encaissement":
                total_attente += montant
                badge_color = ft.colors.ORANGE_400
            else:
                total_attente += montant
                badge_color = ft.colors.BLUE_400

            self.table_cotisations.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(c.get("date", ""))),
                        ft.DataCell(ft.Text(c.get("membre", ""))),
                        ft.DataCell(
                            ft.Text(formule_info, size=12, italic=True)
                        ),
                        ft.DataCell(
                            ft.Text(
                                f"{montant:.2f} €", weight=ft.FontWeight.BOLD
                            )
                        ),
                        ft.DataCell(ft.Text(mode_details)),
                        ft.DataCell(ft.Text(statut or "", color=badge_color)),
                        ft.DataCell(
                            ft.Row(
                                [
                                    ft.IconButton(
                                        ft.icons.EDIT_ROUNDED,
                                        icon_color=ft.colors.AMBER_400,
                                        icon_size=18,
                                        tooltip="Modifier",
                                        on_click=lambda e,
                                        idx=real_index: self.preparer_modification(
                                            idx
                                        ),
                                    ),
                                    ft.IconButton(
                                        ft.icons.DELETE_ROUNDED,
                                        icon_color=ft.colors.RED_400,
                                        icon_size=18,
                                        tooltip="Supprimer",
                                        on_click=lambda e,
                                        idx=real_index: self.supprimer_reglement(
                                            idx
                                        ),
                                    ),
                                ],
                                spacing=0,
                            )
                        ),
                    ]
                )
            )

        self.txt_total_encasse.value = f"{total_encasse:.2f} €"
        self.txt_total_attente.value = f"{total_attente:.2f} €"

    def enregistrer_reglement(self, e):
        if not self.dropdown_membre.value:
            self.dropdown_membre.error_text = "Sélection obligatoire"
            self.update()
            return

        self.dropdown_membre.error_text = None

        nouveau_paiement = {
            "date": datetime.now().strftime("%d/%m/%Y"),
            "membre": self.dropdown_membre.value,
            "formule_info": self.dropdown_rang_famille.value,
            "montant": (
                self.input_montant.value if self.input_montant.value else "0"
            ),
            "mode": self.dropdown_mode.value,
            "statut": self.dropdown_statut.value,
            "num_cheque": (
                self.input_num_cheque.value
                if self.dropdown_mode.value == "Chèque(s)"
                else ""
            ),
            "banque": (
                self.input_banque.value
                if self.dropdown_mode.value == "Chèque(s)"
                else ""
            ),
            "num_pass_sport": (
                self.input_num_pass_sport.value
                if self.dropdown_mode.value == "Pass'Sport"
                else ""
            ),
        }

        if self.editing_index is not None:
            nouveau_paiement["date"] = self.app.cotisations[
                self.editing_index
            ].get("date", datetime.now().strftime("%d/%m/%Y"))
            self.app.cotisations[self.editing_index] = nouveau_paiement
            self.editing_index = None
            self.btn_enregistrer.text = "Valider le règlement"
            self.btn_enregistrer.icon = ft.icons.ADD_ROUNDED
            self.btn_annuler_modif.visible = False
            msg_confirmation = "✏️ Règlement mis à jour avec succès !"
        else:
            self.app.cotisations.append(nouveau_paiement)
            msg_confirmation = "✅ Règlement enregistré avec succès !"

        self.app.save_data()

        self.dropdown_membre.value = None
        self.txt_info_age.value = (
            "Sélectionnez un adhérent pour détecter la catégorie et le tarif."
        )
        self.dropdown_rang_famille.value = "1er membre (0% remise)"
        self.input_num_cheque.value = ""
        self.input_banque.value = ""
        self.input_num_pass_sport.value = ""
        self.mettre_a_jour_champs_details()

        self.load_cotisations_data()
        self.show_snack(msg_confirmation)
        self.update()

    def preparer_modification(self, index):
        if index < 0 or index >= len(self.app.cotisations):
            return

        self.editing_index = index
        c = self.app.cotisations[index]

        self.dropdown_membre.value = c.get("membre")
        self.dropdown_rang_famille.value = c.get(
            "formule_info", "1er membre (0% remise)"
        )
        self.input_montant.value = str(c.get("montant", ""))
        self.dropdown_mode.value = c.get("mode", "Chèque(s)")
        self.dropdown_statut.value = c.get("statut", "Encaissé / Validé")

        self.input_num_cheque.value = c.get("num_cheque", "")
        self.input_banque.value = c.get("banque", "")
        self.input_num_pass_sport.value = c.get("num_pass_sport", "")

        self.mettre_a_jour_champs_details()

        self.btn_enregistrer.text = "Mettre à jour"
        self.btn_enregistrer.icon = ft.icons.EDIT_ROUNDED
        self.btn_annuler_modif.visible = True
        self.update()

    def annuler_modification(self, e):
        self.editing_index = None
        self.dropdown_membre.value = None
        self.txt_info_age.value = (
            "Sélectionnez un adhérent pour détecter la catégorie et le tarif."
        )
        self.dropdown_rang_famille.value = "1er membre (0% remise)"
        self.input_num_cheque.value = ""
        self.input_banque.value = ""
        self.input_num_pass_sport.value = ""
        self.mettre_a_jour_champs_details()

        self.btn_enregistrer.text = "Valider le règlement"
        self.btn_enregistrer.icon = ft.icons.ADD_ROUNDED
        self.btn_annuler_modif.visible = False
        self.update()

    def supprimer_reglement(self, index):
        if 0 <= index < len(self.app.cotisations):
            del self.app.cotisations[index]
            self.app.save_data()

            if self.editing_index == index:
                self.annuler_modification(None)

            self.load_cotisations_data()
            self.show_snack(
                "🗑️ Règlement supprimé avec succès !", is_error=True
            )
            self.update()

    def show_snack(self, message, is_error=False):
        snack = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700,
        )
        self.app.page.overlay.append(snack)
        snack.open = True
        self.app.page.update()