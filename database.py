import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path
import requests

# --- GESTION DES CHEMINS D'EXÉCUTION (.py / .exe PyInstaller) ---
def get_base_dir() -> Path:
    """Retourne le répertoire racine de l'application (dossier de l'exécutable ou du script)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path.cwd()


class DatabaseManager:
    def __init__(self, root_dir: Path | str = None, *args, **kwargs):
        base = get_base_dir()
        if root_dir is None:
            self.root_dir = base / "data"
        else:
            self.root_dir = Path(root_dir)

        self.asso_root = self.root_dir / "asso"
        self.adherents_root = self.root_dir / "adherents"
        self.professeurs_root = self.root_dir / "professeurs"
        self.exports_root = self.root_dir / "exports"
        self.global_config_path = self.root_dir / "config_club.json"

        # Le dossier backups suit le dossier de données actif
        self.backups_dir = self.root_dir / "backups"
        
        self.credentials_file = base / "credentials.json"
        self.token_file = base / "token.json"

        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.asso_root.mkdir(parents=True, exist_ok=True)
        self.adherents_root.mkdir(parents=True, exist_ok=True)
        self.professeurs_root.mkdir(parents=True, exist_ok=True)
        self.exports_root.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self.HAS_GOOGLE_DRIVE = True

    def _get_safe_folder_name(self, nom: str, prenom: str) -> str:
        full_name = f"{nom.strip()}_{prenom.strip()}".lower()
        full_name = re.sub(r'[éèêë]', 'e', full_name)
        full_name = re.sub(r'[àâä]', 'a', full_name)
        full_name = re.sub(r'[ôö]', 'o', full_name)
        full_name = re.sub(r'[ûü]', 'u', full_name)
        full_name = re.sub(r'[ç]', 'c', full_name)
        return re.sub(r'[^a-z0-9_]', '', full_name.replace(" ", "_"))

    # --- GESTION DES DOSSIERS DE DOCUMENTS, JUSTIFICATIFS ET EXPORTS ---

    def get_prof_justificatifs_dir(self, nom: str, prenom: str, annee: str = None) -> Path:
        """Retourne le dossier des justificatifs de frais d'un professeur pour une saison."""
        if not annee:
            annee = self.get_annee_active()
        folder_name = self._get_safe_folder_name(nom, prenom)
        dest_dir = self.professeurs_root / folder_name / str(annee) / "justificatifs_frais"
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir

    def get_adherent_documents_dir(self, nom: str, prenom: str, annee: str = None) -> Path:
        """Retourne le dossier des documents/justificatifs d'un adhérent pour une saison."""
        if not annee:
            annee = self.get_annee_active()
        folder_name = self._get_safe_folder_name(nom, prenom)
        dest_dir = self.adherents_root / folder_name / str(annee) / "documents"
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir

    def get_documents_saison_dir(self, annee: str = None) -> Path:
        """Retourne le dossier des documents généraux d'une saison."""
        if not annee:
            annee = self.get_annee_active()
        dest_dir = self.asso_root / str(annee) / "documents"
        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir

    def get_exports_saison_dir(self, annee: str = None, famille: str = None) -> Path:
        """
        Retourne le dossier des exports à la racine (data/exports/<saison>/[famille]).
        Familles possibles : 'adherents', 'compta', 'professeurs', 'reunions', 'evenements', etc.
        """
        if not annee:
            annee = self.get_annee_active()
        
        dest_dir = self.exports_root / str(annee)
        if famille:
            dest_dir = dest_dir / famille.lower().strip()

        dest_dir.mkdir(parents=True, exist_ok=True)
        return dest_dir

    # --- GESTION DYNAMIQUE DES SAISONS ---

    def get_annee_active(self, *args, **kwargs) -> str:
        """Retourne l'année/saison active configurée."""
        config = self.charger_club_config()
        if config.get("annee_active"):
            return str(config["annee_active"])
        now = datetime.now()
        return str(now.year if now.month >= 8 else now.year - 1)

    def changer_saison(self, nouvelle_saison: str, *args, **kwargs) -> bool:
        """Met à jour et enregistre la saison active dans config_club.json."""
        config = self.charger_club_config()
        config["annee_active"] = str(nouvelle_saison)
        self.sauvegarder_club_config(config)
        return True

    def lister_saisons_disponibles(self, *args, **kwargs) -> list:
        """Scanne l'arborescence pour recenser toutes les saisons existantes."""
        saisons = set()
        
        # Scan asso
        if self.asso_root.exists():
            for f in self.asso_root.iterdir():
                if f.is_dir() and not f.name.startswith('.'):
                    saisons.add(f.name)
                    
        # Scan adhérents
        if self.adherents_root.exists():
            for m_folder in self.adherents_root.iterdir():
                if m_folder.is_dir():
                    for s_folder in m_folder.iterdir():
                        if s_folder.is_dir() and not s_folder.name.startswith('.'):
                            saisons.add(s_folder.name)

        # Scan professeurs
        if self.professeurs_root.exists():
            for p_folder in self.professeurs_root.iterdir():
                if p_folder.is_dir():
                    for s_folder in p_folder.iterdir():
                        if s_folder.is_dir() and not s_folder.name.startswith('.'):
                            saisons.add(s_folder.name)

        # Scan exports
        if self.exports_root.exists():
            for f in self.exports_root.iterdir():
                if f.is_dir() and not f.name.startswith('.'):
                    saisons.add(f.name)

        if not saisons:
            saisons.add(self.get_annee_active())
            
        return sorted(list(saisons), reverse=True)

    # --- CORE BUSINESS LOGIC ---

    def charger_club_config(self, *args, **kwargs) -> dict:
        default_config = {
            "nom": "F-ASSO",
            "sigle": "",
            "rna": "W123456789",
            "siret": "",
            "affiliation": "",
            "adresse_siege": "",
            "adresse_dojo": "",
            "email": "",
            "president": "",
            "tresorier": "",
            "secretaire": "",
            "prof": "",
            "banque": "",
            "iban": "",
            "bic": "",
            "accent_color": "#1E3A8A",
            "logo_path": "",
            "signature_path": "",
            "tampon_path": "",
            "annee_active": "",
        }
        if self.global_config_path.exists():
            try:
                with open(self.global_config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        default_config.update(loaded)
            except Exception as e:
                print("Erreur de lecture de config_club.json :", e)
        return default_config

    def sauvegarder_club_config(self, config_data: dict, *args, **kwargs):
        try:
            with open(self.global_config_path, "w", encoding="utf-8") as f:
                json.dump(self._sanitize_for_json(config_data), f, indent=4, ensure_ascii=False)
        except Exception as e:
            print("Erreur d'écriture de config_club.json :", e)

    def _sanitize_for_json(self, obj):
        if isinstance(obj, dict):
            return {str(k): self._sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [self._sanitize_for_json(i) for i in obj]
        if isinstance(obj, (Path, datetime)):
            return str(obj)
        return obj

    def sauvegarder_adherent(self, adherent_data: dict, *args, **kwargs):
        nom = adherent_data.get("nom", "Inconnu")
        prenom = adherent_data.get("prenom", "Inconnu")
        folder_name = self._get_safe_folder_name(nom, prenom)
        adherent_dir = self.adherents_root / folder_name
        adherent_dir.mkdir(parents=True, exist_ok=True)
        file_path = adherent_dir / "fiche_adherent.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._sanitize_for_json(adherent_data), f, indent=4, ensure_ascii=False)

    def sauvegarder_cotisation_adherent(self, nom: str, prenom: str, annee: str = None, cotis_data: list = None, *args, **kwargs):
        if cotis_data is None:
            cotis_data = []
        if not annee:
            annee = self.get_annee_active()
        folder_name = self._get_safe_folder_name(nom, prenom)
        year_dir = self.adherents_root / folder_name / str(annee)
        year_dir.mkdir(parents=True, exist_ok=True)
        file_path = year_dir / "cotisation.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._sanitize_for_json(cotis_data), f, indent=4, ensure_ascii=False)

    def charger_tous_les_adherents(self, annee_active: str = None, *args, **kwargs) -> tuple:
        if not annee_active:
            annee_active = self.get_annee_active()

        adherents = []
        cotisations = []
        if not self.adherents_root.exists():
            return adherents, cotisations

        for folder in self.adherents_root.iterdir():
            if folder.is_dir():
                fiche_path = folder / "fiche_adherent.json"
                season_dir = folder / str(annee_active)
                
                # RESTRICTION PAR SAISON ACTIVE : L'adhérent doit exister ET avoir un dossier pour cette saison
                if fiche_path.exists() and season_dir.exists():
                    try:
                        with open(fiche_path, "r", encoding="utf-8") as f:
                            adherent_info = json.load(f)
                            adherents.append(adherent_info)
                            
                            cotis_path = season_dir / "cotisation.json"
                            if cotis_path.exists():
                                with open(cotis_path, "r", encoding="utf-8") as cf:
                                    user_cotis = json.load(cf)
                                    for c in user_cotis:
                                        c["membre"] = f"{adherent_info.get('nom', '')} {adherent_info.get('prenom', '')}".strip()
                                    cotisations.extend(user_cotis)
                    except Exception as e:
                        print(f"Erreur de chargement {folder.name} : {e}")
        return adherents, cotisations

    def sauvegarder_professeur(self, prof_data: dict, *args, **kwargs):
        nom = prof_data.get("nom", "Inconnu")
        prenom = prof_data.get("prenom", "Inconnu")
        folder_name = self._get_safe_folder_name(nom, prenom)
        prof_dir = self.professeurs_root / folder_name
        prof_dir.mkdir(parents=True, exist_ok=True)
        file_path = prof_dir / "fiche_professeur.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._sanitize_for_json(prof_data), f, indent=4, ensure_ascii=False)

    def charger_tous_les_professeurs(self, *args, **kwargs) -> list:
        professeurs = []
        if not self.professeurs_root.exists():
            return professeurs

        for folder in self.professeurs_root.iterdir():
            if folder.is_dir():
                fiche_path = folder / "fiche_professeur.json"
                if fiche_path.exists():
                    try:
                        with open(fiche_path, "r", encoding="utf-8") as f:
                            professeurs.append(json.load(f))
                    except Exception as e:
                        print(f"Erreur professeur {folder.name} : {e}")
        return professeurs

    def charger_finances_annee(self, annee: str = None, *args, **kwargs) -> list:
        if not annee:
            annee = self.get_annee_active()
        year_dir = self.asso_root / str(annee)
        finances = []
        if year_dir.exists():
            finances_file = year_dir / "finances.json"
            if finances_file.exists():
                try:
                    with open(finances_file, "r", encoding="utf-8") as f:
                        finances = json.load(f)
                except Exception as e:
                    print("Erreur de lecture finances.json :", e)
        return finances

    def sauvegarder_finances_annee(self, annee: str = None, finances: list = None, *args, **kwargs):
        if finances is None:
            finances = []
        if not annee:
            annee = self.get_annee_active()
        year_dir = self.asso_root / str(annee)
        year_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(year_dir / "finances.json", "w", encoding="utf-8") as f:
                json.dump(self._sanitize_for_json(finances), f, indent=4, ensure_ascii=False)
        except Exception as e:
            print("Erreur écriture finances.json :", e)

    def charger_global_fichier(self, annee: str = None, nom_fichier: str = "", default_value=None, *args, **kwargs):
        if default_value is None:
            default_value = []
        if not annee:
            annee = self.get_annee_active()
        year_dir = self.asso_root / str(annee)
        file_path = year_dir / f"{nom_fichier}.json"
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erreur lecture {nom_fichier}.json : {e}")
        return default_value

    def sauvegarder_global_fichier(self, annee: str = None, nom_fichier: str = "", data=None, *args, **kwargs):
        if not annee:
            annee = self.get_annee_active()
        year_dir = self.asso_root / str(annee)
        year_dir.mkdir(parents=True, exist_ok=True)
        file_path = year_dir / f"{nom_fichier}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self._sanitize_for_json(data), f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur écriture {nom_fichier}.json :", e)

    # --- MÉTHODES D'INTERFACAGE GRAPHIQUE ---

    def load_data(self, *args, **kwargs) -> dict:
        return {
            "association": self.charger_club_config(),
            "membres": self.get_membres(),
            "finances": self.charger_finances_annee()
        }

    def save_data(self, data: dict = None, *args, **kwargs) -> bool:
        if isinstance(data, dict):
            if "association" in data:
                self.sauvegarder_club_config(data["association"])
            return True
        return False

    def get_membres(self, annee_active: str = None, *args, **kwargs) -> list:
        adherents, _ = self.charger_tous_les_adherents(annee_active=annee_active)
        return adherents

    def charger_membres(self, annee_active: str = None, *args, **kwargs) -> list:
        return self.get_membres(annee_active=annee_active, *args, **kwargs)

    def charger_historique(self, *args, **kwargs) -> list:
        return []

    def charger_transactions(self, *args, **kwargs) -> list:
        return []

    def charger_cotisations(self, *args, **kwargs) -> list:
        _, cotis = self.charger_tous_les_adherents()
        return cotis

    # --- SAUVEGARDES LOCALES ---

    def create_local_backup(self, *args, **kwargs) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_club_{timestamp}.zip"
        backup_path = self.backups_dir / backup_filename

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.root_dir):
                # Empêche os.walk de descendre dans le dossier backups
                if self.backups_dir.name in dirs:
                    dirs.remove(self.backups_dir.name)

                for file in files:
                    file_path = Path(root) / file
                    if file_path.resolve() == backup_path.resolve():
                        continue
                    try:
                        arcname = file_path.relative_to(self.root_dir)
                        zipf.write(file_path, arcname)
                    except Exception as e:
                        print(f"Erreur ajout fichier backup {file_path} : {e}")

        return str(backup_path)

    def restore_local_backup(self, zip_filepath: str, *args, **kwargs) -> bool:
        try:
            zip_path = Path(zip_filepath)
            if not zip_path.exists():
                return False

            current_config = self.charger_club_config()
            local_visuals = {
                "logo_path": current_config.get("logo_path", ""),
                "signature_path": current_config.get("signature_path", ""),
                "tampon_path": current_config.get("tampon_path", "")
            }

            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(self.root_dir)

            restored_config = self.charger_club_config()
            for key, val in local_visuals.items():
                if val:
                    restored_config[key] = val
            self.sauvegarder_club_config(restored_config)

            return True
        except Exception as e:
            print(f"Erreur lors de la restauration : {e}")
            return False

    # --- GOOGLE DRIVE (API REST VIA REQUESTS) ---

    def _get_headers(self) -> dict:
        if not self.token_file.exists():
            return {}
        try:
            with open(self.token_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token')
            client_id = token_data.get('client_id')
            client_secret = token_data.get('client_secret')

            if refresh_token and client_id and client_secret:
                response = requests.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token"
                    },
                    timeout=15
                )
                if response.status_code == 200:
                    new_data = response.json()
                    access_token = new_data.get("access_token", access_token)
                    token_data["access_token"] = access_token
                    with open(self.token_file, 'w', encoding='utf-8') as tf:
                        json.dump(token_data, tf, indent=4)
        except Exception as e:
            print(f"Erreur de gestion du token Drive : {e}")

        return {"Authorization": f"Bearer {access_token}"}

    def sync_with_drive(self, *args, **kwargs) -> bool:
        try:
            backup_path = self.create_local_backup()
            folder_id = kwargs.get('folder_id', None)
            self.upload_to_drive(backup_path, folder_id=folder_id)
            return True
        except Exception as e:
            print(f"Erreur de synchronisation Drive : {e}")
            return False

    def delete_from_drive(self, file_id: str) -> bool:
        """Supprime un fichier spécifique du Drive."""
        try:
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            response = requests.delete(url, headers=self._get_headers(), timeout=15)
            return response.status_code in (204, 200)
        except Exception as e:
            print(f"Erreur de suppression Drive : {e}")
            return False

    def list_drive_backups(self, folder_id: str = None, *args, **kwargs) -> list:
        query = "mimeType = 'application/zip' and trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        url = f"https://www.googleapis.com/drive/v3/files?q={query}&orderBy=createdTime desc&pageSize=50&fields=files(id,name,createdTime,size)"
        response = requests.get(url, headers=self._get_headers(), timeout=15)
        return response.json().get('files', [])

    def _cleanup_old_drive_backups(self, folder_id: str = None, max_count: int = 12):
        """Nettoie le Drive pour ne conserver que les 12 sauvegardes les plus récentes."""
        try:
            files = self.list_drive_backups(folder_id=folder_id)
            if len(files) > max_count:
                files_to_delete = files[max_count:]
                for f in files_to_delete:
                    print(f"Suppression de l'ancienne sauvegarde Drive : {f.get('name')}")
                    self.delete_from_drive(f['id'])
        except Exception as e:
            print(f"Erreur lors du nettoyage des anciennes sauvegardes Drive : {e}")

    def upload_to_drive(self, local_zip_path: str, folder_id: str = None, *args, **kwargs) -> dict:
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
        file_name = Path(local_zip_path).name

        metadata = {'name': file_name, 'description': 'Sauvegarde automatique Club App'}
        if folder_id:
            metadata['parents'] = [folder_id]

        files = {
            'data': ('metadata', json.dumps(metadata), 'application/json'),
            'file': (file_name, open(local_zip_path, 'rb'), 'application/zip')
        }
        
        response = requests.post(url, headers=self._get_headers(), files=files, timeout=60)
        res_data = response.json()

        if response.status_code in (200, 201):
            self._cleanup_old_drive_backups(folder_id=folder_id, max_count=12)

        return res_data

    def download_from_drive(self, file_id: str, destination_path: str, *args, **kwargs) -> bool:
        try:
            url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
            response = requests.get(url, headers=self._get_headers(), stream=True, timeout=60)
            if response.status_code == 200:
                with open(destination_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            return False
        except Exception as e:
            print(f"Erreur de téléchargement Drive : {e}")
            return False

    def get_latest_drive_backup(self, folder_id: str = None, *args, **kwargs) -> dict:
        query = "mimeType = 'application/zip' and trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        url = f"https://www.googleapis.com/drive/v3/files?q={query}&orderBy=createdTime desc&pageSize=1&fields=files(id,name,createdTime,size)"
        response = requests.get(url, headers=self._get_headers(), timeout=15)
        files = response.json().get('files', [])
        return files[0] if files else None

    def restore_from_drive_latest(self, folder_id: str = None, *args, **kwargs) -> bool:
        try:
            latest_file = self.get_latest_drive_backup(folder_id=folder_id)
            if not latest_file:
                raise FileNotFoundError("Aucune sauvegarde ZIP trouvée dans le dossier Google Drive.")

            file_id = latest_file['id']
            temp_zip_path = self.backups_dir / "latest_cloud_backup.zip"

            if self.download_from_drive(file_id, str(temp_zip_path)):
                success = self.restore_local_backup(str(temp_zip_path))
                if temp_zip_path.exists():
                    temp_zip_path.unlink()
                return success
            return False
        except Exception as e:
            print(f"Erreur de restauration Drive : {e}")
            return False