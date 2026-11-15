# Desktop upgrade verification

The native application reuses the scanner merged by PR #1. Its source of truth is
still `src/lexer.c`, reached through `analysis_scan` in the desktop result model.
No tokenization is implemented in Python or in a separate UI engine.

## Executed checks

[GitHub Actions run 43757085737](https://github.com/prxns/Lexical-Analyzer/actions/runs/43757085737)
tested source commit `bd834b5e0c7a98514c39f9490eb61c830e1ac1d1`.

| Check | Actual outcome |
|---|---|
| Original scanner suite | All 36 methods passed on Windows GCC, Linux GCC and Linux Clang |
| Shared C analysis integration | Passed on all three compiler/platform builds |
| Sanitizers | Scanner suite and C analysis integration passed under AddressSanitizer and UndefinedBehaviorSanitizer |
| Native Windows GUI workflow suite | All 13 methods passed against `dist/LexicalAnalyzer.exe` |
| Distribution inspection | x64 Windows GUI subsystem, per-monitor DPI manifest, system DLLs only and packaged samples verified |
| Windows build/demo scripts | Executed successfully |

All builds use C11 with `-Wall -Wextra -Wpedantic -Werror`. The original scanner
and command-line interface are preserved. Actual C integration output is in
`analysis-test-output.txt`.

## Native workflows actually exercised

The GUI suite starts its own packaged executable and targets only that process's
windows. Expected categories and aggregates come from the real CLI. It exercised
launch, controls, valid analysis, both sample buttons, diagnostics, search/category
intersection, clearing results, empty input, saving source, opening through the
native file dialog, exporting CSV through the native save dialog, editing during
analysis, cancellation, resizing and double-click source navigation.

`gui-test-results.json` records every executed method and the tested executable's
SHA-256. `gui-export-results.csv` is the actual 128-row exported file, parsed and
checked by the suite.

| Input | Valid tokens | Errors | Desktop constants |
|---|---:|---:|---:|
| Valid demo | 128 | 0 | 18 |
| Error sample | 16 | 6 | 0 |
| Empty editor | 0 | 0 | 0 |

## Screenshot provenance

Files in `screenshots/` are genuine Windows PrintWindow captures of the running
native executable during the GUI tests. They are lossless PNGs, not mockups or
re-created screens. Enlarged report figures crop those same pixels without
altering results. A source caption may identify the temporary test copy named
`source with spaces.c`.

`gui-verification.json` identifies the run, commit and binary hash. Local
interactive launch approval timed out; no claim is made that this automation
completed the GUI launch on the user's laptop. Actual native launch and workflow
verification took place on the Windows runner. The local CLI and C analysis
executables were also run successfully.

## Reports

The DOCX is generated from executed test records and real screenshots. The PDF
uses the DOCX paragraphs, tables and image data. `tools/verify_documents.py`
checks ZIP CRCs, XML, relationships, image CRCs, student details, PDF structure
and matching page counts. Every PDF page is rendered for visual review. These
documentation tools are not application dependencies.

The upgraded 14-page DOCX and PDF passed the integrity checks in
[run 43758736072](https://github.com/prxns/Lexical-Analyzer/actions/runs/43758736072).
All 14 rendered PDF pages were visually inspected: the cover branding, student
details, architecture, genuine screenshots, tables and references are readable,
with no clipped content or extra blank pages. Final executable and document
SHA-256 values are recorded in `deliverable-sha256.json`.

## Documented boundaries

Desktop limits are 4 MiB of UTF-8 source and 500,000 result rows. The editor uses
CRLF snapshots and removes a UTF-8 BOM when opening a text file. Lexical rules
remain the ASCII C11 subset. The scanner is not a parser or full C front end;
numeric range, declarations, types and meaning remain outside scope. DPI support
is implemented; exhaustive multi-monitor hardware testing is not claimed.
