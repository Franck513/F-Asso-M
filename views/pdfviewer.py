import os
import platform
import shutil
import smtplib
import struct
import subprocess
import traceback
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import flet as ft

# Données officielles de secours multi-sports
DEFAULT_ASSOC = {
    "nom": "MON CLUB SPORTIF",
    "rna": "W000000000",
    "siret": "00000000000000",
    "adresse": "Adresse du Siège",
    "email": "contact@monclub.com",
    "tel": "Non renseigné",
    "president": "Le Président",
    "ville": "Ville",
}


def get_icon(name: str):
    """Brique de compatibilité universelle pour les icônes Flet."""
    name_upper = name.upper()
    if hasattr(ft, "Icons") and hasattr(ft.Icons, name_upper):
        return getattr(ft.Icons, name_upper)
    if hasattr(ft, "icons") and hasattr(ft.icons, name_upper):
        return getattr(ft.icons, name_upper)
    return name.lower()


def get_jpeg_dimensions(file_path):
    """Extrait les dimensions et les octets bruts d'un fichier JPEG (Python pur)."""
    if not file_path:
        return None, None, None
    try:
        path = Path(file_path)
        if not path.exists():
            return None, None, None
        with open(path, "rb") as f:
            data = f.read()
        if not data.startswith(b"\xff\xd8"):
            return None, None, None
        i = 2
        while i < len(data) - 8:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            ):
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return w, h, data
            else:
                length = struct.unpack(">H", data[i + 2 : i + 4])[0]
                i += 2 + length
    except Exception:
        pass
    return None, None, None


def extraire_infos_asso(assoc: dict) -> dict:
    """Extrait proprement les infos de l'association en blindant les valeurs de repli."""
    assoc = assoc or {}

    nom = (
        assoc.get("nom")
        or assoc.get("nom_assoc")
        or assoc.get("nom_association")
        or assoc.get("nom_officiel")
        or assoc.get("club")
        or assoc.get("expediteur")
        or DEFAULT_ASSOC["nom"]
    )

    rna = (
        assoc.get("rna")
        or assoc.get("num_rna")
        or assoc.get("numero_rna")
        or DEFAULT_ASSOC["rna"]
    )

    siret = (
        assoc.get("siret")
        or assoc.get("siren")
        or assoc.get("siret_siren")
        or DEFAULT_ASSOC["siret"]
    )

    rue = (
        assoc.get("adresse")
        or assoc.get("rue")
        or assoc.get("adresse_asso")
        or assoc.get("adresse_emetteur")
        or assoc.get("adresse_siege_social")
        or assoc.get("adresse_siege")
        or ""
    ).strip()

    cp = str(
        assoc.get("code_postal")
        or assoc.get("cp")
        or assoc.get("codepostal")
        or ""
    ).strip()

    ville = (
        assoc.get("ville")
        or assoc.get("commune")
        or ""
    ).strip()

    if rue:
        parties_adresse = [p for p in [rue, f"{cp} {ville}".strip()] if p]
        adresse_complete = " - ".join(parties_adresse)
    else:
        adresse_complete = DEFAULT_ASSOC["adresse"]

    tel = (
        assoc.get("telephone")
        or assoc.get("tel")
        or assoc.get("phone")
        or DEFAULT_ASSOC["tel"]
    )

    email = (
        assoc.get("email")
        or assoc.get("mail")
        or assoc.get("adresse_email_de_contact")
        or assoc.get("email_contact")
        or DEFAULT_ASSOC["email"]
    )

    president = (
        assoc.get("president")
        or assoc.get("nom_president")
        or DEFAULT_ASSOC["president"]
    )

    return {
        "nom": nom,
        "rna": rna,
        "siret": siret,
        "adresse": adresse_complete,
        "tel": tel,
        "email": email,
        "president": president,
        "ville": ville or DEFAULT_ASSOC["ville"],
    }


