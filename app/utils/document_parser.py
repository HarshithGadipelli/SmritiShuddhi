import base64
import csv
import email
import email.policy
import io
import json
import logging
import mimetypes
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from typing import Any, Dict, List, Optional, Tuple

import config

logger = logging.getLogger("DocumentParser")

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "tif"}
TEXT_PLAIN_EXTENSIONS = {"txt", "text", "md", "markdown", "log", "yml", "yaml", "rtf"}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _detect_mime_type(filename: str, raw_bytes: bytes) -> str:
    if raw_bytes.startswith(b"%PDF"):
        return "application/pdf"
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WEBP":
        return "image/webp"
    if raw_bytes.startswith(b"GIF8"):
        return "image/gif"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _clean_whitespace(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _flatten_json(obj: Any, prefix: str = "", out: Optional[List[str]] = None) -> List[str]:
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_label = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, (dict, list)):
                _flatten_json(v, key_label, out)
            elif v is not None and str(v).strip():
                out.append(f"{key_label}: {str(v).strip()}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj[:60]):
            item_prefix = f"{prefix}[{idx}]" if prefix else f"Item {idx + 1}"
            _flatten_json(item, item_prefix, out)
    elif obj is not None and str(obj).strip():
        label = f"{prefix}: " if prefix else ""
        out.append(f"{label}{str(obj).strip()}")
    return out


def _gemini_vision_extract(mime_type: str, raw_bytes: bytes, context_hint: str = "") -> Optional[str]:
    """Extracts text, headlines, captions, and infographic content from images or PDFs using Gemini Vision."""
    api_key = (getattr(config, "GEMINI_API_KEY", "") or "").strip()
    if not api_key or not raw_bytes or len(raw_bytes) > 12_000_000:
        return None

    encoded = base64.b64encode(raw_bytes).decode("ascii")
    prompt = (
        "Extract ALL visible readable text, headlines, subheadings, dates, numerical figures, tables, "
        "captions, stamps, and relevant chart labels from this attached document/image faithfully as plain text. "
        "Preserve natural reading order (headline first, then body paragraphs). "
        "If nothing readable is present, describe concisely what factual content/chart is shown. "
        f"Context hint: {context_hint[:140]}"
    )
    models = list(dict.fromkeys([
        getattr(config, "GEMINI_MODEL", "gemini-3-flash-preview") or "gemini-3-flash-preview",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
    ]))
    ctx = _ssl_context()
    for mdl in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={urllib.parse.quote(api_key)}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": encoded}},
                    ]
                }]
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=18.0, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cands = data.get("candidates") or []
            if cands:
                parts = (cands[0].get("content") or {}).get("parts") or []
                texts = [p.get("text", "") for p in parts if p.get("text")]
                combined = "\n".join(texts).strip()
                if combined:
                    return combined
        except Exception as exc:
            logger.debug("Gemini multimodal extraction notice (%s): %s", mdl, exc)
            continue
    return None


def _local_ocr_image(raw_bytes: bytes) -> Optional[str]:
    """Optional offline Tesseract OCR fallback when pytesseract & binary are available."""
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(io.BytesIO(raw_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip() or None
    except Exception:
        return None


def _extract_image_text(raw_bytes: bytes, mime_type: str, context_hint: str = "") -> Tuple[str, Dict[str, Any]]:
    """Extracts text from an image using Pillow inspection + Gemini Vision / optional Tesseract."""
    dims = ""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw_bytes)) as img:
            dims = f"{img.width}x{img.height} {img.format or ''}".strip()
            # Re-encode non-standard formats (bmp/tiff) to PNG for broad API compatibility
            if mime_type in ("image/bmp", "image/tiff", "application/octet-stream"):
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="PNG")
                raw_bytes = buf.getvalue()
                mime_type = "image/png"
    except Exception:
        pass

    vision_text = _gemini_vision_extract(mime_type, raw_bytes, context_hint=context_hint)
    if vision_text:
        return vision_text, {"ocr_used": True, "ocr_engine": "Gemini Multimodal Vision", "image_dims": dims}

    local_text = _local_ocr_image(raw_bytes)
    if local_text:
        return local_text, {"ocr_used": True, "ocr_engine": "Tesseract OCR", "image_dims": dims}

    return "", {"ocr_used": False, "ocr_engine": "unavailable", "image_dims": dims}


