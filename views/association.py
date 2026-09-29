import os
from pathlib import Path
import flet as ft


def get_icon(name: str):
    """Détecte et renvoie le format d'icône valide pour la version Flet active."""
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()


class AssociationView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True, bgcolor="#0F172A", padding=15)
        self.app = app
        asso_data = getattr(self.app, "association", {})
        self.accent_color = asso_data.get("accent_color", "#1E3A8A")

        # --- FILE PICKERS DÉDIÉS ---
        self.fp_logo = ft.FilePicker(on_result=self.on_logo_picked)
        self.fp_tampon = ft.FilePicker(on_result=self.on_tampon_picked)
        self.fp_signature = ft.FilePicker(on_result=self.on_signature_picked)

        # --- IDENTITÉ ADMINISTRATIVE ---
        self.input_nom = ft.TextField(
            label="Nom officiel du club / association",
            value=asso_data.get("nom", "F-ASSO"),
            col={"sm": 12, "md": 8}
        )
        self.input_sigle = ft.TextField(
            label="Sigle / Abréviation",
            value=asso_data.get("sigle", ""),
            col={"sm": 12, "md": 4}
        )
        self.input_rna = ft.TextField(
            label="N° RNA (ex: W123456789)",
            value=asso_data.get("rna", ""),
            col={"sm": 12, "md": 4}
        )
        self.input_siret = ft.TextField(
            label="N° SIRET / SIREN",
            value=asso_data.get("siret", ""),
            col={"sm": 12, "md": 4}
        )
        self.input_affiliation = ft.TextField(
            label="N° Affiliation Fédérale Principal",
            value=asso_data.get("affiliation", ""),
            col={"sm": 12, "md": 4}
        )

        # --- COORDONNÉES ET ADRESSES ---
        self.input_adresse_siege = ft.TextField(
            label="Adresse du Siège Social",
            value=asso_data.get("adresse_siege", ""),
            col={"sm": 12, "md": 6}
        )
        self.input_adresse_installation = ft.TextField(
            label="Installation principale (Gymnase / Stade / Terrain / Salle)",
            value=asso_data.get("adresse_installation", asso_data.get("adresse_dojo", "")),
            col={"sm": 12, "md": 6}
        )
        self.input_email = ft.TextField(
            label="Adresse Email de contact",
            value=asso_data.get("email", ""),
            col={"sm": 12, "md": 6}
        )
        self.input_telephone = ft.TextField(
            label="Téléphone de contact",
            value=asso_data.get("telephone", ""),
            col={"sm": 12, "md": 6}
        )

        # --- DIRIGEANTS & BUREAU ---
        self.input_president = ft.TextField(
            label="Président(e)",
            value=asso_data.get("president", ""),
            col={"sm": 12, "md": 6}
        )
        self.input_tresorier = ft.TextField(
            label="Trésorier(e)",
            value=asso_data.get("tresorier", ""),
            col={"sm": 12, "md": 6}
        )
        self.input_secretaire = ft.TextField(
            label="Secrétaire Général(e)",
            value=asso_data.get("secretaire", ""),
            col={"sm": 12, "md": 6}
        )
        self.input_prof = ft.TextField(
            label="Responsable Technique / Directeur Sportif",
            value=asso_data.get("prof", asso_data.get("directeur_sportif", "")),
            col={"sm": 12, "md": 6}
        )

        # --- BANQUE & RIB ---
        self.input_banque = ft.TextField(
            label="Nom de la Banque",
            value=asso_data.get("banque", ""),
            col={"sm": 12, "md": 4}
        )
        self.input_iban = ft.TextField(
            label="Code IBAN",
            value=asso_data.get("iban", ""),
            col={"sm": 12, "md": 5}
        )
        self.input_bic = ft.TextField(
            label="Code BIC / SWIFT",
            value=asso_data.get("bic", ""),
            col={"sm": 12, "md": 3}
        )

        # --- VISUELS & DOCUMENTS ---
        self.txt_logo_path = ft.Text(asso_data.get("logo_path") or "Aucun logo défini", size=12, color="grey400")
        self.txt_tampon_path = ft.Text(asso_data.get("tampon_path") or "Aucun tampon défini", size=12, color="grey400")
        self.txt_signature_path = ft.Text(asso_data.get("signature_path") or "Aucune signature définie", size=12, color="grey400")

        # Bouton de sauvegarde
        self.btn_sauvegarder = ft.ElevatedButton(
            "💾 Enregistrer les informations de l'association",
            icon=get_icon("SAVE"),
            bgcolor=self.accent_color,
            color="white",
            height=48,
            on_click=self.sauvegarder_association
        )

        # Structure du composant
        self.content = ft.Column(
            scroll="auto",
            spacing=20,
            controls=[
                ft.Row([
                    ft.Icon(get_icon("ACCOUNT_BALANCE"), size=30, color=self.accent_color),
                    ft.Text("Fiche Administrative Multi-Sports", size=24, weight="bold", color="white"),
                ]),
                ft.Divider(color="grey800"),

                # Card 1: Identité
                self.creer_section_card(
                    "Identité & Immatriculation Légale",
                    ft.ResponsiveRow([
                        self.input_nom,
                        self.input_sigle,
                        self.input_rna,
                        self.input_siret,
                        self.input_affiliation,
                    ], spacing=10)
                ),

                # Card 2: Coordonnées
                self.creer_section_card(
                    "Coordonnées & Installations",
                    ft.ResponsiveRow([
                        self.input_adresse_siege,
                        self.input_adresse_installation,
                        self.input_email,
                        self.input_telephone,
                    ], spacing=10)
                ),

                # Card 3: Bureau
                self.creer_section_card(
                    "Bureau Directeur & Encadrement Sportif",
                    ft.ResponsiveRow([
                        self.input_president,
                        self.input_tresorier,
                        self.input_secretaire,
                        self.input_prof,
                    ], spacing=10)
                ),

                # Card 4: Banque
                self.creer_section_card(
                    "Informations Bancaires (RIB)",
                    ft.ResponsiveRow([
                        self.input_banque,
                        self.input_iban,
                        self.input_bic,
                    ], spacing=10)
                ),

                # Card 5: Visuels
                self.creer_section_card(
                    "Logos & Signatures (Impression PDF)",
                    ft.Column([
                        ft.Row([
                            ft.ElevatedButton("Changer le Logo", icon=get_icon("IMAGE"), on_click=self.demander_logo),
                            self.txt_logo_path
                        ], spacing=10, wrap=True),
                        ft.Row([
                            ft.ElevatedButton("Changer le Tampon", icon=get_icon("APPROVAL"), on_click=self.demander_tampon),
                            self.txt_tampon_path
                        ], spacing=10, wrap=True),
                        ft.Row([
                            ft.ElevatedButton("Changer la Signature", icon=get_icon("DRAW"), on_click=self.demander_signature),
                            self.txt_signature_path
                        ], spacing=10, wrap=True),
                    ], spacing=15)
                ),

                # Bouton principal
                ft.Row([self.btn_sauvegarder], alignment="end")
            ]
        )

    def did_mount(self):
        """Attache les FilePickers à l'overlay de la page lors du chargement du composant."""
        page_obj = self.page or getattr(self.app, "page", None)
        if page_obj:
            for fp in [self.fp_logo, self.fp_tampon, self.fp_signature]:
                if fp not in page_obj.overlay:
                    page_obj.overlay.append(fp)
            page_obj.update()

    def creer_section_card(self, titre, contenu):
        return ft.Container(
            bgcolor="#1F2937", padding=20, border_radius=10,
            content=ft.Column([
                ft.Text(titre, size=16, weight="bold", color="#93C5FD"),
                ft.Divider(color="grey800"),
                contenu
            ], spacing=15)
        )

    def demander_logo(self, e):
        self.fp_logo.pick_files(allowed_extensions=["png", "jpg", "jpeg"])

    def demander_tampon(self, e):
        self.fp_tampon.pick_files(allowed_extensions=["png", "jpg", "jpeg"])

    def demander_signature(self, e):
        self.fp_signature.pick_files(allowed_extensions=["png", "jpg", "jpeg"])

    def on_logo_picked(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            p = e.files[0].path
            if hasattr(self.app, "association"):
                self.app.association["logo_path"] = p
            self.txt_logo_path.value = p
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            if hasattr(self.app, "refresh_sidebar"):
                self.app.refresh_sidebar()
            self._show_snackbar("🖼️ Logo de l'association mis à jour !")
            if self.page:
                self.update()

    on_logo_result = on_logo_picked

    def on_tampon_picked(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            p = e.files[0].path
            if hasattr(self.app, "association"):
                self.app.association["tampon_path"] = p
            self.txt_tampon_path.value = p
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self._show_snackbar("💮 Tampon mis à jour !")
            if self.page:
                self.update()

    on_tampon_result = on_tampon_picked

    def on_signature_picked(self, e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            p = e.files[0].path
            if hasattr(self.app, "association"):
                self.app.association["signature_path"] = p
            self.txt_signature_path.value = p
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self._show_snackbar("✍️ Signature du Président mise à jour !")
            if self.page:
                self.update()

    on_signature_result = on_signature_picked

    def sauvegarder_association(self, e):
        assoc = getattr(self.app, "association", {})
        assoc["nom"] = self.input_nom.value.strip()
        assoc["sigle"] = self.input_sigle.value.strip()
        assoc["rna"] = self.input_rna.value.strip()
        assoc["siret"] = self.input_siret.value.strip()
        assoc["affiliation"] = self.input_affiliation.value.strip()
        assoc["adresse_siege"] = self.input_adresse_siege.value.strip()
        assoc["adresse_installation"] = self.input_adresse_installation.value.strip()
        assoc["adresse_dojo"] = self.input_adresse_installation.value.strip()
        assoc["email"] = self.input_email.value.strip()
        assoc["telephone"] = self.input_telephone.value.strip()
        assoc["president"] = self.input_president.value.strip()
        assoc["tresorier"] = self.input_tresorier.value.strip()
        assoc["secretaire"] = self.input_secretaire.value.strip()
        assoc["prof"] = self.input_prof.value.strip()
        assoc["directeur_sportif"] = self.input_prof.value.strip()
        assoc["banque"] = self.input_banque.value.strip()
        assoc["iban"] = self.input_iban.value.strip()
        assoc["bic"] = self.input_bic.value.strip()

        self.app.association = assoc
        if hasattr(self.app, "save_data"):
            self.app.save_data()
        if hasattr(self.app, "refresh_sidebar"):
            self.app.refresh_sidebar()

        self._show_snackbar("💾 Informations de l'association sauvegardées avec succès !")

    def _show_snackbar(self, message: str, is_error: bool = False):
        color = "red700" if is_error else "green700"
        page_obj = getattr(self.app, "page", None) or self.page
        if page_obj:
            snack = ft.SnackBar(ft.Text(message), bgcolor=color)
            if hasattr(page_obj, "open"):
                try:
                    page_obj.open(snack)
                except Exception:
                    page_obj.snack_bar = snack
                    snack.open = True
            else:
                page_obj.snack_bar = snack
                snack.open = True
            page_obj.update()