# Design and Implementation of a Lexical Analyzer

**Compiler Design | C11 | DIT University | Academic year 2026–27**  
Pranshu Rawat · SAP ID 1000021904 · Section D  
B.Tech. Computer Science and Engineering

## How to Run the Application

1. Open the **dist** folder.
2. Double-click **LexicalAnalyzer.exe**. It opens the desktop application directly, without a console.
3. Click **Load Sample**, then **ANALYZE CODE**.
4. Inspect the statistics, token table and diagnostics. Try **Error Sample** to demonstrate lexical errors.

No installation, compiler, Python, Node.js, server, or VS Code is needed to run the
packaged application. Use Windows 10 version 1703 or newer / Windows 11 x64.
Keep the `dist/samples` folder beside the executable. If preferred, double-click
the project's `run.bat` or `dist/run.bat` fallback.

## Desktop workflow

- **Open C File** opens an ASCII/UTF-8 source file. **Save File** saves UTF-8 text.
  A sample is opened as a copy, so Save asks for a new filename.
- The editor has line numbers, scrolling, undo, selection, monospaced text and
  unsaved-change prompts before replacing or closing edits.
- **Analyze Code** calls the existing C scanner through `analysis_scan` on a worker
  thread. The button becomes **Cancel Analysis** while it runs.
- The seven cards show actual counts. Constants combine integer, float, string
  and character categories. Separators count C punctuators.
- Search is case-insensitive ASCII substring matching on lexemes. Category and
  search filters intersect; they change the table, not aggregate counts.
- Double-click a token or diagnostic to select its source span in the editor.
- **Export Results** writes every result row and diagnostic to CSV, including
  rows hidden by the filter. **Clear Results** retains the source code.
- Editing invalidates old results. An older analysis snapshot cannot replace
  the latest editor contents with stale results.

Shortcuts: **Ctrl+O** open, **Ctrl+S** save, **Ctrl+Enter** analyze/cancel,
**Ctrl+F** token search, **Ctrl+E** export. Tab inserts a tab in the editor.

Desktop limits: **4 MiB of UTF-8 source** and **500,000 result rows**. The CLI
remains available for larger inputs. Opening a UTF-8 BOM removes that encoding
marker; saved/editor snapshots use CRLF line endings. Lexical recognition remains
the documented ASCII C11 subset below.

## Objective

To design and implement a program that reads a source code and identifies tokens such as keywords, identifiers, constants, and operators.

## Introduction and technology

This hand-written C scanner reads a source file, skips comments and whitespace,
and reports each lexeme with its category and one-based line and column. It uses
longest-match recognition and recovers from lexical errors so later tokens can
still be inspected. It is a lexical analyzer, not a parser or a complete compiler.

The scanner and analysis model use the C11 standard library. The desktop interface
uses Win32, RichEdit and Windows common controls directly in C. Python is used only
for tests and documentation. Neither executable needs Python. No Lex/Flex,
external GUI framework, web server or database is involved.

## Project files

| Path | Purpose |
|---|---|
| `src/main.c` | File loading, CLI, escaped token output, summary and exit status |
| `src/lexer.c` | Character scanning, keyword lookup, literal validation and recovery |
| `src/gui.c` | Win32 window, editor, background worker and result views |
| `src/analysis.c`, `include/analysis.h` | Shared C result storage, counts, filtering and CSV |
| `include/lexer.h` | Lexer state, borrowed token spans and public API |
| `samples/demo.c` | Short valid demonstration covering every category |
| `samples/errors.c` | Intentionally invalid demonstration input |
| `tests/test_lexer.py` | Standard-library black-box regression and randomized tests |
| `tests/test_analysis.c` | Portable shared-analysis integration checks |
| `tests/test_gui.py` | Real packaged Windows GUI workflow tests |
| `tests/test_distribution.py` | PE subsystem, DPI manifest, system DLL and sample-package checks |
| `resources/` | Application icon/version resource and high-DPI manifest |
| `dist/LexicalAnalyzer.exe` | Ready-to-run native desktop application |
| `.github/workflows/ci.yml` | GCC/Clang builds and sanitizer checks |
| `docs/` | Academic reports, execution transcripts and verification evidence |
| `build.bat`, `run_demo.bat` | Windows build and demonstration scripts |
| `Makefile` | POSIX build, test and demo targets |

