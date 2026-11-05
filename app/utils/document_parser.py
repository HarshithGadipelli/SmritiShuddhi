import re
import io
import json
import base64
import logging
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Any, Tuple

logger = logging.getLogger("DocumentParser")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> Tuple[str, str]:
    """Extracts headline/title and body text from uploaded document bytes.
    Returns (suggested_title, body_text).
    """
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else 'txt'
    body = ""
    suggested_title = ""

    # 1. Plain Text or Markdown
    if ext in ['txt', 'text', 'md', 'markdown', 'log']:
        for enc in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
            try:
                body = file_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not body:
            body = file_bytes.decode('utf-8', errors='ignore')

    # 2. Microsoft Word Document (.docx)
    elif ext == 'docx':
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                xml_content = z.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                # Word namespaces typically use w:t
                paragraphs = []
                for p in tree.iter():
                    if p.tag.endswith('p'):
                        p_text = ''.join(node.text for node in p.iter() if node.text)
                        if p_text.strip():
                            paragraphs.append(p_text.strip())
                body = "\n\n".join(paragraphs)
        except Exception as e:
            logger.warning("Docx XML extraction failed: %s, falling back to string scan", e)
            body = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', file_bytes.decode('utf-8', errors='ignore'))

    # 3. JSON format
    elif ext == 'json':
        try:
            data = json.loads(file_bytes.decode('utf-8', errors='ignore'))
            if isinstance(data, dict):
                suggested_title = data.get('title') or data.get('headline') or ""
                body = data.get('text') or data.get('body') or data.get('content') or json.dumps(data, indent=2)
            elif isinstance(data, list):
                body = "\n\n".join(str(item) for item in data)
        except Exception:
            body = file_bytes.decode('utf-8', errors='ignore')

    # 4. CSV / Tabular
    elif ext in ['csv', 'tsv']:
        lines = file_bytes.decode('utf-8', errors='ignore').splitlines()
        body = "\n".join(lines[:100])

    # 5. PDF format (Pure python stream scan)
    elif ext == 'pdf':
        try:
            raw_pdf = file_bytes.decode('latin-1', errors='ignore')
            # Extract text enclosed in parentheses following 'Tj' or 'TJ' or between BT...ET
            text_chunks = []
            # Extract standard PDF text strings: (Text here) Tj
            matches = re.findall(r'\((.*?)\)\s*Tj', raw_pdf)
            if matches:
                text_chunks.extend(matches)
            else:
                # General literal string extraction
                matches = re.findall(r'BT\s*(.*?)\s*ET', raw_pdf, flags=re.DOTALL)
                for block in matches:
                    parts = re.findall(r'\((.*?)\)', block)
                    if parts:
                        text_chunks.extend(parts)
            if text_chunks:
                body = " ".join(text_chunks)
            else:
                # Strip binary headers and keep printable ascii/utf-8
                clean_lines = [
                    re.sub(r'[^a-zA-Z0-9\s.,!?:;\'"–—\-\n]', '', line).strip()
                    for line in raw_pdf.splitlines()
                ]
                body = " ".join([l for l in clean_lines if len(l) > 15])
        except Exception as e:
            logger.warning("PDF stream extraction notice: %s", e)
            body = file_bytes.decode('utf-8', errors='ignore')

    # Fallback general text
    else:
        body = file_bytes.decode('utf-8', errors='ignore')

    # Clean whitespace
    body = re.sub(r'[ \t]+', ' ', body).strip()

    # Determine title from first line if not provided
    if not suggested_title:
        lines = [line.strip() for line in body.splitlines() if line.strip()]
        if lines:
            first_line = lines[0]
            if len(first_line) > 100:
                suggested_title = first_line[:97] + "..."
            else:
                suggested_title = first_line
            # If the first line is the title, body can be the remainder
            if len(lines) > 1:
                body = "\n\n".join(lines[1:])
        else:
            suggested_title = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title()

    return suggested_title, body


def parse_base64_document(filename: str, base64_content: str) -> Dict[str, Any]:
    """Decodes base64 document and extracts structured article fields."""
    if ',' in base64_content:
        base64_content = base64_content.split(',', 1)[1]
    
    file_bytes = base64.b64decode(base64_content)
    title, body = extract_text_from_bytes(file_bytes, filename)
    word_count = len(body.split())
    
    return {
        "filename": filename,
        "title": title,
        "text": body,
        "word_count": word_count,
        "file_size_bytes": len(file_bytes),
        "file_type": filename.rsplit('.', 1)[-1].lower() if '.' in filename else "txt"
    }
