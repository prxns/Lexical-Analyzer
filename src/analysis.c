#include "analysis.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

void analysis_init(Analysis *a) { memset(a, 0, sizeof *a); }
void analysis_free(Analysis *a)
{
    free(a->tokens); free(a->source); analysis_init(a);
}

AnalysisStatus analysis_scan(Analysis *output, const unsigned char *source, size_t length,
                             AnalysisCancel cancelled, void *context)
{
    Analysis a;
    Lexer lexer;
    Token token;
    AnalysisStatus status = ANALYSIS_OK;
    analysis_init(&a);
    a.source = malloc(length ? length : 1);
    if (a.source == NULL) return ANALYSIS_MEMORY;
    if (length) memcpy(a.source, source, length);
    a.length = length;
    lexer_init(&lexer, a.source, length);
    for (;;) {
        if (cancelled != NULL && cancelled(context)) { status = ANALYSIS_CANCELLED; break; }
        token = lexer_next(&lexer);
        if (token.kind == TOKEN_EOF) break;
        if (a.count == ANALYSIS_TOKEN_LIMIT) { status = ANALYSIS_LIMIT; break; }
        if (a.count == a.capacity) {
            size_t capacity = a.capacity ? a.capacity * 2 : 256;
            Token *larger;
            if (capacity > ANALYSIS_TOKEN_LIMIT) capacity = ANALYSIS_TOKEN_LIMIT;
            if (capacity > SIZE_MAX / sizeof *a.tokens) { status = ANALYSIS_MEMORY; break; }
            larger = realloc(a.tokens, capacity * sizeof *a.tokens);
            if (larger == NULL) { status = ANALYSIS_MEMORY; break; }
            a.tokens = larger; a.capacity = capacity;
        }
        a.tokens[a.count++] = token;
        if (token.kind == TOKEN_ERROR) ++a.errors;
        else ++a.counts[token.kind];
    }
    if (status != ANALYSIS_OK) { analysis_free(&a); return status; }
    analysis_free(output); *output = a;
    return ANALYSIS_OK;
}

size_t analysis_total(const Analysis *a) { return a->count - a->errors; }
size_t analysis_constants(const Analysis *a)
{
    return a->counts[TOKEN_INTEGER] + a->counts[TOKEN_FLOAT] +
           a->counts[TOKEN_STRING] + a->counts[TOKEN_CHARACTER];
}

static unsigned char lower_ascii(unsigned char c)
{
    return c >= 'A' && c <= 'Z' ? (unsigned char)(c + ('a' - 'A')) : c;
}

static int category_matches(TokenKind kind, AnalysisFilter filter)
{
    switch (filter) {
    case FILTER_KEYWORDS: return kind == TOKEN_KEYWORD;
    case FILTER_IDENTIFIERS: return kind == TOKEN_IDENTIFIER;
    case FILTER_CONSTANTS: return kind >= TOKEN_INTEGER && kind <= TOKEN_CHARACTER;
    case FILTER_OPERATORS: return kind == TOKEN_OPERATOR;
    case FILTER_SEPARATORS: return kind == TOKEN_PUNCTUATOR;
    case FILTER_ERRORS: return kind == TOKEN_ERROR;
    default: return 1;
    }
}

int analysis_filter(const Analysis *a, AnalysisFilter category, const char *query,
                    size_t **indices, size_t *count)
{
    unsigned char needle[128];
    size_t prefix[128], n = strlen(query), i, matched, total = 0;
    size_t *rows = NULL;
    if (n > sizeof needle) return 0;
    if (a->count) {
        rows = malloc(a->count * sizeof *rows);
        if (rows == NULL) return 0;
    }
    for (i = 0; i < n; ++i) needle[i] = lower_ascii((unsigned char)query[i]);
    if (n) prefix[0] = 0;
    /* KMP keeps searching linear even for very long repetitive lexemes. */
    for (i = 1, matched = 0; i < n; ++i) {
        while (matched && needle[i] != needle[matched]) matched = prefix[matched - 1];
        if (needle[i] == needle[matched]) ++matched;
        prefix[i] = matched;
    }
    for (i = 0; i < a->count; ++i) {
        size_t j;
        int found = n == 0;
        const Token *t = &a->tokens[i];
        if (!category_matches(t->kind, category)) continue;
        for (j = 0, matched = 0; !found && j < t->length; ++j) {
            unsigned char c = lower_ascii(t->lexeme[j]);
            while (matched && c != needle[matched]) matched = prefix[matched - 1];
            if (c == needle[matched]) ++matched;
            if (matched == n) found = 1;
        }
        if (found) rows[total++] = i;
    }
    free(*indices); *indices = rows; *count = total;
    return 1;
}

static void append_byte(char *out, size_t capacity, size_t *used, char c)
{
    if (out != NULL && *used + 1 < capacity) out[*used] = c;
    ++*used;
}

size_t analysis_lexeme_text(const Token *token, char *out, size_t capacity)
{
    static const char hex[] = "0123456789ABCDEF";
    size_t i, used = 0;
    for (i = 0; i < token->length; ++i) {
        unsigned char c = token->lexeme[i];
        if (c == '\n' || c == '\r' || c == '\t') {
            append_byte(out, capacity, &used, '\\');
            append_byte(out, capacity, &used, c == '\n' ? 'n' : (c == '\r' ? 'r' : 't'));
        } else if (c < 32 || c >= 127) {
            append_byte(out, capacity, &used, '\\'); append_byte(out, capacity, &used, 'x');
            append_byte(out, capacity, &used, hex[c >> 4]); append_byte(out, capacity, &used, hex[c & 15]);
        } else append_byte(out, capacity, &used, (char)c);
    }
    if (out != NULL && capacity) out[used < capacity ? used : capacity - 1] = '\0';
    return used;
}

static int write_lexeme(FILE *file, const Token *t)
{
    size_t i;
    if (fputc('"', file) == EOF) return 0;
    for (i = 0; i < t->length; ++i) {
        unsigned char c = t->lexeme[i];
        if (c == '"' && fputc('"', file) == EOF) return 0;
        if (c < 32 || c >= 127) {
            if (fprintf(file, "\\x%02X", (unsigned int)c) < 0) return 0;
        } else if (fputc(c, file) == EOF) return 0;
    }
    return fputc('"', file) != EOF;
}

int analysis_export_csv(const Analysis *a, FILE *file)
{
    size_t i;
    if (fputs("Token No.,Lexeme,Token Category,Line,Column,Diagnostic\r\n", file) == EOF) return 0;
    for (i = 0; i < a->count; ++i) {
        const Token *t = &a->tokens[i];
        if (fprintf(file, "%zu,", i + 1) < 0 || !write_lexeme(file, t) ||
            fprintf(file, ",%s,%zu,%zu,\"%s\"\r\n", token_kind_name(t->kind), t->line,
                    t->column, t->message ? t->message : "") < 0) return 0;
    }
    return !ferror(file);
}