def _extract_pdf_zlib_fallback(file_bytes: bytes) -> str:
    """Pure-Python FlateDecode PDF stream text fallback when pypdf is unavailable."""
    raw_pdf = file_bytes.decode("latin-1", errors="ignore")
    chunks: List[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", file_bytes, re.DOTALL):
        stream_data = match.group(1)
        try:
            decoded = zlib.decompress(stream_data).decode("latin-1", errors="ignore")
        except Exception:
            decoded = stream_data.decode("latin-1", errors="ignore")
        for tj in re.findall(r"\(([^()\\]*(?:\\.[^()\\]*)*)\)\s*Tj", decoded):
            chunks.append(tj.replace(r"\(", "(").replace(r"\)", ")").replace(r"\n", "\n"))
        for arr in re.findall(r"\[(.*?)\]\s*TJ", decoded, re.DOTALL):
            parts = re.findall(r"\(([^()\\]*(?:\\.[^()\\]*)*)\)", arr)
            if parts:
                chunks.append("".join(parts))
    if not chunks:
        matches = re.findall(r"\((.*?)\)\s*Tj", raw_pdf)
        chunks.extend(matches)
    return _clean_whitespace(" ".join(chunks))


def _extract_pdf(file_bytes: bytes, filename: str) -> Tuple[str, str, Dict[str, Any]]:
    suggested_title = ""
    text_pages: List[str] = []
    embedded_images: List[Tuple[str, bytes]] = []
    ocr_snippets: List[str] = []
    meta: Dict[str, Any] = {
        "extraction_method": "pdf_pypdf",
        "pages": 0,
        "images_detected": 0,
        "ocr_used": False,
    }

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        meta["pages"] = len(reader.pages)
        try:
            doc_info = reader.metadata
            if doc_info and getattr(doc_info, "title", None):
                t_cand = str(doc_info.title).strip()
                if len(t_cand) > 4 and not t_cand.lower().endswith(".pdf"):
                    suggested_title = t_cand
        except Exception:
            pass

        for idx, page in enumerate(reader.pages[:30]):
            try:
                pg_txt = (page.extract_text() or "").strip()
                if pg_txt:
                    text_pages.append(pg_txt)
            except Exception:
                pass
            try:
                for img in getattr(page, "images", []):
                    raw_img = getattr(img, "data", b"")
                    if raw_img and len(raw_img) >= 4096:
                        embedded_images.append((getattr(img, "name", f"page{idx + 1}.png"), raw_img))
            except Exception:
                pass
    except Exception as exc:
        logger.warning("pypdf extraction notice (%s): %s; trying zlib fallback", filename, exc)
        meta["extraction_method"] = "pdf_zlib_fallback"
        fallback_txt = _extract_pdf_zlib_fallback(file_bytes)
        if fallback_txt:
            text_pages.append(fallback_txt)

    meta["images_detected"] = len(embedded_images)
    combined_text = "\n\n".join(text_pages).strip()

    # Run multimodal Vision OCR if PDF is image-based/scanned OR mixes text + embedded images
    if len(combined_text) < 120:
        pdf_vision = _gemini_vision_extract("application/pdf", file_bytes, context_hint=filename)
        if pdf_vision:
            combined_text = pdf_vision if not combined_text else f"{combined_text}\n\n{pdf_vision}"
            meta["ocr_used"] = True
            meta["extraction_method"] = "pdf_multimodal_vision"

    if embedded_images and not meta["ocr_used"]:
        for img_name, img_bytes in embedded_images[:3]:
            mime = _detect_mime_type(img_name, img_bytes)
            ocr_txt, ocr_info = _extract_image_text(img_bytes, mime, context_hint=f"{filename} ({img_name})")
            if ocr_txt and ocr_txt.lower() not in combined_text.lower():
                ocr_snippets.append(f"[Image {img_name} Text]: {ocr_txt}")
                meta["ocr_used"] = meta["ocr_used"] or bool(ocr_info.get("ocr_used"))

    if ocr_snippets:
        combined_text = (combined_text + "\n\n" + "\n\n".join(ocr_snippets)).strip()
        meta["extraction_method"] = "pdf_hybrid_text_plus_vision"

    return suggested_title, combined_text, meta


def _extract_docx(file_bytes: bytes, filename: str) -> Tuple[str, str, Dict[str, Any]]:
    paragraphs: List[str] = []
    tables_count = 0
    embedded_images: List[Tuple[str, bytes]] = []
    ocr_snippets: List[str] = []
    meta: Dict[str, Any] = {
        "extraction_method": "docx_xml_structured",
        "tables_extracted": 0,
        "images_detected": 0,
        "ocr_used": False,
    }

    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            xml_targets = [
                n for n in z.namelist()
                if re.match(r"word/(document|header\d*|footer\d*)\.xml$", n, re.IGNORECASE)
            ]
            # Put document.xml first so body headlines lead
            xml_targets.sort(key=lambda x: (0 if x.endswith("document.xml") else 1, x))

            for xml_name in xml_targets:
                try:
                    tree = ET.fromstring(z.read(xml_name))
                    for elem in tree.iter():
                        tag = elem.tag.split("}")[-1]
                        if tag == "tbl":
                            tables_count += 1
                        elif tag == "p":
                            p_text = "".join(node.text for node in elem.iter() if node.text)
                            if p_text.strip():
                                paragraphs.append(p_text.strip())
                except Exception:
                    continue

            media_files = [
                n for n in z.namelist()
                if n.lower().startswith("word/media/")
                and n.lower().rsplit(".", 1)[-1] in IMAGE_EXTENSIONS
            ]
            for mf in media_files[:5]:
                try:
                    img_bytes = z.read(mf)
                    if len(img_bytes) >= 4096:
                        embedded_images.append((mf.rsplit("/", 1)[-1], img_bytes))
                except Exception:
                    continue
    except Exception as exc:
        logger.warning("Docx XML extraction failed (%s): %s", filename, exc)
        raw_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", file_bytes.decode("utf-8", errors="ignore"))
        paragraphs.append(raw_text)

    meta["tables_extracted"] = tables_count
    meta["images_detected"] = len(embedded_images)

    body = "\n\n".join(dict.fromkeys(paragraphs))
    if embedded_images:
        for img_name, img_bytes in embedded_images[:3]:
            mime = _detect_mime_type(img_name, img_bytes)
            ocr_txt, ocr_info = _extract_image_text(img_bytes, mime, context_hint=f"{filename} ({img_name})")
            if ocr_txt and ocr_txt.lower() not in body.lower():
                ocr_snippets.append(f"[Embedded Media {img_name}]: {ocr_txt}")
                meta["ocr_used"] = meta["ocr_used"] or bool(ocr_info.get("ocr_used"))

    if ocr_snippets:
        body = (body + "\n\n" + "\n\n".join(ocr_snippets)).strip()
        meta["extraction_method"] = "docx_hybrid_text_plus_vision"

    return "", body, meta


def _extract_html_or_xml(file_bytes: bytes, ext: str, filename: str) -> Tuple[str, str, Dict[str, Any]]:
    raw_str = file_bytes.decode("utf-8", errors="replace")
    meta: Dict[str, Any] = {"extraction_method": f"structured_{ext}", "images_detected": 0, "ocr_used": False}
    suggested_title = ""
    parts: List[str] = []

    if ext in ("html", "htm"):
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(raw_str, "html.parser")
            if soup.title and soup.title.string:
                suggested_title = soup.title.string.strip()
            h1 = soup.find("h1")
            if h1 and h1.get_text(" ", strip=True):
                suggested_title = h1.get_text(" ", strip=True)

            img_alts: List[str] = []
            embedded_b64_imgs: List[Tuple[str, bytes]] = []
            for img in soup.find_all("img"):
                alt = (img.get("alt") or "").strip()
                if alt:
                    img_alts.append(f"[Image Caption]: {alt}")
                src = (img.get("src") or "").strip()
                if src.startswith("data:image/") and ";base64," in src:
                    hdr, b64d = src.split(";base64,", 1)
                    mime = hdr.replace("data:", "").strip()
                    try:
                        img_raw = base64.b64decode(b64d)
                        if len(img_raw) >= 4096:
                            embedded_b64_imgs.append((mime, img_raw))
                    except Exception:
                        pass

            for noise in soup(["script", "style", "noscript", "svg"]):
                noise.decompose()

            for node in soup.find_all(["h2", "h3", "p", "li", "tr", "blockquote"]):
                txt = node.get_text(" | " if node.name == "tr" else " ", strip=True)
                if txt and len(txt) > 3:
                    parts.append(txt)

            parts.extend(img_alts)
            meta["images_detected"] = len(embedded_b64_imgs) + len(img_alts)
            for mime, img_raw in embedded_b64_imgs[:2]:
                ocr_txt, ocr_info = _extract_image_text(img_raw, mime, context_hint=filename)
                if ocr_txt:
                    parts.append(f"[Inline Image Text]: {ocr_txt}")
                    meta["ocr_used"] = meta["ocr_used"] or bool(ocr_info.get("ocr_used"))

            body = "\n\n".join(dict.fromkeys(parts))
            return suggested_title, body, meta
        except Exception:
            pass

    try:
        root = ET.fromstring(raw_str)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1]
            txt = (elem.text or "").strip()
            if txt:
                if not suggested_title and tag.lower() in ("title", "headline", "subject"):
                    suggested_title = txt
                else:
                    parts.append(f"{tag}: {txt}")
        return suggested_title, "\n".join(parts[:300]), meta
    except Exception:
        cleaned = re.sub(r"<[^>]+>", " ", raw_str)
        return suggested_title, cleaned, meta


