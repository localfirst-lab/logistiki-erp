#!/usr/bin/env python3
"""
=======================================================
  APP.PY — Flask Backend LogistiKI ERP
  Autore: Davide Carrieri / Simbio Ecosystem
  Avvio: python app.py
  URL:   http://localhost:5050
=======================================================
"""

import json
import sqlite3
import uuid
import os
import io
import re
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS

# ─── Setup ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent
DB_PATH   = BASE_DIR / "db" / "erp_demo.db"
MUSTER_PATH = BASE_DIR / "muster" / "lieferschein_muster.json"

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)


# ─── DB Helper ─────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_if_needed():
    if not DB_PATH.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        import subprocess, sys
        subprocess.run([sys.executable, str(BASE_DIR / "db" / "init_db.py")])


# ─── Frontend ───────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ─── API: Artikel ──────────────────────────────────────
@app.route("/api/artikel", methods=["GET"])
def get_artikel():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM artikel ORDER BY kategorie, bezeichnung"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/artikel/<artikel_nr>", methods=["GET"])
def get_artikel_one(artikel_nr):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM artikel WHERE artikel_nr = ?", (artikel_nr,)
    ).fetchone()
    conn.close()
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "Artikel nicht gefunden"}), 404


@app.route("/api/artikel/<artikel_nr>/bestand", methods=["PATCH"])
def update_bestand(artikel_nr):
    data = request.get_json()
    delta = data.get("delta", 0)
    conn = get_db()
    conn.execute(
        "UPDATE artikel SET bestand = bestand + ? WHERE artikel_nr = ?",
        (delta, artikel_nr)
    )
    conn.commit()
    row = conn.execute("SELECT bestand FROM artikel WHERE artikel_nr = ?", (artikel_nr,)).fetchone()
    conn.close()
    return jsonify({"artikel_nr": artikel_nr, "bestand": row["bestand"] if row else 0})


# ─── API: Buchungen ────────────────────────────────────
@app.route("/api/buchungen", methods=["GET"])
def get_buchungen():
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, l.lieferant, l.ls_nummer
        FROM buchungen b
        LEFT JOIN lieferscheine l ON b.ls_id = l.id
        ORDER BY b.gebucht_am DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/buchen", methods=["POST"])
