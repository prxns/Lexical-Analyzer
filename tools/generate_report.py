"""Build the editable academic report from verified project evidence.

Uses standard-library OOXML and Pillow only for the explanatory flowchart.
Open the resulting DOCX in Word and export it to PDF. No scanner is implemented here.
"""
from pathlib import Path
import json
import textwrap
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
OBJECTIVE = 'To design and implement a program that reads a source code and identifies tokens such as keywords, identifiers, constants, and operators.'
NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
RNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
body = []
images = []


def p(text='', style='Normal', align=None, size=None, before=0, after=100):
    props = f'<w:pStyle w:val="{style}"/><w:spacing w:before="{before}" w:after="{after}"/>'
    if align:
        props += f'<w:jc w:val="{align}"/>'
    run_props = f'<w:sz w:val="{size}"/>' if size else ''
    runs = '<w:br/>'.join(f'<w:t xml:space="preserve">{escape(line)}</w:t>' for line in text.split('\n'))
    body.append(f'<w:p><w:pPr>{props}</w:pPr><w:r><w:rPr>{run_props}</w:rPr>{runs}</w:r></w:p>')


def heading(text):
    p(text, 'Heading1', before=100, after=160)


def sub(text):
    p(text, 'Heading2', before=90, after=100)


def page():
    body.append('<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>')


def code(text, width=94):
    for line in text.splitlines():
        lines = textwrap.wrap(line, width=width, replace_whitespace=False, drop_whitespace=False) or ['']
        for part in lines:
            p(part, 'Code', after=0)


def table(headers, rows, widths, font=19):
    xml = '<w:tbl><w:tblPr><w:tblW w:w="9026" w:type="dxa"/><w:tblLayout w:type="fixed"/>'
    xml += '<w:tblBorders>' + ''.join(f'<w:{edge} w:val="single" w:sz="4" w:color="C6CBD3"/>' for edge in ['top','left','bottom','right','insideH','insideV']) + '</w:tblBorders>'
    xml += '<w:tblCellMar><w:top w:w="65" w:type="dxa"/><w:left w:w="75" w:type="dxa"/><w:bottom w:w="65" w:type="dxa"/><w:right w:w="75" w:type="dxa"/></w:tblCellMar></w:tblPr>'
    xml += '<w:tblGrid>' + ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>'
    for index, row in enumerate([headers, *rows]):
        xml += '<w:tr><w:trPr><w:cantSplit/>' + ('<w:tblHeader/>' if index == 0 else '') + '</w:trPr>'
        for text, width in zip(row, widths):
            shade = '<w:shd w:fill="E9EEF4"/>' if index == 0 else ''
            xml += f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr><w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="220" w:lineRule="auto"/></w:pPr><w:r><w:rPr><w:sz w:val="{font}"/>'
            if index == 0:
                xml += '<w:b/>'
            xml += f'</w:rPr><w:t xml:space="preserve">{escape(str(text))}</w:t></w:r></w:p></w:tc>'
        xml += '</w:tr>'
    xml += '</w:tbl><w:p><w:pPr><w:spacing w:after="40"/></w:pPr></w:p>'
    body.append(xml)


def image(filename, width_inches, dark_panel=False):
    image_path = ROOT / filename
    with Image.open(image_path) as im:
        w, h = im.size
    cx = int(width_inches * 914400)
    cy = int(cx * h / w)
    number = len(images) + 1
    images.append(image_path)
    panel = '<w:shd w:fill="233B59"/><w:ind w:left="2610" w:right="2610"/>' if dark_panel else ''
    body.append(f'''<w:p><w:pPr><w:jc w:val="center"/>{panel}</w:pPr><w:r><w:drawing>
    <wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing">
      <wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{number}" name="{escape(image_path.stem)}" descr="{escape(image_path.stem)}"/>
      <a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
      <pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{number}" name="image{number}.png"/><pic:cNvPicPr/></pic:nvPicPr>
      <pic:blipFill><a:blip r:embed="image{number}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
      <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>
      </a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>''')


