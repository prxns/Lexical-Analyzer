#ifndef ANALYSIS_H
#define ANALYSIS_H
#include "lexer.h"
#include <stdio.h>

#define ANALYSIS_TOKEN_LIMIT 500000u
typedef struct {
    unsigned char *source;
    size_t length;
    Token *tokens;
    size_t count, capacity, counts[TOKEN_ERROR], errors;
} Analysis;

typedef enum {
    FILTER_ALL, FILTER_KEYWORDS, FILTER_IDENTIFIERS, FILTER_CONSTANTS,
    FILTER_OPERATORS, FILTER_SEPARATORS, FILTER_ERRORS
} AnalysisFilter;
typedef enum { ANALYSIS_OK, ANALYSIS_MEMORY, ANALYSIS_CANCELLED, ANALYSIS_LIMIT } AnalysisStatus;
typedef int (*AnalysisCancel)(void *context);

void analysis_init(Analysis *analysis);
void analysis_free(Analysis *analysis);
AnalysisStatus analysis_scan(Analysis *output, const unsigned char *source, size_t length,
                             AnalysisCancel cancelled, void *context);
size_t analysis_total(const Analysis *analysis);
size_t analysis_constants(const Analysis *analysis);
/* Allocates matching token indices. Search uses a bounded 128-byte ASCII query. */
int analysis_filter(const Analysis *analysis, AnalysisFilter category, const char *query,
                    size_t **indices, size_t *count);
/* Printable, untruncated representation when capacity is sufficient; returns required length. */
size_t analysis_lexeme_text(const Token *token, char *buffer, size_t capacity);
int analysis_export_csv(const Analysis *analysis, FILE *file);
#endif
