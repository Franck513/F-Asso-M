# views/professeurs.py
import os
import platform
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
import flet as ft


class ProfesseursView(ft.Container):
    BAREME_KM = 0.45  # Taux officiel au km (€)

    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app
        self.accent_color = getattr(self.app, "association", {}).get("accent_color", "#1E3A8A")
        self.selected_professeur = None
        self.frais_index_pour_justificatif = None

        # FilePickers
        self.file_picker = ft.FilePicker(on_result=self.on_file_selected)
        self.justif_picker = ft.FilePicker(on_result=self.on_justificatif_frais_selected)

        # Formulaire de saisie d'un enseignant
        self.input_nom = ft.TextField(label="Nom", col={"sm": 12, "md": 6})
        self.input_prenom = ft.TextField(label="Prénom", col={"sm": 12, "md": 6})
        self.input_discipline = ft.TextField(label="Discipline / Sport", hint_text="Ex: Basket, Gym, Judo, Multisport", col={"sm": 12, "md": 6})
        self.input_email = ft.TextField(label="Email", col={"sm": 12, "md": 6})
        self.input_tel = ft.TextField(label="Téléphone", col={"sm": 12, "md": 6})
        self.input_adresse = ft.TextField(label="Adresse complète", multiline=True, min_lines=2, col={"sm": 12})
        self.input_niveau = ft.TextField(label="Niveau / Catégorie", col={"sm": 12, "md": 6})
        self.input_diplome = ft.TextField(label="Diplômes (ex: BPJEPS, CQP, DEJEPS, BAF)", col={"sm": 12, "md": 6})

        # Formulaire d'ajout rapide de défraiement / versement
        self.def_date = ft.TextField(label="Date", value=datetime.now().strftime("%d/%m/%Y"), col={"sm": 6, "md": 2})
        self.def_motif = ft.TextField(label="Motif du déplacement / Règlement", hint_text="Ex: Match, Stage, Avance sur frais", col={"sm": 12, "md": 4})
        self.def_type = ft.Dropdown(
            label="Type de Frais",
            options=[
                ft.dropdown.Option("Kms"),
                ft.dropdown.Option("Hôtel"),
                ft.dropdown.Option("Repas"),
                ft.dropdown.Option("Avance / Règlement"),
                ft.dropdown.Option("Autre")
            ],
            value="Kms",
            col={"sm": 6, "md": 2}
        )
        self.def_statut = ft.Dropdown(
            label="Statut",
            options=[
                ft.dropdown.Option("Versé / Réglé"),
                ft.dropdown.Option("En attente (Dû)"),
            ],
            value="Versé / Réglé",
            col={"sm": 6, "md": 2}
        )
        self.def_montant = ft.TextField(label="Montant (€)", keyboard_type=ft.KeyboardType.NUMBER, col={"sm": 6, "md": 2})
        self.def_justifie = ft.Checkbox(label="Justificatif disponible ?", value=True)

        # Bouton d'enregistrement explicite
        self.btn_enregistrer_frais = ft.ElevatedButton(
            "➕ Enregistrer le frais / règlement",
            icon=ft.icons.ADD,
            bgcolor=self.accent_color,
            color=ft.colors.WHITE,
            height=45,
            on_click=self.ajouter_defraiement
        )

        # Bascule de Saison
        self.sw_toutes_saisons = ft.Switch(
            label="Voir toutes les saisons",
            value=False,
            on_change=lambda e: self.charger_defraiements_professeur()
        )

        # Liste d'enseignants horizontale (Bandeau supérieur)
        self.prof_list = ft.Row(spacing=10, scroll=ft.ScrollMode.AUTO)
        
        # Liste de documents
        self.docs_list = ft.Column(spacing=5, scroll=ft.ScrollMode.AUTO, height=200)
        
        # Table des défraiements
        self.defraiements_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Saison")),
                ft.DataColumn(ft.Text("Motif")),
                ft.DataColumn(ft.Text("Type")),
                ft.DataColumn(ft.Text("Statut")),
                ft.DataColumn(ft.Text("Montant")),
                ft.DataColumn(ft.Text("Justificatif")),
                ft.DataColumn(ft.Text("Fichier")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[]
        )

        # Widget d'Équilibre Financier
        self.lbl_total_dus = ft.Text("0.00 €", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.ORANGE_300)
        self.lbl_total_verses = ft.Text("0.00 €", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_300)
        self.lbl_equilibre = ft.Text("0.00 €", size=18, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_400)
        self.lbl_equilibre_status = ft.Text("Compte équilibré", size=12, italic=True, color=ft.colors.GREY_400)

        # Vumètre URSSAF
        self.vumetre_label = ft.Text("Indice de Conformité URSSAF", weight=ft.FontWeight.BOLD, size=14)
        self.vumetre_bar = ft.ProgressBar(height=8, value=0, color=ft.colors.GREEN)
        self.vumetre_status = ft.Text("Sécurisé", weight=ft.FontWeight.BOLD, size=12)
        self.vumetre_conseils = ft.Text("", italic=True, size=11, color=ft.colors.GREY_400)

        # Zone d'affichage dynamique principale (en dessous des profs)
        self.right_container = ft.Container(
            content=ft.Text("Veuillez sélectionner un intervenant ci-dessus.", italic=True, size=15, color=ft.colors.GREY_500),
            alignment=ft.alignment.center,
            padding=20,
            expand=True
        )

        # Layout Principal
        self.content = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                # BANDEAU ENSEIGNANTS EN HAUT
                ft.Container(
                    padding=15,
                    bgcolor="#0f172a",
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.colors.GREY_800)),
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Icon(ft.icons.SPORTS, color=ft.colors.BLUE_400, size=24),
                                ft.Text("Intervenants & Coachs", size=20, weight=ft.FontWeight.BOLD),
                            ]),
                            ft.ElevatedButton(
                                "➕ Nouvel Intervenant", 
                                icon=ft.icons.ADD,
                                on_click=self.ouvrir_dialogue_creation, 
                                bgcolor=self.accent_color, 
                                color=ft.colors.WHITE
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(
                            padding=ft.padding.only(top=10),
                            content=self.prof_list
                        )
                    ])
                ),
                # CONTENU DESSOUS (TABLEAU & DÉTAILS)
                ft.Container(
                    expand=True,
                    padding=10,
                    content=self.right_container
                )
            ]
        )

        self.refresh_prof_list()

    def did_mount(self):
        if self.page:
            if self.file_picker not in self.page.overlay:
                self.page.overlay.append(self.file_picker)
            if self.justif_picker not in self.page.overlay:
                self.page.overlay.append(self.justif_picker)
            self.page.update()

    def _show_snackbar(self, message: str, is_error: bool = False):
        color = ft.colors.RED_700 if is_error else ft.colors.GREEN_700
        if self.page:
            self.page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=color)
            self.page.snack_bar.open = True
            self.page.update()

    def _parse_float(self, value, default: float = 0.0) -> float:
        try:
            return float(str(value).replace(",", ".").strip())
        except (ValueError, AttributeError):
            return default

    def _get_prof_dir(self, subfolder: str = "") -> Path:
        if not self.selected_professeur:
            raise ValueError("Aucun intervenant sélectionné.")
        folder_name = self.app.db._get_safe_folder_name(
            self.selected_professeur.get("nom", ""), 
            self.selected_professeur.get("prenom", "")
        )
        path = self.app.db.professeurs_root / folder_name
        if subfolder:
            path /= subfolder
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_prof_fullname(self, prof: dict = None) -> str:
        p = prof or self.selected_professeur or {}
        return f"{p.get('nom', '').strip()} {p.get('prenom', '').strip()}".strip()

    def refresh_prof_list(self):
        self.prof_list.controls.clear()
        tous_professeurs = getattr(self.app, "professeurs", [])
        saison_act = getattr(self.app, "saison_active", "")
        
        if not tous_professeurs:
            self.prof_list.controls.append(
                ft.Text("Aucun intervenant enregistré.", italic=True, color=ft.colors.GREY_500)
            )
        else:
            for p in tous_professeurs:
                nom_prenom = f"{p.get('prenom', '')} {p.get('nom', '')}".strip()
                saisons_prof = p.setdefault("saisons", [])
                est_dans_saison = saison_act in saisons_prof
                is_selected = (self.selected_professeur == p)
                
                if is_selected:
                    bgcolor = "#2563eb"
                    border_color = ft.colors.BLUE_400
                    text_color = ft.colors.WHITE
                    sub_color = ft.colors.BLUE_100
                elif est_dans_saison:
                    bgcolor = "#1e293b"
                    border_color = ft.colors.GREY_800
                    text_color = ft.colors.GREY_200
                    sub_color = ft.colors.GREY_400
                else:
                    bgcolor = "#0f172a"
                    border_color = ft.colors.GREY_800
                    text_color = ft.colors.GREY_500
                    sub_color = ft.colors.GREY_600

                discipline = p.get("discipline", "Multisport")
                niveau = p.get("niveau", "")
                sub_text = f"{discipline} • {niveau}".strip(" •") if est_dans_saison else f"⚠️ Non inscrit en {saison_act}"

                card = ft.Container(
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border_radius=8,
                    bgcolor=bgcolor,
                    border=ft.border.all(1, border_color),
                    on_click=lambda e, prof=p: self.select_professeur(prof),
                    content=ft.Row([
                        ft.Icon(
                            ft.icons.PERSON, 
                            color=text_color if is_selected else (self.accent_color if est_dans_saison else ft.colors.GREY_600),
                            size=20
                        ),
                        ft.Column([
                            ft.Text(
                                nom_prenom.upper(), 
                                size=13, 
                                weight=ft.FontWeight.BOLD,
                                color=text_color
                            ),
                            ft.Text(
                                sub_text, 
                                size=11, 
                                color=sub_color
                            ),
                        ], spacing=2)
                    ], spacing=10)
                )
                self.prof_list.controls.append(card)

        if self.page:
            self.page.update()

    def select_professeur(self, prof):
        self.selected_professeur = prof
        self.charger_champs_professeur()
        self.charger_documents_professeur()
        self.charger_defraiements_professeur()

        self.right_container.content = self._build_tabs_view()
        self.refresh_prof_list()

    def _build_tabs_view(self) -> ft.Tabs:
        saison_act = getattr(self.app, "saison_active", "")
        saisons_prof = self.selected_professeur.get("saisons", [])
        est_dans_saison = saison_act in saisons_prof

        if est_dans_saison:
            btn_saison = ft.ElevatedButton(
                f"🗑️ Retirer de la saison {saison_act}", 
                on_click=self.retirer_professeur_saison, 
                bgcolor=ft.colors.RED_700, 
                color=ft.colors.WHITE
            )
        else:
            btn_saison = ft.ElevatedButton(
                f"➕ Réintégrer dans la saison {saison_act}", 
                on_click=self.reintegrer_professeur_saison, 
                bgcolor=ft.colors.GREEN_700, 
                color=ft.colors.WHITE
            )

        return ft.Tabs(
            selected_index=0,
            animation_duration=300,
            expand=True,
            tabs=[
                ft.Tab(
                    text="Frais & Défraiements",
                    icon=ft.icons.EURO_SYMBOL,
                    content=ft.Container(
                        padding=15,
                        content=ft.Column([
                            ft.Row([
                                ft.Text("Défraiements & Comptabilité", size=16, weight=ft.FontWeight.BOLD),
                                self.sw_toutes_saisons,
                                ft.ElevatedButton(
                                    "🚗 Note Kilométrique Officielle",
                                    icon=ft.icons.DIRECTIONS_CAR,
                                    bgcolor=ft.colors.GREEN_800,
                                    color=ft.colors.WHITE,
                                    on_click=self.ouvrir_formulaire_kilometrique_legal
                                )
                            ], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            
                            ft.Container(
                                padding=15,
                                border_radius=10,
                                bgcolor="#1e293b",
                                border=ft.border.all(1, ft.colors.GREY_800),
                                content=ft.Column([
                                    ft.Text("Ajout rapide de frais ou règlement", size=14, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                                    ft.ResponsiveRow([
                                        self.def_date,
                                        self.def_motif,
                                        self.def_type,
                                        self.def_statut,
                                        self.def_montant,
                                    ]),
                                    ft.ResponsiveRow([
                                        ft.Container(
                                            content=self.def_justifie,
                                            col={"sm": 12, "md": 6},
                                            alignment=ft.alignment.center_left
                                        ),
                                        ft.Container(
                                            content=self.btn_enregistrer_frais,
                                            col={"sm": 12, "md": 6},
                                            alignment=ft.alignment.center_right
                                        ),
                                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
                                ], spacing=12)
                            ),
                            
                            ft.Divider(),

                            ft.Container(
                                padding=15,
                                border_radius=10,
                                bgcolor="#0f172a",
                                border=ft.border.all(1, ft.colors.BLUE_900),
                                content=ft.Column([
                                    ft.Row([
                                        ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET, color=ft.colors.BLUE_400, size=20),
                                        ft.Text("Équilibre Financier de l'Intervenant", weight=ft.FontWeight.BOLD, size=15),
                                    ]),
                                    ft.ResponsiveRow([
                                        ft.Container(
                                            col={"sm": 12, "md": 4},
                                            padding=10,
                                            bgcolor="#1e293b",
                                            border_radius=8,
                                            content=ft.Column([
                                                ft.Text("Frais Engagés (Dus)", size=11, color=ft.colors.GREY_400),
                                                self.lbl_total_dus
                                            ])
                                        ),
                                        ft.Container(
                                            col={"sm": 12, "md": 4},
                                            padding=10,
                                            bgcolor="#1e293b",
                                            border_radius=8,
                                            content=ft.Column([
                                                ft.Text("Règlements Versés", size=11, color=ft.colors.GREY_400),
                                                self.lbl_total_verses
                                            ])
                                        ),
                                        ft.Container(
                                            col={"sm": 12, "md": 4},
                                            padding=10,
                                            bgcolor="#1e293b",
                                            border_radius=8,
                                            content=ft.Column([
                                                ft.Text("Solde / Équilibre", size=11, color=ft.colors.GREY_400),
                                                self.lbl_equilibre,
                                                self.lbl_equilibre_status
                                            ])
                                        ),
                                    ], spacing=10),
                                ], spacing=10)
                            ),

                            ft.Container(
                                padding=10,
                                border_radius=8,
                                bgcolor="#1e293b",
                                content=ft.Column([
                                    self.vumetre_label,
                                    self.vumetre_bar,
                                    ft.Row([self.vumetre_status], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    self.vumetre_conseils
                                ], spacing=4)
                            ),

                            ft.Divider(),
                            ft.Text("Historique détaillé des opérations :", size=14, weight=ft.FontWeight.BOLD),
                            
                            ft.Container(
                                padding=10,
                                border_radius=8,
                                bgcolor="#1e293b",
                                border=ft.border.all(1, ft.colors.GREY_800),
                                content=ft.Row([self.defraiements_table], scroll=ft.ScrollMode.AUTO)
                            )

                        ], spacing=12, scroll=ft.ScrollMode.AUTO)
                    )
                ),
                ft.Tab(
                    text="Fiche administrative",
                    icon=ft.icons.CONTACT_PAGE,
                    content=ft.Container(
                        padding=15,
                        content=ft.Column([
                            ft.Text("Coordonnées & Discipline", size=16, weight=ft.FontWeight.BOLD),
                            ft.ResponsiveRow([
                                self.input_nom,
                                self.input_prenom,
                                self.input_discipline,
                                self.input_email,
                                self.input_tel,
                                self.input_adresse,
                                self.input_niveau,
                                self.input_diplome,
                            ]),
                            ft.Row([
                                ft.ElevatedButton("💾 Enregistrer les modifications", on_click=self.sauvegarder_modifs_prof, bgcolor=self.accent_color, color=ft.colors.WHITE),
                                btn_saison,
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, scroll=ft.ScrollMode.AUTO)
                        ], spacing=15, scroll=ft.ScrollMode.AUTO)
                    )
                ),
                ft.Tab(
                    text="Diplômes & Justificatifs",
                    icon=ft.icons.ATTACH_FILE,
                    content=ft.Container(
                        padding=15,
                        content=ft.Column([
                            ft.Text("Documents administratifs", size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Sauvegardez ici les cartes professionnelles, cartes d'identité, scans de diplômes ou extraits de casier judiciaire (B2).", size=12, italic=True, color=ft.colors.GREY_400),
                            ft.Row([
                                ft.ElevatedButton("📁 Sélectionner un document", on_click=lambda e: self.file_picker.pick_files(allow_multiple=False), bgcolor=self.accent_color, color=ft.colors.WHITE),
                                ft.OutlinedButton("📂 Ouvrir le dossier des documents", on_click=self.ouvrir_dossier_docs)
                            ], wrap=True),
                            ft.Divider(),
                            self.docs_list
                        ], spacing=15, scroll=ft.ScrollMode.AUTO)
                    )
                ),
            ]
        )

    def charger_champs_professeur(self):
        p = self.selected_professeur or {}
        self.input_nom.value = p.get("nom", "")
        self.input_prenom.value = p.get("prenom", "")
        self.input_discipline.value = p.get("discipline", "")
        self.input_email.value = p.get("email", "")
        self.input_tel.value = p.get("telephone", "")
        self.input_adresse.value = p.get("adresse", "")
        self.input_niveau.value = p.get("niveau", "")
        self.input_diplome.value = p.get("diplome", "")

    def sauvegarder_modifs_prof(self, e):
        if not self.selected_professeur:
            return
        p = self.selected_professeur
        p["nom"] = self.input_nom.value.strip().upper()
        p["prenom"] = self.input_prenom.value.strip().capitalize()
        p["discipline"] = self.input_discipline.value.strip()
        p["email"] = self.input_email.value.strip()
        p["telephone"] = self.input_tel.value.strip()
        p["adresse"] = self.input_adresse.value.strip()
        p["niveau"] = self.input_niveau.value.strip()
        p["diplome"] = self.input_diplome.value.strip()

        self.app.save_data()
        self._show_snackbar("Fiche intervenant modifiée avec succès !")
        self.select_professeur(p)

    def retirer_professeur_saison(self, e):
        if not self.selected_professeur:
            return
        
        saison_act = getattr(self.app, "saison_active", "Courante")
        prof_nom = self._get_prof_fullname()

        def executer_retrait(evt):
            saisons = self.selected_professeur.setdefault("saisons", [saison_act])
            if saison_act in saisons:
                saisons.remove(saison_act)

            self.app.save_data()
            self._fermer_dialogue(dlg_retrait)
            self.select_professeur(self.selected_professeur) 
            self.refresh_prof_list()
            self._show_snackbar(f"L'intervenant {prof_nom} a été retiré de la saison {saison_act}.")

        dlg_retrait = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.icons.WARNING_AMBER, color=ft.colors.ORANGE_400),
                ft.Text("Retirer de la saison active")
            ]),
            content=ft.Text(f"Voulez-vous retirer l'intervenant :\n\n👉 {prof_nom}\n\nde la saison active ({saison_act}) ?\n\n💡 Son profil global et l'historique de ses défraiements des saisons passées seront intégralement conservés."),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._fermer_dialogue(dlg_retrait)),
                ft.ElevatedButton("Confirmer le retrait", bgcolor=ft.colors.RED_700, color=ft.colors.WHITE, on_click=executer_retrait)
            ]
        )

        if self.page:
            self.page.overlay.append(dlg_retrait)
            dlg_retrait.open = True
            self.page.update()

    def reintegrer_professeur_saison(self, e):
        """Remet l'intervenant dans la saison active."""
        if not self.selected_professeur:
            return
        
        saison_act = getattr(self.app, "saison_active", "Courante")
        saisons = self.selected_professeur.setdefault("saisons", [])
        
        if saison_act not in saisons:
            saisons.append(saison_act)
            self.app.save_data()
            
        self._show_snackbar(f"L'intervenant a été réintégré dans la saison {saison_act} avec succès !")
        self.select_professeur(self.selected_professeur)
        self.refresh_prof_list()

    def on_file_selected(self, e: ft.FilePickerResultEvent):
        if e.files and self.selected_professeur:
            src_path = Path(e.files[0].path)
            if not src_path.exists():
                return

            try:
                dest_dir = self._get_prof_dir("documents")
                dest_path = dest_dir / src_path.name
                shutil.copy(src_path, dest_path)
                self._show_snackbar("Document ajouté avec succès !")
                self.charger_documents_professeur()
            except Exception as ex:
                self._show_snackbar(f"Erreur d'ajout du document : {ex}", is_error=True)

    def charger_documents_professeur(self):
        self.docs_list.controls.clear()
        if not self.selected_professeur:
            return

        dest_dir = self._get_prof_dir("documents")
        files = [f for f in dest_dir.iterdir() if f.is_file()]

        if not files:
            self.docs_list.controls.append(ft.Text("Aucun document lié pour le moment.", italic=True, color=ft.colors.GREY_500))
        else:
            for f in files:
                self.docs_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.INSERT_DRIVE_FILE, color=self.accent_color),
                            ft.Text(f.name, expand=True, size=13),
                            ft.IconButton(
                                icon=ft.icons.OPEN_IN_NEW,
                                icon_color=ft.colors.BLUE_200,
                                tooltip="Ouvrir",
                                on_click=lambda e, path=f: self.ouvrir_document(Path(path))
                            ),
                            ft.IconButton(
                                icon=ft.icons.DELETE,
                                icon_color=ft.colors.RED_400,
                                tooltip="Supprimer",
                                on_click=lambda e, path=f: self.supprimer_document(Path(path))
                            )
                        ]),
                        padding=5,
                        border=ft.border.all(1, ft.colors.GREY_800),
                        border_radius=6,
                    )
                )
        if self.page:
            self.page.update()

    def ouvrir_document(self, path: Path):
        try:
            if platform.system() == "Windows":
                os.startfile(str(path))
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as e:
            self._show_snackbar(f"Impossible d'ouvrir le fichier : {e}", is_error=True)

    def supprimer_document(self, path: Path):
        try:
            path.unlink(missing_ok=True)
            self.charger_documents_professeur()
            self._show_snackbar("Document supprimé.")
        except Exception as e:
            self._show_snackbar(f"Erreur de suppression : {e}", is_error=True)

    def ouvrir_dossier_docs(self, e):
        if self.selected_professeur:
            path = self._get_prof_dir("documents")
            self.ouvrir_document(path)

    def _generer_pdf_kilometrique(self, filepath: Path, prof_nom: str, asso_data: dict, saison_act: str,
                                   txt_marque: str, txt_immat: str, dd_cv: str, txt_date_trajet: str,
                                   txt_depart: str, txt_arrivee: str, txt_motif_trajet: str,
                                   kms: float, montant_total: float, dd_valideur: str):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

            doc = SimpleDocTemplate(str(filepath), pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
            story = []
            styles = getSampleStyleSheet()

            style_title = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor("#1E3A8A"), alignment=1, spaceAfter=10)
            style_subtitle = ParagraphStyle('SubTitle', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor("#475569"), alignment=1, spaceAfter=20)
            style_section = ParagraphStyle('Section', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor("#1E3A8A"), spaceBefore=10, spaceAfter=8)
            style_normal = ParagraphStyle('NormalText', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor("#1E293B"))
            style_bold = ParagraphStyle('BoldText', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor("#0F172A"), fontName="Helvetica-Bold")

            asso_nom = asso_data.get('nom', 'ASSOCIATION LOI 1901')
            president_nom = asso_data.get('president', 'Le Président')

            story.append(Paragraph("NOTE DE FRAIS KILOMÉTRIQUES OFFICIELLE", style_title))
            story.append(Paragraph(f"<b>{asso_nom}</b> — Saison {saison_act}", style_subtitle))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=15))

            story.append(Paragraph("1. Bénéficiaire & Véhicule", style_section))
            data_prof = [
                [Paragraph("<b>Intervenant / Bénéficiaire :</b>", style_normal), Paragraph(prof_nom, style_bold)],
                [Paragraph("<b>Véhicule :</b>", style_normal), Paragraph(f"{txt_marque} (Immat : {txt_immat})", style_normal)],
                [Paragraph("<b>Puissance Fiscale :</b>", style_normal), Paragraph(dd_cv, style_normal)]
            ]
            t_prof = Table(data_prof, colWidths=[180, 320])
            t_prof.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
                ('PADDING', (0,0), (-1,-1), 6),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            story.append(t_prof)
            story.append(Spacer(1, 15))

            story.append(Paragraph("2. Détails du Déplacement", style_section))
            data_trajet = [
                [Paragraph("<b>Date du trajet :</b>", style_normal), Paragraph(txt_date_trajet, style_normal)],
                [Paragraph("<b>Trajet effectué :</b>", style_normal), Paragraph(f"{txt_depart} ➔ {txt_arrivee}", style_normal)],
                [Paragraph("<b>Motif du déplacement :</b>", style_normal), Paragraph(txt_motif_trajet, style_normal)],
                [Paragraph("<b>Distance A/R :</b>", style_normal), Paragraph(f"{kms} km", style_normal)],
                [Paragraph("<b>Barème appliqué :</b>", style_normal), Paragraph(f"{self.BAREME_KM:.2f} € / km (URSSAF)", style_normal)],
                [Paragraph("<b>MONTANT TOTAL REMBOURSÉ :</b>", style_bold), Paragraph(f"<b>{montant_total:.2f} €</b>", style_bold)]
            ]
            t_trajet = Table(data_trajet, colWidths=[180, 320])
            t_trajet.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-2), colors.HexColor("#F8FAFC")),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#DCFCE7")),
                ('PADDING', (0,0), (-1,-1), 6),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            story.append(t_trajet)
            story.append(Spacer(1, 15))

            story.append(Paragraph("3. Validation & Engagement", style_section))
            txt_validation = f"""
            [X] Je soussigné(e) <b>{prof_nom}</b> certifie sur l'honneur l'exactitude des renseignements ci-dessus et des kilomètres parcourus.<br/><br/>
            [X] Validé et vérifié par l'association <b>{asso_nom}</b> (Représentée par : <b>{dd_valideur}</b>)<br/>
            <i>Date de validation : {datetime.now().strftime('%d/%m/%Y à %H:%M')}</i>
            """
            story.append(Paragraph(txt_validation, style_normal))
            story.append(Spacer(1, 20))

            data_sig = [
                [Paragraph(f"<b>Signature de l'intervenant :</b><br/><br/><br/><i>{prof_nom}</i>", style_normal), 
                 Paragraph(f"<b>Signature du Président ({president_nom}) :</b><br/><br/><br/><i>Certifié conforme pour l'association {asso_nom}</i>", style_normal)]
            ]
            t_sig = Table(data_sig, colWidths=[250, 250])
            t_sig.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                ('PADDING', (0,0), (-1,-1), 10)
            ]))
            story.append(t_sig)

            doc.build(story)
        except ImportError:
            try:
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "NOTE DE FRAIS KILOMETRIQUES OFFICIELLE", ln=True, align='C')
                pdf.set_font("Arial", '', 11)
                asso_nom = asso_data.get('nom', 'MON CLUB')
                president_nom = asso_data.get('president', 'Le Président')
                pdf.cell(0, 8, f"Club : {asso_nom} - Saison : {saison_act}", ln=True, align='C')
                pdf.ln(10)
                pdf.cell(0, 8, f"Beneficiaire : {prof_nom}", ln=True)
                pdf.cell(0, 8, f"Vehicule : {txt_marque} ({txt_immat}) - {dd_cv}", ln=True)
                pdf.cell(0, 8, f"Date : {txt_date_trajet}", ln=True)
                pdf.cell(0, 8, f"Trajet : {txt_depart} -> {txt_arrivee}", ln=True)
                pdf.cell(0, 8, f"Motif : {txt_motif_trajet}", ln=True)
                pdf.cell(0, 8, f"Distance : {kms} km  x  {self.BAREME_KM:.2f} EUR/km", ln=True)
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, f"TOTAL REMBOURSE : {montant_total:.2f} EUR", ln=True)
                pdf.ln(5)
                pdf.set_font("Arial", '', 10)
                pdf.cell(0, 6, f"Valide par le President : {president_nom}", ln=True)
                pdf.cell(0, 6, f"Date de validation : {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
                pdf.output(str(filepath))
            except Exception as ex_fpdf:
                raise RuntimeError(f"Impossible de générer le PDF : {ex_fpdf}")

    def ouvrir_formulaire_kilometrique_legal(self, e):
        if not self.selected_professeur:
            return

        prof_nom = self._get_prof_fullname().upper()
        asso_data = getattr(self.app, "association", {})
        president = asso_data.get("president", "Le Président")
        tresorier = asso_data.get("tresorier", "Le Trésorier")

        txt_immat = ft.TextField(label="Immatriculation Véhicule", col={"sm": 12, "md": 4}, hint_text="Ex: AB-123-CD")
        txt_marque = ft.TextField(label="Marque / Modèle", col={"sm": 12, "md": 4}, hint_text="Ex: Peugeot 208")
        dd_cv = ft.Dropdown(
            label="Puissance Fiscale",
            col={"sm": 12, "md": 4},
            options=[
                ft.dropdown.Option("3 CV et moins"),
                ft.dropdown.Option("4 CV"),
                ft.dropdown.Option("5 CV"),
                ft.dropdown.Option("6 CV"),
                ft.dropdown.Option("7 CV et plus"),
            ],
            value="5 CV"
        )

        txt_date_trajet = ft.TextField(label="Date", value=datetime.now().strftime("%d/%m/%Y"), col={"sm": 12, "md": 3})
        txt_depart = ft.TextField(label="Ville Départ", col={"sm": 12, "md": 4.5})
        txt_arrivee = ft.TextField(label="Ville Arrivée", col={"sm": 12, "md": 4.5})
        txt_motif_trajet = ft.TextField(label="Motif Officiel", col={"sm": 12, "md": 6}, hint_text="Ex: Match extérieur, Compétition, Stage")
        txt_kms = ft.TextField(label="Distance (Km A/R)", col={"sm": 6, "md": 3}, keyboard_type=ft.KeyboardType.NUMBER)

        dd_statut_km = ft.Dropdown(
            label="Statut du paiement",
            col={"sm": 6, "md": 3},
            options=[
                ft.dropdown.Option("Versé / Réglé"),
                ft.dropdown.Option("En attente (Dû)"),
            ],
            value="Versé / Réglé"
        )

        check_engagement = ft.Checkbox(
            label=f"Je soussigné(e) {prof_nom}, certifie sur l'honneur l'exactitude des kilomètres parcourus.",
            value=False
        )

        dd_valideur = ft.Dropdown(
            label="Validé par (Signataire officiel)",
            col={"sm": 12},
            options=[
                ft.dropdown.Option(f"Président(e) : {president}"),
                ft.dropdown.Option(f"Trésorier(ère) : {tresorier}"),
            ],
            value=f"Président(e) : {president}"
        )

        txt_bareme_info = ft.Text(f"Barème fiscal utilisé : {self.BAREME_KM:.2f} € / km (Barème URSSAF Asso Loi 1901)", size=11, color=ft.colors.GREY_400, italic=True)

        def valider_et_enregistrer_note(evt):
            kms = self._parse_float(txt_kms.value)
            if kms <= 0 or not check_engagement.value:
                self._show_snackbar("⚠️ Veuillez vérifier la distance et cocher l'engagement.", is_error=True)
                return

            montant_total = round(kms * self.BAREME_KM, 2)
            dest_dir = self._get_prof_dir("justificatifs_frais")
            filepath = dest_dir / f"Note_Kms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            saison_act = getattr(self.app, "saison_active", "")

            try:
                self._generer_pdf_kilometrique(
                    filepath=filepath,
                    prof_nom=prof_nom,
                    asso_data=asso_data,
                    saison_act=saison_act,
                    txt_marque=txt_marque.value or "Véhicule personnel",
                    txt_immat=txt_immat.value or "N/A",
                    dd_cv=dd_cv.value,
                    txt_date_trajet=txt_date_trajet.value,
                    txt_depart=txt_depart.value or "Ville d'origine",
                    txt_arrivee=txt_arrivee.value or "Destination",
                    txt_motif_trajet=txt_motif_trajet.value or "Déplacement club",
                    kms=kms,
                    montant_total=montant_total,
                    dd_valideur=dd_valideur.value
                )
                
                nouvel_item = {
                    "professeur": self._get_prof_fullname(),
                    "saison": saison_act,
                    "date": txt_date_trajet.value,
                    "motif": f"🚘 [Kms] {txt_motif_trajet.value} ({kms} km - Immat: {txt_immat.value})",
                    "type_frais": "Kms",
                    "statut": dd_statut_km.value,
                    "montant": montant_total,
                    "justifie": True,
                    "justificatif_path": str(filepath)
                }

                if hasattr(self.app, "defraiements"):
                    self.app.defraiements.append(nouvel_item)
                    self.app.save_data()

                self._fermer_dialogue(dlg_km)
                self._show_snackbar(f"📄 Note kilométrique PDF signée par {president} archivée avec succès !")
                self.charger_defraiements_professeur()
            except Exception as ex:
                self._show_snackbar(f"Erreur lors de la génération PDF : {ex}", is_error=True)

        dlg_km = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.icons.DIRECTIONS_CAR, color=ft.colors.GREEN_400),
                ft.Text(f"Déclaration Kilométrique : {prof_nom}")
            ]),
            content=ft.Container(
                width=600,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=12,
                    controls=[
                        ft.Text("1. Renseignements du Véhicule Utilisé", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                        ft.ResponsiveRow([txt_immat, txt_marque, dd_cv]),
                        ft.Divider(),
                        ft.Text("2. Détails du Déplacement", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                        ft.ResponsiveRow([txt_date_trajet, txt_depart, txt_arrivee]),
                        ft.ResponsiveRow([txt_motif_trajet, txt_kms, dd_statut_km]),
                        txt_bareme_info,
                        ft.Divider(),
                        ft.Text("3. Validation Légale & Bureau", weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                        check_engagement,
                        ft.ResponsiveRow([dd_valideur]),
                    ]
                )
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._fermer_dialogue(dlg_km)),
                ft.ElevatedButton("📄 Valider & Générer le PDF", bgcolor=ft.colors.GREEN_700, color=ft.colors.WHITE, on_click=valider_et_enregistrer_note)
            ]
        )

        self.app.page.overlay.append(dlg_km)
        dlg_km.open = True
        self.app.page.update()

    def _fermer_dialogue(self, dlg):
        dlg.open = False
        if self.page:
            self.page.update()

    def charger_defraiements_professeur(self):
        self.defraiements_table.rows.clear()
        if not self.selected_professeur:
            return

        nom_prof = self._get_prof_fullname()
        toutes_saisons = self.sw_toutes_saisons.value
        saison_act = getattr(self.app, "saison_active", "")
        all_defs = getattr(self.app, "defraiements", [])

        prof_defs = [
            d for d in all_defs
            if d.get("professeur") == nom_prof and (toutes_saisons or d.get("saison", saison_act) == saison_act)
        ]

        total_dus = 0.0
        total_verses = 0.0
        items_sans_justif = 0
        total_kms = 0.0

        for index, item in enumerate(prof_defs):
            montant = self._parse_float(item.get("montant", 0))
            type_frais = item.get("type_frais", "Kms")
            statut = item.get("statut", "Versé / Réglé")
            justifie = item.get("justifie", True)
            saison_item = item.get("saison", saison_act)

            if type_frais == "Avance / Règlement":
                total_verses += montant
            else:
                total_dus += montant
                if statut == "Versé / Réglé":
                    total_verses += montant

            if not justifie:
                items_sans_justif += 1
            if type_frais == "Kms":
                total_kms += (montant / self.BAREME_KM)

            path_justif = item.get("justificatif_path", "")
            if path_justif and Path(path_justif).exists():
                cell_fichier = ft.Row([
                    ft.IconButton(
                        icon=ft.icons.PICTURE_AS_PDF if path_justif.endswith('.pdf') else ft.icons.VISIBILITY,
                        icon_color=ft.colors.RED_400 if path_justif.endswith('.pdf') else ft.colors.BLUE_300,
                        tooltip="Ouvrir la pièce jointe / PDF",
                        on_click=lambda e, p=path_justif: self.ouvrir_document(Path(p))
                    ),
                    ft.Text(Path(path_justif).name, size=11, color=ft.colors.GREY_300)
                ], spacing=2)
            else:
                cell_fichier = ft.Text("Aucun fichier", size=11, italic=True, color=ft.colors.GREY_500)

            badge_statut = ft.Text(
                statut,
                size=11,
                weight=ft.FontWeight.BOLD,
                color=ft.colors.GREEN_400 if statut == "Versé / Réglé" else ft.colors.ORANGE_400
            )

            self.defraiements_table.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.get("date", ""))),
                        ft.DataCell(ft.Text(saison_item, size=11, color=ft.colors.GREY_400)),
                        ft.DataCell(ft.Text(item.get("motif", ""))),
                        ft.DataCell(ft.Text(type_frais)),
                        ft.DataCell(badge_statut),
                        ft.DataCell(ft.Text(f"{montant:.2f} €", weight=ft.FontWeight.BOLD)),
                        ft.DataCell(
                            ft.Icon(
                                ft.icons.CHECK_CIRCLE if justifie else ft.icons.CANCEL,
                                color=ft.colors.GREEN if justifie else ft.colors.RED
                            )
                        ),
                        ft.DataCell(cell_fichier),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.icons.ATTACH_FILE,
                                    icon_color=ft.colors.BLUE_400,
                                    tooltip="Joindre justificatif",
                                    on_click=lambda e, idx=index: self.demander_justificatif_frais(idx)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.EDIT,
                                    icon_color=ft.colors.ORANGE_300,
                                    tooltip="Modifier",
                                    on_click=lambda e, idx=index: self.modifier_defraiement(idx)
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE_OUTLINE,
                                    icon_color=ft.colors.RED_300,
                                    tooltip="Supprimer",
                                    on_click=lambda e, idx=index: self.supprimer_defraiement(idx)
                                )
                            ], spacing=0)
                        )
                    ]
                )
            )

        self._mettre_a_jour_equilibre_financier(total_dus, total_verses)
        self._mettre_a_jour_vumetre_urssaf(len(prof_defs), items_sans_justif, total_frais=total_dus, total_kms=total_kms)

        if self.page:
            self.page.update()

    def _mettre_a_jour_equilibre_financier(self, total_dus: float, total_verses: float):
        solde = total_verses - total_dus

        self.lbl_total_dus.value = f"{total_dus:.2f} €"
        self.lbl_total_verses.value = f"{total_verses:.2f} €"

        if abs(solde) < 0.01:
            self.lbl_equilibre.value = "0.00 €"
            self.lbl_equilibre.color = ft.colors.GREEN_400
            self.lbl_equilibre_status.value = "🟢 Compte équilibré"
            self.lbl_equilibre_status.color = ft.colors.GREEN_400
        elif solde < 0:
            reste = abs(solde)
            self.lbl_equilibre.value = f"{reste:.2f} €"
            self.lbl_equilibre.color = ft.colors.RED_400
            self.lbl_equilibre_status.value = f"🔴 Reste à verser"
            self.lbl_equilibre_status.color = ft.colors.RED_400
        else:
            trop = solde
            self.lbl_equilibre.value = f"{trop:.2f} €"
            self.lbl_equilibre.color = ft.colors.ORANGE_400
            self.lbl_equilibre_status.value = f"🟠 Trop versé / Avance"
            self.lbl_equilibre_status.color = ft.colors.ORANGE_400

    def _mettre_a_jour_vumetre_urssaf(self, nb_defs: int, sans_justif: int, total_frais: float, total_kms: float):
        if nb_defs == 0:
            self.vumetre_bar.value = 1.0
            self.vumetre_bar.color = ft.colors.GREEN_400
            self.vumetre_status.value = "100% SÉCURISÉ — Aucun défraiement enregistré"
            self.vumetre_status.color = ft.colors.GREEN_400
            self.vumetre_conseils.value = "💡 Conseil : Le statut bénévole est idéal pour démarrer."
        elif sans_justif > 0:
            self.vumetre_bar.value = 0.25
            self.vumetre_bar.color = ft.colors.RED_700
            self.vumetre_status.value = f"🔴 RISQUE ÉLEVÉ — {sans_justif} frais sans justificatif !"
            self.vumetre_status.color = ft.colors.RED_400
            self.vumetre_conseils.value = "⚠️ ALERTE : Tout remboursement sans justificatif est un risque de redressement."
        elif total_frais > 2000:
            self.vumetre_bar.value = 0.70
            self.vumetre_bar.color = ft.colors.ORANGE_400
            self.vumetre_status.value = f"🟡 À SURVEILLER — {total_frais:.2f} € engagés"
            self.vumetre_status.color = ft.colors.ORANGE_400
            self.vumetre_conseils.value = f"💡 Optimisation : Montant élevé ({total_kms:.0f} km environ). Conservez un registre précis."
        else:
            self.vumetre_bar.value = 1.0
            self.vumetre_bar.color = ft.colors.GREEN_400
            self.vumetre_status.value = "🟢 100% CONFORME ET SÉCURISÉ"
            self.vumetre_status.color = ft.colors.GREEN_400
            self.vumetre_conseils.value = "🏆 Parfait ! Tous les frais sont étayés par des justificatifs réguliers."

    def ajouter_defraiement(self, e):
        montant_val = self._parse_float(self.def_montant.value)
        if not self.def_motif.value or montant_val <= 0 or not self.selected_professeur:
            self._show_snackbar("Saisie invalide (motif ou montant requis).", is_error=True)
            return

        saison_act = getattr(self.app, "saison_active", "")
        nouvel_item = {
            "professeur": self._get_prof_fullname(),
            "saison": saison_act,
            "date": self.def_date.value,
            "motif": self.def_motif.value.strip(),
            "type_frais": self.def_type.value,
            "statut": self.def_statut.value,
            "montant": montant_val,
            "justifie": self.def_justifie.value,
            "justificatif_path": ""
        }

        if hasattr(self.app, "defraiements"):
            self.app.defraiements.append(nouvel_item)
            self.app.save_data()

        self.def_motif.value = ""
        self.def_montant.value = ""
        self.def_justifie.value = True

        self.charger_defraiements_professeur()

    def _trouver_index_global_defraiement(self, relative_index: int):
        nom_prof = self._get_prof_fullname()
        toutes_saisons = self.sw_toutes_saisons.value
        saison_act = getattr(self.app, "saison_active", "")
        match_count = 0

        all_defs = getattr(self.app, "defraiements", [])
        for global_idx, item in enumerate(all_defs):
            if item.get("professeur") == nom_prof:
                if toutes_saisons or item.get("saison", saison_act) == saison_act:
                    if match_count == relative_index:
                        return global_idx, item
                    match_count += 1
        return None, None

    def modifier_defraiement(self, index_relatif):
        global_idx, target_item = self._trouver_index_global_defraiement(index_relatif)
        if target_item is None:
            return

        edit_date = ft.TextField(label="Date", value=target_item.get("date", ""), col={"sm": 6, "md": 3})
        edit_motif = ft.TextField(label="Motif", value=target_item.get("motif", ""), col={"sm": 12})
        edit_type = ft.Dropdown(
            label="Type",
            col={"sm": 6, "md": 3},
            options=[
                ft.dropdown.Option("Kms"),
                ft.dropdown.Option("Hôtel"),
                ft.dropdown.Option("Repas"),
                ft.dropdown.Option("Avance / Règlement"),
                ft.dropdown.Option("Autre")
            ],
            value=target_item.get("type_frais", "Kms")
        )
        edit_statut = ft.Dropdown(
            label="Statut",
            col={"sm": 6, "md": 3},
            options=[
                ft.dropdown.Option("Versé / Réglé"),
                ft.dropdown.Option("En attente (Dû)"),
            ],
            value=target_item.get("statut", "Versé / Réglé")
        )
        edit_montant = ft.TextField(label="Montant (€)", value=str(target_item.get("montant", "")), col={"sm": 6, "md": 3}, keyboard_type=ft.KeyboardType.NUMBER)
        edit_justifie = ft.Checkbox(label="Justificatif ok ?", value=target_item.get("justifie", True))

        def enregistrer_modif(e):
            m_val = self._parse_float(edit_montant.value)
            if m_val <= 0:
                self._show_snackbar("Veuillez saisir un montant valide.", is_error=True)
                return

            target_item["date"] = edit_date.value
            target_item["motif"] = edit_motif.value.strip()
            target_item["type_frais"] = edit_type.value
            target_item["statut"] = edit_statut.value
            target_item["montant"] = m_val
            target_item["justifie"] = edit_justifie.value

            self.app.save_data()
            self._fermer_dialogue(dlg_edit)
            self.charger_defraiements_professeur()

        dlg_edit = ft.AlertDialog(
            title=ft.Text("✏️ Modifier la ligne de frais / règlement"),
            content=ft.Container(
                width=550,
                content=ft.Column([
                    ft.ResponsiveRow([edit_date, edit_type, edit_statut, edit_montant]),
                    edit_motif,
                    edit_justifie
                ], scroll=ft.ScrollMode.AUTO)
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._fermer_dialogue(dlg_edit)),
                ft.ElevatedButton("Sauvegarder", bgcolor=self.accent_color, color=ft.colors.WHITE, on_click=enregistrer_modif)
            ]
        )
        self.app.page.overlay.append(dlg_edit)
        dlg_edit.open = True
        self.app.page.update()

    def demander_justificatif_frais(self, index_relatif):
        self.frais_index_pour_justificatif = index_relatif
        self.justif_picker.pick_files(allow_multiple=False, allowed_extensions=["pdf", "png", "jpg", "jpeg", "txt"])

    def on_justificatif_frais_selected(self, e: ft.FilePickerResultEvent):
        if not e.files or self.frais_index_pour_justificatif is None or not self.selected_professeur:
            return

        src_path = Path(e.files[0].path)
        if not src_path.exists():
            return

        dest_dir = self._get_prof_dir("justificatifs_frais")
        filename = f"{src_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}{src_path.suffix}"
        dest_path = dest_dir / filename

        try:
            shutil.copy(src_path, dest_path)
            _, item = self._trouver_index_global_defraiement(self.frais_index_pour_justificatif)
            
            if item:
                item["justificatif_path"] = str(dest_path)
                item["justifie"] = True
                self.app.save_data()
                self._show_snackbar("Justificatif associé avec succès !")
                self.charger_defraiements_professeur()
        except Exception as ex:
            self._show_snackbar(f"Erreur d'enregistrement : {ex}", is_error=True)
        finally:
            self.frais_index_pour_justificatif = None

    def supprimer_defraiement(self, index_relatif):
        global_idx, _ = self._trouver_index_global_defraiement(index_relatif)
        if global_idx is not None and hasattr(self.app, "defraiements"):
            self.app.defraiements.pop(global_idx)
            self.app.save_data()
            self._show_snackbar("Défraiement supprimé.")
            self.charger_defraiements_professeur()

    def ouvrir_dialogue_creation(self, e):
        champ_nom = ft.TextField(label="Nom de famille")
        champ_prenom = ft.TextField(label="Prénom")
        champ_discipline = ft.TextField(label="Discipline / Sport", hint_text="Ex: Basket, Gym, Judo, Multisport")
        champ_niveau = ft.TextField(label="Niveau / Catégorie")

        def confirmer_creation(evt):
            if not champ_nom.value.strip() or not champ_prenom.value.strip():
                self._show_snackbar("Veuillez renseigner le nom et le prénom.", is_error=True)
                return

            saison_act = getattr(self.app, "saison_active", "")
            nouveau_prof = {
                "nom": champ_nom.value.strip().upper(),
                "prenom": champ_prenom.value.strip().capitalize(),
                "discipline": champ_discipline.value.strip() or "Multisport",
                "email": "",
                "telephone": "",
                "adresse": "",
                "niveau": champ_niveau.value.strip(),
                "diplome": "",
                "saisons": [saison_act]
            }
            if hasattr(self.app, "professeurs"):
                self.app.professeurs.append(nouveau_prof)
                self.app.save_data()

            self._fermer_dialogue(dlg)
            self.refresh_prof_list()
            self.select_professeur(nouveau_prof)
            self._show_snackbar("Nouvel intervenant créé !")

        dlg = ft.AlertDialog(
            title=ft.Text("Ajouter un Intervenant"),
            content=ft.Container(
                width=400,
                content=ft.Column([champ_nom, champ_prenom, champ_discipline, champ_niveau], spacing=10)
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda e: self._fermer_dialogue(dlg)),
                ft.ElevatedButton("Créer", on_click=confirmer_creation, bgcolor=self.accent_color, color=ft.colors.WHITE),
            ]
        )

        self.app.page.overlay.append(dlg)
        dlg.open = True
        self.app.page.update()