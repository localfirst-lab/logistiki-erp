#!/usr/bin/env python3
"""
=======================================================
  EXTRACTOR.PY — OCR + AI Lieferschein Data Extractor
  LogistiKI — Simbio Ecosystem — Davide Carrieri

  Livello 1: pypdf  (PDF nativo con testo selezionabile)
  Livello 2: Tesseract (PDF scansionato / immagine)
  Livello 3: AI VPS  (Ollama qwen2.5:14b — fallback AI)
=======================================================
"""

import re
import json
import base64
import requests
from pathlib import Path
from io import BytesIO

import os
# ─── Config ────────────────────────────────────────────
MUSTER_PATH  = Path(__file__).parent.parent / "muster" / "lieferschein_muster.json"
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11435")   # Local tunnel o VPS
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")            # modello principale
FALLBACK_MODEL = "Simbio-Lite:latest"

# ─── Carica Muster ─────────────────────────────────────
def load_muster(name: str = "default") -> dict:
    with open(MUSTER_PATH, encoding="utf-8") as f:
        muster = json.load(f)
    return muster.get(name, muster["default"])


# ─── Livello 1: pypdf (PDF nativo) ─────────────────────
def extract_with_pypdf(file_bytes: bytes) -> str:
    try:
        import pypdf
        from io import BytesIO
        reader = pypdf.PdfReader(BytesIO(file_bytes))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return ""
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()
    except Exception as e:
        print(f"[pypdf] Errore: {e}")
        return ""


# ─── Livello 2: Tesseract OCR ──────────────────────────
def extract_with_tesseract(file_bytes: bytes, filename: str = "") -> str:
    try:
        import pytesseract
        from PIL import Image
        import pdf2image

        fname = filename.lower()
        if fname.endswith(".pdf"):
            pages = pdf2image.convert_from_bytes(file_bytes, dpi=300)
            text = ""
            for page in pages:
                text += pytesseract.image_to_string(page, lang="deu+ita+eng") + "\n"
            return text.strip()
        else:
            img = Image.open(BytesIO(file_bytes))
            return pytesseract.image_to_string(img, lang="deu+ita+eng").strip()
    except ImportError:
        print("[Tesseract] pytesseract o pdf2image non installati — skip")
        return ""
    except Exception as e:
        print(f"[Tesseract] Errore: {e}")
        return ""


# ─── Livello 3: AI VPS Ollama ──────────────────────────
def extract_with_ai(raw_text: str, muster_name: str = "default") -> dict:
    """Invia testo grezzo a Ollama e chiede estrazione strutturata JSON."""
    muster = load_muster(muster_name)
    field_hints = "\n".join(
        f"- {k}: {v['ai_hint']}"
        for k, v in muster["fields"].items()
    )

    prompt = f"""Sei un assistente specializzato in logistica industriale tedesca.
Analizza il seguente testo estratto da una Lieferschein (bolla di consegna) e restituisci SOLO un oggetto JSON con i seguenti campi:

{field_hints}

Per il campo "artikel", restituisci una lista di oggetti con: artikel_nr, bezeichnung, menge, einheit.
Se un campo non è trovato, usa null.

TESTO LIEFERSCHEIN:
\"\"\"
{raw_text[:3000]}
\"\"\"

Rispondi SOLO con il JSON, senza spiegazioni. Formato:
{{
  "lieferant": "...",
  "lieferdatum": "...",
  "lieferschein_nr": "...",
  "empfaenger": "...",
  "artikel": [
    {{"artikel_nr": "...", "bezeichnung": "...", "menge": ..., "einheit": "Stück"}}
  ]
}}"""

    try:
        for model in [OLLAMA_MODEL, FALLBACK_MODEL]:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=45
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "")
                # Estrai solo il blocco JSON dalla risposta
                json_match = re.search(r'\{[\s\S]+\}', raw)
                if json_match:
                    return json.loads(json_match.group())
    except requests.exceptions.ConnectionError:
        print("[AI] VPS non raggiungibile — solo regex")
    except json.JSONDecodeError as e:
        print(f"[AI] Errore parsing JSON risposta: {e}")
    except Exception as e:
        print(f"[AI] Errore: {e}")

    return {}


# ─── Estrazione con Regex (Muster) ─────────────────────
def extract_with_regex(text: str, muster_name: str = "default") -> dict:
    muster = load_muster(muster_name)
    result = {}

    for field, config in muster["fields"].items():
        if field == "artikel":
            # Estrazione tabella articoli
            tbl_rx = config.get("regex_table", "")
            if tbl_rx:
                matches = re.findall(tbl_rx, text)
                result["artikel"] = [
                    {
                        "artikel_nr":  m[0].strip(),
                        "bezeichnung": m[1].strip(),
                        "menge":       float(m[2].replace(",", ".")),
                        "einheit":     m[3].strip() if len(m) > 3 else "Stück"
                    }
                    for m in matches
                ]
        else:
            regexes = config.get("regex", [])
            for rx in regexes:
                match = re.search(rx, text, re.IGNORECASE)
                if match:
                    result[field] = match.group(1).strip()
                    break
            if field not in result:
                result[field] = None

    return result


# ─── Entry Point Principale ─────────────────────────────
def extract(file_bytes: bytes, filename: str = "doc.pdf", muster_name: str = "default") -> dict:
    """
    Estrae i dati da una Lieferschein usando i 3 livelli in cascata.
    Restituisce: { raw_text, extracted, method }
    """
    # Livello 1: pypdf
    raw_text = ""
    method = ""

    if filename.lower().endswith(".pdf"):
        raw_text = extract_with_pypdf(file_bytes)
        if raw_text:
            method = "pypdf"
            print(f"[OCR] Testo estratto con pypdf ({len(raw_text)} caratteri)")

    # Livello 2: Tesseract se pypdf vuoto o è un'immagine
    if not raw_text:
        raw_text = extract_with_tesseract(file_bytes, filename)
        if raw_text:
            method = "tesseract"
            print(f"[OCR] Testo estratto con Tesseract ({len(raw_text)} caratteri)")

    if not raw_text:
        return {"raw_text": "", "extracted": {}, "method": "none", "error": "Nessun testo estratto dal documento"}

    # Estrazione con Regex (Muster)
    regex_result = extract_with_regex(raw_text, muster_name)

    # Livello 3: AI per completare i campi mancanti
    missing = [k for k, v in regex_result.items() if v is None or v == []]
    ai_result = {}
    if missing:
        print(f"[OCR] Campi mancanti dopo regex: {missing} → AI VPS")
        ai_result = extract_with_ai(raw_text, muster_name)

    # Merge: regex ha priorità, AI completa i vuoti
    merged = {**ai_result, **{k: v for k, v in regex_result.items() if v is not None and v != []}}

    return {
        "raw_text": raw_text,
        "extracted": merged,
        "method": f"{method}+regex" + ("+ai" if ai_result else ""),
    }
