#include "lexer.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned char *read_source(const char *path, size_t *length)
{
    FILE *file = fopen(path, "rb");
    unsigned char *data;
    size_t capacity = 4096, used = 0;
    if (file == NULL) { perror(path); return NULL; }
    data = malloc(capacity);
    if (data == NULL) { fclose(file); fputs("Out of memory\n", stderr); return NULL; }
    for (;;) {
        size_t got = fread(data + used, 1, capacity - used, file);
        used += got;
        if (ferror(file)) { perror(path); free(data); fclose(file); return NULL; }
        if (feof(file)) break;
        if (used == capacity) {
            unsigned char *larger;
            if (capacity > SIZE_MAX / 2) {
                fputs("Source file is too large\n", stderr); free(data); fclose(file); return NULL;
            }
            capacity *= 2; larger = realloc(data, capacity);
            if (larger == NULL) { fputs("Out of memory\n", stderr); free(data); fclose(file); return NULL; }
            data = larger;
        }
    }
    if (fclose(file) != 0) { perror(path); free(data); return NULL; }
    *length = used;
    return data;
}

/* Escape control bytes so input can never inject terminal control sequences. */
static void print_escaped(const unsigned char *s, size_t length, int json, size_t min_width)
{
    size_t i, width = 0;
    if (json) putchar('"');
    for (i = 0; i < length; ++i) {
        unsigned char c = s[i];
        if (c == '\\' || c == '"') { putchar('\\'); putchar(c); width += 2; }
        else if (c == '\n') { fputs("\\n", stdout); width += 2; }
        else if (c == '\r') { fputs("\\r", stdout); width += 2; }
        else if (c == '\t') { fputs("\\t", stdout); width += 2; }
        else if (c < 32 || c >= 127) { printf(json ? "\\u%04x" : "\\x%02x", (unsigned int)c); width += json ? 6 : 4; }
        else { putchar(c); ++width; }
    }
    if (json) putchar('"');
    while (width++ < min_width) putchar(' ');
}

int main(int argc, char **argv)
{
    int json = 0;
    const char *path;
    unsigned char *source;
    size_t length, number = 0, errors = 0, counts[TOKEN_ERROR] = {0}, i;
    Lexer lexer;
    Token token;
    if (argc == 2 && strcmp(argv[1], "--help") == 0) {
        puts("Usage: lexical_analyzer [--json] <source-file>\nExit codes: 0 success, 1 lexical errors, 2 usage or I/O error.");
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "--json") == 0) json = 1;
    else if (argc != 2 || strcmp(argv[1], "--json") == 0) {
        fputs("Usage: lexical_analyzer [--json] <source-file>\n", stderr); return 2;
    }
    path = argv[json ? 2 : 1];
    source = read_source(path, &length);
    if (source == NULL) return 2;
    lexer_init(&lexer, source, length);
    if (json) fputs("{\"tokens\":[", stdout);
    else {
        puts("Lexical Analyzer | C11 subset");
        fputs("Source: ", stdout); print_escaped((const unsigned char *)path, strlen(path), 0, 0);
        puts("\n\nNo.    Lexeme                    Category      Line   Column");
    }
    while ((token = lexer_next(&lexer)).kind != TOKEN_EOF) {
        ++number;
        if (token.kind == TOKEN_ERROR) ++errors;
        else ++counts[token.kind];
        if (json) {
            if (number > 1) putchar(',');
            printf("{\"number\":%zu,\"lexeme\":", number);
            print_escaped(token.lexeme, token.length, 1, 0);
            printf(",\"category\":\"%s\",\"line\":%zu,\"column\":%zu", token_kind_name(token.kind), token.line, token.column);
            if (token.message != NULL) printf(",\"message\":\"%s\"", token.message);
            putchar('}');
        } else {
            printf("%-6zu ", number); print_escaped(token.lexeme, token.length, 0, 25);
            printf(" %-13s %-6zu %zu", token_kind_name(token.kind), token.line, token.column);
            if (token.message != NULL) printf("  %s", token.message);
            putchar('\n');
        }
    }
    if (json) fputs("],\"summary\":{", stdout);
    else puts("\nToken summary");
    for (i = 0; i < TOKEN_ERROR; ++i) {
        if (json) printf("%s\"%s\":%zu", i ? "," : "", token_kind_name((TokenKind)i), counts[i]);
        else printf("  %-13s %zu\n", token_kind_name((TokenKind)i), counts[i]);
    }
    if (json) printf(",\"total\":%zu,\"errors\":%zu}}\n", number - errors, errors);
    else printf("Total tokens: %zu\nLexical errors: %zu\n", number - errors, errors);
    free(source);
    if (fflush(stdout) == EOF || ferror(stdout)) { fputs("Cannot write output\n", stderr); return 2; }
    return errors ? 1 : 0;
}