## Features and categories

| Category | Recognition |
|---|---|
| Keyword | All 44 C11 keywords, with case-sensitive exact matching |
| Identifier | ASCII `[A-Za-z_][A-Za-z_0-9]*` |
| Integer | Decimal, octal and hexadecimal; valid U/u, L/l, LL/ll suffix combinations |
| Float | Decimal fractions and/or decimal exponents; optional F/f/L/l suffix |
| String | Ordinary quoted strings, including empty strings and supported escapes |
| Character | Exactly one ordinary character or supported escape |
| Operator | Arithmetic, comparison, logical, assignment, bitwise and conditional symbols |
| Punctuator | Brackets, braces, parentheses, comma, semicolon, dot, ellipsis, `#`, `##` and digraphs |
| Error | Invalid byte, malformed/unsupported literal or unterminated literal/comment |

Operators are matched longest first, including `<<=`, `>>=`, `->`, `++`, `--`,
`&&`, `||`, `&=`, `|=`, `^=`, and the usual comparison and assignment operators.
Comments (`//` and `/* ... */`) and whitespace are skipped. CRLF counts as one
newline; LF and standalone CR also start a new line. A tab advances one source
column, not to a display tab stop. Positions are byte positions in the original
file. Tokens borrow input spans; they are not truncated or copied into fixed buffers.

## Windows and VS Code

This section is only for developers rebuilding the project. Running the packaged
desktop application requires none of these tools.

Prerequisite: **C11-compatible MinGW GCC and windres on PATH**. VS Code and its
C/C++ extension alone do not supply a compiler. No software is installed by these
scripts. Check the prerequisite in a new VS Code terminal:

```powershell
gcc --version
```

Open this project folder in VS Code. From the terminal:

```powershell
.\build.bat
.\build\lexical_analyzer.exe samples\demo.c
.\build\lexical_analyzer.exe samples\errors.c
```

Or run `.\run_demo.bat` to build and demonstrate in one step. The build script
changes to its own directory, so launching from a path containing spaces works.
The error sample intentionally returns exit code 1.

Equivalent CLI-only compiler command:

```powershell
gcc -std=c11 -Wall -Wextra -Wpedantic -Werror -O2 -Iinclude src/main.c src/lexer.c -o build/lexical_analyzer.exe
```

Create `build` first if running the command directly. A prebuilt executable, when
included with the verified deliverables, can be run without a compiler.

## Linux and macOS

With GCC or Clang and Make already available:

```sh
make
make demo
make test
# Clang alternative
make clean
make CC=clang
```

## Interface

```text
lexical_analyzer [--json] <source-file>
lexical_analyzer --help
```

The default interface prints a token table and per-category summary. `--json`
exposes the same tokens and diagnostic messages for reproducible automated tests.
String lexemes retain quotes and escapes. Control bytes, including terminal
escape sequences, are printed safely as visible escapes. No source is executed.

| Exit status | Meaning |
|---|---|
| 0 | Scanning completed without lexical errors, or help was displayed |
| 1 | One or more lexical errors were found |
| 2 | Invalid invocation, unreadable/missing source, allocation or output failure |

An empty file produces an empty token table and zero counts. Errors include their
opening line and column and occupy numbered Error rows; summary `total` counts
valid tokens only, while `errors` counts diagnostic rows. Newline-terminated
strings recover at the newline. Invalid numbers consume the entire candidate.

## Tests and demonstration evidence

Build first, then run all 36 test methods (including parameterized edge cases and
120 deterministic randomized byte inputs):

```powershell
python tests/test_lexer.py --exe build/lexical_analyzer.exe --report build/test-results.json
```

On POSIX, `make test` runs the suite. Tests verify categories, exact lexemes,
positions, all operators, numeric/escape errors, comment handling, EOF, recovery,
large lexemes, large files, CLI statuses, JSON consistency and the sample inputs.
CI additionally runs the same suite under AddressSanitizer and
UndefinedBehaviorSanitizer. The workflow uploads executables and actual transcripts.
Verified results, genuine screenshots and sample output are recorded in `docs/`.

