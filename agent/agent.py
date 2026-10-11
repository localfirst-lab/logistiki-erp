"""
Pydantic-AI-Agent "LogistiKI" (Deutsch).

Flusso con Human-in-the-Loop & Architettura Multi-Tier:
  Tier 1: Google Gemini Flash (Multimodale, cloud ultrarapido con failover su 2 chiavi API)
  Tier 2: Ollama Locale/VPS (Fallback facoltativo se abilitato)
  Tier 3: Fallback Deterministico Regex (Zero-AI, garantisce continuità)

WMS Decision Tree:
  Calcolo scaffale in 1 ms (deterministico, mai delegato all'LLM).
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any

from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from .config import (
    GEMINI_API_KEY_PRIMARY,
    GEMINI_API_KEY_BACKUP,
    GEMINI_MODEL,
    GEMINI_FALLBACK_MODEL,
    OLLAMA_ENABLED,
    OLLAMA_URL,
    OLLAMA_MODEL,
    LLM_TIMEOUT,
)
from .schemas import (Abschlussmeldung, Etikett, LagerVorschlag, LieferscheinEntwurf)
from . import lager, etikett
from .logger import log_error, log_warning, log_info

SYSTEM_EXTRAKTION = (
    "Du bist LogistiKI, ein Experte für deutsche Logistikdokumente. "
    "Extrahiere aus dem Text und den Bildern eines Lieferscheins die Daten strikt im vorgegebenen Schema. "
    "Erfinde nichts: Was nicht im Text/Bild steht, bleibt leer. Mengen als Zahl. "
    "Trage in 'hinweise' alles ein, was unklar ist, und setze 'konfidenz' ehrlich zwischen 0 und 1. "
    "Antworte ausschließlich auf Deutsch."
)

SYSTEM_MELDUNG = (
    "Du bist LogistiKI, der Lager-Assistent. Fasse die abgeschlossene Einlagerung in 2-4 "
    "kurzen, freundlichen deutschen Sätzen zusammen. Nenne Lagerplätze exakt wie angegeben."
)


def _crea_gemini_agent(output_type: Any, system_prompt: str, api_key: str, model_name: str = GEMINI_MODEL):
    """Crea un agente Pydantic-AI collegato a Gemini Flash."""
    model = GoogleModel(model_name, provider=GoogleProvider(api_key=api_key))
    return Agent(model, output_type=output_type, system_prompt=system_prompt, retries=2)


def _crea_ollama_agent(output_type: Any, system_prompt: str):
    """Crea un agente Pydantic-AI collegato a Ollama (Tier 2)."""
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    model = OpenAIChatModel(OLLAMA_MODEL, provider=OpenAIProvider(base_url=f"{OLLAMA_URL}/v1"))
    return Agent(model, output_type=output_type, system_prompt=system_prompt, retries=1)


# ── 1. Analyse ────────────────────────────────────────────────────────────
def analysiere(text: str, bilder: list[bytes] | None = None) -> LieferscheinEntwurf:
    """
    Analisi Lieferschein:
    1. Prova Gemini Flash con Chiave Primaria
    2. Se errore e disponibile, failover su Chiave Backup
    3. Se falliscono, prova Ollama (se attivo)
    4. Fallback finale su Regex deterministico
    """
    t0 = time.time()
    prompt: list = [f"LIEFERSCHEIN-TEXT (maschinell extrahiert, evtl. unvollständig):\n\"\"\"\n{text[:8000]}\n\"\"\""]
    if bilder:
        prompt = ["Lies den Lieferschein auf den Seitenbildern. Bei Widerspruch gilt das Bild."] + \
                 [BinaryContent(data=b, media_type="image/png") for b in bilder] + prompt

    # ── Tentativo 1: Gemini Flash (Chiave Primaria) ──
    if GEMINI_API_KEY_PRIMARY:
        try:
            agent = _crea_gemini_agent(LieferscheinEntwurf, SYSTEM_EXTRAKTION, GEMINI_API_KEY_PRIMARY, GEMINI_MODEL)
            res = agent.run_sync(prompt)
            durata = round(time.time() - t0, 2)
            log_info("agent", f"Analisi completata con successo con {GEMINI_MODEL} (Key Primaria) in {durata}s")
            return res.output
        except Exception as e1:
            log_warning("agent", f"Gemini Key Primaria fallita: {e1}. Tentativo di failover...")

            # ── Tentativo 2: Gemini Flash (Chiave Backup) ──
            if GEMINI_API_KEY_BACKUP:
                try:
                    agent = _crea_gemini_agent(LieferscheinEntwurf, SYSTEM_EXTRAKTION, GEMINI_API_KEY_BACKUP, GEMINI_MODEL)
                    res = agent.run_sync(prompt)
                    durata = round(time.time() - t0, 2)
                    log_info("agent", f"Analisi completata con {GEMINI_MODEL} (Key Backup) in {durata}s")
                    return res.output
                except Exception as e2:
                    log_error("agent", "Anche la Gemini Key Backup è fallita", exc=e2)
            else:
                log_error("agent", "Gemini Key Primaria fallita e nessuna Key Backup disponibile", exc=e1)
    else:
        log_warning("agent", "Nessuna GEMINI_API_KEY trovata in config.json o env. Si passa ai fallback.")

    # ── Tentativo 3: Ollama Locale/VPS (Tier 2) ──
    if OLLAMA_ENABLED:
        try:
            log_info("agent", f"Avvio fallback locale Ollama ({OLLAMA_MODEL})...")
            agent_ollama = _crea_ollama_agent(LieferscheinEntwurf, SYSTEM_EXTRAKTION)
            res = agent_ollama.run_sync(prompt)
            durata = round(time.time() - t0, 2)
            log_info("agent", f"Analisi completata con Ollama ({OLLAMA_MODEL}) in {durata}s")
            return res.output
        except Exception as e_ollama:
            log_error("agent", f"Fallback Ollama non riuscito: {e_ollama}", exc=e_ollama)

    # ── Tentativo 4: Regex Fallback Deterministico (Tier 3) ──
    durata = round(time.time() - t0, 2)
    log_warning("agent", f"Attivazione Regex Fallback di sicurezza (durata {durata}s)")
    entwurf = _regex_fallback(text)
    entwurf.hinweise.append("Modelli IA non disponibili: utilizzato parser Regex deterministico di riserva.")
    return entwurf


def _regex_fallback(text: str) -> LieferscheinEntwurf:
    def g(rx):
        m = re.search(rx, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    return LieferscheinEntwurf(
        lieferschein_nr=g(r"Lieferschein(?:-?nr\.?|nummer)?[:\s]*([A-Z0-9\-/]{4,})"),
        lieferdatum=g(r"(\d{2}\.\d{2}\.\d{4})"),
        konfidenz=0.2,
    )


# ── 3. Verbuchen (nur nach Bestätigung!) ──────────────────────────────────
def verbuchen(entwurf: LieferscheinEntwurf) -> tuple[list[LagerVorschlag], list[Etikett]]:
    import json
    from datetime import datetime
    conn = lager.get_db()
    lager.init_lager(conn)
    vorschlaege: list[LagerVorschlag] = []
    etiketten: list[Etikett] = []
    try:
        # Lieferschein in DB persistieren
        ls_nr = entwurf.lieferschein_nr or f"LS-{datetime.now().strftime('%Y%m%d-%H%M')}"
        empf = entwurf.empfaenger or "Carrieri Logistik GmbH"
        conn.execute("""
            INSERT OR REPLACE INTO lieferscheine
            (ls_nummer, lieferant, lieferdatum, empfaenger, status, ai_extracted)
            VALUES (?,?,?,?,'gebucht',?)
        """, (
            ls_nr,
            entwurf.lieferant or "Unbekannt",
            entwurf.lieferdatum or datetime.now().strftime("%d.%m.%Y"),
            empf,
            json.dumps(entwurf.model_dump(), ensure_ascii=False)
        ))

        cur = conn.execute("SELECT id FROM lieferscheine WHERE ls_nummer = ?", (ls_nr,))
        row = cur.fetchone()
        ls_id = row[0] if row else None

        for pos in entwurf.positionen:
            for v in lager.vorschlag(pos, conn):
                lager.einlagern(v, conn)
                vorschlaege.append(v)
                if v.lagerplatz != "KLAERUNG":
                    etiketten.append(etikett.erstelle_etikett(
                        pos.artikel_nr, pos.bezeichnung, v.menge, pos.einheit,
                        v.lagerplatz, ls_nr))

                    # Artikelbestand im Artikelstamm aktualisieren oder anlegen
                    art_row = conn.execute("SELECT id FROM artikel WHERE artikel_nr = ?", (pos.artikel_nr,)).fetchone()
                    if art_row:
                        conn.execute(
                            "UPDATE artikel SET bestand = bestand + ?, lagerplatz = ? WHERE artikel_nr = ?",
                            (int(v.menge), v.lagerplatz, pos.artikel_nr))
                    else:
                        conn.execute("""
                            INSERT INTO artikel (artikel_nr, bezeichnung, kategorie, einheit, lagerplatz, bestand)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (pos.artikel_nr, pos.bezeichnung, "Wareneingang", pos.einheit or "Stück", v.lagerplatz, int(v.menge)))

                    if ls_id:
                        conn.execute("""
                            INSERT INTO buchungen (ls_id, artikel_nr, bezeichnung, menge, einheit, buchungstyp, notiz)
                            VALUES (?, ?, ?, ?, ?, 'Wareneingang', ?)
                        """, (ls_id, pos.artikel_nr, pos.bezeichnung, v.menge, pos.einheit or "Stück", f"Regalplatz: {v.lagerplatz}"))
        conn.commit()
    finally:
        conn.close()
    return vorschlaege, etiketten


