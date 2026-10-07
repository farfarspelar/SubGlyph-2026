import re
import tkinter as tk
import math
import json
import mimetypes
import os
import platform
import webbrowser
import subprocess
import sys
import traceback
from dataclasses import replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.message import EmailMessage
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from access_control import AccessControl
from typing import Callable, Iterable
from PIL import Image, ImageDraw, ImageFont
from nc_geometry import (
    FrontMarking, MantleMarking, front_marking_blocks, mantle_marking_blocks,
    marking_text_width,
)
from dynamic_marking import DynamicMarking, FanucDynamicPost, KINDS, DATE_FORMATS, format_date
from system_font import system_fonts
from additional_translations import (
    BOSNIAN_SUPPORT_TRANSLATIONS,
    BOSNIAN_TRANSLATIONS,
    POLISH_SUPPORT_TRANSLATIONS,
    POLISH_TRANSLATIONS,
)


APP_VERSION = "1.12-test"
PRODUCT_NAME = "SubGlyph 2026"
PROJECT_FORMAT_VERSION = 2
MARKING_ROW_COUNT = 6
BUY_ME_A_COFFEE_URL = "https://buymeacoffee.com/FarfarSpelar"
SUPPORT_EMAIL = "subglyph@gmail.com"
ORIENTATION_ALONG_Z = "Längs Z-axeln"
ORIENTATION_AROUND_CIRCUMFERENCE = "Runt omkretsen"
FANUC_ISO = "FANUC (ISO)"
OKUMA_OSP_ISO = "OKUMA OSP (ISO)"
SIEMENS_SINUMERIK_ISO = "SIEMENS SINUMERIK (ISO)"
CONTROL_SYSTEMS = (FANUC_ISO, OKUMA_OSP_ISO, SIEMENS_SINUMERIK_ISO)
LEGACY_CONTROL_SYSTEMS = {
    "Fanuc": FANUC_ISO,
    "Okuma": OKUMA_OSP_ISO,
}
LEGACY_ORIENTATIONS = {
    "Axiell": ORIENTATION_ALONG_Z,
    "Radiell": ORIENTATION_AROUND_CIRCUMFERENCE,
}


class HoverTooltip:
    """Show unobtrusive contextual help after the pointer rests on a widget."""

    def __init__(self, widget: tk.Widget, text: str | Callable[[], str], delay_ms: int = 3500) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None
        self._outline_windows: list[tk.Toplevel] = []
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: object = None) -> None:
        self._cancel()
        self._show_outline()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _show_outline(self) -> None:
        self._hide_outline()
        if not self.widget.winfo_exists():
            return
        self.widget.update_idletasks()
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty()
        width = self.widget.winfo_width()
        height = self.widget.winfo_height()
        thickness = 2
        rectangles = (
            (x - thickness, y - thickness, width + thickness * 2, thickness),
            (x - thickness, y + height, width + thickness * 2, thickness),
            (x - thickness, y, thickness, height),
            (x + width, y, thickness, height),
        )
        for left, top, rect_width, rect_height in rectangles:
            outline = tk.Toplevel(self.widget)
            outline.wm_overrideredirect(True)
            outline.wm_attributes("-topmost", True)
            outline.configure(background="#2878b5")
            outline.wm_geometry(f"{rect_width}x{rect_height}+{left}+{top}")
            self._outline_windows.append(outline)

    def _hide_outline(self) -> None:
        for outline in self._outline_windows:
            outline.destroy()
        self._outline_windows.clear()

    def _cancel(self) -> None:
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._window is not None or not self.widget.winfo_exists():
            return
        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.wm_attributes("-topmost", True)
        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 18
        window.wm_geometry(f"+{x}+{y}")
        tk.Label(
            window, text=self.text() if callable(self.text) else self.text,
            justify="left", wraplength=380,
            background="#fffbd6", foreground="#202020",
            relief="solid", borderwidth=1, padx=8, pady=6,
        ).pack()
        self._window = window

    def _hide(self, _event: object = None) -> None:
        self._cancel()
        self._hide_outline()
        if self._window is not None:
            self._window.destroy()
            self._window = None


def app_data_directory() -> Path:
    """Return a writable per-user directory for reports and diagnostics."""
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    directory = root / "SubGlyph"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def timestamped_report_path(prefix: str, suffix: str = ".txt") -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return app_data_directory() / f"{prefix}-{stamp}{suffix}"


def directory_history_path() -> Path:
    return app_data_directory() / "directory-history.json"


def load_directory_history(path: Path | None = None) -> dict[str, str]:
    """Load the independent project and NC dialog directories."""
    source = path or directory_history_path()
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        key: value for key, value in data.items()
        if key in ("project", "nc") and isinstance(value, str) and Path(value).is_dir()
    }


def save_directory_history(history: dict[str, str], path: Path | None = None) -> None:
    """Persist dialog directories without putting machine-local paths in SG files."""
    destination = path or directory_history_path()
    destination.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def system_information() -> dict[str, str]:
    return {
        "SubGlyph version": APP_VERSION,
        "Python version": platform.python_version(),
        "Operating system": platform.platform(),
        "Machine": platform.machine(),
        "Executable": sys.executable,
    }


def create_email_draft(
    reply_to: str,
    subject: str,
    body: str,
    attachments: Iterable[Path],
) -> Path:
    message = EmailMessage()
    message["X-Unsent"] = "1"
    message["From"] = reply_to
    message["To"] = SUPPORT_EMAIL
    message["Reply-To"] = reply_to
    message["Subject"] = subject
    message.set_content(body)
    for path in attachments:
        content_type, _encoding = mimetypes.guess_type(path.name)
        main_type, sub_type = (content_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            path.read_bytes(), maintype=main_type, subtype=sub_type, filename=path.name
        )
    destination = timestamped_report_path("SubGlyph-email", ".eml")
    destination.write_bytes(message.as_bytes())
    return destination


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

LANGUAGES = ("Svenska", "Suomi", "Deutsch", "Français", "English", "Bosanski", "Polski")
SUPPORT_TRANSLATIONS = {
    "Suomi": {
        "Rapportera ett fel": "Ilmoita virheestä", "Skicka önskemål": "Lähetä ehdotus",
        "Till:": "Vastaanottaja:", "Din e-postadress:": "Sähköpostiosoitteesi:", "Ämne:": "Aihe:", "Meddelande:": "Viesti:", "Bilagor:": "Liitteet:",
        "Felrapport": "Virheraportti", "Önskemål": "Ehdotus", "Lägg till fil…": "Lisää tiedosto…", "Generera logg": "Luo loki", "Bifoga senaste crashdump": "Liitä uusin kaatumisvedos", "Ta bort": "Poista", "Avbryt": "Peruuta", "Skapa e-postutkast": "Luo sähköpostiluonnos",
        "Välj bilaga": "Valitse liite", "Kunde inte skapa loggen": "Lokia ei voitu luoda", "Diagnoslogg skapad": "Diagnostiikkaloki luotu", "Loggen sparades som:": "Loki tallennettiin nimellä:", "Ingen crashdump": "Ei kaatumisvedosta", "Det finns ingen sparad crashdump att bifoga.": "Liitettävää tallennettua kaatumisvedosta ei ole.",
        "E-postadress saknas": "Sähköpostiosoite puuttuu", "Ange en giltig e-postadress för svar.": "Anna kelvollinen sähköpostiosoite vastausta varten.", "Ofullständig rapport": "Puutteellinen raportti", "Ange både ämne och meddelande.": "Anna sekä aihe että viesti.", "Kunde inte skapa e-postutkastet": "Sähköpostiluonnosta ei voitu luoda", "E-postutkast skapat": "Sähköpostiluonnos luotu", "Utkastet har öppnats i systemets e-postprogram. Kontrollera det och välj Skicka.": "Luonnos on avattu järjestelmän sähköpostiohjelmassa. Tarkista se ja valitse Lähetä.", "Sparat som:": "Tallennettu nimellä:",
    },
    "Deutsch": {
        "Rapportera ett fel": "Fehler melden", "Skicka önskemål": "Wunsch senden",
        "Till:": "An:", "Din e-postadress:": "Ihre E-Mail-Adresse:", "Ämne:": "Betreff:", "Meddelande:": "Nachricht:", "Bilagor:": "Anhänge:",
        "Felrapport": "Fehlerbericht", "Önskemål": "Wunsch", "Lägg till fil…": "Datei hinzufügen…", "Generera logg": "Protokoll erstellen", "Bifoga senaste crashdump": "Letzten Crashdump anhängen", "Ta bort": "Entfernen", "Avbryt": "Abbrechen", "Skapa e-postutkast": "E-Mail-Entwurf erstellen",
        "Välj bilaga": "Anhang auswählen", "Kunde inte skapa loggen": "Protokoll konnte nicht erstellt werden", "Diagnoslogg skapad": "Diagnoseprotokoll erstellt", "Loggen sparades som:": "Protokoll gespeichert unter:", "Ingen crashdump": "Kein Crashdump", "Det finns ingen sparad crashdump att bifoga.": "Es ist kein gespeicherter Crashdump zum Anhängen vorhanden.",
        "E-postadress saknas": "E-Mail-Adresse fehlt", "Ange en giltig e-postadress för svar.": "Geben Sie eine gültige E-Mail-Adresse für die Antwort ein.", "Ofullständig rapport": "Unvollständiger Bericht", "Ange både ämne och meddelande.": "Geben Sie Betreff und Nachricht ein.", "Kunde inte skapa e-postutkastet": "E-Mail-Entwurf konnte nicht erstellt werden", "E-postutkast skapat": "E-Mail-Entwurf erstellt", "Utkastet har öppnats i systemets e-postprogram. Kontrollera det och välj Skicka.": "Der Entwurf wurde im E-Mail-Programm geöffnet. Prüfen Sie ihn und wählen Sie Senden.", "Sparat som:": "Gespeichert unter:",
    },
    "Français": {
        "Rapportera ett fel": "Signaler un problème", "Skicka önskemål": "Envoyer une suggestion",
        "Till:": "À :", "Din e-postadress:": "Votre adresse e-mail :", "Ämne:": "Objet :", "Meddelande:": "Message :", "Bilagor:": "Pièces jointes :",
        "Felrapport": "Rapport de problème", "Önskemål": "Suggestion", "Lägg till fil…": "Ajouter un fichier…", "Generera logg": "Générer le journal", "Bifoga senaste crashdump": "Joindre le dernier rapport de plantage", "Ta bort": "Supprimer", "Avbryt": "Annuler", "Skapa e-postutkast": "Créer le brouillon",
        "Välj bilaga": "Choisir une pièce jointe", "Kunde inte skapa loggen": "Impossible de créer le journal", "Diagnoslogg skapad": "Journal de diagnostic créé", "Loggen sparades som:": "Journal enregistré sous :", "Ingen crashdump": "Aucun rapport de plantage", "Det finns ingen sparad crashdump att bifoga.": "Aucun rapport de plantage enregistré ne peut être joint.",
        "E-postadress saknas": "Adresse e-mail manquante", "Ange en giltig e-postadress för svar.": "Saisissez une adresse e-mail valide pour la réponse.", "Ofullständig rapport": "Rapport incomplet", "Ange både ämne och meddelande.": "Saisissez un objet et un message.", "Kunde inte skapa e-postutkastet": "Impossible de créer le brouillon", "E-postutkast skapat": "Brouillon créé", "Utkastet har öppnats i systemets e-postprogram. Kontrollera det och välj Skicka.": "Le brouillon a été ouvert dans le logiciel de messagerie. Vérifiez-le puis sélectionnez Envoyer.", "Sparat som:": "Enregistré sous :",
    },
    "English": {
        "Rapportera ett fel": "Report a bug", "Skicka önskemål": "Send a request",
        "Till:": "To:", "Din e-postadress:": "Your email address:", "Ämne:": "Subject:", "Meddelande:": "Message:", "Bilagor:": "Attachments:",
        "Felrapport": "Bug report", "Önskemål": "Request", "Lägg till fil…": "Add file…", "Generera logg": "Generate log", "Bifoga senaste crashdump": "Attach latest crash dump", "Ta bort": "Remove", "Avbryt": "Cancel", "Skapa e-postutkast": "Create email draft",
        "Välj bilaga": "Choose attachment", "Kunde inte skapa loggen": "Could not create the log", "Diagnoslogg skapad": "Diagnostic log created", "Loggen sparades som:": "The log was saved as:", "Ingen crashdump": "No crash dump", "Det finns ingen sparad crashdump att bifoga.": "There is no saved crash dump to attach.",
        "E-postadress saknas": "Email address missing", "Ange en giltig e-postadress för svar.": "Enter a valid reply email address.", "Ofullständig rapport": "Incomplete report", "Ange både ämne och meddelande.": "Enter both a subject and a message.", "Kunde inte skapa e-postutkastet": "Could not create the email draft", "E-postutkast skapat": "Email draft created", "Utkastet har öppnats i systemets e-postprogram. Kontrollera det och välj Skicka.": "The draft was opened in the system email application. Review it and select Send.", "Sparat som:": "Saved as:",
    },
}
NC_COMMENT_TRANSLATIONS = {
    "Svenska": {
        "generated_with": "SKAPAT MED SUBGLYPH VERSION",
        "generated_at": "SKAPAT",
    },
    "Suomi": {
        "generated_with": "LUOTU SUBGLYPH-VERSIOLLA",
        "generated_at": "LUOTU",
    },
    "Deutsch": {
        "generated_with": "ERSTELLT MIT SUBGLYPH VERSION",
        "generated_at": "ERSTELLT",
    },
    "Français": {
        "generated_with": "CREE AVEC SUBGLYPH VERSION",
        "generated_at": "CREE LE",
    },
    "English": {
        "generated_with": "CREATED WITH SUBGLYPH VERSION",
        "generated_at": "CREATED",
    },
    "Bosanski": {
        "generated_with": "KREIRANO POMOCU SUBGLYPH VERZIJE",
        "generated_at": "KREIRANO",
    },
    "Polski": {
        "generated_with": "UTWORZONO ZA POMOCA SUBGLYPH W WERSJI",
        "generated_at": "UTWORZONO",
    },
}
TRANSLATIONS = {
    "Suomi": {
        "Arkiv": "Tiedosto", "Om": "Tietoja", "Nytt projekt": "Uusi projekti", "Spara projekt…": "Tallenna projekti…", "Ladda projekt…": "Avaa projekti…", "Avsluta": "Lopeta",
        "Om SubGlyph": "Tietoja SubGlyphista", "Info": "Tietoja", "Hjälp": "Ohje", "Rapportera ett fel…": "Ilmoita virheestä…", "Skicka önskemål…": "Lähetä ehdotus…", "Program": "Ohjelma", "Maskin och yta": "Kone ja pinta", "Märktext": "Merkintäteksti",
        "Förhandsvisning": "Esikatselu", "Ämnesvisning:": "Aihion näyttö:", "Generera NC": "Luo NC-ohjelma", "Språk:": "Kieli:",
        "Öppna i textredigerare efter generering": "Avaa tekstieditorissa luonnin jälkeen",
        "Styrsystem:": "Ohjausjärjestelmä:", "Projektnamn:": "Projektin nimi:", "Programkommentar:": "Ohjelmakommentti:",
        "Spindel:": "Kara:", "Revolver:": "Revolveri:", "Märkyta:": "Merkintäpinta:", "Runt en axel": "Lieriöpinta", "Frontplan": "Päätypinta",
        "Textriktning:": "Tekstin suunta:", "Djupets riktning:": "Kaiverrussyvyyden suunta:", "Maskinen har Y-axel": "Koneessa on Y-akseli", "Arbetsplan:": "Työstötaso:",
        "Detaljdiameter (mm):": "Kappaleen halkaisija (mm):", "Märkdjup (mm):": "Kaiverrussyvyys (mm):", "Frigång (mm):": "Turvaetäisyys (mm):",
        "Nedmatning (mm/min):": "Upotussyöttö (mm/min):", "Gravering (mm/min):": "Kaiverrussyöttö (mm/min):",
        "Programnummer:": "Ohjelmanumero:", "Programnamn:": "Ohjelman nimi:", "Separata märkprogram": "Erilliset merkintäohjelmat", "Text": "Teksti", "Höjd": "Korkeus", "Bredd": "Leveys", "Radie": "Säde", "Spegel": "Peilaus",
    },
    "Deutsch": {
        "Arkiv": "Datei", "Om": "Über", "Nytt projekt": "Neues Projekt", "Spara projekt…": "Projekt speichern…", "Ladda projekt…": "Projekt öffnen…", "Avsluta": "Beenden",
        "Om SubGlyph": "Über SubGlyph", "Info": "Hilfe", "Hjälp": "Hilfe", "Rapportera ett fel…": "Fehler melden…", "Skicka önskemål…": "Wunsch senden…", "Program": "Programm", "Maskin och yta": "Maschine und Fläche", "Märktext": "Gravurtext",
        "Förhandsvisning": "Vorschau", "Ämnesvisning:": "Werkstückanzeige:", "Generera NC": "NC-Programm erzeugen", "Språk:": "Sprache:",
        "Öppna i textredigerare efter generering": "Nach dem Erzeugen im Texteditor öffnen",
        "Styrsystem:": "Steuerung:", "Projektnamn:": "Projektname:", "Programkommentar:": "Programmkommentar:",
        "Spindel:": "Spindel:", "Revolver:": "Revolver:", "Märkyta:": "Gravurfläche:", "Runt en axel": "Mantelfläche", "Frontplan": "Stirnfläche",
        "Textriktning:": "Textausrichtung:", "Djupets riktning:": "Richtung der Gravurtiefe:", "Maskinen har Y-axel": "Maschine mit Y-Achse", "Arbetsplan:": "Bearbeitungsebene:",
        "Detaljdiameter (mm):": "Werkstückdurchmesser (mm):", "Märkdjup (mm):": "Gravurtiefe (mm):", "Frigång (mm):": "Sicherheitsabstand (mm):",
        "Nedmatning (mm/min):": "Eintauchvorschub (mm/min):", "Gravering (mm/min):": "Graviervorschub (mm/min):",
        "Programnummer:": "Programmnummer:", "Programnamn:": "Programmname:", "Separata märkprogram": "Separate Gravurprogramme", "Text": "Text", "Höjd": "Höhe", "Bredd": "Breite", "Radie": "Radius", "Spegel": "Spiegeln",
    },
    "Français": {
        "Arkiv": "Fichier", "Om": "À propos", "Nytt projekt": "Nouveau projet", "Spara projekt…": "Enregistrer le projet…", "Ladda projekt…": "Ouvrir le projet…", "Avsluta": "Quitter",
        "Om SubGlyph": "À propos de SubGlyph", "Info": "Aide", "Hjälp": "Aide", "Rapportera ett fel…": "Signaler un problème…", "Skicka önskemål…": "Envoyer une suggestion…", "Program": "Programme", "Maskin och yta": "Machine et surface", "Märktext": "Texte de gravure",
        "Förhandsvisning": "Aperçu", "Ämnesvisning:": "Affichage de la pièce brute :", "Generera NC": "Générer le programme CN", "Språk:": "Langue :",
        "Öppna i textredigerare efter generering": "Ouvrir dans l’éditeur de texte après génération",
        "Styrsystem:": "Commande CNC :", "Projektnamn:": "Nom du projet :", "Programkommentar:": "Commentaire du programme :",
        "Spindel:": "Broche :", "Revolver:": "Tourelle :", "Märkyta:": "Surface de gravure :", "Runt en axel": "Surface cylindrique", "Frontplan": "Face frontale",
        "Textriktning:": "Orientation du texte :", "Djupets riktning:": "Direction de profondeur :", "Maskinen har Y-axel": "La machine possède un axe Y", "Arbetsplan:": "Plan d’usinage :",
        "Detaljdiameter (mm):": "Diamètre de la pièce (mm) :", "Märkdjup (mm):": "Profondeur de gravure (mm) :", "Frigång (mm):": "Distance de sécurité (mm) :",
        "Nedmatning (mm/min):": "Avance de plongée (mm/min) :", "Gravering (mm/min):": "Avance de gravure (mm/min) :",
        "Programnummer:": "Numéro de programme :", "Programnamn:": "Nom du programme :", "Separata märkprogram": "Programmes de gravure séparés", "Text": "Texte", "Höjd": "Hauteur", "Bredd": "Largeur", "Radie": "Rayon", "Spegel": "Miroir",
    },
    "English": {
        "Arkiv": "File", "Om": "About", "Nytt projekt": "New project", "Spara projekt…": "Save project…", "Ladda projekt…": "Open project…", "Avsluta": "Exit",
        "Om SubGlyph": "About SubGlyph", "Info": "Help", "Hjälp": "Help", "Rapportera ett fel…": "Report a bug…", "Skicka önskemål…": "Send a request…", "Program": "Program", "Maskin och yta": "Machine and surface", "Märktext": "Engraving text",
        "Förhandsvisning": "Preview", "Ämnesvisning:": "Workpiece display:", "Generera NC": "Generate NC program", "Språk:": "Language:",
        "Öppna i textredigerare efter generering": "Open in text editor after generation",
        "Styrsystem:": "Control system:", "Projektnamn:": "Project name:", "Programkommentar:": "Program comment:",
        "Spindel:": "Spindle:", "Revolver:": "Turret:", "Märkyta:": "Engraving surface:", "Runt en axel": "Cylindrical surface", "Frontplan": "End face",
        "Textriktning:": "Text orientation:", "Djupets riktning:": "Engraving depth direction:", "Maskinen har Y-axel": "Machine has a Y-axis", "Arbetsplan:": "Working plane:",
        "Detaljdiameter (mm):": "Workpiece diameter (mm):", "Märkdjup (mm):": "Engraving depth (mm):", "Frigång (mm):": "Clearance (mm):",
        "Nedmatning (mm/min):": "Plunge feed (mm/min):", "Gravering (mm/min):": "Engraving feed (mm/min):",
        "Programnummer:": "Program number:", "Programnamn:": "Program name:", "Separata märkprogram": "Separate engraving programs", "Text": "Text", "Höjd": "Height", "Bredd": "Width", "Radie": "Radius", "Spegel": "Mirror",
    },
}

