#define UNICODE
#define _UNICODE
#define _WIN32_WINNT 0x0A00
#define WINVER 0x0A00
#define _WIN32_IE 0x0600
#include <windows.h>
#include <windowsx.h>
#include <commctrl.h>
#include <commdlg.h>
#include <richedit.h>
#include <dwmapi.h>
#include <uxtheme.h>
#include <shellapi.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
#include "analysis.h"

#define APP_CLASS L"LexicalAnalyzer.Native.C11"
#define SOURCE_LIMIT (4u * 1024u * 1024u)
#define WM_ANALYSIS_DONE (WM_APP + 1)
#define WM_EDITOR_SCROLL (WM_APP + 2)
#define FILTER_TIMER 1
#define ID_EDITOR 100
#define ID_OPEN 110
#define ID_SAVE 111
#define ID_SAMPLE 112
#define ID_ERRORS 113
#define ID_CLEAR 114
#define ID_ANALYZE 115
#define ID_CLEAR_RESULTS 116
#define ID_EXPORT 117
#define ID_SEARCH 120
#define ID_FILTER 121
#define ID_TOKENS 130
#define ID_DIAGNOSTICS 131
#define ID_STATUS 140
#define ID_STAT_BASE 200

#define BG RGB(13, 18, 27)
#define PANEL RGB(21, 29, 42)
#define EDIT_BG RGB(16, 23, 34)
#define BORDER RGB(43, 56, 75)
#define TEXT_COLOR RGB(225, 233, 244)
#define MUTED RGB(146, 163, 186)
#define ACCENT RGB(91, 214, 183)
#define BLUE RGB(132, 177, 255)
#define AMBER RGB(237, 196, 126)
#define RED RGB(255, 141, 157)
#define COUNT_OF(a) (sizeof(a) / sizeof((a)[0]))

typedef struct {
    HWND window;
    unsigned char *source;
    size_t length;
    unsigned long revision;
    volatile LONG cancelled;
    Analysis result;
    AnalysisStatus status;
} ScanJob;

static HINSTANCE app_instance;
static HWND main_window, editor, gutter, token_list, diagnostic_list, search_box, category_box;
static HWND buttons[8], values[7], labels[7], footer, badge, token_empty, diagnostic_empty;
static HFONT font_body, font_small, font_title, font_code, font_number, font_semibold;
static HBRUSH brush_bg, brush_panel, brush_input;
static HIMAGELIST row_images;
static HMODULE rich_edit_module;
static HANDLE worker;
static ScanJob *job;
static Analysis results;
static size_t *visible_rows, visible_count, *error_rows, error_count;
static int has_results, dirty, suppress_changes, closing, current_dpi = 96;
static unsigned long source_revision;
static wchar_t file_path[32768], file_name[512] = L"Untitled.c";
static wchar_t status_text[512] = L"Ready - open a C file, load a sample, or start writing code.";
static RECT source_panel, output_panel, diagnostics_panel;
static int body_top;

static int scaled(int value) { return MulDiv(value, current_dpi, 96); }
static int maximum(int a, int b) { return a > b ? a : b; }
static int minimum(int a, int b) { return a < b ? a : b; }
static void update_state(void);
static void apply_filter(void);
static void layout_window(void);
static void begin_analysis(void);
static int save_source(void);

static void fill(HDC dc, const RECT *rect, COLORREF color)
{
    HBRUSH b = CreateSolidBrush(color);
    FillRect(dc, rect, b); DeleteObject(b);
}

static void line(HDC dc, int x1, int y1, int x2, int y2, COLORREF color)
{
    HPEN pen = CreatePen(PS_SOLID, 1, color);
    HGDIOBJ old = SelectObject(dc, pen);
    MoveToEx(dc, x1, y1, NULL); LineTo(dc, x2, y2);
    SelectObject(dc, old); DeleteObject(pen);
}

static void rounded(HDC dc, RECT rect, COLORREF color, COLORREF edge, int radius)
{
    HBRUSH b = CreateSolidBrush(color);
    HPEN pen = CreatePen(PS_SOLID, 1, edge);
    HGDIOBJ old_b = SelectObject(dc, b), old_p = SelectObject(dc, pen);
    RoundRect(dc, rect.left, rect.top, rect.right, rect.bottom, radius, radius);
    SelectObject(dc, old_b); SelectObject(dc, old_p);
    DeleteObject(b); DeleteObject(pen);
}

static void text(HDC dc, RECT rect, const wchar_t *value, HFONT font, COLORREF color, UINT flags)
{
    HGDIOBJ old = SelectObject(dc, font);
    SetBkMode(dc, TRANSPARENT); SetTextColor(dc, color);
    DrawTextW(dc, value, -1, &rect, flags);
    SelectObject(dc, old);
}

static void set_status(const wchar_t *value)
{
    lstrcpynW(status_text, value, (int)COUNT_OF(status_text));
    SetWindowTextW(footer, status_text);
    InvalidateRect(main_window, NULL, FALSE);
}

static void show_error(const wchar_t *message)
{
    MessageBoxW(main_window, message, L"Lexical Analyzer", MB_OK | MB_ICONERROR);
}

static const wchar_t *base_name(const wchar_t *path)
{
    const wchar_t *a = wcsrchr(path, L'\\'), *b = wcsrchr(path, L'/');
    const wchar_t *last = a;
    if (b != NULL && (a == NULL || b > a)) last = b;
    return last ? last + 1 : path;
}

static void clear_result_data(void)
{
    ListView_SetItemCountEx(token_list, 0, 0);
    ListView_SetItemCountEx(diagnostic_list, 0, 0);
    free(visible_rows); visible_rows = NULL; visible_count = 0;
    free(error_rows); error_rows = NULL; error_count = 0;
    analysis_free(&results); has_results = 0;
}

static void source_changed(void)
{
    if (suppress_changes) return;
    dirty = 1; ++source_revision;
    if (job != NULL) InterlockedExchange(&job->cancelled, 1);
    clear_result_data();
    set_status(L"Source changed - analyze again to refresh the results.");
    update_state(); InvalidateRect(gutter, NULL, FALSE);
}

static unsigned char *editor_source(size_t *length)
{
    GETTEXTLENGTHEX length_info = {GTL_USECRLF | GTL_NUMCHARS, 1200};
    GETTEXTEX get_text;
    LRESULT chars = SendMessageW(editor, EM_GETTEXTLENGTHEX, (WPARAM)&length_info, 0);
    wchar_t *wide;
    unsigned char *bytes;
    int needed;
    if (chars < 0 || (size_t)chars > SOURCE_LIMIT) {
        show_error(L"The desktop editor supports up to 4 MiB of UTF-8 source. Use the CLI for larger inputs.");
        return NULL;
    }
    wide = malloc(((size_t)chars + 1) * sizeof *wide);
    if (wide == NULL) { show_error(L"Not enough memory to read the editor."); return NULL; }
    memset(&get_text, 0, sizeof get_text);
    get_text.cb = (DWORD)(((size_t)chars + 1) * sizeof *wide);
    get_text.flags = GT_USECRLF; get_text.codepage = 1200;
    chars = SendMessageW(editor, EM_GETTEXTEX, (WPARAM)&get_text, (LPARAM)wide);
    needed = chars ? WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, (int)chars, NULL, 0, NULL, NULL) : 0;
    if ((chars && !needed) || needed > (int)SOURCE_LIMIT) {
        free(wide); show_error(L"The source is too large or contains invalid Unicode text."); return NULL;
    }
    bytes = malloc((size_t)needed + 1);
    if (bytes == NULL) { free(wide); show_error(L"Not enough memory to encode the source."); return NULL; }
    if (needed) WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, wide, (int)chars, (char *)bytes, needed, NULL, NULL);
    bytes[needed] = 0; *length = (size_t)needed; free(wide);
    return bytes;
}

