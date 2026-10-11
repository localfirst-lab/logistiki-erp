"""
Zentrale Konfiguration für LogistiKI ERP.
Legge i parametri da 'config.json' esterno, con fallback su variabili d'ambiente.
"""
import os
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
DB_PATH = BASE_DIR / "db" / "erp_demo.db"
LABEL_DIR = BASE_DIR / "output" / "etiketten"
MUSTER_DIR = BASE_DIR / "muster"

# Assicura esistenza cartelle essenziali
LABEL_DIR.mkdir(parents=True, exist_ok=True)
MUSTER_DIR.mkdir(parents=True, exist_ok=True)

# Valori di default
_config_data = {}
if CONFIG_PATH.exists():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_data = json.load(f)
    except Exception as e:
        print(f"[config] Errore lettura config.json: {e}")

_gemini_cfg = _config_data.get("gemini", {})
_server_cfg = _config_data.get("server", {})
_ollama_cfg = _config_data.get("ollama_fallback", {})

# ─── GEMINI API KEYS & MODELLI ──────────────────────────────────────────────
# Modello primario: Gemini 2.5 Flash (il più rapido, economico/gratuito ed evoluto su Google AI Studio)
GEMINI_API_KEY_PRIMARY = (
    _gemini_cfg.get("api_key_primary")
    or os.getenv("GEMINI_API_KEY_PRIMARY")
    or os.getenv("GEMINI_API_KEY", "")
).strip()

GEMINI_API_KEY_BACKUP = (
    _gemini_cfg.get("api_key_backup")
    or os.getenv("GEMINI_API_KEY_BACKUP", "")
).strip()

GEMINI_MODEL = _gemini_cfg.get("model", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL = _gemini_cfg.get("fallback_model", "gemini-2.0-flash")
TEMPERATURE = float(_gemini_cfg.get("temperature", 0.1))
MAX_OUTPUT_TOKENS = int(_gemini_cfg.get("max_output_tokens", 2048))

# ─── SERVER SETTINGS ────────────────────────────────────────────────────────
SERVER_HOST = _server_cfg.get("host", "0.0.0.0")
SERVER_PORT = int(_server_cfg.get("port", 5055))
SERVER_DEBUG = bool(_server_cfg.get("debug", False))

# ─── OLLAMA (FALLBACK TIER 2) ────────────────────────────────────────────────
OLLAMA_ENABLED = bool(_ollama_cfg.get("enabled", False))
OLLAMA_URL = os.getenv("LOGISTIKI_OLLAMA_URL", _ollama_cfg.get("url", "http://localhost:11435"))
OLLAMA_MODEL = os.getenv("LOGISTIKI_MODEL", _ollama_cfg.get("model", "gemma4:e4b"))
LLM_TIMEOUT = int(os.getenv("LOGISTIKI_TIMEOUT", "60"))

# Etikett 100 x 150 mm
LABEL_W_MM = 100
LABEL_H_MM = 150

# Multimodal Vision (PDF gerendert als Bild für Gemini Flash)
USE_VISION = True

