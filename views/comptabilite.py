# views/comptabilite.py
import flet as ft
from datetime import datetime
from pathlib import Path
import shutil
import os
import sys
import subprocess
from io import BytesIO

# Imports ReportLab pour l'exportation PDF pro d'AG
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- ARBORESCENCE FLUX MULTISPORT ---
CATEGORIES_FLUX = {
    "Dépense": {
        "Cotisations & Licences": [
            "Cotisations aux fédérations & ligues (FFK, FFF, UFOLEP...)",
            "Licences versées pour les membres",
            "Cotisations & affiliations diverses"
        ],
        "Déplacements, Missions & Réceptions": [
            "Frais de déplacement (Transports, péages)",
            "Frais de réception & conviviaux (AG, pots...)",
            "Hébergement & Restauration"
        ],
        "Achats & Matériel": [
            "Achat matériel sportif (Ballons, raquettes, tatamis...)",
            "Équipements & tenues du club (Maillots, survêtements)",
            "Petites fournitures de bureau & administration"
        ],
        "Banque": [
            "Frais bancaires & TPE",
            "Intérêts emprunts"
        ],
        "Assurances": [
            "Assurances & garanties"
        ],
        "Manifestations & Stages": [
            "Frais organisation compétitions & tournois",
            "Rémunération experts, juges & intervenants",
            "Achat buvette & restauration événements"
        ]
    },
    "Recette": {
        "Cotisations & Licences": [
            "Cotisations Adhérents",
            "Licences / Affiliations perçues",
            "Droits d'entrée & inscriptions"
        ],
        "Subventions & Aides": [
            "Subvention Mairie",
            "Subvention Départementale / Régionale",
            "Aides CAF / Pass'Sport / ANS",
            "Mécénat & Fondations"
        ],
        "Événements & Buvette": [
            "Entrées compétitions / Galas / Tournois",
            "Ventes buvette & gâteaux",
            "Inscriptions stages multisports"
        ],
        "Partenariats & Dons": [
            "Sponsoring entreprises",
            "Dons des particuliers (Mécénat)"
        ],
        "Produits Divers": [
            "Vente de matériel & tenues du club",
            "Remboursements d'assurances & divers"
        ]
    }
}