static int confirm_discard(void)
{
    int answer;
    if (!dirty) return 1;
    answer = MessageBoxW(main_window, L"Save your source changes before continuing?", L"Unsaved source code",
                         MB_YESNOCANCEL | MB_ICONQUESTION);
    if (answer == IDCANCEL) return 0;
    return answer != IDYES || save_source();
}

static int file_dialog(wchar_t *path, int saving, int csv)
{
    OPENFILENAMEW dialog;
    memset(&dialog, 0, sizeof dialog);
    dialog.lStructSize = sizeof dialog; dialog.hwndOwner = main_window;
    dialog.lpstrFile = path; dialog.nMaxFile = 32768;
    dialog.lpstrFilter = csv ? L"CSV results (*.csv)\0*.csv\0\0" : L"C source files (*.c)\0*.c\0All files (*.*)\0*.*\0\0";
    dialog.lpstrDefExt = csv ? L"csv" : L"c";
    dialog.lpstrTitle = csv ? L"Export Analysis Results" : (saving ? L"Save C Source" : L"Open C Source");
    dialog.Flags = OFN_EXPLORER | OFN_NOCHANGEDIR | OFN_PATHMUSTEXIST |
                   (saving ? OFN_OVERWRITEPROMPT : OFN_FILEMUSTEXIST);
    if (saving ? GetSaveFileNameW(&dialog) : GetOpenFileNameW(&dialog)) return 1;
    if (CommDlgExtendedError()) show_error(L"The file dialog could not be opened.");
    return 0;
}

static void install_source(const wchar_t *wide, const wchar_t *path, const wchar_t *name)
{
    if (job != NULL) InterlockedExchange(&job->cancelled, 1);
    clear_result_data();
    suppress_changes = 1; SetWindowTextW(editor, wide); suppress_changes = 0;
    SendMessageW(editor, EM_EMPTYUNDOBUFFER, 0, 0);
    lstrcpynW(file_path, path, (int)COUNT_OF(file_path));
    lstrcpynW(file_name, name, (int)COUNT_OF(file_name));
    dirty = 0; ++source_revision;
    set_status(L"Source loaded - click Analyze Code or press Ctrl+Enter.");
    update_state(); InvalidateRect(gutter, NULL, FALSE); SetFocus(editor);
}

static int load_source(const wchar_t *path, int sample)
{
    HANDLE file;
    LARGE_INTEGER size;
    DWORD read_count;
    unsigned char *bytes;
    wchar_t *wide;
    size_t skip = 0;
    int chars;
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) { show_error(L"The source file could not be opened. Check its path and read permissions."); return 0; }
    if (!GetFileSizeEx(file, &size) || size.QuadPart < 0 || size.QuadPart > SOURCE_LIMIT) {
        CloseHandle(file); show_error(L"This desktop editor accepts source files up to 4 MiB. Larger files can be scanned with the CLI."); return 0;
    }
    bytes = malloc((size_t)size.QuadPart + 1);
    if (bytes == NULL) { CloseHandle(file); show_error(L"Not enough memory to open the source."); return 0; }
    if (!ReadFile(file, bytes, (DWORD)size.QuadPart, &read_count, NULL) || read_count != (DWORD)size.QuadPart) {
        free(bytes); CloseHandle(file); show_error(L"The complete source file could not be read."); return 0;
    }
    CloseHandle(file); bytes[read_count] = 0;
    if (memchr(bytes, 0, read_count) != NULL) { free(bytes); show_error(L"The file contains NUL bytes and cannot be edited as a C text file."); return 0; }
    if (read_count >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF) skip = 3;
    chars = read_count > skip ? MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (char *)bytes + skip,
                                                   (int)(read_count - skip), NULL, 0) : 0;
    if (read_count > skip && !chars) { free(bytes); show_error(L"Open an ASCII or UTF-8 C source file. This file is not valid UTF-8 text."); return 0; }
    wide = calloc((size_t)chars + 1, sizeof *wide);
    if (wide == NULL) { free(bytes); show_error(L"Not enough memory to decode the source."); return 0; }
    if (chars) MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, (char *)bytes + skip,
                                  (int)(read_count - skip), wide, chars);
    install_source(wide, sample ? L"" : path, base_name(path));
    free(wide); free(bytes); return 1;
}

static void load_sample(int errors)
{
    wchar_t path[32768], *slash;
    DWORD length;
    if (!confirm_discard()) return;
    length = GetModuleFileNameW(NULL, path, (DWORD)COUNT_OF(path));
    slash = wcsrchr(path, L'\\');
    if (!length || length >= COUNT_OF(path) || slash == NULL || (size_t)(slash - path) + 30 >= COUNT_OF(path)) {
        show_error(L"The application directory could not be resolved."); return;
    }
    lstrcpyW(slash + 1, errors ? L"samples\\errors.c" : L"samples\\demo.c");
    load_source(path, 1);
}

static int save_source(void)
{
    wchar_t path[32768];
    size_t length;
    unsigned char *bytes;
    HANDLE file;
    DWORD written;
    int ok;
    lstrcpynW(path, file_path[0] ? file_path : L"Untitled.c", (int)COUNT_OF(path));
    if (!file_path[0] && !file_dialog(path, 1, 0)) return 0;
    bytes = editor_source(&length);
    if (bytes == NULL) return 0;
    file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) { free(bytes); show_error(L"The file could not be saved. Check its path and write permissions."); return 0; }
    ok = WriteFile(file, bytes, (DWORD)length, &written, NULL) && written == length;
    if (!CloseHandle(file)) ok = 0;
    free(bytes);
    if (!ok) { show_error(L"The source could not be saved completely. Your editor contents have been retained."); return 0; }
    lstrcpynW(file_path, path, (int)COUNT_OF(file_path));
    lstrcpynW(file_name, base_name(path), (int)COUNT_OF(file_name)); dirty = 0;
    set_status(L"Source saved as UTF-8. Your analysis results are unchanged."); update_state(); return 1;
}

static void export_results(void)
{
    wchar_t path[32768] = L"Lexical_Analysis.csv";
    FILE *file;
    int ok;
    if (!has_results || !file_dialog(path, 1, 1)) return;
    file = _wfopen(path, L"wb");
    if (file == NULL) { show_error(L"The results file could not be created."); return; }
    ok = analysis_export_csv(&results, file);
    if (fclose(file) != 0) ok = 0;
    if (!ok) show_error(L"The complete CSV could not be written.");
    else set_status(L"Results exported - the CSV includes every token and diagnostic, regardless of the current filter.");
}

static int scan_cancelled(void *context)
{
    ScanJob *scan = context;
    return InterlockedCompareExchange(&scan->cancelled, 0, 0) != 0;
}

static DWORD WINAPI scan_thread(void *parameter)
{
    ScanJob *scan = parameter;
    scan->status = analysis_scan(&scan->result, scan->source, scan->length, scan_cancelled, scan);
    free(scan->source); scan->source = NULL;
    if (!PostMessageW(scan->window, WM_ANALYSIS_DONE, 0, (LPARAM)scan)) {
        analysis_free(&scan->result); free(scan);
    }
    return 0;
}

