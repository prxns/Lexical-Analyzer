#include "lexer.h"
#include <string.h>

static int is_alpha(unsigned char c)
{
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
}

static int is_digit(unsigned char c) { return c >= '0' && c <= '9'; }
static int is_hex(unsigned char c)
{
    return is_digit(c) || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
}
static int is_space(unsigned char c)
{
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}

static unsigned char peek(const Lexer *l, size_t ahead)
{
    return ahead < l->length - l->position ? l->source[l->position + ahead] : 0;
}

static void advance(Lexer *l)
{
    unsigned char c = l->source[l->position++];
    if (c == '\r') { ++l->line; l->column = 1; }
    else if (c == '\n') {
        if (l->position < 2 || l->source[l->position - 2] != '\r') ++l->line;
        l->column = 1;
    } else ++l->column;
}

static Token finish(Lexer *l, size_t start, size_t line, size_t column,
                    TokenKind kind, const char *message)
{
    Token t;
    t.kind = kind; t.lexeme = l->source + start;
    t.length = l->position - start; t.line = line; t.column = column;
    t.message = message;
    return t;
}

void lexer_init(Lexer *l, const unsigned char *source, size_t length)
{
    l->source = source; l->length = length; l->position = 0;
    l->line = 1; l->column = 1;
}

const char *token_kind_name(TokenKind kind)
{
    static const char *const names[] = {
        "Keyword", "Identifier", "Integer", "Float", "String", "Character",
        "Operator", "Punctuator", "Error", "EOF"
    };
    return names[kind];
}

static int is_keyword(const unsigned char *s, size_t n)
{
    static const char *const words[] = {
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "inline", "int", "long", "register", "restrict", "return", "short",
        "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
        "unsigned", "void", "volatile", "while", "_Alignas", "_Alignof",
        "_Atomic", "_Bool", "_Complex", "_Generic", "_Imaginary", "_Noreturn",
        "_Static_assert", "_Thread_local"
    };
    size_t i;
    for (i = 0; i < sizeof words / sizeof words[0]; ++i)
        if (strlen(words[i]) == n && memcmp(s, words[i], n) == 0) return 1;
    return 0;
}

/* Accept U, L and LL suffixes in either order, without mixed-case lL. */
static int integer_suffix(const unsigned char *s, size_t n, size_t i)
{
    int seen_u = 0, seen_l = 0;
    while (i < n) {
        unsigned char c = s[i++];
        if ((c == 'u' || c == 'U') && !seen_u) seen_u = 1;
        else if ((c == 'l' || c == 'L') && !seen_l) {
            seen_l = 1;
            if (i < n && s[i] == c) ++i;
        } else return 0;
    }
    return 1;
}

static TokenKind number_kind(const unsigned char *s, size_t n)
{
    size_t i = 0, digits = 0, j;
    int floating = 0;
    if (n >= 2 && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) {
        i = 2;
        while (i < n && is_hex(s[i])) ++i;
        return i > 2 && integer_suffix(s, n, i) ? TOKEN_INTEGER : TOKEN_ERROR;
    }
    while (i < n && is_digit(s[i])) { ++i; ++digits; }
    if (i < n && s[i] == '.') {
        floating = 1; ++i;
        while (i < n && is_digit(s[i])) { ++i; ++digits; }
    }
    if (!digits) return TOKEN_ERROR;
    if (i < n && (s[i] == 'e' || s[i] == 'E')) {
        size_t exponent_start;
        floating = 1; ++i;
        if (i < n && (s[i] == '+' || s[i] == '-')) ++i;
        exponent_start = i;
        while (i < n && is_digit(s[i])) ++i;
        if (i == exponent_start) return TOKEN_ERROR;
    }
    if (floating) {
        if (i < n && (s[i] == 'f' || s[i] == 'F' || s[i] == 'l' || s[i] == 'L')) ++i;
        return i == n ? TOKEN_FLOAT : TOKEN_ERROR;
    }
    if (s[0] == '0')
        for (j = 0; j < i; ++j) if (s[j] > '7') return TOKEN_ERROR;
    return integer_suffix(s, n, i) ? TOKEN_INTEGER : TOKEN_ERROR;
}

static Token scan_number(Lexer *l, size_t start, size_t line, size_t column)
{
    TokenKind kind;
    while (l->position < l->length) {
        unsigned char c = peek(l, 0);
        if (is_alpha(c) || is_digit(c) || c == '.') advance(l);
        else if ((c == '+' || c == '-') && l->position > start &&
                 strchr("eEpP", l->source[l->position - 1]) != NULL) advance(l);
        else break;
    }
    kind = number_kind(l->source + start, l->position - start);
    return finish(l, start, line, column, kind,
                  kind == TOKEN_ERROR ? "Malformed or unsupported numeric literal" : NULL);
}