class ComptabiliteView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app  
        self.accent_color = self.app.association.get("accent_color", "#1E3A8A")
        
        self.new_justif_path = ""
        self.picking_mode = "NEW"  
        self.picking_row_index = -1
        self.dialog = None

        # --- INITIALISATION FILEPICKER ---
        self.file_picker = ft.FilePicker(on_result=self.on_file_picked)
        self.app.page.overlay.append(self.file_picker)

        # --- RECUPERATION DES SECTIONS / SPORTS ---
        self.sections_disponibles = self.get_sections_list()

        # --- COMPOSANTS DU FORMULAIRE DE SAISIE ---
        self.input_date = ft.TextField(
            label="Date",
            value=datetime.now().strftime("%d/%m/%Y"),
            hint_text="JJ/MM/AAAA",
            width=130
        )
        self.input_libelle = ft.TextField(
            label="Libellé / Description", 
            expand=True, 
            hint_text="Ex : Subvention Mairie, Achat ballons..."
        )
        self.input_montant = ft.TextField(
            label="Montant (€)", 
            width=120, 
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.dropdown_section = ft.Dropdown(
            label="Section / Sport",
            width=180,
            options=[ft.dropdown.Option(sec) for sec in self.sections_disponibles],
            value=self.sections_disponibles[0] if self.sections_disponibles else "Général"
        )

        self.dropdown_type = ft.Dropdown(
            label="Type",
            width=130,
            options=[
                ft.dropdown.Option("Recette"),
                ft.dropdown.Option("Dépense"),
            ],
            value="Dépense",
            on_change=self.on_type_changed
        )
        
        self.dropdown_cat = ft.Dropdown(
            label="Catégorie",
            width=220,
            on_change=self.on_cat_changed
        )
        
        self.dropdown_subcat = ft.Dropdown(
            label="Sous-Catégorie",
            expand=True
        )

        # --- MODE DE PAIEMENT & CHÈQUE ---
        self.dropdown_mode = ft.Dropdown(
            label="Mode de paiement",
            width=160,
            options=[
                ft.dropdown.Option("Virement"),
                ft.dropdown.Option("Prélèvement"),
                ft.dropdown.Option("Chèque"),
                ft.dropdown.Option("Espèces"),
                ft.dropdown.Option("Carte Bancaire"),
            ],
            value="Virement",
            on_change=self.on_mode_change
        )
        
        self.input_cheque = ft.TextField(
            label="N° du Chèque",
            width=150,
            visible=False,
            prefix_icon=ft.icons.NUMBERS
        )

        self.btn_pick_justif = ft.ElevatedButton(
            "Justificatif", 
            icon=ft.icons.ATTACH_FILE, 
            on_click=lambda _: self.ouvrir_selecteur_justificatif("NEW")
        )
        self.txt_justif_status = ft.Text("Aucun fichier", color=ft.colors.GREY_500, size=12)

        self.remplir_dropdowns()

        # --- COMPTEURS DE SYNTHÈSE ---
        self.txt_recettes = ft.Text("0 €", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN)
        self.txt_depenses = ft.Text("0 €", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.RED)
        self.txt_solde = ft.Text("0 €", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE)

        # --- JOURNAL DES OPÉRATIONS ---
        self.table_compta = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Section")),
                ft.DataColumn(ft.Text("Libellé & Mode")),
                ft.DataColumn(ft.Text("Catégorie")),
                ft.DataColumn(ft.Text("Sous-Catégorie")),
                ft.DataColumn(ft.Text("Flux")),
                ft.DataColumn(ft.Text("Montant")),
                ft.DataColumn(ft.Text("Justif")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[]
        )

        self.operations_table_container = ft.Container(
            bgcolor="#1F2937",
            padding=15,
            border_radius=10,
            content=ft.Row(
                scroll=ft.ScrollMode.AUTO,
                controls=[self.table_compta]
            )
        )

        self.calculer_et_remplir_compta()

        self.content = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=15,
            controls=[
                ft.Row([
                    ft.Icon(ft.icons.ACCOUNT_BALANCE_WALLET_ROUNDED, size=30, color=self.accent_color),
                    ft.Text("Registre Comptable Multisport", size=24, weight=ft.FontWeight.BOLD),
                ]),
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
                            content=ft.Column([
                                ft.Text("Bilan Financier Global", size=15, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                                self.create_finance_card("Total Recettes", self.txt_recettes, ft.icons.ARROW_UPWARD, ft.colors.GREEN_900),
                                self.create_finance_card("Total Dépenses", self.txt_depenses, ft.icons.ARROW_DOWNWARD, ft.colors.RED_900),
                                self.create_finance_card("Solde Général", self.txt_solde, ft.icons.ACCOUNT_BALANCE, ft.colors.BLUE_GREY_900),
                            ], spacing=8, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                        ),
                        
                        ft.Container(
                            col={"sm": 12, "md": 8},
                            bgcolor="#1F2937",
                            padding=15,
                            border_radius=10,
                            content=ft.Column([
                                ft.Text("Nouvelle Écriture Manuelle", size=15, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_200),
                                ft.Divider(color=ft.colors.GREY_800),
                                ft.ResponsiveRow([
                                    ft.Container(self.input_date, col={"sm": 12, "md": 3}),
                                    ft.Container(self.input_libelle, col={"sm": 12, "md": 6}),
                                    ft.Container(self.input_montant, col={"sm": 12, "md": 3}),
                                ]),
                                ft.ResponsiveRow([
                                    ft.Container(self.dropdown_section, col={"sm": 12, "md": 3}),
                                    ft.Container(self.dropdown_type, col={"sm": 12, "md": 2}),
                                    ft.Container(self.dropdown_cat, col={"sm": 12, "md": 3}),
                                    ft.Container(self.dropdown_subcat, col={"sm": 12, "md": 4}),
                                ]),
                                ft.ResponsiveRow([
                                    ft.Container(self.dropdown_mode, col={"sm": 12, "md": 5}),
                                    ft.Container(self.input_cheque, col={"sm": 12, "md": 7}),
                                ]),
                                ft.Row([
                                    ft.Row([self.btn_pick_justif, self.txt_justif_status], spacing=10),
                                    ft.ElevatedButton(
                                        "Valider l'écriture",
                                        icon=ft.icons.ADD_ROUNDED,
                                        bgcolor=self.accent_color,
                                        color=ft.colors.WHITE,
                                        on_click=self.ajouter_operation,
                                        height=45
                                    )
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                            ], spacing=10)
                        )
                    ]
                ),
                
                ft.Divider(height=5),

                ft.Row([
                    ft.Row([
                        ft.Icon(ft.icons.FORMAT_LIST_BULLETED_ROUNDED, size=20, color=self.accent_color),
                        ft.Text("Journal des opérations de la saison", size=16, weight=ft.FontWeight.BOLD),
                    ], spacing=10),
                    ft.Container(
                        content=ft.Row([
                            ft.ElevatedButton(
                                "Exporter le Journal",
                                icon=ft.icons.PICTURE_AS_PDF,
                                on_click=self.exporter_journal_pdf,
                                bgcolor=ft.colors.BLUE_GREY_800,
                                color=ft.colors.WHITE
                            ),
                            ft.ElevatedButton(
                                "État Financier (Bilan AG)",
                                icon=ft.icons.ANALYTICS,
                                on_click=self.exporter_bilan_pdf,
                                bgcolor=self.accent_color,
                                color=ft.colors.WHITE
                            ),
                        ], spacing=10, scroll=ft.ScrollMode.AUTO),
                        alignment=ft.alignment.center_right
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                
                self.operations_table_container
            ]
        )

    def get_sections_list(self):
        sections = ["Général"]
        if hasattr(self.app, "sports") and isinstance(self.app.sports, list) and self.app.sports:
            sections.extend([s for s in self.app.sports if s not in sections])
        elif isinstance(self.app.association.get("sports"), list):
            sections.extend([s for s in self.app.association.get("sports") if s not in sections])
        return sections

    def create_finance_card(self, title, text_control, icon, bg_color):
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=30, color=ft.colors.WHITE),
                ft.Column([
                    ft.Text(title, size=11, color=ft.colors.GREY_400),
                    text_control
                ], spacing=1)
            ]),
            bgcolor=bg_color,
            padding=10,
            border_radius=8,
            width=250
        )

    def on_mode_change(self, e):
        self.input_cheque.visible = (self.dropdown_mode.value == "Chèque")
        self.update()

    def remplir_dropdowns(self):
        t_val = self.dropdown_type.value
        categories = list(CATEGORIES_FLUX[t_val].keys())
        self.dropdown_cat.options = [ft.dropdown.Option(cat) for cat in categories]
        self.dropdown_cat.value = categories[0] if categories else None
        self.remplir_sous_categories()

    def remplir_sous_categories(self):
        t_val = self.dropdown_type.value
        cat_val = self.dropdown_cat.value
        if t_val and cat_val and cat_val in CATEGORIES_FLUX[t_val]:
            subcats = CATEGORIES_FLUX[t_val][cat_val]
            self.dropdown_subcat.options = [ft.dropdown.Option(sc) for sc in subcats]
            self.dropdown_subcat.value = subcats[0] if subcats else None
        else:
            self.dropdown_subcat.options = []
            self.dropdown_subcat.value = None

    def on_type_changed(self, e):
        self.remplir_dropdowns()
        self.update()

    def on_cat_changed(self, e):
        self.remplir_sous_categories()
        self.update()

    def calculer_et_remplir_compta(self):
        self.table_compta.rows.clear()
        total_recettes = 0.0
        total_depenses = 0.0
        toutes_operations = []

        for idx, cotis in enumerate(self.app.cotisations):
            if cotis.get("statut") == "Encaissé / Validé":
                montant = float(cotis.get("montant", 0))
                section_item = cotis.get("sport") or cotis.get("section") or "Général"
                toutes_operations.append({
                    "index_cotisation": idx,
                    "date": cotis.get("date"),
                    "section": section_item,
                    "libelle": f"Adhésion : {cotis.get('membre')}",
                    "categorie": "Cotisations & Licences",
                    "sous_categorie": "Cotisations Adhérents",
                    "type": "Recette",
                    "montant": montant,
                    "justificatif": "",
                    "automatique": True
                })
                total_recettes += montant

        for idx, op in enumerate(self.app.finances):
            montant = float(op.get("montant", 0))
            
            libelle = op.get("libelle", "")
            mode = op.get("mode_paiement", "")
            if mode:
                if mode == "Chèque" and op.get("num_cheque"):
                    libelle += f" [{mode} N°{op.get('num_cheque')}]"
                else:
                    libelle += f" [{mode}]"

            toutes_operations.append({
                "index_db": idx,
                "date": op.get("date"),
                "section": op.get("section", "Général"),
                "libelle": libelle,
                "categorie": op.get("categorie"),
                "sous_categorie": op.get("sous_categorie", "N/A"),
                "type": op.get("type"),
                "montant": montant,
                "justificatif": op.get("justificatif", ""),
                "automatique": False
            })
            if op.get("type") == "Recette":
                total_recettes += montant
            else:
                total_depenses += montant

        toutes_operations.reverse()

        for item in toutes_operations:
            is_recette = item.get("type") == "Recette"
            color_flux = ft.colors.GREEN_400 if is_recette else ft.colors.RED_400
            is_auto = item.get("automatique")
            style_texte = ft.TextStyle(italic=True, color=ft.colors.GREY_400) if is_auto else None
            
            db_idx = item.get("index_db")
            cotis_idx = item.get("index_cotisation")
            justif_path = item.get("justificatif", "")

            if is_auto:
                cell_justif = ft.Row([
                    ft.Icon(ft.icons.LOCK_ROUNDED, size=16, color=ft.colors.GREY_600),
                    ft.Text("Auto", size=11, color=ft.colors.GREY_600, italic=True)
                ])
                cell_actions = ft.Row([
                    ft.IconButton(ft.icons.EDIT_ROUNDED, icon_color=ft.colors.AMBER_400, icon_size=18, on_click=lambda e, idx=cotis_idx: self.open_edit_cotisation_dialog(idx)),
                    ft.IconButton(ft.icons.DELETE_ROUNDED, icon_color=ft.colors.RED_400, icon_size=18, on_click=lambda e, idx=cotis_idx: self.open_delete_cotisation_dialog(idx))
                ], spacing=0)
            else:
                if justif_path:
                    cell_justif = ft.Row([
                        ft.IconButton(ft.icons.INSERT_DRIVE_FILE_ROUNDED, icon_color=ft.colors.BLUE_400, icon_size=20, on_click=lambda e, path=justif_path: self.ouvrir_justificatif(path)),
                        ft.IconButton(ft.icons.DELETE_FOREVER_ROUNDED, icon_color=ft.colors.RED_400, icon_size=18, on_click=lambda e, idx=db_idx: self.retirer_justificatif_seul(idx))
                    ], spacing=0)
                else:
                    cell_justif = ft.IconButton(ft.icons.ADD_LINK_ROUNDED, icon_color=ft.colors.GREY_500, icon_size=20, on_click=lambda e, idx=db_idx: self.ouvrir_selecteur_justificatif("EDIT", idx))

                cell_actions = ft.Row([
                    ft.IconButton(ft.icons.EDIT_ROUNDED, icon_color=ft.colors.AMBER_400, icon_size=20, on_click=lambda e, idx=db_idx: self.open_edit_dialog(idx)),
                    ft.IconButton(ft.icons.DELETE_ROUNDED, icon_color=ft.colors.RED_400, icon_size=20, on_click=lambda e, idx=db_idx: self.open_delete_dialog(idx))
                ], spacing=0)

            self.table_compta.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(item.get("date"), style=style_texte)),
                        ft.DataCell(ft.Container(
                            content=ft.Text(item.get("section", "Général"), size=11, weight=ft.FontWeight.W_500),
                            bgcolor=ft.colors.BLUE_GREY_900,
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border_radius=5
                        )),
                        ft.DataCell(ft.Text(item.get("libelle"), style=style_texte)),
                        ft.DataCell(ft.Text(item.get("categorie"), style=style_texte)),
                        ft.DataCell(ft.Text(item.get("sous_categorie"), style=style_texte)),
                        ft.DataCell(ft.Text(item.get("type"), color=color_flux, weight=ft.FontWeight.BOLD)),
                        ft.DataCell(ft.Text(f"{item.get('montant'):.2f} €", style=style_texte)),
                        ft.DataCell(cell_justif),
                        ft.DataCell(cell_actions),
                    ]
                )
            )

        solde = total_recettes - total_depenses
        self.txt_recettes.value = f"{total_recettes:.2f} €"
        self.txt_depenses.value = f"{total_depenses:.2f} €"
        self.txt_solde.value = f"{solde:.2f} €"
        self.txt_solde.color = ft.colors.GREEN if solde >= 0 else ft.colors.RED

    def ajouter_operation(self, e):
        if not self.input_libelle.value or not self.input_montant.value:
            self.show_snack("Veuillez remplir le libellé et le montant.", is_error=True)
            return

        try:
            m_val = float(self.input_montant.value)
        except ValueError:
            self.show_snack("Le montant saisi est incorrect.", is_error=True)
            return

        date_operation = self.input_date.value.strip() if self.input_date.value else datetime.now().strftime("%d/%m/%Y")

        nouvelle_ligne = {
            "date": date_operation,
            "section": self.dropdown_section.value or "Général",
            "libelle": self.input_libelle.value,
            "categorie": self.dropdown_cat.value,
            "sous_categorie": self.dropdown_subcat.value,
            "type": self.dropdown_type.value,
            "montant": m_val,
            "justificatif": self.new_justif_path,
            "mode_paiement": self.dropdown_mode.value,
            "num_cheque": self.input_cheque.value if self.dropdown_mode.value == "Chèque" else ""
        }

        self.app.finances.append(nouvelle_ligne)
        self.app.save_data()

        # Reset des champs
        self.input_date.value = datetime.now().strftime("%d/%m/%Y")
        self.input_libelle.value = ""
        self.input_montant.value = ""
        self.input_cheque.value = ""
        self.input_cheque.visible = False
        self.dropdown_mode.value = "Virement"
        self.new_justif_path = ""
        self.txt_justif_status.value = "Aucun fichier"
        self.txt_justif_status.color = ft.colors.GREY_500

        self.calculer_et_remplir_compta()
        self.show_snack("✅ Écriture comptable ajoutée avec succès !")
        self.update()

    def ouvrir_selecteur_justificatif(self, mode, row_index=-1):
        self.picking_mode = mode
        self.picking_row_index = row_index
        self.file_picker.pick_files(allow_multiple=False, allowed_extensions=["pdf", "png", "jpg", "jpeg"])

    def on_file_picked(self, e: ft.FilePickerResultEvent):
        if not e.files:
            return
        src_file = e.files[0]
        src_path = Path(src_file.path)
        dest_dir = self.app.data_dir / "justificatifs"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"justif_{timestamp}_{src_file.name}"
        dest_path = dest_dir / safe_name

        try:
            shutil.copy(str(src_path), str(dest_path))
            saved_path = str(dest_path)
        except Exception:
            saved_path = str(src_path)

        if self.picking_mode == "NEW":
            self.new_justif_path = saved_path
            self.txt_justif_status.value = f"📎 {src_file.name[:12]}..."
            self.txt_justif_status.color = ft.colors.GREEN_400
        elif self.picking_mode == "EDIT":
            idx = self.picking_row_index
            if 0 <= idx < len(self.app.finances):
                self.app.finances[idx]["justificatif"] = saved_path
                self.app.save_data()
                self.show_snack("✅ Justificatif associé avec succès !")
                self.calculer_et_remplir_compta()
        elif self.picking_mode == "MODAL_EDIT":
            self.modal_justif_path = saved_path
            self.modal_txt_justif.value = f"📎 {src_file.name[:15]}..."
            self.modal_txt_justif.color = ft.colors.GREEN_400
            if hasattr(self, "modal_justif_container"):
                self.modal_justif_container.update()
        self.update()

    def ouvrir_justificatif(self, path):
        if not path:
            return
        p = Path(path)
        if not p.exists():
            self.show_snack("Fichier introuvable sur le disque.", is_error=True)
            return
        try:
            if sys.platform in ["android", "ios"]:
                public_download = Path("/storage/emulated/0/Download")
                if public_download.exists():
                    dest_path = public_download / p.name
                    shutil.copy(p, dest_path)
                    self.app.page.launch_url(f"file://{dest_path}")
                else:
                    self.app.page.launch_url(str(p))
            elif sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)], check=True)
            else:
                try:
                    subprocess.run(["xdg-open", str(p)], check=True)
                except Exception:
                    self.show_snack(f"✅ PDF enregistré avec succès dans : {p.parent}", is_error=False)
                    return
        except Exception:
            self.show_snack(f"✅ PDF enregistré dans {p.parent}", is_error=False)

    def retirer_justificatif_seul(self, idx):
        if 0 <= idx < len(self.app.finances):
            self.app.finances[idx]["justificatif"] = ""
            self.app.save_data()
            self.calculer_et_remplir_compta()
            self.show_snack("🗑️ Le justificatif a été retiré.")
            self.update()

    def open_delete_dialog(self, index):
        def confirm_delete(e):
            self.app.finances.pop(index)
            self.app.save_data()
            self.calculer_et_remplir_compta()
            self.close_dialog()
            self.show_snack("🗑️ Écriture supprimée avec succès !")

        self.dialog = ft.AlertDialog(
            title=ft.Text("Supprimer l'écriture ?"),
            content=ft.Text("Cette action supprimera définitivement l'opération comptable."),
            actions=[
                ft.TextButton("Annuler", on_click=lambda _: self.close_dialog()),
                ft.ElevatedButton("Supprimer", bgcolor=ft.colors.RED, color=ft.colors.WHITE, on_click=confirm_delete)
            ]
        )
        self.app.page.dialog = self.dialog
        self.dialog.open = True
        self.app.page.update()

    def open_delete_cotisation_dialog(self, index):
        def confirm_delete(e):
            self.app.cotisations.pop(index)
            self.app.save_data()
            self.calculer_et_remplir_compta()
            self.close_dialog()
            self.show_snack("🗑️ Cotisation supprimée avec succès !")

        self.dialog = ft.AlertDialog(
            title=ft.Text("Supprimer la cotisation ?"),
            content=ft.Text("Cette action supprimera définitivement le règlement de cotisation associé."),
            actions=[
                ft.TextButton("Annuler", on_click=lambda _: self.close_dialog()),
                ft.ElevatedButton("Supprimer", bgcolor=ft.colors.RED, color=ft.colors.WHITE, on_click=confirm_delete)
            ]
        )
        self.app.page.dialog = self.dialog
        self.dialog.open = True
        self.app.page.update()

    def open_edit_cotisation_dialog(self, index):
        cotis = self.app.cotisations[index]
        self.edit_cotis_montant = ft.TextField(label="Montant (€)", value=str(cotis.get("montant", 0.0)), keyboard_type=ft.KeyboardType.NUMBER)
        self.edit_cotis_statut = ft.Dropdown(
            label="Statut",
            options=[
                ft.dropdown.Option("Encaissé / Validé"),
                ft.dropdown.Option("En attente d'encaissement"),
                ft.dropdown.Option("Incomplet / Partiel"),
                ft.dropdown.Option("Rejeté"),
            ],
            value=cotis.get("statut", "Encaissé / Validé")
        )

        def save_cotis(e):
            try:
                m_val = float(self.edit_cotis_montant.value)
            except ValueError:
                self.show_snack("Le montant doit être numérique.", is_error=True)
                return
            cotis["montant"] = m_val
            cotis["statut"] = self.edit_cotis_statut.value
            self.app.save_data()
            self.calculer_et_remplir_compta()
            self.close_dialog()
            self.show_snack("✏️ Cotisation modifiée avec succès !")

        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Modifier la cotisation de {cotis.get('membre', '')}"),
            content=ft.Container(
                width=350, height=200,
                content=ft.Column([self.edit_cotis_montant, self.edit_cotis_statut], spacing=10)
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda _: self.close_dialog()),
                ft.ElevatedButton("Enregistrer", bgcolor=self.accent_color, color=ft.colors.WHITE, on_click=save_cotis)
            ]
        )
        self.app.page.dialog = self.dialog
        self.dialog.open = True
        self.app.page.update()

    def open_edit_dialog(self, index):
        op = self.app.finances[index]
        self.edit_libelle = ft.TextField(label="Libellé", value=op.get("libelle", ""))
        self.edit_montant = ft.TextField(label="Montant (€)", value=str(op.get("montant", 0.0)), keyboard_type=ft.KeyboardType.NUMBER)
        self.edit_date = ft.TextField(label="Date (JJ/MM/AAAA)", value=op.get("date", datetime.now().strftime("%d/%m/%Y")))
        
        self.edit_section = ft.Dropdown(
            label="Section / Sport",
            options=[ft.dropdown.Option(s) for s in self.sections_disponibles],
            value=op.get("section", "Général")
        )

        t_val = op.get("type", "Dépense")
        self.edit_type = ft.Dropdown(
            label="Type",
            options=[ft.dropdown.Option("Recette"), ft.dropdown.Option("Dépense")],
            value=t_val,
            on_change=self.on_modal_type_change
        )
        
        cat_val = op.get("categorie", "")
        cats_options = list(CATEGORIES_FLUX[t_val].keys())
        if cat_val not in cats_options:
            cat_val = cats_options[0] if cats_options else ""
        self.edit_cat = ft.Dropdown(
            label="Catégorie",
            options=[ft.dropdown.Option(c) for c in cats_options],
            value=cat_val,
            on_change=self.on_modal_cat_change
        )
        
        subcat_val = op.get("sous_categorie", "")
        subcats_options = CATEGORIES_FLUX[t_val].get(cat_val, [])
        if subcat_val not in subcats_options:
            subcat_val = subcats_options[0] if subcats_options else ""
        self.edit_subcat = ft.Dropdown(
            label="Sous-catégorie",
            options=[ft.dropdown.Option(s) for s in subcats_options],
            value=subcat_val
        )

        mode_val = op.get("mode_paiement", "Virement")
        self.edit_mode = ft.Dropdown(
            label="Mode de paiement",
            options=[
                ft.dropdown.Option("Virement"),
                ft.dropdown.Option("Prélèvement"),
                ft.dropdown.Option("Chèque"),
                ft.dropdown.Option("Espèces"),
                ft.dropdown.Option("Carte Bancaire"),
            ],
            value=mode_val,
            on_change=self.on_modal_mode_change
        )
        self.edit_cheque = ft.TextField(
            label="N° du Chèque",
            value=op.get("num_cheque", ""),
            visible=(mode_val == "Chèque")
        )

        self.modal_justif_path = op.get("justificatif", "")
        j_name = Path(self.modal_justif_path).name if self.modal_justif_path else "Aucun fichier"
        self.modal_txt_justif = ft.Text(f"📎 {j_name[:15]}..." if self.modal_justif_path else "Aucun fichier", color=ft.colors.GREEN_400 if self.modal_justif_path else ft.colors.GREY_500)
        self.modal_justif_container = ft.Row([
            self.modal_txt_justif,
            ft.IconButton(ft.icons.UPLOAD_FILE_ROUNDED, on_click=lambda _: self.ouvrir_selecteur_justificatif("MODAL_EDIT"))
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        def save_modifications(e):
            try:
                m_val = float(self.edit_montant.value)
            except ValueError:
                self.show_snack("Le montant doit être numérique.", is_error=True)
                return

            op["libelle"] = self.edit_libelle.value
            op["montant"] = m_val
            op["date"] = self.edit_date.value
            op["section"] = self.edit_section.value
            op["type"] = self.edit_type.value
            op["categorie"] = self.edit_cat.value
            op["sous_categorie"] = self.edit_subcat.value
            op["justificatif"] = self.modal_justif_path
            op["mode_paiement"] = self.edit_mode.value
            op["num_cheque"] = self.edit_cheque.value if self.edit_mode.value == "Chèque" else ""

            self.app.save_data()
            self.calculer_et_remplir_compta()
            self.close_dialog()
            self.show_snack("✏️ Opération modifiée avec succès !")

        self.dialog = ft.AlertDialog(
            title=ft.Text("Modifier la ligne comptable"),
            content=ft.Container(
                width=450, height=480,
                content=ft.Column([
                    self.edit_libelle,
                    ft.Row([self.edit_section, self.edit_type], spacing=10),
                    self.edit_montant,
                    self.edit_cat,
                    self.edit_subcat,
                    ft.Row([self.edit_mode, self.edit_cheque], spacing=10),
                    self.edit_date,
                    self.modal_justif_container
                ], spacing=10, scroll=ft.ScrollMode.AUTO)
            ),
            actions=[
                ft.TextButton("Annuler", on_click=lambda _: self.close_dialog()),
                ft.ElevatedButton("Enregistrer", bgcolor=self.accent_color, color=ft.colors.WHITE, on_click=save_modifications)
            ]
        )
        self.app.page.dialog = self.dialog
        self.dialog.open = True
        self.app.page.update()

    def on_modal_type_change(self, e):
        t_val = self.edit_type.value
        cats_options = list(CATEGORIES_FLUX[t_val].keys())
        self.edit_cat.options = [ft.dropdown.Option(c) for c in cats_options]
        self.edit_cat.value = cats_options[0] if cats_options else None
        self.on_modal_cat_change(None)

    def on_modal_cat_change(self, e):
        t_val = self.edit_type.value
        cat_val = self.edit_cat.value
        subcats_options = CATEGORIES_FLUX[t_val].get(cat_val, [])
        self.edit_subcat.options = [ft.dropdown.Option(s) for s in subcats_options]
        self.edit_subcat.value = subcats_options[0] if subcats_options else None
        self.dialog.update()

    def on_modal_mode_change(self, e):
        self.edit_cheque.visible = (self.edit_mode.value == "Chèque")
        self.dialog.update()

    def close_dialog(self):
        if self.dialog:
            self.dialog.open = False
            self.app.page.update()

    def exporter_journal_pdf(self, e):
        toutes_ops = []
        for cotis in self.app.cotisations:
            if cotis.get("statut") == "Encaissé / Validé":
                toutes_ops.append({
                    "date": cotis.get("date"),
                    "section": cotis.get("sport") or cotis.get("section") or "Général",
                    "libelle": f"Adhésion : {cotis.get('membre')}",
                    "categorie": "Cotisations & Licences",
                    "sous_categorie": "Cotisations Adhérents",
                    "type": "Recette",
                    "montant": float(cotis.get("montant", 0))
                })
        
        for op in self.app.finances:
            lib = op.get("libelle")
            mode = op.get("mode_paiement", "")
            if mode:
                if mode == "Chèque" and op.get("num_cheque"):
                    lib += f" [{mode} N°{op.get('num_cheque')}]"
                else:
                    lib += f" [{mode}]"
            toutes_ops.append({
                "date": op.get("date"),
                "section": op.get("section", "Général"),
                "libelle": lib,
                "categorie": op.get("categorie"),
                "sous_categorie": op.get("sous_categorie", "N/A"),
                "type": op.get("type"),
                "montant": float(op.get("montant", 0))
            })

        toutes_ops.reverse()

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, spaceAfter=12, textColor=colors.HexColor("#1E3A8A"))
        story.append(Paragraph(f"Grand Livre & Journal Financier - {self.app.association.get('nom', 'Club Multisport')}", title_style))
        story.append(Paragraph(f"Saison en cours - Document d'AG généré le {datetime.now().strftime('%d/%m/%Y')}", styles['Normal']))
        story.append(Spacer(1, 15))

        data = [["Date", "Section", "Désignation", "Poste Comptable", "Sous-Poste", "Flux", "Montant"]]
        for op in toutes_ops:
            data.append([
                op['date'],
                op['section'][:12],
                op['libelle'][:22],
                op['categorie'],
                op['sous_categorie'],
                op['type'],
                f"{op['montant']:.2f} €"
            ])

        table_journal = Table(data, colWidths=[55, 65, 115, 105, 105, 50, 60])
        table_journal.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (6,0), (6,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ]))
        
        for i in range(1, len(data)):
            flux = data[i][5]
            bg = colors.HexColor("#F8FAFC") if i % 2 == 0 else colors.white
            table_journal.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), bg),
                ('TEXTCOLOR', (5, i), (6, i), colors.HexColor("#16A34A") if flux == "Recette" else colors.HexColor("#DC2626"))
            ]))

        story.append(table_journal)
        doc.build(story)
        pdf_bytes = buffer.getvalue()

        exports_dir = self.app.data_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        file_path = exports_dir / f"journal_complet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        try:
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            self.ouvrir_justificatif(str(file_path))
        except Exception as ex:
            self.show_snack(f"Erreur d'écriture du PDF : {ex}", is_error=True)

    def exporter_bilan_pdf(self, e):
        recettes_tree = {}
        depenses_tree = {}
        total_rec = 0.0
        total_dep = 0.0

        for cotis in self.app.cotisations:
            if cotis.get("statut") == "Encaissé / Validé":
                mt = float(cotis.get("montant", 0))
                cat = "Cotisations & Licences"
                subcat = "Cotisations Adhérents"
                if cat not in recettes_tree: recettes_tree[cat] = {}
                recettes_tree[cat][subcat] = recettes_tree[cat].get(subcat, 0.0) + mt
                total_rec += mt

        for op in self.app.finances:
            mt = float(op.get("montant", 0))
            cat = op.get("categorie", "Divers")
            subcat = op.get("sous_categorie", "N/A")
            if op.get("type") == "Recette":
                if cat not in recettes_tree: recettes_tree[cat] = {}
                recettes_tree[cat][subcat] = recettes_tree[cat].get(subcat, 0.0) + mt
                total_rec += mt
            else:
                if cat not in depenses_tree: depenses_tree[cat] = {}
                depenses_tree[cat][subcat] = depenses_tree[cat].get(subcat, 0.0) + mt
                total_dep += mt

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, spaceAfter=5, textColor=colors.HexColor("#1E3A8A"))
        subtitle_style = ParagraphStyle('SubStyle', parent=styles['Heading2'], fontSize=12, spaceAfter=20, textColor=colors.HexColor("#475569"))
        h3_style = ParagraphStyle('H3Style', parent=styles['Heading3'], fontSize=11, spaceBefore=12, spaceAfter=8, textColor=colors.HexColor("#0F172A"))

        story.append(Paragraph("Rapport Financier de l'Exercice", title_style))
        story.append(Paragraph(f"Bilan officiel présenté à l'AG - {self.app.association.get('nom', 'Club Multisport')}", subtitle_style))

        solde = total_rec - total_dep
        solde_color = "#16A34A" if solde >= 0 else "#DC2626"
        
        synth_data = [
            ["Poste Comptable", "Montant Global"],
            ["Total des Recettes (Crédits)", f"{total_rec:.2f} €"],
            ["Total des Dépenses (Débits)", f"{total_dep:.2f} €"],
            ["Résultat de l'Exercice (Solde net)", f"{solde:.2f} €"]
        ]
        t_synth = Table(synth_data, colWidths=[340, 160])
        t_synth.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#475569")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('BACKGROUND', (0,1), (-1,-2), colors.HexColor("#F8FAFC")),
            ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#E2E8F0")),
            ('FONTNAME', (0,3), (-1,3), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1,3), (1,3), colors.HexColor(solde_color)),
        ]))
        story.append(Paragraph("1. Synthèse de l'Exercice", h3_style))
        story.append(t_synth)

        story.append(Paragraph("2. Ventilation Détaillée des Recettes", h3_style))
        rec_data = [["Catégorie", "Sous-Catégorie", "Total perçu"]]
        for cat, subcats in recettes_tree.items():
            for subcat, mt in subcats.items():
                rec_data.append([cat, subcat, f"{mt:.2f} €"])
        rec_data.append(["TOTAL RECETTES", "", f"{total_rec:.2f} €"])

        t_rec = Table(rec_data, colWidths=[200, 200, 100])
        t_rec.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#16A34A")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#DCFCE7")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ]))
        story.append(t_rec)

        story.append(Paragraph("3. Ventilation Détaillée des Dépenses", h3_style))
        dep_data = [["Catégorie", "Sous-Catégorie", "Total engagé"]]
        for cat, subcats in depenses_tree.items():
            for subcat, mt in subcats.items():
                dep_data.append([cat, subcat, f"{mt:.2f} €"])
        dep_data.append(["TOTAL DÉPENSES", "", f"{total_dep:.2f} €"])

        t_dep = Table(dep_data, colWidths=[200, 200, 100])
        t_dep.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DC2626")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('ALIGN', (2,0), (2,-1), 'RIGHT'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#FEE2E2")),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ]))
        story.append(t_dep)

        doc.build(story)
        pdf_bytes = buffer.getvalue()

        exports_dir = self.app.data_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        file_path = exports_dir / f"bilan_ag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        try:
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            self.ouvrir_justificatif(str(file_path))
        except Exception as ex:
            self.show_snack(f"Erreur d'écriture du PDF : {ex}", is_error=True)

    def show_snack(self, message, is_error=False):
        self.app.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.colors.RED_700 if is_error else ft.colors.GREEN_700
        )
        self.app.page.snack_bar.open = True
        self.app.page.update()