static void begin_analysis(void)
{
    size_t length;
    unsigned char *source;
    if (job != NULL) {
        InterlockedExchange(&job->cancelled, 1); set_status(L"Cancelling the current analysis..."); return;
    }
    source = editor_source(&length);
    if (source == NULL) return;
    job = calloc(1, sizeof *job);
    if (job == NULL) { free(source); show_error(L"Not enough memory to start analysis."); return; }
    job->source = source; job->length = length; job->window = main_window; job->revision = source_revision;
    analysis_init(&job->result); clear_result_data();
    worker = CreateThread(NULL, 0, scan_thread, job, 0, NULL);
    if (worker == NULL) {
        free(source); free(job); job = NULL; show_error(L"The analysis worker could not be started.");
    } else set_status(L"Analyzing a source snapshot on a background thread. You can continue editing or cancel.");
    update_state();
}

static void apply_filter(void)
{
    wchar_t wide[129];
    char query[129];
    int i, selection;
    GetWindowTextW(search_box, wide, (int)COUNT_OF(wide));
    for (i = 0; wide[i] && i < 128; ++i) query[i] = wide[i] <= 127 ? (char)wide[i] : '\x7f';
    query[i] = 0;
    selection = (int)SendMessageW(category_box, CB_GETCURSEL, 0, 0);
    if (!analysis_filter(&results, selection < 0 ? FILTER_ALL : (AnalysisFilter)selection,
                         query, &visible_rows, &visible_count)) {
        show_error(L"Not enough memory to filter the token view. Previous results are retained."); return;
    }
    ListView_SetItemCountEx(token_list, (int)visible_count, LVSICF_NOINVALIDATEALL);
    InvalidateRect(token_list, NULL, TRUE); update_state();
}

static void analysis_finished(ScanJob *scan)
{
    wchar_t message[512];
    size_t i;
    if (worker != NULL) { CloseHandle(worker); worker = NULL; }
    job = NULL;
    if (closing) { analysis_free(&scan->result); free(scan); DestroyWindow(main_window); return; }
    if (scan->revision != source_revision) {
        set_status(L"Source changed during analysis - analyze again to use the latest editor contents.");
    } else if (scan->status == ANALYSIS_OK && !scan_cancelled(scan)) {
        results = scan->result; analysis_init(&scan->result); has_results = 1;
        if (results.errors) error_rows = malloc(results.errors * sizeof *error_rows);
        if (results.errors && error_rows == NULL) {
            clear_result_data(); show_error(L"Not enough memory to build the diagnostic view.");
        } else {
            for (i = 0; i < results.count; ++i)
                if (results.tokens[i].kind == TOKEN_ERROR) error_rows[error_count++] = i;
            ListView_SetItemCountEx(diagnostic_list, (int)error_count, 0);
            apply_filter();
            swprintf(message, COUNT_OF(message), results.errors ? L"Errors detected - %zu valid tokens, %zu lexical errors." :
                     L"Analysis completed - %zu tokens, %zu lexical errors.", analysis_total(&results), results.errors);
            set_status(message);
        }
    } else if (scan->status == ANALYSIS_MEMORY) {
        set_status(L"Analysis could not be completed: insufficient memory.");
        show_error(L"Analysis stopped because available memory was exhausted.");
    } else if (scan->status == ANALYSIS_LIMIT) {
        set_status(L"Analysis stopped at the desktop row limit. The CLI supports larger token streams.");
        show_error(L"The desktop result view supports up to 500,000 rows. Use the CLI for a larger token stream.");
    }
    else set_status(L"Analysis cancelled. The editor contents have been retained.");
    analysis_free(&scan->result); free(scan); update_state();
}

static void jump_to_token(size_t index)
{
    const Token *token;
    size_t offset;
    CHARRANGE selection;
    int start, length;
    if (index >= results.count) return;
    token = &results.tokens[index]; offset = (size_t)(token->lexeme - results.source);
    start = offset ? MultiByteToWideChar(CP_UTF8, 0, (const char *)results.source, (int)offset, NULL, 0) : 0;
    length = token->length ? MultiByteToWideChar(CP_UTF8, 0, (const char *)token->lexeme, (int)token->length, NULL, 0) : 0;
    /* RichEdit's internal indices count CRLF as a single paragraph marker. */
    {
        size_t j;
        for (j = 1; j < offset; ++j) if (results.source[j] == '\n' && results.source[j-1] == '\r') --start;
        for (j = 1; j < token->length; ++j) if (token->lexeme[j] == '\n' && token->lexeme[j-1] == '\r') --length;
    }
    selection.cpMin = start; selection.cpMax = start + length;
    SendMessageW(editor, EM_EXSETSEL, 0, (LPARAM)&selection);
    SendMessageW(editor, EM_SCROLLCARET, 0, 0); SetFocus(editor); InvalidateRect(gutter, NULL, FALSE);
}

static void update_state(void)
{
    static const wchar_t *const names[] = {L"Total Tokens", L"Keywords", L"Identifiers", L"Constants", L"Operators", L"Separators", L"Lexical Errors"};
    size_t counts[7] = {analysis_total(&results), results.counts[TOKEN_KEYWORD], results.counts[TOKEN_IDENTIFIER],
                        analysis_constants(&results), results.counts[TOKEN_OPERATOR], results.counts[TOKEN_PUNCTUATOR], results.errors};
    wchar_t value[64], title[640];
    int i;
    for (i = 0; i < 7; ++i) {
        swprintf(value, COUNT_OF(value), L"%zu", counts[i]);
        SetWindowTextW(values[i], has_results ? value : L"-"); SetWindowTextW(labels[i], names[i]);
    }
    SetWindowTextW(badge, job ? L"ANALYZING" : (has_results ? (results.errors ? L"ERRORS DETECTED" : L"ANALYSIS COMPLETE") : L"READY"));
    SetWindowTextW(buttons[5], job ? L"CANCEL ANALYSIS" : L"ANALYZE CODE");
    EnableWindow(buttons[7], has_results && job == NULL);
    swprintf(title, COUNT_OF(title), L"%ls%ls - Lexical Analyzer", file_name, dirty ? L" *" : L"");
    SetWindowTextW(main_window, title);
    ShowWindow(token_empty, visible_count ? SW_HIDE : SW_SHOW);
    SetWindowTextW(token_empty, job ? L"Analyzing your source...\nThe scanner runs on a background thread." :
        (has_results ? (results.count ? L"No matching tokens\nTry another search or category." : L"No tokens to display\nThe source is empty or contains only comments.") :
        L"Your token stream appears here\nOpen a C file or load a sample, then analyze."));
    ShowWindow(diagnostic_list, error_count ? SW_SHOW : SW_HIDE);
    ShowWindow(diagnostic_empty, error_count ? SW_HIDE : SW_SHOW);
    SetWindowTextW(diagnostic_empty, job ? L"Checking lexical rules..." :
        (has_results ? L"No lexical errors detected.\nThe source passed all supported lexical checks." :
        L"Diagnostics will appear after analysis.\nDouble-click an error to locate it in the editor."));
    InvalidateRect(main_window, NULL, FALSE);
    InvalidateRect(values[6], NULL, TRUE); InvalidateRect(diagnostic_empty, NULL, TRUE);
}

static void move(HWND window, int x, int y, int width, int height)
{
    MoveWindow(window, x, y, maximum(1, width), maximum(1, height), TRUE);
}

