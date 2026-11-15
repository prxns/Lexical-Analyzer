CC = gcc
CFLAGS = -std=c11 -Wall -Wextra -Wpedantic -Werror -O2
CPPFLAGS = -Iinclude
PYTHON = python3
EXE = build/lexical_analyzer

.PHONY: all test demo clean
all: $(EXE)

$(EXE): src/main.c src/lexer.c include/lexer.h
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c src/lexer.c -o $(EXE)

build/test_analysis: tests/test_analysis.c src/analysis.c src/lexer.c include/analysis.h include/lexer.h
	mkdir -p build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_analysis.c src/analysis.c src/lexer.c -o build/test_analysis

test: $(EXE) build/test_analysis
	$(PYTHON) tests/test_lexer.py --exe $(EXE)
	./build/test_analysis

demo: $(EXE)
	./$(EXE) samples/demo.c

clean:
	rm -f $(EXE) build/test_analysis