# ── 4. Abschlussmeldung ───────────────────────────────────────────────────
def abschlussmeldung(entwurf: LieferscheinEntwurf, vs: list[LagerVorschlag],
                     et: list[Etikett]) -> Abschlussmeldung:
    zeilen = "\n".join(f"- {v.menge:g}× {v.artikel_nr} → {v.lagerplatz} ({v.begruendung})" for v in vs)
    fallback = (
        f"Lieferschein {entwurf.lieferschein_nr or '(ohne Nr.)'} von {entwurf.lieferant or 'unbekannt'} "
        f"wurde gebucht. {len(vs)} Einlagerung(en), {len(et)} Etikett(en) erstellt:\n{zeilen}"
    )

    prompt_msg = f"Lieferschein {entwurf.lieferschein_nr} von {entwurf.lieferant}.\n{zeilen}"

    # Prova Gemini Flash (Key 1 poi Key 2)
    for key in [k for k in [GEMINI_API_KEY_PRIMARY, GEMINI_API_KEY_BACKUP] if k]:
        try:
            agent = _crea_gemini_agent(str, SYSTEM_MELDUNG, key, GEMINI_MODEL)
            res = agent.run_sync(prompt_msg)
            text = res.output.strip() or fallback
            return Abschlussmeldung(text=text, gebucht=vs, etiketten=et)
        except Exception as e:
            log_warning("agent", f"Abschlussmeldung con Gemini fallita ({e}), continuo...")

    # Fallback statico
    return Abschlussmeldung(text=fallback, gebucht=vs, etiketten=et)