static void layout_window(void)
{
    RECT client;
    int width, height, margin = scaled(24), gap = scaled(12), card_width, i, left_width, right_x, right_width;
    int toolbar_y = scaled(88), button_height = scaled(36), source_y, source_height, filter_y, list_y, list_height, diag_height;
    int actions[] = {122, 108, 120, 122, 105};
    int x = margin;
    GetClientRect(main_window, &client); width = client.right; height = client.bottom;
    for (i = 0; i < 5; ++i) { move(buttons[i], x, toolbar_y, scaled(actions[i]), button_height); x += scaled(actions[i] + 8); }
    move(buttons[5], width - margin - scaled(186), toolbar_y, scaled(186), button_height);
    move(badge, width - margin - scaled(190), scaled(30), scaled(190), scaled(26));
    card_width = (width - 2 * margin - 6 * gap) / 7;
    for (i = 0; i < 7; ++i) {
        int card_x = margin + i * (card_width + gap);
        move(labels[i], card_x + scaled(14), scaled(154), card_width - scaled(22), scaled(19));
        move(values[i], card_x + scaled(14), scaled(178), card_width - scaled(22), scaled(36));
    }
    body_top = scaled(244);
    source_height = maximum(scaled(280), height - body_top - scaled(58));
    left_width = (width - 2 * margin - gap) * 43 / 100;
    right_x = margin + left_width + gap; right_width = width - margin - right_x;
    source_panel = (RECT){margin, body_top, margin + left_width, body_top + source_height};
    output_panel = (RECT){right_x, body_top, width - margin, body_top + source_height};
    source_y = body_top + scaled(46);
    move(gutter, margin + scaled(6), source_y, scaled(40), source_height - scaled(78));
    move(editor, margin + scaled(48), source_y, left_width - scaled(60), source_height - scaled(78));
    filter_y = body_top + scaled(45);
    {
        int search_width = maximum(scaled(100), right_width - scaled(362));
        move(search_box, right_x + scaled(14), filter_y + scaled(6), search_width - scaled(10), scaled(25));
        move(category_box, right_x + search_width + scaled(12), filter_y, scaled(132), scaled(280));
        move(buttons[6], right_x + right_width - scaled(206), filter_y, scaled(86), scaled(34));
        move(buttons[7], right_x + right_width - scaled(112), filter_y, scaled(100), scaled(34));
    }
    list_y = filter_y + scaled(46);
    diag_height = minimum(scaled(205), maximum(scaled(148), source_height / 3));
    diagnostics_panel = (RECT){right_x, body_top + source_height - diag_height, width - margin, body_top + source_height};
    list_height = maximum(scaled(90), diagnostics_panel.top - list_y - scaled(10));
    move(token_list, right_x + scaled(12), list_y, right_width - scaled(24), list_height);
    move(token_empty, right_x + scaled(30), list_y + scaled(55), right_width - scaled(60), scaled(75));
    move(diagnostic_list, right_x + scaled(12), diagnostics_panel.top + scaled(38), right_width - scaled(24), diag_height - scaled(50));
    move(diagnostic_empty, right_x + scaled(22), diagnostics_panel.top + scaled(66), right_width - scaled(44), scaled(65));
    move(footer, margin, height - scaled(36), width - 2 * margin, scaled(22));
    ListView_SetColumnWidth(token_list, 0, scaled(58));
    ListView_SetColumnWidth(token_list, 1, maximum(scaled(120), right_width - scaled(334)));
    ListView_SetColumnWidth(token_list, 2, scaled(132));
    ListView_SetColumnWidth(token_list, 3, scaled(55)); ListView_SetColumnWidth(token_list, 4, scaled(65));
    ListView_SetColumnWidth(diagnostic_list, 0, scaled(76));
    ListView_SetColumnWidth(diagnostic_list, 1, maximum(scaled(180), right_width - scaled(260)));
    ListView_SetColumnWidth(diagnostic_list, 2, scaled(145));
    InvalidateRect(main_window, NULL, TRUE);
}

