#include "analysis.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>

static int cancel_now(void *context) { (void)context; return 1; }

int main(void)
{
    static const unsigned char source[] = "int count=25U; double scale=.5; char c='A'; \"x,y\" @";
    Analysis a;
    size_t *rows = NULL, count = 0, old_count;
    char small[5], full[80], csv[4096];
    FILE *file;
    size_t read_count;
    analysis_init(&a);
    assert(analysis_scan(&a, source, sizeof source - 1, NULL, NULL) == ANALYSIS_OK);
    assert(analysis_total(&a) == 16 && a.errors == 1 && a.count == 17);
    assert(a.counts[TOKEN_KEYWORD] == 3 && a.counts[TOKEN_IDENTIFIER] == 3);
    assert(analysis_constants(&a) == 4 && a.counts[TOKEN_OPERATOR] == 3);
    assert(a.counts[TOKEN_PUNCTUATOR] == 3);
    assert(analysis_filter(&a, FILTER_KEYWORDS, "", &rows, &count) && count == 3);
    assert(analysis_filter(&a, FILTER_IDENTIFIERS, "COUNT", &rows, &count) && count == 1);
    assert(a.tokens[rows[0]].length == 5);
    assert(analysis_filter(&a, FILTER_CONSTANTS, "", &rows, &count) && count == 4);
    assert(analysis_filter(&a, FILTER_ERRORS, "@", &rows, &count) && count == 1);
    assert(a.tokens[rows[0]].line == 1 && a.tokens[rows[0]].message != NULL);
    assert(analysis_filter(&a, FILTER_ALL, "does_not_exist", &rows, &count) && count == 0);
    assert(analysis_lexeme_text(&a.tokens[1], small, sizeof small) == 5);
    assert(strcmp(small, "coun") == 0);
    assert(analysis_lexeme_text(&a.tokens[1], full, sizeof full) == 5 && strcmp(full, "count") == 0);
    file = tmpfile(); assert(file != NULL);
    assert(analysis_export_csv(&a, file)); rewind(file);
    read_count = fread(csv, 1, sizeof csv - 1, file); csv[read_count] = 0;
    assert(strstr(csv, "Token No.,Lexeme,Token Category,Line,Column,Diagnostic") != NULL);
    assert(strstr(csv, "\"\"\"x,y\"\"\"") != NULL);
    assert(strstr(csv, "Invalid or unsupported character") != NULL);
    assert(fclose(file) == 0);
    old_count = a.count;
    assert(analysis_scan(&a, source, sizeof source - 1, cancel_now, NULL) == ANALYSIS_CANCELLED);
    assert(a.count == old_count); /* Failed/cancelled scans do not replace prior results. */
    assert(analysis_scan(&a, NULL, 0, NULL, NULL) == ANALYSIS_OK);
    assert(a.count == 0 && a.errors == 0 && analysis_constants(&a) == 0);
    assert(analysis_filter(&a, FILTER_ALL, "", &rows, &count) && count == 0);
    {
        static const unsigned char invalid[] = {0, '\n', '\t', 255};
        Token t = {TOKEN_ERROR, invalid, sizeof invalid, 1, 1, "Invalid byte"};
        assert(analysis_lexeme_text(&t, full, sizeof full) == 12);
        assert(strcmp(full, "\\x00\\n\\t\\xFF") == 0);
    }
    {
        unsigned char *large = malloc(250005);
        assert(large != NULL); memset(large, 'a', 250000); memcpy(large + 250000, "abab", 4);
        assert(analysis_scan(&a, large, 250004, NULL, NULL) == ANALYSIS_OK);
        assert(analysis_filter(&a, FILTER_IDENTIFIERS, "aabab", &rows, &count) && count == 1);
        free(large);
    }
    free(rows); analysis_free(&a); analysis_free(&a);
    puts("Analysis integration checks passed: scanner results, aggregates, filters, CSV, cancellation, empty input and long lexemes.");
    return 0;
}
