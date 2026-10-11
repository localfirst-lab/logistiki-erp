"""
LogistiKI — Pydantic-Schemas (Demo, alle Daten fiktiv).
Gemeinsamer Vertrag zwischen Agent, Flask-API, MCP-Server und UI.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

Einheit = Literal["Stück", "Rolle", "Paar", "Karton", "Palette", "kg", "m", "l"]
Zone = Literal["Standard", "Schwer", "Sperrig", "Gefahrstoff"]


class Artikel(BaseModel):
    artikel_nr: str = Field(description="Artikelnummer des Lieferanten oder interne Nummer")
    bezeichnung: str = Field(description="Artikelbezeichnung auf Deutsch")
    menge: float = Field(gt=0, description="Gelieferte Menge")
    einheit: Einheit = "Stück"

    @field_validator("artikel_nr")
    @classmethod
    def _nr_clean(cls, v: str) -> str:
        return v.strip().replace(" ", "")


class LieferscheinEntwurf(BaseModel):
    """Vom Agenten extrahierter Entwurf — wird NIE ohne menschliche Bestätigung gebucht."""
    lieferant: Optional[str] = None
    lieferschein_nr: Optional[str] = None
    lieferdatum: Optional[str] = Field(default=None, description="Format TT.MM.JJJJ")
    empfaenger: Optional[str] = None
    positionen: list[Artikel] = Field(default_factory=list)
    konfidenz: float = Field(default=0.0, ge=0, le=1, description="Selbsteinschätzung 0..1")
    hinweise: list[str] = Field(default_factory=list, description="Unsicherheiten für den Prüfer")


class Lagerplatz(BaseModel):
    """Generisches Regalsystem: Regal-Fach-Platz, z. B. A-03-12."""
    code: str
    regal: str
    fach: int
    platz: int
    zone: Zone = "Standard"
    kapazitaet: int = 100
    belegt: int = 0

    @property
    def frei(self) -> int:
        return self.kapazitaet - self.belegt


class LagerVorschlag(BaseModel):
    artikel_nr: str
    menge: float
    lagerplatz: str
    begruendung: str = Field(description="Kurze deutsche Begründung der Platzwahl")


class Etikett(BaseModel):
    artikel_nr: str
    bezeichnung: str
    menge: float
    einheit: str
    lagerplatz: str
    lieferschein_nr: Optional[str] = None
    pdf_pfad: str
    qr_inhalt: str = Field(description="Format: ARTIKEL|MENGE")


class Abschlussmeldung(BaseModel):
    """Antwort des Agenten nach abgeschlossener Buchung (Deutsch)."""
    text: str
    gebucht: list[LagerVorschlag]
    etiketten: list[Etikett]
