"""
Etikett 100 x 150 mm als PDF (reportlab).
Enthält:
- Lagerplatz (groß und lesbar für Staplerfahrer)
- Artikel-Nr. & Bezeichnung
- Menge & Einheit
- Wareneingangsdatum & FIFO-Kriterium (First-In, First-Out)
- QR-Code (ARTIKEL|MENGE)
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

from .config import LABEL_DIR, LABEL_W_MM, LABEL_H_MM
from .schemas import Etikett

NAVY = HexColor("#0f2238")
ACCENT = HexColor("#1f6feb")
EMERALD = HexColor("#059669")
BORDER_GRAY = HexColor("#cbd5e1")


def qr_inhalt(artikel_nr: str, menge: float) -> str:
    m = int(menge) if float(menge).is_integer() else menge
    return f"{artikel_nr}|{m}"


def erstelle_etikett(artikel_nr: str, bezeichnung: str, menge: float, einheit: str,
                     lagerplatz: str, lieferschein_nr: str | None = None,
                     datum: str | None = None) -> Etikett:
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    we_datum = datum or datetime.now().strftime("%d.%m.%Y")
    safe = lagerplatz.replace("/", "-")
    pfad = Path(LABEL_DIR) / f"ETIKETT_{artikel_nr}_{safe}.pdf"
    W, H = LABEL_W_MM * mm, LABEL_H_MM * mm
    c = canvas.Canvas(str(pfad), pagesize=(W, H))

    # ── 1. Kopfzeile (harmonischer Abstand) ───────────────────
    c.setFillColor(NAVY)
    c.rect(0, H - 18 * mm, W, 18 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(7 * mm, H - 12 * mm, "WARENEINGANG")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(W - 7 * mm, H - 12 * mm, "LogistiKI · Carrieri WMS")

    # ── 2. FIFO- & Datums-Leiste ──────────────────────────────
    c.setFillColor(HexColor("#f1f5f9"))
    c.rect(0, H - 28 * mm, W, 10 * mm, stroke=0, fill=1)
    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(0.5)
    c.line(0, H - 28 * mm, W, H - 28 * mm)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(7 * mm, H - 24.5 * mm, f"WE-DATUM: {we_datum}")
    
    # FIFO Badge rechts
    c.setFillColor(EMERALD)
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(W - 7 * mm, H - 24.5 * mm, "FIFO: Älteste Charge zuerst")

    # ── 3. Lagerplatz (groß und eindeutig) ─────────────────────
    c.setFillColor(HexColor("#64748b"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(7 * mm, H - 35 * mm, "ZIEL-LAGERPLATZ")
    
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 40)
    c.drawString(7 * mm, H - 49 * mm, lagerplatz)

    # Trennlinie
    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(0.5)
    c.line(7 * mm, H - 53 * mm, W - 7 * mm, H - 53 * mm)

    # ── 4. Artikeldaten ───────────────────────────────────────
    c.setFillColor(HexColor("#64748b"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(7 * mm, H - 59 * mm, "ARTIKELNUMMER")
    
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(7 * mm, H - 66 * mm, artikel_nr)

    c.setFont("Helvetica", 9.5)
    # Zeilenumbruch für Artikelbezeichnung
    words = bezeichnung.split()
    line = ""
    y = H - 73 * mm
    for w in words:
        if c.stringWidth(line + " " + w, "Helvetica", 9.5) > W - 14 * mm:
            c.drawString(7 * mm, y, line.strip())
            y -= 4.5 * mm
            line = w
        else:
            line += " " + w
    c.drawString(7 * mm, y, line.strip())

    # ── 5. Menge ──────────────────────────────────────────────
    c.setFillColor(HexColor("#64748b"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(7 * mm, 66 * mm, "MENGE & EINHEIT")
    
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 26)
    m = int(menge) if float(menge).is_integer() else menge
    c.drawString(7 * mm, 56 * mm, f"{m} {einheit}")

    # ── 6. QR-Code (50x50 mm) ─────────────────────────────────
    inhalt = qr_inhalt(artikel_nr, menge)
    qr = QrCodeWidget(inhalt)
    x0, y0, x1, y1 = qr.getBounds()
    size = 46 * mm
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(qr)
    renderPDF.draw(d, c, (W - size) / 2, 7 * mm)

    # Fußzeile
    c.setFillColor(HexColor("#64748b"))
    c.setFont("Helvetica", 6.5)
    ls_info = f"LS: {lieferschein_nr or '-'} · FIFO: {we_datum} · QR: {inhalt}"
    c.drawCentredString(W / 2, 3 * mm, ls_info)

    c.showPage()
    c.save()

    return Etikett(artikel_nr=artikel_nr, bezeichnung=bezeichnung, menge=menge,
                   einheit=einheit, lagerplatz=lagerplatz, lieferschein_nr=lieferschein_nr,
                   pdf_pfad=str(pfad), qr_inhalt=inhalt)