def make_flowchart():
    canvas = Image.new('RGB', (1100, 1080), 'white')
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype('C:/Windows/Fonts/calibri.ttf', 28)
    small = ImageFont.truetype('C:/Windows/Fonts/calibri.ttf', 24)
    navy = '#233B59'
    def label(box, text, f=font):
        x1, y1, x2, y2 = box
        bbox = d.multiline_textbbox((0, 0), text, font=f, align='center', spacing=3)
        d.multiline_text(((x1+x2-bbox[2])/2, (y1+y2-bbox[3])/2-2), text, font=f, fill=navy, align='center', spacing=3)
    def box(coords, text):
        d.rounded_rectangle(coords, radius=12, fill='#EFF3F7', outline=navy, width=3)
        label(coords, text)
    def arrow(points):
        d.line(points, fill=navy, width=3)
        x, y = points[-1]; px, py = points[-2]
        if x == px:
            direction = 1 if y > py else -1
            d.polygon([(x,y),(x-7,y-12*direction),(x+7,y-12*direction)],fill=navy)
        else:
            direction = 1 if x > px else -1
            d.polygon([(x,y),(x-12*direction,y-7),(x-12*direction,y+7)],fill=navy)
    box((300, 20, 800, 100), 'Open and read source safely')
    arrow([(550,100),(550,140)])
    box((300,140,800,220), 'Initialize Lexer and counters')
    arrow([(550,220),(550,260)])
    box((300,260,800,350), 'lexer_next\nSkip whitespace and comments')
    arrow([(550,350),(550,390)])
    diamond=[(550,390),(725,455),(550,520),(375,455)]
    d.polygon(diamond, fill='#EFF3F7',outline=navy,width=3)
    label((390,420,710,490),'EOF reached?')
    arrow([(725,455),(920,455),(920,650)])
    d.text((760,420),'Yes',font=small,fill=navy)
    box((805,650,1070,770),'Print summary\nand exit')
    arrow([(550,520),(550,560)])
    d.text((570,526),'No',font=small,fill=navy)
    box((300,560,800,650),'Scan identifier, literal or symbol\nUse longest matching span')
    arrow([(550,650),(550,690)])
    box((300,690,800,780),'Return Token or Error\nwith opening line and column')
    arrow([(550,780),(550,820)])
    box((300,820,800,910),'Print row and update counts')
    arrow([(550,910),(550,970),(170,970),(170,305),(300,305)])
    d.text((190,930),'Continue after a recoverable error',font=small,fill=navy)
    canvas.save(ROOT/'assets/scanner-flowchart.png')


def make_desktop_flowchart():
    canvas=Image.new('RGB',(1100,1130),'white')
    draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('C:/Windows/Fonts/calibri.ttf',28)
    navy='#233B59'
    boxes=[(260,20,840,105,'Source editor and file actions'),
           (260,155,840,240,'Capture UTF-8 snapshot and revision'),
           (260,290,840,390,'Worker thread\nanalysis_scan calls the original lexer_next'),
           (260,440,840,525,'Owned Token vector and real counts'),
           (260,575,840,660,'Post WM_ANALYSIS_DONE to main thread'),
           (260,710,840,810,'Revision still matches?\nReject cancelled or outdated results'),
           (260,860,840,965,'Dashboard, token table and diagnostics\nSearch, navigate and export CSV')]
    for x1,y1,x2,y2,label in boxes:
        draw.rounded_rectangle((x1,y1,x2,y2),radius=12,fill='#EFF3F7',outline=navy,width=3)
        bounds=draw.multiline_textbbox((0,0),label,font=font,align='center',spacing=4)
        draw.multiline_text(((x1+x2-bounds[2])/2,(y1+y2-bounds[3])/2-2),label,font=font,fill=navy,align='center',spacing=4)
    for previous,current in zip(boxes,boxes[1:]):
        start,end=previous[3],current[1]
        draw.line((550,start,550,end),fill=navy,width=3)
        draw.polygon([(550,end),(542,end-13),(558,end-13)],fill=navy)
    draw.line([(260,760),(125,760),(125,198),(260,198)],fill=navy,width=3)
    draw.polygon([(260,198),(247,190),(247,206)],fill=navy)
    draw.text((160,1010),'Editor changes invalidate results and request cancellation.',font=font,fill=navy)
    canvas.save(ROOT/'assets/desktop-flowchart.png')


