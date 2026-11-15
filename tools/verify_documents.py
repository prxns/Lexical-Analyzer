"""Validate the actual DOCX package and PDF export, using the standard library."""
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as E
from zipfile import ZipFile
import zlib

ROOT=Path(__file__).resolve().parents[1]
docx=ROOT/'docs/Lexical_Analyzer_Report.docx'
pdf=ROOT/'docs/Lexical_Analyzer_Report.pdf'
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
REL='{http://schemas.openxmlformats.org/package/2006/relationships}'
def png_valid(data):
    assert data[:8]==b'\x89PNG\r\n\x1a\n'
    position=8
    while position<len(data):
        length=struct.unpack_from('>I',data,position)[0]
        kind=data[position+4:position+8]
        payload=data[position+8:position+8+length]
        crc=struct.unpack_from('>I',data,position+8+length)[0]
        assert zlib.crc32(kind+payload)&0xFFFFFFFF==crc,'Invalid embedded image CRC'
        position+=length+12
        if kind==b'IEND':
            return
    raise AssertionError('Truncated PNG image')
with ZipFile(docx) as archive:
    assert archive.testzip() is None,'Corrupted DOCX ZIP entry'
    names=set(archive.namelist())
    for part in names:
        if part.endswith(('.xml','.rels')):
            E.fromstring(archive.read(part))
    document=E.fromstring(archive.read('word/document.xml'))
    text=' '.join(n.text or '' for n in document.iter(W+'t'))
    for required in ['Pranshu Rawat','1000021904','Section  D','DIT UNIVERSITY',
                     '2026-27','Source editor','Diagnostics','analysis_scan','Native Desktop Testing']:
        assert required.casefold() in text.casefold(),required
    logical_pages=1+len(document.findall('.//'+W+'br[@'+W+'type="page"]'))
    relations=E.fromstring(archive.read('word/_rels/document.xml.rels'))
    embedded=0
    for relation in relations:
        target='word/'+relation.get('Target')
        assert target in names,'Broken document relationship: '+target
        if relation.get('Type','').endswith('/image'):
            png_valid(archive.read(target))
            embedded+=1
    assert embedded>=7,'Expected real interface screenshots and report figures'
raw=pdf.read_bytes()
assert raw.startswith(b'%PDF-') and b'%%EOF' in raw[-1024:],'Invalid/truncated PDF'
physical_pages=len(re.findall(rb'/Type\s*/Page\b',raw))
assert physical_pages==logical_pages,(logical_pages,physical_pages)
assert b'/Font' in raw and b'/Subtype /Image' in raw,'Expected genuine text and image objects'
print(f'Verified genuine DOCX and PDF: {logical_pages} pages, {embedded} valid embedded images, package CRC/XML/relationships and PDF structure intact.')