static LRESULT CALLBACK header_proc(HWND window, UINT message, WPARAM wp, LPARAM lp,
                                    UINT_PTR subclass, DWORD_PTR reference)
{
    (void)subclass; (void)reference;
    if (message == WM_ERASEBKGND) return 1;
    if (message == WM_PAINT) {
        PAINTSTRUCT paint;
        RECT client;
        int count = Header_GetItemCount(window), i;
        HDC dc = BeginPaint(window, &paint);
        GetClientRect(window, &client); fill(dc, &client, PANEL);
        for (i = 0; i < count; ++i) {
            RECT r;
            wchar_t label[128];
            HDITEMW item;
            memset(&item, 0, sizeof item); item.mask = HDI_TEXT;
            item.pszText = label; item.cchTextMax = (int)COUNT_OF(label);
            Header_GetItemRect(window, i, &r); Header_GetItem(window, i, &item);
            r.left += scaled(8);
            text(dc, r, label, font_small, MUTED, DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
        }
        line(dc, 0, client.bottom - 1, client.right, client.bottom - 1, BORDER);
        EndPaint(window, &paint); return 0;
    }
    return DefSubclassProc(window, message, wp, lp);
}

static LRESULT CALLBACK editor_proc(HWND window, UINT message, WPARAM wp, LPARAM lp,
                                    UINT_PTR subclass, DWORD_PTR reference)
{
    LRESULT result;
    (void)subclass; (void)reference;
    if (message == WM_GETDLGCODE) return DefSubclassProc(window, message, wp, lp) | DLGC_WANTTAB;
    result = DefSubclassProc(window, message, wp, lp);
    if (message == WM_VSCROLL || message == WM_MOUSEWHEEL || message == WM_KEYUP || message == WM_SIZE || message == EM_SCROLLCARET)
        PostMessageW(main_window, WM_EDITOR_SCROLL, 0, 0);
    return result;
}

static LRESULT CALLBACK button_proc(HWND window, UINT message, WPARAM wp, LPARAM lp,
                                    UINT_PTR subclass, DWORD_PTR reference)
{
    (void)subclass; (void)reference;
    if (message == WM_MOUSEMOVE) {
        TRACKMOUSEEVENT track = {sizeof track, TME_LEAVE, window, 0};
        TrackMouseEvent(&track); InvalidateRect(window, NULL, FALSE);
    } else if (message == WM_MOUSELEAVE || message == WM_SETFOCUS || message == WM_KILLFOCUS)
        InvalidateRect(window, NULL, FALSE);
    return DefSubclassProc(window, message, wp, lp);
}

static LRESULT CALLBACK combo_proc(HWND window, UINT message, WPARAM wp, LPARAM lp,
                                   UINT_PTR subclass, DWORD_PTR reference)
{
    (void)subclass; (void)reference;
    if (message == WM_ERASEBKGND) return 1;
    if (message == WM_PAINT) {
        PAINTSTRUCT paint;
        RECT rect, label;
        wchar_t current[80] = L"All tokens";
        LRESULT selected = SendMessageW(window, CB_GETCURSEL, 0, 0);
        HDC dc = BeginPaint(window, &paint);
        GetClientRect(window, &rect); rounded(dc, rect, EDIT_BG, BORDER, scaled(6));
        if (selected >= 0) SendMessageW(window, CB_GETLBTEXT, (WPARAM)selected, (LPARAM)current);
        label = rect; label.left += scaled(10); label.right -= scaled(22);
        text(dc, label, current, font_small, TEXT_COLOR, DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
        line(dc, rect.right - scaled(17), scaled(14), rect.right - scaled(12), scaled(19), MUTED);
        line(dc, rect.right - scaled(12), scaled(19), rect.right - scaled(7), scaled(14), MUTED);
        EndPaint(window, &paint); return 0;
    }
    return DefSubclassProc(window, message, wp, lp);
}

static LRESULT CALLBACK gutter_proc(HWND window, UINT message, WPARAM wp, LPARAM lp)
{
    if (message == WM_ERASEBKGND) return 1;
    if (message == WM_PAINT) {
        PAINTSTRUCT paint;
        RECT client;
        LONG first, count, i;
        HDC dc = BeginPaint(window, &paint);
        GetClientRect(window, &client); fill(dc, &client, EDIT_BG);
        first = (LONG)SendMessageW(editor, EM_GETFIRSTVISIBLELINE, 0, 0);
        count = (LONG)SendMessageW(editor, EM_GETLINECOUNT, 0, 0);
        for (i = first; i < count && i < first + 100; ++i) {
            LONG index = (LONG)SendMessageW(editor, EM_LINEINDEX, (WPARAM)i, 0);
            POINTL point = {0, 0};
            RECT r;
            wchar_t number[32];
            SendMessageW(editor, EM_POSFROMCHAR, (WPARAM)&point, index);
            if (point.y > client.bottom) break;
            r = (RECT){0, point.y, client.right - scaled(7), point.y + scaled(20)};
            swprintf(number, COUNT_OF(number), L"%ld", (long)i + 1);
            text(dc, r, number, font_code, MUTED, DT_RIGHT | DT_SINGLELINE);
        }
        line(dc, client.right - 1, 0, client.right - 1, client.bottom, BORDER);
        EndPaint(window, &paint); return 0;
    }
    return DefWindowProcW(window, message, wp, lp);
}

static void configure_fonts(void)
{
    HFONT previous[] = {font_body, font_small, font_title, font_code, font_number, font_semibold};
    HWND fixed[] = {editor, search_box, category_box, token_list, diagnostic_list, footer, badge, token_empty, diagnostic_empty};
    size_t i;
    CHARFORMAT2W format;
    font_body = CreateFontW(-scaled(14), 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
    font_small = CreateFontW(-scaled(12), 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
    font_title = CreateFontW(-scaled(27), 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
    font_code = CreateFontW(-scaled(14), 0, 0, 0, FW_NORMAL, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Consolas");
    font_number = CreateFontW(-scaled(28), 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
    font_semibold = CreateFontW(-scaled(13), 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, CLEARTYPE_QUALITY, 0, L"Segoe UI");
    for (i = 0; i < COUNT_OF(fixed); ++i) SendMessageW(fixed[i], WM_SETFONT, (WPARAM)(i == 0 ? font_code : font_body), TRUE);
    SendMessageW(footer, WM_SETFONT, (WPARAM)font_small, TRUE);
    SendMessageW(badge, WM_SETFONT, (WPARAM)font_small, TRUE);
    for (i = 0; i < COUNT_OF(buttons); ++i) SendMessageW(buttons[i], WM_SETFONT, (WPARAM)font_semibold, TRUE);
    for (i = 0; i < 7; ++i) {
        SendMessageW(labels[i], WM_SETFONT, (WPARAM)font_small, TRUE);
        SendMessageW(values[i], WM_SETFONT, (WPARAM)font_number, TRUE);
    }
    SendMessageW(category_box, CB_SETITEMHEIGHT, (WPARAM)-1, scaled(28));
    SendMessageW(category_box, CB_SETITEMHEIGHT, 0, scaled(28));
    memset(&format, 0, sizeof format); format.cbSize = sizeof format;
    format.dwMask = CFM_COLOR; format.crTextColor = TEXT_COLOR;
    SendMessageW(editor, EM_SETCHARFORMAT, SCF_ALL, (LPARAM)&format);
    if (row_images != NULL) ImageList_Destroy(row_images);
    row_images = ImageList_Create(1, scaled(24), ILC_COLOR32, 1, 1);
    if (row_images != NULL) ImageList_SetImageCount(row_images, 1);
    ListView_SetImageList(token_list, row_images, LVSIL_SMALL);
    ListView_SetImageList(diagnostic_list, row_images, LVSIL_SMALL);
    for (i = 0; i < COUNT_OF(previous); ++i) if (previous[i] != NULL) DeleteObject(previous[i]);
}

static HWND child(const wchar_t *class_name, const wchar_t *caption, DWORD style, int id)
{
    return CreateWindowExW(0, class_name, caption, WS_CHILD | WS_VISIBLE | style,
                           0, 0, 1, 1, main_window, (HMENU)(INT_PTR)id, app_instance, NULL);
}

static void setup_list(HWND list, const wchar_t *const *names, size_t count)
{
    size_t i;
    ListView_SetExtendedListViewStyle(list, LVS_EX_FULLROWSELECT | LVS_EX_DOUBLEBUFFER | LVS_EX_LABELTIP);
    ListView_SetBkColor(list, EDIT_BG); ListView_SetTextBkColor(list, EDIT_BG); ListView_SetTextColor(list, TEXT_COLOR);
    SetWindowTheme(list, L"DarkMode_Explorer", NULL);
    for (i = 0; i < count; ++i) {
        LVCOLUMNW column;
        memset(&column, 0, sizeof column); column.mask = LVCF_TEXT | LVCF_WIDTH | LVCF_FMT;
        column.pszText = (wchar_t *)names[i]; column.cx = scaled(100); column.fmt = LVCFMT_LEFT;
        ListView_InsertColumn(list, (int)i, &column);
    }
    SetWindowSubclass(ListView_GetHeader(list), header_proc, 1, 0);
}

static void create_controls(void)
{
    static const wchar_t *const captions[] = {L"Open C File", L"Save File", L"Load Sample", L"Error Sample", L"Clear Editor", L"ANALYZE CODE", L"Clear Results", L"Export Results"};
    static const int ids[] = {ID_OPEN, ID_SAVE, ID_SAMPLE, ID_ERRORS, ID_CLEAR, ID_ANALYZE, ID_CLEAR_RESULTS, ID_EXPORT};
    static const wchar_t *const token_columns[] = {L"Token No.", L"Lexeme", L"Token Category", L"Line", L"Column"};
    static const wchar_t *const error_columns[] = {L"Line : Col", L"Diagnostic", L"Lexeme"};
    static const wchar_t *const categories[] = {L"All tokens", L"Keywords", L"Identifiers", L"Constants", L"Operators", L"Separators", L"Errors"};
    size_t i;
    editor = child(MSFTEDIT_CLASS, L"", WS_TABSTOP | WS_VSCROLL | WS_HSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_AUTOHSCROLL | ES_NOHIDESEL | ES_WANTRETURN, ID_EDITOR);
    SendMessageW(editor, EM_SETBKGNDCOLOR, 0, EDIT_BG);
    SendMessageW(editor, EM_EXLIMITTEXT, 0, SOURCE_LIMIT);
    SendMessageW(editor, EM_SETEVENTMASK, 0, ENM_CHANGE | ENM_SCROLL | ENM_UPDATE);
    SetWindowSubclass(editor, editor_proc, 1, 0);
    gutter = child(L"LexicalAnalyzer.Gutter", L"", 0, 101);
    for (i = 0; i < COUNT_OF(buttons); ++i) {
        buttons[i] = child(L"BUTTON", captions[i], WS_TABSTOP | BS_OWNERDRAW, ids[i]);
        SetWindowSubclass(buttons[i], button_proc, 1, 0);
    }
    for (i = 0; i < 7; ++i) {
        labels[i] = child(L"STATIC", L"", SS_LEFT, 220 + (int)i);
        values[i] = child(L"STATIC", L"-", SS_LEFT, ID_STAT_BASE + (int)i);
    }
    badge = child(L"STATIC", L"READY", SS_CENTER | SS_CENTERIMAGE, 141);
    footer = child(L"STATIC", status_text, SS_LEFT | SS_CENTERIMAGE, ID_STATUS);
    search_box = child(L"EDIT", L"", WS_TABSTOP | ES_AUTOHSCROLL, ID_SEARCH);
    SendMessageW(search_box, EM_SETLIMITTEXT, 128, 0);
    SendMessageW(search_box, EM_SETCUEBANNER, TRUE, (LPARAM)L"Search lexemes...");
    category_box = child(L"COMBOBOX", L"", WS_TABSTOP | CBS_DROPDOWNLIST | CBS_OWNERDRAWFIXED | CBS_HASSTRINGS, ID_FILTER);
    for (i = 0; i < COUNT_OF(categories); ++i) SendMessageW(category_box, CB_ADDSTRING, 0, (LPARAM)categories[i]);
    SendMessageW(category_box, CB_SETCURSEL, 0, 0); SetWindowSubclass(category_box, combo_proc, 1, 0);
    token_list = child(WC_LISTVIEWW, L"Token analysis table", WS_TABSTOP | LVS_REPORT | LVS_OWNERDATA | LVS_SHOWSELALWAYS | LVS_SHAREIMAGELISTS, ID_TOKENS);
    diagnostic_list = child(WC_LISTVIEWW, L"Error diagnostics", WS_TABSTOP | LVS_REPORT | LVS_OWNERDATA | LVS_SHOWSELALWAYS | LVS_SHAREIMAGELISTS, ID_DIAGNOSTICS);
    setup_list(token_list, token_columns, COUNT_OF(token_columns)); setup_list(diagnostic_list, error_columns, COUNT_OF(error_columns));
    token_empty = child(L"STATIC", L"", SS_CENTER, 150);
    diagnostic_empty = child(L"STATIC", L"", SS_LEFT, 151);
    configure_fonts(); update_state();
}

static void paint_window(HDC dc, RECT client)
{
    RECT r, badge_rect;
    int width = client.right, margin = scaled(24), gap = scaled(12), i;
    int card_width = (width - margin * 2 - gap * 6) / 7;
    wchar_t info[640];
    fill(dc, &client, BG);
    r = (RECT){margin, scaled(23), margin + scaled(42), scaled(65)};
    rounded(dc, r, PANEL, BORDER, scaled(10)); text(dc, r, L"Lx", font_semibold, ACCENT, DT_CENTER | DT_VCENTER | DT_SINGLELINE);
    r = (RECT){margin + scaled(57), scaled(17), width - scaled(260), scaled(51)};
    text(dc, r, L"Lexical Analyzer", font_title, TEXT_COLOR, DT_SINGLELINE | DT_VCENTER);
    r.top = scaled(53); r.bottom = scaled(73);
    text(dc, r, L"C Source Code Analysis", font_body, MUTED, DT_SINGLELINE);
    GetWindowRect(badge, &badge_rect); MapWindowPoints(NULL, main_window, (POINT *)&badge_rect, 2);
    rounded(dc, badge_rect, PANEL, BORDER, scaled(8));
    for (i = 0; i < 7; ++i) {
        r = (RECT){margin + i * (card_width + gap), scaled(142), margin + i * (card_width + gap) + card_width, scaled(224)};
        rounded(dc, r, PANEL, BORDER, scaled(10));
        if (i == 0) line(dc, r.left + scaled(14), r.top + 1, r.right - scaled(14), r.top + 1, ACCENT);
        if (i == 6 && has_results && results.errors) line(dc, r.left + scaled(14), r.top + 1, r.right - scaled(14), r.top + 1, RED);
    }
    rounded(dc, source_panel, EDIT_BG, BORDER, scaled(10)); rounded(dc, output_panel, EDIT_BG, BORDER, scaled(10));
    r = source_panel; r.left += scaled(16); r.top += scaled(13); r.bottom = r.top + scaled(22);
    text(dc, r, L"SOURCE EDITOR", font_semibold, MUTED, DT_SINGLELINE);
    r.left += scaled(132); r.right -= scaled(14);
    text(dc, r, file_name, font_small, TEXT_COLOR, DT_SINGLELINE | DT_RIGHT | DT_END_ELLIPSIS);
    line(dc, source_panel.left + 1, body_top + scaled(36), source_panel.right - 1, body_top + scaled(36), BORDER);
    r = output_panel; r.left += scaled(16); r.top += scaled(13); r.bottom = r.top + scaled(22);
    text(dc, r, L"TOKEN EXPLORER", font_semibold, MUTED, DT_SINGLELINE);
    swprintf(info, COUNT_OF(info), has_results ? L"%zu rows  /  %zu shown" : L"Exact lexemes. Real C scanner.", results.count, visible_count);
    r.left += scaled(150); r.right -= scaled(16);
    text(dc, r, info, font_small, MUTED, DT_SINGLELINE | DT_RIGHT | DT_END_ELLIPSIS);
    line(dc, output_panel.left + 1, body_top + scaled(36), output_panel.right - 1, body_top + scaled(36), BORDER);
    r = diagnostics_panel; r.left += scaled(16); r.top += scaled(12); r.bottom = r.top + scaled(22);
    line(dc, diagnostics_panel.left + 1, diagnostics_panel.top, diagnostics_panel.right - 1, diagnostics_panel.top, BORDER);
    text(dc, r, L"DIAGNOSTICS", font_semibold, has_results && results.errors ? RED : MUTED, DT_SINGLELINE);
    if (has_results) {
        swprintf(info, COUNT_OF(info), L"%zu lexical errors", results.errors);
        r.left += scaled(140); r.right -= scaled(16); text(dc, r, info, font_small, results.errors ? RED : ACCENT, DT_SINGLELINE | DT_RIGHT);
    }
    r = source_panel; r.top = r.bottom - scaled(28); r.left += scaled(15); r.right -= scaled(15);
    swprintf(info, COUNT_OF(info), L"%ld lines   |   UTF-8   |   %ls", (long)SendMessageW(editor, EM_GETLINECOUNT, 0, 0), dirty ? L"Unsaved changes" : L"Source ready");
    text(dc, r, info, font_small, MUTED, DT_SINGLELINE | DT_VCENTER | DT_END_ELLIPSIS);
    line(dc, margin, client.bottom - scaled(48), width - margin, client.bottom - scaled(48), BORDER);
}

static LRESULT display_item(NMLVDISPINFOW *info)
{
    int row = info->item.iItem, column = info->item.iSubItem;
    size_t index;
    const Token *token;
    wchar_t value[2048];
    char lexeme[2048];
    if (!(info->item.mask & LVIF_TEXT) || row < 0) return 0;
    if (info->hdr.hwndFrom == token_list) {
        if ((size_t)row >= visible_count) return 0;
        index = visible_rows[row];
    } else {
        if ((size_t)row >= error_count) return 0;
        index = error_rows[row];
    }
    token = &results.tokens[index]; value[0] = 0;
    if (info->hdr.hwndFrom == diagnostic_list) {
        if (column == 0) swprintf(value, COUNT_OF(value), L"%zu : %zu", token->line, token->column);
        else if (column == 1) MultiByteToWideChar(CP_UTF8, 0, token->message, -1, value, (int)COUNT_OF(value));
        else {
            analysis_lexeme_text(token, lexeme, sizeof lexeme);
            MultiByteToWideChar(CP_UTF8, 0, lexeme, -1, value, (int)COUNT_OF(value));
        }
    } else {
        switch (column) {
        case 0: swprintf(value, COUNT_OF(value), L"%zu", index + 1); break;
        case 1:
            analysis_lexeme_text(token, lexeme, sizeof lexeme);
            MultiByteToWideChar(CP_UTF8, 0, lexeme, -1, value, (int)COUNT_OF(value)); break;
        case 2: MultiByteToWideChar(CP_UTF8, 0, token_kind_name(token->kind), -1, value, (int)COUNT_OF(value)); break;
        case 3: swprintf(value, COUNT_OF(value), L"%zu", token->line); break;
        case 4: swprintf(value, COUNT_OF(value), L"%zu", token->column); break;
        }
    }
    lstrcpynW(info->item.pszText, value, info->item.cchTextMax); return 0;
}

static LRESULT custom_list_draw(NMLVCUSTOMDRAW *draw)
{
    if (draw->nmcd.dwDrawStage == CDDS_PREPAINT) return CDRF_NOTIFYITEMDRAW;
    if (draw->nmcd.dwDrawStage == CDDS_ITEMPREPAINT) return CDRF_NOTIFYSUBITEMDRAW;
    if (draw->nmcd.dwDrawStage == (CDDS_ITEMPREPAINT | CDDS_SUBITEM)) {
        size_t row = (size_t)draw->nmcd.dwItemSpec;
        TokenKind kind = TOKEN_ERROR;
        if (draw->nmcd.hdr.hwndFrom == token_list && row < visible_count) kind = results.tokens[visible_rows[row]].kind;
        draw->clrTextBk = (draw->nmcd.uItemState & CDIS_SELECTED) ? RGB(39, 65, 88) : EDIT_BG;
        draw->clrText = TEXT_COLOR;
        if (draw->nmcd.hdr.hwndFrom == diagnostic_list) draw->clrText = RED;
        else if (draw->iSubItem == 2) {
            if (kind == TOKEN_KEYWORD) draw->clrText = ACCENT;
            else if (kind >= TOKEN_INTEGER && kind <= TOKEN_CHARACTER) draw->clrText = AMBER;
            else if (kind == TOKEN_OPERATOR) draw->clrText = BLUE;
            else if (kind == TOKEN_ERROR) draw->clrText = RED;
            else if (kind == TOKEN_PUNCTUATOR) draw->clrText = MUTED;
        }
    }
    return CDRF_DODEFAULT;
}

static LRESULT CALLBACK window_proc(HWND window, UINT message, WPARAM wp, LPARAM lp)
{
    switch (message) {
    case WM_CREATE: {
        BOOL dark = TRUE;
        main_window = window; current_dpi = (int)GetDpiForWindow(window);
        DwmSetWindowAttribute(window, 20, &dark, sizeof dark);
        create_controls(); return 0;
    }
    case WM_SIZE: if (editor != NULL) layout_window(); return 0;
    case WM_GETMINMAXINFO: {
        MINMAXINFO *info = (MINMAXINFO *)lp;
        info->ptMinTrackSize.x = scaled(1080); info->ptMinTrackSize.y = scaled(720); return 0;
    }
    case WM_DPICHANGED: {
        RECT *suggested = (RECT *)lp;
        current_dpi = HIWORD(wp); configure_fonts();
        SetWindowPos(window, NULL, suggested->left, suggested->top, suggested->right - suggested->left,
                     suggested->bottom - suggested->top, SWP_NOZORDER | SWP_NOACTIVATE);
        layout_window(); return 0;
    }
    case WM_ERASEBKGND: return 1;
    case WM_PAINT: {
        PAINTSTRUCT paint;
        RECT client;
        HDC dc = BeginPaint(window, &paint), memory = CreateCompatibleDC(dc);
        HBITMAP bitmap;
        HGDIOBJ old;
        GetClientRect(window, &client);
        bitmap = CreateCompatibleBitmap(dc, maximum(1, client.right), maximum(1, client.bottom));
        old = SelectObject(memory, bitmap); paint_window(memory, client);
        BitBlt(dc, 0, 0, client.right, client.bottom, memory, 0, 0, SRCCOPY);
        SelectObject(memory, old); DeleteObject(bitmap); DeleteDC(memory);
        EndPaint(window, &paint); return 0;
    }
    case WM_PRINTCLIENT: {
        RECT client; GetClientRect(window, &client); paint_window((HDC)wp, client); return 0;
    }
    case WM_CTLCOLORSTATIC: {
        HDC dc = (HDC)wp;
        HWND control = (HWND)lp;
        int id = GetDlgCtrlID(control);
        SetBkMode(dc, TRANSPARENT); SetTextColor(dc, TEXT_COLOR);
        if (id >= 200 && id < 227) {
            if (id == ID_STAT_BASE) SetTextColor(dc, ACCENT);
            if (id == ID_STAT_BASE + 6) SetTextColor(dc, has_results && results.errors ? RED : MUTED);
            if (id >= 220) SetTextColor(dc, MUTED);
            SetBkColor(dc, PANEL); return (LRESULT)brush_panel;
        }
        if (control == token_empty || control == diagnostic_empty) {
            SetBkColor(dc, EDIT_BG); SetTextColor(dc, control == diagnostic_empty && has_results && !results.errors ? ACCENT : MUTED);
            return (LRESULT)brush_input;
        }
        if (control == badge) {
            SetBkColor(dc, PANEL); SetTextColor(dc, has_results && results.errors ? RED : ACCENT); return (LRESULT)brush_panel;
        }
        SetTextColor(dc, MUTED); SetBkColor(dc, BG); return (LRESULT)brush_bg;
    }
    case WM_CTLCOLOREDIT:
    case WM_CTLCOLORLISTBOX:
        SetTextColor((HDC)wp, TEXT_COLOR); SetBkColor((HDC)wp, EDIT_BG); return (LRESULT)brush_input;
    case WM_MEASUREITEM:
        ((MEASUREITEMSTRUCT *)lp)->itemHeight = (UINT)scaled(28); return TRUE;
    case WM_DRAWITEM: {
        DRAWITEMSTRUCT *draw = (DRAWITEMSTRUCT *)lp;
        RECT rect = draw->rcItem;
        wchar_t caption[128];
        if (draw->CtlType == ODT_COMBOBOX) {
            if (draw->itemID == (UINT)-1) return TRUE;
            SendMessageW(draw->hwndItem, CB_GETLBTEXT, draw->itemID, (LPARAM)caption);
            fill(draw->hDC, &rect, (draw->itemState & ODS_SELECTED) ? RGB(39, 65, 88) : EDIT_BG);
            rect.left += scaled(10); text(draw->hDC, rect, caption, font_body, TEXT_COLOR, DT_SINGLELINE | DT_VCENTER); return TRUE;
        }
        if (draw->CtlType == ODT_BUTTON) {
            POINT cursor;
            RECT bounds;
            int primary = draw->CtlID == ID_ANALYZE, hovered, disabled = (draw->itemState & ODS_DISABLED) != 0;
            GetCursorPos(&cursor); GetWindowRect(draw->hwndItem, &bounds); hovered = PtInRect(&bounds, cursor);
            GetWindowTextW(draw->hwndItem, caption, (int)COUNT_OF(caption));
            rounded(draw->hDC, rect, primary ? (disabled ? BORDER : ACCENT) : (hovered ? RGB(40, 54, 74) : PANEL),
                    (draw->itemState & ODS_FOCUS) ? ACCENT : (primary ? ACCENT : BORDER), scaled(7));
            if (draw->itemState & ODS_SELECTED) OffsetRect(&rect, 0, 1);
            text(draw->hDC, rect, caption, font_semibold, disabled ? MUTED : (primary ? BG : TEXT_COLOR), DT_CENTER | DT_SINGLELINE | DT_VCENTER);
            return TRUE;
        }
        break;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp), event = HIWORD(wp);
        if (id == ID_EDITOR) {
            if (event == EN_CHANGE) source_changed();
            if (event == EN_VSCROLL || event == EN_UPDATE) InvalidateRect(gutter, NULL, FALSE);
            return 0;
        }
        if (id == ID_SEARCH && event == EN_CHANGE) { SetTimer(window, FILTER_TIMER, 150, NULL); return 0; }
        if (id == ID_FILTER && event == CBN_SELCHANGE) { apply_filter(); InvalidateRect(category_box, NULL, TRUE); return 0; }
        switch (id) {
        case ID_OPEN: {
            wchar_t path[32768] = L"";
            if (confirm_discard() && file_dialog(path, 0, 0)) load_source(path, 0); break;
        }
        case ID_SAVE: save_source(); break;
        case ID_SAMPLE: load_sample(0); break;
        case ID_ERRORS: load_sample(1); break;
        case ID_CLEAR:
            if (confirm_discard()) { install_source(L"", L"", L"Untitled.c"); set_status(L"Ready - the editor is empty."); } break;
        case ID_ANALYZE: begin_analysis(); break;
        case ID_CLEAR_RESULTS:
            if (job != NULL) InterlockedExchange(&job->cancelled, 1);
            clear_result_data(); update_state(); set_status(L"Results cleared. Your source code has been retained."); break;
        case ID_EXPORT: export_results(); break;
        case 160: SetFocus(search_box); break;
        }
        return 0;
    }
    case WM_NOTIFY: {
        NMHDR *header = (NMHDR *)lp;
        if (header->hwndFrom == token_list || header->hwndFrom == diagnostic_list) {
            if (header->code == LVN_GETDISPINFOW) return display_item((NMLVDISPINFOW *)lp);
            if (header->code == NM_CUSTOMDRAW) return custom_list_draw((NMLVCUSTOMDRAW *)lp);
            if (header->code == NM_DBLCLK) {
                NMITEMACTIVATE *item = (NMITEMACTIVATE *)lp;
                if (item->iItem >= 0) {
                    size_t row = (size_t)item->iItem;
                    if (header->hwndFrom == token_list && row < visible_count) jump_to_token(visible_rows[row]);
                    if (header->hwndFrom == diagnostic_list && row < error_count) jump_to_token(error_rows[row]);
                }
            }
        }
        return 0;
    }
    case WM_TIMER:
        if (wp == FILTER_TIMER) { KillTimer(window, FILTER_TIMER); apply_filter(); } return 0;
    case WM_EDITOR_SCROLL: InvalidateRect(gutter, NULL, FALSE); return 0;
    case WM_ANALYSIS_DONE: analysis_finished((ScanJob *)lp); return 0;
    case WM_CLOSE:
        if (!confirm_discard()) return 0;
        if (job != NULL) { closing = 1; InterlockedExchange(&job->cancelled, 1); set_status(L"Closing after the worker releases its source snapshot..."); }
        else DestroyWindow(window);
        return 0;
    case WM_DESTROY:
        clear_result_data();
        if (row_images != NULL) ImageList_Destroy(row_images);
        DeleteObject(font_body); DeleteObject(font_small); DeleteObject(font_title); DeleteObject(font_code);
        DeleteObject(font_number); DeleteObject(font_semibold);
        DeleteObject(brush_bg); DeleteObject(brush_panel); DeleteObject(brush_input);
        PostQuitMessage(0); return 0;
    }
    return DefWindowProcW(window, message, wp, lp);
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command_line, int show)
{
    INITCOMMONCONTROLSEX controls = {sizeof controls, ICC_LISTVIEW_CLASSES | ICC_STANDARD_CLASSES};
    WNDCLASSEXW cls;
    HWND window;
    RECT work;
    MSG message;
    HACCEL accelerators;
    ACCEL keys[] = {{FCONTROL | FVIRTKEY, 'O', ID_OPEN}, {FCONTROL | FVIRTKEY, 'S', ID_SAVE},
                    {FCONTROL | FVIRTKEY, VK_RETURN, ID_ANALYZE}, {FCONTROL | FVIRTKEY, 'F', 160},
                    {FCONTROL | FVIRTKEY, 'E', ID_EXPORT}};
    int width, height, argc;
    wchar_t **argv;
    (void)previous; (void)command_line; (void)show;
    app_instance = instance; analysis_init(&results);
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    InitCommonControlsEx(&controls);
    rich_edit_module = LoadLibraryW(L"Msftedit.dll");
    if (rich_edit_module == NULL) { MessageBoxW(NULL, L"The Windows RichEdit component could not be loaded.", L"Lexical Analyzer", MB_ICONERROR); return 2; }
    brush_bg = CreateSolidBrush(BG); brush_panel = CreateSolidBrush(PANEL); brush_input = CreateSolidBrush(EDIT_BG);
    memset(&cls, 0, sizeof cls); cls.cbSize = sizeof cls;
    cls.hInstance = instance; cls.lpfnWndProc = gutter_proc; cls.lpszClassName = L"LexicalAnalyzer.Gutter";
    cls.hCursor = LoadCursorW(NULL, IDC_ARROW); RegisterClassExW(&cls);
    cls.lpfnWndProc = window_proc; cls.lpszClassName = APP_CLASS;
    cls.hIcon = LoadIconW(instance, MAKEINTRESOURCEW(1)); cls.hIconSm = cls.hIcon;
    cls.hbrBackground = brush_bg;
    if (!RegisterClassExW(&cls)) { FreeLibrary(rich_edit_module); return 2; }
    current_dpi = (int)GetDpiForSystem();
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    width = minimum(scaled(1440), work.right - work.left - scaled(32));
    height = minimum(scaled(940), work.bottom - work.top - scaled(32));
    window = CreateWindowExW(WS_EX_APPWINDOW, APP_CLASS, L"Lexical Analyzer", WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN,
                              work.left + (work.right - work.left - width) / 2, work.top + (work.bottom - work.top - height) / 2,
                              width, height, NULL, NULL, instance, NULL);
    if (window == NULL) { FreeLibrary(rich_edit_module); return 2; }
    ShowWindow(window, SW_SHOWNORMAL); UpdateWindow(window);
    argc = 0; argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv != NULL) { if (argc > 1) load_source(argv[1], 0); LocalFree(argv); }
    accelerators = CreateAcceleratorTableW(keys, (int)COUNT_OF(keys));
    while (GetMessageW(&message, NULL, 0, 0) > 0) {
        if (!TranslateAcceleratorW(window, accelerators, &message) && !IsDialogMessageW(window, &message)) {
            TranslateMessage(&message); DispatchMessageW(&message);
        }
    }
    DestroyAcceleratorTable(accelerators); FreeLibrary(rich_edit_module);
    return (int)message.wParam;
}