def build():
    import hashlib
    from PIL import Image
    body.clear(); images.clear()
    gui=json.loads((DOCS/'gui-test-results.json').read_text())
    assert gui['successful'] and gui['tests_run']==len(gui['passed'])
    assert hashlib.sha256((ROOT/'dist/LexicalAnalyzer.exe').read_bytes()).hexdigest()==gui['executable_sha256']
    scanner=json.loads((DOCS/'test-results-windows.json').read_text())
    assert scanner['successful'] and scanner['tests_run']==36
    provenance=json.loads((DOCS/'gui-verification.json').read_text())
    for name in ['gui-demo','gui-errors','gui-ready','gui-empty']:
        with Image.open(DOCS/'screenshots'/f'{name}.png') as im:
            im.verify()
    with Image.open(DOCS/'screenshots/gui-demo.png') as im:
        w,h=im.size
        im.crop((int(w*.025),int(h*.215),int(w*.975),int(h*.332))).save(ROOT/'assets/dashboard-detail.png')
        im.crop((int(w*.445),int(h*.35),int(w*.97),int(h*.73))).save(ROOT/'assets/token-table-detail.png')
    with Image.open(DOCS/'screenshots/gui-errors.png') as im:
        w,h=im.size
        im.crop((int(w*.445),int(h*.735),int(w*.97),int(h*.92))).save(ROOT/'assets/diagnostics-detail.png')
    make_desktop_flowchart()
    # 1 Cover
    p('',after=240); image('assets/dit-logo.png',2.0,dark_panel=True)
    p('DIT UNIVERSITY','University','center',after=300)
    p('DESIGN AND IMPLEMENTATION\nOF A LEXICAL ANALYZER','Title','center',after=240)
    p('Native Windows Desktop Application','Subtitle','center',after=180)
    p('Subject  Compiler Design',align='center',after=440)
    p('Submitted by',align='center',after=100)
    p('Pranshu Rawat','Heading2','center',after=100)
    p('SAP ID  1000021904\nSection  D',align='center',after=240)
    p('B.Tech. Computer Science and Engineering',align='center',after=100)
    p('Academic Year  2026-27',align='center',after=160)
    p('Implementation  C11 and the Windows API',align='center'); page()
    # 2 Abstract and contents
    heading('Abstract')
    p('This project combines a hand-written C11 lexical analyzer with a native Windows desktop application. A source editor, token dashboard, searchable token table and diagnostics panel present the actual output of the existing C scanner. Source files can be opened, edited, saved and analyzed without a terminal. The packaged executable starts directly and requires no Python, Node.js, server or external GUI framework.')
    p(f'The scanner remains the single source of truth. A portable C analysis model owns token spans, computes counts, filters results and exports CSV. A Win32 worker analyzes an editor snapshot while the window continues processing input; source revisions prevent stale results from replacing newer edits. The demonstration produces 128 valid tokens and no errors. All 36 scanner tests, the C analysis integration executable and {gui["tests_run"]} native desktop workflow tests passed in the recorded verification run.')
    sub('Table of Contents')
    table(['Section','Page'],[
        ('1 Introduction and Problem Statement',3),('2 Objectives and Scope',3),
        ('3 Theory and System Requirements',4),('4 System Architecture',5),
        ('5 Interface and Application Workflow',6),('6 Actual Application Overview',7),
        ('7 Dashboard and Token Explorer',8),('8 Error Diagnostics',9),
        ('9 Algorithm and Implementation',10),('10 Scanner and Model Testing',11),
        ('11 Native Desktop Testing',12),('12 Complexity and Limitations',13),
        ('13 Conclusion',14),('14 References and Appendix',14)], [7900,1126],font=20)
    page()
    # 3 Purpose
    heading('1 Introduction and Problem Statement')
    p('Lexical analysis groups source characters into meaningful units before later compiler stages consider their arrangement or meaning. For example, int total = 10; contains a keyword, identifier, operator, integer and punctuator. The scanner must distinguish reserved words from similar identifiers, recognize multi-character operators and avoid treating comments as ordinary program tokens [1].')
    p('The original project exposed this behavior through a command-line program. The desktop upgrade preserves that implementation and adds a practical demonstration workflow: the user can see the source, its token stream, category totals and error locations in one window. The interface must display genuine scanner results and remain usable while scanning larger inputs.')
    heading('2 Objectives and Scope')
    p(OBJECTIVE)
    p('Supporting objectives are to provide a clear native interface, preserve source positions, explain lexical errors, support searchable results and CSV export, and verify that the graphical and command-line applications use the same scanner.')
    sub('Implemented scope')
    p('The lexical subset includes all 44 C11 keywords, ASCII identifiers, common integer and decimal floating forms, ordinary strings and single-character constants, C operators, punctuators and digraphs. Whitespace and both C comment forms are skipped. Invalid or unsupported lexical input produces diagnostics at its opening position. The project does not parse syntax, resolve identifiers, evaluate macros or generate executable code.')
    p('The desktop layer supports UTF-8 text files and Unicode Windows filenames, but the lexical rules remain the documented ASCII subset. The editor removes a UTF-8 BOM when opening a text file and normalizes its snapshot to CRLF. This behavior does not alter the portable CLI scanner, which continues to analyze its input bytes directly.')
    page()
    # 4 Theory and requirements
    heading('3 Theory and System Requirements')
    table(['Concept','Meaning and example'],[
        ('Token and lexeme','A token has a category and source span; its lexeme is the original text, such as 0x2A.'),
        ('Pattern','A recognition rule; ASCII identifiers follow [A-Za-z_][A-Za-z_0-9]*.'),
        ('Keyword','A reserved word such as int or _Atomic, matched after the entire identifier has been read.'),
        ('Constants','Integer, float, string and character categories; the dashboard combines these four counts.'),
        ('Operators','Symbols such as >=, >>= and ++, matched longest first.'),
        ('Punctuators','Structural and preprocessing symbols, including braces, semicolons, dots, # and ##.'),
        ('Maximal munch','Prefer the longest recognized span; >>= is one operator rather than >> followed by =.')
    ],[2200,6826],font=21)
    sub('Running the application')
    p('The distribution targets Windows 10 version 1703 or newer and Windows 11 on x64. Double-click dist/LexicalAnalyzer.exe; keep its samples subfolder beside it. The executable uses only Windows system libraries, RichEdit and common controls. It has the Windows GUI subsystem and does not display a console. No compiler, Python, Node.js or server is needed to demonstrate it.')
    sub('Development and verification')
    p('Rebuilding requires a C11-capable MinGW GCC toolchain and windres. The automated runner uses Python 3 standard-library modules; the actual scanner and interface are written in C. GUI tests require Windows. Portable scanner and analysis-model checks also run on Linux with GCC and Clang. Report authoring uses local Python/Pillow tooling; those tools are not application dependencies.')
    p('No minimum CPU speed or installed RAM specification is claimed. Desktop input is limited to 4 MiB and 500,000 result rows to bound editor and table storage. The preserved CLI remains available for larger inputs. Fonts and geometry scale with window DPI; resizing was exercised by the native integration suite. Multi-monitor hardware combinations are not claimed as exhaustively tested.')
    page()
    # 5 Architecture
    heading('4 System Architecture')
    p('The GUI does not contain a second tokenizer. Both applications link src/lexer.c. The desktop adds a portable result model and a Win32 presentation layer. Tokens borrow spans from the analysis model\'s owned source buffer; that buffer remains alive while results are displayed.')
    image('assets/desktop-flowchart.png',4.65)
    p('Figure 1  Actual desktop analysis and revision-check workflow','Caption','center')
    p('The worker never modifies controls. It posts a completion message containing an owned result. The main thread accepts it only if the editor revision still matches. An edit requests cancellation and clears displayed results. Closing waits asynchronously for an active worker to release its snapshot, rather than blocking the message loop.')
    page()
    # 6 Interface explanation
    heading('5 Interface and Application Workflow')
    table(['Area or action','Implemented behavior'],[
        ('Header','Application name, C Source Code Analysis description, source filename and current status.'),
        ('Source editor','RichEdit with Consolas, line numbers, multiline text, scrolling, undo and selection.'),
        ('Open and Save','Native file dialogs; UTF-8 saves use a temporary file and replace the destination after a successful write.'),
        ('Sample buttons','Load the packaged copies of demo.c and errors.c. Save asks for a new filename for a sample copy.'),
        ('Analyze Code','Captures editor text, starts a native worker and changes to Cancel Analysis while work is active.'),
        ('Summary cards','Display actual valid-token, keyword, identifier, constant, operator, punctuator and error counts.'),
        ('Token explorer','Virtual list view with stable token numbers, exact lexemes, categories, lines and columns.'),
        ('Search and category','Case-insensitive ASCII search intersects the selected category without changing overall counts.'),
        ('Diagnostics','Separate error rows with line/column, message and lexeme; success text when the error count is zero.'),
        ('Navigation','Double-clicking a token or error selects its original source span in the editor.'),
        ('Export Results','Writes all result rows and diagnostic messages to CSV, regardless of the active view filter.'),
        ('Clear controls','Clear Results retains source; Clear Editor asks about unsaved edits before replacing text.')
    ],[2550,6476],font=20)
    sub('Demonstration sequence')
    p('1. Double-click LexicalAnalyzer.exe.\n2. Load Sample or open a C file.\n3. Click Analyze Code, or press Ctrl+Enter.\n4. Inspect counts and tokens, then search or filter.\n5. Open Error Sample to demonstrate diagnostics and source navigation.\n6. Export the completed analysis as CSV.')
    p('Ctrl+O opens a file, Ctrl+S saves, Ctrl+F focuses token search and Ctrl+E exports. Tab inserts a tab inside the source editor. Unsaved-change prompts provide Save, Discard and Cancel choices.')
    page()
    # 7 Native overview screenshot
    heading('6 Actual Application Overview')
    p('Figure 2 is a genuine Windows capture of the compiled desktop application after analyzing the valid sample. It was taken by the native integration test process using Windows PrintWindow; the displayed values come from the C scanner, not a visual mockup.')
    image('docs/screenshots/gui-demo.png',6.2)
    p('Figure 2  Running application with the successful demonstration analysis','Caption','center')
    p('The source editor and result explorer share one window. Category colors provide restrained emphasis, while the dashboard distinguishes a completed analysis from the initial state. Before a scan the cards display a dash; analyzing empty input produces actual zero counts. This avoids presenting invented statistics in an empty view.')
    p('The native executable was launched as a child application with its real packaged files during verification. The test suite reads visible control values and compares their totals with JSON produced by the existing CLI. The captured executable hash and CI run are retained with the verification evidence.')
    page()
    # 8 Enlarged genuine UI panels
    heading('7 Dashboard and Token Explorer')
    image('assets/dashboard-detail.png',6.2)
    p('Figure 3  Enlarged dashboard crop from the unmodified application capture','Caption','center')
    table(['Metric','Actual valid sample result'],[
        ('Valid tokens',128),('Keywords',15),('Identifiers',29),('Constants',18),('Operators',23),('Separators / punctuators',43),('Lexical errors',0)
    ],[5000,4026],font=20)
    image('assets/token-table-detail.png',6.2)
    p('Figure 4  Enlarged token explorer crop from the same running application','Caption','center')
    p('The constants total is the sum of 12 integers, 2 floats, 2 strings and 2 characters. Error rows are counted separately from valid tokens. Table numbering follows scanner order and remains stable when a filter hides other rows. Native list views supply selection, scrolling and resizable columns; long lexemes retain their full source span and are exported without the visible cell-width restriction.')
    page()
    # 9 Error screenshot
    heading('8 Error Diagnostics')
    p('The intentional-error sample produces 16 valid tokens and six diagnostic rows. It demonstrates invalid octal digits, an incomplete exponent, an invalid escape, an unclosed string, an unsupported character and an unclosed block comment.')
    image('docs/screenshots/gui-errors.png',6.2)
    p('Figure 5  Actual native application after analyzing the error sample','Caption','center')
    image('assets/diagnostics-detail.png',6.2)
    p('Figure 6  Enlarged diagnostics crop; the complete list scrolls independently','Caption','center')
    p('Each diagnostic retains the opening line and column and the relevant lexeme. The first malformed number begins at line 2, column 13. Double-clicking a row locates its source span. Newline-terminated quoted literals recover at the newline; an unterminated block comment consumes the remaining input and reports its opening position.')
    page()
    # 10 Real algorithm and implementation
    heading('9 Algorithm and Implementation')
    code('\n'.join([
        'on Analyze Code:', '    snapshot = editor_source(); revision = source_revision',
        '    start scan_thread(snapshot, revision)', 'worker:',
        '    analysis_scan -> lexer_init -> repeated lexer_next',
        '    store each real Token; accumulate category counts',
        '    post WM_ANALYSIS_DONE with owned result', 'main thread:',
        '    reject cancelled or outdated revisions',
        '    populate statistics, token rows and diagnostics',
        '    keep processing resize, editor and control messages']))
    table(['Source function or structure','Actual responsibility'],[
        ('Lexer, Token, lexer_next','Original portable scanner state and borrowed lexeme spans; unchanged by the GUI upgrade.'),
        ('Analysis and analysis_scan','Own a source copy and grow the token vector safely; retain counts and diagnostic tokens.'),
        ('analysis_filter','Category matching and KMP substring search; produces indices rather than duplicated tokens.'),
        ('analysis_export_csv','Writes complete token rows with quote escaping and diagnostic messages.'),
        ('begin_analysis and scan_thread','Capture editor UTF-8, start CreateThread and post completion to the window.'),
        ('analysis_finished','Check source revision/cancellation, transfer ownership and refresh the real result views.'),
        ('display_item and jump_to_token','Provide virtual-table text and convert source byte spans to editor selection indices.'),
        ('load_source and save_source','Validate text-file input and save source through a checked temporary-file replacement.'),
        ('window_proc and layout_window','Route native messages, draw the dark interface, resize controls and handle DPI changes.')
    ],[3400,5626],font=20)
    p('The scanner still applies longest-match recognition and exact keyword lookup. Whitespace/comment skipping, numeric validation, escapes and source positions remain in src/lexer.c. No lexical rule is duplicated in the interface or Python test harness.')
    page()
    # 11 Existing tests and model tests
    heading('10 Scanner and Model Testing')
    p('The original 36 regression methods remain intact. They passed on Windows GCC, Linux GCC and Linux Clang. The same scanner suite and the new analysis-model executable also passed under AddressSanitizer and UndefinedBehaviorSanitizer. Strict compilation uses -std=c11 -Wall -Wextra -Wpedantic -Werror.')
    table(['Cases','Test condition','Expected and actual outcome','Status'],[
        ('T01-T02','44 keywords and identifier boundaries','Exact categories and lexemes matched','Pass'),
        ('T03-T06','Integer, float, string and character forms','Supported literals recognized exactly','Pass'),
        ('T07-T09','Operators, longest match and punctuators','Expected full token sequence matched','Pass'),
        ('T10-T13','Comments, lines, columns and newline forms','Trivia skipped and positions matched','Pass'),
        ('T14-T16','Empty source, whitespace and comments only','Zero ordinary tokens and no errors','Pass'),
        ('T17-T24','Invalid bytes, malformed/unsupported literals','Expected errors and opening positions','Pass'),
        ('T25-T26','Recovery and individual symbols at EOF','Later and final tokens retained','Pass'),
        ('T27-T28','Long lexemes and 5,000 source lines','Full spans and 25,000 tokens retained','Pass'),
        ('T29-T32','Samples and command-line behavior','Expected counts, output and exit codes','Pass'),
        ('T33-T36','120 random inputs and remaining edge cases','Termination and asserted invariants held','Pass'),
        ('Model','Counts, filter groups and search intersection','Matched actual C Token data','Pass'),
        ('Model','CSV quotes, cancellation and empty input','Correct output and safe retained ownership','Pass'),
        ('Model','Long repetitive identifier and bounded display','Search matched; original span retained','Pass')
    ],[1200,3000,4000,826],font=19)
    p('The portable C model test does not replace the scanner tests. It checks the additional bridge used by the desktop: source/result ownership, category aggregates, constant grouping, view indices, safe printable lexeme formatting and complete CSV output. Cancelled analysis leaves a caller\'s previous model intact, and freeing an initialized model twice is safe.')
    p('Random-input testing and sanitizers cover exercised paths; they are not proof of full C conformance or the absence of every possible defect. Full machine-readable results and genuine execution transcripts are supplied in docs/.')
    page()
    # 12 Real GUI integration results
    heading('11 Native Desktop Testing')
    p(f'All {gui["tests_run"]} native workflow tests passed using the actual packaged executable. The test harness starts its own child process and targets only windows belonging to that process. Expected token aggregates come from the real CLI; there is no Python tokenizer or simulated dashboard.')
    descriptions=[
        ('Launch and controls','Windows GUI subsystem; all controls present'),
        ('Valid sample','128 tokens, zero errors; values match CLI'),
        ('Load Sample button','Packaged demo is loaded and analyzed'),
        ('Error Sample button','16 valid tokens and six diagnostics'),
        ('Search and category','Case-insensitive intersection; totals unchanged'),
        ('Clear Results','Rows removed; editor source retained'),
        ('Clear Editor and empty input','Empty analysis gives actual zero counts'),
        ('Save File','Changed UTF-8 source saved and reanalyzed'),
        ('Open File dialog','Selected file opened through the native dialog'),
        ('Export Results dialog','CSV contains all actual token rows'),
        ('Edits during analysis','No stale old-source result survives an edit'),
        ('Cancel and resize','Cancellation completes; window remains usable'),
        ('Double-click navigation','The token source span is selected')]
    rows=[]
    for i,name in enumerate(gui['passed']):
        description=descriptions[i] if i<len(descriptions) else ('Additional input check',name)
        rows.append((f'G{i+1:02}',description[0],description[1],'As expected','Pass'))
    table(['ID','Action','Expected result','Actual','Status'],rows,[600,2300,3900,1450,776],font=18)
    sub('Distribution validation')
    p('The package check reads the actual PE header and import table. It verifies the Windows x64 GUI subsystem, per-monitor DPI manifest, standard system-library dependencies, both packaged samples and the preserved CLI. The native workflow suite launches the distribution executable itself. The application does not require a Python interpreter or development environment at runtime.')
    p(f'Evidence source: GitHub Actions run {provenance["run_id"]}. Screenshot capture and GUI test records include the executable SHA-256. These are executed outcomes; no terminal or application screenshots have been manufactured.')
    page()
    # 13 Complexity and limits
    heading('12 Complexity and Limitations')
    p('Let n be source length and t the number of returned rows. The scanner advances through input in O(n) time for the fixed keyword/symbol tables. The desktop model retains the source and token vector, requiring O(n + t) storage. Growth is geometric. The CLI still streams returned tokens while retaining its source buffer, so its own working memory remains O(n).')
    p('Filtering scans candidate token spans with a bounded query and KMP prefix table. Its work is linear in the searched lexeme bytes plus query preparation, while its index array uses O(t) space. The virtual table requests visible text rather than creating a child control for every token. CSV export is proportional to the output size and does not depend on the active filter.')
    p('The desktop limit is 4 MiB of UTF-8 source and 500,000 result rows. Allocation, encoding, I/O and limit failures are reported. Cancellation is checked between scanner calls; a single long lexeme is completed before the next check. File opening and saving are synchronous, bounded text-file operations; lexical analysis itself runs in the worker.')
    p('The lexical subset excludes universal character names, wide/encoded literals, hexadecimal floats, binary integers and C23 digit separators. Character constants must contain one character or supported escape. Numeric magnitudes and escape values are not evaluated or range-checked. Adjacent strings remain separate tokens.')
    p('Preprocessor markers are punctuators. Macro expansion, conditional preprocessing, header-name recognition, trigraph translation and backslash-newline splicing are not implemented. Block comments do not nest. The scanner does not validate syntax, declarations, types, balanced delimiters or program meaning.')
    p('Windows supplies the native file dialogs, caption and scrolling infrastructure. Exact system chrome can vary across Windows versions. Per-monitor DPI support is implemented in the manifest and resize path; verification does not claim exhaustive testing across every monitor, display scale or accessibility configuration. The portable CLI remains the cross-platform interface.')
    page()
    # 14 Conclusion, references and appendix
    heading('13 Conclusion')
    p('The project now provides a complete native desktop workflow while retaining its original C scanner and command-line application. The editor, dashboard, token explorer, diagnostics, filtering, navigation and CSV export operate on real C analysis results. The packaged application launches directly and does not require manual setup of a server or language runtime.')
    p(f'Verification includes the original 36 scanner methods, shared C model integration checks, {gui["tests_run"]} Windows desktop workflow tests, strict compiler builds, sanitizers and distribution validation. Genuine captures document successful and erroneous source analysis. The implementation remains a lexical analyzer with explicit, documented language boundaries.')
    heading('14 References and Appendix')
    p('[1] WG14. N1570 Committee Draft, Programming languages - C, 12 April 2011, Sections 5.1.1.2 and 6.4.1-6.4.9. https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf',size=20)
    p('[2] Microsoft Learn. About List-View Controls; Creating Threads; High DPI Desktop Application Development on Windows. https://learn.microsoft.com/en-us/windows/win32/controls/list-view-controls-overview ; https://learn.microsoft.com/en-us/windows/win32/procthread/creating-threads ; https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows',size=20)
    p('[3] DIT University official media kit and linked dit_main.webp logo. https://www.dituniversity.edu.in/media-kits/logo',size=20)
    p('[4] Project source and executed workflow evidence. https://github.com/prxns/Lexical-Analyzer',size=20)
    sub('Demonstration and developer checks')
    code('\n'.join(['Double-click: dist\\LexicalAnalyzer.exe','Fallback: run.bat',
        'Portable CLI: dist\\lexical_analyzer.exe samples\\demo.c',
        'Developer build: build.bat',
        'CLI tests: python tests/test_lexer.py --exe dist/lexical_analyzer.exe',
        'GUI tests: python tests/test_gui.py --exe dist/LexicalAnalyzer.exe']))
    p('Source files, both samples, complete execution transcripts, screenshot originals, test records and executable/report hashes are supplied with the project. Enlarged report figures are crops of those genuine screenshots; they do not change application content.',size=20)
    sect = '''<w:sectPr><w:headerReference w:type="default" r:id="header"/><w:footerReference w:type="default" r:id="footer"/><w:titlePg/>
    <w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1440" w:bottom="1134" w:left="1440" w:header="567" w:footer="567"/>
    </w:sectPr>'''
    document = f'<w:document xmlns:w="{NS}" xmlns:r="{RNS}"><w:body>{"".join(body)}{sect}</w:body></w:document>'
    styles = f'''<w:styles xmlns:w="{NS}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:sz w:val="24"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
    <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
    <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="38"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="University"><w:name w:val="University"/><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="233B59"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:sz w:val="28"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/><w:color w:val="233B59"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:keepNext/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:pPr><w:spacing w:before="0" w:after="0" w:line="200" w:lineRule="exact"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="17"/></w:rPr></w:style>
    <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:rPr><w:i/><w:sz w:val="20"/><w:color w:val="444444"/></w:rPr></w:style></w:styles>'''
    rels = f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="styles" Type="{RNS}/styles" Target="styles.xml"/><Relationship Id="header" Type="{RNS}/header" Target="header1.xml"/><Relationship Id="footer" Type="{RNS}/footer" Target="footer1.xml"/>'
    rels += ''.join(f'<Relationship Id="image{i}" Type="{RNS}/image" Target="media/image{i}.png"/>' for i in range(1,len(images)+1)) + '</Relationships>'
    types = '''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'''
    for part, mime in [('document','document.main'),('styles','styles'),('header1','header'),('footer1','footer')]:
        types += f'<Override PartName="/word/{part}.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{mime}+xml"/>'
    types += '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>'
    output = DOCS/'Lexical_Analyzer_Report.docx'
    with ZipFile(output,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',types)
        z.writestr('_rels/.rels',f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="document" Type="{RNS}/officeDocument" Target="word/document.xml"/><Relationship Id="core" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>')
        z.writestr('docProps/core.xml','<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Design and Implementation of a Lexical Analyzer</dc:title><dc:creator>Pranshu Rawat</dc:creator><dc:subject>Compiler Design native Windows desktop application</dc:subject><cp:keywords>C11 Win32 lexical analysis</cp:keywords></cp:coreProperties>')
        z.writestr('word/document.xml',document)
        z.writestr('word/styles.xml',styles)
        z.writestr('word/_rels/document.xml.rels',rels)
        z.writestr('word/header1.xml',f'<w:hdr xmlns:w="{NS}"><w:p><w:pPr><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:sz w:val="18"/><w:color w:val="666666"/></w:rPr><w:t>DIT University  |  Compiler Design</w:t></w:r></w:p></w:hdr>')
        z.writestr('word/footer1.xml',f'<w:ftr xmlns:w="{NS}"><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:fldSimple w:instr="PAGE"><w:r><w:rPr><w:sz w:val="18"/></w:rPr><w:t>1</w:t></w:r></w:fldSimple></w:p></w:ftr>')
        for i, img in enumerate(images,1):
            z.write(img,f'word/media/image{i}.png')
    print(f'Created editable report: {output}')


if __name__ == '__main__':
    build()
