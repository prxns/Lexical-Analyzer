#ifndef LEXER_H
#define LEXER_H

#include <stddef.h>

typedef enum {
    TOKEN_KEYWORD, TOKEN_IDENTIFIER, TOKEN_INTEGER, TOKEN_FLOAT,
    TOKEN_STRING, TOKEN_CHARACTER, TOKEN_OPERATOR, TOKEN_PUNCTUATOR,
    TOKEN_ERROR, TOKEN_EOF
} TokenKind;

/* A token borrows its lexeme from the input; no allocation is performed. */
typedef struct {
    TokenKind kind;
    const unsigned char *lexeme;
    size_t length, line, column;
    const char *message;
} Token;

typedef struct {
    const unsigned char *source;
    size_t length, position, line, column;
} Lexer;

void lexer_init(Lexer *lexer, const unsigned char *source, size_t length);
Token lexer_next(Lexer *lexer);
const char *token_kind_name(TokenKind kind);

#endif
