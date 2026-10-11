"""
Texterkennung: PDF (pypdf) · DOCX (python-docx) · Bild/Scan (Tesseract).
Erweiterung des bisherigen pdftotext/pypdf-Moduls um DOCX und saubere Fehlerbehandlung.
"""
from __future__ import annotations

from io import BytesIO


def seiten_als_bilder(data: bytes, dateiname: str, max_seiten: int = 3, dpi: int = 130) -> list[bytes]:
    """PDF-Seiten oder Bild -> PNG-Bytes für das multimodale Modell. Leere Liste, wenn nicht möglich."""
    n = dateiname.lower()
    try:
        if n.endswith(".pdf"):
            import fitz  # pip install pymupdf
            doc = fitz.open(stream=data, filetype="pdf")
            return [p.get_pixmap(dpi=dpi).tobytes("png") for p in list(doc)[:max_seiten]]
        if n.endswith((".png", ".jpg", ".jpeg")):
            return [data]
    except Exception as e:
        print(f"[vision] {e}")
    return []


def text_aus_pdf(data: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception as e:
        print(f"[pdf] {e}")
        return ""


def text_aus_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError:
        print("[docx] python-docx fehlt: pip install python-docx")
        return ""
    d = docx.Document(BytesIO(data))
    teile = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            zellen = [c.text.strip() for c in row.cells]
            teile.append(" | ".join(dict.fromkeys(zellen)))  # doppelte (verbundene) Zellen entfernen
    return "\n".join(teile).strip()


def text_aus_bild(data: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(BytesIO(data)), lang="deu+eng").strip()
    except Exception as e:
        print(f"[ocr] {e}")
        return ""


def lese_text(data: bytes, dateiname: str) -> tuple[str, str]:
    """Gibt (text, methode) zurück."""
    n = dateiname.lower()
    if n.endswith(".pdf"):
        t = text_aus_pdf(data)
        if t:
            return t, "pypdf"
        # Scan-PDF: Tesseract via pdf2image
        try:
            import pdf2image, pytesseract
            seiten = pdf2image.convert_from_bytes(data, dpi=300)
            return "\n".join(pytesseract.image_to_string(s, lang="deu+eng") for s in seiten).strip(), "tesseract"
        except Exception as e:
            print(f"[scan-pdf] {e}")
            return "", "none"
    if n.endswith(".docx"):
        return text_aus_docx(data), "python-docx"
    if n.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff")):
        return text_aus_bild(data), "tesseract"
    return "", "none"