def buchen():
    """Registra l'ingresso merce e aggiorna il bestand."""
    data = request.get_json()
    ls_id = data.get("ls_id")
    positionen = data.get("positionen", [])

    if not positionen:
        return jsonify({"error": "Nessuna posizione fornita"}), 400

    conn = get_db()
    booked = []
    ts = datetime.now().strftime("%d.%m.%Y %H:%M")

    for pos in positionen:
        art_nr = pos.get("artikel_nr", "").strip()
        menge  = float(pos.get("menge", 0))
        bez    = pos.get("bezeichnung", "Unbekannt")
        einh   = pos.get("einheit", "Stück")

        # Inserisci buchung
        conn.execute("""
            INSERT INTO buchungen
            (ls_id, artikel_nr, bezeichnung, menge, einheit, buchungstyp, gebucht_am)
            VALUES (?,?,?,?,?,'Wareneingang',?)
        """, (ls_id, art_nr, bez, menge, einh, ts))

        # Aggiorna bestand se l'articolo esiste
        existing = conn.execute(
            "SELECT id FROM artikel WHERE artikel_nr = ?", (art_nr,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE artikel SET bestand = bestand + ? WHERE artikel_nr = ?",
                (int(menge), art_nr)
            )
        else:
            # Crea articolo al volo
            conn.execute("""
                INSERT INTO artikel (artikel_nr, bezeichnung, einheit, bestand)
                VALUES (?,?,?,?)
            """, (art_nr, bez, einh, int(menge)))

        booked.append({"artikel_nr": art_nr, "menge": menge})

    # Aggiorna status LS
    if ls_id:
        conn.execute(
            "UPDATE lieferscheine SET status='gebucht' WHERE id=?", (ls_id,)
        )

    conn.commit()
    conn.close()
    return jsonify({"success": True, "gebucht": booked, "zeitstempel": ts})


# ─── API: Scan Lieferschein ────────────────────────────
@app.route("/api/scan", methods=["POST"])
def scan():
    """Riceve un file, estrae dati con OCR+AI, salva LS nel DB."""
    if "file" not in request.files:
        return jsonify({"error": "Nessun file caricato"}), 400

    f = request.files["file"]
    muster_name = request.form.get("muster", "default")
    file_bytes = f.read()
    filename   = f.filename

    # Importa extractor
    import sys
    sys.path.insert(0, str(BASE_DIR / "ocr"))
    from extractor import extract

    result = extract(file_bytes, filename, muster_name)

    if result.get("error"):
        return jsonify({"error": result["error"]}), 422

    extracted = result.get("extracted", {})

    # Genera numero LS se non trovato
    ls_nr = extracted.get("lieferschein_nr") or f"LS-AUTO-{uuid.uuid4().hex[:8].upper()}"
    lieferant    = extracted.get("lieferant") or "Unbekannt"
    lieferdatum  = extracted.get("lieferdatum") or datetime.now().strftime("%d.%m.%Y")

    # Salva in DB
    conn = get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO lieferscheine
            (ls_nummer, lieferant, lieferdatum, status, ocr_raw_text, ai_extracted)
            VALUES (?,?,?,'offen',?,?)
        """, (ls_nr, lieferant, lieferdatum,
              result.get("raw_text", "")[:5000],
              json.dumps(extracted, ensure_ascii=False)))
        conn.commit()
        ls_id = conn.execute(
            "SELECT id FROM lieferscheine WHERE ls_nummer=?", (ls_nr,)
        ).fetchone()["id"]
    finally:
        conn.close()

    return jsonify({
        "success": True,
        "ls_id": ls_id,
        "ls_nummer": ls_nr,
        "extracted": extracted,
        "method": result.get("method"),
        "raw_preview": result.get("raw_text", "")[:500]
    })


# ─── API: Lieferscheine (lista) ────────────────────────
@app.route("/api/lieferscheine", methods=["GET"])
def get_lieferscheine():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, ls_nummer, lieferant, lieferdatum, empfaenger, status, created_at FROM lieferscheine ORDER BY created_at DESC LIMIT 30"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


def get_lan_ip():
    """Restituisce l'IP locale LAN della macchina."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_public_base_url():
    """
    Restituisce l'URL pubblico HTTPS (Cloudflare Tunnel) per la scansione immediata da smartphone
    senza problemi di firewall Windows o reti Wi-Fi/4G/5G separate.
    """
    tunnel_file = BASE_DIR / "tunnel_url.txt"
    if tunnel_file.exists():
        try:
            url = tunnel_file.read_text(encoding="utf-8").strip()
            if url.startswith("http"):
                return url
        except Exception:
            pass

    for p in [BASE_DIR / "tunnel.log", BASE_DIR / "cloudflared.log"]:
        if p.exists():
            try:
                import re
                text = p.read_text(encoding="utf-8", errors="ignore")
                m = re.findall(r"https://[a-zA-Z0-9\.\-_]+\.trycloudflare\.com", text)
                if m:
                    return m[-1]
            except Exception:
                pass

    lan_ip = get_lan_ip()
    return f"http://{lan_ip}:5055"


# ─── API: Crea Lieferschein (Output) ──────────────────
@app.route("/api/create_ls", methods=["POST"])
def create_ls():
    """Genera un nuovo numero LS e lo salva con URL accessibile direttamente da smartphone."""
    data = request.get_json() or {}
    empfaenger = data.get("empfaenger", "") or "Musterbau Deutschland GmbH"
    positionen = data.get("positionen", [])
    datum = data.get("datum", datetime.now().strftime("%d.%m.%Y"))
    notiz = data.get("notiz", "")

    ls_nr = data.get("ls_nummer") or f"LS-OUT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
    base_url = get_public_base_url()
    ls_url = f"{base_url}/ls/{ls_nr}"

    conn = get_db()
    conn.execute("""
        INSERT INTO ausgabe_ls (ls_nummer, empfaenger, datum, positionen, qr_data)
        VALUES (?,?,?,?,?)
    """, (ls_nr, empfaenger, datum, json.dumps(positionen, ensure_ascii=False), ls_url))
    conn.commit()
    ls_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    return jsonify({
        "success": True,
        "ls_nummer": ls_nr,
        "ls_id": ls_id,
        "ls_url": ls_url,
        "qr_data": ls_url
    })


# ─── Vista Web Mobile Paperless e-Lieferschein ──────────
@app.route("/ls/<path:ls_nr>")
def view_digital_lieferschein(ls_nr):
    """Visualizza il Lieferschein digitale scansionato dal QR Code dello smartphone."""
    conn = get_db()
    # 1. Cerca in ausgabe_ls
    row = conn.execute("SELECT * FROM ausgabe_ls WHERE ls_nummer=?", (ls_nr,)).fetchone()
    if row:
        pos = []
        try:
            pos = json.loads(row["positionen"]) if row["positionen"] else []
        except Exception:
            pass
        ls_data = {
            "ls_nummer": row["ls_nummer"],
            "empfaenger": row["empfaenger"],
            "datum": row["datum"],
            "positionen": pos,
            "status": "In Auslieferung / Bereit"
        }
        conn.close()
        return render_template("lieferschein_view.html", ls=ls_data)

    # 2. Cerca in lieferscheine (inbound)
    row_in = conn.execute("SELECT * FROM lieferscheine WHERE ls_nummer=?", (ls_nr,)).fetchone()
    if row_in:
        pos = []
        try:
            ai = json.loads(row_in["ai_extracted"]) if row_in["ai_extracted"] else {}
            pos = ai.get("positionen", [])
        except Exception:
            pass
        ls_data = {
            "ls_nummer": row_in["ls_nummer"],
            "empfaenger": row_in["empfaenger"] or "Carrieri Logistik GmbH",
            "datum": row_in["lieferdatum"],
            "positionen": pos,
            "status": row_in["status"]
        }
        conn.close()
        return render_template("lieferschein_view.html", ls=ls_data)

    conn.close()
    
    # 3. Fallback per preview immediata di codici non ancora a DB
    demo_pos = [
        {"artikel_nr": "100001", "bezeichnung": "Sechskantschraube M8x30 DIN 933", "menge": 50, "einheit": "Stück"},
        {"artikel_nr": "100010", "bezeichnung": "Klebeband OPP 50mm x 66m", "menge": 10, "einheit": "Rolle"},
        {"artikel_nr": "100012", "bezeichnung": "Stretchfolie 50cm x 300m", "menge": 2, "einheit": "Rolle"}
    ]
    ls_data = {
        "ls_nummer": ls_nr,
        "empfaenger": "Musterbau Deutschland GmbH (München)",
        "datum": datetime.now().strftime("%d.%m.%Y"),
        "positionen": demo_pos,
        "status": "In Zustellung / Bereit"
    }
    return render_template("lieferschein_view.html", ls=ls_data)


@app.route("/api/ls/<path:ls_nr>/sign", methods=["POST"])
def sign_digital_lieferschein(ls_nr):
    """Registra la firma digitale ricevuta da smartphone."""
    data = request.get_json() or {}
    status = data.get("status", "Quittiert & Geliefert")
    conn = get_db()
    conn.execute("UPDATE ausgabe_ls SET qr_data = ? WHERE ls_nummer = ?", (status, ls_nr))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "ls_nummer": ls_nr, "status": status})


