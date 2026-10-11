"""
Modulo di logging centralizzato per LogistiKI ERP.
Scrive simultaneamente su:
1. File locale 'errori.log'
2. Tabella SQLite 'errori_log' nel database erp_demo.db
"""

import os
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE_PATH = BASE_DIR / "errori.log"
DB_PATH = BASE_DIR / "db" / "erp_demo.db"


def init_log_table(conn: sqlite3.Connection):
    """Crea la tabella per gli errori se non esiste ancora."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS errori_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT DEFAULT CURRENT_TIMESTAMP,
            livello     TEXT NOT NULL,
            modulo      TEXT NOT NULL,
            messaggio   TEXT NOT NULL,
            dettagli    TEXT
        )
    """)
    conn.commit()


def _scrivi_su_file(livello: str, modulo: str, messaggio: str, dettagli: str = ""):
    """Accoda il messaggio formattato al file errori.log."""
    ora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ora}] [{livello.upper():<7}] [{modulo}] {messaggio}"
    if dettagli:
        linea += f" | Dettagli: {dettagli}"
    linea += "\n"

    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(linea)
    except Exception as e:
        print(f"[logger] Errore scrittura su file errori.log: {e}")


def _scrivi_su_db(livello: str, modulo: str, messaggio: str, dettagli: str = ""):
    """Salva il record dell'errore nel database SQLite."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            init_log_table(conn)
            ora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                INSERT INTO errori_log (timestamp, livello, modulo, messaggio, dettagli)
                VALUES (?, ?, ?, ?, ?)
            """, (ora, livello.upper(), modulo, messaggio, dettagli))
    except Exception as e:
        print(f"[logger] Errore scrittura su database SQLite: {e}")


def log_error(modulo: str, messaggio: str, dettagli: str = None, exc: Exception = None):
    """Registra un ERRORE sia nel file che nel database."""
    dettagli_str = dettagli or ""
    if exc:
        trace = traceback.format_exc()
        if trace and trace != "NoneType: None\n":
            dettagli_str = f"{dettagli_str} - Exception: {exc} | Stack: {trace.strip()}"
        else:
            dettagli_str = f"{dettagli_str} - Exception: {exc}"

    print(f"[ERROR] [{modulo}] {messaggio}")
    _scrivi_su_file("ERROR", modulo, messaggio, dettagli_str)
    _scrivi_su_db("ERROR", modulo, messaggio, dettagli_str)


def log_warning(modulo: str, messaggio: str, dettagli: str = None):
    """Registra un WARNING sia nel file che nel database."""
    print(f"[WARN]  [{modulo}] {messaggio}")
    _scrivi_su_file("WARNING", modulo, messaggio, dettagli or "")
    _scrivi_su_db("WARNING", modulo, messaggio, dettagli or "")


def log_info(modulo: str, messaggio: str, dettagli: str = None):
    """Registra una INFO sia nel file che nel database."""
    print(f"[INFO]  [{modulo}] {messaggio}")
    _scrivi_su_file("INFO", modulo, messaggio, dettagli or "")
    _scrivi_su_db("INFO", modulo, messaggio, dettagli or "")


def get_ultimi_errori(limite: int = 50) -> list[dict]:
    """Recupera gli ultimi errori salvati nel DB SQLite."""
    if not DB_PATH.exists():
        return []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            init_log_table(conn)
            rows = conn.execute(
                "SELECT * FROM errori_log ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        print(f"[logger] Impossibile recuperare errori dal DB: {e}")
        return []