_EXTRA_TRANSLATIONS = {
    "Suomi": {
        "Solid": "Kiinteä", "Wireframe": "Lankamalli", "Av": "Pois", "O-nr": "O-nro", "Rot°": "Kierto°",
        "Fanuc sparas som programnummer utan filändelse. Okuma sparas som Programnamn.SSB.": "Fanuc tallennetaan ohjelmanumerolla ilman tiedostopäätettä. Okuma tallennetaan nimellä OhjelmanNimi.SSB.",
        "Sparas som Programnamn.SSB. O-numret finns inne i filen.": "Tallennetaan nimellä OhjelmanNimi.SSB. O-numero on tiedoston sisällä.",
        "Sparas som O + programnummer utan filändelse, en fil per unikt O-nummer.": "Tallennetaan O-kirjaimella alkavana ohjelmanumerona ilman tiedostopäätettä, yksi tiedosto jokaista yksilöllistä O-numeroa kohden.",
        "Tomma märktexter ignoreras. Z0 är ämnets ändplan; varje text har egen Z/C-position, storlek, rotation och spegling.": "Tyhjät merkintätekstit ohitetaan. Z0 on aihion päätypinta; jokaisella tekstillä on oma Z/C-sijainti, koko, kierto ja peilaus.",
        "Längs Z-axeln": "Z-akselin suuntaisesti", "Runt omkretsen": "Kehän suuntaisesti",
        "Gravering": "Kaiverrus", "Frigång": "Turva-asema", "Kontrollera diametermåtten.": "Tarkista halkaisijamitat.",
        "DIN MÄRKTEXT": "OMA MERKINTÄTEKSTISI", "Aktiva axlar:": "Aktiiviset akselit:",
        "Ämnestyp:": "Aihion tyyppi:", "Ämnestyp & längd:": "Aihion tyyppi ja pituus:", "Ämneslängd:": "Aihion pituus:", "Ämneslängd (mm):": "Aihion pituus (mm):", "Rund": "Pyöreä", "Sexkant": "Kuusikulmio", "Rektangel": "Suorakulmio", "Nyckelvidd (NV):": "Avainväli (NV):", "Bredd / höjd:": "Leveys / korkeus:",
        "Fyll i ett programnummer för att börja.": "Aloita syöttämällä ohjelmanumero.", "Nytt projekt skapat.": "Uusi projekti luotu.", "Alla aktuella projektuppgifter rensas. Vill du fortsätta?": "Kaikki nykyiset projektitiedot tyhjennetään. Haluatko jatkaa?", "Storlek och rotation anges per textrad": "Koko ja kierto määritetään tekstiriveittäin", "Djup": "Syvyys", "Dra för att vrida 3D-vyn": "Kierrä 3D-näkymää vetämällä", "djup": "syvyys",
        "Håll höger musknapp och dra för att rotera • Mushjul zoomar": "Kierrä pitämällä oikeaa hiiren painiketta ja vetämällä • Zoomaa hiiren rullalla",
        "Vänsterdrag: fri vy • Högerdrag: rotera runt ämnet • Mushjul: zoom": "Vasen veto: vapaa näkymä • Oikea veto: kierrä aihiota • Hiiren rulla: zoomaus",
        "Skapad av Kristian Simontaival.": "Tekijä: Kristian Simontaival.", "Programmet är helt gratis.": "Ohjelma on täysin maksuton.",
        "SubGlyph skapar ett underprogram. Verktygsval, spindelvarvtal, arbetsplan och första säkra förpositionering ska anges i huvudprogrammet innan underprogrammet anropas.": "SubGlyph luo aliohjelman. Työkalun valinta, karan pyörimisnopeus, työstötaso ja ensimmäinen turvallinen esipaikoitus on määritettävä pääohjelmassa ennen aliohjelman kutsua.",
    },
    "Deutsch": {
        "Solid": "Volumenmodell", "Wireframe": "Drahtmodell", "Av": "Aus", "O-nr": "O-Nr.", "Rot°": "Drehung (°)",
        "Fanuc sparas som programnummer utan filändelse. Okuma sparas som Programnamn.SSB.": "Fanuc wird unter der Programmnummer ohne Dateiendung gespeichert. Okuma wird als Programmname.SSB gespeichert.",
        "Sparas som Programnamn.SSB. O-numret finns inne i filen.": "Wird als Programmname.SSB gespeichert. Die O-Nummer steht in der Datei.",
        "Sparas som O + programnummer utan filändelse, en fil per unikt O-nummer.": "Speicherung als O plus Programmnummer ohne Dateiendung. Eine Datei pro eindeutiger O-Nummer.",
        "Tomma märktexter ignoreras. Z0 är ämnets ändplan; varje text har egen Z/C-position, storlek, rotation och spegling.": "Leere Gravurtexte werden ignoriert. Z0 ist die Werkstückstirnfläche; jeder Text besitzt eine eigene Z/C-Position, Größe, Drehung und Spiegelung.",
        "Längs Z-axeln": "Entlang der Z-Achse", "Runt omkretsen": "In Umfangsrichtung",
        "Gravering": "Gravur", "Frigång": "Sicherheitsposition", "Kontrollera diametermåtten.": "Durchmesserwerte prüfen.",
        "DIN MÄRKTEXT": "IHR GRAVURTEXT", "Aktiva axlar:": "Aktive Achsen:",
        "Ämnestyp:": "Rohteilform:", "Ämnestyp & längd:": "Rohteilform und Länge:", "Ämneslängd:": "Rohteillänge:", "Ämneslängd (mm):": "Rohteillänge (mm):", "Rund": "Rund", "Sexkant": "Sechskant", "Rektangel": "Rechteck", "Nyckelvidd (NV):": "Schlüsselweite (SW):", "Bredd / höjd:": "Breite / Höhe:",
        "Fyll i ett programnummer för att börja.": "Zum Start eine Programmnummer eingeben.", "Nytt projekt skapat.": "Neues Projekt erstellt.", "Alla aktuella projektuppgifter rensas. Vill du fortsätta?": "Alle aktuellen Projektdaten werden gelöscht. Möchten Sie fortfahren?", "Storlek och rotation anges per textrad": "Größe und Drehung werden je Textzeile festgelegt", "Djup": "Tiefe", "Dra för att vrida 3D-vyn": "Ziehen, um die 3D-Ansicht zu drehen", "djup": "Tiefe",
        "Håll höger musknapp och dra för att rotera • Mushjul zoomar": "Zum Drehen rechte Maustaste halten und ziehen • Mausrad zoomt",
        "Vänsterdrag: fri vy • Högerdrag: rotera runt ämnet • Mushjul: zoom": "Links ziehen: freie Ansicht • Rechts ziehen: Werkstück rollen • Mausrad: Zoom",
        "Skapad av Kristian Simontaival.": "Entwickelt von Kristian Simontaival.", "Programmet är helt gratis.": "Das Programm ist vollständig kostenlos.",
        "SubGlyph skapar ett underprogram. Verktygsval, spindelvarvtal, arbetsplan och första säkra förpositionering ska anges i huvudprogrammet innan underprogrammet anropas.": "SubGlyph erzeugt ein Unterprogramm. Werkzeugwahl, Spindeldrehzahl, Bearbeitungsebene und die erste sichere Vorpositionierung müssen vor dem Unterprogrammaufruf im Hauptprogramm festgelegt werden.",
    },
    "Français": {
        "Solid": "Solide", "Wireframe": "Filaire", "Av": "Désactivé", "O-nr": "N° O", "Rot°": "Rotation (°)",
        "Fanuc sparas som programnummer utan filändelse. Okuma sparas som Programnamn.SSB.": "Fanuc est enregistré sous le numéro de programme sans extension. Okuma est enregistré sous NomDuProgramme.SSB.",
        "Sparas som Programnamn.SSB. O-numret finns inne i filen.": "Enregistré sous NomDuProgramme.SSB. Le numéro O se trouve dans le fichier.",
        "Sparas som O + programnummer utan filändelse, en fil per unikt O-nummer.": "Enregistré sous O suivi du numéro de programme sans extension. Un fichier par numéro O distinct.",
        "Tomma märktexter ignoreras. Z0 är ämnets ändplan; varje text har egen Z/C-position, storlek, rotation och spegling.": "Les textes de gravure vides sont ignorés. Z0 correspond à la face de référence ; chaque texte possède sa position Z/C, ses dimensions, sa rotation et sa symétrie.",
        "Längs Z-axeln": "Le long de l’axe Z", "Runt omkretsen": "Dans le sens circonférentiel",
        "Gravering": "Gravure", "Frigång": "Position de sécurité", "Kontrollera diametermåtten.": "Vérifiez les diamètres.",
        "DIN MÄRKTEXT": "VOTRE TEXTE DE GRAVURE", "Aktiva axlar:": "Axes actifs :",
        "Ämnestyp:": "Forme du brut :", "Ämnestyp & längd:": "Forme et longueur du brut :", "Ämneslängd:": "Longueur du brut :", "Ämneslängd (mm):": "Longueur du brut (mm) :", "Rund": "Rond", "Sexkant": "Hexagonal", "Rektangel": "Rectangulaire", "Nyckelvidd (NV):": "Largeur sur plats :", "Bredd / höjd:": "Largeur / hauteur :",
        "Fyll i ett programnummer för att börja.": "Saisissez un numéro de programme pour commencer.", "Nytt projekt skapat.": "Nouveau projet créé.", "Alla aktuella projektuppgifter rensas. Vill du fortsätta?": "Toutes les données actuelles du projet seront effacées. Voulez-vous continuer ?", "Storlek och rotation anges per textrad": "Dimensions et rotation définies pour chaque ligne", "Djup": "Profondeur", "Dra för att vrida 3D-vyn": "Faites glisser pour tourner la vue 3D", "djup": "profondeur",
        "Håll höger musknapp och dra för att rotera • Mushjul zoomar": "Maintenez le bouton droit et faites glisser pour tourner • Molette pour zoomer",
        "Vänsterdrag: fri vy • Högerdrag: rotera runt ämnet • Mushjul: zoom": "Glisser à gauche : vue libre • Glisser à droite : rotation du brut • Molette : zoom",
        "Skapad av Kristian Simontaival.": "Créé par Kristian Simontaival.", "Programmet är helt gratis.": "Le programme est entièrement gratuit.",
        "SubGlyph skapar ett underprogram. Verktygsval, spindelvarvtal, arbetsplan och första säkra förpositionering ska anges i huvudprogrammet innan underprogrammet anropas.": "SubGlyph génère un sous-programme. Le choix de l’outil, la vitesse de broche, le plan d’usinage et le premier positionnement d’approche sécurisé doivent être définis dans le programme principal avant l’appel du sous-programme.",
    },
    "English": {
        "Solid": "Solid", "Wireframe": "Wireframe", "Av": "Off", "O-nr": "O No.", "Rot°": "Rotation (°)",
        "Fanuc sparas som programnummer utan filändelse. Okuma sparas som Programnamn.SSB.": "Fanuc files use the program number without an extension. Okuma files use ProgramName.SSB.",
        "Sparas som Programnamn.SSB. O-numret finns inne i filen.": "Saved as ProgramName.SSB. The O number is stored inside the file.",
        "Sparas som O + programnummer utan filändelse, en fil per unikt O-nummer.": "Saved as O plus the program number without a file extension. One file is created for each unique O number.",
        "Tomma märktexter ignoreras. Z0 är ämnets ändplan; varje text har egen Z/C-position, storlek, rotation och spegling.": "Blank engraving texts are ignored. Z0 is the workpiece end face; each text has its own Z/C position, size, rotation and mirroring.",
        "Längs Z-axeln": "Along the Z axis", "Runt omkretsen": "Circumferentially",
        "Gravering": "Engraving", "Frigång": "Clearance", "Kontrollera diametermåtten.": "Check the diameter values.",
        "DIN MÄRKTEXT": "YOUR ENGRAVING TEXT", "Aktiva axlar:": "Active axes:",
        "Ämnestyp:": "Stock shape:", "Ämnestyp & längd:": "Stock shape & length:", "Ämneslängd:": "Stock length:", "Ämneslängd (mm):": "Stock length (mm):", "Rund": "Round", "Sexkant": "Hexagonal", "Rektangel": "Rectangular", "Nyckelvidd (NV):": "Across flats (AF):", "Bredd / höjd:": "Width / height:",
        "Fyll i ett programnummer för att börja.": "Enter a program number to begin.", "Nytt projekt skapat.": "New project created.", "Alla aktuella projektuppgifter rensas. Vill du fortsätta?": "All current project data will be cleared. Do you want to continue?", "Storlek och rotation anges per textrad": "Size and rotation are specified per text row", "Djup": "Depth", "Dra för att vrida 3D-vyn": "Drag to rotate the 3D view", "djup": "depth",
        "Håll höger musknapp och dra för att rotera • Mushjul zoomar": "Hold the right mouse button and drag to rotate • Mouse wheel zooms",
        "Vänsterdrag: fri vy • Högerdrag: rotera runt ämnet • Mushjul: zoom": "Left-drag: free view • Right-drag: roll workpiece • Mouse wheel: zoom",
        "Skapad av Kristian Simontaival.": "Created by Kristian Simontaival.", "Programmet är helt gratis.": "The program is completely free.",
        "SubGlyph skapar ett underprogram. Verktygsval, spindelvarvtal, arbetsplan och första säkra förpositionering ska anges i huvudprogrammet innan underprogrammet anropas.": "SubGlyph generates a subprogram. Tool selection, spindle speed, machining plane and the initial safe pre-positioning move must be defined in the main program before the subprogram is called.",
    },
}
_TOOLTIP_TRANSLATIONS = {
    "Programnamnet blir Okumas SSB-filnamn, till exempel hej.SSB. Programnumret används fortfarande som O-nummer inne i SSB-filen.": {
        "Suomi": "Ohjelmanimestä tulee Okuman SSB-tiedoston nimi, esimerkiksi hei.SSB. Ohjelmanumeroa käytetään edelleen SSB-tiedoston sisäisenä O-numerona.",
        "Deutsch": "Der Programmname wird zum Dateinamen der Okuma-SSB-Datei, zum Beispiel hallo.SSB. Die Programmnummer wird weiterhin als O-Nummer innerhalb der SSB-Datei verwendet.",
        "Français": "Le nom du programme devient le nom du fichier SSB Okuma, par exemple bonjour.SSB. Le numéro de programme reste utilisé comme numéro O dans le fichier SSB.",
        "English": "The program name becomes the Okuma SSB filename, for example hello.SSB. The program number is still used as the O number inside the SSB file.",
    },
    "Teckensnitt:": {"Suomi": "Fontti:", "Deutsch": "Schriftart:", "Français": "Police :", "English": "Font:"},
    "Installerat": {"Suomi": "Asennettu", "Deutsch": "Installiert", "Français": "Installée", "English": "Installed"},
    "Egen fontfil": {"Suomi": "Oma fonttitiedosto", "Deutsch": "Eigene Schriftdatei", "Français": "Fichier de police", "English": "Custom font file"},
    "Välj fontfil…": {"Suomi": "Valitse fonttitiedosto…", "Deutsch": "Schriftdatei wählen…", "Français": "Choisir un fichier de police…", "English": "Choose font file…"},
    "Välj fontfil": {"Suomi": "Valitse fonttitiedosto", "Deutsch": "Schriftdatei wählen", "Français": "Choisir un fichier de police", "English": "Choose font file"},
    "Ogiltig fontfil": {"Suomi": "Virheellinen fonttitiedosto", "Deutsch": "Ungültige Schriftdatei", "Français": "Fichier de police non valide", "English": "Invalid font file"},
    "Fontfilen kunde inte läsas:": {"Suomi": "Fonttitiedostoa ei voitu lukea:", "Deutsch": "Die Schriftdatei konnte nicht gelesen werden:", "Français": "Impossible de lire le fichier de police :", "English": "The font file could not be read:"},
    "SubGlyph använder en enlinjefont. Installerad eller egen fontfil konturgraveras och skapar därför fler NC-block.": {
        "Suomi": "SubGlyph käyttää yksiviivafonttia. Asennettu tai oma fontti kaiverretaan ääriviivoina ja tuottaa siksi enemmän NC-lauseita.",
        "Deutsch": "SubGlyph verwendet eine Einlinienschrift. Installierte oder eigene Schriften werden als Konturen graviert und erzeugen daher mehr NC-Sätze.",
        "Français": "SubGlyph utilise une police monoligne. Une police installée ou personnalisée est gravée par contours et génère donc davantage de blocs CN.",
        "English": "SubGlyph uses a single-line font. Installed or custom fonts are outline engraved and therefore create more NC blocks.",
    },
    "XPos anger märkningens grundposition i X på frontplanet.": {
        "Suomi": "XPos määrittää merkinnän perussijainnin etupinnan X-akselilla.",
        "Deutsch": "XPos legt die Grundposition der Gravur in X auf der Stirnfläche fest.",
        "Français": "XPos définit la position de base X de la gravure sur la face frontale.",
        "English": "XPos sets the engraving base position along X on the end face.",
    },
    "Använd eget systemteckensnitt (konturgravyr)": {
        "Suomi": "Käytä järjestelmän fonttia (ääriviivakaiverrus)", "Deutsch": "Systemschrift verwenden (Konturgravur)",
        "Français": "Utiliser une police système (gravure des contours)", "English": "Use a system font (outline engraving)",
    },
    "NC-adressen för rotationsaxeln. C är standard; skriv exempelvis CS för att posta CS60 i stället för C60.": {
        "Suomi": "Pyörivän akselin NC-osoite. Oletus on C; kirjoita esimerkiksi CS tuottaaksesi CS60 arvon C60 sijaan.",
        "Deutsch": "NC-Adresse der Drehachse. Standard ist C; z. B. CS eingeben, um CS60 statt C60 auszugeben.",
        "Français": "Adresse CN de l’axe rotatif. C est la valeur par défaut ; saisissez par exemple CS pour générer CS60 au lieu de C60.",
        "English": "NC address for the rotary axis. C is the default; enter CS, for example, to output CS60 instead of C60.",
    },
    "ZPos anger var på detaljen märkningen placeras. Skriv alltid positionen som ett negativt värde, till exempel -5. Z-riktningen avgör sedan om posten använder Z-5 eller Z+5.": {
        "Suomi": "ZPos määrittää merkinnän sijainnin kappaleessa. Anna aina negatiivinen arvo, esimerkiksi -5. Z-suunta määrää, tulostetaanko Z-5 vai Z+5.",
        "Deutsch": "ZPos legt die Position der Gravur fest. Immer einen negativen Wert eingeben, z. B. -5. Die Z-Richtung bestimmt dann Z-5 oder Z+5.",
        "Français": "ZPos définit la position de la gravure. Saisissez toujours une valeur négative, par exemple -5. La direction Z détermine ensuite Z-5 ou Z+5.",
        "English": "ZPos sets the engraving position. Always enter a negative value, such as -5. The Z direction then determines whether the output uses Z-5 or Z+5.",
    },
    "Fritt avstånd mellan tecknen i mm/inch, exempelvis 0,4. Värdet 0 ger inget extra mellanrum.": {
        "Suomi": "Merkkien välinen lisäväli millimetreinä/tuumina, esimerkiksi 0,4. Arvo 0 ei lisää väliä.",
        "Deutsch": "Zusätzlicher Zeichenabstand in mm/Zoll, z. B. 0,4. Der Wert 0 fügt keinen Abstand hinzu.",
        "Français": "Espacement supplémentaire entre caractères en mm/pouces, par exemple 0,4. La valeur 0 n’ajoute aucun espace.",
        "English": "Extra spacing between characters in mm/inches, for example 0.4. A value of 0 adds no extra spacing.",
    },
    "Z-riktning påverkar endast postens Z-värden. Den ändrar inte märktextens utseende eller förhandsvisningen.": {
        "Suomi": "Z-suunta vaikuttaa vain NC-tulosteen Z-arvoihin. Se ei muuta tekstin ulkoasua tai esikatselua.",
        "Deutsch": "Die Z-Richtung beeinflusst nur die Z-Werte der Ausgabe, nicht das Aussehen oder die Vorschau.",
        "Français": "La direction Z affecte uniquement les valeurs Z du programme, pas l’aspect du texte ni l’aperçu.",
        "English": "The Z direction only affects output Z values. It does not change the engraving appearance or preview.",
    },
    "Placering längs detaljens Z-axel. Ange alltid ett negativt värde, exempelvis -5. Fältet ändrar inte vald Z-riktning.": {
        "Suomi": "Sijainti kappaleen Z-akselilla. Anna aina negatiivinen arvo, esimerkiksi -5. Kenttä ei muuta valittua Z-suuntaa.",
        "Deutsch": "Position entlang der Z-Achse. Immer einen negativen Wert eingeben, z. B. -5. Das Feld ändert die gewählte Z-Richtung nicht.",
        "Français": "Position le long de l’axe Z. Saisissez toujours une valeur négative, par exemple -5. Ce champ ne change pas la direction Z choisie.",
        "English": "Position along the workpiece Z axis. Always enter a negative value, such as -5. This field does not change the selected Z direction.",
    },
    "Väljer hur ZPos skrivs i NC-posten: Z- eller Z+. Valet påverkar inte förhandsvisningen.": {
        "Suomi": "Valitsee, kirjoitetaanko ZPos NC-tulosteeseen muodossa Z- vai Z+. Valinta ei vaikuta esikatseluun.",
        "Deutsch": "Legt fest, ob ZPos als Z- oder Z+ ausgegeben wird. Die Vorschau bleibt unverändert.",
        "Français": "Détermine si ZPos est généré sous la forme Z- ou Z+. Ce choix n’affecte pas l’aperçu.",
        "English": "Selects whether ZPos is output as Z- or Z+. The selection does not affect the preview.",
    },
    "Avmarkerad använder SubGlyphs vanliga enlinjefont. Markerad graverar konturerna i valt teckensnitt och skapar därför fler NC-block.": {
        "Suomi": "Kun valinta ei ole käytössä, käytetään SubGlyphin tavallista yksiviivafonttia. Valittuna kaiverretaan fontin ääriviivat, mikä tuottaa enemmän NC-lauseita.",
        "Deutsch": "Ohne Auswahl wird die normale Einlinienschrift verwendet. Mit Auswahl werden die Schriftkonturen graviert, wodurch mehr NC-Sätze entstehen.",
        "Français": "Désactivé, SubGlyph utilise sa police monoligne. Activé, les contours de la police sont gravés, ce qui produit davantage de blocs CN.",
        "English": "Off uses SubGlyph’s normal single-line font. On engraves the selected font outlines and therefore creates more NC blocks.",
    },
}
for _source, _by_language in _TOOLTIP_TRANSLATIONS.items():
    for _language, _translated in _by_language.items():
        TRANSLATIONS[_language][_source] = _translated

