# views/mails.py
import os
import smtplib
import sys
import threading
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import flet as ft

IS_ANDROID = "ANDROID_STORAGE" in os.environ or "ANDROID_ROOT" in os.environ or hasattr(sys, "getandroidapilevel")


def get_icon(name: str):
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()


class CustomTabs(ft.Column):
    def __init__(self, tabs_data, selected_index=0, accent_color="#1E3A8A"):
        super().__init__(expand=True, spacing=10)
        self.tabs_data = tabs_data
        self.selected_index = selected_index
        self.accent_color = accent_color

        self.buttons_row = ft.Row(spacing=5, scroll="auto")
        self.content_container = ft.Container(expand=True)

        self.controls = [self.buttons_row, self.content_container]
        self.render_tabs()

    def render_tabs(self):
        self.buttons_row.controls.clear()
        for idx, tab in enumerate(self.tabs_data):
            is_selected = (idx == self.selected_index)
            
            btn_widgets = []
            icon_val = tab.get("icon")
            if icon_val:
                icon_obj = get_icon(icon_val) if isinstance(icon_val, str) else icon_val
                btn_widgets.append(ft.Icon(icon_obj, size=16, color="white" if is_selected else "grey400"))
            
            btn_widgets.append(
                ft.Text(
                    tab.get("label", ""), 
                    size=12, 
                    weight="bold" if is_selected else "normal", 
                    color="white" if is_selected else "grey300"
                )
            )

            try:
                pad = ft.padding.only(left=12, top=8, right=12, bottom=8)
            except Exception:
                pad = 8

            btn = ft.Container(
                content=ft.Row(btn_widgets, spacing=6, alignment="center"),
                padding=pad,
                border_radius=8,
                bgcolor=self.accent_color if is_selected else "#111827",
                ink=True,
                on_click=lambda e, i=idx: self.select_tab(i)
            )
            self.buttons_row.controls.append(btn)

        if 0 <= self.selected_index < len(self.tabs_data):
            self.content_container.content = self.tabs_data[self.selected_index]["content"]

    def select_tab(self, index):
        self.selected_index = index
        self.render_tabs()
        try:
            if self.page:
                self.update()
        except Exception:
            pass