static Token scan_literal(Lexer *l, size_t start, size_t line, size_t column,
                          int prefixed)
{
    unsigned char quote = peek(l, 0);
    size_t units = 0;
    const char *error = prefixed ? "Encoded and wide literals are outside this subset" : NULL;
    advance(l);
    while (l->position < l->length && peek(l, 0) != '\r' && peek(l, 0) != '\n') {
        unsigned char c = peek(l, 0);
        if (c == quote) {
            advance(l);
            if (quote == '\'' && units != 1) error = "Character constant must contain exactly one character";
            return finish(l, start, line, column,
                          error ? TOKEN_ERROR : (quote == '"' ? TOKEN_STRING : TOKEN_CHARACTER), error);
        }
        ++units; advance(l);
        if (c == '\\') {
            size_t count;
            if (l->position == l->length || peek(l, 0) == '\n' || peek(l, 0) == '\r') break;
            c = peek(l, 0); advance(l);
            if (c == 'x') {
                count = 0;
                while (l->position < l->length && is_hex(peek(l, 0))) { advance(l); ++count; }
                if (!count) error = "Hexadecimal escape requires at least one digit";
            } else if (c >= '0' && c <= '7') {
                count = 1;
                while (count < 3 && l->position < l->length && peek(l, 0) >= '0' && peek(l, 0) <= '7') {
                    advance(l); ++count;
                }
            } else if (c == 0 || strchr("'\"?\\abfnrtv", c) == NULL) error = "Invalid or unsupported escape sequence";
        } else if (c == 0 || c >= 127 || (c < 32 && c != '\t')) error = "Unsupported byte in literal";
    }
    return finish(l, start, line, column, TOKEN_ERROR,
                  quote == '"' ? "Unterminated string literal" : "Unterminated character literal");
}

Token lexer_next(Lexer *l)
{
    static const char *const symbols[] = {
        "%:%:", ">>=", "<<=", "...", "++", "--", "->", "+=", "-=", "*=", "/=", "%=",
        "<=", ">=", "==", "!=", "&&", "||", "<<", ">>", "&=", "|=", "^=", "##",
        "<:", ":>", "<%", "%>", "%:",
        "+", "-", "*", "/", "%", "<", ">", "=", "!", "&", "|", "^", "~", "?", ":",
        "(", ")", "{", "}", "[", "]", ",", ";", ".", "#"
    };
    size_t start, line, column, i;
    unsigned char c;
    for (;;) {
        while (l->position < l->length && is_space(peek(l, 0))) advance(l);
        start = l->position; line = l->line; column = l->column;
        if (l->position == l->length) return finish(l, start, line, column, TOKEN_EOF, NULL);
        if (peek(l, 0) == '/' && peek(l, 1) == '/') {
            while (l->position < l->length && peek(l, 0) != '\n' && peek(l, 0) != '\r') advance(l);
        } else if (peek(l, 0) == '/' && peek(l, 1) == '*') {
            advance(l); advance(l);
            while (l->position < l->length && !(peek(l, 0) == '*' && peek(l, 1) == '/')) advance(l);
            if (l->position == l->length)
                return finish(l, start, line, column, TOKEN_ERROR, "Unterminated block comment");
            advance(l); advance(l);
        } else break;
    }
    c = peek(l, 0);
    if ((c == 'L' || c == 'u' || c == 'U') && (peek(l, 1) == '"' || peek(l, 1) == '\'')) {
        advance(l); return scan_literal(l, start, line, column, 1);
    }
    if (c == 'u' && peek(l, 1) == '8' && peek(l, 2) == '"') {
        advance(l); advance(l); return scan_literal(l, start, line, column, 1);
    }
    if (is_alpha(c)) {
        do { advance(l); } while (l->position < l->length && (is_alpha(peek(l, 0)) || is_digit(peek(l, 0))));
        return finish(l, start, line, column,
                      is_keyword(l->source + start, l->position - start) ? TOKEN_KEYWORD : TOKEN_IDENTIFIER, NULL);
    }
    if (is_digit(c) || (c == '.' && is_digit(peek(l, 1)))) return scan_number(l, start, line, column);
    if (c == '\'' || c == '"') return scan_literal(l, start, line, column, 0);
    for (i = 0; i < sizeof symbols / sizeof symbols[0]; ++i) {
        size_t n = strlen(symbols[i]), j;
        if (n <= l->length - l->position && memcmp(l->source + l->position, symbols[i], n) == 0) {
            TokenKind kind = TOKEN_OPERATOR;
            if (strchr("(){}[],;.#", c) != NULL || strcmp(symbols[i], "...") == 0 ||
                strcmp(symbols[i], "%:%:") == 0 || strcmp(symbols[i], "%:") == 0 ||
                strcmp(symbols[i], "<:") == 0 || strcmp(symbols[i], ":>") == 0 ||
                strcmp(symbols[i], "<%") == 0 || strcmp(symbols[i], "%>") == 0) kind = TOKEN_PUNCTUATOR;
            for (j = 0; j < n; ++j) advance(l);
            return finish(l, start, line, column, kind, NULL);
        }
    }
    advance(l);
    return finish(l, start, line, column, TOKEN_ERROR, "Invalid or unsupported character");
}