_DYNAMIC_HELP = {
    "Z/Y positionerar texten på den indexerade ytan. C väljer detaljytans vinkel; X används för märkdjupet.": {
        "Suomi": "Z/Y sijoittaa tekstin indeksoidulle pinnalle. C valitsee kappaleen kulman; X määrää kaiverrussyvyyden.",
        "Deutsch": "Z/Y positioniert den Text auf der indexierten Fläche. C bestimmt den Werkstückwinkel; X steuert die Gravurtiefe.",
        "Français": "Z/Y positionne le texte sur la face indexée. C définit l’angle de la pièce ; X commande la profondeur de gravure.",
        "English": "Z/Y positions the text on the indexed surface. C selects the workpiece angle; X controls engraving depth.",
    },
    "Z0 är ämnets ändplan. Z/C formar märkningen och X används för märkdjupet; Y är låst i XZ+C-läge.": {
        "Suomi": "Z0 on aihion päätypinnassa. Z/C muodostavat merkinnän ja X määrää kaiverrussyvyyden. Y on lukittu XZ+C-tilassa.",
        "Deutsch": "Z0 liegt auf der Werkstückstirnfläche. Z/C erzeugen die Gravur und X bestimmt die Gravurtiefe. Y ist in der XZ+C-Achskonfiguration gesperrt.",
        "Français": "Z0 correspond à la face frontale de la pièce. Z/C génèrent la gravure et X détermine la profondeur de gravure. Y est verrouillé dans la configuration XZ+C.",
        "English": "Z0 is the workpiece end face. Z/C generate the engraving and X controls the engraving depth; Y is locked in the XZ+C axis configuration.",
    },
}
for _source, _by_language in _DYNAMIC_HELP.items():
    for _language, _translated in _by_language.items():
        TRANSLATIONS[_language][_source] = _translated
for _language, _translations in _EXTRA_TRANSLATIONS.items():
    TRANSLATIONS[_language].update(_translations)
TRANSLATIONS["Bosanski"] = BOSNIAN_TRANSLATIONS
TRANSLATIONS["Polski"] = POLISH_TRANSLATIONS
SUPPORT_TRANSLATIONS["Bosanski"] = BOSNIAN_SUPPORT_TRANSLATIONS
SUPPORT_TRANSLATIONS["Polski"] = POLISH_SUPPORT_TRANSLATIONS

_CONTROLLER_HELP_TRANSLATIONS = {
    "FANUC (ISO) sparas utan filändelse, OKUMA OSP (ISO) som Programnamn.SSB och SIEMENS SINUMERIK (ISO) som programnummer.spf.": {
        "Suomi": "FANUC (ISO) tallennetaan ilman tiedostopäätettä, OKUMA OSP (ISO) nimellä OhjelmanNimi.SSB ja SIEMENS SINUMERIK (ISO) nimellä ohjelmanumero.spf.",
        "Deutsch": "FANUC (ISO) wird ohne Dateiendung, OKUMA OSP (ISO) als Programmname.SSB und SIEMENS SINUMERIK (ISO) als Programmnummer.spf gespeichert.",
        "Français": "FANUC (ISO) est enregistré sans extension, OKUMA OSP (ISO) sous NomDuProgramme.SSB et SIEMENS SINUMERIK (ISO) sous numérodeprogramme.spf.",
        "English": "FANUC (ISO) is saved without an extension, OKUMA OSP (ISO) as ProgramName.SSB, and SIEMENS SINUMERIK (ISO) as programnumber.spf.",
        "Bosanski": "FANUC (ISO) se čuva bez ekstenzije, OKUMA OSP (ISO) kao NazivPrograma.SSB, a SIEMENS SINUMERIK (ISO) kao brojprograma.spf.",
        "Polski": "FANUC (ISO) jest zapisywany bez rozszerzenia, OKUMA OSP (ISO) jako NazwaProgramu.SSB, a SIEMENS SINUMERIK (ISO) jako numerprogramu.spf.",
    },
    "Sparas som programnummer.spf, en fil per unikt O-nummer.": {
        "Suomi": "Tallennetaan nimellä ohjelmanumero.spf, yksi tiedosto jokaista yksilöllistä O-numeroa kohden.",
        "Deutsch": "Wird als Programmnummer.spf gespeichert, eine Datei pro eindeutiger O-Nummer.",
        "Français": "Enregistré sous numérodeprogramme.spf, un fichier par numéro O distinct.",
        "English": "Saved as programnumber.spf, one file per unique O number.",
        "Bosanski": "Čuva se kao brojprograma.spf, jedna datoteka za svaki jedinstveni O-broj.",
        "Polski": "Zapisywany jako numerprogramu.spf, jeden plik dla każdego unikalnego numeru O.",
    },
}
for _source, _by_language in _CONTROLLER_HELP_TRANSLATIONS.items():
    for _language, _translated in _by_language.items():
        TRANSLATIONS[_language][_source] = _translated


def _clean_nc_comment(comment: str, field_name: str) -> str:
    clean_comment = comment.strip()
    if "(" in clean_comment or ")" in clean_comment:
        raise ValueError(f"{field_name} får inte innehålla ( eller ).")
    return clean_comment


def normalize_control_system(control_system: str) -> str:
    """Map saved legacy controller names to their current display names."""
    return LEGACY_CONTROL_SYSTEMS.get(control_system, control_system)


def posted_mantle_marking_blocks(marking: MantleMarking, control_system: str) -> list[str]:
    """Apply controller-specific coordinates without changing the shared defaults."""
    okuma = normalize_control_system(control_system) == OKUMA_OSP_ISO
    planar = marking.plane in ("XY", "XYZ", "XYZC", "XYZ+C")
    if okuma and planar:
        marking = replace(
            marking,
            engraving_diameter=marking.engraving_diameter / 2,
            clearance_diameter=marking.clearance_diameter / 2,
            rotation_clearance_diameter=(
                None if marking.rotation_clearance_diameter is None
                else marking.rotation_clearance_diameter / 2
            ),
        )
    lines = mantle_marking_blocks(
        marking, reverse_rotary_c=okuma, compact_circles=okuma and planar,
    )
    if okuma and planar:
        return ["G19", *okuma_continuous_arcs(lines, ("Z", "Y"), "X")]
    return lines


def okuma_continuous_arcs(lines: list[str], axes: tuple[str, str], depth_axis: str) -> list[str]:
    """Keep adjacent glyph arcs at cutting depth; retain lifts across gaps."""
    def coordinates(line: str) -> dict[str, Decimal]:
        return {axis: Decimal(value) for axis, value in
                re.findall(r"([XYZ])([+-]?\d+(?:\.\d*)?)", line)}

    result: list[str] = []
    index = 0
    plunge: str | None = None
    while index < len(lines):
        line = lines[index]
        if line.startswith(f"G1 {depth_axis}"):
            plunge = line
        # The generator emits arc, retract, position, plunge, next arc.
        if (result and re.match(r"^G[23] ", result[-1])
                and index + 3 < len(lines)
                and line.startswith(f"G0 {depth_axis}")
                and lines[index + 1].startswith("G0 ")
                and lines[index + 2] == plunge
                and re.match(r"^G[23] ", lines[index + 3])):
            endpoint = coordinates(result[-1])
            startpoint = coordinates(lines[index + 1])
            if (set(startpoint) == set(axes)
                    and all(endpoint.get(axis) == startpoint[axis] for axis in axes)):
                index += 3
                continue
        result.append(line)
        index += 1
    return result


def okuma_c_direction_blocks(lines: Iterable[str], c_axis: str = "C") -> list[str]:
    """Post absolute generated motion blocks for OSP's directed rotary axis.

    Keep the unwrapped coordinates to determine cutting direction before
    mapping targets to 0 <= C < 360. The initial position is unknown, so the
    first positioning move explicitly selects M15, as in the reference OMARK.
    """
    axis = c_axis.upper()
    coordinate = re.compile(rf"(?<![A-Z]){re.escape(axis)}([+-]?\d+(?:\.\d*)?)")
    previous: Decimal | None = None
    result: list[str] = []
    turn = Decimal(360)
    for line in lines:
        # Generated comments are standalone; never interpret their text as axes.
        if not re.match(r"^G[01] ", line):
            result.append(line)
            continue
        code, separator, comment = line.partition("(")
        match = coordinate.search(code)
        if match is None:
            result.append(line)
            continue
        value = Decimal(match.group(1))
        delta = None if previous is None else value - previous
        previous = value
        rapid = code.startswith("G0 ")
        if delta is not None and rapid:
            # Reposition between strokes by the shorter route at clearance.
            delta = (delta % turn + turn) % turn
            if delta > 180:
                delta -= turn
        if delta == 0:
            # Repeated C targets add no motion; keep Z/X/Y and any feed word.
            code = code[:match.start()] + code[match.end():]
        else:
            if delta is not None and abs(delta) >= turn:
                raise ValueError("En graveringsrörelse på C-axeln måste vara mindre än ett varv för OKUMA.")
            target = (value % turn + turn) % turn
            target_text = f"{target:.3f}".rstrip("0")
            code = code[:match.start()] + axis + target_text + code[match.end():]
            code = code.rstrip() + (" M16" if delta is not None and delta < 0 else " M15")
        result.append(code.rstrip() + (separator + comment if separator else ""))
    return result


def create_nc_program(
    program_number: str,
    comment: str = "",
    markings: Iterable[str] | None = None,
    body_lines: Iterable[str] | None = None,
    header_lines: Iterable[str] | None = None,
    control_system: str = FANUC_ISO,
    generated_at: datetime | None = None,
    language: str = "Svenska",
    c_axis: str = "C",
) -> str:
    """Create an NC subprogram frame and comments for non-empty markings."""
    number = program_number.strip().upper()
    if number.startswith("O"):
        number = number[1:]
    if not re.fullmatch(r"\d+", number):
        raise ValueError("Programnumret måste innehålla enbart siffror.")

    clean_comment = _clean_nc_comment(comment, "Programkommentaren")
    program_line = f"O{number}"
    if clean_comment:
        program_line += f"({clean_comment})"

    body: list[str] = list(body_lines or ())
    if body_lines is None:
        for index, marking in enumerate(markings or (), start=1):
            clean_marking = _clean_nc_comment(marking, f"Märktext {index}")
            if clean_marking:
                body.extend((f"({clean_marking})", ""))

    nc_comments = NC_COMMENT_TRANSLATIONS.get(language, NC_COMMENT_TRANSLATIONS["Svenska"])
    generator_comment = f"({nc_comments['generated_with']} {APP_VERSION})"
    timestamp = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    timestamp_comment = f"({nc_comments['generated_at']} {timestamp})"
    control_system = normalize_control_system(control_system)
    if control_system == OKUMA_OSP_ISO:
        body = okuma_c_direction_blocks(body, c_axis)
        # Feed values are distance/minute; never inherit G95 from the caller.
        lines = [program_line, generator_comment, timestamp_comment, *(header_lines or ()), "G94", "", *body, "RTS"]
    elif control_system == SIEMENS_SINUMERIK_ISO:
        lines = ["%", program_line, generator_comment, timestamp_comment, *(header_lines or ()), "", *body, "M17", "%"]
    else:
        lines = ["%", program_line, generator_comment, timestamp_comment, *(header_lines or ()), "", *body, "M99", "%"]
    return "\n".join(lines) + "\n"


def create_nc_collection(
    programs: Iterable[tuple[str, str, Iterable[str]]],
    header_lines: Iterable[str] | None = None,
    control_system: str = FANUC_ISO,
    language: str = "Svenska",
    c_axis: str = "C",
) -> str:
    """Create one machine file containing one or more O subprograms."""
    control_system = normalize_control_system(control_system)
    sections: list[str] = []
    generated_at = datetime.now()
    for number, comment, body in programs:
        program = create_nc_program(
            number,
            comment,
            body_lines=body,
            header_lines=header_lines,
            control_system=control_system,
            generated_at=generated_at,
            language=language,
            c_axis=c_axis,
        ).strip()
        if control_system != OKUMA_OSP_ISO:
            program = program.removeprefix("%\n").removesuffix("\n%")
        sections.append(program)
    if not sections:
        raise ValueError("Minst en märktext måste anges.")
    joined = "\n\n".join(sections)
    return f"{joined}\n" if control_system == OKUMA_OSP_ISO else f"%\n{joined}\n%\n"


def group_program_indices(
    numbered_indices: Iterable[tuple[str, int]],
) -> list[tuple[str, list[int]]]:
    """Group marking rows by O number while preserving their entered order."""
    grouped: dict[str, list[int]] = {}
    for number, index in numbered_indices:
        normalized = number.strip().upper().removeprefix("O")
        grouped.setdefault(normalized, []).append(index)
    return list(grouped.items())


def create_fanuc_files(
    programs: Iterable[tuple[str, str, Iterable[str]]],
    header_lines: Iterable[str] | None = None,
    language: str = "Svenska",
) -> list[tuple[str, str]]:
    """Create one extensionless, O-prefixed Fanuc file per program number."""
    files: list[tuple[str, str]] = []
    for number, comment, body in programs:
        normalized = number.strip().upper().removeprefix("O")
        content = create_nc_collection(
            ((normalized, comment, body),),
            header_lines=header_lines,
            control_system=FANUC_ISO,
            language=language,
        )
        files.append((f"O{normalized}", content))
    if not files:
        raise ValueError("Minst en märktext måste anges.")
    return files


def create_siemens_files(
    programs: Iterable[tuple[str, str, Iterable[str]]],
    header_lines: Iterable[str] | None = None,
    language: str = "Svenska",
) -> list[tuple[str, str]]:
    """Create one Siemens SINUMERIK ISO .spf file per O number."""
    files: list[tuple[str, str]] = []
    for number, comment, body in programs:
        normalized = number.strip().upper().removeprefix("O")
        content = create_nc_collection(
            ((normalized, comment, body),),
            header_lines=header_lines,
            control_system=SIEMENS_SINUMERIK_ISO,
            language=language,
        )
        files.append((f"{normalized}.spf", content))
    if not files:
        raise ValueError("Minst en märktext måste anges.")
    return files