def _extract_email(file_bytes: bytes, filename: str) -> Tuple[str, str, Dict[str, Any]]:
    msg = email.message_from_bytes(file_bytes, policy=email.policy.default)
    suggested_title = str(msg.get("subject") or "").strip()
    sender = str(msg.get("from") or "").strip()
    date_hdr = str(msg.get("date") or "").strip()

    text_parts: List[str] = []
    if sender:
        text_parts.append(f"From: {sender}")
    if date_hdr:
        text_parts.append(f"Date: {date_hdr}")

    images: List[Tuple[str, bytes]] = []
    for part in msg.walk():
        ctype = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        if ctype == "text/plain":
            text_parts.append(payload.decode("utf-8", errors="replace"))
        elif ctype == "text/html" and len(text_parts) <= 2:
            _, html_body, _ = _extract_html_or_xml(payload, "html", filename)
            if html_body:
                text_parts.append(html_body)
        elif ctype.startswith("image/") and len(payload) >= 4096:
            images.append((ctype, payload))

    meta: Dict[str, Any] = {
        "extraction_method": "eml_structured",
        "images_detected": len(images),
        "ocr_used": False,
    }
    for mime, img_raw in images[:3]:
        ocr_txt, ocr_info = _extract_image_text(img_raw, mime, context_hint=suggested_title or filename)
        if ocr_txt:
            text_parts.append(f"[Attached Image Text]: {ocr_txt}")
            meta["ocr_used"] = meta["ocr_used"] or bool(ocr_info.get("ocr_used"))

    return suggested_title, "\n\n".join(text_parts), meta