def generer_pdf_zero_dep(
    output_path, assoc, membre, doc_type, montant, saison
):
    """Générateur PDF officiel 100 % Python pur."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def clean(txt):
        if not txt:
            return ""
        map_accents = {
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "à": "a",
            "â": "a",
            "ä": "a",
            "î": "i",
            "ï": "i",
            "ô": "o",
            "ö": "o",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ç": "c",
            "É": "E",
            "È": "E",
            "À": "A",
            "€": "EUR",
            "°": "o",
        }
        res = str(txt)
        for k, v in map_accents.items():
            res = res.replace(k, v)
        res = res.encode("latin-1", "ignore").decode("latin-1")
        return res.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    asso_info = extraire_infos_asso(assoc)
    membre = membre or {}

    nom_assoc = clean(asso_info["nom"].upper())
    rna = clean(asso_info["rna"])
    siret = clean(asso_info["siret"])
    adresse_complete_assoc = clean(asso_info["adresse"])
    tel_assoc = clean(asso_info["tel"])
    email_assoc = clean(asso_info["email"])
    president = clean(asso_info["president"])

    nom_m = clean(membre.get("nom", "").upper())
    prenom_m = clean(membre.get("prenom", "").capitalize())
    nom_complet = f"{nom_m} {prenom_m}".strip() or "MEMBRE INCONNU"
    adresse_m = clean(
        membre.get("adresse") or membre.get("rue") or "Non renseignee"
    )
    cp_ville_m = clean(
        f"{membre.get('code_postal', '')} {membre.get('ville', '')}".strip()
    )
    email_m = clean(membre.get("email") or "Non renseigne")
    tel_m = clean(
        membre.get("telephone") or membre.get("tel") or "Non renseigne"
    )
    dob_m = clean(membre.get("date_naissance") or "Non renseignee")
    
    # Gestion générique de la licence et du niveau/grade
    licence_m = clean(
        membre.get("licence") or membre.get("licence_federale") or membre.get("licence_ffk") or "Non renseignee"
    )
    grade_m = clean(
        membre.get("niveau") or membre.get("grade") or membre.get("grade_actuel") or "Non renseigne"
    )
    date_jour = datetime.now().strftime("%d/%m/%Y")

    loaded_images = {}
    logo_path = assoc.get("logo_path") or assoc.get("logo") if assoc else None
    lw, lh, lbytes = get_jpeg_dimensions(logo_path)
    if lbytes:
        loaded_images["ImgLogo"] = {"w": lw, "h": lh, "bytes": lbytes}

    stamp_path = (
        (assoc.get("tampon_path") or assoc.get("stamp") or assoc.get("tampon"))
        if assoc
        else None
    )
    tw, th, tbytes = get_jpeg_dimensions(stamp_path)
    if tbytes:
        loaded_images["ImgStamp"] = {"w": tw, "h": th, "bytes": tbytes}

    sig_path = (
        (assoc.get("signature_path") or assoc.get("signature"))
        if assoc
        else None
    )
    sw, sh, sbytes = get_jpeg_dimensions(sig_path)
    if sbytes:
        loaded_images["ImgSig"] = {"w": sw, "h": sh, "bytes": sbytes}

    cmds = []

    text_x = 40
    if "ImgLogo" in loaded_images:
        img = loaded_images["ImgLogo"]
        aspect = img["w"] / img["h"]
        draw_w = 60 if aspect >= 1 else 60 * aspect
        draw_h = 60 / aspect if aspect >= 1 else 60
        cmds.append(
            f"q {draw_w:.2f} 0 0 {draw_h:.2f} 40 {750 + (60 - draw_h) / 2:.2f} cm /ImgLogo Do Q"
        )
        text_x = 115

    cmds.append("BT")
    cmds.append("0.12 0.23 0.54 rg /F1 14 Tf")
    cmds.append(f"{text_x:.2f} 798 Td ({nom_assoc}) Tj")
    cmds.append("0.3 0.3 0.3 rg /F1 9 Tf")
    cmds.append(f"0 -16 Td (Adresse : {adresse_complete_assoc}) Tj")
    cmds.append(f"0 -13 Td (Tel : {tel_assoc}  |  E-mail : {email_assoc}) Tj")
    cmds.append(f"0 -13 Td (SIRET : {siret}  |  RNA : {rna}) Tj")
    cmds.append("ET")

    cmds.append("0.7 0.7 0.75 rg 40 738 515 1 re f")

    titres = {
        "attestation": "ATTESTATION DE COTISATION",
        "recu": "RECU DE PAIEMENT",
        "licence": "ATTESTATION DE LICENCE & AFFILIATION",
        "fiche": "FICHE SYNOPTIQUE ADHERENT",
    }
    titre = titres.get(doc_type, "ATTESTATION OFFICIELLE")

    cmds.append("0.96 0.97 0.99 rg 40 675 515 40 re f")
    cmds.append("0.12 0.23 0.54 RG 1 w 40 675 515 40 re S")
    cmds.append(f"BT 0.12 0.23 0.54 rg /F1 12 Tf 55 690 Td ({titre}) Tj ET")

    if doc_type == "recu":
        cmds.append("BT 0.1 0.1 0.1 rg /F1 10 Tf")
        cmds.append(
            f"40 642 Td (Je soussigne\\(e\\), {president}, certifie avoir recu de l'adherent\\(e\\) :) Tj ET"
        )
        cmds.append("0.12 0.23 0.54 rg 40 595 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 601 Td (IDENTITE DU PAYEUR) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 495 515 100 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 495 515 100 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(f"55 572 Td (Nom et Prenom : {nom_complet}) Tj")
        cmds.append(f"0 -18 Td (Adresse : {adresse_m} {cp_ville_m}) Tj")
        cmds.append(f"0 -18 Td (Contact : {tel_m} - {email_m}) Tj")
        cmds.append("ET")
        cmds.append("0.12 0.23 0.54 rg 40 460 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 466 Td (DETAIL DU REGLEMENT) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 360 515 100 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 360 515 100 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(
            f"55 437 Td (Objet : Cotisation annuelle saison sportive {saison}) Tj"
        )
        cmds.append(f"0 -22 Td (Montant total percu : {montant} EUR) Tj")
        cmds.append(f"0 -22 Td (Statut : Reglement complet et solde) Tj")
        cmds.append("ET")
    elif doc_type == "licence":
        cmds.append("BT 0.1 0.1 0.1 rg /F1 10 Tf")
        cmds.append(
            f"40 642 Td (Je soussigne\\(e\\), {president}, agissant en qualite de President\\(e\\), atteste que :) Tj ET"
        )
        cmds.append("0.12 0.23 0.54 rg 40 595 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 601 Td (INFORMATIONS DU LICENCIE) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 495 515 100 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 495 515 100 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(f"55 572 Td (Nom et Prenom : {nom_complet}) Tj")
        cmds.append(f"0 -18 Td (Date de naissance : {dob_m}) Tj")
        cmds.append(f"0 -18 Td (Club : {nom_assoc}) Tj")
        cmds.append("ET")
        cmds.append("0.12 0.23 0.54 rg 40 460 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 466 Td (QUALIFICATION ET AFFILIATION) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 360 515 100 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 360 515 100 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(f"55 437 Td (Numero de licence : {licence_m}) Tj")
        cmds.append(f"0 -22 Td (Niveau / Grade : {grade_m}) Tj")
        cmds.append(f"0 -22 Td (Saison de validite : {saison}) Tj")
        cmds.append("ET")
    elif doc_type == "fiche":
        cmds.append("BT 0.1 0.1 0.1 rg /F1 10 Tf")
        cmds.append(
            "40 642 Td (Fiche synthetique recapitulatives du membre pour la saison sportive :) Tj ET"
        )
        cmds.append("0.12 0.23 0.54 rg 40 595 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 601 Td (ETAT CIVIL & CONTACT) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 475 515 120 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 475 515 120 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(f"55 572 Td (Nom & Prenom : {nom_complet}) Tj")
        cmds.append(f"0 -18 Td (Date de Naissance : {dob_m}) Tj")
        cmds.append(
            f"0 -18 Td (Adresse complete : {adresse_m} {cp_ville_m}) Tj"
        )
        cmds.append(f"0 -18 Td (Telephone : {tel_m}) Tj")
        cmds.append(f"0 -18 Td (E-mail : {email_m}) Tj")
        cmds.append("ET")
        cmds.append("0.12 0.23 0.54 rg 40 440 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 446 Td (SITUATIONS ADMINISTRATIVE ET FINANCIERE) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 330 515 110 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 330 515 110 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(f"55 415 Td (Saison active : {saison}) Tj")
        cmds.append(f"0 -20 Td (Numero de Licence : {licence_m}) Tj")
        cmds.append(f"0 -20 Td (Niveau / Grade : {grade_m}) Tj")
        cmds.append(f"0 -20 Td (Cotisation saisonniere : {montant} EUR) Tj")
        cmds.append("ET")
    else:
        cmds.append("BT 0.1 0.1 0.1 rg /F1 10 Tf")
        cmds.append(
            f"40 642 Td (Je soussigne\\(e\\), {president}, agissant en qualite de President\\(e\\) de l'association) Tj"
        )
        cmds.append(f"0 -15 Td ({nom_assoc}, atteste par la presente que :) Tj ET")
        cmds.append("0.12 0.23 0.54 rg 40 595 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 601 Td (IDENTITE DE L'ADHERENT) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 475 515 120 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 475 515 120 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(f"55 572 Td (Nom et Prenom : {nom_complet}) Tj")
        cmds.append(f"0 -18 Td (Date de naissance : {dob_m}) Tj")
        cmds.append(f"0 -18 Td (Adresse : {adresse_m} {cp_ville_m}) Tj")
        cmds.append(f"0 -18 Td (Telephone : {tel_m}) Tj")
        cmds.append(f"0 -18 Td (E-mail : {email_m}) Tj")
        cmds.append("ET")
        cmds.append("0.12 0.23 0.54 rg 40 440 515 20 re f")
        cmds.append(
            "BT 1 1 1 rg /F1 9 Tf 50 446 Td (COTISATION ET AFFILIATION SPORTIVE) Tj ET"
        )
        cmds.append("0.98 0.98 0.99 rg 40 330 515 110 re f")
        cmds.append("0.85 0.85 0.85 RG 0.8 w 40 330 515 110 re S")
        cmds.append("BT 0 0 0 rg /F1 10 Tf")
        cmds.append(
            f"55 415 Td (A acquitte l'integralite de sa cotisation pour la saison sportive : {saison}) Tj"
        )
        cmds.append(f"0 -22 Td (Montant de la cotisation : {montant} EUR) Tj")
        cmds.append(f"0 -22 Td (Licence N : {licence_m}) Tj")
        cmds.append(f"0 -22 Td (Niveau / Grade : {grade_m}) Tj")
        cmds.append("ET")

    cmds.append("BT 0.15 0.15 0.15 rg /F1 10 Tf")
    cmds.append(
        "40 280 Td (La presente attestation est delivree a l'interesse\\(e\\) pour servir et valoir ce que de droit.) Tj ET"
    )

    cmds.append("0.12 0.23 0.54 RG 1 w 290 95 265 155 re S")
    cmds.append("BT 0.12 0.23 0.54 rg /F1 9 Tf")
    cmds.append(
        f"300 232 Td (Fait a {clean(asso_info['ville'])}, le {date_jour}) Tj"
    )
    cmds.append("0.3 0.3 0.3 rg /F1 9 Tf")
    cmds.append(f"0 -14 Td (Le President : {president}) Tj")
    cmds.append("ET")

    if "ImgStamp" in loaded_images:
        img = loaded_images["ImgStamp"]
        aspect = img["w"] / img["h"]
        max_w, max_h = 66.5, 59.5
        draw_w = max_w if aspect >= 1 else max_h * aspect
        draw_h = max_w / aspect if aspect >= 1 else max_h
        pos_x = 300
        pos_y = 105 + (59.5 - draw_h) / 2
        cmds.append(
            f"q {draw_w:.2f} 0 0 {draw_h:.2f} {pos_x:.2f} {pos_y:.2f} cm /ImgStamp Do Q"
        )

    if "ImgSig" in loaded_images:
        img = loaded_images["ImgSig"]
        aspect = img["w"] / img["h"]
        max_w, max_h = 162.0, 90.0
        draw_w = max_w if aspect >= 1 else max_h * aspect
        draw_h = max_w / aspect if aspect >= 1 else max_h
        pos_x = 375
        pos_y = 100 + (90 - draw_h) / 2
        cmds.append(
            f"q {draw_w:.2f} 0 0 {draw_h:.2f} {pos_x:.2f} {pos_y:.2f} cm /ImgSig Do Q"
        )

    if "ImgSig" not in loaded_images and "ImgStamp" not in loaded_images:
        cmds.append("[3 3] 0 d 0.6 0.6 0.6 RG 300 135 m 535 135 l S [] 0 d")

    cmds.append("0.85 0.85 0.85 RG 0.5 w 40 45 m 555 45 l S")
    cmds.append("BT 0.5 0.5 0.5 rg /F1 8 Tf")
    cmds.append(
        f"40 32 Td ({nom_assoc} - Document officiel delivre le {date_jour} - Valide sans rature) Tj ET"
    )

    stream_bytes = "\n".join(cmds).encode("latin-1", "ignore")
    img_objs = []
    xobj_refs = []
    obj_counter = 6

    for key, img_data in loaded_images.items():
        xobj_refs.append(f"/{key} {obj_counter} 0 R")
        head = f"{obj_counter} 0 obj\n<</Type /XObject /Subtype /Image /Width {img_data['w']} /Height {img_data['h']} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(img_data['bytes'])}>>\nstream\n".encode(
            "latin-1"
        )
        foot = b"\nendstream\nendobj\n"
        img_objs.append(head + img_data["bytes"] + foot)
        obj_counter += 1

    res_resources = (
        f"<</Font <</F1 4 0 R>> /XObject <<{' '.join(xobj_refs)}>>>>"
        if xobj_refs
        else "<</Font <</F1 4 0 R>>>>"
    )

    objects_data = [
        "1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n".encode("latin-1"),
        "2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n".encode(
            "latin-1"
        ),
        f"3 0 obj\n<</Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources {res_resources} /Contents 5 0 R>>\nendobj\n".encode(
            "latin-1"
        ),
        "4 0 obj\n<</Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding>>\nendobj\n".encode(
            "latin-1"
        ),
        f"5 0 obj\n<</Length {len(stream_bytes)}>>\nstream\n".encode("latin-1")
        + stream_bytes
        + b"\nendstream\nendobj\n",
    ]
    objects_data.extend(img_objs)

    header = "%PDF-1.4\n"
    pos = len(header.encode("latin-1"))
    offsets = []
    for data in objects_data:
        offsets.append(pos)
        pos += len(data)

    xref_offset = pos
    num_objs = len(objects_data) + 1

    xref_lines = ["xref", f"0 {num_objs}", "0000000000 65535 f "]
    for off in offsets:
        xref_lines.append(f"{off:010d} 00000 n ")

    xref_lines.extend(
        [
            f"trailer\n<</Size {num_objs} /Root 1 0 R>>",
            f"startxref\n{xref_offset}",
            "%%EOF\n",
        ]
    )

    xref_bytes = "\n".join(xref_lines).encode("latin-1")

    with open(output_path, "wb") as f:
        f.write(header.encode("latin-1"))
        for data in objects_data:
            f.write(data)
        f.write(xref_bytes)


def generer_pdf_physique_integre(
    doc_type, membre, association, montant, saison, mode_paiement, output_path
):
    """Fonction relais."""
    generer_pdf_zero_dep(
        output_path=output_path,
        assoc=association,
        membre=membre,
        doc_type=doc_type,
        montant=montant,
        saison=saison,
    )


class PdfViewerView(ft.Container):

    def __init__(self, app, membre=None):
        super().__init__(expand=True)
        self.app = app
        
        # Récupération multi-sources avec repli automatique
        self.association = (
            getattr(self.app, "association", None)
            or getattr(self.app, "mails", None)
            or getattr(self.app, "mail", None)
            or getattr(self.app, "config", None)
            or {}
        )
        self.accent_color = self.association.get("accent_color", "#1E3A8A")

        self.selected_membre = membre or getattr(
            self.app, "membre_selectionne", None
        )
        self.current_pdf_path = None
        self.current_zoom = 1.0
        self.selected_doc_type = "attestation"

        self.save_file_picker = ft.FilePicker(
            on_result=self.on_save_pdf_result
        )
        self.import_file_picker = ft.FilePicker(
            on_result=self.on_import_pdf_result
        )

        self.txt_recherche_fichier = ft.TextField(
            label="Rechercher un document...",
            prefix_icon=get_icon("SEARCH"),
            expand=True,
            on_change=self.filtrer_fichiers_saison,
        )
        self.list_fichiers_saison = ft.ListView(
            expand=True, spacing=5, padding=5
        )

        self.dropdown_membres = ft.Dropdown(
            label="Choisir un adhérent", on_change=self.on_membre_changed
        )
        self.remplir_dropdown_membres()

        self.docs_list_options = [
            {"key": "attestation", "label": "📜 Attestation de Cotisation"},
            {"key": "fiche", "label": "📄 Fiche Synthétique Adhérent"},
            {"key": "recu", "label": "🧾 Reçu de Paiement"},
            {"key": "licence", "label": "🏅 Attestation de Licence & Adhésion"},
        ]
        self.checkboxes_doc_types = {}
        self.col_doc_types = ft.Column(spacing=5)
        self.construire_liste_checkboxes_docs()

        self.input_montant = ft.TextField(
            label="Montant réglé (€)",
            value="150.00",
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
            on_change=self.rafraichir_apercu_auto,
        )
        saison_act = getattr(self.app, "saison_active", "2025-2026")
        self.input_saison = ft.TextField(
            label="Saison Sportive",
            value=str(saison_act),
            expand=True,
            on_change=self.rafraichir_apercu_auto,
        )

        self.container_options_attestation = ft.Container(
            visible=True,
            content=ft.Row(
                [self.input_montant, self.input_saison], spacing=10
            ),
        )

        self.txt_status = ft.Text(
            "Sélectionnez un adhérent", color="gray", italic=True, size=12
        )

        self.btn_generer = ft.ElevatedButton(
            text="Générer l'Aperçu",
            icon=get_icon("PREVIEW"),
            bgcolor=self.accent_color,
            color="white",
            disabled=True,
            on_click=self.generer_apercu_integre,
        )
        self.btn_sauvegarder = ft.ElevatedButton(
            text="Exporter",
            icon=get_icon("SAVE_ALT"),
            bgcolor="green",
            color="white",
            disabled=True,
            on_click=self.demander_lieu_sauvegarde,
        )
        self.btn_email = ft.OutlinedButton(
            text="Envoyer Mail",
            icon=get_icon("EMAIL"),
            disabled=True,
            on_click=self.ouvrir_dialogue_email,
        )

        self.btn_toolbar_open = ft.ElevatedButton(
            text="Ouvrir PDF",
            icon=get_icon("OPEN_IN_NEW"),
            bgcolor="indigo",
            color="white",
            disabled=True,
            on_click=lambda e: self.ouvrir_pdf_externe(),
        )
        self.btn_toolbar_print = ft.ElevatedButton(
            text="Imprimer",
            icon=get_icon("PRINT"),
            bgcolor="blue",
            color="white",
            disabled=True,
            on_click=self.imprimer_document,
        )
        self.btn_toolbar_export = ft.ElevatedButton(
            text="Exporter",
            icon=get_icon("SAVE_ALT"),
            bgcolor="green",
            color="white",
            disabled=True,
            on_click=self.demander_lieu_sauvegarde,
        )
        self.btn_toolbar_email = ft.ElevatedButton(
            text="Envoyer Mail",
            icon=get_icon("EMAIL"),
            bgcolor=self.accent_color,
            color="white",
            disabled=True,
            on_click=self.ouvrir_dialogue_email,
        )

        self.txt_zoom_val = ft.Text("100%", weight="bold", size=12)
        self.txt_nom_doc_ouvert = ft.Text(
            "Aucun document ouvert",
            weight="bold",
            size=13,
            color="#93C5FD",
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        self.toolbar_preview = ft.Container(
            bgcolor="#1F2937",
            padding=8,
            border_radius=8,
            content=ft.Row(
                scroll=ft.ScrollMode.AUTO,
                spacing=10,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        [
                            ft.Icon(
                                get_icon("PICTURE_AS_PDF"),
                                color="red",
                                size=20,
                            ),
                            self.txt_nom_doc_ouvert,
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        [
                            ft.IconButton(
                                get_icon("ZOOM_OUT"),
                                icon_size=18,
                                on_click=self.zoom_out,
                            ),
                            self.txt_zoom_val,
                            ft.IconButton(
                                get_icon("ZOOM_IN"),
                                icon_size=18,
                                on_click=self.zoom_in,
                            ),
                            ft.IconButton(
                                get_icon("ZOOM_OUT_MAP"),
                                icon_size=18,
                                on_click=self.zoom_reset,
                            ),
                        ],
                        spacing=2,
                    ),
                    ft.Row(
                        [
                            self.btn_toolbar_open,
                            self.btn_toolbar_print,
                            self.btn_toolbar_export,
                            self.btn_toolbar_email,
                        ],
                        spacing=6,
                    ),
                ],
            ),
        )

        self.preview_placeholder = ft.Column(
            [
                ft.Icon(get_icon("PICTURE_AS_PDF"), size=60, color="gray"),
                ft.Text(
                    "L'aperçu du document s'affichera ici.",
                    color="gray",
                    italic=True,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        )

        self.preview_display_box = ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=self.preview_placeholder,
        )

        self.tabs_controle = ft.Tabs(
            selected_index=1,
            animation_duration=200,
            expand=True,
            tabs=[
                ft.Tab(
                    text=f"Archives ({saison_act})",
                    content=ft.Container(
                        padding=10,
                        content=ft.Column(
                            [
                                ft.Row([
                                    self.txt_recherche_fichier,
                                    ft.IconButton(
                                        icon=get_icon("FILE_UPLOAD"),
                                        bgcolor=self.accent_color,
                                        icon_color="white",
                                        on_click=lambda e: self.import_file_picker.pick_files(
                                            allowed_extensions=["pdf"]
                                        ),
                                    ),
                                ]),
                                ft.Divider(height=1),
                                self.list_fichiers_saison,
                            ],
                            expand=True,
                        ),
                    ),
                ),
                ft.Tab(
                    text="Générateur",
                    content=ft.Container(
                        padding=10,
                        content=ft.Column(
                            [
                                self.dropdown_membres,
                                ft.Text(
                                    "Type de document :",
                                    weight="bold",
                                    size=12,
                                ),
                                self.col_doc_types,
                                self.container_options_attestation,
                                ft.Divider(height=1),
                                self.txt_status,
                                self.btn_generer,
                                ft.Row(
                                    [self.btn_sauvegarder, self.btn_email],
                                    wrap=True,
                                    spacing=10,
                                    run_spacing=10,
                                ),
                            ],
                            spacing=12,
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                    ),
                ),
            ],
        )

        left_panel = ft.Container(
            col={"sm": 12, "md": 5, "lg": 4},
            bgcolor="#1F2937",
            padding=8,
            border_radius=10,
            height=500,
            content=self.tabs_controle,
        )

        right_panel = ft.Container(
            col={"sm": 12, "md": 7, "lg": 8},
            bgcolor="#111827",
            padding=12,
            border_radius=10,
            height=620,
            content=ft.Column(
                [self.toolbar_preview, self.preview_display_box],
                expand=True,
                spacing=10,
            ),
        )

        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=15,
            controls=[
                ft.Row([
                    ft.Icon(
                        get_icon("DOCUMENT_SCANNER"),
                        size=26,
                        color=self.accent_color,
                    ),
                    ft.Text(
                        "Gestionnaire & Générateur de Documents",
                        size=18,
                        weight="bold",
                    ),
                ]),
                ft.Divider(height=1),
                ft.ResponsiveRow([left_panel, right_panel], spacing=15),
            ],
        )

        self.charger_fichiers_saison()

        membres_list = getattr(self.app, "membres", [])
        if self.selected_membre and membres_list:
            for idx, m in enumerate(membres_list):
                if m == self.selected_membre:
                    self.dropdown_membres.value = str(idx)
                    self.btn_generer.disabled = False
                    self.set_action_buttons_state(True)
                    self.generer_apercu_integre(None)
                    break

    def safe_update(self):
        if self.page:
            self.update()

    def did_mount(self):
        if self.page:
            self.page.overlay.extend(
                [self.save_file_picker, self.import_file_picker]
            )
            self.page.update()

    def afficher_snackbar(self, message: str, color: str):
        if self.page:
            sb = ft.SnackBar(content=ft.Text(message), bgcolor=color)
            self.page.snack_bar = sb
            sb.open = True
            self.page.update()

    def set_action_buttons_state(self, enabled: bool):
        self.btn_sauvegarder.disabled = not enabled
        self.btn_email.disabled = not enabled
        self.btn_toolbar_open.disabled = not enabled
        self.btn_toolbar_print.disabled = not enabled
        self.btn_toolbar_export.disabled = not enabled
        self.btn_toolbar_email.disabled = not enabled

    def construire_liste_checkboxes_docs(self):
        self.col_doc_types.controls.clear()
        self.checkboxes_doc_types.clear()

        for doc in self.docs_list_options:
            key = doc["key"]
            is_checked = key == self.selected_doc_type

            cb = ft.Checkbox(
                label=doc["label"],
                value=is_checked,
                on_change=lambda e, k=key: self.on_checkbox_doc_changed(k),
            )

            item_container = ft.Container(
                content=cb,
                padding=5,
                border_radius=6,
                ink=True,
                bgcolor="#111827" if is_checked else None,
                on_click=lambda e, k=key: self.on_checkbox_doc_changed(k),
            )

            self.checkboxes_doc_types[key] = (cb, item_container)
            self.col_doc_types.controls.append(item_container)

    def on_checkbox_doc_changed(self, selected_key):
        self.selected_doc_type = selected_key
        for key, (cb, container) in self.checkboxes_doc_types.items():
            checked = key == selected_key
            cb.value = checked
            container.bgcolor = "#111827" if checked else None

        self.container_options_attestation.visible = selected_key in [
            "attestation",
            "recu",
        ]
        self.safe_update()

        if self.selected_membre:
            self.generer_apercu_integre(None)

    def get_dossier_fichiers_saison(self) -> Path:
        data_dir = getattr(self.app, "data_dir", Path.cwd())
        saison_act = getattr(self.app, "saison_active", "2025-2026")
        docs_dir = Path(data_dir) / "asso" / str(saison_act) / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir

    def charger_fichiers_saison(self, filtre=""):
        self.list_fichiers_saison.controls.clear()
        dossier = self.get_dossier_fichiers_saison()

        if dossier.exists():
            files = sorted(
                dossier.glob("*.pdf"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for filepath in files:
                if filtre and filtre.lower() not in filepath.name.lower():
                    continue
                self.list_fichiers_saison.controls.append(
                    ft.Container(
                        bgcolor="#111827",
                        padding=8,
                        border_radius=6,
                        ink=True,
                        on_click=lambda e, p=filepath: self.ouvrir_pdf_existant(
                            p
                        ),
                        content=ft.Row([
                            ft.Icon(
                                get_icon("PICTURE_AS_PDF"),
                                color="red",
                                size=18,
                            ),
                            ft.Text(
                                filepath.name,
                                size=12,
                                weight="bold",
                                expand=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.IconButton(
                                get_icon("DELETE_OUTLINE"),
                                icon_size=16,
                                icon_color="red",
                                on_click=lambda e, p=filepath: self.supprimer_fichier_archive(
                                    p
                                ),
                            ),
                        ]),
                    )
                )
        self.safe_update()

    def filtrer_fichiers_saison(self, e):
        self.charger_fichiers_saison(filtre=self.txt_recherche_fichier.value)

    def supprimer_fichier_archive(self, filepath: Path):
        if filepath.exists():
            filepath.unlink()
        self.charger_fichiers_saison()
        if self.current_pdf_path == filepath:
            self.current_pdf_path = None
            self.txt_nom_doc_ouvert.value = "Aucun document ouvert"
            self.set_action_buttons_state(False)
            self.preview_display_box.content = self.preview_placeholder
        self.safe_update()

    def on_import_pdf_result(self, e: ft.FilePickerResultEvent):
        if e.files:
            source = Path(e.files[0].path)
            cible = self.get_dossier_fichiers_saison() / source.name
            shutil.copy(source, cible)
            self.charger_fichiers_saison()
            self.ouvrir_pdf_existant(cible)

    def ouvrir_pdf_existant(self, filepath: Path):
        if not filepath.exists():
            return
        self.current_pdf_path = filepath
        self.txt_nom_doc_ouvert.value = filepath.name
        self.set_action_buttons_state(True)

        filename_lower = filepath.stem.lower()
        membres_list = getattr(self.app, "membres", [])
        for m in membres_list:
            nom = str(m.get("nom", "")).lower().strip()
            prenom = str(m.get("prenom", "")).lower().strip()
            if (
                nom
                and prenom
                and (nom in filename_lower and prenom in filename_lower)
            ):
                self.selected_membre = m
                break

        self.afficher_page_preview()

    def remplir_dropdown_membres(self):
        self.dropdown_membres.options.clear()
        membres_list = getattr(self.app, "membres", [])
        for i, m in enumerate(membres_list):
            self.dropdown_membres.options.append(
                ft.dropdown.Option(
                    str(i), f"{m.get('nom', '').upper()} {m.get('prenom', '')}"
                )
            )

    def on_membre_changed(self, e):
        if self.dropdown_membres.value:
            membres_list = getattr(self.app, "membres", [])
            self.selected_membre = membres_list[
                int(self.dropdown_membres.value)
            ]
            self.btn_generer.disabled = False
            self.set_action_buttons_state(True)
            self.generer_apercu_integre(None)

    def rafraichir_apercu_auto(self, e):
        if self.selected_membre:
            self.generer_apercu_integre(None)

    def generer_apercu_integre(self, e):
        if not self.selected_membre:
            return

        doc_type = self.selected_doc_type
        nom_fic = f"{doc_type}_{self.selected_membre.get('nom','doc')}_{self.selected_membre.get('prenom','')}.pdf".lower()
        self.current_pdf_path = self.get_dossier_fichiers_saison() / nom_fic
        self.txt_nom_doc_ouvert.value = nom_fic

        # Synchronisation prioritaire multi-sources des données association
        self.association = (
            getattr(self.app, "association", None)
            or getattr(self.app, "mails", None)
            or getattr(self.app, "mail", None)
            or getattr(self.app, "config", None)
            or {}
        )

        try:
            generer_pdf_physique_integre(
                doc_type=doc_type,
                membre=self.selected_membre,
                association=self.association,
                montant=self.input_montant.value,
                saison=self.input_saison.value,
                mode_paiement="",
                output_path=self.current_pdf_path,
            )
            self.txt_status.value = "Document PDF officiel généré."
            self.txt_status.color = "green"
        except Exception as ex:
            err_detail = traceback.format_exc()
            print(f"Erreur création PDF :\n{err_detail}")
            self.txt_status.value = f"Erreur génération PDF : {ex}"
            self.txt_status.color = "red"

        self.set_action_buttons_state(True)
        self.afficher_page_preview()
        self.charger_fichiers_saison()

    def ouvrir_pdf_externe(self, filepath=None):
        target = filepath or self.current_pdf_path
        if not target or not Path(target).exists():
            self.afficher_snackbar("Aucun document à ouvrir", "red")
            return

        abs_path = Path(target).resolve()

        try:
            if platform.system() == "Windows":
                os.startfile(str(abs_path))
            else:
                public_download = Path("/storage/emulated/0/Download")
                if public_download.exists():
                    dest_path = public_download / abs_path.name
                    shutil.copy(abs_path, dest_path)
                    if self.page:
                        self.page.launch_url(f"file://{dest_path}")
                    self.afficher_snackbar(
                        "Copié dans Téléchargements et ouvert !", "green"
                    )
                else:
                    if self.page:
                        self.page.launch_url(f"file://{abs_path}")
        except Exception as ex:
            print("Erreur ouverture externe :", ex)
            self.afficher_snackbar(
                f"Impossible d'ouvrir le fichier : {ex}", "red"
            )

    def afficher_page_preview(self):
        m = self.selected_membre or {}
        assoc = self.association
        asso_info = extraire_infos_asso(assoc)

        nom_assoc = asso_info["nom"].upper()
        rna = asso_info["rna"]
        siret = asso_info["siret"]
        adresse_complete_assoc = asso_info["adresse"]
        tel_assoc = asso_info["tel"]
        email_assoc = asso_info["email"]
        president = asso_info["president"]

        logo_path = assoc.get("logo_path") or assoc.get("logo") if assoc else None
        stamp_path = (
            (assoc.get("tampon_path") or assoc.get("stamp") or assoc.get("tampon"))
            if assoc
            else None
        )
        sig_path = (
            (assoc.get("signature_path") or assoc.get("signature"))
            if assoc
            else None
        )

        nom = str(m.get("nom", "")).upper()
        prenom = str(m.get("prenom", "")).capitalize()
        nom_complet = f"{nom} {prenom}".strip() or "MEMBRE INCONNU"

        adresse_m = str(m.get("adresse") or m.get("rue") or "Non renseignée")
        cp_ville_m = f"{m.get('code_postal', '')} {m.get('ville', '')}".strip()
        email_m = str(m.get("email") or "Non renseigné")
        tel_m = str(m.get("telephone") or m.get("tel") or "Non renseigné")
        dob_m = str(m.get("date_naissance") or "Non renseignée")
        
        licence_m = str(
            m.get("licence") or m.get("licence_federale") or m.get("licence_ffk") or "Non renseignée"
        )
        grade_m = str(
            m.get("niveau") or m.get("grade") or m.get("grade_actuel") or "Non renseigné"
        )

        montant_val = self.input_montant.value
        saison_val = self.input_saison.value
        date_jour = datetime.now().strftime("%d/%m/%Y")

        titres_docs = {
            "attestation": "ATTESTATION DE COTISATION",
            "recu": "REÇU DE PAIEMENT",
            "licence": "ATTESTATION DE LICENCE & AFFILIATION",
            "fiche": "FICHE SYNOPTIQUE ADHÉRENT",
        }
        titre_affiche = titres_docs.get(
            self.selected_doc_type, "DOCUMENT OFFICIEL"
        )
        base_width = int(350 * self.current_zoom)

        header_controls = []
        if logo_path and Path(logo_path).exists():
            header_controls.append(
                ft.Image(
                    src=str(logo_path),
                    width=45,
                    height=45,
                    fit=ft.ImageFit.CONTAIN,
                )
            )

        header_controls.append(
            ft.Column(
                [
                    ft.Text(
                        nom_assoc, weight="bold", color="#1E3A8A", size=11
                    ),
                    ft.Text(
                        f"Adresse : {adresse_complete_assoc}",
                        size=8,
                        color="#475569",
                    ),
                    ft.Text(
                        f"Tél : {tel_assoc}  |  E-mail : {email_assoc}",
                        size=8,
                        color="#475569",
                    ),
                    ft.Text(f"SIRET : {siret}  |  RNA : {rna}", size=7, color="#64748B"),
                ],
                spacing=1,
                expand=True,
            )
        )

        signature_box_controls = []
        if stamp_path and Path(stamp_path).exists():
            signature_box_controls.append(
                ft.Image(
                    src=str(stamp_path),
                    width=49,
                    height=38,
                    fit=ft.ImageFit.CONTAIN,
                )
            )

        if sig_path and Path(sig_path).exists():
            signature_box_controls.append(
                ft.Image(
                    src=str(sig_path),
                    width=114,
                    height=60,
                    fit=ft.ImageFit.CONTAIN,
                )
            )

        if not signature_box_controls:
            signature_box_controls.append(ft.Container(height=35))

        body_widgets = []
        if self.selected_doc_type == "recu":
            body_widgets.extend([
                ft.Text(
                    f"Je soussigné(e), {president}, certifie avoir reçu de"
                    " l'adhérent(e) :",
                    size=9,
                    color="black",
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"Payeur : {nom_complet}",
                                weight="bold",
                                color="black",
                                size=10,
                            ),
                            ft.Text(
                                f"Adresse : {adresse_m} {cp_ville_m}".strip(),
                                color="#334155",
                                size=9,
                            ),
                            ft.Text(
                                f"Contact : {tel_m} - {email_m}",
                                color="#334155",
                                size=9,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"Objet : Cotisation annuelle saison {saison_val}",
                                color="black",
                                size=9,
                            ),
                            ft.Text(
                                f"Montant perçu : {montant_val} €",
                                weight="bold",
                                color="green",
                                size=10,
                            ),
                            ft.Text(
                                "Statut : Règlement soldé",
                                color="#334155",
                                size=9,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
            ])
        elif self.selected_doc_type == "licence":
            body_widgets.extend([
                ft.Text(
                    f"Je soussigné(e), {president}, agissant en qualité de"
                    " Président(e), atteste que :",
                    size=9,
                    color="black",
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"Licencié(e) : {nom_complet}",
                                weight="bold",
                                color="black",
                                size=10,
                            ),
                            ft.Text(
                                f"Né(e) le : {dob_m}", color="#334155", size=9
                            ),
                            ft.Text(
                                f"Club : {nom_assoc}", color="#334155", size=9
                            ),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"N° de Licence : {licence_m}",
                                weight="bold",
                                color="#1E3A8A",
                                size=10,
                            ),
                            ft.Text(
                                f"Niveau / Grade : {grade_m}",
                                color="black",
                                size=9,
                            ),
                            ft.Text(
                                f"Saison de validité : {saison_val}",
                                color="#334155",
                                size=9,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
            ])
        elif self.selected_doc_type == "fiche":
            body_widgets.extend([
                ft.Text(
                    "Fiche récapitulative des informations du membre pour la"
                    f" saison {saison_val} :",
                    size=9,
                    color="black",
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"Adhérent : {nom_complet}",
                                weight="bold",
                                color="black",
                                size=10,
                            ),
                            ft.Text(
                                f"Date de Naissance : {dob_m}",
                                color="#334155",
                                size=9,
                            ),
                            ft.Text(
                                f"Adresse : {adresse_m} {cp_ville_m}".strip(),
                                color="#334155",
                                size=9,
                            ),
                            ft.Text(
                                f"Contact : {tel_m} - {email_m}",
                                color="#334155",
                                size=9,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"Licence N° : {licence_m}",
                                color="#334155",
                                size=9,
                            ),
                            ft.Text(
                                f"Niveau / Grade : {grade_m}", color="#334155", size=9
                            ),
                            ft.Text(
                                f"Cotisation : {montant_val} €",
                                color="green",
                                weight="bold",
                                size=9,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
            ])
        else:
            body_widgets.extend([
                ft.Text(
                    f"Je soussigné(e), {president}, agissant en qualité de"
                    f" Président(e) de l'association {nom_assoc}, atteste par"
                    " la présente que :",
                    size=9,
                    color="black",
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                f"Adhérent : {nom_complet}",
                                weight="bold",
                                color="black",
                                size=10,
                            ),
                            ft.Text(
                                f"Né(e) le : {dob_m}", color="#334155", size=9
                            ),
                            ft.Text(
                                f"Adresse : {adresse_m} {cp_ville_m}".strip(),
                                color="#334155",
                                size=9,
                            ),
                            ft.Text(
                                f"Tél : {tel_m}  |  E-mail : {email_m}",
                                color="#334155",
                                size=9,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(height=6),
                ft.Container(
                    bgcolor="#F8FAFC",
                    padding=8,
                    border=ft.border.all(1, "#E2E8F0"),
                    border_radius=4,
                    content=ft.Column(
                        [
                            ft.Text(
                                "A acquitté la cotisation pour la saison :"
                                f" {saison_val}",
                                color="black",
                                size=9,
                            ),
                            ft.Text(
                                f"Montant réglé : {montant_val} €",
                                weight="bold",
                                color="green",
                                size=10,
                            ),
                            ft.Text(
                                f"Licence N° : {licence_m}  |  Niveau/Grade :"
                                f" {grade_m}",
                                color="#334155",
                                size=9,
                            ),
                        ],
                        spacing=2,
                    ),
                ),
            ])

        feuille_a4 = ft.Container(
            width=base_width,
            bgcolor="white",
            padding=18,
            border_radius=4,
            shadow=ft.BoxShadow(blur_radius=8, color="black38"),
            content=ft.Column(
                [
                    ft.Row(header_controls, spacing=8),
                    ft.Divider(color="gray", thickness=1, height=10),
                    ft.Container(
                        alignment=ft.alignment.center,
                        padding=6,
                        bgcolor="#F0F4F8",
                        border_radius=4,
                        border=ft.border.all(1, "#CBD5E1"),
                        content=ft.Text(
                            titre_affiche,
                            weight="bold",
                            color="#1E3A8A",
                            size=10,
                        ),
                    ),
                    ft.Container(height=6),
                    *body_widgets,
                    ft.Container(height=8),
                    ft.Text(
                        "La présente attestation est délivrée à l'intéressé(e)"
                        " pour servir et valoir ce que de droit.",
                        size=9,
                        italic=True,
                        color="black",
                    ),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Container(expand=True),
                        ft.Container(
                            width=175,
                            padding=6,
                            border=ft.border.all(1, "#1E3A8A"),
                            border_radius=4,
                            bgcolor=None,
                            content=ft.Column(
                                [
                                    ft.Text(
                                        f"Fait à {asso_info['ville']}, le"
                                        f" {date_jour}",
                                        size=8,
                                        weight="bold",
                                        color="#1E3A8A",
                                    ),
                                    ft.Text(
                                        f"Le Président : {president}",
                                        size=7.5,
                                        color="#334155",
                                    ),
                                    ft.Container(height=2),
                                    ft.Row(
                                        signature_box_controls,
                                        alignment=ft.MainAxisAlignment.SPACE_AROUND,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ),
                    ]),
                    ft.Container(height=8),
                    ft.ElevatedButton(
                        "📄 Ouvrir le PDF officiel",
                        icon=get_icon("OPEN_IN_NEW"),
                        bgcolor="indigo",
                        color="white",
                        style=ft.ButtonStyle(padding=6),
                        on_click=lambda e: self.ouvrir_pdf_externe(),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
        )

        self.txt_zoom_val.value = f"{int(self.current_zoom * 100)}%"
        self.preview_display_box.content = ft.Column(
            [
                ft.Text(
                    "Aperçu du document imprimable",
                    color="gray",
                    size=10,
                    italic=True,
                ),
                feuille_a4,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )

        self.safe_update()

    def zoom_in(self, e):
        if self.current_zoom < 1.8:
            self.current_zoom += 0.15
            self.afficher_page_preview()

    def zoom_out(self, e):
        if self.current_zoom > 0.6:
            self.current_zoom -= 0.15
            self.afficher_page_preview()

    def zoom_reset(self, e):
        self.current_zoom = 1.0
        self.afficher_page_preview()

    def get_system_printers(self) -> list:
        printers = []
        try:
            sys_name = platform.system()
            if sys_name == "Windows":
                cmd = [
                    "powershell",
                    "-Command",
                    "Get-Printer | Select-Object -ExpandProperty Name",
                ]
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    creationflags=flags,
                )
                printers = [
                    line.strip()
                    for line in res.stdout.splitlines()
                    if line.strip()
                ]
            elif sys_name in ["Linux", "Darwin"]:
                cmd = ["lpstat", "-e"]
                res = subprocess.run(
                    cmd, capture_output=True, text=True, check=True
                )
                printers = [
                    line.strip()
                    for line in res.stdout.strip().splitlines()
                    if line.strip()
                ]
        except Exception as ex:
            print("Erreur impression :", ex)
        return printers

    def lancer_impression_systeme(self, printer_name=None):
        sys_name = platform.system()
        filepath = str(self.current_pdf_path.resolve())

        if sys_name == "Windows":
            if printer_name:
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                cmd = [
                    "powershell",
                    "-Command",
                    f"Start-Process -FilePath '{filepath}' -Verb PrintTo"
                    f" -ArgumentList '\"{printer_name}\"' -ErrorAction Stop",
                ]
                res = subprocess.run(
                    cmd, capture_output=True, text=True, creationflags=flags
                )
                if res.returncode != 0:
                    os.startfile(filepath, "print")
            else:
                os.startfile(filepath, "print")
        elif sys_name in ["Linux", "Darwin"]:
            cmd = (
                ["lp", "-d", printer_name, filepath]
                if printer_name
                else ["lp", filepath]
            )
            subprocess.run(cmd, check=True)
        else:
            self.ouvrir_pdf_externe()

    def imprimer_document(self, e):
        if not self.current_pdf_path or not self.current_pdf_path.exists():
            return

        printers = self.get_system_printers()

        if not printers:
            self.ouvrir_pdf_externe()
            self.afficher_snackbar(
                "Ouverture du lecteur pour impression...", "blue"
            )
            return

        dd_imprimantes = ft.Dropdown(
            label="Imprimantes détectées",
            options=[ft.dropdown.Option(p) for p in printers],
            value=printers[0],
            expand=True,
        )

        def fermer_dialogue(evt=None):
            dlg.open = False
            if self.page:
                self.page.update()

        def valider_impression(evt):
            imprimante_choisie = dd_imprimantes.value
            fermer_dialogue()
            try:
                self.lancer_impression_systeme(imprimante_choisie)
                self.afficher_snackbar(
                    f"Impression lancée sur '{imprimante_choisie}' !", "green"
                )
            except Exception as ex:
                self.afficher_snackbar(f"Erreur d'impression : {ex}", "red")

        dlg = ft.AlertDialog(
            title=ft.Text("Sélection d'Imprimante"),
            content=ft.Container(
                width=360,
                height=120,
                content=ft.Column([
                    ft.Text("Choisissez l'appareil de destination :", size=12),
                    dd_imprimantes,
                ], spacing=10),
            ),
            actions=[
                ft.TextButton("Annuler", on_click=fermer_dialogue),
                ft.ElevatedButton(
                    "Imprimer",
                    bgcolor=self.accent_color,
                    color="white",
                    on_click=valider_impression,
                ),
            ],
        )

        if self.page:
            self.page.overlay.append(dlg)
            dlg.open = True
            self.page.update()

    def demander_lieu_sauvegarde(self, e):
        if self.current_pdf_path and self.current_pdf_path.exists():
            self.save_file_picker.save_file(
                file_name=self.current_pdf_path.name,
                allowed_extensions=["pdf"],
            )

    def on_save_pdf_result(self, e: ft.FilePickerResultEvent):
        if e.path and self.current_pdf_path:
            shutil.copy(self.current_pdf_path, e.path)
            self.afficher_snackbar("Document exporté avec succès !", "green")

    def ouvrir_dialogue_email(self, e):
        if not self.current_pdf_path or not self.current_pdf_path.exists():
            return

        email_dest = ""
        if self.selected_membre and self.selected_membre.get("email"):
            email_dest = str(self.selected_membre.get("email", ""))

        assoc = self.association
        asso_info = extraire_infos_asso(assoc)
        nom_club = asso_info["nom"]

        txt_dest = ft.TextField(
            label="Destinataire (Email)", value=email_dest, expand=True
        )
        txt_objet = ft.TextField(
            label="Objet", value=f"Document officiel - {nom_club}", expand=True
        )
        txt_corps = ft.TextField(
            label="Message",
            value=(
                "Bonjour,\n\nVeuillez trouver ci-joint votre document"
                " officiel.\n\nCordialement,"
            ),
            multiline=True,
            min_lines=3,
            expand=True,
        )

        def envoyer(evt):
            user = str(assoc.get("email") or DEFAULT_ASSOC["email"])
            pwd = str(assoc.get("smtp_password") or "")
            if not pwd:
                self.afficher_snackbar(
                    "Erreur : Mot de passe SMTP non configuré dans l'application.", "red"
                )
                return

            try:
                msg = MIMEMultipart()
                msg["From"] = user
                msg["To"] = txt_dest.value
                msg["Subject"] = txt_objet.value
                msg.attach(MIMEText(txt_corps.value, "plain"))

                with open(self.current_pdf_path, "rb") as f:
                    part = MIMEApplication(
                        f.read(), Name=self.current_pdf_path.name
                    )
                    part["Content-Disposition"] = (
                        'attachment; filename="'
                        f'{self.current_pdf_path.name}"'
                    )
                    msg.attach(part)

                server = smtplib.SMTP(
                    str(assoc.get("smtp_server", "smtp.gmail.com")),
                    int(assoc.get("smtp_port", 587)),
                )
                server.starttls()
                server.login(user, pwd.replace(" ", ""))
                server.send_message(msg)
                server.quit()

                dlg.open = False
                if self.page:
                    self.page.update()

                self.afficher_snackbar(
                    f"E-mail envoyé à {txt_dest.value} !", "green"
                )
            except Exception as ex:
                print("Erreur mail :", ex)
                self.afficher_snackbar(f"Échec de l'envoi : {ex}", "red")

        dlg = ft.AlertDialog(
            title=ft.Text("Envoyer par e-mail"),
            content=ft.Container(
                width=380,
                height=300,
                content=ft.Column([txt_dest, txt_objet, txt_corps], spacing=10),
            ),
            actions=[
                ft.TextButton(
                    "Annuler",
                    on_click=lambda e: (
                        setattr(dlg, "open", False),
                        self.page.update() if self.page else None,
                    ),
                ),
                ft.ElevatedButton(
                    "Envoyer",
                    bgcolor=self.accent_color,
                    color="white",
                    on_click=envoyer,
                ),
            ],
        )
        if self.page:
            self.page.overlay.append(dlg)
            dlg.open = True
            self.page.update()