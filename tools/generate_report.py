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


def build():
    evidence = json.loads((DOCS/'test-results-local.json').read_text())
    assert evidence['successful'] and evidence['tests_run'] == 36 and len(evidence['passed']) == 36
    for name in ['test-results-windows.json', 'verified-ubuntu-latest-gcc-results.json',
                 'verified-ubuntu-latest-clang-results.json', 'sanitizer-results-results.json']:
        result = json.loads((DOCS/name).read_text())
        assert result['successful'] and result['tests_run'] == 36
    summary = json.loads((DOCS/'demo-tokens.json').read_text())['summary']
    executions = json.loads((DOCS/'execution-results.json').read_text())
    assert executions['demo']['exit_status'] == 0 and executions['errors']['exit_status'] == 1
    make_flowchart()

    # Page 1
    p('', after=240)
    image('assets/dit-logo.png', 2.0, dark_panel=True)
    p('DIT UNIVERSITY', 'University', 'center', after=360)
    p('DESIGN AND IMPLEMENTATION\nOF A LEXICAL ANALYZER', 'Title', 'center', after=300)
    p('Academic Project Report', 'Subtitle', 'center', after=180)
    p('Subject  Compiler Design', align='center', after=540)
    p('Submitted by', align='center', after=120)
    p('Pranshu Rawat', 'Heading2', 'center', after=100)
    p('SAP ID  1000021904\nSection  D', align='center', after=320)
    p('B.Tech. Computer Science and Engineering', align='center', after=140)
    p('Academic Year  2026–27', align='center', after=260)
    p('Implementation language  C11', align='center')
    page()

    # Page 2
    heading('Abstract')
    p('This project implements a hand-written lexical analyzer in standard C11. It reads a source file and classifies keywords, identifiers, integer and floating constants, strings, characters, operators and punctuators. Each token is reported with its original lexeme and one-based source position. Comments and whitespace are skipped. Malformed literals and unsupported bytes produce diagnostic rows, allowing the scan to continue where recovery is possible.')
    p(f'The implementation uses a dynamically grown input buffer and a small scanner state. It recognizes all 44 C11 keywords while deliberately limiting literal syntax and preprocessing. The demonstration produces {summary["total"]} valid tokens with no lexical errors. All 36 automated test methods passed on Windows GCC, Linux GCC and Linux Clang, and under AddressSanitizer and UndefinedBehaviorSanitizer. The downloaded Windows executable also passed the suite on the demonstration laptop.')
    sub('Table of Contents')
    contents = [('1 Introduction',3),('2 Problem Statement',3),('3 Objectives',3),('4 Scope',3),
        ('5 Theoretical Background',4),('6 System Requirements',4),('7 System Design',5),
        ('8 Algorithm and Working',6),('9 Implementation Details',6),('10 Results and Execution',7),
        ('11 Testing',9),('12 Complexity Analysis',11),('13 Limitations',11),
        ('14 Conclusion',12),('15 References',12),('16 Appendix',12)]
    table(['Section','Page'], contents, [7900,1126], font=20)
    page()

    # Page 3
    heading('1 Introduction')
    p('A compiler translates a source program into another representation through several stages. Lexical analysis is the stage that groups source characters into recognizable units. For example, the statement int total = 10; contains a keyword, an identifier, an operator, an integer constant and a punctuator. Later compiler stages reason about the arrangement and meaning of those tokens. This project implements only their recognition [1, Section 6.4].')
    p('The application accepts a source filename in a terminal and displays a token table followed by counts for each category. This makes the scanner suitable for a Compiler Design practical demonstration: the input, classification and position of each lexeme can be inspected directly. The source is analyzed as text and is never compiled or executed by the analyzer.')
    heading('2 Problem Statement')
    p('Source characters alone do not reveal the lexical role of a word or symbol. The scanner must distinguish a reserved keyword from a similarly named identifier, combine multi-character operators correctly and avoid treating comment contents as ordinary program tokens. Invalid input must be identified without corrupting source positions or overrunning buffers.')
    heading('3 Objectives')
    p(OBJECTIVE)
    p('The supporting objectives are to apply longest-match recognition, preserve source positions, report recoverable lexical errors clearly and provide reproducible evidence of correct behavior through automated tests and sample executions.')
    heading('4 Scope')
    p('The implemented subset includes ASCII identifiers, the C11 keyword set, common integer and decimal floating forms, ordinary strings and single-character constants, C operators, punctuators and digraphs. Whitespace and both forms of C comments are skipped. Preprocessor markers are tokenized but directives are not evaluated. The project does not perform parsing, semantic analysis, code generation or symbol-table construction.')
    page()

    # Page 4
    heading('5 Theoretical Background')
    table(['Term','Meaning in this implementation'], [
        ('Compiler','A translator that processes a source language; lexical analysis is one stage.'),
        ('Lexical analyzer','A scanner that partitions input into tokens and diagnoses invalid lexical forms.'),
        ('Token','A category and source span; for example, Integer at line 2, column 13.'),
        ('Lexeme','The actual source characters belonging to a token, such as 0x2A.'),
        ('Pattern','A rule describing a token family, such as [A-Za-z_][A-Za-z_0-9]*.'),
        ('Keyword','A reserved word such as int or _Atomic, recognized by exact comparison.'),
        ('Identifier','A user-defined name such as total; identifiers are case-sensitive.'),
        ('Constant or literal','A numeric, quoted string or character form recognized by the scanner.'),
        ('Operator','A symbol such as +, >= or >>=; its use is not semantically evaluated.'),
        ('Punctuator','A structural or preprocessing symbol such as ;, {, ... or ##.')
    ], [2200,6826], font=21)
    sub('Symbol recognition and maximal munch')
    p('The scanner tests multi-character symbols before their shorter prefixes. Thus >>= is one Operator, rather than >> followed by =. Keyword recognition occurs after the complete identifier span has been read, so integer is an Identifier even though it begins with int. Numeric scanning collects a candidate before validation; 123abc is diagnosed as one malformed candidate rather than two apparently valid tokens. These choices make token boundaries explicit [1, Sections 6.4 and 6.4.8].')
    heading('6 System Requirements')
    p('The application needs an operating system capable of running its compiled executable. Rebuilding requires a C11-compatible compiler and the standard C library. Automated testing requires Python 3, using only its standard library. No minimum CPU speed or memory capacity is claimed; memory use grows with source size. VS Code is an optional editor and does not itself provide GCC.')
    p('Verification used GitHub-hosted Windows GCC 15.2.0 and Linux GCC/Clang builds. The prebuilt Windows executable was then exercised locally. No local C compiler was found during inspection; rebuilding on this laptop therefore requires a separately configured toolchain. The application itself runs without Python or a compiler.')
    page()

    # Page 5
    heading('7 System Design')
    p('The command-line layer owns the source buffer, output and category counters. The scanner reads that buffer through a Lexer state and returns one borrowed Token span at a time. This keeps lexical recognition independent of table and JSON formatting. The input remains alive until all tokens have been processed.')
    image('assets/scanner-flowchart.png', 4.65)
    p('Figure 1  Actual scanner and output workflow', 'Caption', 'center')
    p('A lexical error returns TOKEN_ERROR with the opening position and a message. EOF ends the loop; the CLI prints the summary, frees the input and returns the appropriate status. Allocation, file and output failures are handled separately as execution errors.')
    page()

    # Page 6
    heading('8 Algorithm and Working')
    p('1. Validate the invocation, open the file in binary mode and read it into a growing buffer. Check allocation, read and close results.\n2. Initialize the byte offset, line and column.\n3. Skip whitespace and comments, retaining an error for an unterminated block comment.\n4. At EOF, stop; otherwise record the next opening position.\n5. Scan an identifier and perform exact keyword lookup, validate a numeric candidate, scan a quoted literal, or match a symbol longest first.\n6. Return a token or diagnostic. Print it and update counts, then request the next token.\n7. Print the summary, release the buffer and return status 0, 1 or 2.')
    sub('Pseudocode')
    code('''source = read_source(path)
lexer_init(source)
while true:
    token = lexer_next()
    if token.kind == TOKEN_EOF: break
    print token and source position
    if token.kind == TOKEN_ERROR: increment errors
    else: increment category count
print summary
free source
return errors ? 1 : 0''')
    heading('9 Implementation Details')
    table(['Function or type','Actual responsibility'], [
        ('Lexer and Token','Size-based offsets and positions; a borrowed lexeme pointer and length.'),
        ('read_source','fread with malloc/realloc; allocation growth checked against SIZE_MAX.'),
        ('advance and peek','Bounded lookahead and CRLF-aware source position updates.'),
        ('is_keyword','Exact length and byte comparison against 44 reserved words.'),
        ('scan_number and number_kind','Candidate extraction, base/exponent checks and suffix validation.'),
        ('scan_literal','Quote matching, escape checks, character length checks and recovery.'),
        ('lexer_next','Whitespace/comments, category dispatch and ordered symbol recognition.'),
        ('print_escaped','Visible control-byte escaping for safe table and valid JSON output.')
    ], [3200,5826], font=20)
    p('Tabs count as one column. A CRLF pair advances one line; CR and LF alone also start new lines. Invalid bytes consume one byte. A quoted literal stops at its closing delimiter, newline or EOF. Numeric magnitude and escape values are not converted, so range or type errors remain outside lexical analysis.')
    page()

    # Page 7
    heading('10 Results and Execution')
    p('The following source is the actual demonstration input. It covers all eight valid token categories in a short array-accumulation program. Preprocessor text is tokenized without resolving the include directive.')
    code((ROOT/'samples/demo.c').read_text())
    sub('Successful execution excerpt')
    demo = (DOCS/'demo-output.txt').read_text().splitlines()
    code('\n'.join(demo[:14]))
    p('Transcript excerpt from dist/lexical_analyzer.exe samples/demo.c. The complete 128-token table is supplied in docs/demo-output.txt and the structured equivalent in docs/demo-tokens.json.', 'Caption')
    table(['Keyword','Identifier','Integer','Float','String','Character','Operator','Punctuator'],
          [[str(summary[k]) for k in ['Keyword','Identifier','Integer','Float','String','Character','Operator','Punctuator']]],
          [1100,1250,1000,850,900,1250,1200,1476], font=18)
    p('Total tokens: 128. Lexical errors: 0. Actual exit status: 0.')
    page()

    # Page 8
    heading('10 Lexical Error Demonstration')
    sub('Lexical error demonstration')
    p('The second input deliberately contains invalid octal digits, an incomplete exponent, an invalid escape, an unclosed string, an unsupported character and an unclosed block comment. The scanner returns six diagnostic rows while preserving the positions of the valid tokens around them.')
    code((ROOT/'samples/errors.c').read_text())
    sub('Genuine execution transcript')
    error_lines = (DOCS/'errors-output.txt').read_text().splitlines()
    # Diagnostic rows are preserved verbatim, apart from line wrapping.
    code('\n'.join([error_lines[0],error_lines[1],error_lines[3]] + [line for line in error_lines if 'Error ' in line] + error_lines[-12:]), width=92)
    p('Only diagnostic rows and the summary are shown above; long rows are wrapped for readability. Complete output, including valid rows, is in docs/errors-output.txt. Actual exit status: 1.', 'Caption')
    sub('Recovery and interpretation')
    p('A malformed number is consumed as one candidate. An invalid escape marks its entire quoted literal as an Error. An unclosed quoted literal stops before the newline, allowing the next line to be analyzed. The unclosed block comment consumes the remaining input and produces one final diagnostic. Messages identify the opening position of the affected span.')
    p('The first error begins at line 2, column 13; the unterminated block comment begins at line 7, column 1. An empty file instead returns status 0 with all counts zero. A missing file or incorrect invocation returns status 2 with an explanatory message on standard error.')
    page()

    cases = [
        ('All C11 keywords','44 exact keyword matches','44 Keyword rows'),
        ('Identifier boundaries','Case-sensitive full names','All names matched'),
        ('Integer forms','Decimal, octal, hex, suffixes','All forms matched'),
        ('Floating forms','Fractions, exponents, suffixes','All forms matched'),
        ('String escapes','Valid strings and escapes','Exact lexemes matched'),
        ('Character escapes','One character or escape','Exact lexemes matched'),
        ('All operators','One expected token per operator','All operators matched'),
        ('Adjacent operators','Longest matching symbols','Exact sequence matched'),
        ('Punctuators and digraphs','Correct punctuator category','All symbols matched'),
        ('Whitespace and comments','Skip all trivia','Only 3 program tokens'),
        ('Markers inside literals','Preserve literal contents','Both literals matched'),
        ('Multiline positions','Exact line and column values','7 positions matched'),
        ('CRLF, CR and LF','Each newline convention','Lines 1 through 4'),
        ('Empty source','No tokens and no errors','Zero counts'),
        ('Whitespace only','No tokens and no errors','Zero counts'),
        ('Comment only and EOF','No ordinary tokens','Zero tokens'),
        ('Invalid bytes and NUL','Five errors at columns 1–5','5 errors'),
        ('Unterminated strings','Diagnostic at opening quote','Expected messages'),
        ('Unterminated character','Character diagnostic','Expected message'),
        ('Unterminated comment','Error at line 2 column 2','Position matched'),
        ('Malformed numerics','Reject entire candidates','All cases rejected'),
        ('Invalid escape forms','Error for each bad literal','All cases rejected'),
        ('Character lengths','Reject empty or multi-unit','One error per input'),
        ('Encoded literal prefixes','Explicit subset diagnostic','Whole spans rejected'),
        ('Error recovery','Resume on following lines','2 errors, later tokens'),
        ('Single symbols at EOF','No lost final token','All final tokens read'),
        ('Large lexemes','Preserve 100,000-byte name','Full lexemes retained'),
        ('Large source','5,000 repeated source lines','25,000 tokens'),
        ('Valid demo fixture','Every valid category present','128 tokens, 0 errors'),
        ('Error fixture','Six intentional errors','6 errors'),
        ('CLI and missing file','Status 2 and stderr; help 0','Statuses matched'),
        ('Default table output','Table, summary and success','Output markers found'),
        ('120 random byte inputs','Terminate; ordered positions','All trials completed'),
        ('Preprocessor markers','No directive evaluation','Exact token sequence'),
        ('Raw NUL in literal','Reject entire literal','1 error'),
        ('Leading signs','Separate operator tokens','4 expected tokens')
    ]
    # Pages 9 and 10
    for block in range(2):
        heading('11 Testing' + (' Continued' if block else ''))
        if block == 0:
            p('The Python standard-library runner executes the C binary as a subprocess. Assertions compare exact lexemes, categories, positions, summaries and exit codes. Every case below was executed successfully; subcases are included within the 36 test methods.')
        else:
            p('The remaining cases exercise error recovery, boundaries, larger inputs and command-line behavior. The random-input check uses a fixed seed, making failures reproducible; it verifies termination and ordered nonempty spans rather than full C conformance.')
        rows = [[f'T{i+1:02}', *cases[i], 'Pass'] for i in range(block*18, (block+1)*18)]
        table(['ID','Input or condition','Expected result','Actual result','Status'], rows,
              [580,2350,2750,2676,670], font=18)
        if block == 0:
            p('Table 1  Executed regression cases T01 to T18', 'Caption')
        else:
            p('Table 2  Executed regression cases T19 to T36', 'Caption')
            sub('Build and memory checks')
            p('Strict builds used -std=c11 -Wall -Wextra -Wpedantic -Werror -O2 and completed without warnings. All 36 tests passed in each Windows GCC, Linux GCC and Linux Clang job. A separate Clang job ran the same suite with -fsanitize=address,undefined and reported no sanitizer failure. The Windows binary also passed all 36 tests locally. These checks cover exercised paths; they are not a proof that every possible input is defect-free.')
        page()

    # Page 11
    heading('12 Complexity Analysis')
    p('Let n be the number of input bytes. File loading grows its buffer geometrically, giving O(n) total copying and O(n) memory. The scan moves forward without rewinding. Keyword lookup examines a fixed set of 44 words and symbol matching examines a fixed table of short symbols. Numeric validation may reread its own candidate once; each candidate is disjoint. Total scanning time is therefore O(n) for this fixed language subset.')
    p('Printing is proportional to the number of bytes emitted. With an explicit output-size variable m, total processing is O(n + m); escaped bytes may occupy several display characters. The scanner uses O(1) auxiliary state and borrowed token spans. The CLI retains the full source, so application working memory is O(n). Tokens are printed as they are returned; an O(n) token collection is not retained by the application. The Python test runner intentionally does collect JSON results for assertions.')
    heading('13 Limitations')
    p('The program is a documented lexical subset rather than a standards-conforming C front end. Identifiers are limited to ASCII letters, digits and underscores. Non-ASCII bytes, a UTF-8 byte-order mark and NUL are unsupported outside comments. Comments are opaque byte sequences and block comments do not nest.')
    p('Integer syntax supports decimal, octal and hexadecimal forms with common U and L suffixes. Floating syntax is decimal, with fractions or exponents and an optional floating suffix. Hexadecimal floating forms, binary literals, C23 separators and numeric range checking are excluded. A leading sign remains an Operator.')
    p('Only ordinary strings and character constants are supported. A character constant must contain exactly one character or escape. Common simple escapes, up to three octal digits and nonempty hexadecimal escapes are recognized syntactically; their values are not converted or range-checked. Wide and encoded prefixes and universal character names are diagnosed. Adjacent strings are not concatenated.')
    p('Preprocessing is not performed. The symbols # and ## and digraph equivalents are returned as Punctuator tokens. Header names receive no special category, and include files are not opened. Trigraph translation and backslash-newline splicing are excluded. These decisions are documented so that tokenization is not confused with the full C translation phases [1, Section 5.1.1.2].')
    p('Diagnostics report the opening location of a bad span, with one primary message per literal. After malformed quotes, later delimiters may cause additional diagnostic rows. The scanner does not check balanced delimiters, declaration validity, identifier meaning or type compatibility. Such checks belong to subsequent compiler stages.')
    page()

    # Page 12
    heading('14 Conclusion')
    p('The project meets its token-identification objective with a readable C11 implementation and a direct terminal interface. The valid demonstration produces 128 tokens across all eight supported categories; the invalid demonstration produces six lexical diagnostics at the expected source positions. The program is organized into a scanner module and a command-line layer, with no runtime framework or scanner generator.')
    p('Correctness was checked through 36 automated methods across three compiler/platform builds, a sanitizer build and local Windows execution. The report, README and saved transcripts describe the implemented behavior and its boundaries. The remaining local setup requirement for rebuilding is a working C compiler; the supplied verified Windows executable can be demonstrated directly.')
    heading('15 References')
    p('[1] ISO/IEC JTC1/SC22/WG14. N1570 Committee Draft, Programming languages — C, 12 April 2011. Sections 5.1.1.2 and 6.4.1–6.4.9. https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf', size=21)
    p('[2] DIT University. Official media kit, Logos, and linked dit_main.webp asset. Accessed 15 November 2026. https://www.dituniversity.edu.in/media-kits/logo', size=21)
    p('[3] Lexical Analyzer project repository. Implementation and reproducible checks. https://github.com/prxns/Lexical-Analyzer', size=21)
    heading('16 Appendix')
    sub('Demonstration and test commands')
    code('''dist\\lexical_analyzer.exe samples\\demo.c
dist\\lexical_analyzer.exe samples\\errors.c
python tests/test_lexer.py --exe dist/lexical_analyzer.exe
build.bat
run_demo.bat''')
    sub('Token data structure excerpt')
    code('''typedef struct {
    TokenKind kind;
    const unsigned char *lexeme;
    size_t length, line, column;
    const char *message;
} Token;''')
    p('Evidence provenance: GitHub Actions run 43725899657 tested source commit eed408193de72970187dc0423cca1973d3b046a7. JSON test records and full transcripts are supplied in docs/. The Windows executable SHA-256 is recorded in docs/execution-results.json.', size=20)

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
    types += '</Types>'
    output = DOCS/'Lexical_Analyzer_Report.docx'
    with ZipFile(output,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml',types)
        z.writestr('_rels/.rels',f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="document" Type="{RNS}/officeDocument" Target="word/document.xml"/></Relationships>')
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
