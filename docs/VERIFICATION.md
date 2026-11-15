# Verification record

The scanner source at commit `eed408193de72970187dc0423cca1973d3b046a7`
was compiled and exercised in [GitHub Actions run 43725899657](https://github.com/prxns/Lexical-Analyzer/actions/runs/43725899657).

| Environment | Build and executed checks | Result |
|---|---|---|
| Windows hosted runner, GCC 15.2.0 | Strict C11 compilation; 36 regression methods | Passed |
| Linux hosted runner, GCC | Strict C11 compilation; 36 regression methods | Passed |
| Linux hosted runner, Clang | Strict C11 compilation; 36 regression methods | Passed |
| Linux hosted runner, Clang sanitizers | AddressSanitizer and UndefinedBehaviorSanitizer; 36 methods | Passed |
| Local Windows laptop | Downloaded Windows executable; 36 regression methods | Passed |

Compilation used `-std=c11 -Wall -Wextra -Wpedantic -Werror -O2`.
The instrumented build used `-g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer`.
No compiler warnings or sanitizer failures were reported by those runs.

The tests include multiple subcases per method and 120 deterministic random-byte
inputs. They test the documented subset rather than full C language compliance.
Memory allocation and cleanup were also reviewed in `read_source` and `main`:
the input buffer grows with overflow checks, realloc failure retains ownership
until cleanup, and returned tokens borrow the input without additional allocation.

## Actual demonstrations

| Input | Valid tokens | Lexical errors | Exit code |
|---|---:|---:|---:|
| `samples/demo.c` | 128 | 0 | 0 |
| `samples/errors.c` | 16 | 6 | 1 |

See the complete `demo-output.txt`, `errors-output.txt` and `demo-tokens.json`.
`execution-results.json` records the executable SHA-256 and observed statuses.
The supplied `dist/lexical_analyzer.exe` is the verified Windows runner binary.

## Academic report reproduction

`tools/generate_report.py` builds the editable DOCX from these executed test
records, sample source files and transcripts. Its optional authoring dependency
is Pillow for the flowchart; it uses an available Windows Calibri font. The
application and its tests do not depend on Pillow.

`tools/export_report.py` extracts the DOCX paragraphs, tables and images into
temporary paginated HTML, preserving the report content and page divisions, and
prints that layout with an existing Chromium browser. It checks content height
before export. It does not install dependencies, access a personal browser
profile, or change the DOCX. This provides a PDF export when native Word
automation is unavailable. The final visual review uses the exported PDF.

The report includes genuine execution transcripts in place of terminal
screenshots. No sample formatting reference was present in the project folder.
University branding comes from the official media kit; its source is documented
in `assets/README.md`. No faculty details, certification or signatures are invented.

## Local build prerequisite

No usable local C compiler was found during inspection. The scripts report this
condition clearly. A C11-compatible GCC toolchain on PATH is needed to rebuild;
the verified Windows executable can be demonstrated without that toolchain.

## Report export verification

The final report was exported and all 12 PDF pages rendered in [Actions run 43730041629](https://github.com/prxns/Lexical-Analyzer/actions/runs/43730041629). The page count matches the 12 logical DOCX page divisions. Every rendered page was visually reviewed, including the cover branding, contents, flowchart, execution transcripts and test tables. The DOCX package XML and relationships were parsed successfully.
