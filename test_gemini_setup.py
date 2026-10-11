#!/usr/bin/env python3
"""
Test di verifica configurazione Gemini Flash per LogistiKI ERP.
Esegui: python test_gemini_setup.py
"""
import sys
import time
from pathlib import Path

# Assicura encoding UTF-8 su Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Carica config locale
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from agent.config import (
    CONFIG_PATH,
    GEMINI_API_KEY_PRIMARY,
    GEMINI_API_KEY_BACKUP,
    GEMINI_MODEL,
    SERVER_PORT,
)
from agent.logger import log_info, log_error, get_ultimi_errori

def print_separator(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)

def test_key(nome: str, key: str, model_name: str):
    if not key:
        print(f"[-] {nome}: NON IMPOSTATA in config.json")
        return False

    masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
    print(f"[*] Test {nome} ({masked}) su modello '{model_name}'...")
    
    try:
        from google import genai
        client = genai.Client(api_key=key)
        
        t0 = time.time()
        response = client.models.generate_content(
            model=model_name,
            contents="Rispondi solo con: PING_OK",
        )
        elapsed = round(time.time() - t0, 2)
        
        print(f"[OK] {nome} ATTIVA E FUNZIONANTE!")
        print(f"     Tempo di risposta: {elapsed} secondi")
        print(f"     Risposta modello: {response.text.strip()}")
        log_info("test_setup", f"{nome} verificata con successo in {elapsed}s")
        return True
    except Exception as e:
        print(f"[ERR] Errore con {nome}: {e}")
        log_error("test_setup", f"Errore test {nome}", exc=e)
        return False

def main():
    print_separator("TEST CONFIGURAZIONE LOGISTIKI ERP - GEMINI FLASH")
    
    print(f"[PATH] Percorso config: {CONFIG_PATH}")
    print(f"[PORT] Porta configurata: {SERVER_PORT}")
    print(f"[MODL] Modello predefinito: {GEMINI_MODEL}")
    
    print_separator("1. VERIFICA CHIAVI API GEMINI")
    k1_ok = test_key("Chiave Primaria", GEMINI_API_KEY_PRIMARY, GEMINI_MODEL)
    k2_ok = test_key("Chiave Backup", GEMINI_API_KEY_BACKUP, GEMINI_MODEL)
    
    print_separator("2. VERIFICA SISTEMA DI LOGGING & SQLITE")
    errori = get_ultimi_errori(5)
    print(f"[DB]   Record nel DB SQLite (tabella errori_log): {len(errori)} trovati")
    log_file = BASE_DIR / "errori.log"
    print(f"[FILE] File locale errori.log: {'Presente (' + str(log_file.stat().st_size) + ' bytes)' if log_file.exists() else 'Non ancora creato'}")
    
    print_separator("ESITO COMPLESSIVO")
    if k1_ok:
        print("[OK] Il sistema e' PRONTO per i test con Gemini Flash!")
        print(f"     Puoi avviare il server con: python app.py")
        print(f"     E aprire il browser su: http://localhost:{SERVER_PORT}")
    else:
        print("[INFO] Inserisci la tua API key in 'config.json' (campo 'api_key_primary')")
        print("       e riesegui: python test_gemini_setup.py")

if __name__ == "__main__":
    main()
