"""
Lagerlogik (generisches Regalsystem Regal-Fach-Platz) — deterministisch, erklärbar.
Der Agent ruft diese Funktionen als Tools auf; die KI "rät" keine Lagerplätze.

Regeln (Priorität):
  1. Gleicher Artikel schon eingelagert und Platz hat Kapazität  -> Bestand bündeln
  2. Passende Zone (Schwer / Sperrig / Gefahrstoff / Standard)
  3. Näher am Wareneingang (kleineres Regal, Fach, Platz) -> kurze Wege
  4. Genug freie Kapazität; bei Bedarf Menge auf mehrere Plätze splitten
"""
from __future__ import annotations

import sqlite3
from .config import DB_PATH
from .schemas import Artikel, LagerVorschlag

REGALE = ["A", "B", "C", "D"]
FAECHER = 6
PLAETZE = 4

# Schlüsselwörter -> Zone (Demo-Heuristik)
ZONEN_HINWEISE = {
    "Schwer": ["stahl", "träger", "profil", "paneel", "kanister"],
    "Sperrig": ["stuhl", "schreibtisch", "wand", "palette"],
    "Gefahrstoff": ["reiniger", "lösemittel", "farbe", "kleber"],
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_lager(conn: sqlite3.Connection | None = None) -> None:
    """Erzeugt Tabellen und ein fiktives Demo-Lager (idempotent)."""
    own = conn is None
    conn = conn or get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lagerplaetze (
            code TEXT PRIMARY KEY, regal TEXT, fach INTEGER, platz INTEGER,
            zone TEXT DEFAULT 'Standard', kapazitaet INTEGER DEFAULT 100
        );
        CREATE TABLE IF NOT EXISTS lagerbestand (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT REFERENCES lagerplaetze(code),
            artikel_nr TEXT, menge REAL, eingelagert_am TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    if conn.execute("SELECT COUNT(*) FROM lagerplaetze").fetchone()[0] == 0:
        zone_by_regal = {"A": "Standard", "B": "Standard", "C": "Schwer", "D": "Sperrig"}
        for r in REGALE:
            for f in range(1, FAECHER + 1):
                for p in range(1, PLAETZE + 1):
                    kap = 60 if zone_by_regal[r] in ("Schwer", "Sperrig") else 200
                    conn.execute(
                        "INSERT INTO lagerplaetze VALUES (?,?,?,?,?,?)",
                        (f"{r}-{f:02d}-{p:02d}", r, f, p, zone_by_regal[r], kap),
                    )
        # Zone Gefahrstoff: letztes Fach Regal B
        conn.execute("UPDATE lagerplaetze SET zone='Gefahrstoff' WHERE regal='B' AND fach=6")
    conn.commit()
    if own:
        conn.close()


def zone_fuer(bezeichnung: str) -> str:
    text = bezeichnung.lower()
    for zone, hints in ZONEN_HINWEISE.items():
        if any(h in text for h in hints):
            return zone
    return "Standard"


def _frei(conn: sqlite3.Connection, code: str, kap: int) -> float:
    belegt = conn.execute(
        "SELECT COALESCE(SUM(menge),0) FROM lagerbestand WHERE code=?", (code,)
    ).fetchone()[0]
    return kap - belegt


def vorschlag(artikel: Artikel, conn: sqlite3.Connection | None = None) -> list[LagerVorschlag]:
    """Liefert 1..n Vorschläge (Splitting bei Platzmangel). Bucht noch NICHTS."""
    own = conn is None
    conn = conn or get_db()
    init_lager(conn)
    zone = zone_fuer(artikel.bezeichnung)
    rest = artikel.menge
    out: list[LagerVorschlag] = []

    # 1. Bündeln mit vorhandenem Bestand desselben Artikels
    bekannte = conn.execute(
        """SELECT DISTINCT p.code, p.kapazitaet FROM lagerbestand b
           JOIN lagerplaetze p ON p.code=b.code WHERE b.artikel_nr=? ORDER BY p.code""",
        (artikel.artikel_nr,),
    ).fetchall()
    for row in bekannte:
        frei = _frei(conn, row["code"], row["kapazitaet"])
        if frei > 0 and rest > 0:
            menge = min(rest, frei)
            out.append(LagerVorschlag(
                artikel_nr=artikel.artikel_nr, menge=menge, lagerplatz=row["code"],
                begruendung=f"Artikel bereits hier gelagert – Bestand wird gebündelt ({zone}-Zone).",
            ))
            rest -= menge

    # 2./3./4. Passende Zone, nahe am Eingang, mit freier Kapazität
    if rest > 0:
        plaetze = conn.execute(
            "SELECT * FROM lagerplaetze WHERE zone=? ORDER BY regal, fach, platz", (zone,)
        ).fetchall()
        for p in plaetze:
            if rest <= 0:
                break
            if any(v.lagerplatz == p["code"] for v in out):
                continue
            frei = _frei(conn, p["code"], p["kapazitaet"])
            if frei <= 0:
                continue
            menge = min(rest, frei)
            out.append(LagerVorschlag(
                artikel_nr=artikel.artikel_nr, menge=menge, lagerplatz=p["code"],
                begruendung=f"Zone {zone}, kurzer Weg zum Wareneingang, {int(frei)} Einheiten frei.",
            ))
            rest -= menge

    if rest > 0:
        out.append(LagerVorschlag(
            artikel_nr=artikel.artikel_nr, menge=rest, lagerplatz="KLAERUNG",
            begruendung=f"Kein freier Platz in Zone {zone} – manuelle Klärung nötig.",
        ))
    if own:
        conn.close()
    return out


def einlagern(v: LagerVorschlag, conn: sqlite3.Connection) -> None:
    """Schreibt die bestätigte Einlagerung. Nur nach menschlicher Freigabe aufrufen."""
    if v.lagerplatz == "KLAERUNG":
        return
    conn.execute(
        "INSERT INTO lagerbestand (code, artikel_nr, menge) VALUES (?,?,?)",
        (v.lagerplatz, v.artikel_nr, v.menge),
    )
