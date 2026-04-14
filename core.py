"""
PDF Voz by Jair Lima — Módulo central de extração e marcação de posição.
Suporta PDF (PyMuPDF) e EPUB (ebooklib).
"""
import hashlib
import html as htmlmod
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

BOOKMARK_FILE = Path.home() / ".pdfvoz_bookmarks.json"
HEADER_ZONE = 0.08   # top 8% da página = cabeçalho
FOOTER_ZONE = 0.92   # bottom 8% da página = rodapé
MIN_PARA_LEN = 30    # ignora parágrafos menores que isso (ruído)


# ---------------------------------------------------------------------------
# Hash do arquivo para identificação no bookmark
# ---------------------------------------------------------------------------

def file_hash(path: str) -> str:
    """Calcula hash MD5 dos primeiros 64 KB do arquivo."""
    with open(path, "rb") as f:
        data = f.read(65536)
    return hashlib.md5(data).hexdigest()


# ---------------------------------------------------------------------------
# Extração de PDF
# ---------------------------------------------------------------------------

def _collect_repeated_texts(doc) -> set:
    """Detecta textos repetidos em cabeçalho/rodapé em >= 3 páginas."""
    header_count: dict = {}
    footer_count: dict = {}

    for page in doc:
        h = page.rect.height
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, _, btype = block
            if btype != 0:
                continue
            key = text.strip()[:120]
            if not key:
                continue
            if y0 < h * HEADER_ZONE:
                header_count[key] = header_count.get(key, 0) + 1
            elif y1 > h * FOOTER_ZONE:
                footer_count[key] = footer_count.get(key, 0) + 1

    blacklist = set()
    blacklist.update(k for k, v in header_count.items() if v >= 3)
    blacklist.update(k for k, v in footer_count.items() if v >= 3)
    return blacklist


def _extract_pages_text(doc, blacklist: set) -> list[list[str]]:
    """Extrai texto de cada página, sem cabeçalhos/rodapés."""
    pages = []
    for page in doc:
        h = page.rect.height
        paras = []
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text, _, btype = block
            if btype != 0:
                continue
            text = text.strip()
            if not text or len(text) < MIN_PARA_LEN:
                continue
            if y0 < h * HEADER_ZONE:
                continue
            if y1 > h * FOOTER_ZONE:
                continue
            if text[:120] in blacklist:
                continue
            paras.append(text)
        pages.append(paras)
    return pages


def _chapters_from_toc(toc: list, pages_text: list, n_pages: int) -> list[dict]:
    """Divide o texto em capítulos usando o TOC nativo do PDF."""
    index_titles = {
        "índice", "sumário", "conteúdo", "contents",
        "table of contents", "indice", "summary",
    }

    # Pular entradas de índice/sumário no início do TOC
    start_idx = 0
    for i, (level, title, page) in enumerate(toc):
        if any(kw in title.lower() for kw in index_titles):
            start_idx = i + 1

    toc_use = toc[start_idx:] if start_idx < len(toc) else toc

    chapters = []
    for i, (level, title, page) in enumerate(toc_use):
        p0 = max(0, page - 1)
        p1 = toc_use[i + 1][2] - 1 if i + 1 < len(toc_use) else n_pages

        paras = []
        for pg_idx in range(p0, min(p1, n_pages)):
            paras.extend(pages_text[pg_idx])

        if paras:
            chapters.append({"title": title.strip(), "paragraphs": paras, "page": page})

    return chapters


def _is_index_page(paras: list[str]) -> bool:
    """Detecta páginas de índice/sumário (muitas linhas curtas com números)."""
    if not paras:
        return False
    short = sum(1 for p in paras if len(p) < 80)
    has_nums = sum(1 for p in paras if re.search(r'\d{1,4}\s*$', p))
    return short > len(paras) * 0.55 and has_nums > len(paras) * 0.25


_CHAPTER_PATTERNS = [
    re.compile(r'^(capítulo|capitulo|chapter)\s+\w+', re.IGNORECASE),
    re.compile(r'^(CAPÍTULO|CAPITULO|CHAPTER)\s+\w+'),
    re.compile(r'^\d+[\.\)]\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]'),
    re.compile(r'^[IVXLCDMivxlcdm]{1,6}[\.\)\s]\s'),
]


def _is_chapter_heading(text: str) -> bool:
    if len(text) > 80 or len(text) < 2:
        return False
    return any(p.match(text.strip()) for p in _CHAPTER_PATTERNS)