def parse_dimension(value: str, field_name: str) -> Decimal:
    """Parse a positive dimension, accepting both decimal comma and point."""
    try:
        dimension = Decimal(value.strip().replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(f"{field_name} måste vara ett tal.") from error
    if dimension < 0:
        raise ValueError(f"{field_name} får inte vara negativt.")
    return dimension


def parse_coordinate(value: str, field_name: str) -> Decimal:
    """Parse a signed coordinate, accepting both decimal comma and point."""
    try:
        return Decimal(value.strip().replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(f"{field_name} måste vara ett tal.") from error


def calculate_diameter_levels(
    marking_diameter: str, marking_depth: str, clearance: str
) -> tuple[Decimal, Decimal]:
    diameter = parse_dimension(marking_diameter, "Märkdiameter")
    depth = parse_dimension(marking_depth, "Märkdjup")
    clearance_value = parse_dimension(clearance, "Frigång")
    engraving_diameter = diameter - depth
    if engraving_diameter < 0:
        raise ValueError("Märkdjupet kan inte vara större än märkdiametern.")
    return engraving_diameter, diameter + clearance_value


def flat_stock_surface_dimension(
    stock_type: str, across_flats: float, width: float, height: float, c_degrees: float
) -> float:
    """Return the diametral X value of the flat face selected by C."""
    if stock_type == "Sexkant":
        return across_flats
    angle = math.radians(c_degrees)
    return width if abs(math.cos(angle)) >= abs(math.sin(angle)) else height


def format_nc_number(value: Decimal) -> str:
    formatted = format(value, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def front_text_point(
    horizontal: float,
    vertical: float,
    center_x: float,
    center_y: float,
    angle_degrees: float,
    bending_radius: float | None,
) -> tuple[float, float]:
    """Bend text around its fixed anchor, then rotate and translate it on the face."""
    angle = math.radians(angle_degrees)
    if bending_radius is None:
        local_x, local_y = horizontal, vertical
    else:
        bend_angle = horizontal / bending_radius
        local_x = bending_radius * math.sin(bend_angle)
        local_y = bending_radius * (1 - math.cos(bend_angle)) + vertical
    return (
        center_x + local_x * math.cos(angle) - local_y * math.sin(angle),
        center_y + local_x * math.sin(angle) + local_y * math.cos(angle),
    )


def rotate_front_position(x: float, y: float, c_degrees: float) -> tuple[float, float]:
    """Index an XY position around the workpiece centre using the C axis."""
    angle = math.radians(c_degrees)
    return (
        x * math.cos(angle) - y * math.sin(angle),
        x * math.sin(angle) + y * math.cos(angle),
    )


class SupportForm(tk.Toplevel):
    """Compose a support email draft without storing mail credentials."""

    def __init__(self, app: "SubGlyphApp", report_type: str) -> None:
        super().__init__(app)
        self.app = app
        self.report_type = report_type
        self.attachments: list[Path] = []
        self._t = app._support_t
        title = self._t("Rapportera ett fel" if report_type == "bug" else "Skicka önskemål")
        self.title(title)
        self.geometry("640x560")
        self.minsize(560, 500)
        self.transient(app)

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text=self._t("Till:")).grid(row=0, column=0, sticky="w", pady=4)
        recipient = ttk.Entry(frame)
        recipient.insert(0, SUPPORT_EMAIL)
        recipient.configure(state="readonly")
        recipient.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text=self._t("Din e-postadress:")).grid(row=1, column=0, sticky="w", pady=4)
        self.reply_to = ttk.Entry(frame)
        self.reply_to.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text=self._t("Ämne:")).grid(row=2, column=0, sticky="w", pady=4)
        self.subject = ttk.Entry(frame)
        subject_type = self._t("Felrapport" if report_type == "bug" else "Önskemål")
        self.subject.insert(0, f"SubGlyph {APP_VERSION} – {subject_type}")
        self.subject.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text=self._t("Meddelande:")).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 4))
        self.message = tk.Text(frame, height=9, wrap="word")
        self.message.grid(row=4, column=0, columnspan=2, sticky="nsew")

        ttk.Label(frame, text=self._t("Bilagor:")).grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 4))
        self.attachment_list = tk.Listbox(frame, height=4)
        self.attachment_list.grid(row=6, column=0, columnspan=2, sticky="ew")

        attachment_buttons = ttk.Frame(frame)
        attachment_buttons.grid(row=7, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Button(attachment_buttons, text=self._t("Lägg till fil…"), command=self._add_file).pack(side="left")
        ttk.Button(attachment_buttons, text=self._t("Generera logg"), command=self._generate_log).pack(side="left", padx=6)
        if report_type == "bug":
            ttk.Button(attachment_buttons, text=self._t("Bifoga senaste crashdump"), command=self._add_latest_crash).pack(side="left")
        ttk.Button(attachment_buttons, text=self._t("Ta bort"), command=self._remove_selected).pack(side="right")

        actions = ttk.Frame(frame)
        actions.grid(row=8, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text=self._t("Avbryt"), command=self.destroy).pack(side="right")
        ttk.Button(actions, text=self._t("Skapa e-postutkast"), command=self._create_draft).pack(side="right", padx=8)
        self.reply_to.focus_set()

    def _append_attachment(self, path: Path) -> None:
        path = path.resolve()
        if path not in self.attachments:
            self.attachments.append(path)
            self.attachment_list.insert("end", str(path))

    def _add_file(self) -> None:
        source = filedialog.askopenfilename(parent=self, title=self._t("Välj bilaga"))
        if source:
            self._append_attachment(Path(source))

    def _generate_log(self) -> None:
        try:
            path = self.app.generate_diagnostic_log()
        except OSError as error:
            messagebox.showerror(self._t("Kunde inte skapa loggen"), str(error), parent=self)
            return
        self._append_attachment(path)
        messagebox.showinfo(self._t("Diagnoslogg skapad"), f"{self._t('Loggen sparades som:')}\n{path}", parent=self)

    def _add_latest_crash(self) -> None:
        crashes = sorted(app_data_directory().glob("SubGlyph-crash-*.txt"), reverse=True)
        if not crashes:
            messagebox.showinfo(self._t("Ingen crashdump"), self._t("Det finns ingen sparad crashdump att bifoga."), parent=self)
            return
        self._append_attachment(crashes[0])

    def _remove_selected(self) -> None:
        selection = self.attachment_list.curselection()
        if not selection:
            return
        index = selection[0]
        del self.attachments[index]
        self.attachment_list.delete(index)

    def _create_draft(self) -> None:
        reply_to = self.reply_to.get().strip()
        subject = self.subject.get().strip()
        body = self.message.get("1.0", "end-1c").strip()
        if "@" not in reply_to or reply_to.startswith("@") or reply_to.endswith("@"):
            messagebox.showwarning(self._t("E-postadress saknas"), self._t("Ange en giltig e-postadress för svar."), parent=self)
            return
        if not subject or not body:
            messagebox.showwarning(self._t("Ofullständig rapport"), self._t("Ange både ämne och meddelande."), parent=self)
            return
        try:
            draft = create_email_draft(reply_to, subject, body, self.attachments)
            open_path(draft)
        except OSError as error:
            messagebox.showerror(self._t("Kunde inte skapa e-postutkastet"), str(error), parent=self)
            return
        self.app.record_activity(f"Skapade {self.report_type}-utkast")
        messagebox.showinfo(
            self._t("E-postutkast skapat"),
            f"{self._t('Utkastet har öppnats i systemets e-postprogram. Kontrollera det och välj Skicka.')}\n\n{self._t('Sparat som:')}\n{draft}",
            parent=self,
        )
        self.destroy()


class SubGlyphApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{PRODUCT_NAME} – NC-generator – {APP_VERSION}")
        self.geometry("1200x720")
        self.minsize(1040, 640)
        self.activity_log: list[str] = []
        self.record_activity("Programmet startades")
        self.dialog_directories = load_directory_history()
        self.is_admin = False
        self.access_control = AccessControl(app_data_directory() / "permissions.json")

        self.project_name = tk.StringVar()
        self.language = tk.StringVar(value="Svenska")
        self.units = tk.StringVar(value="MM")
        self._active_units = "MM"
        self.program_number = tk.StringVar()
        self.program_name = tk.StringVar()
        self.separate_programs = tk.BooleanVar(value=False)
        self.marking_program_numbers = [tk.StringVar() for _ in range(MARKING_ROW_COUNT)]
        self.comment = tk.StringVar()
        self.open_after_generate = tk.BooleanVar(value=False)
        self.control_system = tk.StringVar(value=FANUC_ISO)
        self.spindle = tk.StringVar(value="HSP")
        self.turret = tk.StringVar(value="Lower")
        self.surface = tk.StringVar(value="Runt en axel")
        self.orientation = tk.StringVar(value=ORIENTATION_ALONG_Z)
        self.orientation_display = tk.StringVar(value=ORIENTATION_ALONG_Z)
        self.depth_direction = tk.StringVar(value="-")
        self.has_y_axis = tk.BooleanVar(value=True)
        self.plane = tk.StringVar(value="XZ+C")
        self.marking_diameter = tk.StringVar(value="50")
        self.stock_type = tk.StringVar(value="Rund")
        self.hex_across_flats = tk.StringVar(value="50")
        self.stock_width = tk.StringVar(value="50")
        self.stock_height = tk.StringVar(value="50")
        self.stock_length = tk.StringVar(value="70")
        self.marking_depth = tk.StringVar(value="0,5")
        self.clearance = tk.StringVar(value="2")
        self.character_height = tk.StringVar(value="5")
        self.character_width = tk.StringVar(value="3")
        self.text_rotation = tk.StringVar(value="0")
        self.flip_text = tk.BooleanVar(value=False)
        self.mirror_text = tk.BooleanVar(value=False)
        self.marking_z = tk.StringVar(value="0")
        self.dynamic_markings = [DynamicMarking() for _ in range(MARKING_ROW_COUNT)]
        self.markings = [tk.StringVar() for _ in range(MARKING_ROW_COUNT)]
        self.marking_placements = [tk.StringVar(value="Ny rad") for _ in range(MARKING_ROW_COUNT)]
        self.marking_z_values = [tk.StringVar(value="0") for _ in range(MARKING_ROW_COUNT)]
        self.marking_y_values = [tk.StringVar(value="0") for _ in range(MARKING_ROW_COUNT)]
        self.marking_c_values = [tk.StringVar(value="0") for _ in range(MARKING_ROW_COUNT)]
        self.c_axis = tk.StringVar(value="C")
        self.plunge_feed = tk.StringVar(value="150")
        self.engraving_feed = tk.StringVar(value="800")
        self.marking_heights = [tk.StringVar(value="5") for _ in range(MARKING_ROW_COUNT)]
        self.marking_widths = [tk.StringVar(value="3") for _ in range(MARKING_ROW_COUNT)]
        self.marking_spacings = [tk.StringVar(value="0") for _ in range(MARKING_ROW_COUNT)]
        self.marking_rotations = [tk.StringVar(value="0") for _ in range(MARKING_ROW_COUNT)]
        self.marking_bending_radii = [tk.StringVar(value="") for _ in range(MARKING_ROW_COUNT)]
        self.marking_mirrors = [tk.BooleanVar(value=False) for _ in range(MARKING_ROW_COUNT)]
        self.marking_z_directions = [tk.StringVar(value="Z-") for _ in range(MARKING_ROW_COUNT)]
        self.use_system_font = tk.BooleanVar(value=False)
        self.font_source = tk.StringVar(value="SubGlyph")
        self.system_font_name = tk.StringVar()
        self.custom_font_path = tk.StringVar()
        self.available_system_fonts = system_fonts()
        self.preview_mode = tk.StringVar(value="Solid")
        self.view_yaw = -24.0
        self.view_pitch = 16.0
        self.view_roll = 0.0
        self.preview_zoom = 1.0
        self._drag_origin: tuple[int, int] | None = None
        self._text_mask_cache: dict[tuple[str, str | None], Image.Image] = {}
        self.diameter_preview = tk.StringVar()
        self.status = tk.StringVar(value="Fyll i ett programnummer för att börja.")
        self._new_project_defaults = self._project_data()

        self._build_ui()
        self._build_menu()
        self._build_menu_buttons()
        self._bind_preview_updates()
        self._update_configuration()
        # Capture the Swedish source labels before the first language switch.
        self._translate_widgets()
        self._update_permissions()

    def _t(self, source: str) -> str:
        translated = TRANSLATIONS.get(self.language.get(), {}).get(source)
        if translated is not None:
            return translated
        marking_match = re.fullmatch(r"Märktext (\d+):", source)
        if marking_match:
            prefix = {
                "Suomi": "Merkintäteksti",
                "Deutsch": "Gravurtext",
                "Français": "Texte de gravure",
                "English": "Engraving text",
                "Bosanski": "Tekst graviranja",
                "Polski": "Tekst grawerowania",
            }.get(self.language.get(), "Märktext")
            return f"{prefix} {marking_match.group(1)}:"
        return source

    def _tooltip(self, widget: tk.Widget, source: str) -> HoverTooltip:
        return HoverTooltip(widget, lambda: self._t(source))

    def _support_t(self, source: str) -> str:
        return SUPPORT_TRANSLATIONS.get(self.language.get(), {}).get(source, source)

    def _translate_widgets(self, parent: tk.Misc | None = None) -> None:
        parent = parent or self
        for widget in parent.winfo_children():
            try:
                source = getattr(widget, "_sg_source_text", None)
                if source is None:
                    source = str(widget.cget("text"))
                    widget._sg_source_text = source
                if source:
                    widget.configure(text=self._t(source))
            except (tk.TclError, AttributeError):
                pass
            self._translate_widgets(widget)
        if hasattr(self, "notebook"):
            for tab_id, source in zip(
                self.notebook.tabs(), ("Program", "Maskin och yta", "Märktext")
            ):
                self.notebook.tab(tab_id, text=self._t(source))

    def _change_language(self, *_args: object) -> None:
        self._build_menu()
        self._build_menu_buttons()
        self._translate_widgets()
        self._update_unit_labels()
        self._sync_orientation_display()
        if self.status.get() in {text.get("Fyll i ett programnummer för att börja.", "") for text in TRANSLATIONS.values()} or self.status.get() == "Fyll i ett programnummer för att börja.":
            self.status.set(self._t("Fyll i ett programnummer för att börja."))
        self._update_configuration()
        self._draw_preview()

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label=self._t("Nytt projekt"), command=self.new_project, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label=self._t("Spara projekt…"), command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label=self._t("Ladda projekt…"), command=self.load_project, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label=self._t("Avsluta"), command=self.destroy)
        menu.add_cascade(label=self._t("Arkiv"), menu=file_menu)

        info_menu = tk.Menu(menu, tearoff=False)
        info_menu.add_command(label=self._t("Rapportera ett fel…"), command=self.show_bug_report)
        info_menu.add_command(label=self._t("Skicka önskemål…"), command=self.show_request_form)
        menu.add_cascade(label=self._t("Hjälp"), menu=info_menu)

        about_menu = tk.Menu(menu, tearoff=False)
        about_menu.add_command(label=self._t("Om SubGlyph"), command=self.show_about)
        about_menu.add_command(label="Buy Me a Coffee", command=self.open_buy_me_a_coffee)
        menu.add_cascade(label=self._t("Om"), menu=about_menu)
        self.main_menu = menu
        self.file_menu = file_menu
        self.info_menu = info_menu
        self.about_menu = about_menu
        self.permission_menu = tk.Menu(menu, tearoff=False)
        self.permission_menu.add_command(label="Operatör", command=self._become_operator)
        self.permission_menu.add_command(label="Admin…", command=self._login_admin)
        self.permission_menu.add_separator()
        self.permission_menu.add_command(label="Ändra adminlösenord…", command=self._change_admin_password)
        # Use the in-window menu row below. Attaching this menu natively as well
        # creates a duplicate row on desktops that render Tk menus themselves.
        self.configure(menu="")
        self.bind_all("<Control-n>", lambda _event: self.new_project())
        self.bind_all("<Control-s>", lambda _event: self.save_project())
        self.bind_all("<Control-o>", lambda _event: self.load_project())

    def _build_menu_buttons(self) -> None:
        """Provide an in-window menu row on desktops that hide Tk's native menu."""
        if hasattr(self, "menu_button_frame"):
            self.menu_button_frame.destroy()
        frame = ttk.Frame(self.ui_root)
        frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        file_button = ttk.Menubutton(frame, text=self._t("Arkiv"), menu=self.file_menu)
        file_button.pack(side="left")
        help_button = ttk.Menubutton(frame, text=self._t("Hjälp"), menu=self.info_menu)
        help_button.pack(side="left", padx=(8, 0))
        about_button = ttk.Menubutton(frame, text=self._t("Om"), menu=self.about_menu)
        about_button.pack(side="left", padx=(8, 0))
        self.permission_button = ttk.Menubutton(frame, menu=self.permission_menu)
        self.permission_button.pack(side="right")
        self.menu_button_frame = frame
        self._update_permissions()

    def _update_permissions(self):
        if hasattr(self, "permission_button"):
            self.permission_button.configure(text="Behörighet: " + ("Admin" if self.is_admin else "Operatör"))
            self.permission_menu.entryconfigure("Ändra adminlösenord…", state="normal" if self.is_admin else "disabled")
        for index, entry in enumerate(getattr(self, "marking_text_entries", [])):
            locked = not self.is_admin and self.dynamic_markings[index].kind != "Statisk text"
            entry.configure(state="readonly" if locked else "normal")
        for button in getattr(self, "marking_type_buttons", []):
            button.configure(state="normal" if self.is_admin else "disabled")

    def _become_operator(self):
        self.is_admin = False
        self._update_permissions()

    def _login_admin(self):
        password = simpledialog.askstring("Admin", "Adminlösenord:", show="*", parent=self)
        if password is None:
            return
        if not self.access_control.check_password(password):
            messagebox.showerror("Admin", "Fel lösenord.", parent=self)
            return
        self.is_admin = True
        self._update_permissions()

    def _change_admin_password(self):
        if not self.is_admin:
            return
        current = simpledialog.askstring("Ändra adminlösenord", "Nuvarande lösenord:", show="*", parent=self)
        if current is None:
            return
        if not self.access_control.check_password(current):
            messagebox.showerror("Admin", "Fel lösenord.", parent=self)
            return
        password = simpledialog.askstring("Ändra adminlösenord", "Nytt lösenord:", show="*", parent=self)
        if password is None:
            return
        confirmation = simpledialog.askstring("Ändra adminlösenord", "Upprepa nytt lösenord:", show="*", parent=self)
        if confirmation is None:
            return
        if password != confirmation:
            messagebox.showerror("Admin", "Lösenorden stämmer inte överens.", parent=self)
            return
        try:
            self.access_control.set_password(password)
        except (OSError, ValueError) as error:
            messagebox.showerror("Admin", str(error), parent=self)
            return
        messagebox.showinfo("Admin", "Adminlösenordet har ändrats.", parent=self)

    def _project_data(self) -> dict[str, object]:
        return {
            "dynamic_markings": [item.to_dict() for item in getattr(self, "dynamic_markings", [])],
            "format_version": PROJECT_FORMAT_VERSION,
            "language": self.language.get(),
            "units": self.units.get(),
            "project_name": self.project_name.get(),
            "program_number": self.program_number.get(),
            "program_name": self.program_name.get(),
            "separate_programs": self.separate_programs.get(),
            "marking_program_numbers": [
                value.get() for value in self.marking_program_numbers
            ],
            "comment": self.comment.get(),
            "open_after_generate": self.open_after_generate.get(),
            "control_system": self.control_system.get(),
            "spindle": self.spindle.get(),
            "turret": self.turret.get(),
            "surface": self.surface.get(),
            "orientation": self.orientation.get(),
            "depth_direction": self.depth_direction.get(),
            "has_y_axis": self.has_y_axis.get(),
            "plane": self.plane.get(),
            "marking_diameter": self.marking_diameter.get(),
            "stock_type": self.stock_type.get(),
            "hex_across_flats": self.hex_across_flats.get(),
            "stock_width": self.stock_width.get(),
            "stock_height": self.stock_height.get(),
            "stock_length": self.stock_length.get(),
            "marking_depth": self.marking_depth.get(),
            "clearance": self.clearance.get(),
            "character_height": self.character_height.get(),
            "character_width": self.character_width.get(),
            "text_rotation": self.text_rotation.get(),
            "flip_text": self.flip_text.get(),
            "mirror_text": self.mirror_text.get(),
            "marking_z": self.marking_z.get(),
            "marking_z_values": [value.get() for value in self.marking_z_values],
            "marking_y_values": [value.get() for value in self.marking_y_values],
            "markings": [value.get() for value in self.markings],
            "marking_placements": [value.get() for value in self.marking_placements],
            "marking_c_values": [value.get() for value in self.marking_c_values],
            "c_axis": self.c_axis.get(),
            "marking_heights": [value.get() for value in self.marking_heights],
            "marking_widths": [value.get() for value in self.marking_widths],
            "marking_spacings": [value.get() for value in self.marking_spacings],
            "marking_rotations": [value.get() for value in self.marking_rotations],
            "marking_bending_radii": [value.get() for value in self.marking_bending_radii],
            "marking_mirrors": [value.get() for value in self.marking_mirrors],
            "marking_z_directions": [value.get() for value in self.marking_z_directions],
            "use_system_font": self.use_system_font.get(),
            "font_source": self.font_source.get(),
            "system_font_name": self.system_font_name.get(),
            "custom_font_path": self.custom_font_path.get(),
            "plunge_feed": self.plunge_feed.get(),
            "engraving_feed": self.engraving_feed.get(),
        }

    def _remember_directory(self, kind: str, selected_path: str | Path) -> None:
        path = Path(selected_path)
        directory = path if path.is_dir() else path.parent
        self.dialog_directories[kind] = str(directory.resolve())
        try:
            save_directory_history(self.dialog_directories)
        except OSError:
            # A read-only or unavailable settings directory must not prevent saving.
            pass

    def save_project(self) -> None:
        self.record_activity("Försökte spara projekt")
        initial_name = self.project_name.get().strip()
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Spara SubGlyph-projekt",
            initialfile=f"{initial_name}.SG" if initial_name else "",
            initialdir=self.dialog_directories.get("project"),
            defaultextension=".SG",
            filetypes=(("SubGlyph-projekt", "*.SG"), ("Alla filer", "*.*")),
        )
        if not destination:
            return
        try:
            Path(destination).write_text(
                json.dumps(self._project_data(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as error:
            messagebox.showerror("Kunde inte spara projektet", str(error), parent=self)
            return
        self.status.set(f"Sparade projektet {destination}")
        self._remember_directory("project", destination)
        self.record_activity("Projekt sparat")

    def new_project(self) -> None:
        current = self._project_data()
        current_language = self.language.get()
        comparable_current = {key: value for key, value in current.items() if key != "language"}
        comparable_defaults = {
            key: value for key, value in self._new_project_defaults.items() if key != "language"
        }
        if comparable_current != comparable_defaults and not messagebox.askyesno(
            self._t("Nytt projekt"),
            self._t("Alla aktuella projektuppgifter rensas. Vill du fortsätta?"),
            parent=self,
        ):
            return
        defaults = dict(self._new_project_defaults)
        defaults["language"] = current_language
        self._apply_project_data(defaults)
        self.status.set(self._t("Nytt projekt skapat."))
        self.record_activity("Nytt projekt skapat")

    def load_project(self) -> None:
        self.record_activity("Försökte ladda projekt")
        source = filedialog.askopenfilename(
            parent=self,
            title="Ladda SubGlyph-projekt",
            filetypes=(("SubGlyph-projekt", "*.SG"), ("Alla filer", "*.*")),
        )
        if not source:
            return
        try:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format_version") != PROJECT_FORMAT_VERSION:
                raise ValueError("Projektfilens format stöds inte av denna version.")
            self._apply_project_data(data)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
            messagebox.showerror("Kunde inte ladda projektet", str(error), parent=self)
            return
        self.status.set(f"Laddade projektet {source}")
        self.record_activity("Projekt laddat")

    def _apply_project_data(self, data: dict[str, object]) -> None:
        self.dynamic_markings = [DynamicMarking() for _ in range(MARKING_ROW_COUNT)]
        for index, item in enumerate(data.get("dynamic_markings", [])):
            if index >= MARKING_ROW_COUNT or not isinstance(item, dict):
                raise ValueError("Ogiltiga inställningar för dynamisk märkning.")
            self.dynamic_markings[index] = DynamicMarking.from_dict(item)
        scalar_variables = {
            "language": self.language,
            "units": self.units,
            "project_name": self.project_name,
            "program_number": self.program_number,
            "program_name": self.program_name,
            "comment": self.comment,
            "control_system": self.control_system,
            "spindle": self.spindle,
            "turret": self.turret,
            "surface": self.surface,
            "orientation": self.orientation,
            "depth_direction": self.depth_direction,
            "plane": self.plane,
            "marking_diameter": self.marking_diameter,
            "stock_type": self.stock_type,
            "hex_across_flats": self.hex_across_flats,
            "stock_width": self.stock_width,
            "stock_height": self.stock_height,
            "stock_length": self.stock_length,
            "marking_depth": self.marking_depth,
            "clearance": self.clearance,
            "character_height": self.character_height,
            "character_width": self.character_width,
            "text_rotation": self.text_rotation,
            "marking_z": self.marking_z,
            "c_axis": self.c_axis,
            "plunge_feed": self.plunge_feed,
            "engraving_feed": self.engraving_feed,
            "system_font_name": self.system_font_name,
            "font_source": self.font_source,
            "custom_font_path": self.custom_font_path,
        }
        for key, variable in scalar_variables.items():
            if key in data:
                variable.set(str(data[key]))
        self.control_system.set(normalize_control_system(self.control_system.get()))
        self._active_units = self.units.get()
        self.orientation.set(
            LEGACY_ORIENTATIONS.get(self.orientation.get(), self.orientation.get())
        )
        if self.plane.get() in ("XC", "XCY", "ZXC"):
            self.plane.set("XZ+C")
        elif self.plane.get() in ("XY", "XYZ", "XYZC"):
            self.plane.set("XYZ+C")
        if "project_name" not in data:
            legacy_name = str(data.get("comment", "")).strip()
            self.project_name.set(legacy_name or f"O{self.program_number.get().strip()}")
        if "separate_programs" in data:
            self.separate_programs.set(bool(data["separate_programs"]))
        if "open_after_generate" in data:
            self.open_after_generate.set(bool(data["open_after_generate"]))
        if "has_y_axis" in data:
            self.has_y_axis.set(bool(data["has_y_axis"]))
        if "flip_text" in data:
            self.flip_text.set(bool(data["flip_text"]))
        if "mirror_text" in data:
            self.mirror_text.set(bool(data["mirror_text"]))
        if "use_system_font" in data:
            self.use_system_font.set(bool(data["use_system_font"]))
            if "font_source" not in data and self.use_system_font.get():
                self.font_source.set("System")
        for key, variables in (
            ("markings", self.markings),
            ("marking_placements", self.marking_placements),
            ("marking_z_values", self.marking_z_values),
            ("marking_y_values", self.marking_y_values),
            ("marking_c_values", self.marking_c_values),
            ("marking_heights", self.marking_heights),
            ("marking_widths", self.marking_widths),
            ("marking_spacings", self.marking_spacings),
            ("marking_rotations", self.marking_rotations),
            ("marking_bending_radii", self.marking_bending_radii),
            ("marking_mirrors", self.marking_mirrors),
            ("marking_z_directions", self.marking_z_directions),
            ("marking_program_numbers", self.marking_program_numbers),
        ):
            values = data.get(key)
            if isinstance(values, list):
                for variable, value in zip(variables, values):
                    variable.set(bool(value) if isinstance(variable, tk.BooleanVar) else str(value))
        if "marking_z_values" not in data and "marking_z" in data:
            for variable in self.marking_z_values:
                variable.set(str(data["marking_z"]))
        if "marking_heights" not in data:
            for variable in self.marking_heights:
                variable.set(str(data.get("character_height", "5")))
        if "marking_widths" not in data:
            for variable in self.marking_widths:
                variable.set(str(data.get("character_width", "3")))
        if "marking_rotations" not in data:
            legacy_rotation = float(str(data.get("text_rotation", "0")).replace(",", "."))
            if bool(data.get("flip_text", False)):
                legacy_rotation += 180
            for variable in self.marking_rotations:
                variable.set(format_nc_number(Decimal(str(legacy_rotation))))
        if "marking_bending_radii" not in data:
            legacy_radius = str(data.get("bending_radius", ""))
            for variable in self.marking_bending_radii:
                variable.set(legacy_radius)
        if "marking_mirrors" not in data:
            for variable in self.marking_mirrors:
                variable.set(bool(data.get("mirror_text", False)))
        if "marking_z_directions" not in data:
            for variable in self.marking_z_directions:
                variable.set("Z-")
        if "marking_program_numbers" not in data:
            for variable in self.marking_program_numbers:
                variable.set(self.program_number.get())
        self._update_configuration()
        self._update_program_mode()
        self._update_font_mode()

        for config in self.dynamic_markings:
            self.access_control.restore_verification(config, self.control_system.get())
        self._update_permissions()

    def show_about(self) -> None:
        messagebox.showinfo(
            self._t("Om SubGlyph"),
            f"{PRODUCT_NAME} version {APP_VERSION}\n\n"
            f"{self._t('Skapad av Kristian Simontaival.')}\n\n"
            f"{self._t('Programmet är helt gratis.')}",
            parent=self,
        )

    def show_bug_report(self) -> None:
        self.record_activity("Öppnade formuläret Rapportera ett fel")
        SupportForm(self, "bug")

    def show_request_form(self) -> None:
        self.record_activity("Öppnade formuläret Skicka önskemål")
        SupportForm(self, "request")

    def record_activity(self, description: str) -> None:
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        self.activity_log.append(f"{stamp}  {description}")
        del self.activity_log[:-100]

    def _diagnostic_text(self) -> str:
        settings = self._project_data() if hasattr(self, "language") else {}
        lines = ["SUBGLYPH DIAGNOSTIC LOG", "", "SYSTEM"]
        lines.extend(f"{key}: {value}" for key, value in system_information().items())
        lines.extend(("", "CURRENT SETTINGS", json.dumps(settings, ensure_ascii=False, indent=2)))
        lines.extend(("", "RECENT ACTIVITY"))
        lines.extend(self.activity_log or ("No activity recorded.",))
        return "\n".join(lines) + "\n"

    def generate_diagnostic_log(self) -> Path:
        self.record_activity("Genererade diagnoslogg")
        destination = timestamped_report_path("SubGlyph-diagnostic")
        destination.write_text(self._diagnostic_text(), encoding="utf-8")
        return destination

    def report_callback_exception(self, exc_type: type[BaseException], exc_value: BaseException, exc_traceback: object) -> None:
        """Persist uncaught Tk callback errors so they can be attached to reports."""
        destination = timestamped_report_path("SubGlyph-crash")
        crash = [
            "SUBGLYPH CRASH DUMP",
            "",
            f"Time: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            "",
            "TRACEBACK",
            "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            "",
            self._diagnostic_text(),
        ]
        try:
            destination.write_text("\n".join(crash), encoding="utf-8")
            detail = f"\n\nEn crashdump sparades som:\n{destination}"
        except OSError:
            detail = ""
        messagebox.showerror("Oväntat programfel", f"Ett oväntat fel inträffade:\n{exc_value}{detail}", parent=self)

    def open_buy_me_a_coffee(self) -> None:
        webbrowser.open(BUY_ME_A_COFFEE_URL)

    def _open_in_text_editor(self, paths: Iterable[Path]) -> None:
        if not self.open_after_generate.get():
            return
        try:
            for path in paths:
                if sys.platform == "win32":
                    command = ["notepad.exe", str(path)]
                elif sys.platform == "darwin":
                    command = ["open", "-a", "TextEdit", str(path)]
                else:
                    command = ["xdg-open", str(path)]
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except OSError as error:
            messagebox.showwarning(
                "Kunde inte öppna textredigeraren",
                f"Programmet sparades, men textredigeraren kunde inte öppnas:\n{error}",
                parent=self,
            )

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        self.ui_root = root
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)
        root.rowconfigure(2, weight=1)

        ttk.Label(
            root, text=PRODUCT_NAME, font=("TkDefaultFont", 20, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))

        self.notebook = ttk.Notebook(root)
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=(0, 16))
        program_tab = ttk.Frame(self.notebook, padding=18)
        machine_tab = ttk.Frame(self.notebook, padding=18)
        text_tab = ttk.Frame(self.notebook, padding=18)
        self.notebook.add(program_tab, text="Program")
        self.notebook.add(machine_tab, text="Maskin och yta")
        self.notebook.add(text_tab, text="Märktext")
        for tab in (program_tab, machine_tab, text_tab):
            tab.columnconfigure(1, weight=1)

        self._build_program_tab(program_tab)
        self._build_machine_tab(machine_tab)
        self._build_text_tab(text_tab)

        preview_frame = ttk.LabelFrame(root, text="Förhandsvisning", padding=12)
        preview_frame.grid(row=2, column=1, sticky="nsew")
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(1, weight=1)
        preview_controls = ttk.Frame(preview_frame)
        preview_controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(preview_controls, text="Ämnesvisning:").pack(side="left")
        for mode in ("Solid", "Wireframe", "Av"):
            ttk.Radiobutton(
                preview_controls,
                text=mode,
                value=mode,
                variable=self.preview_mode,
                command=self._draw_preview,
            ).pack(side="left", padx=(8, 0))
        self.preview_canvas = tk.Canvas(
            preview_frame, background="#f7f8fa", highlightthickness=0
        )
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda _event: self._draw_preview())
        self.preview_canvas.bind("<ButtonPress-1>", self._start_preview_drag)
        self.preview_canvas.bind("<B1-Motion>", self._drag_preview)
        self.preview_canvas.bind("<ButtonPress-3>", self._start_preview_drag)
        self.preview_canvas.bind("<B3-Motion>", self._roll_preview)
        self.preview_canvas.bind("<ButtonRelease-1>", self._end_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-3>", self._end_preview_drag)
        self.preview_canvas.bind("<MouseWheel>", self._zoom_preview)
        self.preview_canvas.bind("<Button-4>", self._zoom_preview)
        self.preview_canvas.bind("<Button-5>", self._zoom_preview)
        self.preview_canvas.configure(cursor="fleur")

        footer = ttk.Frame(root)
        footer.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status, foreground="#555555").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(
            footer,
            text="Öppna i textredigerare efter generering",
            variable=self.open_after_generate,
        ).grid(row=0, column=1, sticky="e", padx=(12, 14))
        ttk.Button(footer, text="Generera NC", command=self.generate_nc).grid(
            row=0, column=2, sticky="e"
        )

    def _labeled_entry(
        self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar
    ) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=7
        )
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=7)
        return entry

    def _build_program_tab(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="Språk:").grid(row=0, column=0, sticky="w", pady=7)
        language_units = ttk.Frame(tab)
        language_units.grid(row=0, column=1, sticky="ew", pady=7)
        language_units.columnconfigure(0, weight=1)
        ttk.Combobox(
            language_units, textvariable=self.language, values=LANGUAGES, state="readonly"
        ).grid(row=0, column=0, sticky="ew")
        ttk.Radiobutton(
            language_units, text="MM", value="MM", variable=self.units,
            command=lambda: self._select_units("MM"),
        ).grid(row=0, column=1, padx=(16, 4))
        ttk.Radiobutton(
            language_units, text="INCH", value="INCH", variable=self.units,
            command=lambda: self._select_units("INCH"),
        ).grid(row=0, column=2, padx=(4, 0))
        ttk.Label(tab, text="Styrsystem:").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Combobox(
            tab,
            textvariable=self.control_system,
            values=CONTROL_SYSTEMS,
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=7)
        tab.grid_slaves(row=0, column=0)[0].grid_configure(row=1)
        name_entry = self._labeled_entry(tab, 2, "Projektnamn:", self.project_name)
        self._labeled_entry(tab, 3, "Programkommentar:", self.comment)
        self.program_format_help = ttk.Label(
            tab,
            text="FANUC (ISO) sparas utan filändelse, OKUMA OSP (ISO) som Programnamn.SSB och SIEMENS SINUMERIK (ISO) som programnummer.spf.",
            foreground="#555555",
            wraplength=480,
        )
        self.program_format_help.grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )
        ttk.Label(
            tab,
            text=("SubGlyph skapar ett underprogram. Verktygsval, spindelvarvtal, "
                  "arbetsplan och första säkra förpositionering ska anges i huvudprogrammet "
                  "innan underprogrammet anropas."),
            foreground="#a12622",
            wraplength=480,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(14, 0))
        name_entry.focus_set()

    def _build_machine_tab(self, tab: ttk.Frame) -> None:
        ttk.Label(tab, text="Spindel:").grid(row=0, column=0, sticky="w", pady=7)
        ttk.Combobox(
            tab, textvariable=self.spindle, values=("HSP", "MSP"), state="readonly"
        ).grid(row=0, column=1, sticky="ew", pady=7)

        ttk.Label(tab, text="Revolver:").grid(row=1, column=0, sticky="w", pady=7)
        ttk.Combobox(
            tab, textvariable=self.turret, values=("Lower", "Upper"), state="readonly"
        ).grid(row=1, column=1, sticky="ew", pady=7)

        ttk.Label(tab, text="Märkyta:").grid(row=2, column=0, sticky="w", pady=7)
        surface_frame = ttk.Frame(tab)
        surface_frame.grid(row=2, column=1, sticky="w", pady=7)
        ttk.Radiobutton(
            surface_frame, text="Runt en axel", value="Runt en axel", variable=self.surface
        ).pack(side="left")
        ttk.Radiobutton(
            surface_frame,
            text="Frontplan",
            value="Frontplan",
            variable=self.surface,
        ).pack(side="left", padx=(14, 0))

        ttk.Label(tab, text="Textriktning:").grid(row=3, column=0, sticky="w", pady=7)
        self.orientation_combo = ttk.Combobox(
            tab,
            textvariable=self.orientation_display,
            state="readonly",
        )
        self.orientation_combo.grid(row=3, column=1, sticky="ew", pady=7)
        self.orientation_combo.bind("<<ComboboxSelected>>", self._select_orientation)

        self.direction_label = ttk.Label(tab, text="Djupets riktning:")
        self.direction_label.grid(row=4, column=0, sticky="w", pady=7)
        ttk.Combobox(
            tab,
            textvariable=self.depth_direction,
            values=("-", "+"),
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", pady=7)

        ttk.Checkbutton(tab, text="Maskinen har Y-axel", variable=self.has_y_axis).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=7
        )
        ttk.Label(tab, text="Aktiva axlar:").grid(row=6, column=0, sticky="w", pady=7)
        self.plane_combo = ttk.Combobox(tab, textvariable=self.plane, state="readonly")
        self.plane_combo.grid(row=6, column=1, sticky="ew", pady=7)

        ttk.Label(tab, text="Ämnestyp:").grid(row=7, column=0, sticky="w", pady=7)
        stock_frame = ttk.Frame(tab)
        stock_frame.grid(row=7, column=1, sticky="ew", pady=7)
        for column, stock_type in enumerate(("Rund", "Sexkant", "Rektangel")):
            ttk.Radiobutton(
                stock_frame, text=stock_type, value=stock_type,
                variable=self.stock_type, command=self._update_configuration,
            ).grid(row=0, column=column, padx=(0 if column == 0 else 12, 0))
        ttk.Label(stock_frame, text="Ämneslängd:").grid(
            row=0, column=3, padx=(12, 4)
        )
        ttk.Entry(stock_frame, textvariable=self.stock_length, width=4).grid(
            row=0, column=4, padx=(0, 3)
        )
        self.stock_length_unit_label = ttk.Label(stock_frame, text="mm")
        self.stock_length_unit_label.grid(row=0, column=5)

        self.stock_dimension_label = ttk.Label(tab, text="Detaljdiameter (mm):")
        self.stock_dimension_label.grid(row=8, column=0, sticky="w", padx=(0, 12), pady=7)
        self.stock_dimension_frame = ttk.Frame(tab)
        self.stock_dimension_frame.grid(row=8, column=1, sticky="ew", pady=7)
        self.stock_dimension_frame.columnconfigure(0, weight=1)
        self.stock_dimension_frame.columnconfigure(1, weight=1)
        self.stock_dimension_entry_1 = ttk.Entry(self.stock_dimension_frame, textvariable=self.marking_diameter)
        self.stock_dimension_entry_1.grid(row=0, column=0, sticky="ew")
        self.stock_dimension_entry_2 = ttk.Entry(self.stock_dimension_frame, textvariable=self.stock_height)
        self.diameter_entry = self.stock_dimension_entry_1

        self._labeled_entry(tab, 9, "Märkdjup (mm):", self.marking_depth)
        self._labeled_entry(tab, 10, "Frigång (mm):", self.clearance)
        self.plunge_feed_entry = self._labeled_entry(
            tab, 11, "Nedmatning (mm/min):", self.plunge_feed
        )
        self.engraving_feed_entry = self._labeled_entry(
            tab, 12, "Gravering (mm/min):", self.engraving_feed
        )
        ttk.Label(tab, textvariable=self.diameter_preview, foreground="#245a87").grid(
            row=13, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

    def _build_text_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(1, weight=1)
        program_frame = ttk.Frame(tab)
        program_frame.grid(row=0, column=0, columnspan=11, sticky="ew", pady=(0, 12))
        ttk.Label(program_frame, text="Programnummer:").pack(side="left")
        self.shared_program_entry = ttk.Entry(
            program_frame, textvariable=self.program_number, width=10
        )
        self.shared_program_entry.pack(side="left", padx=(8, 18))
        program_name_label = ttk.Label(program_frame, text="Programnamn:")
        program_name_label.pack(side="left")
        self.program_name_entry = ttk.Entry(
            program_frame, textvariable=self.program_name, width=18
        )
        self.program_name_entry.pack(side="left", padx=(8, 18))
        program_name_help = (
            "Programnamnet blir Okumas SSB-filnamn, till exempel hej.SSB. "
            "Programnumret används fortfarande som O-nummer inne i SSB-filen."
        )
        self._tooltip(program_name_label, program_name_help)
        self._tooltip(self.program_name_entry, program_name_help)
        ttk.Checkbutton(
            program_frame,
            text="Separata märkprogram",
            variable=self.separate_programs,
            command=self._update_program_mode,
        ).pack(side="left")
        ttk.Label(program_frame, text="C-axel:").pack(side="left", padx=(18, 0))
        self.c_axis_entry = ttk.Entry(program_frame, textvariable=self.c_axis, width=5)
        self.c_axis_entry.pack(side="left", padx=(8, 0))
        self._tooltip(
            self.c_axis_entry,
            "NC-adressen för rotationsaxeln. C är standard; skriv exempelvis CS "
            "för att posta CS60 i stället för C60.",
        )

        ttk.Label(tab, text="Text").grid(row=1, column=1, sticky="w")
        ttk.Label(tab, text="O-nr").grid(row=1, column=2, sticky="w", padx=(8, 0))
        self.first_position_label = ttk.Label(tab, text="ZPos (-)")
        self.first_position_label.grid(row=1, column=3, sticky="w", padx=(8, 0))
        self.first_position_tooltip = self._tooltip(
            self.first_position_label,
            "ZPos anger var på detaljen märkningen placeras. Skriv alltid positionen "
            "som ett negativt värde, till exempel -5. Z-riktningen avgör sedan om "
            "posten använder Z-5 eller Z+5.",
        )
        self.y_position_label = ttk.Label(tab, text="Y")
        self.y_position_label.grid(row=1, column=4, sticky="w", padx=(8, 0))
        self.second_position_label = ttk.Label(tab, text="C°")
        self.second_position_label.grid(row=1, column=5, sticky="w", padx=(8, 0))
        ttk.Label(tab, text="Höjd").grid(row=1, column=6, sticky="w", padx=(8, 0))
        ttk.Label(tab, text="Bredd").grid(row=1, column=7, sticky="w", padx=(8, 0))
        ttk.Label(tab, text="Rot°").grid(row=1, column=8, sticky="w", padx=(8, 0))
        self.spacing_label = ttk.Label(tab, text="Mellanr.")
        self.spacing_label.grid(row=1, column=9, sticky="w", padx=(8, 0))
        self._tooltip(self.spacing_label, "Fritt avstånd mellan tecknen i mm/inch, exempelvis 0,4. Värdet 0 ger inget extra mellanrum.")
        ttk.Label(tab, text="Radie").grid(row=1, column=10, sticky="w", padx=(8, 0))
        ttk.Label(tab, text="Spegel").grid(row=1, column=11, sticky="w", padx=(8, 0))
        self.z_direction_label = ttk.Label(tab, text="Z-rikt.")
        self.z_direction_label.grid(row=1, column=12, sticky="w", padx=(8, 0))
        self._tooltip(
            self.z_direction_label,
            "Z-riktning påverkar endast postens Z-värden. Den ändrar inte märktextens "
            "utseende eller förhandsvisningen.",
        )
        self.y_entries: list[ttk.Entry] = []
        self.c_entries: list[ttk.Entry] = []
        self.radius_entries: list[ttk.Entry] = []
        self.program_number_entries: list[ttk.Entry] = []
        self.z_position_entries: list[ttk.Entry] = []
        self.z_position_tooltips: list[HoverTooltip] = []
        self.z_direction_combos: list[ttk.Combobox] = []
        self.marking_text_entries = []
        self.marking_type_buttons = []
        for index, variable in enumerate(self.markings, start=1):
            type_button = ttk.Button(tab, text=f"Märktext {index}…", command=lambda i=index - 1: self._edit_dynamic(i))
            self.marking_type_buttons.append(type_button)
            type_button.grid(
                row=index + 1, column=0, sticky="w", padx=(0, 10), pady=6
            )
            text_entry = ttk.Entry(tab, textvariable=variable)
            self.marking_text_entries.append(text_entry)
            text_entry.grid(
                row=index + 1, column=1, sticky="ew", pady=6
            )
            program_entry = ttk.Entry(
                tab, textvariable=self.marking_program_numbers[index - 1], width=7
            )
            program_entry.grid(row=index + 1, column=2, sticky="ew", padx=(8, 0), pady=6)
            self.program_number_entries.append(program_entry)
            z_entry = ttk.Entry(
                tab, textvariable=self.marking_z_values[index - 1], width=9
            )
            z_entry.grid(row=index + 1, column=3, sticky="ew", padx=(8, 0), pady=6)
            self.z_position_entries.append(z_entry)
            self.z_position_tooltips.append(self._tooltip(
                z_entry,
                "Placering längs detaljens Z-axel. Ange alltid ett negativt värde, "
                "exempelvis -5. Fältet ändrar inte vald Z-riktning.",
            ))
            y_entry = ttk.Entry(
                tab, textvariable=self.marking_y_values[index - 1], width=7
            )
            y_entry.grid(row=index + 1, column=4, sticky="ew", padx=(8, 0), pady=6)
            self.y_entries.append(y_entry)
            c_entry = ttk.Entry(
                tab, textvariable=self.marking_c_values[index - 1], width=7
            )
            c_entry.grid(row=index + 1, column=5, sticky="ew", padx=(8, 0), pady=6)
            self.c_entries.append(c_entry)
            ttk.Entry(tab, textvariable=self.marking_heights[index - 1], width=6).grid(
                row=index + 1, column=6, sticky="ew", padx=(8, 0), pady=6
            )
            ttk.Entry(tab, textvariable=self.marking_widths[index - 1], width=6).grid(
                row=index + 1, column=7, sticky="ew", padx=(8, 0), pady=6
            )
            ttk.Entry(tab, textvariable=self.marking_rotations[index - 1], width=6).grid(
                row=index + 1, column=8, sticky="ew", padx=(8, 0), pady=6
            )
            ttk.Entry(tab, textvariable=self.marking_spacings[index - 1], width=6).grid(
                row=index + 1, column=9, sticky="ew", padx=(8, 0), pady=6
            )
            radius_entry = ttk.Entry(
                tab, textvariable=self.marking_bending_radii[index - 1], width=7
            )
            radius_entry.grid(row=index + 1, column=10, sticky="ew", padx=(8, 0), pady=6)
            self.radius_entries.append(radius_entry)
            ttk.Checkbutton(tab, variable=self.marking_mirrors[index - 1]).grid(
                row=index + 1, column=11, padx=(12, 0), pady=6
            )
            direction_combo = ttk.Combobox(
                tab, textvariable=self.marking_z_directions[index - 1],
                values=("Z-", "Z+"), state="readonly", width=4,
            )
            direction_combo.grid(row=index + 1, column=12, sticky="ew", padx=(8, 0), pady=6)
            self.z_direction_combos.append(direction_combo)
            self._tooltip(
                direction_combo,
                "Väljer hur ZPos skrivs i NC-posten: Z- eller Z+. Valet påverkar "
                "inte förhandsvisningen.",
            )
        font_frame = ttk.Frame(tab)
        font_frame.grid(row=8, column=0, columnspan=13, sticky="ew", pady=(10, 2))
        ttk.Label(font_frame, text="Teckensnitt:").grid(row=0, column=0, sticky="w")
        for column, (label, value) in enumerate(
            (("SubGlyph", "SubGlyph"), ("Installerat", "System"),
             ("Egen fontfil", "Custom")), start=1
        ):
            ttk.Radiobutton(
                font_frame, text=label, value=value, variable=self.font_source,
                command=self._update_font_mode,
            ).grid(row=0, column=column, sticky="w", padx=(10, 0))
        self.system_font_combo = ttk.Combobox(
            font_frame, textvariable=self.system_font_name,
            values=tuple(self.available_system_fonts), state="disabled", width=32,
        )
        self.system_font_combo.grid(row=1, column=1, columnspan=3, sticky="w", padx=(10, 0), pady=(6, 0))
        self.system_font_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_font_mode())
        if self.available_system_fonts:
            self.system_font_name.set(next(iter(self.available_system_fonts)))
        self.custom_font_button = ttk.Button(
            font_frame, text="Välj fontfil…", command=self._choose_custom_font
        )
        self.custom_font_button.grid(row=1, column=4, sticky="w", padx=(12, 0), pady=(6, 0))
        self.custom_font_label = ttk.Label(font_frame, text="", foreground="#555555")
        self.custom_font_label.grid(row=1, column=5, sticky="w", padx=(8, 0), pady=(6, 0))
        self._tooltip(font_frame,
            "SubGlyph använder en enlinjefont. Installerad eller egen fontfil "
            "konturgraveras och skapar därför fler NC-block.")
        ttk.Separator(tab).grid(row=9, column=0, columnspan=13, sticky="ew", pady=12)
        self.position_help = ttk.Label(
            tab,
            text=("Tomma märktexter ignoreras. Z0 är ämnets ändplan; varje text "
                  "har egen Z/C-position, storlek, rotation, spegling och Z-riktning."),
            foreground="#555555",
            wraplength=620,
        )
        self.position_help.grid(
            row=10, column=0, columnspan=13, sticky="w", pady=(4, 0)
        )
        self._update_font_mode()
        self._update_program_mode()

    def _update_font_mode(self) -> None:
        if not hasattr(self, "system_font_combo"):
            return
        mode = self.font_source.get()
        self.use_system_font.set(mode != "SubGlyph")
        self.system_font_combo.configure(
            state="readonly" if mode == "System" and self.available_system_fonts else "disabled"
        )
        self.custom_font_button.configure(state="normal" if mode == "Custom" else "disabled")
        custom_path = Path(self.custom_font_path.get()) if self.custom_font_path.get() else None
        self.custom_font_label.configure(
            text=custom_path.name if mode == "Custom" and custom_path else ""
        )
        self._text_mask_cache.clear()
        self._draw_preview()

    def _choose_custom_font(self) -> None:
        current = Path(self.custom_font_path.get()) if self.custom_font_path.get() else None
        selected = filedialog.askopenfilename(
            parent=self, title=self._t("Välj fontfil"),
            initialdir=str(current.parent) if current else None,
            filetypes=(("TrueType/OpenType", "*.ttf *.otf *.ttc"), ("Alla filer", "*.*")),
        )
        if not selected:
            return
        try:
            ImageFont.truetype(selected, 32)
        except OSError as error:
            messagebox.showerror(
                self._t("Ogiltig fontfil"), self._t("Fontfilen kunde inte läsas:") + f"\n{error}",
                parent=self,
            )
            return
        self.custom_font_path.set(selected)
        self.font_source.set("Custom")
        self._update_font_mode()

    def _selected_font_path(self) -> str | None:
        if self.font_source.get() == "SubGlyph":
            return None
        if self.font_source.get() == "System":
            return self.available_system_fonts.get(self.system_font_name.get())
        path = Path(self.custom_font_path.get())
        return str(path) if path.is_file() else None

    def _update_program_mode(self) -> None:
        if not hasattr(self, "shared_program_entry"):
            return
        separate = self.separate_programs.get()
        self.shared_program_entry.configure(state="disabled" if separate else "normal")
        for entry in self.program_number_entries:
            entry.configure(state="normal" if separate else "disabled")

    def _select_units(self, selected: str) -> None:
        previous = getattr(self, "_active_units", "MM")
        if selected == previous:
            return
        factor = Decimal("0.0393700787401575") if selected == "INCH" else Decimal("25.4")
        linear_values = (
            self.marking_diameter, self.marking_depth, self.clearance,
            self.hex_across_flats, self.stock_width, self.stock_height, self.stock_length,
            self.plunge_feed, self.engraving_feed,
            *self.marking_z_values, *self.marking_y_values,
            *self.marking_heights, *self.marking_widths, *self.marking_spacings,
            *self.marking_bending_radii,
        )
        for variable in linear_values:
            raw = variable.get().strip()
            if not raw:
                continue
            try:
                converted = Decimal(raw.replace(",", ".")) * factor
            except InvalidOperation:
                continue
            variable.set(format_nc_number(converted.quantize(Decimal("0.0001"))))
        self._active_units = selected
        self._update_unit_labels()
        self._update_configuration()

    def _update_unit_labels(self) -> None:
        suffix = "mm" if self.units.get() == "MM" else "inch"
        for widget in self.winfo_children():
            self._update_unit_labels_in(widget, suffix)

    def _update_unit_labels_in(self, parent: tk.Misc, suffix: str) -> None:
        for widget in parent.winfo_children():
            source = getattr(widget, "_sg_source_text", "")
            if source in ("Detaljdiameter (mm):", "Märkdjup (mm):", "Frigång (mm):"):
                widget.configure(text=self._t(source).replace("mm", suffix))
            self._update_unit_labels_in(widget, suffix)

    def _sync_orientation_display(self) -> None:
        values = (self._t(ORIENTATION_ALONG_Z), self._t(ORIENTATION_AROUND_CIRCUMFERENCE))
        self.orientation_combo.configure(values=values)
        self.orientation_display.set(self._t(self.orientation.get()))

    def _select_orientation(self, _event: object = None) -> None:
        displayed = self.orientation_display.get()
        for internal in (ORIENTATION_ALONG_Z, ORIENTATION_AROUND_CIRCUMFERENCE):
            if displayed == self._t(internal):
                self.orientation.set(internal)
                return

    def _bind_preview_updates(self) -> None:
        self.language.trace_add("write", self._change_language)
        variables = (
            self.control_system,
            self.spindle,
            self.turret,
            self.surface,
            self.orientation,
            self.depth_direction,
            self.has_y_axis,
            self.plane,
            self.marking_diameter,
            self.stock_type,
            self.hex_across_flats,
            self.stock_width,
            self.stock_height,
            self.stock_length,
            self.marking_depth,
            self.clearance,
            self.character_height,
            self.character_width,
            self.text_rotation,
            self.flip_text,
            self.mirror_text,
            self.marking_z,
            self.plunge_feed,
            self.engraving_feed,
            *self.markings,
            *self.marking_placements,
            *self.marking_z_values,
            *self.marking_y_values,
            *self.marking_c_values,
            self.c_axis,
            *self.marking_heights,
            *self.marking_widths,
            *self.marking_spacings,
            *self.marking_rotations,
            *self.marking_bending_radii,
            *self.marking_mirrors,
            *self.marking_z_directions,
        )
        for variable in variables:
            variable.trace_add("write", self._update_configuration)

    def _update_configuration(self, *_args: object) -> None:
        self._sync_orientation_display()
        around_axis = self.surface.get() == "Runt en axel"
        stock_type = self.stock_type.get()
        unit_suffix = "mm" if self.units.get() == "MM" else "inch"
        self.stock_length_unit_label.configure(text=unit_suffix)
        if stock_type == "Rund":
            self.stock_dimension_label.configure(
                text=self._t("Detaljdiameter (mm):").replace("mm", unit_suffix)
            )
            self.stock_dimension_entry_1.configure(textvariable=self.marking_diameter)
            self.stock_dimension_entry_2.grid_remove()
        elif stock_type == "Sexkant":
            self.stock_dimension_label.configure(
                text=f"{self._t('Nyckelvidd (NV):').rstrip(': ')} ({unit_suffix}):"
            )
            self.stock_dimension_entry_1.configure(textvariable=self.hex_across_flats)
            self.stock_dimension_entry_2.grid_remove()
        else:
            self.stock_dimension_label.configure(
                text=f"{self._t('Bredd / höjd:').rstrip(': ')} ({unit_suffix}):"
            )
            self.stock_dimension_entry_1.configure(textvariable=self.stock_width)
            self.stock_dimension_entry_2.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        if self.control_system.get() == OKUMA_OSP_ISO:
            self.program_name_entry.configure(state="normal")
            self.program_format_help.configure(
                text=self._t("Sparas som Programnamn.SSB. O-numret finns inne i filen.")
            )
        elif self.control_system.get() == SIEMENS_SINUMERIK_ISO:
            self.program_name_entry.configure(state="disabled")
            self.program_format_help.configure(
                text=self._t("Sparas som programnummer.spf, en fil per unikt O-nummer.")
            )
        else:
            self.program_name_entry.configure(state="disabled")
            self.program_format_help.configure(
                text=self._t("Sparas som O + programnummer utan filändelse, en fil per unikt O-nummer.")
            )
        if around_axis:
            self.first_position_label.configure(text="ZPos (-)")
            zpos_help = (
                "ZPos anger var på detaljen märkningen placeras. Skriv alltid positionen "
                "som ett negativt värde, till exempel -5. Z-riktningen avgör sedan om "
                "posten använder Z-5 eller Z+5."
            )
            self.first_position_tooltip.text = lambda source=zpos_help: self._t(source)
            z_help = (
                "Placering längs detaljens Z-axel. Ange alltid ett negativt värde, "
                "exempelvis -5. Fältet ändrar inte vald Z-riktning."
            )
            for tooltip in self.z_position_tooltips:
                tooltip.text = lambda source=z_help: self._t(source)
            self.second_position_label.configure(text="C°")
        else:
            self.first_position_label.configure(text="XPos")
            xpos_help = "XPos anger märkningens grundposition i X på frontplanet."
            self.first_position_tooltip.text = lambda source=xpos_help: self._t(source)
            for tooltip in self.z_position_tooltips:
                tooltip.text = lambda source=xpos_help: self._t(source)
            self.second_position_label.configure(text="C°")
        self.orientation_combo.configure(state="readonly" if around_axis else "disabled")
        self.diameter_entry.configure(state="normal")
        self.plunge_feed_entry.configure(state="normal")
        self.engraving_feed_entry.configure(state="normal")
        depth_axis = "X" if around_axis else "Z"
        direction = self._t("Djupets riktning:").rstrip(": ")
        self.direction_label.configure(text=f"{direction} ({depth_axis}):")

        if not around_axis:
            planes = ("XYZ+C",)
        else:
            planes = ("XYZ+C", "XZ+C") if self.has_y_axis.get() else ("XZ+C",)
        self.plane_combo.configure(values=planes)
        if self.plane.get() not in planes:
            self.plane.set(planes[0])

        uses_y = self.has_y_axis.get() and (not around_axis or self.plane.get() == "XYZ+C")
        for entry in self.y_entries:
            entry.configure(state="normal" if uses_y else "disabled")
        for entry in self.c_entries:
            entry.configure(state="normal")
        for entry in self.radius_entries:
            entry.configure(state="disabled" if around_axis else "normal")
        if around_axis and self.plane.get() == "XYZ+C":
            self.position_help.configure(
                text=self._t("Z/Y positionerar texten på den indexerade ytan. C väljer "
                             "detaljytans vinkel; X används för märkdjupet.")
            )
        elif around_axis:
            self.position_help.configure(
                text=self._t("Z0 är ämnets ändplan. Z/C formar märkningen och X används "
                             "för märkdjupet; Y är låst i XZ+C-läge.")
            )
        else:
            self.position_help.configure(
                text=("På frontplanet anger X/Y grundpositionen. C indexerar positionen "
                      "runt detaljcentrum; Rot vrider endast texten på sin plats. Radie "
                      "böjer texten utan att flytta mittpunkten. X0/Y0 är detaljcentrum.")
            )

        if around_axis:
            try:
                engraving, clearance = calculate_diameter_levels(
                    self.marking_diameter.get(),
                    self.marking_depth.get(),
                    self.clearance.get(),
                )
                self.diameter_preview.set(
                    f"{self._t('Gravering')}: X{format_nc_number(engraving)}    "
                    f"{self._t('Frigång')}: X{format_nc_number(clearance)}"
                )
            except ValueError:
                self.diameter_preview.set(self._t("Kontrollera diametermåtten."))
        else:
            self.diameter_preview.set(
                f"Ø {self.marking_diameter.get()} mm    Djupaxel: Z{self.depth_direction.get()}    "
                "X0/Y0 = detaljcentrum"
            )
        self._draw_preview()

    def _start_preview_drag(self, event: tk.Event) -> None:
        self._drag_origin = (event.x, event.y)

    def _drag_preview(self, event: tk.Event) -> None:
        if self._drag_origin is None:
            return
        old_x, old_y = self._drag_origin
        self.view_yaw += (event.x - old_x) * 0.7
        self.view_pitch = max(-80, min(80, self.view_pitch + (event.y - old_y) * 0.7))
        self._drag_origin = (event.x, event.y)
        self._draw_preview()

    def _roll_preview(self, event: tk.Event) -> None:
        if self._drag_origin is None:
            return
        old_x, _old_y = self._drag_origin
        self.view_roll = (self.view_roll + (event.x - old_x) * 0.8) % 360
        self._drag_origin = (event.x, event.y)
        self._draw_preview()

    def _end_preview_drag(self, _event: tk.Event) -> None:
        self._drag_origin = None

    def _zoom_preview(self, event: tk.Event) -> None:
        zoom_in = getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4
        self.preview_zoom = max(0.45, min(2.5, self.preview_zoom * (1.12 if zoom_in else 1 / 1.12)))
        self._draw_preview()

    def _transform_point(self, point: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = point
        roll = math.radians(self.view_roll)
        y, z = y * math.cos(roll) - z * math.sin(roll), y * math.sin(roll) + z * math.cos(roll)
        yaw = math.radians(self.view_yaw)
        pitch = math.radians(self.view_pitch)
        x1 = x * math.cos(yaw) + z * math.sin(yaw)
        z1 = -x * math.sin(yaw) + z * math.cos(yaw)
        y1 = y * math.cos(pitch) - z1 * math.sin(pitch)
        z2 = y * math.sin(pitch) + z1 * math.cos(pitch)
        return x1, y1, z2

    def _project_point(
        self, point: tuple[float, float, float], cx: float, cy: float, scale: float
    ) -> tuple[float, float]:
        x, y, _z = self._transform_point(point)
        # Orthographic projection keeps a cylindrical workpiece cylindrical.
        return cx + x * scale, cy - y * scale

    def _draw_3d_workpiece(
        self,
        canvas: tk.Canvas,
        cx: float,
        cy: float,
        scale: float,
        color: str,
        wireframe: bool = False,
    ) -> None:
        stock_type = self.stock_type.get()
        segments = 6 if stock_type == "Sexkant" else 4 if stock_type == "Rektangel" else (16 if wireframe else 32)
        y_scale = z_scale = 1.0
        try:
            reference_diameter = max(0.001, float(self.marking_diameter.get().replace(",", ".")))
        except ValueError:
            reference_diameter = 50.0
        try:
            stock_length = max(0.001, float(self.stock_length.get().replace(",", ".")))
            half_length = stock_length / reference_diameter
        except ValueError:
            half_length = 1.4
        if stock_type == "Sexkant":
            try:
                across_flats = max(0.001, float(self.hex_across_flats.get().replace(",", ".")))
                y_scale = z_scale = 2 * across_flats / (math.sqrt(3) * reference_diameter)
            except ValueError:
                pass
        elif stock_type == "Rektangel":
            try:
                width = max(0.001, float(self.stock_width.get().replace(",", ".")))
                height = max(0.001, float(self.stock_height.get().replace(",", ".")))
                y_scale, z_scale = width / reference_diameter, height / reference_diameter
            except ValueError:
                pass
        angle_offset = math.pi / 6 if stock_type == "Sexkant" else math.pi / 4 if stock_type == "Rektangel" else 0.0
        def section_point(index: int) -> tuple[float, float]:
            angle = angle_offset + index * 2 * math.pi / segments
            return math.cos(angle) * y_scale, math.sin(angle) * z_scale
        if wireframe:
            rings = (-half_length, half_length)
            for x in rings:
                ring = [
                    self._project_point(
                        (x, *section_point(i)),
                        cx,
                        cy,
                        scale,
                    )
                    for i in range(segments)
                ]
                canvas.create_line(*sum(ring + [ring[0]], ()), fill=color, width=2)
            for i in range(0, segments, 2):
                section_y, section_z = section_point(i)
                edge = [
                    self._project_point(
                        (x, section_y, section_z), cx, cy, scale
                    )
                    for x in rings
                ]
                canvas.create_line(*sum(edge, ()), fill="#7d8c96")
            return

        faces: list[tuple[float, list[tuple[float, float]], str]] = []
        for i in range(segments):
            y1, z1 = section_point(i)
            y2, z2 = section_point(i + 1)
            points_3d = [
                (-half_length, y1, z1), (half_length, y1, z1),
                (half_length, y2, z2), (-half_length, y2, z2),
            ]
            depth = sum(self._transform_point(point)[2] for point in points_3d) / 4
            shade = max(0, min(255, 202 + int(28 * max(0, (y1 + y2) / 2))))
            fill = f"#{shade:02x}{min(242, shade + 7):02x}{min(248, shade + 12):02x}"
            faces.append((depth, [self._project_point(p, cx, cy, scale) for p in points_3d], fill))
        for depth, points, fill in sorted(faces, key=lambda face: face[0]):
            canvas.create_polygon(*sum(points, ()), fill=fill, outline="#9ca9b2")

        for x, fill in ((-half_length, "#cbd5dc"), (half_length, "#e5ebef")):
            ring_3d = [
                (x, *section_point(i))
                for i in range(segments)
            ]
            center_depth = self._transform_point((x, 0, 0))[2]
            if center_depth >= 0:
                ring = [self._project_point(point, cx, cy, scale) for point in ring_3d]
                canvas.create_polygon(*sum(ring, ()), fill=fill, outline=color, width=2)

    def _draw_surface_markings(
        self, canvas: tk.Canvas, cx: float, cy: float, scale: float
    ) -> None:
        active = [(i, value.get().strip()) for i, value in enumerate(self.markings) if value.get().strip()]
        if not active:
            active = [(-1, self._t("DIN MÄRKTEXT"))]
        try:
            diameter_mm = float(self.marking_diameter.get().replace(",", "."))
        except ValueError:
            diameter_mm = 50.0
        radius_mm = max(0.1, diameter_mm / 2)
        try:
            stock_length_mm = max(
                0.001, float(self.stock_length.get().replace(",", "."))
            )
            stock_end_x = stock_length_mm / max(0.001, diameter_mm)
        except ValueError:
            stock_end_x = 1.4

        def cylinder_point(u_mm: float, v_mm: float, theta_center: float) -> tuple[float, float, float]:
            theta = theta_center + v_mm / radius_mm
            return u_mm / radius_mm, math.cos(theta), math.sin(theta)

        def front_point(u_mm: float, v_mm: float, height: float) -> tuple[float, float, float]:
            normal_scale = max(radius_mm, height * 4, 1)
            return stock_end_x + 0.01, u_mm / normal_scale, v_mm / normal_scale

        def indexed_flat_face(c_degrees: float) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
            """Return face midpoint and tangent for the flat side selected by C."""
            if self.stock_type.get() == "Sexkant":
                count, offset = 6, math.pi / 6
                try:
                    nv = float(self.hex_across_flats.get().replace(",", "."))
                    radius_scale = nv / (math.sqrt(3) * radius_mm)
                except ValueError:
                    radius_scale = 1.0
                vertices = [
                    (math.cos(offset + i * 2 * math.pi / count) * radius_scale,
                     math.sin(offset + i * 2 * math.pi / count) * radius_scale)
                    for i in range(count)
                ]
            else:
                try:
                    half_width = float(self.stock_width.get().replace(",", ".")) / (2 * radius_mm)
                    half_height = float(self.stock_height.get().replace(",", ".")) / (2 * radius_mm)
                except ValueError:
                    half_width = half_height = 1.0
                vertices = [
                    (half_width, half_height), (-half_width, half_height),
                    (-half_width, -half_height), (half_width, -half_height),
                ]
            target = (math.cos(math.radians(c_degrees)), math.sin(math.radians(c_degrees)))
            candidates = []
            for i, first in enumerate(vertices):
                second = vertices[(i + 1) % len(vertices)]
                midpoint = ((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
                length = math.hypot(second[0] - first[0], second[1] - first[1]) or 1.0
                tangent = ((second[0] - first[0]) / length, (second[1] - first[1]) / length)
                normal_length = math.hypot(*midpoint) or 1.0
                normal = (midpoint[0] / normal_length, midpoint[1] / normal_length)
                candidates.append((normal[0] * target[0] + normal[1] * target[1], midpoint, tangent, normal))
            _, midpoint, tangent, normal = max(candidates, key=lambda item: item[0])
            return midpoint, tangent, normal

        for _row, (index, text_value) in enumerate(active):
            try:
                height_mm = float(self.marking_heights[index].get().replace(",", ".")) if index >= 0 else 5.0
                width_mm = float(self.marking_widths[index].get().replace(",", ".")) if index >= 0 else 3.0
                rotation = float(self.marking_rotations[index].get().replace(",", ".")) if index >= 0 else 0.0
                spacing_mm = float(self.marking_spacings[index].get().replace(",", ".")) if index >= 0 else 0.0
            except ValueError:
                height_mm, width_mm, rotation, spacing_mm = 5.0, 3.0, 0.0, 0.0
            rotation_rad = math.radians(rotation)
            mirrored = self.marking_mirrors[index].get() if index >= 0 else False
            if self.surface.get() == "Runt en axel":
                if index >= 0:
                    try:
                        theta = math.radians(float(self.marking_c_values[index].get().replace(",", ".")))
                    except ValueError:
                        theta = 0.0
                    try:
                        text_z = float(self.marking_z_values[index].get().replace(",", "."))
                    except ValueError:
                        text_z = 0.0
                else:
                    theta = 0.0
                    text_z = -radius_mm * 0.8
                base_angle = (
                    0.0 if self.orientation.get() == ORIENTATION_ALONG_Z else math.pi / 2
                )
                baseline_angle = base_angle + rotation_rad
                anchor_u = text_z
                if index >= 0 and self.plane.get() == "XYZ+C":
                    try:
                        anchor_v = float(
                            self.marking_y_values[index].get().replace(",", ".")
                        )
                    except ValueError:
                        anchor_v = 0.0
                else:
                    anchor_v = 0.0
                flat_face = (
                    indexed_flat_face(math.degrees(theta))
                    if self.plane.get() == "XYZ+C" and self.stock_type.get() != "Rund"
                    else None
                )
            else:
                theta = 0.0
                if index >= 0:
                    try:
                        anchor_u = float(
                            self.marking_z_values[index].get().replace(",", ".")
                        )
                        anchor_v = float(
                            self.marking_y_values[index].get().replace(",", ".")
                        )
                        c_angle = float(
                            self.marking_c_values[index].get().replace(",", ".")
                        )
                    except ValueError:
                        anchor_u = anchor_v = c_angle = 0.0
                else:
                    anchor_u = 0.0
                    anchor_v = _row * height_mm * 1.35
                    c_angle = 0.0
                anchor_u, anchor_v = rotate_front_position(anchor_u, anchor_v, c_angle)
                try:
                    bending_radius = (
                        float(self.marking_bending_radii[index].get().replace(",", "."))
                        if index >= 0 and self.marking_bending_radii[index].get().strip()
                        else None
                    )
                    if bending_radius == 0:
                        bending_radius = None
                except ValueError:
                    bending_radius = None

            mirror_factor = 1.0 if mirrored else -1.0
            rigid_arc = self.surface.get() == "Frontplan" and bending_radius is not None
            normalized_preview = (
                text_value.upper().replace("Å", "A").replace("Ä", "A").replace("Ö", "O")
            )
            advance = width_mm + spacing_mm
            total_width = marking_text_width(
                normalized_preview, width_mm, spacing_mm
            )
            z_origin = (
                (abs(math.cos(baseline_angle)) * total_width
                 + abs(math.sin(baseline_angle)) * height_mm) / 2
            ) if (
                self.surface.get() == "Runt en axel"
                and self.orientation.get() == ORIENTATION_ALONG_Z
            ) else 0.0
            left = -total_width / 2
            glyphs = [
                (
                    self._text_mask(character),
                    left + position * advance + width_mm / 2,
                    width_mm,
                )
                for position, character in enumerate(normalized_preview)
            ]
            step = 2
            for mask, glyph_center, glyph_width in glyphs:
                mask_width, mask_height = mask.size
                pixels = mask.load()
                for py in range(0, mask_height, step):
                    for px in range(0, mask_width, step):
                        if pixels[px, py] < 96:
                            continue
                        quad: list[tuple[float, float]] = []
                        visible = True
                        for qx, qy in ((px, py), (px + step, py), (px + step, py + step), (px, py + step)):
                            raster_x = qx / mask_width - 0.5
                            local_horizontal = raster_x * glyph_width
                            horizontal = (glyph_center + local_horizontal) * mirror_factor
                            vertical = (0.5 - qy / mask_height) * height_mm
                            if self.surface.get() == "Runt en axel":
                                u = (anchor_u + horizontal * math.cos(baseline_angle)
                                     + vertical * math.cos(baseline_angle + math.pi / 2)
                                     + z_origin)
                                v = (anchor_v + horizontal * math.sin(baseline_angle)
                                     + vertical * math.sin(baseline_angle + math.pi / 2))
                                if flat_face is not None:
                                    midpoint, face_tangent, face_normal = flat_face
                                    point_3d = (
                                        stock_end_x + u / radius_mm,
                                        midpoint[0] + face_tangent[0] * v / radius_mm + face_normal[0] * 0.01,
                                        midpoint[1] + face_tangent[1] * v / radius_mm + face_normal[1] * 0.01,
                                    )
                                    surface_normal = (0, face_normal[0], face_normal[1])
                                else:
                                    raw_point = cylinder_point(u, v, theta)
                                    point_3d = (
                                        stock_end_x + raw_point[0], raw_point[1], raw_point[2]
                                    )
                                    local_theta = theta + v / radius_mm
                                    surface_normal = (0, math.cos(local_theta), math.sin(local_theta))
                                if self._transform_point(surface_normal)[2] < 0:
                                    visible = False
                                    break
                            elif rigid_arc:
                                mirrored_center = glyph_center * mirror_factor
                                horizontal = local_horizontal * mirror_factor
                                glyph_u, glyph_v = front_text_point(
                                    mirrored_center, 0, anchor_u, anchor_v,
                                    rotation, bending_radius,
                                )
                                tangent = math.radians(rotation) + mirrored_center / bending_radius
                                u = glyph_u + horizontal * math.cos(tangent) - vertical * math.sin(tangent)
                                v = glyph_v + horizontal * math.sin(tangent) + vertical * math.cos(tangent)
                                point_3d = front_point(u, v, height_mm)
                                if self._transform_point((1, 0, 0))[2] < 0:
                                    visible = False
                                    break
                            else:
                                u, v = front_text_point(
                                    horizontal, vertical, anchor_u, anchor_v,
                                    rotation, None,
                                )
                                point_3d = front_point(u, v, height_mm)
                                if self._transform_point((1, 0, 0))[2] < 0:
                                    visible = False
                                    break
                            quad.append(self._project_point(point_3d, cx, cy, scale))
                        if visible:
                            shade = pixels[px, py]
                            color = "#294b5e" if shade > 180 else "#496879"
                            canvas.create_polygon(*sum(quad, ()), fill=color, outline=color)

    def _text_mask(self, text: str) -> Image.Image:
        font_path = self._selected_font_path()
        cache_key = (text, font_path)
        cached = self._text_mask_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            font = ImageFont.truetype(font_path or "DejaVuSans.ttf", 64)
        except OSError:
            font = ImageFont.load_default(size=64)
        temporary = Image.new("L", (1, 1))
        draw = ImageDraw.Draw(temporary)
        box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        width, height = max(1, box[2] - box[0]), max(1, box[3] - box[1])
        mask = Image.new("L", (width + 4, height + 4))
        ImageDraw.Draw(mask).text(
            (2 - box[0], 2 - box[1]), text, font=font, fill=255, stroke_width=1
        )
        self._text_mask_cache[cache_key] = mask
        return mask

    def _draw_coordinate_triad(
        self, canvas: tk.Canvas, width: float, height: float
    ) -> None:
        origin_x, origin_y = width - 68, height - 72
        axes = (
            ("X", (0.0, 1.0, 0.0), "#d1493f"),
            ("Y", (0.0, 0.0, 1.0), "#2f8a4c"),
            ("Z", (1.0, 0.0, 0.0), "#286fb4"),
        )
        canvas.create_oval(
            origin_x - 3, origin_y - 3, origin_x + 3, origin_y + 3,
            fill="#27313a", outline=""
        )
        for label, vector, color in axes:
            transformed = self._transform_point(vector)
            length = 38
            end_x = origin_x + transformed[0] * length
            end_y = origin_y - transformed[1] * length
            canvas.create_line(
                origin_x, origin_y, end_x, end_y,
                fill=color, width=3, arrow="last"
            )
            canvas.create_text(
                end_x, end_y, text=label, fill=color,
                font=("TkDefaultFont", 9, "bold"), anchor="center"
            )

    def _draw_preview(self) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        canvas = self.preview_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 500)
        dark, blue, red = "#27313a", "#2878b5", "#c44b45"

        canvas.create_text(
            18,
            18,
            anchor="nw",
            text=f"{self.spindle.get()}  •  {self._t('Aktiva axlar:').rstrip(': ')} {self.plane.get()}",
            fill=dark,
            font=("TkDefaultFont", 11, "bold"),
        )
        cx, cy = width / 2, height * 0.36
        scale = min(width * 0.24, height * 0.19) * self.preview_zoom
        preview_mode = self.preview_mode.get()
        if preview_mode != "Av":
            self._draw_3d_workpiece(
                canvas, cx, cy, scale, dark, wireframe=preview_mode == "Wireframe"
            )
        if preview_mode != "Av":
            self._draw_surface_markings(canvas, cx, cy, scale)
        self._draw_coordinate_triad(canvas, width, height)
        hint = (
            self._t("Ämnesvisningen är avstängd")
            if preview_mode == "Av"
            else self._t("Vänsterdrag: fri vy • Högerdrag: rotera runt ämnet • Mushjul: zoom")
        )
        canvas.create_text(
            width / 2, height - 18, anchor="s", text=hint, fill="#63717c"
        )

    def _validate_geometry(self) -> None:
        if self.surface.get() == "Frontplan" and not self.has_y_axis.get():
            raise ValueError("Frontplansbearbetning kräver att maskinen har Y-axel.")
        project_name = self.project_name.get().strip()
        if not project_name:
            raise ValueError("Projektnamn måste anges.")
        if "/" in project_name or "\\" in project_name:
            raise ValueError("Projektnamnet får inte innehålla / eller \\.")
        if self.control_system.get() == OKUMA_OSP_ISO:
            program_name = self.program_name.get().strip()
            if not program_name:
                raise ValueError("Programnamn måste anges för OKUMA OSP (ISO).")
            if program_name.lower().endswith(".ssb"):
                raise ValueError("Ange programnamnet utan filändelsen .SSB.")
            if program_name in {".", ".."} or any(
                character in program_name for character in '/\\:*?"<>|'
            ):
                raise ValueError("Programnamnet innehåller tecken som inte får användas i filnamn.")
        active_indices = [
            index for index, text in enumerate(self.markings) if text.get().strip()
        ]
        if not active_indices:
            raise ValueError("Minst en märktext måste anges.")
        if self.font_source.get() != "SubGlyph" and not self._selected_font_path():
            raise ValueError("Det valda systemteckensnittet finns inte på den här datorn.")
        if self.separate_programs.get():
            program_numbers = [
                self.marking_program_numbers[index].get() for index in active_indices
            ]
        else:
            program_numbers = [self.program_number.get()]
        for number in program_numbers:
            normalized = number.strip().upper().removeprefix("O")
            if not re.fullmatch(r"\d+", normalized):
                raise ValueError("Programnummer måste innehålla enbart siffror.")
        depth = parse_dimension(self.marking_depth.get(), "Märkdjup")
        parse_dimension(self.clearance.get(), "Frigång")
        if depth == 0:
            raise ValueError("Märkdjupet måste vara större än noll.")
        if self.surface.get() == "Runt en axel":
            if self.stock_type.get() != "Rund" and self.plane.get() != "XYZ+C":
                raise ValueError("Sexkant och rektangel kräver aktiva axlar XYZ+C för plan gravering.")
            if self.stock_type.get() == "Rund":
                calculate_diameter_levels(
                    self.marking_diameter.get(), self.marking_depth.get(), self.clearance.get()
                )
            elif self.stock_type.get() == "Sexkant":
                across_flats = parse_dimension(self.hex_across_flats.get(), "Nyckelvidd")
                if across_flats == 0:
                    raise ValueError("Nyckelvidden måste vara större än noll.")
                if depth > across_flats:
                    raise ValueError("Märkdjupet kan inte vara större än nyckelvidden.")
            elif self.stock_type.get() == "Rektangel":
                stock_width = parse_dimension(self.stock_width.get(), "Ämnesbredd")
                stock_height = parse_dimension(self.stock_height.get(), "Ämneshöjd")
                if stock_width == 0:
                    raise ValueError("Ämnesbredden måste vara större än noll.")
                if stock_height == 0:
                    raise ValueError("Ämneshöjden måste vara större än noll.")
                if depth > min(stock_width, stock_height):
                    raise ValueError("Märkdjupet kan inte vara större än ämnets minsta sida.")
        else:
            diameter = parse_dimension(self.marking_diameter.get(), "Detaljdiameter")
            if diameter == 0:
                raise ValueError("Detaljdiametern måste vara större än noll.")
        for index, (text_value, z_value, y_value, c_value, height_value, width_value, rotation_value, spacing_value) in enumerate(
            zip(
                self.markings,
                self.marking_z_values,
                self.marking_y_values,
                self.marking_c_values,
                self.marking_heights,
                self.marking_widths,
                self.marking_rotations,
                self.marking_spacings,
            ),
            start=1,
        ):
            if text_value.get().strip():
                if self.surface.get() == "Runt en axel" and self.plane.get() == "XYZ+C":
                    position_names = "Z, Y, C"
                elif self.surface.get() == "Runt en axel":
                    position_names = "Z, C"
                else:
                    position_names = "X, Y"
                try:
                    Decimal(z_value.get().strip().replace(",", "."))
                    if not self.surface.get() == "Runt en axel" or self.plane.get() == "XYZ+C":
                        Decimal(y_value.get().strip().replace(",", "."))
                    Decimal(c_value.get().strip().replace(",", "."))
                    rotation = Decimal(rotation_value.get().strip().replace(",", "."))
                    spacing = Decimal(spacing_value.get().strip().replace(",", "."))
                except InvalidOperation as error:
                    raise ValueError(
                        f"{position_names} och rotation för märktext {index} måste vara tal."
                    ) from error
                height = parse_dimension(height_value.get(), f"Höjd för märktext {index}")
                width = parse_dimension(width_value.get(), f"Bredd för märktext {index}")
                if height == 0 or width == 0:
                    raise ValueError(f"Storleken för märktext {index} måste vara större än noll.")
                if spacing < 0:
                    raise ValueError(f"Mellanrummet för märktext {index} får inte vara negativt.")
        if self.surface.get() == "Frontplan":
            for index, (text_value, radius_value) in enumerate(
                zip(self.markings, self.marking_bending_radii), start=1
            ):
                if text_value.get().strip() and radius_value.get().strip():
                    radius = parse_coordinate(radius_value.get(), f"Böjningsradie för märktext {index}")
                    if radius == 0:
                        raise ValueError(
                            f"Böjningsradien för märktext {index} måste vara större än noll."
                        )
                    raise ValueError(
                        f"Böjd frontplanstext ingår inte i version {APP_VERSION} ännu. "
                        f"Lämna böjningsradien tom för märktext {index}."
                    )
        parse_dimension(self.plunge_feed.get(), "Nedmatningens matning")
        parse_dimension(self.engraving_feed.get(), "Graveringens matning")
        c_axis = self.c_axis.get().strip()
        if not re.fullmatch(r"[A-Za-z]+", c_axis):
            raise ValueError("C-axeln måste anges med en eller flera bokstäver, exempelvis C eller CS.")

    def generate_nc(self) -> None:
        self.record_activity("Försökte generera NC-program")
        try:
            self._validate_geometry()
            dynamic = self._dynamic_safety()
            if dynamic and not self._confirm_dynamic(dynamic):
                return
            header = self._build_nc_header()
            active_indices = [
                index for index, text in enumerate(self.markings) if text.get().strip()
            ]
            if self.separate_programs.get():
                grouped_programs = group_program_indices(
                    (self.marking_program_numbers[index].get(), index)
                    for index in active_indices
                )
                programs = [
                    (
                        number,
                        self.comment.get(),
                        self._build_nc_body(indices),
                    )
                    for number, indices in grouped_programs
                ]
            else:
                programs = [
                    (
                        self.program_number.get(),
                        self.comment.get(),
                        self._build_nc_body(active_indices),
                    )
                ]
            if self.control_system.get() == FANUC_ISO:
                fanuc_files = create_fanuc_files(
                    programs, header_lines=header, language=self.language.get()
                )
                content = ""
            elif self.control_system.get() == SIEMENS_SINUMERIK_ISO:
                fanuc_files = create_siemens_files(
                    programs, header_lines=header, language=self.language.get()
                )
                content = ""
            else:
                fanuc_files = []
                content = create_nc_collection(
                    programs,
                    header_lines=header,
                    control_system=self.control_system.get(),
                    language=self.language.get(),
                    c_axis=self.c_axis.get().strip().upper(),
                )
        except ValueError as error:
            messagebox.showerror("Ogiltiga uppgifter", str(error), parent=self)
            return

        okuma = self.control_system.get() == OKUMA_OSP_ISO
        if not okuma:
            controller_name = self.control_system.get().split(" (")[0]
            directory = filedialog.askdirectory(
                parent=self,
                title=f"Välj mapp för {controller_name}-program",
                mustexist=True,
                initialdir=self.dialog_directories.get("nc"),
            )
            if not directory:
                self.status.set("Sparandet avbröts.")
                return
            destinations = [Path(directory) / filename for filename, _ in fanuc_files]
            existing = [path.name for path in destinations if path.exists()]
            if existing and not messagebox.askyesno(
                "Skriv över filer?",
                "Följande program finns redan och kommer att skrivas över:\n"
                + "\n".join(existing),
                parent=self,
            ):
                self.status.set("Sparandet avbröts.")
                return
            try:
                for destination, (_, file_content) in zip(destinations, fanuc_files):
                    destination.write_text(file_content, encoding="utf-8", newline="\n")
            except OSError as error:
                messagebox.showerror(
                    "Kunde inte spara filen",
                    f"Filen kunde inte sparas:\n{error}",
                    parent=self,
                )
                return
            saved_names = ", ".join(path.name for path in destinations)
            self._remember_directory("nc", directory)
            self.status.set(f"Sparade {saved_names} i {directory}")
            self.record_activity(f"Genererade {len(destinations)} {controller_name}-program")
            messagebox.showinfo(
                "NC-program skapade",
                f"Sparade i {directory}:\n" + "\n".join(path.name for path in destinations),
                parent=self,
            )
            self._open_in_text_editor(destinations)
            return

        program_name = self.program_name.get().strip()
        directory = filedialog.askdirectory(
            parent=self,
            title="Välj mapp för OKUMA-program",
            initialdir=self.dialog_directories.get("nc"),
            mustexist=True,
        )
        if not directory:
            self.status.set("Sparandet avbröts.")
            return
        destination = Path(directory) / f"{program_name}.SSB"
        if destination.exists() and not messagebox.askyesno(
            "Skriv över fil?",
            f"{destination.name} finns redan och kommer att skrivas över.",
            parent=self,
        ):
            self.status.set("Sparandet avbröts.")
            return
        try:
            destination.write_text(content, encoding="utf-8", newline="\n")
        except OSError as error:
            messagebox.showerror(
                "Kunde inte spara filen", f"Filen kunde inte sparas:\n{error}", parent=self
            )
            return
        self.status.set(f"Sparade {destination}")
        self._remember_directory("nc", directory)
        self.record_activity("Genererade OKUMA-program")
        messagebox.showinfo("NC-program skapat", f"Filen har sparats:\n{destination}", parent=self)
        self._open_in_text_editor((destination,))

    def _build_nc_body(self, indices: Iterable[int] | None = None) -> list[str]:
        if self.surface.get() == "Frontplan":
            return self._build_front_nc_body(indices)
        diameter = float(self.marking_diameter.get().replace(",", "."))
        depth = float(self.marking_depth.get().replace(",", "."))
        clearance = float(self.clearance.get().replace(",", "."))
        plunge_feed = float(self.plunge_feed.get().replace(",", "."))
        engraving_feed = float(self.engraving_feed.get().replace(",", "."))
        rotation_clearance = None
        if self.stock_type.get() == "Sexkant":
            rotation_clearance = (
                2 * float(self.hex_across_flats.get().replace(",", ".")) / math.sqrt(3)
                + clearance
            )
        elif self.stock_type.get() == "Rektangel":
            rotation_clearance = (
                math.hypot(
                    float(self.stock_width.get().replace(",", ".")),
                    float(self.stock_height.get().replace(",", ".")),
                )
                + clearance
            )
        body: list[str] = []
        previous_index_c: float | None = None

        selected_indices = range(len(self.markings)) if indices is None else indices
        for index in selected_indices:
            text_value = self.markings[index]
            text = text_value.get().strip()
            if not text:
                continue
            c_value = float(self.marking_c_values[index].get().replace(",", "."))
            index_c = previous_index_c is None or not math.isclose(
                c_value, previous_index_c, abs_tol=1e-9
            )
            z_value = float(self.marking_z_values[index].get().replace(",", "."))
            y_value = (
                float(self.marking_y_values[index].get().replace(",", "."))
                if self.plane.get() == "XYZ+C"
                else 0.0
            )
            height = float(self.marking_heights[index].get().replace(",", "."))
            width = float(self.marking_widths[index].get().replace(",", "."))
            rotation = float(self.marking_rotations[index].get().replace(",", "."))
            spacing = float(self.marking_spacings[index].get().replace(",", "."))
            row_diameter = diameter
            if self.plane.get() == "XYZ+C" and self.stock_type.get() != "Rund":
                row_diameter = flat_stock_surface_dimension(
                    self.stock_type.get(),
                    float(self.hex_across_flats.get().replace(",", ".")),
                    float(self.stock_width.get().replace(",", ".")),
                    float(self.stock_height.get().replace(",", ".")),
                    c_value,
                )
            body.extend(
                self._row_blocks(index,
                    MantleMarking(
                        text=text,
                        c_degrees=c_value,
                        z=z_value,
                        diameter=row_diameter,
                        engraving_diameter=row_diameter - depth,
                        clearance_diameter=row_diameter + clearance,
                        rotation_clearance_diameter=rotation_clearance,
                        index_c=index_c,
                        height=height,
                        width=width,
                        orientation=self.orientation.get(),
                        rotation_degrees=rotation,
                        mirrored=self.marking_mirrors[index].get(),
                        plunge_feed=plunge_feed,
                        engraving_feed=engraving_feed,
                        plane=self.plane.get(),
                        y=y_value,
                        z_direction=self.marking_z_directions[index].get(),
                        c_axis=self.c_axis.get().strip().upper(),
                        character_spacing=spacing,
                        font_path=self._selected_font_path(),
                        turret=self.turret.get(),
                    ),
                )
            )
            body.append("")
            previous_index_c = c_value
        return body

    def _build_front_nc_body(self, indices: Iterable[int] | None = None) -> list[str]:
        depth = float(self.marking_depth.get().replace(",", "."))
        clearance = float(self.clearance.get().replace(",", "."))
        if self.depth_direction.get() == "+":
            engraving_z, clearance_z = depth, -clearance
        else:
            engraving_z, clearance_z = -depth, clearance
        plunge_feed = float(self.plunge_feed.get().replace(",", "."))
        engraving_feed = float(self.engraving_feed.get().replace(",", "."))
        body: list[str] = []
        previous_index_c: float | None = None
        selected_indices = range(len(self.markings)) if indices is None else indices
        for index in selected_indices:
            text = self.markings[index].get().strip()
            if not text:
                continue
            c_value = float(self.marking_c_values[index].get().replace(",", "."))
            index_c = previous_index_c is None or not math.isclose(
                c_value, previous_index_c, abs_tol=1e-9
            )
            body.extend(self._row_blocks(index, FrontMarking(
                text=text,
                x=float(self.marking_z_values[index].get().replace(",", ".")),
                y=float(self.marking_y_values[index].get().replace(",", ".")),
                c_degrees=c_value,
                engraving_z=engraving_z,
                clearance_z=clearance_z,
                height=float(self.marking_heights[index].get().replace(",", ".")),
                width=float(self.marking_widths[index].get().replace(",", ".")),
                rotation_degrees=float(self.marking_rotations[index].get().replace(",", ".")),
                mirrored=self.marking_mirrors[index].get(),
                index_c=index_c,
                plunge_feed=plunge_feed,
                engraving_feed=engraving_feed,
                c_axis=self.c_axis.get().strip().upper(),
                character_spacing=float(self.marking_spacings[index].get().replace(",", ".")),
                font_path=self._selected_font_path(),
                turret=self.turret.get(),
            )))
            body.append("")
            previous_index_c = c_value
        return body

    def _edit_dynamic(self, index):
        if not self.is_admin:
            return
        config = self.dynamic_markings[index]
        window = tk.Toplevel(self)
        window.title("Märktyp – test 1.12")
        fields = {}
        values = {"kind": config.kind, "start": str(config.start), "digits": str(config.digits),
                  "variable": config.variable, "position_variable": config.position_variable,
                  "date_format": config.date_format, "date": self.markings[index].get()}
        labels = {"kind": "Märktyp", "start": "Startvärde (separat initiering)", "digits": "Antal siffror (1–8)",
                  "variable": "Serienummervariabel", "position_variable": "Arbetsvariabel för teckenposition",
                  "date_format": "Datumformat", "date": "Fast datum (YYYY-MM-DD) eller fri text"}
        for row, (key, value) in enumerate(values.items()):
            fields[key] = tk.StringVar(value=value)
            ttk.Label(window, text=labels[key]).grid(row=row, column=0, sticky="w", padx=8, pady=4)
            choices = KINDS if key == "kind" else tuple(DATE_FORMATS) if key == "date_format" else None
            widget = (ttk.Combobox(window, textvariable=fields[key], values=choices, state="readonly")
                      if choices else ttk.Entry(window, textvariable=fields[key]))
            widget.grid(row=row, column=1, padx=8, pady=4)
        zeros = tk.BooleanVar(value=config.leading_zeros)
        verified = tk.BooleanVar(value=config.verified)
        for key in ("variable", "position_variable"):
            fields[key].trace_add("write", lambda *_: verified.set(False))
        ttk.Checkbutton(window, text="Ledande nollor", variable=zeros).grid(row=7, columnspan=2, sticky="w")
        ttk.Checkbutton(window, text="Jag har verifierat mot maskinens dokumentation att båda dessa variabler är säkra att använda.",
                        variable=verified).grid(row=8, columnspan=2, sticky="w", padx=8)
        ttk.Label(window, text="FANUC Custom Macro B krävs. Arbetsvariabeln skrivs över. Maskindatum stöds inte ännu.").grid(row=9, columnspan=2, padx=8, pady=8)
        def apply():
            if not self.is_admin:
                window.destroy()
                return
            try:
                new = DynamicMarking(kind=fields["kind"].get(), start=int(fields["start"].get()),
                                     digits=int(fields["digits"].get()), leading_zeros=zeros.get(),
                                     variable=fields["variable"].get(), position_variable=fields["position_variable"].get(),
                                     date_format=fields["date_format"].get())
                if verified.get():
                    new.verify()
                text = self.markings[index].get()
                if new.kind == "Serienummer":
                    from dynamic_marking import serial_digits
                    serial_digits(new.start, new.digits)
                    text = str(new.start).zfill(new.digits)
                elif new.kind == "Fast datum":
                    text = fields["date"].get()
                    try:
                        text = format_date(text, new.date_format)
                    except ValueError:
                        pass  # Explicit fixed text is also permitted.
                elif new.kind == "Maskindatum":
                    text = "MASKINDATUM"
                if new.kind == "Serienummer" and new.verified:
                    new.validate(self.control_system.get())
                    self.access_control.approve(new, self.control_system.get())
                self.dynamic_markings[index] = new
                self.markings[index].set(text)
                window.destroy()
                self._update_permissions()
                self._draw_preview()
            except (OSError, ValueError, KeyError) as error:
                messagebox.showerror("Ogiltiga inställningar", str(error), parent=window)
        ttk.Button(window, text="Spara", command=apply).grid(row=10, column=1, pady=8)
        ttk.Button(window, text="Avbryt", command=window.destroy).grid(row=10, column=0, pady=8)
        window.transient(self)
        window.grab_set()

    def _dynamic_safety(self):
        active = []
        for index, config in enumerate(getattr(self, "dynamic_markings", [])):
            if config.kind in ("Serienummer", "Maskindatum"):
                config.validate(self.control_system.get())
                if self.marking_bending_radii[index].get().strip():
                    raise ValueError("Dynamisk märkning stöder inte böjd text ännu.")
                active.append(config)
        counters = [config.variable for config in active]
        scratch = {config.position_variable for config in active}
        if len(counters) != len(set(counters)):
            raise ValueError("Använd en serienummerrad per räknare; samma räknare får inte ökas flera gånger.")
        if set(counters) & scratch:
            raise ValueError("En arbetsvariabel får inte vara en annan rads serienummerräknare.")
        return active

    def _confirm_dynamic(self, configs):
        window = tk.Toplevel(self)
        window.title("VARNING – maskinspecifik NC-kod")
        accepted = [False]
        text = ("Den här NC-koden innehåller makron och/eller maskinspecifika variabler.\n\n"
                "Fel variabel eller inkompatibel makrokod kan påverka maskinens funktion.\n"
                "Kontrollera programmet och vald variabel mot dokumentationen för aktuell maskin och styrning innan körning.\n\n"
                + self.control_system.get() + "\n" + "\n".join(
                    f"{c.kind}: {c.variable}; arbetsvariabel {c.position_variable}" for c in configs))
        ttk.Label(window, text=text, wraplength=560).pack(padx=20, pady=20)
        def approve():
            accepted[0] = True
            window.destroy()
        ttk.Button(window, text="Avbryt", command=window.destroy).pack(side="left", padx=20, pady=15)
        ttk.Button(window, text="Jag har verifierat – generera", command=approve).pack(side="right", padx=20, pady=15)
        window.transient(self)
        window.grab_set()
        self.wait_window(window)
        return accepted[0]

    def _row_blocks(self, index, marking):
        geometry = (front_marking_blocks if isinstance(marking, FrontMarking) else
                    lambda m: posted_mantle_marking_blocks(m, self.control_system.get()))
        configs = getattr(self, "dynamic_markings", [])
        config = configs[index] if configs else DynamicMarking()
        config.validate(self.control_system.get())
        if config.kind == "Serienummer":
            if marking.c_axis != "C":
                raise ValueError("Dynamisk märkning stöder endast C som rotationsaxel i testversionen.")
            return FanucDynamicPost().blocks(config, marking, geometry, index)
        return geometry(marking)

    def _build_nc_header(self) -> list[str]:
        configs = self._dynamic_safety()
        if not configs:
            return []
        return ["(*** VARNING - MASKINSPECIFIK MAKROKOD ***)",
                "(VERIFIERA VARIABEL OCH MAKROSTOD FORE KORNING)",
                *[f"(SERIENUMMER {c.variable} ARBETSVARIABEL {c.position_variable})" for c in configs]]


def resource_path(filename: str) -> Path:
    """Resolve bundled PyInstaller resources as well as source-tree files."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_root / filename


def show_startup_splash(app: SubGlyphApp, duration_ms: int = 2500) -> None:
    """Show the bundled splash briefly before revealing the main window."""
    splash_path = resource_path("SubGlyph2026Splash.png")
    if not splash_path.is_file():
        app.deiconify()
        return
    try:
        source_image = tk.PhotoImage(file=splash_path)
        scale = max(
            1,
            math.ceil(source_image.width() / 520),
            math.ceil(source_image.height() / 620),
        )
        splash_image = source_image.subsample(scale, scale)
    except (OSError, tk.TclError):
        app.deiconify()
        return

    splash = tk.Toplevel(app)
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    image_label = tk.Label(splash, image=splash_image, borderwidth=0)
    image_label.pack()
    tk.Label(
        image_label,
        text=f"Version {APP_VERSION}",
        foreground="white",
        background="#202020",
        font=("TkDefaultFont", 10, "bold"),
        padx=7,
        pady=3,
    ).place(relx=0.97, rely=0.96, anchor="se")
    splash.image = splash_image
    splash.update_idletasks()
    x = max(0, (splash.winfo_screenwidth() - splash.winfo_width()) // 2)
    y = max(0, (splash.winfo_screenheight() - splash.winfo_height()) // 2)
    splash.geometry(f"+{x}+{y}")

    def finish() -> None:
        if splash.winfo_exists():
            splash.destroy()
        app.deiconify()
        app.lift()
        app.focus_force()

    splash.after(duration_ms, finish)


def run_app() -> None:
    app = SubGlyphApp()
    app.withdraw()
    show_startup_splash(app)
    app.mainloop()


def install_crash_handler() -> None:
    original_hook = sys.excepthook

    def crash_hook(exc_type: type[BaseException], exc_value: BaseException, exc_traceback: object) -> None:
        try:
            destination = timestamped_report_path("SubGlyph-crash")
            lines = [
                "SUBGLYPH CRASH DUMP",
                "",
                f"Time: {datetime.now().astimezone().isoformat(timespec='seconds')}",
                *(f"{key}: {value}" for key, value in system_information().items()),
                "",
                "TRACEBACK",
                "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            ]
            destination.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
        original_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = crash_hook


if __name__ == "__main__":
    install_crash_handler()
    run_app()