class MailsView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app
        self.accent_color = getattr(self.app, "association", {}).get("accent_color", "#1E3A8A")
        
        self.attachments = []
        if not IS_ANDROID:
            self.file_picker = ft.FilePicker()
            self.file_picker.on_result = self.on_attachment_picked
        else:
            self.file_picker = None

        self.progress_ring = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)
        self.btn_send = ft.ElevatedButton(
            "🚀 Envoyer l'email",
            icon=get_icon("SEND"),
            bgcolor=self.accent_color,
            color="white",
            height=48,
            on_click=self.envoyer_email
        )

        # --- COMPOSANTS DE COMPOSITION ---
        self.dd_destinataires = ft.Dropdown(
            label="Groupe de destinataires",
            options=[
                ft.dropdown.Option("TOUS", "Tous les membres & enseignants"),
                ft.dropdown.Option("MEMBRES", "Adhérents uniquement"),
                ft.dropdown.Option("SANS_CERTIF", "Adhérents sans certificat médical OK"),
                ft.dropdown.Option("SANS_LICENCE", "Adhérents sans licence prise"),
                ft.dropdown.Option("PROFESSEURS", "Enseignants / Professeurs"),
                ft.dropdown.Option("MANUEL", "Adresse spécifique (Saisie manuelle)"),
            ],
            value="TOUS",
            col={"sm": 12, "md": 6}
        )
        self.dd_destinataires.on_change = self.on_destinataires_change
        
        self.input_email_manuel = ft.TextField(
            label="Email destinataire unique",
            hint_text="exemple@domaine.com",
            visible=False,
            col={"sm": 12, "md": 6}
        )

        self.input_sujet = ft.TextField(
            label="Sujet de l'email",
            hint_text="Ex: Information importante - Stage de Karaté",
            col={"sm": 12}
        )
        
        self.input_corps = ft.TextField(
            label="Message / Contenu de l'email",
            multiline=True,
            min_lines=8,
            max_lines=15,
            expand=True,
            hint_text="Rédigez votre message ici..."
        )

        self.list_attachments = ft.Row(spacing=10, wrap=True)

        # --- COMPOSANTS CONFIGURATION SMTP (Synchronisés avec self.app.association) ---
        assoc = getattr(self.app, "association", {})
        self.input_smtp_host = ft.TextField(label="Serveur SMTP", value=assoc.get("smtp_server", "smtp.gmail.com"), col={"sm": 12, "md": 6})
        self.input_smtp_port = ft.TextField(label="Port SMTP", value=str(assoc.get("smtp_port", 587)), col={"sm": 6, "md": 3}, keyboard_type="number")
        self.check_smtp_tls = ft.Checkbox(label="Utiliser TLS / STARTTLS", value=assoc.get("smtp_use_tls", True))
        self.input_smtp_user = ft.TextField(label="Nom d'utilisateur / Email d'envoi", value=assoc.get("smtp_user", assoc.get("email", "")), col={"sm": 12, "md": 6})
        self.input_smtp_pass = ft.TextField(label="Mot de passe d'application", password=True, can_reveal_password=True, value=assoc.get("smtp_password", ""), col={"sm": 12, "md": 6})
        self.input_sender_name = ft.TextField(label="Nom d'expéditeur affiché", value=assoc.get("smtp_sender_name", assoc.get("nom", "Mon Club")), col={"sm": 12, "md": 6})

        # Table d'historique
        self.table_historique = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("Destinataires")),
                ft.DataColumn(ft.Text("Sujet")),
                ft.DataColumn(ft.Text("Statut")),
            ],
            rows=[]
        )

        self.content = self._build_main_view()

    def safe_update(self):
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def did_mount(self):
        if not IS_ANDROID:
            page_obj = getattr(self.app, "page", None) or self.page
            if page_obj and self.file_picker:
                try:
                    if self.file_picker not in page_obj.overlay:
                        page_obj.overlay.append(self.file_picker)
                except Exception:
                    pass
            self.safe_update()

    def will_unmount(self):
        if not IS_ANDROID:
            page_obj = getattr(self.app, "page", None) or self.page
            if page_obj and self.file_picker:
                try:
                    if self.file_picker in page_obj.overlay:
                        page_obj.overlay.remove(self.file_picker)
                except Exception:
                    pass

    def _build_main_view(self):
        return CustomTabs(
            tabs_data=[
                {"label": "Composition", "content": self._build_tab_composition(), "icon": "EMAIL"},
                {"label": "Modèles & Relances", "content": self._build_tab_modeles(), "icon": "AUTO_MODE"},
                {"label": "Historique d'envois", "content": self._build_tab_historique(), "icon": "HISTORY"},
                {"label": "Configuration SMTP", "content": self._build_tab_smtp(), "icon": "SETTINGS"},
            ],
            selected_index=0,
            accent_color=self.accent_color
        )

    def _build_tab_composition(self):
        return ft.Container(
            padding=15,
            content=ft.Column([
                ft.Text("✉️ Rédiger un e-mail groupé ou individuel", size=16, weight="bold"),
                ft.ResponsiveRow([
                    self.dd_destinataires,
                    self.input_email_manuel,
                ]),
                ft.ResponsiveRow([
                    self.input_sujet
                ]),
                self.input_corps,
                ft.Row([
                    ft.ElevatedButton(
                        "📎 Joindre un fichier",
                        icon=get_icon("ATTACH_FILE"),
                        on_click=self.joindre_fichier_click
                    ),
                    self.list_attachments
                ], wrap=True),
                ft.Divider(color="grey800"),
                ft.Row([
                    self.progress_ring,
                    self.btn_send
                ], alignment="end", vertical_alignment="center", spacing=10)
            ], spacing=12, scroll="auto")
        )

    def joindre_fichier_click(self, e):
        if IS_ANDROID:
            self._show_snackbar("La sélection directe de pièces jointes n'est pas activée sur cet APK Android.")
            return
        if self.file_picker:
            try:
                self.file_picker.pick_files(allow_multiple=True)
            except Exception as ex:
                self._show_snackbar(f"Sélecteur indisponible : {ex}", is_error=True)

    def _build_tab_modeles(self):
        return ft.Container(
            padding=15,
            content=ft.Column([
                ft.Text("⚡ Modèles de messages prédéfinis", size=16, weight="bold"),
                ft.Text("Cliquez sur un modèle pour pré-remplir automatiquement le sujet et le message.", size=12, italic=True, color="grey400"),
                ft.ResponsiveRow([
                    ft.Container(
                        col={"sm": 12, "md": 4},
                        padding=12,
                        bgcolor="#1e293b",
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("🏥 Relance Certificat Médical", weight="bold", size=14, color="#93C5FD"),
                            ft.Text("Rappelle aux membres qu'il manque leur certificat médical valide.", size=12, color="grey400"),
                            ft.ElevatedButton("Utiliser ce modèle", on_click=lambda e: self.charger_modele("CERTIF"))
                        ], spacing=8)
                    ),
                    ft.Container(
                        col={"sm": 12, "md": 4},
                        padding=12,
                        bgcolor="#1e293b",
                        border_radius=8,
                        content=ft.Column([
                            ft.Text(" Relance Licence ", weight="bold", size=14, color="#93C5FD"),
                            ft.Text("Rappelle aux membres de régulariser la prise de licence.", size=12, color="grey400"),
                            ft.ElevatedButton("Utiliser ce modèle", on_click=lambda e: self.charger_modele("LICENCE"))
                        ], spacing=8)
                    ),
                    ft.Container(
                        col={"sm": 12, "md": 4},
                        padding=12,
                        bgcolor="#1e293b",
                        border_radius=8,
                        content=ft.Column([
                            ft.Text("📢 Convocation AG", weight="bold", size=14, color="#93C5FD"),
                            ft.Text("Invitation formelle des membres à l'Assemblée Générale.", size=12, color="grey400"),
                            ft.ElevatedButton("Utiliser ce modèle", on_click=lambda e: self.charger_modele("AG"))
                        ], spacing=8)
                    ),
                ], spacing=10),
            ], spacing=15, scroll="auto")
        )

    def _build_tab_historique(self):
        self.charger_table_historique()
        return ft.Container(
            padding=15,
            content=ft.Column([
                ft.Text("📜 Historique des communications", size=16, weight="bold"),
                ft.Container(
                    padding=10,
                    bgcolor="#1e293b",
                    border_radius=8,
                    border=ft.Border(
                        top=ft.BorderSide(1, "grey800"),
                        right=ft.BorderSide(1, "grey800"),
                        bottom=ft.BorderSide(1, "grey800"),
                        left=ft.BorderSide(1, "grey800")
                    ),
                    content=ft.Row([self.table_historique], scroll="auto")
                )
            ], spacing=12, scroll="auto")
        )

    def _build_tab_smtp(self):
        try:
            pad_top = ft.padding.only(top=15)
        except Exception:
            pad_top = 10

        return ft.Container(
            padding=15,
            content=ft.Column([
                ft.Text("⚙️ Configuration du serveur de messagerie (SMTP)", size=16, weight="bold"),
                ft.Text("Configurez vos accès SMTP (ex: Gmail, Outlook, OVH) pour expédier vos e-mails.", size=12, italic=True, color="grey400"),
                ft.ResponsiveRow([
                    self.input_smtp_host,
                    self.input_smtp_port,
                ]),
                ft.ResponsiveRow([
                    self.input_smtp_user,
                    self.input_smtp_pass,
                ]),
                ft.ResponsiveRow([
                    self.input_sender_name,
                    ft.Container(content=self.check_smtp_tls, padding=pad_top, col={"sm": 12, "md": 6})
                ]),
                ft.Divider(color="grey800"),
                ft.Row([
                    ft.ElevatedButton(
                        "💾 Sauvegarder les paramètres SMTP",
                        icon=get_icon("SAVE"),
                        bgcolor=self.accent_color,
                        color="white",
                        on_click=self.sauvegarder_smtp
                    )
                ], alignment="end")
            ], spacing=12, scroll="auto")
        )

    def on_destinataires_change(self, e):
        self.input_email_manuel.visible = (self.dd_destinataires.value == "MANUEL")
        self.safe_update()

    def on_attachment_picked(self, e: ft.FilePickerResultEvent):
        if e.files:
            for f in e.files:
                if f.path:
                    p = Path(f.path)
                    if p not in self.attachments:
                        self.attachments.append(p)
            self.rafraichir_attachments_ui()

    def rafraichir_attachments_ui(self):
        self.list_attachments.controls.clear()
        for p in self.attachments:
            self.list_attachments.controls.append(
                ft.Chip(
                    label=ft.Text(p.name, size=11),
                    on_delete=lambda e, path=p: self.supprimer_attachment(path)
                )
            )
        self.safe_update()

    def supprimer_attachment(self, path: Path):
        if path in self.attachments:
            self.attachments.remove(path)
            self.rafraichir_attachments_ui()

    def charger_modele(self, type_modele):
        club_nom = getattr(self.app, "association", {}).get("nom", "Notre Club")
        if type_modele == "CERTIF":
            self.dd_destinataires.value = "SANS_CERTIF"
            self.input_sujet.value = f"[{club_nom}] Rappel : Certificat médical manquant"
            self.input_corps.value = (
                "Bonjour,\n\n"
                "Sauf erreur de notre part, nous n'avons pas encore reçu votre certificat médical "
                "(ou attestation de santé) valide pour la saison en cours.\n\n"
                "Merci de bien vouloir nous le transmettre dans les meilleurs délais afin de valider votre dossier.\n\n"
                "Sportivement,\n"
                f"L'équipe du {club_nom}"
            )
        elif type_modele == "LICENCE":
            self.dd_destinataires.value = "SANS_LICENCE"
            self.input_sujet.value = f"[{club_nom}] Rappel : Prise de licence "
            self.input_corps.value = (
                "Bonjour,\n\n"
                "Nous constatons que votre licence n'a pas encore été régularisée pour cette saison.\n\n"
                "Afin d'être duly couvert(e) par l'assurance lors des entraînements et des compétitions, merci d'effectuer les démarches nécessaires.\n\n"
                "Cordialement,\n"
                f"L'équipe du {club_nom}"
            )
        elif type_modele == "AG":
            self.dd_destinataires.value = "TOUS"
            self.input_sujet.value = f"[{club_nom}] Convocation à l'Assemblée Générale"
            self.input_corps.value = (
                "Chers adhérents, chers parents,\n\n"
                "Nous avons le plaisir de vous inviter à l'Assemblée Générale annuelle de notre association.\n\n"
                "Date : [À préciser]\n"
                "Lieu : [À préciser]\n"
                "Ordre du jour : Bilan moral, bilan financier et projets de la saison.\n\n"
                "Votre présence est importante pour le fonctionnement de notre club.\n\n"
                "Bien cordialement,\n"
                "Le Bureau"
            )
        self.input_email_manuel.visible = False
        self.safe_update()

    def collecter_emails_destinataires(self):
        emails = []
        choix = self.dd_destinataires.value

        if choix == "MANUEL":
            if self.input_email_manuel.value.strip():
                emails.append(self.input_email_manuel.value.strip())
            return emails

        membres = getattr(self.app, "membres", [])
        professeurs = getattr(self.app, "professeurs", [])

        if choix in ["TOUS", "MEMBRES", "SANS_CERTIF", "SANS_LICENCE"]:
            for m in membres:
                em = m.get("email", "").strip()
                if not em:
                    continue
                if choix == "TOUS" or choix == "MEMBRES":
                    emails.append(em)
                elif choix == "SANS_CERTIF" and not m.get("certificat_medical_valide"):
                    emails.append(em)
                elif choix == "SANS_LICENCE" and not m.get("licence_prise"):
                    emails.append(em)

        if choix in ["TOUS", "PROFESSEURS"]:
            for p in professeurs:
                em = p.get("email", "").strip()
                if em:
                    emails.append(em)

        return list(set(emails))

    def sauvegarder_smtp(self, e):
        assoc = self.app.association or {}
        assoc["smtp_server"] = self.input_smtp_host.value.strip()
        assoc["smtp_port"] = int(self.input_smtp_port.value.strip() or 587)
        assoc["smtp_use_tls"] = self.check_smtp_tls.value
        assoc["smtp_user"] = self.input_smtp_user.value.strip()
        assoc["smtp_password"] = self.input_smtp_pass.value
        assoc["smtp_sender_name"] = self.input_sender_name.value.strip()

        self.app.association = assoc
        if hasattr(self.app, "save_data"):
            self.app.save_data()
        self._show_snackbar("Paramètres SMTP enregistrés dans la configuration du club !")

    def envoyer_email(self, e):
        destinataires = self.collecter_emails_destinataires()
        if not destinataires:
            self._show_snackbar("Aucun destinataire trouvé ou adresse invalide.", is_error=True)
            return

        if not self.input_sujet.value.strip() or not self.input_corps.value.strip():
            self._show_snackbar("Veuillez renseigner le sujet et le message.", is_error=True)
            return

        assoc = getattr(self.app, "association", {})
        host = assoc.get("smtp_server")
        user = assoc.get("smtp_user", assoc.get("email", ""))
        pwd = assoc.get("smtp_password")

        if not host or not user or not pwd:
            self._show_snackbar("Configuration SMTP incomplète. Renseignez l'onglet Configuration SMTP.", is_error=True)
            return

        self.btn_send.disabled = True
        self.progress_ring.visible = True
        self.safe_update()

        threading.Thread(
            target=self._process_envoi_smtp,
            args=(destinataires, assoc),
            daemon=True
        ).start()

    def _process_envoi_smtp(self, destinataires, assoc):
        try:
            host = assoc.get("smtp_server")
            user = assoc.get("smtp_user", assoc.get("email", ""))
            pwd = assoc.get("smtp_password")
            port = int(assoc.get("smtp_port", 587))
            use_tls = assoc.get("smtp_use_tls", True)
            sender_name = assoc.get("smtp_sender_name", assoc.get("nom", "Mon Club"))

            server = smtplib.SMTP(host, port, timeout=12)
            if use_tls:
                server.starttls()
            server.login(user, pwd.replace(" ", ""))

            for dest in destinataires:
                msg = MIMEMultipart()
                msg["From"] = f"{sender_name} <{user}>"
                msg["To"] = dest
                msg["Subject"] = self.input_sujet.value

                msg.attach(MIMEText(self.input_corps.value, "plain", "utf-8"))

                for attach_path in self.attachments:
                    if attach_path.exists():
                        with open(attach_path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header("Content-Disposition", f'attachment; filename="{attach_path.name}"')
                        msg.attach(part)

                server.send_message(msg)

            server.quit()

            log_item = {
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "destinataires": f"{len(destinataires)} destinataire(s)",
                "sujet": self.input_sujet.value,
                "statut": "Envoyé avec succès"
            }
            if not hasattr(self.app, "mails_history") or self.app.mails_history is None:
                self.app.mails_history = []
            self.app.mails_history.append(log_item)
            if hasattr(self.app, "save_data"):
                self.app.save_data()

            self._show_snackbar(f"🎉 Email envoyé avec succès à {len(destinataires)} destinataire(s) !")
            self.attachments.clear()
            self.rafraichir_attachments_ui()
            self.input_sujet.value = ""
            self.input_corps.value = ""

        except Exception as ex:
            self._show_snackbar(f"Erreur d'envoi SMTP : {ex}", is_error=True)
        finally:
            self.btn_send.disabled = False
            self.progress_ring.visible = False
            self.safe_update()

    def charger_table_historique(self):
        self.table_historique.rows.clear()
        logs = getattr(self.app, "mails_history", []) or []
        for log in reversed(logs):
            self.table_historique.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(log.get("date", ""))),
                        ft.DataCell(ft.Text(log.get("destinataires", ""))),
                        ft.DataCell(ft.Text(log.get("sujet", ""))),
                        ft.DataCell(ft.Text(log.get("statut", ""), color="green400")),
                    ]
                )
            )

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
            self.safe_update()