def _chapters_from_heuristic(pages_text: list[list[str]]) -> list[dict]:
    """Detecta capítulos por padrões de texto quando não há TOC."""
    # Encontrar última página de índice
    last_index_page = -1
    for i, paras in enumerate(pages_text):
        if _is_index_page(paras):
            last_index_page = i

    chapters = []
    current_title = "Capítulo 1"
    current_paras: list[str] = []
    current_page = 1

    for page_idx, paras in enumerate(pages_text):
        if page_idx <= last_index_page:
            continue

        for para in paras:
            if _is_chapter_heading(para):
                if current_paras:
                    chapters.append({
                        "title": current_title,
                        "paragraphs": current_paras,
                        "page": current_page,
                    })
                current_title = para.strip()
                current_paras = []
                current_page = page_idx + 1
            else:
                current_paras.append(para)

    if current_paras:
        chapters.append({
            "title": current_title,
            "paragraphs": current_paras,
            "page": current_page,
        })

    if not chapters:
        all_paras = [p for page in pages_text for p in page]
        chapters = [{"title": "Capítulo 1", "paragraphs": all_paras, "page": 1}]

    return chapters


def extract_pdf(path: str) -> list[dict]:
    """
    Extrai texto de PDF agrupado por capítulos.
    Retorna lista de dicts: {'title', 'paragraphs', 'page'}
    """
    doc = fitz.open(path)
    blacklist = _collect_repeated_texts(doc)
    pages_text = _extract_pages_text(doc, blacklist)
    toc = doc.get_toc()
    n_pages = len(pages_text)

    if toc:
        chapters = _chapters_from_toc(toc, pages_text, n_pages)
    else:
        chapters = []

    if not chapters:
        chapters = _chapters_from_heuristic(pages_text)

    doc.close()
    return chapters


# ---------------------------------------------------------------------------
# Extração de EPUB
# ---------------------------------------------------------------------------

def _strip_html(html_text: str) -> str:
    """Remove tags HTML e retorna texto limpo."""
    html_text = re.sub(
        r'<(script|style)[^>]*>.*?</(script|style)>',
        '', html_text, flags=re.DOTALL | re.IGNORECASE,
    )
    html_text = re.sub(
        r'<(p|div|br|h[1-6]|li|tr)[^>]*/?>',
        '\n', html_text, flags=re.IGNORECASE,
    )
    html_text = re.sub(r'<[^>]+>', '', html_text)
    return htmlmod.unescape(html_text)


def _epub_chapter_title(item, book) -> str:
    """Tenta obter título legível do item EPUB via TOC."""
    try:
        href = item.get_name()
        def _search_toc(nodes):
            for node in nodes:
                if isinstance(node, tuple):
                    section, children = node
                    if hasattr(section, 'href') and href in section.href:
                        return section.title
                    found = _search_toc(children)
                    if found:
                        return found
                else:
                    if hasattr(node, 'href') and href in node.href:
                        return node.title
            return None
        title = _search_toc(book.toc)
        if title:
            return title
    except Exception:
        pass
    name = item.get_name().split('/')[-1]
    return re.sub(r'\.(html?|xhtml?)$', '', name, flags=re.IGNORECASE)


def extract_epub(path: str) -> list[dict]:
    """Extrai texto de EPUB agrupado por capítulos (ordem do spine)."""
    import ebooklib
    from ebooklib import epub

    book = epub.read_epub(path, options={"ignore_ncx": True})
    spine_ids = [iid for iid, _ in book.spine]
    chapters = []

    for iid in spine_ids:
        item = book.get_item_with_id(iid)
        if item is None or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        content = item.get_content().decode("utf-8", errors="ignore")
        text = _strip_html(content)
        paras = [
            p.strip() for p in text.split('\n')
            if len(p.strip()) >= MIN_PARA_LEN
        ]
        if paras:
            chapters.append({
                "title": _epub_chapter_title(item, book),
                "paragraphs": paras,
                "page": 0,
            })

    if not chapters:
        chapters = [{"title": "Leitura", "paragraphs": [], "page": 0}]

    return chapters


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def load_file(path: str) -> list[dict]:
    """Detecta formato (PDF ou EPUB) e retorna lista de capítulos."""
    ext = Path(path).suffix.lower()
    if ext == ".epub":
        return extract_epub(path)
    return extract_pdf(path)


# ---------------------------------------------------------------------------
# Bookmark
# ---------------------------------------------------------------------------

def _load_bookmarks() -> dict:
    if BOOKMARK_FILE.exists():
        try:
            with open(BOOKMARK_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def get_bookmark(path: str) -> Optional[dict]:
    """Retorna posição salva ou None."""
    key = file_hash(path)
    return _load_bookmarks().get(key)


def save_bookmark(path: str, chapter_idx: int, para_idx: int):
    """Salva posição de leitura."""
    key = file_hash(path)
    bookmarks = _load_bookmarks()
    bookmarks[key] = {
        "path": str(path),
        "chapter": chapter_idx,
        "paragraph": para_idx,
        "timestamp": datetime.now().isoformat(),
    }
    with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, ensure_ascii=False, indent=2)


def clear_bookmark(path: str):
    """Remove marcador de posição."""
    key = file_hash(path)
    bookmarks = _load_bookmarks()
    bookmarks.pop(key, None)
    with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, ensure_ascii=False, indent=2)
