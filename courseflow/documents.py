"""Optional text-document import; scans remain an image-import task."""
from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


def document_text(path) -> str:
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix in {".txt", ".tsv"}:
        return target.read_text(encoding="utf-8-sig")
    if suffix == ".docx":
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        try:
            with ZipFile(target) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > 20 * 1024 * 1024:
                    raise ValueError("Word 文档过大, 请只保留课表部分.")
                root = ET.fromstring(archive.read(info))
            rows = []
            for row in root.findall(".//w:tbl/w:tr", ns):
                cells = [" ".join(node.text or "" for node in cell.findall(".//w:t", ns))
                         for cell in row.findall("w:tc", ns)]
                rows.append("\t".join(cells))
            if not rows:
                raise ValueError("Word 中没有可识别的课表表格, 可复制文字后粘贴导入.")
            return "\n".join(rows)
        except (OSError, KeyError, ET.ParseError, BadZipFile) as exc:
            raise ValueError("无法读取 Word 文档, 请确认是 .docx 文件.") from exc
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            from pypdf.errors import PyPdfError
        except ImportError as exc:
            raise ValueError("文字 PDF 导入需要可选依赖: pip install 'courseflow[documents]'. 扫描 PDF 请先导出图片再识图.") from exc
        try:
            reader = PdfReader(target)
            if reader.is_encrypted:
                raise ValueError("请先手动解密 PDF 后再导入.")
            if len(reader.pages) > 20:
                raise ValueError("PDF 超过 20 页, 请只保留课表部分.")
            parts = []
            for page in reader.pages:
                content = page.get_contents()
                if content is not None and len(content.get_data()) > 20 * 1024 * 1024:
                    raise ValueError("PDF 页面内容过大, 请只保留课表部分.")
                parts.append(page.extract_text(extraction_mode="layout") or "")
            text = "\n".join(parts)
        except (OSError, RuntimeError, PyPdfError) as exc:
            raise ValueError("无法提取 PDF 文字, 可以将页面保存为图片后识图.") from exc
        if not text.strip():
            raise ValueError("PDF 没有可提取的文字, 请将页面保存为图片后识图.")
        return text
    raise ValueError("支持 .txt / .tsv / .docx / 文字版 .pdf.")
