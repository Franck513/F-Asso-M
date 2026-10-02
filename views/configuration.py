# views/configuration.py
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import flet as ft
from database import DatabaseManager


def get_icon(name: str):
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()


def extract_drive_folder_id(url_or_id: str) -> str:
    """Extrait l'ID du dossier à partir d'un lien Google Drive ou renvoie l'ID directement."""
    if not url_or_id:
        return ""
    text = url_or_id.strip()
    if "folders/" in text:
        match = re.search(r'folders/([a-zA-Z0-9_-]+)', text)
        if match:
            return match.group(1)
    return text


class ConfigurationView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True, bgcolor="#0F172A", padding=15)
        self.app = app
        asso_data = getattr(self.app, "association", {})
        self.accent_color = asso_data.get("accent_color", "#1E3A8A")

        # --- EXPLORATEUR INTERNE (ÉTAT PERSISTANT) ---
        data_dir_path = Path(getattr(self.app, "data_dir", "."))
        if not hasattr(self.app, "current_explorer_path") or not self.app.current_explorer_path:
            self.app.current_explorer_path = data_dir_path
        
        try:
            if not Path(self.app.current_explorer_path).resolve().is_relative_to(data_dir_path.resolve()):
                self.app.current_explorer_path = data_dir_path
        except Exception:
            self.app.current_explorer_path = data_dir_path

        self.current_explorer_path = Path(self.app.current_explorer_path)
        self.explorer_container = ft.Container()

        # --- APPARENCE & GRAPHISME ---
        page_obj = getattr(self.app, "page", None) or getattr(self, "page", None)
        current_theme = getattr(page_obj, "theme_mode", ft.ThemeMode.DARK) if page_obj else ft.ThemeMode.DARK

        self.sw_theme = ft.Switch(
            label="Mode Sombre",
            value=(current_theme == ft.ThemeMode.DARK or current_theme is None),
            on_change=self.toggle_theme
        )

        self.dropdown_couleur = ft.Dropdown(
            label="Couleur d'accentuation (Thème du Club)",
            options=[
                ft.dropdown.Option(key="#1E3A8A", text="🔵 Bleu Sport (Défaut)"),
                ft.dropdown.Option(key="#B91C1C", text="🔴 Rouge Dynamique"),
                ft.dropdown.Option(key="#0369A1", text="Cyan Élite"),
                ft.dropdown.Option(key="#047857", text="🟢 Vert Terrain"),
                ft.dropdown.Option(key="#6D28D9", text="🟣 Violet Performance"),
                ft.dropdown.Option(key="#374151", text="⚫ Gris Sombre Intense"),
            ],
            value=asso_data.get("accent_color", "#1E3A8A")
        )
        self.dropdown_couleur.on_change = self.change_accent_color

        # Visuels (Logo, Tampon, Signature)
        self.txt_logo_path = ft.Text(asso_data.get("logo_path") or "Aucun logo défini", size=12, color="grey400")
        self.txt_tampon_path = ft.Text(asso_data.get("tampon_path") or "Aucun tampon défini", size=12, color="grey400")
        self.txt_signature_path = ft.Text(asso_data.get("signature_path") or "Aucune signature définie", size=12, color="grey400")

        # --- CONFIGURATION CLOUD & DOSSIER LOCAL ---
        data_dir_str = str(data_dir_path)
        self.input_path_cloud = ft.TextField(
            label="Chemin local du dossier de données (Local ou Drive synchronisé)",
            value=data_dir_str,
            expand=True,
            read_only=False,
            hint_text="Ex: C:\\Users\\Nom\\Google Drive\\MonClubData"
        )

        self.btn_apply_manual_path = ft.ElevatedButton(
            "Valider le chemin",
            icon=get_icon("CHECK"),
            on_click=self.appliquer_chemin_manuel
        )

        self.btn_select_cloud_folder = ft.ElevatedButton(
            "📁 Parcourir",
            icon=get_icon("FOLDER_OPEN"),
            on_click=self.demander_dossier_cloud
        )

        self.btn_reset_default_folder = ft.OutlinedButton(
            "🏠 Remettre le dossier par défaut",
            icon=get_icon("HOME"),
            on_click=self.reinitialiser_dossier_defaut
        )

        self.btn_sync = ft.ElevatedButton(
            "🔄 Recharger & Synchroniser les données locales",
            icon=get_icon("SYNC"),
            bgcolor=self.accent_color,
            color="white",
            on_click=self.forcer_synchronisation
        )

        # --- LIEN DU DOSSIER GOOGLE DRIVE (API Directe) ---
        saved_drive_link = asso_data.get("drive_folder_link", "")
        self.input_drive_link = ft.TextField(
            label="Lien de partage du dossier Google Drive (pour l'API)",
            value=saved_drive_link,
            hint_text="Collez ici : https://drive.google.com/drive/folders/1a2b3c4d...",
            expand=True
        )

        self.btn_save_drive_link = ft.ElevatedButton(
            "💾 Enregistrer le lien",
            icon=get_icon("SAVE"),
            on_click=self.sauvegarder_lien_drive
        )

        # --- ÉTAT ET ACTIONS DRIVE API (CREDENTIALS & TOKEN) ---
        cred_in_root = Path("credentials.json").exists()
        cred_in_data = (data_dir_path / "credentials.json").exists()
        has_credentials = cred_in_root or cred_in_data

        self.txt_drive_status = ft.Text(
            "Fichier credentials.json détecté" if has_credentials else "Fichier credentials.json introuvable",
            size=12,
            color="#4ADE80" if has_credentials else "red400"
        )

        self.btn_import_credentials = ft.ElevatedButton(
            "🔑 Importer credentials.json",
            icon=get_icon("KEY"),
            on_click=self.demander_credentials
        )

        token_in_root = Path("token.json").exists()
        token_in_data = (data_dir_path / "token.json").exists()
        has_token = token_in_root or token_in_data

        self.txt_token_status = ft.Text(
            "Fichier token.json détecté" if has_token else "Fichier token.json introuvable",
            size=12,
            color="#4ADE80" if has_token else "red400"
        )

        self.btn_import_token = ft.ElevatedButton(
            "🔑 Importer token.json",
            icon=get_icon("KEY"),
            on_click=self.demander_token
        )

        self.btn_upload_drive = ft.ElevatedButton(
            "☁️ Envoyez vos données sur Drive",
            icon=get_icon("CLOUD_UPLOAD"),
            bgcolor="#065F46",
            color="white",
            on_click=self.envoyer_sauvegarde_drive
        )

        self.btn_download_drive = ft.ElevatedButton(
            "📥 Récupérer la dernière version depuis Drive",
            icon=get_icon("CLOUD_DOWNLOAD"),
            bgcolor="#1D4ED8",
            color="white",
            on_click=self.telecharger_derniere_sauvegarde_drive
        )

        # --- SAUVEGARDES LOCALES & RESTAURATION ---
        self.btn_backup = ft.ElevatedButton(
            "💾 Créer une copie ZIP locale",
            icon=get_icon("BACKUP"),
            bgcolor=self.accent_color,
            color="white",
            on_click=self.creer_sauvegarde
        )

        self.btn_restore = ft.OutlinedButton(
            "📥 Restaurer depuis un ZIP local",
            icon=get_icon("RESTORE"),
            on_click=self.demander_restauration
        )

        self.btn_reset_storage = ft.OutlinedButton(
            "🧹 Vider le cache local",
            icon=get_icon("DELETE_SWEEP"),
            icon_color="red400",
            on_click=self.reinitialiser_cache
        )

        # --- LAYOUT ---
        saison_act = getattr(self.app, "saison_active", "En cours")
        club_nom = asso_data.get("nom", "N/A")

        self.content = ft.Column(
            scroll="auto",
            spacing=20,
            controls=[
                ft.Row([
                    ft.Icon(get_icon("SETTINGS_ROUNDED"), size=30, color=self.accent_color),
                    ft.Text("Configuration Technique & Cloud de l'Application", size=24, weight="bold", color="white"),
                ]),
                ft.Divider(color="grey800"),

                # Card 1: Personnalisation Graphique
                self.creer_section_card(
                    "Personnalisation Graphique & Visuels de l'Association",
                    ft.Column([
                        self.sw_theme,
                        self.dropdown_couleur,
                        ft.Divider(color="grey800"),
                        ft.Text("Images & Documents Officiels (pour PDF)", weight="bold", size=14, color="white"),
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

                # Card 2: Configuration Cloud / Google Drive
                self.creer_section_card(
                    "Synchronisation Multi-Utilisateurs & Google Drive / Cloud",
                    ft.Column([
                        ft.Text(
                            "1. Synchronisation Automatique par Dossier Drive :",
                            size=13, weight="bold", color="white"
                        ),
                        ft.ResponsiveRow([
                            self.input_path_cloud,
                            self.btn_apply_manual_path,
                            self.btn_select_cloud_folder,
                        ], spacing=10),
                        ft.Row([
                            self.btn_reset_default_folder,
                            self.btn_sync
                        ], spacing=10, wrap=True),
                        ft.Divider(color="grey800"),
                        ft.Text(
                            "2. Synchronisation Manuelle par l'API (Envoi / Récupération ZIP) :",
                            weight="bold", size=13, color="white"
                        ),
                        ft.ResponsiveRow([
                            self.input_drive_link,
                            self.btn_save_drive_link
                        ], spacing=10),
                        ft.Row([
                            self.txt_drive_status,
                            self.btn_import_credentials
                        ], spacing=10, wrap=True),
                        ft.Row([
                            self.txt_token_status,
                            self.btn_import_token
                        ], spacing=10, wrap=True),
                        ft.Row([
                            self.btn_upload_drive,
                            self.btn_download_drive
                        ], spacing=10, wrap=True)
                    ], spacing=15)
                ),

                # Card 3: Maintenance, Backups & Restauration
                self.creer_section_card(
                    "Maintenance, Sauvegardes & Restauration Local",
                    ft.Column([
                        ft.Text("Sauvegardez, restaurez ou réinitialisez la mémoire locale de l'application.", size=13, color="grey300"),
                        ft.Row([
                            self.btn_backup,
                            self.btn_restore
                        ], spacing=10, wrap=True),
                        ft.Divider(color="grey800"),
                        self.btn_reset_storage
                    ], spacing=15)
                ),

                # Card 4: Explorateur Interne Interactif
                self.creer_section_card(
                    "Explorateur de Données Intégré",
                    self.construire_explorateur_interne()
                ),

                # Card 5: Informations Système
                self.creer_section_card(
                    "Informations Système",
                    ft.Column([
                        ft.Text("🏆 Application Gestion Club Multi-Sports", weight="bold", color="white"),
                        ft.Text(f"Saison active chargée : {saison_act}", size=12, color="grey400"),
                        ft.Text(f"Club : {club_nom}", size=12, color="grey400"),
                        ft.Text("Moteur : Hybrid SQLite / JSON + Flet Material Design 3", size=12, color="grey400"),
                    ], spacing=5)
                )
            ]
        )

    def creer_section_card(self, titre, contenu):
        return ft.Container(
            bgcolor="#1F2937", padding=20, border_radius=10,
            content=ft.Column([
                ft.Text(titre, size=16, weight="bold", color="#93C5FD"),
                ft.Divider(color="grey800"),
                contenu
            ], spacing=15)
        )

    # --- MÉTHODES DE L'EXPLORATEUR INTERACTIF ---
    def _clean_path_name(self, text: str) -> str:
        if not text:
            return "Club"
        cleaned = re.sub(r'[\\/*?:"<>|]', '_', str(text)).strip()
        return cleaned if cleaned else "Club"

    def _get_dossier_export(self) -> Path:
        if sys.platform in ["win32", "darwin"]:
            download_dir = Path.home() / "Downloads"
        else:
            android_path = Path("/storage/emulated/0/Download")
            if android_path.exists() and android_path.is_dir():
                download_dir = android_path
            else:
                download_dir = Path.home() / "Downloads"

        asso_data = getattr(self.app, "association", {})
        nom_asso = self._clean_path_name(asso_data.get("nom", "Club_Sportif"))
        saison = self._clean_path_name(getattr(self.app, "saison_active", "Saison_En_Cours"))

        target_dir = download_dir / nom_asso / saison
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def _get_current_directory_contents(self):
        dossiers = []
        fichiers = []
        
        base_dir = Path(getattr(self.app, "data_dir", "."))
        try:
            if not self.current_explorer_path.resolve().is_relative_to(base_dir.resolve()):
                self.current_explorer_path = base_dir
        except Exception:
            self.current_explorer_path = base_dir

        if self.current_explorer_path.exists() and self.current_explorer_path.is_dir():
            for item in sorted(self.current_explorer_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                try:
                    item_size = item.stat().st_size if item.is_file() else sum(f.stat().st_size for f in item.glob('**/*') if f.is_file())
                except Exception:
                    item_size = 0

                if item.is_dir():
                    dossiers.append({"path": item, "name": item.name, "type": "dir"})
                else:
                    fichiers.append({
                        "path": item,
                        "name": item.name,
                        "size": f"{item_size / 1024:.1f} Ko" if item_size > 1024 else f"{item_size} octets",
                        "type": "file"
                    })
                    
        return dossiers, fichiers

    def _creer_contenu_explorateur(self):
        base_dir = Path(getattr(self.app, "data_dir", "."))
        dossiers, fichiers = self._get_current_directory_contents()
        
        try:
            rel_path = self.current_explorer_path.relative_to(base_dir)
            path_display = str(Path("data") / rel_path)
        except Exception:
            path_display = "data"

        lignes_elements = []

        if self.current_explorer_path.resolve() != base_dir.resolve():
            lignes_elements.append(
                ft.Container(
                    bgcolor="#1F2937",
                    padding=8,
                    border_radius=6,
                    margin=ft.margin.only(bottom=5),
                    ink=True,
                    on_click=self.remonter_dossier,
                    content=ft.Row([
                        ft.Icon(get_icon("ARROW_BACK"), size=18, color="#FBBF24"),
                        ft.Text(".. (Dossier supérieur)", size=12, weight="bold", color="#FBBF24"),
                    ], spacing=10)
                )
            )

        for d in dossiers:
            lignes_elements.append(
                ft.Container(
                    bgcolor="#111827",
                    padding=10,
                    border_radius=6,
                    margin=ft.margin.only(bottom=5),
                    ink=True,
                    on_click=self.ouvrir_dossier,
                    data=str(d["path"]),
                    content=ft.Row([
                        ft.Icon(get_icon("FOLDER"), size=18, color="#FBBF24"),
                        ft.Text(d["name"], size=12, weight="bold", color="white", expand=True),
                        ft.Icon(get_icon("CHEVRON_RIGHT"), size=16, color="grey500")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            )

        for f in fichiers:
            lignes_elements.append(
                ft.Container(
                    bgcolor="#111827",
                    padding=10,
                    border_radius=6,
                    margin=ft.margin.only(bottom=5),
                    ink=True,
                    on_click=self.clic_fichier,
                    data=str(f["path"]),
                    content=ft.Row([
                        ft.Icon(get_icon("INSERT_DRIVE_FILE"), size=18, color="#93C5FD"),
                        ft.Column([
                            ft.Text(f["name"], size=12, weight="bold", color="white"),
                            ft.Text(f["size"], size=10, color="grey400"),
                        ], expand=True, spacing=2),
                        ft.Icon(get_icon("OPEN_IN_NEW" if sys.platform == "win32" else "SHARE"), size=16, color="#93C5FD", tooltip="Ouvrir / Partager")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                )
            )

        if not dossiers and not fichiers:
            lignes_elements.append(ft.Text("Ce dossier est vide.", size=12, color="grey400"))

        return ft.Column([
            ft.Row([
                ft.Icon(get_icon("FOLDER_OPEN"), size=16, color="#93C5FD"),
                ft.Text(f"Emplacement : {path_display}", size=12, weight="bold", color="#93C5FD", expand=True),
            ], spacing=5),
            ft.Container(
                content=ft.Column(lignes_elements, scroll="auto", spacing=5),
                height=220,
                bgcolor="#0B0F19",
                padding=10,
                border_radius=8,
                border=ft.border.all(1, "grey800")
            ),
            ft.Row([
                ft.OutlinedButton("🏠 Retour Racine", icon=get_icon("HOME"), on_click=self.aller_racine),
                ft.OutlinedButton("🔄 Rafraîchir", icon=get_icon("REFRESH"), on_click=self.rafraichir_explorateur_ui)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ], spacing=10)

    def construire_explorateur_interne(self):
        self.explorer_container.content = self._creer_contenu_explorateur()
        return self.explorer_container

    def mettre_a_jour_affichage_explorateur(self):
        if hasattr(self, "explorer_container") and self.explorer_container:
            self.explorer_container.content = self._creer_contenu_explorateur()
            self.explorer_container.update()

    def ouvrir_dossier(self, e):
        nouveau_chemin = e.control.data
        if nouveau_chemin:
            self.current_explorer_path = Path(nouveau_chemin)
            self.app.current_explorer_path = self.current_explorer_path
            self.mettre_a_jour_affichage_explorateur()

    def remonter_dossier(self, e):
        base_dir = Path(getattr(self.app, "data_dir", "."))
        if self.current_explorer_path.resolve() != base_dir.resolve():
            self.current_explorer_path = self.current_explorer_path.parent
            self.app.current_explorer_path = self.current_explorer_path
            self.mettre_a_jour_affichage_explorateur()

    def aller_racine(self, e):
        self.current_explorer_path = Path(getattr(self.app, "data_dir", "."))
        self.app.current_explorer_path = self.current_explorer_path
        self.mettre_a_jour_affichage_explorateur()

    def rafraichir_explorateur_ui(self, e):
        self.mettre_a_jour_affichage_explorateur()

    def clic_fichier(self, e):
        file_path = Path(e.control.data)

        if not file_path.exists():
            self._show_snackbar("Fichier introuvable.", is_error=True)
            return

        suffix = file_path.suffix.lower()

        if sys.platform in ["win32", "darwin"]:
            try:
                if sys.platform == "win32":
                    os.startfile(str(file_path))
                else:
                    subprocess.run(["open", str(file_path)], check=True)
                self._show_snackbar(f"📂 Ouverture de {file_path.name}...")
                return
            except Exception:
                pass

        if suffix in [".json", ".txt", ".log", ".md", ".csv", ".ini"]:
            self._afficher_dialogue_fichier(file_path)
            return

        try:
            target_dir = self._get_dossier_export()
            dest_path = target_dir / file_path.name

            file_bytes = file_path.read_bytes()
            if not file_bytes:
                self._show_snackbar("❌ Le fichier source est vide.", is_error=True)
                return

            dest_path.write_bytes(file_bytes)
            asso_name = target_dir.parent.name
            season_name = target_dir.name
            self._show_snackbar(f"✅ Enregistré dans {asso_name}/{season_name}")

            page_obj = getattr(self.app, "page", None) or self.page
            if page_obj:
                page_obj.launch_url(dest_path.as_uri())

            return
        except Exception as ex:
            self._show_snackbar(f"Fichier copié, mais ouverture auto impossible : {ex}", is_error=True)

        if hasattr(self.app, "file_picker") and hasattr(self.app.file_picker, "save_file"):
            try:
                filename = file_path.name
                self.app.file_picker.on_result = lambda res: self._sauvegarder_copie_fichier(res, str(file_path))
                self.app.file_picker.save_file(
                    dialog_title=f"Enregistrer {filename} sur l'appareil",
                    file_name=filename
                )
                self._show_snackbar(f"Sélectionnez l'emplacement pour {filename}")
            except Exception as ex:
                self._show_snackbar(f"❌ Erreur d'export : {ex}", is_error=True)
        else:
            self._show_snackbar(f"Chemin : {file_path}")

    def _afficher_dialogue_fichier(self, file_path: Path):
        page_obj = getattr(self.app, "page", None) or getattr(self, "page", None)
        if not page_obj:
            return

        contenu_texte = ""
        is_text = file_path.suffix.lower() in [".json", ".txt", ".log", ".md", ".csv", ".ini"]
        if is_text:
            try:
                if file_path.stat().st_size < 150 * 1024:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        contenu_texte = f.read()
                else:
                    contenu_texte = "[Fichier texte trop volumineux pour un affichage direct]"
            except Exception as ex:
                contenu_texte = f"[Erreur de lecture : {ex}]"

        controls_list = [
            ft.Text(f"Chemin : {file_path}", size=11, color="grey400", selectable=True),
        ]

        if is_text and contenu_texte:
            controls_list.append(ft.Divider(color="grey800"))
            controls_list.append(ft.Text("Aperçu du contenu :", weight="bold", size=13, color="white"))
            controls_list.append(
                ft.Container(
                    content=ft.Text(contenu_texte, size=11, font_family="monospace", color="grey200", selectable=True),
                    bgcolor="#0B0F19",
                    padding=10,
                    border_radius=6,
                    height=200,
                    border=ft.border.all(1, "grey800")
                )
            )
        else:
            controls_list.append(ft.Text("Ce type de fichier ne peut pas être prévisualisé en texte brut.", size=12, color="grey400"))

        def exporter_clic(_):
            self._fermer_dlg(page_obj, dlg)

            if hasattr(self.app, "file_picker") and hasattr(self.app.file_picker, "save_file"):
                try:
                    filename = file_path.name
                    self.app.file_picker.on_result = lambda res: self._sauvegarder_copie_fichier(res, str(file_path))
                    self.app.file_picker.save_file(dialog_title=f"Exporter {filename} vers...", file_name=filename)
                except Exception as ex:
                    self._show_snackbar(f"Erreur d'export : {ex}", is_error=True)

        dlg = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(get_icon("INSERT_DRIVE_FILE"), color="#93C5FD"),
                ft.Text(file_path.name, size=16, weight="bold", color="white", expand=True)
            ]),
            content=ft.Column(controls_list, width=400, tight=True, spacing=10),
            actions=[
                ft.TextButton("Fermer", on_click=lambda _: self._fermer_dlg(page_obj, dlg)),
                ft.ElevatedButton("📥 Exporter / Sauvegarder", icon=get_icon("SAVE"), on_click=exporter_clic)
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor="#1F2937"
        )
        
        self._ouvrir_dlg(page_obj, dlg)

    def _ouvrir_dlg(self, page_obj, dlg):
        """Ouvre un dialogue de manière compatible inter-versions Flet."""
        try:
            if hasattr(page_obj, "open"):
                page_obj.open(dlg)
            else:
                page_obj.dialog = dlg
                dlg.open = True
                page_obj.update()
        except Exception:
            dlg.open = True
            page_obj.dialog = dlg
            page_obj.update()

    def _fermer_dlg(self, page_obj, dlg):
        """Ferme un dialogue de manière compatible inter-versions Flet."""
        try:
            if hasattr(page_obj, "close"):
                page_obj.close(dlg)
            else:
                dlg.open = False
                page_obj.update()
        except Exception:
            dlg.open = False
            try:
                page_obj.update()
            except Exception:
                pass

    def _sauvegarder_copie_fichier(self, e, source_path):
        if not getattr(e, "path", None):
            return

        try:
            source = Path(source_path)
            if not source.exists():
                self._show_snackbar("❌ Fichier source introuvable.", is_error=True)
                return

            file_bytes = source.read_bytes()
            if not file_bytes:
                self._show_snackbar("❌ Le fichier source est vide.", is_error=True)
                return

            dest_path = Path(e.path)
            dest_path.write_bytes(file_bytes)

            if dest_path.exists() and dest_path.stat().st_size > 0:
                self._show_snackbar("✅ Fichier exporté avec succès !")
            else:
                self._show_snackbar("⚠️ Restriction Android : le fichier fait 0 octet.", is_error=True)

        except Exception as ex:
            self._show_snackbar(f"❌ Erreur lors de la copie : {ex}", is_error=True)

    # --- AUTRES MÉTHODES ---
    def toggle_theme(self, e):
        page_obj = getattr(self.app, "page", None) or self.page
        if page_obj:
            page_obj.theme_mode = ft.ThemeMode.DARK if self.sw_theme.value else ft.ThemeMode.LIGHT
            page_obj.update()

    def change_accent_color(self, e):
        chosen_hex = self.dropdown_couleur.value
        if hasattr(self.app, "association"):
            self.app.association["accent_color"] = chosen_hex
        if hasattr(self.app, "save_data"):
            self.app.save_data()
        if hasattr(self.app, "refresh_sidebar"):
            self.app.refresh_sidebar()

        self.btn_backup.bgcolor = chosen_hex
        self.btn_sync.bgcolor = chosen_hex
        self._show_snackbar("Thème mis à jour avec succès !")

    def appliquer_chemin_manuel(self, e):
        nouveau_chemin_str = self.input_path_cloud.value.strip()
        if not nouveau_chemin_str:
            self._show_snackbar("Veuillez entrer un chemin valide.", is_error=True)
            return

        nouveau_dossier = Path(nouveau_chemin_str)
        try:
            nouveau_dossier.mkdir(parents=True, exist_ok=True)
            self.app.data_dir = nouveau_dossier
            self.app.db = DatabaseManager(self.app.data_dir)
            self.app.current_explorer_path = nouveau_dossier

            if hasattr(self.app, "association"):
                self.app.association["custom_data_dir"] = str(nouveau_dossier)
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            if hasattr(self.app, "load_data"):
                self.app.load_data()
            if hasattr(self.app, "navigate_to") and hasattr(self.app, "current_view_name"):
                self.app.navigate_to(self.app.current_view_name)

            self._show_snackbar(f"📁 Données connectées au chemin : {nouveau_dossier}")
        except Exception as ex:
            self._show_snackbar(f"Impossible d'accéder à ce chemin : {ex}", is_error=True)

    def sauvegarder_lien_drive(self, e):
        lien = self.input_drive_link.value.strip()
        folder_id = extract_drive_folder_id(lien)
        
        if hasattr(self.app, "association"):
            self.app.association["drive_folder_link"] = lien
            self.app.association["drive_folder_id"] = folder_id
        if hasattr(self.app, "save_data"):
            self.app.save_data()

        if folder_id:
            self._show_snackbar(f"🔗 Lien Drive enregistré ! ID du dossier : {folder_id}")
        else:
            self._show_snackbar("Lien réinitialisé.")

    def demander_credentials(self, e):
        if hasattr(self.app, "file_picker"):
            self.app.file_picker.on_result = self.on_credentials_picked
            self.app.file_picker.pick_files(
                allowed_extensions=["json"],
                dialog_title="Sélectionner le fichier credentials.json"
            )
        else:
            self._show_snackbar("Sélecteur de fichier indisponible.", is_error=True)

    def on_credentials_picked(self, e):
        if not e.files or len(e.files) == 0:
            return

        picked_file = e.files[0]
        try:
            src_path = Path(picked_file.path) if picked_file.path else None
            if not src_path or not src_path.exists():
                self._show_snackbar("❌ Fichier introuvable.", is_error=True)
                return

            content = src_path.read_bytes()

            dest_data = Path(getattr(self.app, "data_dir", ".")) / "credentials.json"
            dest_data.write_bytes(content)

            try:
                Path("credentials.json").write_bytes(content)
            except Exception:
                pass

            self.txt_drive_status.value = "Fichier credentials.json détecté"
            self.txt_drive_status.color = "#4ADE80"
            self.update()

            self._show_snackbar("🔑 Fichier credentials.json importé avec succès !")
        except Exception as ex:
            self._show_snackbar(f"❌ Erreur lors de l'importation : {ex}", is_error=True)

    def demander_token(self, e):
        if hasattr(self.app, "file_picker"):
            self.app.file_picker.on_result = self.on_token_picked
            self.app.file_picker.pick_files(
                allowed_extensions=["json"],
                dialog_title="Sélectionner le fichier token.json"
            )
        else:
            self._show_snackbar("Sélecteur de fichier indisponible.", is_error=True)

    def on_token_picked(self, e):
        if not e.files or len(e.files) == 0:
            return

        picked_file = e.files[0]
        try:
            src_path = Path(picked_file.path) if picked_file.path else None
            if not src_path or not src_path.exists():
                self._show_snackbar("❌ Fichier introuvable.", is_error=True)
                return

            content = src_path.read_bytes()

            dest_data = Path(getattr(self.app, "data_dir", ".")) / "token.json"
            dest_data.write_bytes(content)

            try:
                Path("token.json").write_bytes(content)
            except Exception:
                pass

            self.txt_token_status.value = "Fichier token.json détecté"
            self.txt_token_status.color = "#4ADE80"
            self.update()

            self._show_snackbar("🔑 Fichier token.json importé avec succès !")
        except Exception as ex:
            self._show_snackbar(f"❌ Erreur lors de l'importation : {ex}", is_error=True)

    def demander_dossier_cloud(self, e):
        if hasattr(self.app, "dir_picker"):
            self.app.dir_picker.on_result = self.on_dir_picked
            self.app.dir_picker.get_directory_path(dialog_title="Sélectionner le dossier Google Drive / Cloud")
        else:
            self._show_snackbar("Sélecteur de dossier indisponible sur cette plateforme.", is_error=True)

    def on_dir_picked(self, e):
        if e.path:
            nouveau_dossier = Path(e.path)
            self.input_path_cloud.value = str(nouveau_dossier)
            
            self.app.data_dir = nouveau_dossier
            self.app.db = DatabaseManager(self.app.data_dir)
            self.app.current_explorer_path = nouveau_dossier
            
            if hasattr(self.app, "association"):
                self.app.association["custom_data_dir"] = str(nouveau_dossier)
            if hasattr(self.app, "save_data"):
                self.app.save_data()
                
            if hasattr(self.app, "load_data"):
                self.app.load_data()
            if hasattr(self.app, "navigate_to") and hasattr(self.app, "current_view_name"):
                self.app.navigate_to(self.app.current_view_name)
                
            self._show_snackbar(f"📁 Données connectées au dossier Drive : {e.path}")

    def reinitialiser_dossier_defaut(self, e):
        from main import get_writable_data_dir
        dossier_defaut = get_writable_data_dir()
        
        self.app.data_dir = dossier_defaut
        self.app.db = DatabaseManager(self.app.data_dir)
        self.app.current_explorer_path = dossier_defaut
        self.input_path_cloud.value = str(dossier_defaut)
        
        if hasattr(self.app, "association") and "custom_data_dir" in self.app.association:
            del self.app.association["custom_data_dir"]
        if hasattr(self.app, "save_data"):
            self.app.save_data()
        if hasattr(self.app, "load_data"):
            self.app.load_data()
        if hasattr(self.app, "navigate_to") and hasattr(self.app, "current_view_name"):
            self.app.navigate_to(self.app.current_view_name)
            
        self._show_snackbar("🏠 Dossier réinitialisé vers l'emplacement par défaut !")

    def demander_logo(self, e):
        if hasattr(self.app, "file_picker"):
            self.app.file_picker.on_result = self.on_logo_picked
            self.app.file_picker.pick_files(allowed_extensions=["png", "jpg", "jpeg"])

    def demander_tampon(self, e):
        if hasattr(self.app, "file_picker"):
            self.app.file_picker.on_result = self.on_tampon_picked
            self.app.file_picker.pick_files(allowed_extensions=["png", "jpg", "jpeg"])

    def demander_signature(self, e):
        if hasattr(self.app, "file_picker"):
            self.app.file_picker.on_result = self.on_signature_picked
            self.app.file_picker.pick_files(allowed_extensions=["png", "jpg", "jpeg"])

    def demander_restauration(self, e):
        if hasattr(self.app, "file_picker"):
            self.app.file_picker.on_result = self.on_restore_picked
            self.app.file_picker.pick_files(allowed_extensions=["zip"], dialog_title="Sélectionner la sauvegarde ZIP à restaurer")

    def on_logo_picked(self, e):
        if e.files:
            p = e.files[0].path
            if hasattr(self.app, "association"):
                self.app.association["logo_path"] = p
            self.txt_logo_path.value = p
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            if hasattr(self.app, "refresh_sidebar"):
                self.app.refresh_sidebar()
            self._show_snackbar("🖼️ Logo mis à jour avec succès !")

    def on_tampon_picked(self, e):
        if e.files:
            p = e.files[0].path
            if hasattr(self.app, "association"):
                self.app.association["tampon_path"] = p
            self.txt_tampon_path.value = p
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self._show_snackbar("💮 Tampon de l'association mis à jour !")

    def on_signature_picked(self, e):
        if e.files:
            p = e.files[0].path
            if hasattr(self.app, "association"):
                self.app.association["signature_path"] = p
            self.txt_signature_path.value = p
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self._show_snackbar("✍️ Signature du Président mise à jour !")

    def on_restore_picked(self, e):
        if e.files and len(e.files) > 0:
            zip_path = e.files[0].path
            try:
                if hasattr(self.app, "db") and hasattr(self.app.db, "restore_local_backup"):
                    if self.app.db.restore_local_backup(zip_path):
                        if hasattr(self.app, "load_data"):
                            self.app.load_data()
                        if hasattr(self.app, "navigate_to") and hasattr(self.app, "current_view_name"):
                            self.app.navigate_to(self.app.current_view_name)
                        self._show_snackbar("✅ Données restaurées et rechargées avec succès !")
                    else:
                        self._show_snackbar("❌ Impossible de restaurer ce fichier ZIP.", is_error=True)
            except Exception as ex:
                self._show_snackbar(f"❌ Erreur de restauration : {ex}", is_error=True)

    def forcer_synchronisation(self, e):
        try:
            if hasattr(self.app, "load_data"):
                self.app.load_data()
            if hasattr(self.app, "navigate_to") and hasattr(self.app, "current_view_name"):
                self.app.navigate_to(self.app.current_view_name)
            self._show_snackbar("✅ Données rechargées & synchronisées !")
        except Exception as ex:
            self._show_snackbar(f"❌ Erreur de synchronisation : {ex}", is_error=True)

    def creer_sauvegarde(self, e):
        try:
            if hasattr(self.app, "db") and hasattr(self.app.db, "create_local_backup"):
                backup_path = self.app.db.create_local_backup()
                self._show_snackbar(f"💾 Sauvegarde ZIP créée : {Path(backup_path).name}")
            else:
                self._show_snackbar("Module de base de données non connecté.", is_error=True)
        except Exception as ex:
            self._show_snackbar(f"Erreur de sauvegarde : {ex}", is_error=True)

    def envoyer_sauvegarde_drive(self, e):
        """Envoie la sauvegarde locale vers Google Drive avec affichage d'un popup de chargement."""
        page_obj = getattr(self.app, "page", None) or getattr(self, "page", None)

        loading_dlg = ft.AlertDialog(
            modal=True,
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.ProgressRing(color="#4ADE80", width=40, height=40),
                        ft.Text("Envoi de la sauvegarde sur Google Drive...", weight="bold", color="white", size=14),
                        ft.Text("Veuillez patienter pendant le transfert...", size=12, color="grey400"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=15,
                ),
                padding=10,
            ),
            bgcolor="#1F2937",
        )

        def worker():
            msg = ""
            is_err = False
            try:
                if hasattr(self.app, "db"):
                    zip_path = self.app.db.create_local_backup()
                    folder_id = self.app.association.get("drive_folder_id")
                    res = self.app.db.upload_to_drive(zip_path, folder_id=folder_id)
                    msg = f"☁ Sauvegarde transmise sur Google Drive (ID: {res.get('id')}) !"
                else:
                    msg = "Gestionnaire de données indisponible."
                    is_err = True
            except Exception as ex:
                msg = f"❌ Erreur Google Drive : {ex}"
                is_err = True
            finally:
                self._fermer_dlg(page_obj, loading_dlg)
                self._show_snackbar(msg, is_error=is_err)

        self._ouvrir_dlg(page_obj, loading_dlg)
        threading.Thread(target=worker, daemon=True).start()

    def telecharger_derniere_sauvegarde_drive(self, e):
        """Récupère et applique la dernière sauvegarde Drive avec affichage d'un popup de chargement."""
        page_obj = getattr(self.app, "page", None) or getattr(self, "page", None)

        loading_dlg = ft.AlertDialog(
            modal=True,
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.ProgressRing(color="#93C5FD", width=40, height=40),
                        ft.Text("Récupération de la sauvegarde depuis Google Drive...", weight="bold", color="white", size=14),
                        ft.Text("Veuillez patienter pendant le téléchargement...", size=12, color="grey400"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=15,
                ),
                padding=10,
            ),
            bgcolor="#1F2937",
        )

        def worker():
            msg = ""
            is_err = False
            try:
                if hasattr(self.app, "db"):
                    folder_id = self.app.association.get("drive_folder_id")
                    if self.app.db.restore_from_drive_latest(folder_id=folder_id):
                        if hasattr(self.app, "load_data"):
                            self.app.load_data()
                        if hasattr(self.app, "navigate_to") and hasattr(self.app, "current_view_name"):
                            self.app.navigate_to(self.app.current_view_name)
                        msg = "📥 Dernière sauvegarde du Drive rapatriée et appliquée !"
                    else:
                        msg = "❌ Impossible de restaurer la sauvegarde Cloud."
                        is_err = True
                else:
                    msg = "Gestionnaire de données indisponible."
                    is_err = True
            except Exception as ex:
                msg = f"❌ Erreur de récupération Drive : {ex}"
                is_err = True
            finally:
                self._fermer_dlg(page_obj, loading_dlg)
                self._show_snackbar(msg, is_error=is_err)

        self._ouvrir_dlg(page_obj, loading_dlg)
        threading.Thread(target=worker, daemon=True).start()

    def reinitialiser_cache(self, e):
        page_obj = getattr(self.app, "page", None) or self.page
        if page_obj and hasattr(page_obj, "client_storage"):
            page_obj.client_storage.clear()
        self._show_snackbar("🧹 Cache local vidé avec succès.")

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
