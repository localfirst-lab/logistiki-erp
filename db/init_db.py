#!/usr/bin/env python3
"""
=======================================================
  INIT_DB.PY — Inizializza il database ERP demo
  LogistiKI — Simbio Ecosystem — Davide Carrieri
  Esegui: python db/init_db.py
=======================================================
"""
import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "erp_demo.db"

# Articoli REALI corrispondenti esattamente ai 3 Lieferschein Muster scansionati
ARTIKEL_DEMO = [
    # Muster 1: kalkül (Arbeitsschutz / Bekleidung -> Regal A)
    ("111111", "Latzhose blau, Gr. 52",                     "Arbeitsschutz",      "Stück", "A-01-01", 45),
    ("222222", "Latzhose grau, Gr. 54",                     "Arbeitsschutz",      "Stück", "A-01-02", 38),
    ("333333", "Overall grün, Gr. 53",                      "Arbeitsschutz",      "Stück", "A-01-03", 24),

    # Muster 2: Muster AG (Standard Verbindungstechnik / Verpackung -> Regal B)
    ("100001", "Sechskantschraube M8x30 DIN 933",           "Verbindungstechnik", "Stück", "B-01-01", 1250),
    ("100010", "Klebeband OPP 50mm x 66m",                  "Verpackung",         "Rolle", "B-01-02", 200),
    ("100012", "Stretchfolie 50cm x 300m",                  "Verpackung",         "Rolle", "B-01-03", 75),

    # Muster 3: Würth Industrie Service (Schwerlast / DIN & Stahl -> Regal C)
    ("100002", "Sechskantschraube M10x50 DIN 933 8.8",      "Schwerlast / DIN",   "Stück", "C-01-01", 850),
    ("100003", "Unterlegscheibe M8 DIN 125 Form A",         "Verbindungstechnik", "Stück", "C-01-02", 5000),
    ("100004", "Sicherungsmutter M8 DIN 985 verzinkt",       "Verbindungstechnik", "Stück", "C-01-03", 2300),
    ("100005", "Stahlprofil 40x40x2 mm, L=6m (Schwergut)",  "Schwerlast Träger",  "Stück", "C-01-01", 45),
]

# I 3 Lieferschein Reali dimostrati nel sistema
LIEFERSCHEINE_DEMO = [
    (
        "LI-2026-W982",
        "Würth Industrie Service GmbH & Co. KG",
        "07.10.2026",
        "Carrieri Logistik GmbH",
        "gebucht",
        json.dumps({
            "lieferschein_nr": "LI-2026-W982",
            "lieferant": "Würth Industrie Service GmbH & Co. KG",
            "empfaenger": "Carrieri Logistik GmbH",
            "lieferdatum": "07.10.2026",
            "positionen": [
                {"artikel_nr": "100002", "bezeichnung": "Sechskantschraube M10x50 DIN 933 8.8 verzinkt", "menge": 850, "einheit": "Stück"},
                {"artikel_nr": "100003", "bezeichnung": "Unterlegscheibe M8 DIN 125 Form A", "menge": 2000, "einheit": "Stück"},
                {"artikel_nr": "100004", "bezeichnung": "Sicherungsmutter M8 DIN 985 verzinkt", "menge": 1000, "einheit": "Stück"},
                {"artikel_nr": "100005", "bezeichnung": "Stahlprofil 40x40x2 mm, L=6m (Schwergut)", "menge": 20, "einheit": "Stück"}
            ]
        }, ensure_ascii=False)
    ),
    (
        "LS-2026-8841",
        "Muster AG",
        "05.10.2026",
        "Carrieri Logistik GmbH",
        "gebucht",
        json.dumps({
            "lieferschein_nr": "LS-2026-8841",
            "lieferant": "Muster AG",
            "empfaenger": "Carrieri Logistik GmbH",
            "lieferdatum": "05.10.2026",
            "positionen": [
                {"artikel_nr": "100001", "bezeichnung": "Sechskantschraube M8x30 DIN 933", "menge": 50, "einheit": "Stück"},
                {"artikel_nr": "100010", "bezeichnung": "Klebeband OPP 50mm x 66m", "menge": 10, "einheit": "Rolle"},
                {"artikel_nr": "100012", "bezeichnung": "Stretchfolie 50cm x 300m", "menge": 2, "einheit": "Rolle"}
            ]
        }, ensure_ascii=False)
    ),
    (
        "LI-2025-007",
        "kalkül — Max Mustermann",
        "01.01.2025",
        "Manfred Mannmuster",
        "gebucht",
        json.dumps({
            "lieferschein_nr": "LI-2025-007",
            "lieferant": "kalkül — Max Mustermann",
            "empfaenger": "Manfred Mannmuster",
            "lieferdatum": "01.01.2025",
            "positionen": [
                {"artikel_nr": "111111", "bezeichnung": "Latzhose blau, Gr. 52", "menge": 1, "einheit": "Stück"},
                {"artikel_nr": "222222", "bezeichnung": "Latzhose grau, Gr. 54", "menge": 3, "einheit": "Stück"},
                {"artikel_nr": "333333", "bezeichnung": "Overall grün, Gr. 53", "menge": 5, "einheit": "Stück"}
            ]
        }, ensure_ascii=False)
    ),
]