def _extract_spreadsheet(file_bytes: bytes, ext: str, filename: str) -> Tuple[str, str, Dict[str, Any]]:
    if ext in ("csv", "tsv"):
        delim = "\t" if ext == "tsv" else ","
        raw_txt = file_bytes.decode("utf-8", errors="replace")
        rows = list(csv.reader(io.StringIO(raw_txt), delimiter=delim))
        if not rows:
            return "", raw_txt, {"extraction_method": ext, "rows": 0}
        headers = rows[0]
        formatted: List[str] = []
        for r in rows[1:200]:
            if any(c.strip() for c in r):
                pairs = [f"{headers[i].strip() if i < len(headers) else f'Col{i+1}'}: {val.strip()}" for i, val in enumerate(r) if val.strip()]
                if pairs:
                    formatted.append(" | ".join(pairs))
        body = "\n".join(formatted) if formatted else "\n".join(raw_txt.splitlines()[:150])
        return "", body, {"extraction_method": f"{ext}_structured", "rows": len(rows)}

    # XLSX / XLSM
    meta: Dict[str, Any] = {"extraction_method": "xlsx_openpyxl", "images_detected": 0, "ocr_used": False}
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        lines: List[str] = []
        img_blobs: List[bytes] = []
        for sheet in wb.worksheets[:8]:
            lines.append(f"=== Sheet: {sheet.title} ===")
            rows_iter = list(sheet.iter_rows(values_only=True))
            headers = [str(h or "").strip() for h in (rows_iter[0] if rows_iter else [])]
            for r in rows_iter[1:200]:
                cells = [
                    f"{headers[i] if i < len(headers) and headers[i] else f'Col{i+1}'}: {str(c).strip()}"
                    for i, c in enumerate(r)
                    if c is not None and str(c).strip()
                ]
                if cells:
                    lines.append(" | ".join(cells))
            for im in getattr(sheet, "_images", []):
                try:
                    raw_i = im._data()
                    if raw_i and len(raw_i) >= 4096:
                        img_blobs.append(raw_i)
                except Exception:
                    pass
        meta["images_detected"] = len(img_blobs)
        for ib in img_blobs[:2]:
            ocr_txt, ocr_info = _extract_image_text(ib, _detect_mime_type("sheet.png", ib), context_hint=filename)
            if ocr_txt:
                lines.append(f"[Sheet Embedded Image]: {ocr_txt}")
                meta["ocr_used"] = meta["ocr_used"] or bool(ocr_info.get("ocr_used"))
        return "", "\n".join(lines), meta
    except Exception as exc:
        logger.warning("XLSX parse notice (%s): %s", filename, exc)
        return "", "", meta


