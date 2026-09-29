# main.py
import os
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
import flet as ft

from database import DatabaseManager

# --- IMPORTS EXPLICITES POUR LA COMPILATION .EXE ---
from views.dashboard import DashboardView
from views.association import AssociationView
from views.membres import MembresView
from views.professeurs import ProfesseursView
from views.cotisations import CotisationsView
from views.evenements import EvenementsView
from views.materiel import MaterielView
from views.comptabilite import ComptabiliteView
from views.planning import PlanningView
from views.pdfviewer import PdfViewerView
from views.configuration import ConfigurationView
from views.mails import MailsView
from views.reunions import ReunionsView


def get_icon(name: str):
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()


def get_writable_data_dir() -> Path:
    if sys.platform in ["win32", "linux", "darwin"]:
        p = Path.cwd() / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p

    candidates = [
        os.environ.get("FILES_DIR"),
        os.environ.get("ANDROID_PRIVATE_DIR"),
        os.environ.get("TMPDIR"),
    ]
    
    home_env = os.environ.get("HOME")
    if home_env and home_env not in ["/", "/data"]:
        candidates.append(home_env)

    for candidate in candidates:
        if candidate and candidate not in ["/", "/data"]:
            try:
                p = Path(candidate) / "data"
                p.mkdir(parents=True, exist_ok=True)
                test_file = p / ".perm_check"
                test_file.write_text("ok")
                test_file.unlink()
                return p
            except Exception:
                continue

    p = Path(tempfile.gettempdir()) / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


class ClubSportifApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "F-Asso par Francky"
        self.page.theme_mode = "dark"
        self.page.padding = 0

        self.file_picker = ft.FilePicker()
        self.dir_picker = ft.FilePicker()
        self.page.overlay.append(self.file_picker)
        self.page.overlay.append(self.dir_picker)

        self.data_dir = get_writable_data_dir()
        self.db = DatabaseManager(self.data_dir)

        now = datetime.now()
        annee_courante = now.year if now.month >= 9 else now.year - 1
        self.saison_active = f"{annee_courante}-{annee_courante + 1}"
        self.current_view_name = "Dashboard"
        self.membre_selectionne = None
        self.active_dialog = None

        self.membres = []       
        self.cotisations = []   
        self.evenements = []    
        self.materiel = []      
        self.finances = []      
        self.planning_general = {}  
        self.professeurs = []      
        self.defraiements = []     
        self.association = {}
        self.mails_history = []
        self.reunions_docs = [] # <-- Initialisation de l'historique des réunions

        self.load_data()

        custom_dir = self.association.get("custom_data_dir")
        if custom_dir and Path(custom_dir).exists():
            self.data_dir = Path(custom_dir)
            self.db = DatabaseManager(self.data_dir)
            self.load_data()

        self.content_area = ft.Container(expand=True, padding=12)
        self.setup_layout()
        self.navigate_to("Dashboard")

    def detecter_credentials(self):
        candidats = [
            Path.cwd() / "credential.json",
            Path.cwd() / "credentials.json",
            self.data_dir / "credential.json",
            self.data_dir / "credentials.json",
        ]
        for p in candidats:
            if p.exists():
                return p
        return None

    def synchro_demarrage_drive(self):
        cred_path = self.detecter_credentials()
        if not cred_path:
            return

        dialog_demarrage = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.ProgressRing(width=20, height=20, stroke_width=2),
                ft.Text("Démarrage en cours...", weight="bold", size=16)
            ], spacing=12),
            content=ft.Text("Chargement et récupération de la dernière sauvegarde Google Drive. Veuillez patienter..."),
        )
        self.page.overlay.append(dialog_demarrage)
        dialog_demarrage.open = True
        self.page.update()

        try:
            self.restaurer_depuis_drive(cred_path)
            self.load_data()
            self.refresh_sidebar()
            self.navigate_to(self.current_view_name)
        except Exception as e:
            print("Erreur restauration Drive au démarrage :", e)
        finally:
            dialog_demarrage.open = False
            self.page.update()

    def restaurer_depuis_drive(self, cred_path: Path):
        if hasattr(self.db, "restaurer_drive"):
            self.db.restaurer_drive(cred_path)
            return

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload

            SCOPES = ['https://www.googleapis.com/auth/drive.file']
            token_path = cred_path.parent / "token.json"
            creds = None
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            service = build('drive', 'v3', credentials=creds)
            results = service.files().list(
                q="name contains 'f_asso_backup' and mimeType='application/zip' and trashed=false",
                orderBy="createdTime desc",
                pageSize=1,
                fields="files(id, name)"
            ).execute()
            items = results.get('files', [])

            if items:
                file_id = items[0]['id']
                request = service.files().get_media(fileId=file_id)
                temp_zip = Path(tempfile.gettempdir()) / "latest_drive_backup.zip"
                with open(temp_zip, "wb") as f:
                    downloader = MediaIoBaseDownload(f, request)
                    done = False
                    while not done:
                        _, done = downloader.next_chunk()

                with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                    zip_ref.extractall(self.data_dir)
                temp_zip.unlink(missing_ok=True)
        except Exception as e:
            print("Détail exception restaure Drive :", e)

    def sauvegarder_vers_drive(self, cred_path: Path):
        if hasattr(self.db, "sauvegarder_drive"):
            self.db.sauvegarder_drive(cred_path)
            return

        zip_path = None
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            SCOPES = ['https://www.googleapis.com/auth/drive.file']
            token_path = cred_path.parent / "token.json"
            creds = None
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            service = build('drive', 'v3', credentials=creds)

            zip_filename = f"f_asso_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = Path(tempfile.gettempdir()) / zip_filename

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(self.data_dir):
                    for file in files:
                        if not file.endswith('.zip') and not file.startswith('.'):
                            fp = Path(root) / file
                            arcname = fp.relative_to(self.data_dir)
                            zipf.write(fp, arcname)

            file_metadata = {'name': zip_filename, 'mimeType': 'application/zip'}
            media = MediaFileUpload(str(zip_path), mimetype='application/zip')
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()

            del media
        except Exception as e:
            print("Détail exception sauvegarde Drive :", e)
        finally:
            if zip_path and zip_path.exists():
                try:
                    zip_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def fermer_application(self, e=None):
        dialog_fermeture = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.ProgressRing(width=20, height=20, stroke_width=2),
                ft.Text("Fermeture appli en cours... veuillez patienter", weight="bold", size=15)
            ], spacing=12),
            content=ft.Text("Sauvegarde locale et envoi de la sauvegarde Google Drive en cours..."),
        )
        self.page.overlay.append(dialog_fermeture)
        dialog_fermeture.open = True
        self.page.update()

        try:
            self.save_data()
            cred_path = self.detecter_credentials()
            if cred_path:
                self.sauvegarder_vers_drive(cred_path)
            time.sleep(0.5)
        except Exception as ex:
            print("Erreur pendant la fermeture :", ex)
        finally:
            dialog_fermeture.open = False
            self.page.update()

            if hasattr(self.page, "window_close"):
                self.page.window_close()
            elif hasattr(self.page, "window_destroy"):
                self.page.window_destroy()
            elif hasattr(self.page, "window") and hasattr(self.page.window, "close"):
                self.page.window.close()
            else:
                os._exit(0)

    def load_data(self):
        try:
            self.association = self.db.charger_club_config()
            self.finances = self.db.charger_finances_annee(self.saison_active)
            self.evenements = self.db.charger_global_fichier(self.saison_active, "evenements", [])
            self.materiel = self.db.charger_global_fichier(self.saison_active, "materiel", [])
            self.planning_general = self.db.charger_global_fichier(self.saison_active, "planning_general", {})
            self.defraiements = self.db.charger_global_fichier(self.saison_active, "defraiements", [])
            self.mails_history = self.db.charger_global_fichier(self.saison_active, "mails_history", [])
            self.reunions_docs = self.db.charger_global_fichier(self.saison_active, "reunions_docs", []) # <-- Chargement persistant
            self.membres, self.cotisations = self.db.charger_tous_les_adherents(self.saison_active)
            self.professeurs = self.db.charger_tous_les_professeurs()
        except Exception as e:
            print("Erreur globale lors du chargement :", e)

    def save_data(self):
        try:
            self.db.sauvegarder_club_config(self.association)
            self.db.sauvegarder_finances_annee(self.saison_active, self.finances)
            self.db.sauvegarder_global_fichier(self.saison_active, "evenements", self.evenements)
            self.db.sauvegarder_global_fichier(self.saison_active, "materiel", self.materiel)
            self.db.sauvegarder_global_fichier(self.saison_active, "planning_general", self.planning_general)
            self.db.sauvegarder_global_fichier(self.saison_active, "defraiements", self.defraiements)
            self.db.sauvegarder_global_fichier(self.saison_active, "mails_history", self.mails_history)
            self.db.sauvegarder_global_fichier(self.saison_active, "reunions_docs", self.reunions_docs) # <-- Sauvegarde persistante

            for membre in self.membres:
                self.db.sauvegarder_adherent(membre)
                nom_prenom = f"{membre.get('nom', '').strip()} {membre.get('prenom', '').strip()}".strip()
                cotis_perso = [c for c in self.cotisations if c.get("membre") == nom_prenom]
                self.db.sauvegarder_cotisation_adherent(
                    nom=membre.get("nom", "Inconnu"),
                    prenom=membre.get("prenom", "Inconnu"),
                    annee=self.saison_active,
                    cotis_data=cotis_perso
                )
                
            for prof in self.professeurs:
                self.db.sauvegarder_professeur(prof)
        except Exception as e:
            print("Erreur globale lors de la sauvegarde :", e)

    def changer_saison(self, e):
        nouvelle_saison = e.control.value if e and hasattr(e, "control") and e.control else self.dropdown_saison.value
        if nouvelle_saison:
            self.saison_active = nouvelle_saison
            self.dropdown_saison.value = self.saison_active
            self.load_data()
            self.refresh_sidebar()
            self.navigate_to(self.current_view_name)

    def get_menu_items(self):
        return [
            ("📊 Tableau de Bord", "Dashboard"),
            ("🏛️ Association", "Association"),
            ("👥 Adhérents & Licences", "Membres"),
            ("🎓 Enseignants", "Professeurs"),
            ("💰 Cotisations & Caisses", "Cotisations"),
            ("📅 Événements", "Evenements"),
            ("🎒 Inventaire Matériel", "Materiel"),
            ("📈 Compta / Budget", "Comptabilite"),
            ("📅 Planning Général", "Planning"),
            ("📄 Visionneuse PDF", "PdfViewer"),
            ("✉️ Messagerie & Mails", "Mails"),
            ("📋 Réunions & AG", "Reunions"),
            ("⚙️ Configuration Club", "Configuration"),
        ]

    def open_mobile_menu(self, e=None):
        def on_item_click(v_name):
            self.close_active_dialog()
            self.navigate_to(v_name)

        mobile_saison_dropdown = ft.Dropdown(
            label="Saison d'activité",
            width=260,
            options=self.dropdown_saison.options,
            value=self.saison_active,
        )
        mobile_saison_dropdown.on_change = lambda evt: (self.close_active_dialog(), self.changer_saison(evt))

        menu_controls = [mobile_saison_dropdown, ft.Divider()]
        for texte, vue in self.get_menu_items():
            menu_controls.append(
                ft.ListTile(
                    title=ft.Text(texte, weight="bold", size=14),
                    on_click=lambda e, v=vue: on_item_click(v)
                )
            )

        self.active_dialog = ft.AlertDialog(
            title=ft.Text("📍 Navigation F-ASSO"),
            content=ft.Container(
                content=ft.Column(controls=menu_controls, tight=True, scroll="auto"),
                width=300,
                height=480
            ),
            actions=[
                ft.TextButton("Fermer", on_click=lambda e: self.close_active_dialog())
            ]
        )

        self.page.overlay.append(self.active_dialog)
        self.active_dialog.open = True
        self.page.update()

    def close_active_dialog(self):
        if self.active_dialog:
            self.active_dialog.open = False
            self.active_dialog = None
            self.page.update()

    def setup_layout(self):
        path_logo = self.association.get("logo_path", "")
        self.sidebar_logo = ft.Image(
            src=path_logo,
            width=90,
            height=90,
            fit="contain",
            visible=bool(path_logo)
        )

        self.sidebar_titre = ft.Text(
            self.association.get("nom", "F-ASSO").upper(),
            size=16,
            weight="bold",
            text_align="center",
        )

        options_saisons = [
            ft.dropdown.Option(key=f"{year}-{year + 1}", text=f"Saison {year}-{year + 1}")
            for year in range(2015, 2041)
        ]

        self.dropdown_saison = ft.Dropdown(
            label="Saison d'activité",
            width=210,
            options=options_saisons,
            value=self.saison_active,
        )
        self.dropdown_saison.on_change = self.changer_saison

        self.desktop_menu_column = ft.Column(
            spacing=6,
            horizontal_alignment="center",
            scroll="auto",
            expand=True,
        )

        self.build_desktop_menu()

        self.sidebar_container = ft.Container(
            width=240,
            bgcolor="#111827",
            padding=10,
            content=ft.Column(
                controls=[
                    self.sidebar_logo,
                    self.sidebar_titre,
                    self.dropdown_saison,
                    ft.Divider(color="#374151"),
                    self.desktop_menu_column,
                ],
                spacing=10,
                horizontal_alignment="center",
                expand=True,
            )
        )

        self.top_app_bar = ft.Container(
            padding=8,
            bgcolor="#111827",
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=get_icon("MENU"),
                        on_click=self.open_mobile_menu
                    ),
                    ft.Text(self.association.get("nom", "F-ASSO"), size=18, weight="bold"),
                ]
            ),
            visible=False
        )

        self.main_layout = ft.Row(
            controls=[self.sidebar_container, self.content_area],
            expand=True,
            spacing=0,
        )

        self.page.add(
            ft.Column(
                controls=[self.top_app_bar, self.main_layout],
                expand=True,
                spacing=0
            )
        )

        def update_responsive(e=None):
            is_mobile = (self.page.width or 0) < 700
            if is_mobile:
                self.sidebar_container.visible = False
                self.top_app_bar.visible = True
            else:
                self.sidebar_container.visible = True
                self.top_app_bar.visible = False
            self.page.update()

        self.page.on_resized = update_responsive
        update_responsive()

    def build_desktop_menu(self):
        accent = self.association.get("accent_color", "#1E3A8A")
        buttons = []
        for texte, vue in self.get_menu_items():
            btn = ft.ElevatedButton(
                content=ft.Text(texte, color="white", size=13),
                width=210,
                height=38,
                bgcolor=accent,
                on_click=lambda e, v=vue: self.navigate_to(v)
            )
            buttons.append(btn)
        self.desktop_menu_column.controls = buttons

    def refresh_sidebar(self):
        path_logo = self.association.get("logo_path", "")
        self.sidebar_logo.src = path_logo
        self.sidebar_logo.visible = bool(path_logo)
        self.sidebar_titre.value = self.association.get("nom", "F-ASSO").upper()
        self.dropdown_saison.value = self.saison_active
        
        self.build_desktop_menu()
        self.page.update()

    def navigate_to(self, view_name, **kwargs):
        if "membre" in kwargs:
            self.membre_selectionne = kwargs["membre"]

        self.current_view_name = view_name

        try:
            if view_name == "Dashboard":
                self.content_area.content = DashboardView(self)
            elif view_name == "Association":
                self.content_area.content = AssociationView(self)
            elif view_name == "Membres":
                self.content_area.content = MembresView(self)
            elif view_name == "Professeurs":
                self.content_area.content = ProfesseursView(self)
            elif view_name == "Cotisations":
                self.content_area.content = CotisationsView(self)
            elif view_name == "Evenements":
                self.content_area.content = EvenementsView(self)
            elif view_name == "Materiel":
                self.content_area.content = MaterielView(self)
            elif view_name == "Comptabilite":
                self.content_area.content = ComptabiliteView(self)
            elif view_name == "Planning": 
                self.content_area.content = PlanningView(self)
            elif view_name == "PdfViewer":
                try:
                    self.content_area.content = PdfViewerView(self, **kwargs)
                except TypeError:
                    self.content_area.content = PdfViewerView(self)
            elif view_name == "Configuration":
                self.content_area.content = ConfigurationView(self)
            elif view_name == "Mails":
                self.content_area.content = MailsView(self)
            elif view_name == "Reunions":                              
                self.content_area.content = ReunionsView(self)
            else:
                self.content_area.content = ft.Text(f"Vue {view_name} en développement...", color="white")
        
        except Exception as e:
            self.content_area.content = ft.Container(
                content=ft.Column([
                    ft.Icon(get_icon("ERROR"), color="red", size=40),
                    ft.Text(f"Erreur dans le module {view_name} :", size=16, weight="bold", color="white"),
                    ft.Text(str(e), color="red400", selectable=True)
                ], horizontal_alignment="center")
            )
        
        self.page.update()


def main(page: ft.Page):
    ClubSportifApp(page)

if __name__ == "__main__":
    ft.app(target=main)