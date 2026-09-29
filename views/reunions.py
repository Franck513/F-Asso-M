# views/reunions.py
import flet as ft
from datetime import datetime
import re
import os
import webbrowser

def get_icon_safe(name: str):
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()

class ReunionsView(ft.Container):
    def __init__(self, app):
        super().__init__(expand=True)
        self.app = app
        self.accent_color = self.app.association.get("accent_color", "#1E3A8A")
        
        # Index du document en cours de modification (None = Nouveau document)
        self.current_index = None

        # Initialisation de la structure de stockage si absente
        if not hasattr(self.app, "reunions_docs") or self.app.reunions_docs is None:
            self.app.reunions_docs = []

        # --- CHAMPS DU FORMULAIRE ---
        self.dropdown_type = ft.Dropdown(
            label="Type de Document",
            width=250,
            options=[
                ft.dropdown.Option("Convocation - Réunion de Bureau"),
                ft.dropdown.Option("Compte-Rendu - Réunion de Bureau"),
                ft.dropdown.Option("Convocation - Assemblée Générale (AG)"),
                ft.dropdown.Option("Procès-Verbal (PV) - Assemblée Générale"),
                ft.dropdown.Option("Note Réglementaire / Statutaire"),
            ],
            value="Convocation - Réunion de Bureau",
            on_change=self.charger_modele_type
        )

        self.input_titre = ft.TextField(
            label="Objet / Titre du document", 
            width=400,
            hint_text="Ex: Bureau extraordinaire - Préparation saison"
        )
        
        self.input_date = ft.TextField(
            label="Date de l'événement", 
            width=180,
            value=datetime.now().strftime("%d/%m/%Y")
        )

        self.input_contenu = ft.TextField(
            label="Contenu et Mise en page réglementaire",
            multiline=True,
            min_lines=12,
            max_lines=20,
            expand=True,
            hint_text="Rédigez ou chargez un modèle réglementaire..."
        )

        # Charger le premier modèle par défaut si nouveau
        if self.current_index is None:
            self.charger_modele_type(None)

        # --- TABLEAU DE GESTION DES DOCUMENTS ENREGISTRÉS ---
        self.table_documents = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Date rédac.")),
                ft.DataColumn(ft.Text("Type")),
                ft.DataColumn(ft.Text("Titre / Objet")),
                ft.DataColumn(ft.Text("Actions")),
            ],
            rows=[]
        )

        # --- COLONNE PRINCIPALE SCROLLABLE ---
        self.main_column = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
            controls=[
                ft.Row([
                    ft.Icon(get_icon_safe("DESCRIPTION"), size=30, color=self.accent_color),
                    ft.Text("Gestion des Réunions, Bureau & Assemblées Générales (AG)", size=22, weight="bold"),
                ]),
                ft.Divider(),
                
                # Zone de rédaction / édition avec scrolls mobiles intégrés
                ft.Container(
                    content=ft.Column([
                        ft.Text("Rédacteur de documents réglementaires", size=16, weight="bold"),
                        # Ligne de champs avec défilement horizontal mobile
                        ft.Row([
                            ft.Row([
                                self.dropdown_type,
                                self.input_titre,
                                self.input_date,
                            ], spacing=15)
                        ], scroll=ft.ScrollMode.AUTO),
                        
                        self.input_contenu,
                        
                        # Ligne de boutons avec défilement horizontal mobile
                        ft.Row([
                            ft.Row([
                                ft.ElevatedButton(
                                    "Nouveau Document",
                                    icon=get_icon_safe("ADD"),
                                    on_click=self.nouveau_document
                                ),
                                ft.ElevatedButton(
                                    "Charger Modèle Type",
                                    icon=get_icon_safe("AUTO_FIX_HIGH"),
                                    on_click=self.charger_modele_type
                                ),
                                ft.ElevatedButton(
                                    "Enregistrer",
                                    icon=get_icon_safe("SAVE"),
                                    bgcolor=self.accent_color,
                                    color="white",
                                    on_click=self.sauvegarder_document
                                ),
                                ft.ElevatedButton(
                                    "Exporter en PDF",
                                    icon=get_icon_safe("PICTURE_AS_PDF"),
                                    bgcolor="red700",
                                    color="white",
                                    on_click=self.generer_et_sauvegarder_pdf
                                )
                            ], spacing=15)
                        ], scroll=ft.ScrollMode.AUTO)
                    ], spacing=15),
                    bgcolor="#1F2937",
                    padding=20,
                    border_radius=10
                ),
                
                ft.Divider(),
                ft.Text("Historique des documents de bureau et AG", size=16, weight="bold"),
                
                # Tableau d'historique avec scroll horizontal
                ft.Row(
                    [self.table_documents],
                    scroll=ft.ScrollMode.AUTO,
                )
            ]
        )

        self.content = self.main_column
        self.rafraichir_tableau()

    def did_mount(self):
        self.rafraichir_tableau()
        if self.page:
            self.update()

    def afficher_message(self, text, is_error=False):
        color = "red700" if is_error else "green700"
        try:
            snack = ft.SnackBar(ft.Text(text), bgcolor=color)
            if hasattr(self.app.page, "open"):
                self.app.page.open(snack)
            elif hasattr(self.app.page, "show_snack_bar"):
                self.app.page.show_snack_bar(snack)
            else:
                self.app.page.snack_bar = snack
                snack.open = True
                self.app.page.update()
        except Exception as ex:
            print("Erreur SnackBar:", ex)

    def nouveau_document(self, e):
        self.current_index = None
        self.input_date.value = datetime.now().strftime("%d/%m/%Y")
        self.charger_modele_type(None)
        self.afficher_message("✨ Prêt pour la rédaction d'un nouveau document.")

    def charger_modele_type(self, e):
        nom_club = self.app.association.get("nom", "Notre Association")
        type_doc = self.dropdown_type.value

        if "Convocation - Réunion de Bureau" in type_doc:
            self.input_titre.value = "Convocation au Conseil d'Administration / Bureau"
            self.input_contenu.value = f"""ASSOCIATION : {nom_club}
OBJET : Convocation à la réunion du Bureau Directeur

Madame, Monsieur, Cher membre du bureau,

Vous êtes convié(e) à participer à la prochaine réunion du Bureau Directeur de l'association {nom_club}, qui se tiendra :
- Date : [Insérer la date]
- Heure : [Insérer l'heure]
- Lieu : [Insérer le lieu ou lien visio]

Ordre du jour prévisionnel :
1. Approbation du dernier compte-rendu
2. Point sur la trésorerie et les cotisations
3. Prévision des prochains événements et manifestations
4. Questions diverses

Comptant sur votre présence indispensable pour le bon fonctionnement de notre structure.

Sportivement,
Le Secrétaire / Le Président"""

        elif "Compte-Rendu - Réunion de Bureau" in type_doc:
            self.input_titre.value = "Compte-Rendu de Réunion de Bureau"
            self.input_contenu.value = f"""ASSOCIATION : {nom_club}
COMPTE-RENDU DE LA RÉUNION DU BUREAU DIRECTOIRE

Date de la réunion : [Insérer la date]
Membres présents : [Lister les présents]
Membres excusés / absents : [Lister les absents]

1. Bilan des activités en cours :
- ...

2. Décisions validées à l'unanimité / vote :
- Décision 1 : ...
- Décision 2 : ...

3. Prochaines échéances :
- ...

Fin de la séance à [Heure]."""

        elif "Convocation - Assemblée Générale" in type_doc:
            self.input_titre.value = "Convocation officielle à l'Assemblée Générale Annuelle"
            self.input_contenu.value = f"""ASSOCIATION : {nom_club}
CONVOCATION À L'ASSEMBLÉE GÉNÉRALE ORDINAIRE

Madame, Monsieur, Chers Adhérents,

Conformément aux statuts de notre association, nous avons le plaisir de vous convier à notre Assemblée Générale Ordinaire qui se déroulera :
- Date : [Insérer la date]
- Heure : [Insérer l'heure]
- Lieu : [Insérer la salle]

Ordre du jour réglementaire :
1. Rapport moral présenté par le Président
2. Rapport financier présenté par le Trésorier
3. Rapport des vérificateurs aux comptes (le cas échéant)
4. Vote de renouvellement des membres du Conseil d'Administration
5. Orientation du budget et des cotisations pour la prochaine saison
6. Questions diverses des adhérents

En cas d'impossibilité d'assister à cette assemblée, vous avez la possibilité de vous faire représenter en remettant un pouvoir (procuration) signé à un autre membre présent.

Comptant sur votre participation active.

Le Président,
{nom_club}"""

        elif "Procès-Verbal (PV) - Assemblée Générale" in type_doc:
            self.input_titre.value = "Procès-Verbal de l'Assemblée Générale"
            self.input_contenu.value = f"""ASSOCIATION : {nom_club}
PROCÈS-VERBAL DE L'ASSEMBLÉE GÉNÉRALE ORDINAIRE

L'an [Année] et le [Date], à [Heure], les membres de l'association {nom_club} se sont réunis en Assemblée Générale Ordinaire.
Feuille de présence émargée : [Nombre] membres présents ou représentés (Le quorum est / n'est pas atteint).

1. Rapport Moral : Adopté à l'unanimité.
2. Rapport Financier : Adopté à l'unanimité.
3. Élections au Conseil d'Administration :
Sont élus / réélus membres du bureau :
- ...

L'ordre du jour étant épuisé, la séance est levée à [Heure].

Fait à [Ville], le [Date]
Le Président                        Le Secrétaire"""

        else:
            self.input_titre.value = "Note d'information réglementaire"
            self.input_contenu.value = f"Note réglementaire interne pour l'association {nom_club}..."

        if self.page:
            self.update()

    def sauvegarder_document(self, e):
        titre = self.input_titre.value.strip()
        if not titre:
            self.afficher_message("⚠️ Veuillez indiquer un titre pour ce document.", is_error=True)
            return

        doc_data = {
            "date": self.input_date.value.strip() or datetime.now().strftime("%d/%m/%Y"),
            "type": self.dropdown_type.value,
            "titre": titre,
            "contenu": self.input_contenu.value
        }

        # Modification ou Ajout
        if self.current_index is not None and 0 <= self.current_index < len(self.app.reunions_docs):
            self.app.reunions_docs[self.current_index] = doc_data
            self.afficher_message("✅ Document mis à jour avec succès !")
        else:
            self.app.reunions_docs.append(doc_data)
            self.current_index = len(self.app.reunions_docs) - 1
            self.afficher_message("✅ Document enregistré dans l'historique !")

        if hasattr(self.app, "save_data"):
            self.app.save_data()

        self.rafraichir_tableau()

    def generer_et_sauvegarder_pdf(self, e):
        titre = self.input_titre.value.strip()
        if not titre:
            self.afficher_message("⚠️ Veuillez saisir un titre pour exporter le PDF.", is_error=True)
            return
        
        try:
            # Sauvegarde ou mise à jour automatique dans l'historique avant export
            self.sauvegarder_document(None)

            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            
            # --- INSERTION DU LOGO DE L'ASSOCIATION (si disponible) ---
            logo_path = self.app.association.get("logo") or self.app.association.get("logo_path")
            if logo_path and os.path.exists(logo_path):
                try:
                    pdf.image(logo_path, x=10, y=10, w=25)
                    pdf.ln(15)
                except Exception as img_err:
                    print("Erreur chargement logo PDF :", img_err)

            # --- MISE EN PAGE DU DOCUMENT PDF ---
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, txt=self.input_titre.value.encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
            pdf.ln(5)
            
            pdf.set_font("Arial", 'I', 11)
            infos = f"Type : {self.dropdown_type.value}  |  Date : {self.input_date.value}"
            pdf.cell(0, 8, txt=infos.encode('latin-1', 'replace').decode('latin-1'), ln=True, align='C')
            pdf.ln(10)
            
            pdf.set_font("Arial", '', 10)
            contenu = self.input_contenu.value or ""
            for ligne in contenu.split('\n'):
                safe_ligne = ligne.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(0, 6, txt=safe_ligne, ln=True)
            
            # --- SIGNATURE DU PRÉSIDENT / SECRÉTAIRE ---
            pdf.ln(15)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 6, txt="Le Président / Le Secrétaire", ln=True, align='R')
            pdf.ln(5)
            
            signature_path = self.app.association.get("signature") or self.app.association.get("signature_path")
            if signature_path and os.path.exists(signature_path):
                try:
                    pdf.image(signature_path, x=140, y=pdf.get_y(), w=40)
                except Exception as sig_err:
                    print("Erreur chargement signature PDF :", sig_err)

            # --- ENREGISTREMENT VIA DATABASE.PY ---
            dossier_cible = self.app.db.get_documents_saison_dir()
            titre_nettoye = re.sub(r'[^a-zA-Z0-9]', '_', titre)
            titre_nettoye = re.sub(r'_+', '_', titre_nettoye).lower().strip('_')
            nom_fichier = f"{titre_nettoye}.pdf"
            chemin_complet = dossier_cible / nom_fichier
            
            pdf.output(str(chemin_complet))
            
            # --- OUVERTURE ADAPTÉE (ANDROID / WINDOWS) ---
            try:
                if hasattr(self.app.page, "share_files"):
                    self.app.page.share_files([str(chemin_complet)])
                else:
                    webbrowser.open(str(chemin_complet))
            except Exception:
                webbrowser.open(str(chemin_complet))

            self.afficher_message(f"📄 PDF généré et ouvert !\nFichier : {nom_fichier}")
        except Exception as ex:
            self.afficher_message(f"❌ Erreur lors de la création du PDF : {ex}", is_error=True)

    def ouvrir_pdf_externe(self, doc):
        try:
            titre = doc.get("titre", "")
            titre_nettoye = re.sub(r'[^a-zA-Z0-9]', '_', titre)
            titre_nettoye = re.sub(r'_+', '_', titre_nettoye).lower().strip('_')
            nom_fichier = f"{titre_nettoye}.pdf"
            dossier_cible = self.app.db.get_documents_saison_dir()
            chemin_complet = dossier_cible / nom_fichier
            
            if chemin_complet.exists():
                try:
                    if hasattr(self.app.page, "share_files"):
                        self.app.page.share_files([str(chemin_complet)])
                    else:
                        webbrowser.open(str(chemin_complet))
                except Exception:
                    webbrowser.open(str(chemin_complet))
                self.afficher_message(f"📂 Ouverture du PDF : {nom_fichier}")
            else:
                self.afficher_message(f"⚠️ Le fichier PDF n'existe pas encore. Veuillez cliquer sur 'Exporter en PDF'.", is_error=True)
        except Exception as ex:
            self.afficher_message(f"❌ Erreur d'ouverture : {ex}", is_error=True)

    def rafraichir_tableau(self):
        self.table_documents.rows.clear()
        docs = getattr(self.app, "reunions_docs", [])

        for idx, doc in enumerate(reversed(docs)):
            real_idx = len(docs) - 1 - idx
            self.table_documents.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(doc.get("date", "")))),
                        ft.DataCell(ft.Text(str(doc.get("type", "")))),
                        ft.DataCell(ft.Text(str(doc.get("titre", "")))),
                        ft.DataCell(
                            ft.Row([
                                ft.IconButton(
                                    get_icon_safe("VISIBILITY"),
                                    icon_color="blue300",
                                    icon_size=18,
                                    tooltip="Charger / Modifier",
                                    on_click=lambda e, i=real_idx: self.charger_document_existant(i)
                                ),
                                ft.IconButton(
                                    get_icon_safe("FOLDER_OPEN"),
                                    icon_color="amber300",
                                    icon_size=18,
                                    tooltip="Voir le PDF externe",
                                    on_click=lambda e, d=doc: self.ouvrir_pdf_externe(d)
                                ),
                                ft.IconButton(
                                    get_icon_safe("DELETE"),
                                    icon_color="red400",
                                    icon_size=18,
                                    tooltip="Supprimer",
                                    on_click=lambda e, i=real_idx: self.supprimer_document(i)
                                ),
                            ], spacing=0)
                        )
                    ]
                )
            )
        if self.page:
            self.update()

    def charger_document_existant(self, index):
        docs = getattr(self.app, "reunions_docs", [])
        if 0 <= index < len(docs):
            self.current_index = index
            doc = docs[index]
            self.dropdown_type.value = doc.get("type", self.dropdown_type.value)
            self.input_titre.value = doc.get("titre", "")
            self.input_date.value = doc.get("date", "")
            self.input_contenu.value = doc.get("contenu", "")
            
            try:
                self.main_column.scroll_to(offset=0, duration=300)
            except Exception:
                pass

            if self.page:
                self.update()
            self.afficher_message(f"✏️ Document chargé pour modification (Index #{index + 1}).")

    def supprimer_document(self, index):
        docs = getattr(self.app, "reunions_docs", [])
        if 0 <= index < len(docs):
            del docs[index]
            if self.current_index == index:
                self.current_index = None
            elif self.current_index is not None and self.current_index > index:
                self.current_index -= 1

            if hasattr(self.app, "save_data"):
                self.app.save_data()
            self.rafraichir_tableau()
            self.afficher_message("🗑️ Document supprimé.", is_error=True)