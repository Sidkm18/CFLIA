#!/usr/bin/env python3
"""Append selected real screenshots while retaining each report's existing edits.

Uses python-docx for authoring, then preserves every original package member
except the document, its relationships and image content-type declarations.
Run with the bundled Python described by the documents skill.
"""
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PAGES = json.loads((ROOT / 'submission/ADDITIONAL_SCREENSHOTS.json').read_text())
CHANGED_PARTS = {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}


def add_pages(doc):
    for page in PAGES:
        heading = doc.add_paragraph(page['heading'], style='Heading 1')
        heading.paragraph_format.page_break_before = True
        heading.paragraph_format.space_before = Pt(0)
        heading.paragraph_format.space_after = Pt(8)
        heading.paragraph_format.keep_with_next = True
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0, 0, 0)
        intro = doc.add_paragraph(page['intro'])
        intro.paragraph_format.space_after = Pt(7)
        intro.paragraph_format.keep_with_next = True
        for figure in page['images']:
            path = ROOT / figure['path']
            with Image.open(path) as image:
                width, height = image.size
            scale = min(6.65 / width, figure['max_height'] / height)
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1
            p.paragraph_format.keep_with_next = True
            shape = p.add_run().add_picture(str(path), width=Inches(width * scale), height=Inches(height * scale))
            shape._inline.docPr.set('descr', figure['caption'])
            shape._inline.docPr.set('title', path.stem)
            caption = doc.add_paragraph(figure['caption'], style='Caption')
            caption.paragraph_format.space_before = Pt(0)
            caption.paragraph_format.space_after = Pt(8)
            caption.paragraph_format.keep_with_next = False
            for run in caption.runs:
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0, 0, 0)
        for text in page.get('after', []):
            doc.add_paragraph(text)


def main():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    qa = ROOT / 'tmp' / ('report-screenshots-' + stamp)
    before_dir = qa / 'before'
    before_dir.mkdir(parents=True)
    audit = []
    for name in ['CFLIA_Final_Report.docx', 'CFLIA_Final_Report_Editable.docx']:
        path = ROOT / 'output/documents' / name
        original = path.read_bytes()
        original_hash = hashlib.sha256(original).hexdigest()
        doc = Document(path)
        if any(p.text == PAGES[0]['heading'] for p in doc.paragraphs):
            raise RuntimeError('Screenshot pages already present; refusing a duplicate appendix')
        before = Document(path)
        original_count = len(before.paragraphs)
        original_paragraph_xml = [p._p.xml for p in before.paragraphs]
        original_tables = [t._tbl.xml for t in before.tables]
        shutil.copy2(path, before_dir / name)
        add_pages(doc)
        stage = qa / name
        doc.save(stage)
        merged = qa / ('preserved-' + name)
        with ZipFile(path) as old, ZipFile(stage) as new, ZipFile(merged, 'w') as result:
            for info in old.infolist():
                result.writestr(info, new.read(info.filename) if info.filename in CHANGED_PARTS else old.read(info.filename))
            for info in new.infolist():
                if info.filename not in old.namelist():
                    assert info.filename.startswith('word/media/'), info.filename
                    result.writestr(info, new.read(info.filename))
        checked = Document(merged)
        assert [p._p.xml for p in checked.paragraphs[:original_count]] == original_paragraph_xml
        assert [t._tbl.xml for t in checked.tables] == original_tables
        assert len(checked.inline_shapes) == len(before.inline_shapes) + 10
        with ZipFile(path) as old, ZipFile(merged) as new:
            assert all(old.read(n) == new.read(n) for n in old.namelist() if n not in CHANGED_PARTS)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash, 'Report was saved externally; refusing overwrite'
        os.replace(merged, path)
        audit.append({'file': str(path), 'original_sha256': original_hash,
                      'updated_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'original_paragraphs_unchanged': original_count, 'original_images': len(before.inline_shapes),
                      'updated_images': len(checked.inline_shapes), 'tables_unchanged': True})
        print('Updated', name, 'with ten screenshots; existing paragraphs, tables and images preserved')
    shutil.copy2(ROOT / 'output/pdf/CFLIA_Final_Report.pdf', before_dir / 'CFLIA_Final_Report.pdf')
    (qa / 'edit-audit.json').write_text(json.dumps({'files': audit, 'pages': PAGES}, indent=2) + '\n')
    print('QA directory:', qa)


if __name__ == '__main__':
    main()