def init():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Drop vecchie tabelle per azzerare residui di terze parti
    c.execute("DROP TABLE IF EXISTS artikel")
    c.execute("DROP TABLE IF EXISTS lieferscheine")
    c.execute("DROP TABLE IF EXISTS buchungen")
    c.execute("DROP TABLE IF EXISTS ausgabe_ls")
    c.execute("DROP TABLE IF EXISTS errori_log")

    # ─── Tabella Artikel ───────────────────────────────────
    c.execute("""
        CREATE TABLE artikel (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            artikel_nr  TEXT UNIQUE NOT NULL,
            bezeichnung TEXT NOT NULL,
            kategorie   TEXT,
            einheit     TEXT DEFAULT 'Stück',
            lagerplatz  TEXT,
            bestand     INTEGER DEFAULT 0,
            mindestbestand INTEGER DEFAULT 10,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── Tabella Lieferscheine (eingescannte) ──────────────
    c.execute("""
        CREATE TABLE lieferscheine (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ls_nummer       TEXT UNIQUE NOT NULL,
            lieferant       TEXT,
            lieferdatum     TEXT,
            empfaenger      TEXT DEFAULT 'Carrieri Logistik GmbH',
            status          TEXT DEFAULT 'offen',
            ocr_raw_text    TEXT,
            ai_extracted    TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── Tabella Buchungen ──────────────────────────────────
    c.execute("""
        CREATE TABLE buchungen (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ls_id           INTEGER REFERENCES lieferscheine(id),
            artikel_nr      TEXT,
            bezeichnung     TEXT,
            menge           REAL,
            einheit         TEXT,
            buchungstyp     TEXT DEFAULT 'Wareneingang',
            gebucht_am      TEXT DEFAULT CURRENT_TIMESTAMP,
            notiz           TEXT
        )
    """)

    # ─── Tabella Ausgaben (LS uscita) ──────────────────────
    c.execute("""
        CREATE TABLE ausgabe_ls (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ls_nummer   TEXT UNIQUE NOT NULL,
            empfaenger  TEXT,
            datum       TEXT,
            positionen  TEXT,
            qr_data     TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── Tabella Errori Log ─────────────────────────────────
    c.execute("""
        CREATE TABLE errori_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT DEFAULT CURRENT_TIMESTAMP,
            livello     TEXT NOT NULL,
            modulo      TEXT NOT NULL,
            messaggio   TEXT NOT NULL,
            dettagli    TEXT
        )
    """)

    # ─── Inserimento Articoli Reali ────────────────────────
    for ar in ARTIKEL_DEMO:
        c.execute("""
            INSERT INTO artikel
            (artikel_nr, bezeichnung, kategorie, einheit, lagerplatz, bestand)
            VALUES (?,?,?,?,?,?)
        """, ar)

    # ─── Inserimento i 3 Lieferschein Muster Reali ──────────
    for ls in LIEFERSCHEINE_DEMO:
        c.execute("""
            INSERT INTO lieferscheine
            (ls_nummer, lieferant, lieferdatum, empfaenger, status, ai_extracted)
            VALUES (?,?,?,?,?,?)
        """, ls)
        ls_id = c.lastrowid
        parsed = json.loads(ls[5])
        for p in parsed.get("positionen", []):
            c.execute("""
                INSERT INTO buchungen
                (ls_id, artikel_nr, bezeichnung, menge, einheit, buchungstyp, gebucht_am)
                VALUES (?,?,?,?,?,'Wareneingang',?)
            """, (ls_id, p.get("artikel_nr"), p.get("bezeichnung"), p.get("menge"), p.get("einheit", "Stück"), ls[2] + " 08:30"))

    conn.commit()
    conn.close()
    print(f"[OK] Database inizializzato con successo: {DB_PATH}")
    print(f"   - {len(ARTIKEL_DEMO)} articoli reali caricati (Muster 1, 2, 3)")
    print(f"   - {len(LIEFERSCHEINE_DEMO)} Lieferschein storici reali caricati (kalkül, Muster AG, Würth)")

if __name__ == "__main__":
    init()
