#!/usr/bin/env python3
"""
=======================================================
  LOGISTIKI_MCP_SERVER.PY — MCP Server per LogistiKI
  Protocollo: Model Context Protocol (MCP) via stdio
  Autore: Davide Carrieri / Simbio Ecosystem

  Avvio standalone:
    python mcp/logistiki_mcp_server.py

  Usato da Antigravity IDE come tool server MCP.
  Espone i tool dell'ERP LogistiKI agli agenti AI.
=======================================================
"""

import json
import sys
import sqlite3
import os
from pathlib import Path

# Aggiungi la root del progetto al path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ocr"))

DB_PATH = ROOT / "db" / "erp_demo.db"

# ── Helpers DB ──────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ══════════════════════════════════════════════════════
#  TOOL DEFINITIONS
# ══════════════════════════════════════════════════════
TOOLS = [
    {
        "name": "logistiki_get_artikel",
        "description": "Ottieni la lista degli articoli presenti nel magazzino ERP. Puoi cercare per nome, codice o categoria.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Testo da cercare in codice articolo o descrizione (opzionale)"
                },
                "kategorie": {
                    "type": "string",
                    "description": "Filtra per categoria (opzionale)"
                }
            }
        }
    },
    {
        "name": "logistiki_get_buchungen",
        "description": "Ottieni la cronologia degli ultimi buchungen (ingressi merce) nell'ERP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Numero massimo di risultati (default 20, max 50)",
                    "default": 20
                }
            }
        }
    },
    {
        "name": "logistiki_scan_text",
        "description": "Analizza testo grezzo di una Lieferschein ed estrae i dati strutturati (fornitore, data, articoli, quantità) usando regex e AI VPS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Testo della Lieferschein da analizzare"
                },
                "muster": {
                    "type": "string",
                    "description": "Template di riconoscimento da usare: 'muster_gmbh_standard', 'default', 'strahle_intern'",
                    "default": "muster_gmbh_standard"
                },
                "use_ai": {
                    "type": "boolean",
                    "description": "Usa AI VPS per completare i campi mancanti (default true)",
                    "default": True
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "logistiki_buchen",
        "description": "Registra un ingresso merce (Buchung) nell'ERP aggiornando il bestand degli articoli.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ls_nummer": {
                    "type": "string",
                    "description": "Numero della Lieferschein"
                },
                "lieferant": {
                    "type": "string",
                    "description": "Nome del fornitore"
                },
                "positionen": {
                    "type": "array",
                    "description": "Lista posizioni articoli da buchare",
                    "items": {
                        "type": "object",
                        "properties": {
                            "artikel_nr":  {"type": "string"},
                            "bezeichnung": {"type": "string"},
                            "menge":       {"type": "number"},
                            "einheit":     {"type": "string", "default": "Stueck"}
                        },
                        "required": ["artikel_nr", "menge"]
                    }
                }
            },
            "required": ["ls_nummer", "positionen"]
        }
    },
    {
        "name": "logistiki_create_lieferschein",
        "description": "Crea una nuova Lieferschein in uscita selezionando articoli dal magazzino.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "empfaenger": {
                    "type": "string",
                    "description": "Nome del destinatario/cliente"
                },
                "datum": {
                    "type": "string",
                    "description": "Data nel formato GG.MM.AAAA (default oggi)"
                },
                "positionen": {
                    "type": "array",
                    "description": "Lista articoli da includere (max 3 in demo)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "artikel_nr":  {"type": "string"},
                            "bezeichnung": {"type": "string"},
                            "menge":       {"type": "number"},
                            "einheit":     {"type": "string"}
                        },
                        "required": ["artikel_nr", "menge"]
                    }
                },
                "notiz": {
                    "type": "string",
                    "description": "Nota o commento opzionale"
                }
            },
            "required": ["empfaenger", "positionen"]
        }
    },
    {
        "name": "logistiki_bestand_check",
        "description": "Controlla il bestand (giacenza) di uno o più articoli nel magazzino.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artikel_nummern": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista di codici articolo da verificare"
                }
            },
            "required": ["artikel_nummern"]
        }
    },
    {
        "name": "logistiki_decision_tree_slotting",
        "description": "Albero decisionale deterministico (WMS Decision Tree) per assegnare l'ubicazione ottimale nello scaffale (Regal-Fach-Platz) con motivazione in tedesco (Regole: Bündelung, Zone Schwer/Sperrig/Gefahrstoff/Standard, rotazione ergonomica e controllo capienza).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artikel_nr": {
                    "type": "string",
                    "description": "Codice articolo (es. '111111' o '100001')"
                },
                "bezeichnung": {
                    "type": "string",
                    "description": "Descrizione dell'articolo in tedesco (es. 'Sechskantschraube M8' o 'Latzhose blau')"
                },
                "menge": {
                    "type": "number",
                    "description": "Quantità da stoccare"
                },
                "einheit": {
                    "type": "string",
                    "description": "Unità di misura (default 'Stück')",
                    "default": "Stück"
                }
            },
            "required": ["artikel_nr", "bezeichnung", "menge"]
        }
    },
    {
        "name": "logistiki_generate_label",
        "description": "Genera l'etichetta fisica di magazzino in PDF formato 100x150 mm con codice a barre e QR Code (formato ARTIKEL|MENGE).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artikel_nr": {"type": "string"},
                "bezeichnung": {"type": "string"},
                "menge": {"type": "number"},
                "einheit": {"type": "string", "default": "Stück"},
                "lagerplatz": {"type": "string", "description": "Ubicazione scaffale assegnata (es. 'A-01-01')"},
                "lieferschein_nr": {"type": "string", "description": "Numero del documento di consegna"}
            },
            "required": ["artikel_nr", "bezeichnung", "menge", "lagerplatz"]
        }
    },
    {
        "name": "logistiki_analyse_lieferschein",
        "description": "Analizza un documento di consegna (PDF o DOCX) tramite Gemma 4 E4B + OCR ed estrae la bozza validata con Pydantic (Human-in-the-Loop ready).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Percorso assoluto o relativo del file da analizzare"
                },
                "sample_name": {
                    "type": "string",
                    "description": "Nome file di esempio nella cartella muster/ (es. 'Lieferschein_muster2.pdf')"
                }
            }
        }
    },
    {
        "name": "logistiki_status",
        "description": "Ritorna lo stato generale dell'ERP LogistiKI: numero articoli, buchungen, lieferscheine elaborate.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# ══════════════════════════════════════════════════════
#  TOOL HANDLERS
# ══════════════════════════════════════════════════════

def tool_get_artikel(args):
    conn = get_db()
    query = args.get("query", "").strip()
    kat   = args.get("kategorie", "").strip()
    sql   = "SELECT * FROM artikel WHERE 1=1"
    params = []
    if query:
        sql += " AND (bezeichnung LIKE ? OR artikel_nr LIKE ?)"
        params += [f"%{query}%", f"%{query}%"]
    if kat:
        sql += " AND kategorie LIKE ?"
        params.append(f"%{kat}%")
    sql += " ORDER BY kategorie, bezeichnung LIMIT 30"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    return {
        "count": len(result),
        "artikel": result
    }


def tool_get_buchungen(args):
    limit = min(int(args.get("limit", 20)), 50)
    conn  = get_db()
    rows  = conn.execute("""
        SELECT b.*, l.lieferant, l.ls_nummer
        FROM buchungen b
        LEFT JOIN lieferscheine l ON b.ls_id = l.id
        ORDER BY b.gebucht_am DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return {"buchungen": [dict(r) for r in rows]}


def tool_scan_text(args):
    from extractor import extract_with_regex, extract_with_ai, load_muster
    text     = args.get("text", "")
    muster   = args.get("muster", "muster_gmbh_standard")
    use_ai   = args.get("use_ai", True)

    regex_result = extract_with_regex(text, muster)
    ai_result    = {}
    missing = [k for k, v in regex_result.items() if v is None or v == []]

    if use_ai and missing:
        ai_result = extract_with_ai(text, muster)

    merged = {**ai_result, **{k: v for k, v in regex_result.items() if v is not None and v != []}}
    return {
        "extracted": merged,
        "missing_fields": missing,
        "method": "regex" + ("+ai" if ai_result else ""),
        "muster_used": muster
    }


def tool_buchen(args):
    from datetime import datetime
    import uuid
    ls_nummer  = args.get("ls_nummer", f"LS-MCP-{uuid.uuid4().hex[:8].upper()}")
    lieferant  = args.get("lieferant", "Unbekannt")
    positionen = args.get("positionen", [])

    conn = get_db()
    ts   = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Crea o trova LS
    existing = conn.execute(
        "SELECT id FROM lieferscheine WHERE ls_nummer=?", (ls_nummer,)
    ).fetchone()
    if not existing:
        conn.execute("""
            INSERT INTO lieferscheine (ls_nummer, lieferant, lieferdatum, status)
            VALUES (?,?,?,'offen')
        """, (ls_nummer, lieferant, ts.split(" ")[0]))
        conn.commit()
    ls_id = conn.execute("SELECT id FROM lieferscheine WHERE ls_nummer=?", (ls_nummer,)).fetchone()["id"]

    booked = []
    for pos in positionen:
        art_nr = pos.get("artikel_nr", "").strip()
        menge  = float(pos.get("menge", 0))
        bez    = pos.get("bezeichnung", "Unbekannt")
        einh   = pos.get("einheit", "Stueck")

        conn.execute("""
            INSERT INTO buchungen (ls_id, artikel_nr, bezeichnung, menge, einheit, buchungstyp, gebucht_am)
            VALUES (?,?,?,?,?,'Wareneingang',?)
        """, (ls_id, art_nr, bez, menge, einh, ts))

        existing_art = conn.execute("SELECT id FROM artikel WHERE artikel_nr=?", (art_nr,)).fetchone()
        if existing_art:
            conn.execute("UPDATE artikel SET bestand = bestand + ? WHERE artikel_nr=?", (int(menge), art_nr))
        else:
            conn.execute("INSERT INTO artikel (artikel_nr, bezeichnung, einheit, bestand) VALUES (?,?,?,?)",
                         (art_nr, bez, einh, int(menge)))
        booked.append({"artikel_nr": art_nr, "menge": menge, "einheit": einh})

    conn.execute("UPDATE lieferscheine SET status='gebucht' WHERE id=?", (ls_id,))
    conn.commit()
    conn.close()
    return {"success": True, "ls_id": ls_id, "ls_nummer": ls_nummer, "gebucht": booked, "zeitstempel": ts}


def tool_create_lieferschein(args):
    import uuid
    from datetime import datetime
    empfaenger = args.get("empfaenger", "")
    datum      = args.get("datum", datetime.now().strftime("%d.%m.%Y"))
    positionen = args.get("positionen", [])
    notiz      = args.get("notiz", "")
    ls_nr      = f"LS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    qr_data    = json.dumps({"ls_nr": ls_nr, "datum": datum, "empfaenger": empfaenger, "positionen": positionen}, ensure_ascii=False)

    conn = get_db()
    conn.execute("INSERT INTO ausgabe_ls (ls_nummer, empfaenger, datum, positionen, qr_data) VALUES (?,?,?,?,?)",
                 (ls_nr, empfaenger, datum, json.dumps(positionen, ensure_ascii=False), qr_data))
    conn.commit()
    conn.close()
    return {"success": True, "ls_nummer": ls_nr, "empfaenger": empfaenger, "datum": datum,
            "positionen_count": len(positionen), "qr_data": qr_data,
            "note": "Usa logistiki_generate_qr con qr_data per creare l'etichetta QR"}


def tool_bestand_check(args):
    nummern = args.get("artikel_nummern", [])
    conn    = get_db()
    result  = []
    for nr in nummern:
        row = conn.execute("SELECT artikel_nr, bezeichnung, bestand, einheit, mindestbestand, lagerplatz FROM artikel WHERE artikel_nr=?", (nr,)).fetchone()
        if row:
            d = dict(row)
            d["status"] = "niedrig" if d["bestand"] <= d["mindestbestand"] else "ok"
            result.append(d)
        else:
            result.append({"artikel_nr": nr, "status": "nicht_gefunden"})
    conn.close()
    return {"bestand": result}


def tool_status(args):
    conn = get_db()
    n_artikel = conn.execute("SELECT COUNT(*) FROM artikel").fetchone()[0]
    n_buch    = conn.execute("SELECT COUNT(*) FROM buchungen").fetchone()[0]
    n_ls      = conn.execute("SELECT COUNT(*) FROM lieferscheine").fetchone()[0]
    n_ausgabe = conn.execute("SELECT COUNT(*) FROM ausgabe_ls").fetchone()[0]
    n_low     = conn.execute("SELECT COUNT(*) FROM artikel WHERE bestand <= mindestbestand").fetchone()[0]
    conn.close()
    return {
        "system": "LogistiKI ERP Demo",
        "version": "1.0.0",
        "db": str(DB_PATH),
        "artikel_total": n_artikel,
        "buchungen_total": n_buch,
        "lieferscheine_verarbeitet": n_ls,
        "ausgabe_ls_erstellt": n_ausgabe,
        "artikel_bestand_niedrig": n_low
    }


def tool_decision_tree_slotting(args):
    from agent.schemas import Artikel
    from agent import lager
    art = Artikel(
        artikel_nr=str(args.get("artikel_nr", "")),
        bezeichnung=str(args.get("bezeichnung", "")),
        menge=float(args.get("menge", 1)),
        einheit=args.get("einheit", "Stück")
    )
    conn = get_db()
    try:
        vorschlaege = lager.vorschlag(art, conn)
        return {
            "success": True,
            "artikel_nr": art.artikel_nr,
            "menge": art.menge,
            "vorschlaege": [v.model_dump() for v in vorschlaege],
            "decision_tree_rules_applied": [
                "1. Bündelung (Gleicher Artikel bereits am Platz)",
                "2. Zonen-Klassifizierung (Standard / Schwer / Sperrig / Gefahrstoff)",
                "3. Ergonomie & Wege-Optimierung (Kurze Distanz zum Wareneingang)",
                "4. Kapazitätsprüfung & Dynamischer Split"
            ]
        }
    finally:
        conn.close()


def tool_generate_label(args):
    from agent import etikett
    art_nr = str(args.get("artikel_nr", ""))
    bez    = str(args.get("bezeichnung", ""))
    menge  = float(args.get("menge", 1))
    einh   = args.get("einheit", "Stück")
    platz  = str(args.get("lagerplatz", "A-01-01"))
    ls_nr  = args.get("lieferschein_nr")
    et     = etikett.erstelle_etikett(art_nr, bez, menge, einh, platz, ls_nr)
    return {
        "success": True,
        "pdf_pfad": et.pdf_pfad,
        "qr_inhalt": et.qr_inhalt,
        "format": "100x150 mm (Zebra / PDF)"
    }


def tool_analyse_lieferschein(args):
    from agent.config import MUSTER_DIR, USE_VISION
    from agent.textextract import lese_text, seiten_als_bilder
    from agent.agent import analysiere
    file_path = args.get("file_path")
    sample_name = args.get("sample_name", "Lieferschein_muster2.pdf")
    p = Path(file_path) if file_path else (MUSTER_DIR / sample_name)
    if not p.exists():
        return {"error": f"Datei nicht gefunden: {p}"}
    raw = p.read_bytes()
    text, methode = lese_text(raw, p.name)
    bilder = seiten_als_bilder(raw, p.name) if USE_VISION else []
    if bilder:
        methode += "+vision"
    entwurf = analysiere(text, bilder)
    return {
        "success": True,
        "datei": p.name,
        "methode": methode,
        "entwurf": entwurf.model_dump()
    }


TOOL_HANDLERS = {
    "logistiki_get_artikel":          tool_get_artikel,
    "logistiki_get_buchungen":        tool_get_buchungen,
    "logistiki_scan_text":            tool_scan_text,
    "logistiki_buchen":               tool_buchen,
    "logistiki_create_lieferschein":  tool_create_lieferschein,
    "logistiki_bestand_check":        tool_bestand_check,
    "logistiki_status":               tool_status,
    "logistiki_decision_tree_slotting": tool_decision_tree_slotting,
    "logistiki_generate_label":       tool_generate_label,
    "logistiki_analyse_lieferschein": tool_analyse_lieferschein,
}

# ══════════════════════════════════════════════════════
#  MCP STDIO LOOP
# ══════════════════════════════════════════════════════

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()

def handle(msg):
    method = msg.get("method", "")
    mid    = msg.get("id")

    if method == "initialize":
        send({"jsonrpc":"2.0","id":mid,"result":{
            "protocolVersion":"2024-11-05",
            "capabilities":{"tools":{}},
            "serverInfo":{"name":"logistiki-mcp","version":"1.0.0"}
        }})

    elif method == "tools/list":
        send({"jsonrpc":"2.0","id":mid,"result":{"tools":TOOLS}})

    elif method == "tools/call":
        params    = msg.get("params", {})
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        handler   = TOOL_HANDLERS.get(tool_name)
        if not handler:
            send({"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":f"Tool '{tool_name}' not found"}})
            return
        try:
            result = handler(tool_args)
            send({"jsonrpc":"2.0","id":mid,"result":{
                "content":[{"type":"text","text":json.dumps(result, ensure_ascii=False, indent=2)}]
            }})
        except Exception as e:
            send({"jsonrpc":"2.0","id":mid,"error":{"code":-32000,"message":str(e)}})

    elif method == "notifications/initialized":
        pass  # ack silenzioso

    else:
        if mid:
            send({"jsonrpc":"2.0","id":mid,"error":{"code":-32601,"message":f"Method not found: {method}"}})


def main():
    import sys
    # Imposta encoding UTF-8 su Windows
    if sys.platform == "win32":
        import io
        sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8")
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            handle(msg)
        except json.JSONDecodeError:
            pass

if __name__ == "__main__":
    main()
