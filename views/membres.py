# views/membres.py
import os
import sys
import webbrowser
from datetime import datetime
import flet as ft

IS_ANDROID = "ANDROID_STORAGE" in os.environ or "ANDROID_ROOT" in os.environ or hasattr(sys, "getandroidapilevel")


def get_icon_safe(name: str):
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()


class MembresView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app
        self.accent_color = getattr(self.app, "association", {}).get("accent_color", "#1E3A8A")
        
        self.current_editing_index = None

        # --- INITIALISATION DU FILEPICKER (PHOTO) ---
        self.file_picker = ft.FilePicker(on_result=self.on_photo_picked)

        # --- COMPOSANTS DU FORMULAIRE ---
        self.input_nom = ft.TextField(label="Nom", expand=True)
        self.input_prenom = ft.TextField(label="Prénom", expand=True)
        self.dropdown_sexe = ft.Dropdown(
            label="Sexe",
            expand=True,
            options=[
                ft.dropdown.Option("H", "Homme"),
                ft.dropdown.Option("F", "Femme"),
            ]
        )
        self.input_date_naissance = ft.TextField(label="Né(e) le (JJ/MM/AAAA)", expand=True, hint_text="Ex: 14/02/2010")
        self.input_photo = ft.TextField(label="Photo", expand=True, read_only=True, hint_text="Aucune photo sélectionnée")
        
        self.input_email = ft.TextField(label="Adresse Email", expand=True, keyboard_type="email")
        self.input_telephone = ft.TextField(label="N° Téléphone", expand=True, keyboard_type="phone")
        
        self.input_rue = ft.TextField(label="Rue / Avenue / Boulevard", expand=True)
        self.input_cp = ft.TextField(label="Code Postal", expand=True, keyboard_type="number")
        self.input_ville = ft.TextField(label="Ville", expand=True)
        
        self.input_responsable = ft.TextField(label="Responsable Légal (Si mineur)", expand=True, hint_text="Nom, Prénom + Lien (Ex: Père)")
        self.check_medical = ft.Checkbox(label="Certificat Médical OK / Fourni", value=False)
        self.check_accord_soins = ft.Checkbox(label="Accord parental soins urgences", value=False)
        self.input_allergies = ft.TextField(label="Allergies / Contre-indications", expand=True, hint_text="Ex: Asthme... (Laisser vide si RAS)")
        self.input_fiche_medecin = ft.TextField(label="Notes du médecin / Suivi", multiline=True, min_lines=2, max_lines=4, expand=True)

        self.input_licence = ft.TextField(label="N° Licence", expand=True)
        self.check_licence_prise = ft.Checkbox(label="Licence prise", value=False)
        
        # --- DROPDOWN NIVEAU GÉNÉRIQUE ET COMPLET ---
        self.dropdown_niveau = ft.Dropdown(
            label="Niveau / Grade / Catégorie",
            expand=True,
            options=self.generer_options_niveaux(),
            value="Débutant"
        )
        
        self.input_historique_licences = ft.TextField(
            label="Historique des saisons passées", 
            multiline=True, 
            min_lines=2, 
            max_lines=4, 
            expand=True,
            hint_text="Ex: 2023/2024: Club de Lyon..."
        )

        self.input_tarif_custom = ft.TextField(
            label="Cotisation due (€) [Sur-mesure]", 
            expand=True, 
            keyboard_type="number",
            hint_text="Vide = Calcul auto selon l'âge"
        )

        # --- COMPOSANTS DE L'ÉCRAN LISTE ---
        self.input_recherche = ft.TextField(
            label="Rechercher un adhérent...",
            prefix_icon=get_icon_safe("SEARCH"),
            expand=True,
            on_change=self.filtrer_membres
        )

        self.dropdown_filtre_cotis = ft.Dropdown(
            label="Filtrer par Cotisation",
            expand=True,
            options=[
                ft.dropdown.Option("Tous", "Toutes les cotisations"),
                ft.dropdown.Option("Soldes", "Soldés uniquement"),
                ft.dropdown.Option("RestantDu", "Restant dû uniquement"),
            ],
            value="Tous",
            on_change=self.filtrer_membres
        )

        self.btn_export_pdf = ft.ElevatedButton(
            "📄 Exporter la liste en PDF",
            icon=get_icon_safe("PICTURE_AS_PDF"),
            bgcolor="#334155",
            color="white",
            height=44,
            on_click=self.generer_et_ouvrir_pdf_direct
        )
        
        self.table_membres = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Adhérent")),
                ft.DataColumn(ft.Text("Licence / Niveau")),
                ft.DataColumn(ft.Text("Contact")),
                ft.DataColumn(ft.Text("Santé / Licence")),
                ft.DataColumn(ft.Text("Cotisation / Solde")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[]
        )

        self.view_container = ft.Container(expand=True)
        self.content = ft.Column([self.view_container], expand=True)

        self.afficher_ecran_liste()

    def generer_options_niveaux(self, valeur_actuelle=None):
        """Génère une liste complète, catégorisée et extensible de niveaux."""
        niveaux_asso = getattr(self.app, "association", {}).get("niveaux")
        options = []

        if niveaux_asso and isinstance(niveaux_asso, list):
            for n in niveaux_asso:
                options.append(ft.dropdown.Option(key=str(n), text=str(n)))
        else:
            structure_niveaux = [
                # --- Niveaux Généraux ---
                ("--- NIVEAUX GÉNÉRAUX ---", True),
                ("Éveil / Baby-Sport", False),
                ("Débutant", False),
                ("Intermédiaire", False),
                ("Confirmé", False),
                ("Avancé", False),
                ("Expert / Élite", False),

                # --- Pratique & Compétition ---
                ("--- PRATIQUE & PRÉPARATION ---", True),
                ("Loisir / Entretien", False),
                ("Compétition Régionale", False),
                ("Compétition Nationale", False),
                ("Haut Niveau / Pro", False),

                # --- Grades & Ceintures ---
                ("--- GRADES & CEINTURES ---", True),
                ("Ceinture Blanche", False),
                ("Ceinture Jaune", False),
                ("Ceinture Orange", False),
                ("Ceinture Verte", False),
                ("Ceinture Bleue", False),
                ("Ceinture Marron (1er Kyu)", False),
                ("Ceinture Noire 1er Dan", False),
                ("Ceinture Noire 2ème Dan", False),
                ("Ceinture Noire 3ème Dan ou +", False),

                # --- Encadrement & Arbitrage ---
                ("--- ENCADREMENT & OFFICIELS ---", True),
                ("Assistant / Aide-Moniteur", False),
                ("Animateur / Initiateur", False),
                ("Éducateur / Entraîneur", False),
                ("Arbitre / Juge Officiel", False),
            ]

            for item, is_header in structure_niveaux:
                if is_header:
                    options.append(ft.dropdown.Option(key=f"hdr_{item}", text=item, disabled=True))
                else:
                    options.append(ft.dropdown.Option(key=item, text=item))

        if valeur_actuelle and str(valeur_actuelle).strip():
            cles_existantes = [o.key for o in options]
            if valeur_actuelle not in cles_existantes:
                options.insert(0, ft.dropdown.Option(key=valeur_actuelle, text=f"{valeur_actuelle} (Spécifique)"))

        return options

    def did_mount(self):
        page_obj = self.page or getattr(self.app, "page", None)
        if page_obj:
            if hasattr(page_obj, "overlay") and self.file_picker not in page_obj.overlay:
                page_obj.overlay.append(self.file_picker)
            page_obj.update()

        self.recharger_donnees_actuelles()

    def afficher_message(self, text, is_error=False):
        color = "red700" if is_error else "green700"
        page_obj = self.page or getattr(self.app, "page", None)
        if not page_obj:
            return
        try:
            snack = ft.SnackBar(ft.Text(text), bgcolor=color)
            if hasattr(page_obj, "open"):
                page_obj.open(snack)
            elif hasattr(page_obj, "show_snack_bar"):
                page_obj.show_snack_bar(snack)
            else:
                page_obj.snack_bar = snack
                snack.open = True
                page_obj.update()
        except Exception as ex:
            print("Erreur SnackBar:", ex)

    def _nettoyer_float(self, valeur):
        if valeur is None:
            return 0.0
        try:
            return float(str(valeur).replace("€", "").replace(",", ".").strip())
        except ValueError:
            return 0.0

    def recharger_donnees_actuelles(self):
        if hasattr(self.app, "db") and self.app.db:
            saison = getattr(self.app, "saison_active", None)
            try:
                if hasattr(self.app.db, "charger_cotisations"):
                    self.app.cotisations = self.app.db.charger_cotisations(saison=saison)
                
                if hasattr(self.app.db, "charger_adherents_par_saison"):
                    donnees = self.app.db.charger_adherents_par_saison(saison)
                    if donnees is not None:
                        self.app.membres = donnees
                elif hasattr(self.app.db, "charger_tous_les_adherents"):
                    res = self.app.db.charger_tous_les_adherents(saison)
                    if isinstance(res, tuple):
                        if len(res) > 0:
                            self.app.membres = res[0]
                        if len(res) > 1 and res[1] is not None:
                            self.app.cotisations = res[1]
                    elif isinstance(res, list):
                        self.app.membres = res
            except Exception as err:
                print(f"Erreur de rechargement BDD : {err}")

        self.load_membres_table()
        if self.page:
            self.update()

    def generer_et_ouvrir_pdf_direct(self, e):
        """Génère directement le PDF en mode portrait avec fpdf2 en tenant compte des filtres."""
        try:
            from fpdf import FPDF
        except ImportError:
            self.afficher_message("Bibliothèque fpdf2 introuvable.", is_error=True)
            return

        try:
            membres_a_exporter = []
            filtre_txt = (self.input_recherche.value or "").strip().lower()
            filtre_cotis = self.dropdown_filtre_cotis.value or "Tous"

            for m in getattr(self.app, "membres", []):
                nom_str = (m.get('nom') or '').upper()
                prenom_str = (m.get('prenom') or '')
                nom_complet = f"{nom_str} {prenom_str}"
                if filtre_txt and filtre_txt not in nom_complet.lower():
                    continue

                bilan = self.obtenir_bilan_financier_membre(m)
                if filtre_cotis == "Soldes" and not bilan["is_solde"]:
                    continue
                elif filtre_cotis == "RestantDu" and bilan["is_solde"]:
                    continue
                
                membres_a_exporter.append((m, bilan))

            if not membres_a_exporter:
                self.afficher_message("⚠️ Aucun adhérent ne correspond aux filtres actuels.", is_error=True)
                return

            dossier_cible = self.app.db.get_documents_saison_dir()
            nom_fichier = f"liste_adherents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            chemin_complet = dossier_cible / nom_fichier

            pdf = FPDF(orientation='P', unit='mm', format='A4')
            pdf.add_page()
            pdf.set_margins(10, 10, 10)

            pdf.set_font("Arial", 'B', 14)
            nom_asso = getattr(self.app, "association", {}).get("nom", "Association Sportive")
            saison = getattr(self.app, "saison_active", "En cours")
            titre_texte = f"Liste des Adhérents - {nom_asso} (Saison {saison})"
            pdf.cell(0, 10, txt=titre_texte.encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
            pdf.ln(4)

            col_widths = [45, 30, 45, 35, 35]
            headers = ["Adhérent", "Contact", "Niveau / Licence", "Santé & Licence", "Cotisation"]

            pdf.set_font("Arial", 'B', 9)
            pdf.set_fill_color(51, 65, 85)
            pdf.set_text_color(255, 255, 255)

            for i, h in enumerate(headers):
                pdf.cell(col_widths[i], 8, txt=h, border=1, align='C', fill=True)
            pdf.ln()

            pdf.set_font("Arial", '', 8)
            pdf.set_text_color(0, 0, 0)

            fill = False
            for m, bilan in membres_a_exporter:
                pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)

                nom_complet = f"{(m.get('nom') or '').upper()} {m.get('prenom') or ''}"
                contact = m.get('telephone') or 'N/A'
                
                niveau_str = (m.get('niveau_actuel') or 'Débutant').split('(')[0].strip()
                lic_str = m.get('licence')
                niveau_lic = f"{niveau_str} (Lic: {lic_str})" if lic_str else niveau_str

                certif = "Cert. OK" if m.get("certificat_medical_valide") else "Cert. Manq."
                licence_statut = "Licence: Oui" if m.get("licence_prise") else "Licence: Non"
                sante_str = f"{certif} | {licence_statut}"

                cotis_str = bilan["badge_texte"]

                row_data = [nom_complet, contact, niveau_lic, sante_str, cotis_str]

                if pdf.get_y() > 275:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 9)
                    pdf.set_fill_color(51, 65, 85)
                    pdf.set_text_color(255, 255, 255)
                    for i, h in enumerate(headers):
                        pdf.cell(col_widths[i], 8, txt=h, border=1, align='C', fill=True)
                    pdf.ln()
                    pdf.set_font("Arial", '', 8)
                    pdf.set_text_color(0, 0, 0)

                for i, text in enumerate(row_data):
                    safe_text = str(text).encode('latin-1', 'replace').decode('latin-1')
                    pdf.cell(col_widths[i], 7, txt=safe_text, border=1, align='L', fill=True)
                
                pdf.ln()
                fill = not fill

            pdf.output(str(chemin_complet))

            try:
                page_obj = self.page or getattr(self.app, "page", None)
                if page_obj and hasattr(page_obj, "share_files"):
                    page_obj.share_files([str(chemin_complet)])
                else:
                    webbrowser.open(str(chemin_complet))
            except Exception:
                webbrowser.open(str(chemin_complet))

            self.afficher_message(f"📄 PDF généré et ouvert avec succès !\nFichier : {nom_fichier}")
        except Exception as ex:
            print(ex)
            self.afficher_message(f"❌ Erreur lors de la génération du PDF : {ex}", is_error=True)

    def calculer_age(self, date_str):
        if not date_str:
            return None
        formats = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"]
        for fmt in formats:
            try:
                birth = datetime.strptime(str(date_str).strip(), fmt)
                today = datetime.today()
                return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            except ValueError:
                continue
        return None

    def obtenir_tarif_theorique(self, membre):
        tarif_custom = membre.get("tarif_custom")
        if tarif_custom is not None and str(tarif_custom).strip() != "":
            return self._nettoyer_float(tarif_custom)

        tarifs = getattr(self.app, "association", {}).get("tarifs", {"u12": 100.0, "u18": 130.0, "adult": 160.0})
        age = self.calculer_age(membre.get("date_naissance"))
        if age is None:
            return float(tarifs.get("adult", 160.0))
        if age < 12:
            return float(tarifs.get("u12", 100.0))
        elif age < 18:
            return float(tarifs.get("u18", 130.0))
        else:
            return float(tarifs.get("adult", 160.0))

    def obtenir_reglements_membre(self, nom_membre, prenom_membre):
        nom = str(nom_membre or "").strip().upper()
        prenom = str(prenom_membre or "").strip().upper()
        
        cles_recherche = {f"{nom} {prenom}".strip(), f"{prenom} {nom}".strip()}
        
        reglements = []
        total_paye = 0.0

        cotis_list = getattr(self.app, "cotisations", [])
        for c in cotis_list:
            membre_cotis = str(c.get("membre", "")).strip().upper()
            if membre_cotis in cles_recherche:
                reglements.append(c)
                if c.get("statut") not in ["Annulé", "Rejeté"]:
                    total_paye += self._nettoyer_float(c.get("montant", 0))
                    
        return reglements, total_paye

    def obtenir_bilan_financier_membre(self, membre):
        tarif_du = self.obtenir_tarif_theorique(membre)
        _, total_paye = self.obtenir_reglements_membre(membre.get("nom", ""), membre.get("prenom", ""))
        solde = total_paye - tarif_du

        is_solde = solde >= -0.01
        reste_a_payer = abs(solde) if not is_solde else 0.0

        if is_solde:
            badge_texte = "✅ Soldé"
            color = "green400"
        elif total_paye > 0:
            badge_texte = f"🟠 Reste : {reste_a_payer:.2f} €"
            color = "orange400"
        else:
            badge_texte = f"🔴 Non payé ({tarif_du:.2f} €)"
            color = "red400"

        return {
            "tarif_du": tarif_du,
            "total_paye": total_paye,
            "solde": solde,
            "reste_a_payer": reste_a_payer,
            "is_solde": is_solde,
            "badge_texte": badge_texte,
            "color": color
        }

    def afficher_ecran_liste(self):
        self.current_editing_index = None
        self.recharger_donnees_actuelles()

        self.view_container.content = ft.Column(
            scroll="auto",
            spacing=15,
            controls=[
                ft.Row([
                    ft.Icon(get_icon_safe("PEOPLE"), size=28, color=self.accent_color),
                    ft.Text("Adhérents & Licenciés", size=20, weight="bold"),
                ]),
                ft.Divider(),
                
                ft.ResponsiveRow([
                    ft.Container(self.input_recherche, col={"sm": 12, "md": 7, "lg": 8}),
                    ft.Container(self.dropdown_filtre_cotis, col={"sm": 12, "md": 5, "lg": 4}),
                ], run_spacing=10),

                ft.Row([
                    self.btn_export_pdf,
                    ft.OutlinedButton(
                        "🔄 Renouvellement",
                        icon=get_icon_safe("AUTORENEW"),
                        height=44,
                        on_click=self.ouvrir_dialogue_renouvellement
                    ),
                    ft.ElevatedButton(
                        "Ajouter",
                        icon=get_icon_safe("PERSON_ADD"),
                        bgcolor=self.accent_color,
                        color="white",
                        height=44,
                        on_click=lambda e: self.afficher_ecran_formulaire()
                    )
                ], spacing=10, wrap=True),
                
                ft.Container(
                    bgcolor="#1F2937",
                    padding=10,
                    border_radius=10,
                    content=ft.Column(
                        scroll="auto",
                        controls=[
                            ft.Row(
                                scroll="auto",
                                controls=[self.table_membres]
                            )
                        ]
                    )
                )
            ]
        )
        if self.page:
            self.update()

    def afficher_ecran_formulaire(self, index_membre=None):
        self.current_editing_index = index_membre
        titre_form = "Créer une fiche adhérent"
        icon_form = get_icon_safe("PERSON_ADD")
        
        if index_membre is not None:
            titre_form = "Modifier l'adhérent"
            icon_form = get_icon_safe("EDIT")
            self.pre_remplir_formulaire(index_membre)
        else:
            self.vider_formulaire()

        self.view_container.content = ft.Column(
            scroll="auto",
            spacing=20,
            controls=[
                ft.Row([
                    ft.Icon(icon_form, size=28, color=self.accent_color),
                    ft.Text(titre_form, size=18, weight="bold"),
                    ft.Container(expand=True),
                    ft.OutlinedButton("Retour", icon=get_icon_safe("ARROW_BACK"), on_click=lambda e: self.afficher_ecran_liste())
                ]),
                ft.Divider(),

                self.creer_section_card("1. Identité & Photo", [
                    ft.ResponsiveRow([
                        ft.Container(self.input_nom, col={"sm": 12, "md": 6}),
                        ft.Container(self.input_prenom, col={"sm": 12, "md": 6}),
                    ]),
                    ft.ResponsiveRow([
                        ft.Container(self.dropdown_sexe, col={"sm": 12, "md": 4}),
                        ft.Container(self.input_date_naissance, col={"sm": 12, "md": 8}),
                    ]),
                    ft.Row([
                        self.input_photo,
                        ft.IconButton(
                            icon=get_icon_safe("ADD_A_PHOTO"), 
                            icon_color=self.accent_color, 
                            tooltip="Sélectionner une photo",
                            on_click=lambda e: self.file_picker.pick_files(file_type="image")
                        )
                    ], spacing=10)
                ]),

                self.creer_section_card("2. Contacts & Adresse", [
                    ft.ResponsiveRow([
                        ft.Container(self.input_telephone, col={"sm": 12, "md": 6}),
                        ft.Container(self.input_email, col={"sm": 12, "md": 6}),
                    ]),
                    ft.Row([self.input_rue]),
                    ft.ResponsiveRow([
                        ft.Container(self.input_cp, col={"sm": 12, "md": 4}),
                        ft.Container(self.input_ville, col={"sm": 12, "md": 8}),
                    ]),
                ]),

                self.creer_section_card("3. Santé & Responsabilité", [
                    ft.Row([self.input_responsable]),
                    ft.ResponsiveRow([
                        ft.Container(self.check_medical, col={"sm": 12, "md": 6}),
                        ft.Container(self.check_accord_soins, col={"sm": 12, "md": 6}),
                    ]),
                    ft.Row([self.input_allergies]),
                    ft.Row([self.input_fiche_medecin]),
                ]),

                self.creer_section_card("4. Licence, Niveau & Cotisation", [
                    ft.ResponsiveRow([
                        ft.Container(self.input_licence, col={"sm": 12, "md": 6}),
                        ft.Container(self.dropdown_niveau, col={"sm": 12, "md": 6}),
                    ]),
                    ft.ResponsiveRow([
                        ft.Container(self.input_tarif_custom, col={"sm": 12, "md": 12}),
                    ]),
                    ft.Row([self.check_licence_prise]),
                    ft.Row([self.input_historique_licences]),
                ]),

                ft.Row([
                    ft.TextButton("Annuler", icon=get_icon_safe("CANCEL"), icon_color="red400", on_click=lambda e: self.afficher_ecran_liste()),
                    ft.ElevatedButton(
                        "Enregistrer", 
                        icon=get_icon_safe("SAVE"), 
                        bgcolor="green700", 
                        color="white", 
                        height=48,
                        on_click=self.sauvegarder_fiche
                    )
                ], alignment="end", spacing=10),
                ft.Container(height=20)
            ]
        )
        if self.page:
            self.update()

    def creer_section_card(self, titre, composants):
        return ft.Container(
            bgcolor="#1F2937",
            padding=15,
            border_radius=10,
            content=ft.Column([
                ft.Text(titre, size=14, weight="bold", color="blue200"),
                ft.Divider(color="grey800", height=8),
                ft.Column(controls=composants, spacing=10)
            ], spacing=5)
        )

    def ouvrir_dialogue_renouvellement(self, e):
        page_obj = self.page or getattr(self.app, "page", None)
        if not page_obj:
            return

        saison_actuelle = str(getattr(self.app, "saison_active", "2024-2025"))

        saisons_disponibles = []
        if hasattr(self.app, "db") and self.app.db:
            if hasattr(self.app.db, "lister_saisons"):
                toutes_saisons = self.app.db.lister_saisons()
                saisons_disponibles = [str(s) for s in toutes_saisons if str(s) != saison_actuelle]

        if not saisons_disponibles:
            try:
                start_year = int(saison_actuelle.split("-")[0])
            except Exception:
                start_year = 2024
            saisons_disponibles = [f"{start_year - i}-{start_year - i + 1}" for i in range(1, 6)]

        noms_existants = [
            f"{(m.get('nom') or '').strip().upper()} {(m.get('prenom') or '').strip().upper()}" 
            for m in getattr(self.app, "membres", [])
        ]

        membres_trouves_global = {}
        for s in reversed(saisons_disponibles):
            anciens = []
            if hasattr(self.app, "db") and self.app.db:
                if hasattr(self.app.db, "charger_adherents_par_saison"):
                    anciens = self.app.db.charger_adherents_par_saison(s)
                else:
                    res = self.app.db.charger_tous_les_adherents(s)
                    if isinstance(res, tuple) and len(res) > 0:
                        anciens = res[0]

            if anciens:
                for m in anciens:
                    cle = f"{(m.get('nom') or '').strip().upper()} {(m.get('prenom') or '').strip().upper()}"
                    if cle not in noms_existants:
                        membres_trouves_global[cle] = (m, s)

        options_membres = [ft.dropdown.Option("tous", "-- Tous les membres inscriptibles --")]
        for cle, (m_data, s_source) in membres_trouves_global.items():
            nom_aff = f"{(m_data.get('nom') or '').upper()} {m_data.get('prenom') or ''}"
            options_membres.append(ft.dropdown.Option(cle, f"{nom_aff} (Ex: S{s_source})"))

        dropdown_membres = ft.Dropdown(
            label="Sélectionner un membre",
            expand=True,
            options=options_membres,
            value="tous"
        )

        dropdown_saison = ft.Dropdown(
            label="Saison source",
            expand=True,
            options=[ft.dropdown.Option("toutes", "Toutes les anciennes saisons")] + [
                ft.dropdown.Option(s, f"Saison {s}") for s in saisons_disponibles
            ],
            value="toutes"
        )

        input_recherche_modal = ft.TextField(
            label="Filtrer par nom...",
            prefix_icon=get_icon_safe("SEARCH"),
            expand=True
        )

        container_liste = ft.Column(scroll="auto", expand=True)
        checkboxes_map = {}

        def actualiser_liste_dialogue(evt=None):
            checkboxes_map.clear()
            container_liste.controls.clear()

            saison_choisie = dropdown_saison.value
            membre_choisi = dropdown_membres.value
            filtre_txt = input_recherche_modal.value.strip().lower() if input_recherche_modal.value else ""

            saisons_a_charger = saisons_disponibles if saison_choisie == "toutes" else [saison_choisie]
            
            liste_controls = []
            for cle, (m_data, s_source) in membres_trouves_global.items():
                if s_source not in saisons_a_charger:
                    continue

                if membre_choisi != "tous" and cle != membre_choisi:
                    continue

                nom_affiche = f"{(m_data.get('nom') or '').upper()} {m_data.get('prenom') or ''}"
                niveau = m_data.get('niveau_actuel') or 'Débutant'
                
                if filtre_txt and filtre_txt not in nom_affiche.lower():
                    continue

                cb = ft.Checkbox(
                    label=f"{nom_affiche} ({niveau}) - Ex S{s_source}",
                    value=True
                )
                checkboxes_map[cb] = (m_data, s_source)
                liste_controls.append(cb)

            if not liste_controls:
                container_liste.controls.append(
                    ft.Text("Aucun membre correspondant.", italic=True, color="grey400", size=12)
                )
            else:
                container_liste.controls.extend(liste_controls)

            if page_obj:
                page_obj.update()

        dropdown_saison.on_change = actualiser_liste_dialogue
        dropdown_membres.on_change = actualiser_liste_dialogue
        input_recherche_modal.on_change = actualiser_liste_dialogue

        def valider_renouvellement(ev):
            membres_ajoutes = 0
            for cb, (m_data, s_source) in checkboxes_map.items():
                if cb.value:
                    nouvelle_fiche = dict(m_data)
                    nouvelle_fiche["certificat_medical_valide"] = False
                    nouvelle_fiche["licence_prise"] = False
                    histo = nouvelle_fiche.get("historique_licences") or ""
                    nouvelle_fiche["historique_licences"] = f"Renouvelé en {saison_actuelle} (Ex: {s_source})\n{histo}".strip()
                    
                    self.app.membres.append(nouvelle_fiche)
                    membres_ajoutes += 1

            if membres_ajoutes > 0:
                if hasattr(self.app, "save_data"):
                    self.app.save_data()
                self.recharger_donnees_actuelles()
                self.afficher_message(f"🎉 {membres_ajoutes} membre(s) réinscrit(s) pour {saison_actuelle} !")
            else:
                self.afficher_message("Aucun membre sélectionné.")

            if hasattr(page_obj, "close"):
                page_obj.close(dialog_renouvellement)
            else:
                dialog_renouvellement.open = False
                page_obj.update()

        def fermer_dialogue(ev):
            if hasattr(page_obj, "close"):
                page_obj.close(dialog_renouvellement)
            else:
                dialog_renouvellement.open = False
                page_obj.update()

        dialog_renouvellement = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(get_icon_safe("AUTORENEW"), color=self.accent_color, size=22),
                ft.Text(f"Renouvellement pour {saison_actuelle}", size=16)
            ]),
            content=ft.Container(
                width=380,
                height=420,
                content=ft.Column(
                    controls=[
                        ft.Row([dropdown_membres], spacing=5),
                        ft.Row([dropdown_saison], spacing=5),
                        ft.Row([input_recherche_modal], spacing=5),
                        ft.Divider(height=5),
                        container_liste
                    ],
                    spacing=8
                )
            ),
            actions=[
                ft.TextButton("Annuler", on_click=fermer_dialogue),
                ft.ElevatedButton("Réinscrire", bgcolor="green700", color="white", on_click=valider_renouvellement)
            ]
        )

        if hasattr(page_obj, "open"):
            page_obj.open(dialog_renouvellement)
        else:
            if dialog_renouvellement not in page_obj.overlay:
                page_obj.overlay.append(dialog_renouvellement)
            dialog_renouvellement.open = True
            page_obj.update()

        actualiser_liste_dialogue()

    def modifier_statut_direct(self, e, index):
        self.app.membres[index]["licence_prise"] = e.control.value
        if hasattr(self.app, "save_data"):
            self.app.save_data()

    def load_membres_table(self, filtre_texte="", filtre_cotis="Tous"):
        self.table_membres.rows.clear()
        
        for index, m in enumerate(getattr(self.app, "membres", [])):
            nom_complet = f"{(m.get('nom') or '').upper()} {m.get('prenom') or ''}"
            
            if filtre_texte and filtre_texte.lower() not in nom_complet.lower():
                continue

            bilan = self.obtenir_bilan_financier_membre(m)

            if filtre_cotis == "Soldes" and not bilan["is_solde"]:
                continue
            elif filtre_cotis == "RestantDu" and bilan["is_solde"]:
                continue

            icon_med = ft.Icon(get_icon_safe("CHECK_CIRCLE"), color="green400", size=16) if m.get("certificat_medical_valide") else ft.Icon(get_icon_safe("DANGEROUS"), color="red400", size=16)
            
            cb_licence = ft.Checkbox(
                label="Licence",
                value=m.get("licence_prise", False),
                on_change=lambda e, idx=index: self.modifier_statut_direct(e, idx)
            )

            statut_sante = ft.Row([
                ft.Text("Certif:"), icon_med,
                ft.Container(content=cb_licence, padding=ft.padding.only(left=5))
            ], spacing=2, vertical_alignment="center")

            widget_cotis = ft.Column([
                ft.Text(bilan["badge_texte"], color=bilan["color"], weight="bold", size=11),
                ft.Text(f"Réglé: {bilan['total_paye']:.2f} € / Dû: {bilan['tarif_du']:.2f} €", size=10, color="grey400")
            ], spacing=2)

            avatar_char = (m.get("nom") or "X")[0].upper()

            self.table_membres.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Row([
                            ft.CircleAvatar(
                                foreground_image_url=m.get("photo") if m.get("photo") else None,
                                content=ft.Text(avatar_char) if not m.get("photo") else None,
                                radius=14
                            ),
                            ft.Text(nom_complet, weight="bold", size=12)
                        ], spacing=8)),
                        ft.DataCell(ft.Text(f"{m.get('niveau_actuel') or 'Débutant'}\n({m.get('licence') or 'N/A'})", size=11)),
                        ft.DataCell(ft.Text(f"{m.get('telephone') or 'N/A'}\n{m.get('email') or 'N/A'}", size=11)),
                        ft.DataCell(statut_sante),
                        ft.DataCell(widget_cotis),
                        ft.DataCell(ft.Row([
                            ft.IconButton(
                                icon=get_icon_safe("VISIBILITY"), 
                                icon_color="blue300", 
                                icon_size=20, 
                                tooltip="Voir la liste & détails des règlements", 
                                on_click=lambda e, idx=index: self.ouvrir_boite_details(idx)
                            ),
                            ft.IconButton(
                                icon=get_icon_safe("EDIT"), 
                                icon_color="orange300", 
                                icon_size=18, 
                                tooltip="Modifier l'adhérent", 
                                on_click=lambda e, idx=index: self.afficher_ecran_formulaire(idx)
                            ),
                            ft.IconButton(
                                icon=get_icon_safe("DELETE"), 
                                icon_color="red400", 
                                icon_size=18, 
                                tooltip="Supprimer", 
                                on_click=lambda e, idx=index: self.supprimer_fiche(idx)
                            ),
                        ], spacing=0))
                    ]
                )
            )

    def sauvegarder_fiche(self, e):
        if not self.input_nom.value or not self.input_prenom.value:
            self.afficher_message("Nom et prénom obligatoires", is_error=True)
            return

        dictionnaire_membre = {
            "nom": self.input_nom.value.strip(),
            "prenom": self.input_prenom.value.strip(),
            "sexe": self.dropdown_sexe.value if self.dropdown_sexe.value else "H",
            "date_naissance": self.input_date_naissance.value,
            "photo": self.input_photo.value,
            "email": self.input_email.value,
            "telephone": self.input_telephone.value,
            "adresse_rue": self.input_rue.value,
            "adresse_cp": self.input_cp.value,
            "adresse_ville": self.input_ville.value,
            "responsable_legal": self.input_responsable.value,
            "certificat_medical_valide": self.check_medical.value,
            "accord_parental_soins": self.check_accord_soins.value,
            "allergies": self.input_allergies.value,
            "fiche_medecin": self.input_fiche_medecin.value,
            "licence": self.input_licence.value,
            "licence_prise": self.check_licence_prise.value,
            "niveau_actuel": self.dropdown_niveau.value if self.dropdown_niveau.value else "Débutant",
            "historique_licences": self.input_historique_licences.value,
            "tarif_custom": self.input_tarif_custom.value.strip() if self.input_tarif_custom.value else ""
        }

        if self.current_editing_index is not None:
            self.app.membres[self.current_editing_index] = dictionnaire_membre
        else:
            self.app.membres.append(dictionnaire_membre)

        if hasattr(self.app, "save_data"):
            self.app.save_data()
            
        self.afficher_ecran_liste()

    def supprimer_fiche(self, index):
        page_obj = self.page or getattr(self.app, "page", None)
        
        def confirmer_suppression(e):
            self.app.membres.pop(index)
            if hasattr(self.app, "save_data"):
                self.app.save_data()
            
            if hasattr(page_obj, "close"):
                page_obj.close(dialog_confirmation)
            else:
                dialog_confirmation.open = False
                if page_obj:
                    page_obj.update()
            self.afficher_ecran_liste()

        nom_aff = (self.app.membres[index].get('nom') or '').upper()
        prenom_aff = self.app.membres[index].get('prenom') or ''

        dialog_confirmation = ft.AlertDialog(
            title=ft.Text("⚠️ Suppression", size=16),
            content=ft.Text(f"Supprimer la fiche de {nom_aff} {prenom_aff} ?", size=13),
            actions=[
                ft.TextButton("Non", on_click=lambda e: page_obj.close(dialog_confirmation) if hasattr(page_obj, "close") else setattr(dialog_confirmation, "open", False)),
                ft.ElevatedButton("Oui, supprimer", bgcolor="red700", color="white", on_click=confirmer_suppression)
            ]
        )
        if page_obj:
            if hasattr(page_obj, "open"):
                page_obj.open(dialog_confirmation)
            else:
                if dialog_confirmation not in page_obj.overlay:
                    page_obj.overlay.append(dialog_confirmation)
                dialog_confirmation.open = True
                page_obj.update()

    def ouvrir_boite_details(self, index):
        page_obj = self.page or getattr(self.app, "page", None)
        m = self.app.membres[index]
        
        adresse = f"{m.get('adresse_rue') or ''}\n{m.get('adresse_cp') or ''} {m.get('adresse_ville') or ''}".strip()
        if not adresse.replace("\n", ""):
            adresse = "Non renseignée"

        sexe_libelle = "Homme" if m.get("sexe") == "H" else ("Femme" if m.get("sexe") == "F" else "N/R")

        bilan = self.obtenir_bilan_financier_membre(m)
        reglements, _ = self.obtenir_reglements_membre(m.get("nom", ""), m.get("prenom", ""))

        liste_widgets_reglements = []
        if not reglements:
            liste_widgets_reglements.append(
                ft.Container(
                    padding=10,
                    content=ft.Text("Aucun règlement enregistré pour cet adhérent.", italic=True, size=11, color="grey400")
                )
            )
        else:
            for r in reglements:
                mode = r.get("mode") or "Règlement"
                details_mode = []
                if r.get("num_cheque"):
                    details_mode.append(f"Chèque N°{r.get('num_cheque')}")
                if r.get("banque"):
                    details_mode.append(f"Banque: {r.get('banque')}")
                if r.get("num_pass_sport"):
                    details_mode.append(f"Pass'Sport: {r.get('num_pass_sport')}")

                str_details = (" - " + ", ".join(details_mode)) if details_mode else ""
                statut = r.get("statut") or "Validé"
                
                if statut == "Encaissé / Validé":
                    badge_statut_color = "green400"
                elif statut in ["Annulé", "Rejeté"]:
                    badge_statut_color = "red400"
                else:
                    badge_statut_color = "orange400"

                montant_val = self._nettoyer_float(r.get("montant", 0))

                liste_widgets_reglements.append(
                    ft.Container(
                        padding=10,
                        bgcolor="#111827",
                        border_radius=8,
                        border=ft.border.all(1, "#374151"),
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Icon(get_icon_safe("RECEIPT"), size=16, color="blue300"),
                                    ft.Text(f"Date : {r.get('date') or 'N/A'}", size=12, weight="bold"),
                                ]),
                                ft.Text(f"{montant_val:.2f} €", weight="bold", color="green300", size=13)
                            ], alignment="spaceBetween"),
                            
                            ft.Text(f"Mode : {mode}{str_details}", size=11, color="grey300"),
                            ft.Row([
                                ft.Text("Statut : ", size=11, color="grey400"),
                                ft.Text(statut, size=11, weight="bold", color=badge_statut_color)
                            ])
                        ], spacing=3)
                    )
                )

        nom_aff = (m.get('nom') or '').upper()
        prenom_aff = m.get('prenom') or ''
        avatar_char = (m.get('nom') or 'X')[0].upper()

        dialog_details = ft.AlertDialog(
            title=ft.Row([
                ft.CircleAvatar(
                    foreground_image_url=m.get("photo") if m.get("photo") else None,
                    content=ft.Text(avatar_char) if not m.get("photo") else None,
                    radius=22
                ),
                ft.Column([
                    ft.Text(f"{nom_aff} {prenom_aff}", size=16, weight="bold"),
                    ft.Text(f"Sexe: {sexe_libelle} | Né(e): {m.get('date_naissance') or 'N/A'}", size=11, color="grey400"),
                ], spacing=2, expand=True)
            ], spacing=10),
            
            content=ft.Container(
                width=420,
                height=480,
                content=ft.Column(
                    scroll="auto",
                    spacing=12,
                    controls=[
                        ft.Container(
                            padding=12,
                            bgcolor="#1E293B",
                            border_radius=10,
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon(get_icon_safe("ACCOUNT_BALANCE_WALLET"), color="blue300", size=20),
                                    ft.Text("Détail & Historique des Règlements", weight="bold", size=14, color="blue200")
                                ]),
                                ft.Divider(height=5, color="grey700"),
                                ft.Row([
                                    ft.Text("Tarif dû (appliqué) :", size=11, color="grey300"),
                                    ft.Text(f"{bilan['tarif_du']:.2f} €", size=11, weight="bold")
                                ], alignment="spaceBetween"),
                                ft.Row([
                                    ft.Text("Total réglé (valide) :", size=11, color="grey300"),
                                    ft.Text(f"{bilan['total_paye']:.2f} €", size=11, weight="bold", color="green300")
                                ], alignment="spaceBetween"),
                                ft.Row([
                                    ft.Text("État de la cotisation :", size=11, color="grey300"),
                                    ft.Text(bilan["badge_texte"], size=11, weight="bold", color=bilan["color"])
                                ], alignment="spaceBetween"),
                                ft.Divider(height=5, color="grey700"),
                                ft.Text("Versements effectués :", size=12, weight="bold", color="blue200"),
                                ft.Column(controls=liste_widgets_reglements, spacing=8)
                            ], spacing=6)
                        ),

                        ft.Container(
                            padding=12,
                            bgcolor="#111827",
                            border_radius=10,
                            content=ft.Column([
                                ft.Text("Informations Personnelles", weight="bold", size=13, color="blue200"),
                                ft.Divider(height=5, color="grey800"),
                                self.creer_ligne_detail("📞 Tél :", m.get("telephone") or "N/A"),
                                self.creer_ligne_detail("📧 Email :", m.get("email") or "N/A"),
                                self.creer_ligne_detail("📍 Adresse :", adresse, multiline=True),
                                self.creer_ligne_detail("👤 Responsable :", m.get("responsable_legal") or "Majeur"),
                                self.creer_ligne_detail("📜 Certif médical :", "✅ OK" if m.get("certificat_medical_valide") else "❌ MANQUANT", color_val="green400" if m.get("certificat_medical_valide") else "red400"),
                                self.creer_ligne_detail("🩺 Urgences :", "Autorisé" if m.get("accord_parental_soins") else "Non signé", color_val="blue300" if m.get("accord_parental_soins") else "orange300"),
                                self.creer_ligne_detail("⚠️ Allergies :", m.get("allergies") or "RAS", color_val="red300" if m.get("allergies") else "white"),
                                self.creer_ligne_detail(" Level / Grade :", m.get("niveau_actuel") or "Débutant"),
                                self.creer_ligne_detail("🆔 Licence :", f"{m.get('licence') or 'N/A'} ({'✅ Prise' if m.get('licence_prise') else '❌ Non prise'})"),
                            ], spacing=6)
                        )
                    ]
                )
            ),
            actions=[
                ft.TextButton("Fermer", on_click=lambda e: page_obj.close(dialog_details) if hasattr(page_obj, "close") else setattr(dialog_details, "open", False))
            ]
        )
        if page_obj:
            if hasattr(page_obj, "open"):
                page_obj.open(dialog_details)
            else:
                if dialog_details not in page_obj.overlay:
                    page_obj.overlay.append(dialog_details)
                dialog_details.open = True
                page_obj.update()

    def creer_ligne_detail(self, label, valeur, multiline=False, color_val="white"):
        val_text = ft.Text(valeur, size=12, weight="bold" if not multiline else "normal", color=color_val, selectable=True, expand=True)
        if multiline:
            return ft.Column([
                ft.Text(label, size=11, color="blue200", italic=True),
                ft.Container(content=val_text, padding=ft.padding.only(left=8))
            ], spacing=2)
        return ft.Row([
            ft.Text(label, size=11, color="blue200", italic=True, width=120),
            val_text
        ], alignment="start")

    def on_photo_picked(self, e: ft.FilePickerResultEvent):
        if e.files:
            self.input_photo.value = e.files[0].path
            if self.page:
                self.update()

    def filtrer_membres(self, e):
        txt = self.input_recherche.value or ""
        filtre_cotis = self.dropdown_filtre_cotis.value or "Tous"
        self.load_membres_table(filtre_texte=txt, filtre_cotis=filtre_cotis)
        if self.page:
            self.table_membres.update()

    def pre_remplir_formulaire(self, index):
        m = self.app.membres[index]
        valeur_niveau = m.get("niveau_actuel") or "Débutant"
        
        self.input_nom.value = m.get("nom") or ""
        self.input_prenom.value = m.get("prenom") or ""
        self.dropdown_sexe.value = m.get("sexe") or "H"
        self.input_date_naissance.value = m.get("date_naissance") or ""
        self.input_photo.value = m.get("photo") or ""
        self.input_email.value = m.get("email") or ""
        self.input_telephone.value = m.get("telephone") or ""
        self.input_rue.value = m.get("adresse_rue") or ""
        self.input_cp.value = m.get("adresse_cp") or ""
        self.input_ville.value = m.get("adresse_ville") or ""
        self.input_responsable.value = m.get("responsable_legal") or ""
        self.check_medical.value = m.get("certificat_medical_valide", False)
        self.check_accord_soins.value = m.get("accord_parental_soins", False)
        self.input_allergies.value = m.get("allergies") or ""
        self.input_fiche_medecin.value = m.get("fiche_medecin") or ""
        self.input_licence.value = m.get("licence") or ""
        self.check_licence_prise.value = m.get("licence_prise", False)
        
        # Mettre à jour les options avec la valeur du membre
        self.dropdown_niveau.options = self.generer_options_niveaux(valeur_actuelle=valeur_niveau)
        self.dropdown_niveau.value = valeur_niveau
        
        self.input_historique_licences.value = m.get("historique_licences") or ""
        self.input_tarif_custom.value = str(m.get("tarif_custom") or "")

    def vider_formulaire(self):
        self.input_nom.value = ""
        self.input_prenom.value = ""
        self.dropdown_sexe.value = "H"
        self.input_date_naissance.value = ""
        self.input_photo.value = ""
        self.input_email.value = ""
        self.input_telephone.value = ""
        self.input_rue.value = ""
        self.input_cp.value = ""
        self.input_ville.value = ""
        self.input_responsable.value = ""
        self.check_medical.value = False
        self.check_accord_soins.value = False
        self.input_allergies.value = ""
        self.input_fiche_medecin.value = ""
        self.input_licence.value = ""
        self.check_licence_prise.value = False
        
        self.dropdown_niveau.options = self.generer_options_niveaux()
        self.dropdown_niveau.value = "Débutant"
        
        self.input_historique_licences.value = ""
        self.input_tarif_custom.value = ""