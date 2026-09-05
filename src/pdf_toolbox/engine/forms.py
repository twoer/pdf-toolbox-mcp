"""fill_form / edit_metadata：AcroForm 填写与元数据编辑（pikepdf，纯 Python 依赖）。"""

from __future__ import annotations

from pathlib import Path

from .pages import _page_count, _prep_output
from .sandbox import assert_readable, ensure_pdf


def _iter_fields(acroform) -> list:
    """展平 AcroForm 字段树（含 Parent 层级，限定一层常见深度）。"""
    result: list = []
    stack = list(acroform.get("/Fields", []))
    while stack:
        field = stack.pop(0)
        result.append(field)
        if "/Kids" in field:
            stack.extend(field.Kids)
    return result


def _field_name(field, parent_name: str = "") -> str:
    own = str(field.get("/T", "")) if "/T" in field else ""
    return f"{parent_name}.{own}" if parent_name and own else (own or parent_name)


def fill_form(
    path: str | Path,
    fields: dict,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """填写 AcroForm 字段（flat 字段名 → 字符串或布尔）。

    字段名以 "." 连接层级（如 employee.name）。未匹配的字段在 missing 中返回。
    外观由查看器按 NeedAppearances 重新生成（Adobe 之外普遍支持）。
    """
    pdf_path = assert_readable(ensure_pdf(Path(path)))
    import pikepdf

    out = Path(output) if output else pdf_path.with_name(f"{pdf_path.stem}_filled.pdf")
    out = _prep_output(out, overwrite)

    def _full_name(field) -> str:
        parts = [str(field.get("/T", ""))] if "/T" in field else []
        parent = field.get("/Parent")
        depth = 0
        while parent is not None and depth < 8:
            parts.append(str(parent.get("/T", "")))
            parent = parent.get("/Parent")
            depth += 1
        return ".".join(reversed([p for p in parts if p]))

    with pikepdf.open(pdf_path) as pdf:
        if "/AcroForm" not in pdf.Root:
            raise ValueError("文档没有 AcroForm 表单")

        filled: list[str] = []
        for field in _iter_fields(pdf.Root.AcroForm):
            name = _full_name(field)
            if name in fields:
                value = fields[name]
                if isinstance(value, bool):
                    field.V = pikepdf.Name("Yes") if value else pikepdf.Name.Off
                    field.AS = field.V
                else:
                    field.V = str(value)
                filled.append(name)

        pdf.Root.AcroForm.NeedAppearances = True
        pdf.save(out)

    return {
        "input": str(pdf_path),
        "output": str(out),
        "filled": filled,
        "missing": sorted(set(fields) - set(filled)),
        "pages": _page_count(out),
    }


_META_KEYS = {
    "title": ("/Title", "dc:title"),
    "author": ("/Author", "dc:creator"),
    "subject": ("/Subject", "dc:description"),
    "keywords": ("/Keywords", "pdf:Keywords"),
    "creator": ("/Creator", "xmp:CreatorTool"),
}


def edit_metadata(
    path: str | Path,
    title: str | None = None,
    author: str | None = None,
    subject: str | None = None,
    keywords: str | None = None,
    creator: str | None = None,
    clear: bool = False,
    output: str | Path | None = None,
    overwrite: bool = False,
) -> dict:
    """编辑文档元数据（docinfo + XMP 双写）。clear=True 清空全部。"""
    pdf = assert_readable(ensure_pdf(Path(path)))
    import pikepdf

    out = Path(output) if output else pdf.with_name(f"{pdf.stem}_meta.pdf")
    out = _prep_output(out, overwrite)

    values = {
        "title": title, "author": author, "subject": subject,
        "keywords": keywords, "creator": creator,
    }
    provided = {k: v for k, v in values.items() if v is not None}

    with pikepdf.open(pdf) as doc:
        if clear:
            for key in list(doc.docinfo.keys()):
                del doc.docinfo[key]
        for key, value in provided.items():
            doc.docinfo[_META_KEYS[key][0]] = value
        with doc.open_metadata() as meta:
            if clear:
                for _, xmp_key in _META_KEYS.values():
                    if xmp_key in meta:
                        del meta[xmp_key]
            for key, value in provided.items():
                xmp_key = _META_KEYS[key][1]
                # dc:creator 在 XMP 中是有序数组（rdf:Seq），其余为标量
                meta[xmp_key] = [value] if xmp_key == "dc:creator" else value
        doc.save(out)

    return {
        "input": str(pdf),
        "output": str(out),
        "set": sorted(provided),
        "cleared": clear,
    }