def extract_document_with_metadata(file_bytes: bytes, filename: str) -> Tuple[str, str, Dict[str, Any]]:
    """Extracts (suggested_title, body_text, metadata) across text, semi-structured, and image+text docs."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"
    mime_type = _detect_mime_type(filename, file_bytes)
    suggested_title = ""
    body = ""
    meta: Dict[str, Any] = {
        "extraction_method": ext,
        "images_detected": 0,
        "ocr_used": False,
        "tables_extracted": 0,
    }

    if ext in TEXT_PLAIN_EXTENSIONS or mime_type.startswith("text/plain"):
        for enc in ("utf-8", "utf-16", "latin-1", "cp1252"):
            try:
                body = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not body:
            body = file_bytes.decode("utf-8", errors="ignore")
        if ext == "rtf":
            body = re.sub(r"\\[a-zA-Z]+\d* ?|[{}]", " ", body)

    elif ext in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        ocr_txt, img_meta = _extract_image_text(file_bytes, mime_type, context_hint=filename)
        body = ocr_txt
        meta["extraction_method"] = "image_multimodal_ocr"
        meta["images_detected"] = 1
        meta.update(img_meta)

    elif ext == "docx":
        suggested_title, body, meta = _extract_docx(file_bytes, filename)

    elif ext == "json":
        try:
            data = json.loads(file_bytes.decode("utf-8", errors="ignore"))
            if isinstance(data, dict):
                suggested_title = str(data.get("title") or data.get("headline") or data.get("subject") or "").strip()
                direct_body = data.get("text") or data.get("body") or data.get("content") or data.get("description")
                if isinstance(direct_body, str) and direct_body.strip():
                    body = direct_body.strip()
                    extra_lines = _flatten_json({k: v for k, v in data.items() if k not in ("title", "headline", "text", "body", "content")})
                    if extra_lines:
                        body = body + "\n\n" + "\n".join(extra_lines[:40])
                else:
                    body = "\n".join(_flatten_json(data))
            else:
                body = "\n".join(_flatten_json(data))
            meta["extraction_method"] = "json_structured"
        except Exception:
            body = file_bytes.decode("utf-8", errors="ignore")

    elif ext in ("csv", "tsv", "xlsx", "xlsm"):
        suggested_title, body, meta = _extract_spreadsheet(file_bytes, ext, filename)

    elif ext in ("html", "htm", "xml", "rss"):
        suggested_title, body, meta = _extract_html_or_xml(file_bytes, ext, filename)

    elif ext == "eml":
        suggested_title, body, meta = _extract_email(file_bytes, filename)

    elif ext == "pdf" or mime_type == "application/pdf":
        suggested_title, body, meta = _extract_pdf(file_bytes, filename)

    else:
        body = file_bytes.decode("utf-8", errors="ignore")

    body = _clean_whitespace(body)

    if not suggested_title:
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        if lines:
            first_line = lines[0]
            suggested_title = (first_line[:97] + "...") if len(first_line) > 100 else first_line
            if len(lines) > 1:
                body = "\n\n".join(lines[1:])
        else:
            suggested_title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()

    return suggested_title, body, meta


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    """Extracts headline/title and body text from uploaded document bytes.
    Returns (suggested_title, body_text).
    """
    title, body, _ = extract_document_with_metadata(file_bytes, filename)
    return title, body


def parse_base64_document(filename: str, base64_content: str) -> Dict[str, Any]:
    """Decodes base64 document/image and extracts structured article fields plus extraction metadata."""
    if "," in base64_content:
        base64_content = base64_content.split(",", 1)[1]

    file_bytes = base64.b64decode(base64_content)
    title, body, meta = extract_document_with_metadata(file_bytes, filename)
    word_count = len(body.split())

    return {
        "filename": filename,
        "title": title,
        "text": body,
        "word_count": word_count,
        "file_size_bytes": len(file_bytes),
        "file_type": filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt",
        "extraction_metadata": meta,
    }
