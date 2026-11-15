"""Export the generated DOCX's content through local Chromium print layout.

This fallback requires no downloads and does not use a personal browser profile.
The source DOCX remains the editable master. HTML is an intermediate, not a deliverable.
"""
import argparse
import base64
from html import escape
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def convert(source):
    with ZipFile(source) as z:
        document = ET.fromstring(z.read('word/document.xml'))
        relationships = ET.fromstring(z.read('word/_rels/document.xml.rels'))
        images = {r.get('Id'): z.read('word/' + r.get('Target'))
                  for r in relationships if r.get('Type', '').endswith('/image')}
    def runs(element):
        out = ''
        for run in element.findall(W+'r'):
            size = run.find(W+'rPr/'+W+'sz')
            css = f'font-size:{int(size.get(W+"val"))/2}pt' if size is not None else ''
            text = ''
            for child in run:
                if child.tag == W+'t':
                    text += escape(child.text or '')
                elif child.tag == W+'br':
                    text += '<br>'
                elif child.tag == W+'drawing':
                    blip = child.find('.//'+A+'blip')
                    ext = child.find('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent')
                    encoded = base64.b64encode(images[blip.get(R+'embed')]).decode()
                    width = int(ext.get('cx'))/914400
                    text += f'<img alt="Report figure" style="width:{width}in" src="data:image/png;base64,{encoded}">'
            if run.find(W+'rPr/'+W+'b') is not None:
                css += ';font-weight:bold'
            out += f'<span style="{css}">{text}</span>'
        return out
    def paragraph(element):
        style = element.find(W+'pPr/'+W+'pStyle')
        style = style.get(W+'val') if style is not None else 'Normal'
        align = element.find(W+'pPr/'+W+'jc')
        spacing = element.find(W+'pPr/'+W+'spacing')
        css = f'text-align:{align.get(W+"val")};' if align is not None else ''
        if spacing is not None:
            for attr, rule in [('before','margin-top'),('after','margin-bottom')]:
                if spacing.get(W+attr) is not None:
                    css += f'{rule}:{int(spacing.get(W+attr))/20}pt;'
        return f'<p class="{style}" style="{css}">{runs(element) or "&nbsp;"}</p>'
    def table(element):
        widths = [int(c.get(W+'w'))/20 for c in element.findall(W+'tblGrid/'+W+'gridCol')]
        out = '<table><colgroup>' + ''.join(f'<col style="width:{w}pt">' for w in widths) + '</colgroup>'
        for i, row in enumerate(element.findall(W+'tr')):
            out += '<tr>'
            for cell in row.findall(W+'tc'):
                out += ('<th>' if i == 0 else '<td>')
                out += ''.join(paragraph(p) for p in cell.findall(W+'p'))
                out += '</th>' if i == 0 else '</td>'
            out += '</tr>'
        return out + '</table>'
    pages = ['']
    for element in document.find(W+'body'):
        if element.tag == W+'p':
            if element.find('.//'+W+'br[@'+W+'type="page"]') is not None:
                pages.append('')
            else:
                pages[-1] += paragraph(element)
        elif element.tag == W+'tbl':
            pages[-1] += table(element)
    css = '''@page {size:A4; margin:20mm 25.4mm} * {box-sizing:border-box}
    body {margin:0;color:#111;font-family:"Times New Roman",serif;font-size:12pt;line-height:1.15}
    .page {height:256mm;position:relative;break-after:page;display:flow-root;padding-top:.01px}
    .page:last-of-type {break-after:auto}.content{display:flow-root;padding-top:5mm;padding-bottom:5mm}
    p {margin:0 0 5pt} .Title {font-size:19pt;font-weight:bold;color:black}
    .University {font-size:16pt;font-weight:bold;color:#233b59}.Subtitle{font-size:14pt}
    .Heading1{font-size:14pt;font-weight:bold;color:#233b59;break-after:avoid}
    .Heading2{font-size:12pt;font-weight:bold;break-after:avoid}
    .Code{font-family:Consolas,monospace;font-size:8.5pt;line-height:10pt;white-space:pre-wrap}
    .Caption{font-size:10pt;font-style:italic;color:#444}
    table{width:451.3pt;table-layout:fixed;border-collapse:collapse;margin:0 0 7pt;font-size:9.5pt;line-height:1.1}
    td,th{border:.5pt solid #c6cbd3;padding:3.25pt 3.75pt;vertical-align:top;text-align:left;overflow-wrap:normal}
    th{background:#e9eef4} table p{margin:0!important;line-height:1.1}
    .header{position:absolute;right:0;top:-10mm;font-size:9pt;color:#666}
    .footer{position:absolute;bottom:0;width:100%;text-align:center;font-size:9pt}
    img{max-width:100%;height:auto}'''
    output = '<!doctype html><html><head><meta charset="utf-8"><title>Lexical Analyzer Project Report</title><style>'+css+'</style></head><body>'
    for i, content in enumerate(pages, 1):
        output += '<section class="page">'
        if i > 1:
            output += '<header class="header">DIT University | Compiler Design</header>'
        output += '<div class="content">' + content + '</div>'
        if i > 1:
            output += f'<footer class="footer">Pranshu Rawat | {i}</footer>'
        output += '</section>'
    output += '''<pre id="layout-metrics" style="display:none"></pre><script>
    window.addEventListener('load',()=>{document.getElementById('layout-metrics').textContent=JSON.stringify(
    Array.from(document.querySelectorAll('.page')).map((p,i)=>({page:i+1,height:p.clientHeight,content:p.querySelector('.content').getBoundingClientRect().height})));});
    </script></body></html>'''
    return output, len(pages)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', type=Path, required=True)
    args = parser.parse_args()
    scratch = ROOT/'tmp/report-render'
    scratch.mkdir(parents=True, exist_ok=True)
    source = ROOT/'docs/Lexical_Analyzer_Report.docx'
    html, count = convert(source)
    html_path = scratch/'report.html'
    html_path.write_text(html, encoding='utf-8')
    common = [str(args.browser), '--headless', '--user-data-dir='+str(scratch/'browser-profile'),
              '--allow-file-access-from-files']
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if hasattr(subprocess,'CREATE_NO_WINDOW') else {}
    result = subprocess.run(common + ['--dump-dom', html_path.as_uri()], capture_output=True, timeout=60, **flags)
    (scratch/'browser-layout.log').write_bytes(result.stderr)
    if result.returncode:
        raise RuntimeError('Chromium layout failed; see browser-layout.log')
    dom = result.stdout.decode('utf-8', errors='replace')
    matched = re.search(r'<pre id="layout-metrics"[^>]*>(.*?)</pre>', dom, re.S)
    if not matched:
        raise RuntimeError('Layout metrics not found')
    metrics = json.loads(matched.group(1))
    (scratch/'layout-metrics.json').write_text(json.dumps(metrics, indent=2))
    overflow = [p for p in metrics if p['content'] > p['height'] + 1]
    if overflow:
        raise RuntimeError(f'Content overflows its page: {overflow}')
    output = ROOT/'docs/Lexical_Analyzer_Report.pdf'
    result = subprocess.run(common + ['--no-pdf-header-footer','--print-to-pdf='+str(output),html_path.as_uri()],
                            capture_output=True, timeout=60, **flags)
    (scratch/'browser-export.log').write_bytes(result.stderr)
    if result.returncode or not output.is_file():
        raise RuntimeError('PDF export failed; see browser-export.log')
    actual_pages = len(re.findall(rb'/Type\s*/Page\b', output.read_bytes()))
    if actual_pages != count:
        raise RuntimeError(f'PDF pagination mismatch: {actual_pages} physical pages for {count} report pages')
    print(json.dumps({'pdf':str(output),'logical_pages':count,'physical_pages':actual_pages,
                      'bytes':output.stat().st_size,'layout':metrics},indent=2))