The new C analysis-model checks run with `make test` on POSIX. On Windows, after
building, the complete native workflow and distribution checks can be run with:

```powershell
python tests/test_gui.py --exe dist/LexicalAnalyzer.exe --cli dist/lexical_analyzer.exe
python tests/test_distribution.py
```

The desktop suite launches its own real application process. It checks the
controls and compares visible counts against the actual CLI, exercises native
file dialogs and exports, and captures genuine screenshots. Python implements
only test automation; it never tokenizes source code for the desktop.

The main sample is a short array-accumulation program with decimal, octal,
hexadecimal, floating, string and character examples; it uses a loop, conditional
operators and formatted output. View its complete source in `samples/demo.c`.

## Demonstration result

The supplied sample program is:

```c
#include <stdio.h>

/* A small program for the Compiler Design demonstration. */
int main(void) {
    int values[3] = {10, 075, 0x2A};
    unsigned int limit = 25U;
    double scale = .5, epsilon = 2e-3;
    char grade = 'A', newline = '\n';
    const char *message = "Total:\t";
    int total = 0;
    // Accumulate values and exercise longest-match operators.
    for (int i = 0; i < 3; i++) {
        total += values[i];
    }
    if (total >= 10 && total != 0) {
        printf("%s%.2f %c%c", message, total * scale + epsilon, grade, newline);
    }
    return total > (int)limit ? 0 : 1;
}
```

Actual output excerpt from the verified Windows executable:

```text
Lexical Analyzer | C11 subset
Source: samples/demo.c

No.    Lexeme                    Category      Line   Column
1      #                         Punctuator    1      1
2      include                   Identifier    1      2
3      <                         Operator      1      10
4      stdio                     Identifier    1      11
5      .                         Punctuator    1      16
6      h                         Identifier    1      17
7      >                         Operator      1      18
8      int                       Keyword       4      1
...
Token summary
  Keyword       15
  Identifier    29
  Integer       12
  Float         2
  String        2
  Character     2
  Operator      23
  Punctuator    43
Total tokens: 128
Lexical errors: 0
```

## Supported subset and limitations

- The input is ASCII C-like source. Non-ASCII bytes and embedded NUL are rejected
  outside comments; comments are opaque byte sequences. An optional UTF-8 BOM is
  not silently discarded. Universal character names are unsupported.
- All C11 keywords are recognized, but this does **not** imply full C11 compliance.
- Wide/encoded literal prefixes (`L`, `u`, `U`, `u8`) are diagnosed. Adjacent ordinary
  strings remain separate tokens. Multi-character character constants are rejected.
- Escapes: `\'`, `\"`, `\?`, `\\`, `\a`, `\b`, `\f`, `\n`, `\r`, `\t`, `\v`,
  one-to-three octal digits, and `\x` followed by one or more hex digits. Escape
  values and numeric magnitude are not converted or range-checked.
- Hexadecimal floats, binary integers, C23 literals and digit separators are not
  supported. A leading sign is an operator. Numeric candidates follow a
  preprocessing-number-like longest span, so `123abc` and `1.2.3` are single errors.
- `#`, `##` and their digraphs are punctuators. No macro expansion, conditional
  preprocessing, header-name token, include resolution, or directive evaluation
  occurs. For example `<stdio.h>` is split into ordinary tokens.
- Trigraph translation and backslash-newline splicing are not performed. Block
  comments do not nest. Escape errors are reported once per affected literal;
  after malformed input, later quote characters may produce additional errors.
- The scanner does not validate syntax, balanced delimiters, declarations, types,
  undefined variables or program meaning. It does not build a symbol table.
- Input is read into dynamically grown memory. Working space is O(n), plus the
  output handled by the consumer; the scanner itself uses constant extra space.

## References

- WG14, *N1570 Committee Draft, Programming languages — C*, 12 April 2011,
  especially 6.4.1–6.4.9: https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf
- Official project repository: https://github.com/prxns/Lexical-Analyzer