# ─── API: Genera QR Code ───────────────────────────────
@app.route("/api/qr", methods=["POST", "GET"])
def generate_qr():
    """Genera immagine QR Code PNG con URL diretto al Lieferschein."""
    try:
        import qrcode
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return jsonify({"error": "qrcode o Pillow non installati"}), 500

    if request.method == "POST":
        data = request.get_json() or {}
    else:
        data = request.args.to_dict()

    ls_nr = data.get("ls_nummer", "LS-OUT-2026-0042")
    empfaenger = data.get("empfaenger", "Musterbau Deutschland GmbH")
    datum = data.get("datum", datetime.now().strftime("%d.%m.%Y"))
    
    # Riscrivi l'URL con l'indirizzo pubblico HTTPS Cloudflare (o LAN IP se offline)
    # per consentire l'apertura istantanea da qualsiasi smartphone e fotocamera
    base_url = get_public_base_url()
    qr_text = data.get("qr_data", "")
    if qr_text:
        qr_text = qr_text.replace("http://localhost:5055", base_url) \
                         .replace("https://localhost:5055", base_url) \
                         .replace("http://127.0.0.1:5055", base_url) \
                         .replace("https://127.0.0.1:5055", base_url) \
                         .replace("http://192.168.2.30:5055", base_url)
    if not qr_text or not qr_text.startswith("http"):
        qr_text = f"{base_url}/ls/{ls_nr}"

    # Genera QR
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1a2e4a", back_color="white").convert("RGB")

    # Crea etichetta con bordo e testo
    label_w, label_h = 400, 520
    label = Image.new("RGB", (label_w, label_h), color="#f0f4f8")
    draw = ImageDraw.Draw(label)

    # Bordo
    draw.rectangle([4, 4, label_w-5, label_h-5], outline="#1a2e4a", width=3)

    # Header etichetta
    draw.rectangle([4, 4, label_w-5, 60], fill="#1a2e4a")

    # QR centrato
    qr_size = 280
    qr_img_resized = qr_img.resize((qr_size, qr_size))
    qr_x = (label_w - qr_size) // 2
    label.paste(qr_img_resized, (qr_x, 75))

    # Testi
    try:
        font_big   = ImageFont.truetype("arial.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 11)
        font_title = ImageFont.truetype("arialbd.ttf", 16)
    except Exception:
        font_big = font_small = font_title = ImageFont.load_default()

    draw.text((label_w//2, 32), "LogistiKI — LIEFERSCHEIN", fill="white", font=font_title, anchor="mm")
    draw.text((label_w//2, 370), ls_nr, fill="#1a2e4a", font=font_big, anchor="mm")
    draw.text((label_w//2, 395), f"Datum: {datum}", fill="#333", font=font_small, anchor="mm")
    if empfaenger:
        draw.text((label_w//2, 415), f"An: {empfaenger[:40]}", fill="#555", font=font_small, anchor="mm")
    draw.text((label_w//2, 450), "Scan per dettagli / Zum Scannen", fill="#888", font=font_small, anchor="mm")
    draw.text((label_w//2, 500), "LogistiKI © Davide Carrieri", fill="#aaa", font=font_small, anchor="mm")

    # Invia come PNG
    buf = io.BytesIO()
    label.save(buf, format="PNG", dpi=(300, 300))
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     as_attachment=False,
                     download_name=f"{ls_nr}_QR.png")


# ─── API: Muster disponibili ───────────────────────────
@app.route("/api/muster", methods=["GET"])
def get_muster():
    with open(MUSTER_PATH, encoding="utf-8") as f:
        muster = json.load(f)
    return jsonify([
        {"id": k, "description": v.get("description", k)}
        for k, v in muster.items()
    ])


# ─── API v2: Agent-Flow mit menschlicher Bestätigung ────
@app.route("/api/v2/analyse", methods=["POST"])
def v2_analyse():
    """Schritt 1: Datei -> Text -> Agent-Entwurf. Es wird NICHTS gebucht."""
    if "file" not in request.files:
        return jsonify({"error": "Keine Datei hochgeladen"}), 400
    f = request.files["file"]
    from agent.textextract import lese_text, seiten_als_bilder
    from agent.agent import analysiere
    from agent.config import USE_VISION
    raw = f.read()
    text, methode = lese_text(raw, f.filename or "")
    bilder = seiten_als_bilder(raw, f.filename or "") if USE_VISION else []
    if not text and not bilder:
        return jsonify({"error": "Kein Text erkannt (Format oder Scan-Qualität prüfen)"}), 422
    if bilder:
        methode += "+vision"
    entwurf = analysiere(text, bilder)
    return jsonify({"entwurf": entwurf.model_dump(), "methode": methode,
                    "text_vorschau": text[:600], "status": "warte_auf_bestaetigung"})


@app.route("/api/v2/analyse_sample", methods=["POST"])
def v2_analyse_sample():
    """Analisi immediata di uno dei PDF di esempio in muster/ per demo rapida."""
    data = request.get_json(silent=True) or {}
    sample_name = data.get("sample", "Lieferschein_muster2.pdf")
    from agent.config import MUSTER_DIR, USE_VISION
    from agent.textextract import lese_text, seiten_als_bilder
    from agent.agent import analysiere
    
    file_path = MUSTER_DIR / sample_name
    if not file_path.exists():
        # Fallback al primo PDF trovato in muster/
        pdfs = list(MUSTER_DIR.glob("*.pdf"))
        if not pdfs:
            return jsonify({"error": f"Musterdatei {sample_name} nicht gefunden"}), 404
        file_path = pdfs[0]

    raw = file_path.read_bytes()
    text, methode = lese_text(raw, file_path.name)
    bilder = seiten_als_bilder(raw, file_path.name) if USE_VISION else []
    if not text and not bilder:
        return jsonify({"error": "Kein Text erkannt"}), 422
    if bilder:
        methode += "+vision"
    entwurf = analysiere(text, bilder)
    return jsonify({
        "entwurf": entwurf.model_dump(),
        "methode": methode,
        "filename": file_path.name,
        "text_vorschau": text[:600],
        "status": "warte_auf_bestaetigung"
    })


@app.route("/api/v2/bestaetigen", methods=["POST"])
def v2_bestaetigen():
    """Schritt 2: Mensch hat (ggf. korrigiert) bestätigt -> Einlagerung + Etiketten + Meldung."""
    from pydantic import ValidationError
    from agent.schemas import LieferscheinEntwurf
    from agent.agent import verbuchen, abschlussmeldung
    req_json = request.get_json(silent=True) or {}
    try:
        entwurf = LieferscheinEntwurf.model_validate(req_json.get("entwurf", {}))
    except ValidationError as e:
        return jsonify({"error": "Ungültige Daten", "details": e.errors()}), 422
    if not entwurf.positionen:
        return jsonify({"error": "Keine Positionen"}), 400
    vs, et = verbuchen(entwurf)
    meldung = abschlussmeldung(entwurf, vs, et)
    return jsonify(meldung.model_dump())


@app.route("/api/v2/etikett/<path:name>")
def v2_etikett(name):
    from agent.config import LABEL_DIR
    from agent import etikett
    p = (LABEL_DIR / Path(name).name)
    if not p.exists():
        # Genera al volo l'etichetta richiesta per evitare 404
        safe_name = Path(name).stem
        parts = safe_name.split("_")
        art = parts[1] if len(parts) > 1 else "111111"
        loc = parts[2] if len(parts) > 2 else "A-01-01"
        etikett.erstelle_etikett(
            artikel_nr=art,
            bezeichnung="Latzhose blau, Gr. 52 (Demo)",
            menge=1,
            einheit="Stück",
            lagerplatz=loc,
            lieferschein_nr="LI-2025-007"
        )
    return send_file(p, mimetype="application/pdf")


# ─── API: Errori & Config Status ───────────────────────
@app.route("/api/errori", methods=["GET"])
def get_errori():
    """Restituisce la lista degli errori registrati nel DB SQLite."""
    from agent.logger import get_ultimi_errori
    limite = int(request.args.get("limit", 50))
    return jsonify(get_ultimi_errori(limite))


@app.route("/api/config/status", methods=["GET"])
def get_config_status():
    """Stato del sistema AI e delle chiavi (senza esporre i secret)."""
    from agent.config import (
        GEMINI_API_KEY_PRIMARY,
        GEMINI_API_KEY_BACKUP,
        GEMINI_MODEL,
        OLLAMA_ENABLED,
        OLLAMA_MODEL,
        SERVER_PORT,
    )
    return jsonify({
        "gemini": {
            "has_primary_key": bool(GEMINI_API_KEY_PRIMARY),
            "primary_key_hint": f"...{GEMINI_API_KEY_PRIMARY[-4:]}" if len(GEMINI_API_KEY_PRIMARY) >= 4 else "non impostata",
            "has_backup_key": bool(GEMINI_API_KEY_BACKUP),
            "backup_key_hint": f"...{GEMINI_API_KEY_BACKUP[-4:]}" if len(GEMINI_API_KEY_BACKUP) >= 4 else "non impostata",
            "model": GEMINI_MODEL,
        },
        "ollama_fallback": {
            "enabled": OLLAMA_ENABLED,
            "model": OLLAMA_MODEL,
        },
        "server_port": SERVER_PORT,
    })


# ─── Run ───────────────────────────────────────────────
if __name__ == "__main__":
    from agent.config import SERVER_HOST, SERVER_PORT, SERVER_DEBUG
    init_db_if_needed()
    print("=" * 50)
    print("  LogistiKI ERP -- Simbio Ecosystem (Davide Carrieri)")
    print(f"  URL: http://localhost:{SERVER_PORT}")
    print("=" * 50)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)

