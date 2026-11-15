"""Black-box tests of the C executable; Python standard library only."""
import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = """auto break case char const continue default do double else enum extern
float for goto if inline int long register restrict return short signed sizeof
static struct switch typedef union unsigned void volatile while _Alignas _Alignof
_Atomic _Bool _Complex _Generic _Imaginary _Noreturn _Static_assert _Thread_local""".split()


class LexerTests(unittest.TestCase):
    executable = None

    def invoke(self, source, expected_status=0):
        if isinstance(source, str):
            source = source.encode('ascii')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input with spaces.c'
            path.write_bytes(source)
            process = subprocess.run([str(self.executable), '--json', str(path)],
                                     capture_output=True, timeout=15)
        self.assertEqual(process.returncode, expected_status, process.stderr.decode(errors='replace'))
        self.assertEqual(process.stderr, b'')
        result = json.loads(process.stdout)
        self.assertEqual([t['number'] for t in result['tokens']], list(range(1, len(result['tokens']) + 1)))
        self.assertEqual(result['summary']['total'] + result['summary']['errors'], len(result['tokens']))
        self.assertEqual(sum(v for k, v in result['summary'].items() if k not in ('total', 'errors')),
                         result['summary']['total'])
        return result

    def expect(self, source, pairs):
        tokens = self.invoke(source)['tokens']
        self.assertEqual([(t['lexeme'], t['category']) for t in tokens], pairs)
        return tokens

    def test_01_all_c11_keywords(self):
        self.assertEqual(len(KEYWORDS), 44)
        self.expect(' '.join(KEYWORDS), [(k, 'Keyword') for k in KEYWORDS])

    def test_02_identifiers_and_keyword_boundaries(self):
        names = ['total', 'student_name', '_value', 'number123', 'Int', 'integer', 'int2', '_AtomicX', '_']
        self.expect(' '.join(names), [(n, 'Identifier') for n in names])

    def test_03_integer_forms(self):
        values = ['0', '100', '075', '0x2A', '0Xff', '25U', '7u', '42L', '3ll', '1ULL', '1llu', '0UL']
        self.expect(' '.join(values), [(n, 'Integer') for n in values])

    def test_04_floating_forms(self):
        values = ['3.14', '.5', '10.0', '2e-3', '1.', '1E+2', '0.5f', '1e2L', '08.5', '.5e-1F']
        self.expect(' '.join(values), [(n, 'Float') for n in values])

    def test_05_string_escapes(self):
        values = ['""', '"hello world"', r'"line\n\t\"\\"', r'"\a\b\f\r\v\?\047\x41"']
        self.expect(' '.join(values), [(n, 'String') for n in values])

    def test_06_character_escapes(self):
        values = ["'A'", r"'\n'", r"'\''", r"'\\'", r"'\123'", r"'\x41'"]
        self.expect(' '.join(values), [(n, 'Character') for n in values])

    def test_07_operators(self):
        operators = '+ - * / % < > <= >= == != && || ! = += -= *= /= %= ++ -- & | ^ ~ << >> -> ? : &= |= ^= <<= >>='.split()
        self.expect(' '.join(operators), [(n, 'Operator') for n in operators])

    def test_08_maximal_munch_without_whitespace(self):
        self.expect('a>>=2;b+++c;d->x!=0;', [
            ('a', 'Identifier'), ('>>=', 'Operator'), ('2', 'Integer'), (';', 'Punctuator'),
            ('b', 'Identifier'), ('++', 'Operator'), ('+', 'Operator'), ('c', 'Identifier'),
            (';', 'Punctuator'), ('d', 'Identifier'), ('->', 'Operator'), ('x', 'Identifier'),
            ('!=', 'Operator'), ('0', 'Integer'), (';', 'Punctuator')])

    def test_09_punctuators_and_digraphs(self):
        values = ['(', ')', '{', '}', '[', ']', ',', ';', '.', '...', '#', '##', '<:', ':>', '<%', '%>', '%:', '%:%:']
        self.expect(' '.join(values), [(n, 'Punctuator') for n in values])

    def test_10_comments_and_whitespace(self):
        self.expect(' \t\v\f// keyword int\n/* a ** / x */ int/*c*/x;//end', [('int', 'Keyword'), ('x', 'Identifier'), (';', 'Punctuator')])

    def test_11_comment_markers_inside_literals(self):
        self.expect('"/*not*/ //comment" \'/\'', [('"/*not*/ //comment"', 'String'), ("'/'", 'Character')])

    def test_12_line_and_column_positions(self):
        tokens = self.invoke('int x;\n\t/*note\nxx*/ x += 2;')['tokens']
        self.assertEqual([(t['lexeme'], t['line'], t['column']) for t in tokens], [
            ('int', 1, 1), ('x', 1, 5), (';', 1, 6), ('x', 3, 6), ('+=', 3, 8), ('2', 3, 11), (';', 3, 12)])

    def test_13_crlf_and_cr(self):
        tokens = self.invoke(b'a\r\nb\rc\nd')['tokens']
        self.assertEqual([(t['line'], t['column']) for t in tokens], [(1, 1), (2, 1), (3, 1), (4, 1)])

    def test_14_empty_file(self):
        self.assertEqual(self.invoke(b'')['tokens'], [])

    def test_15_whitespace_only(self):
        self.assertEqual(self.invoke(' \t\r\n\v\f')['tokens'], [])

    def test_16_comment_only_and_comment_at_eof(self):
        for source in ['// end', '/* end */', '/**/', '/* outer /* inner */']:
            with self.subTest(source=source):
                self.assertEqual(self.invoke(source)['tokens'], [])

    def test_17_invalid_bytes(self):
        result = self.invoke(b'@`$\x00\xff', 1)
        self.assertEqual(result['summary']['errors'], 5)
        self.assertEqual([t['column'] for t in result['tokens']], [1, 2, 3, 4, 5])

    def test_18_unterminated_string(self):
        for source in ['"hello', '"abc\\', '"abc\nint x;']:
            with self.subTest(source=source):
                token = self.invoke(source, 1)['tokens'][0]
                self.assertEqual(token['message'], 'Unterminated string literal')
                self.assertEqual((token['line'], token['column']), (1, 1))

    def test_19_unterminated_character(self):
        token = self.invoke("'x", 1)['tokens'][0]
        self.assertEqual(token['message'], 'Unterminated character literal')

    def test_20_unterminated_block_comment(self):
        token = self.invoke(' \n /*not closed', 1)['tokens'][0]
        self.assertEqual(token['message'], 'Unterminated block comment')
        self.assertEqual((token['line'], token['column']), (2, 2))

    def test_21_malformed_numbers(self):
        for source in ['09', '0x', '0xG', '1e', '2e+', '1.2.3', '25UU', '1lL', '123abc', '1f', '0b10', '0x1p2', '1e2u', '1lul']:
            with self.subTest(source=source):
                self.assertEqual(self.invoke(source, 1)['tokens'][0]['lexeme'], source)

    def test_22_invalid_escapes(self):
        for source in [r'"\q"', r"'\x'", r'"\u1234"', r'"\8"']:
            with self.subTest(source=source):
                self.assertEqual(self.invoke(source, 1)['tokens'][0]['category'], 'Error')

    def test_23_invalid_character_lengths(self):
        for source in ["''", "'ab'", r"'\1234'"]:
            with self.subTest(source=source):
                self.assertEqual(self.invoke(source, 1)['summary']['errors'], 1)

    def test_24_unsupported_encoded_literals(self):
        for source in ['L"hi"', 'u8"hi"', 'u"hi"', "U'A'"]:
            with self.subTest(source=source):
                token = self.invoke(source, 1)['tokens'][0]
                self.assertEqual(token['lexeme'], source)
                self.assertIn('subset', token['message'])

    def test_25_error_recovery(self):
        result = self.invoke('@ int x;\n"bad\nreturn 0;', 1)
        self.assertEqual(result['summary']['errors'], 2)
        self.assertEqual([(t['lexeme'], t['line'], t['column']) for t in result['tokens'][-3:]],
                         [('return', 3, 1), ('0', 3, 8), (';', 3, 9)])

    def test_26_each_single_symbol_at_eof(self):
        for source in ['a', '0', '/', '*', '.', '#', '+', ':', '<', '>']:
            with self.subTest(source=source):
                self.assertEqual(self.invoke(source)['tokens'][0]['lexeme'], source)

    def test_27_large_identifier_and_literal(self):
        name = 'a' * 100000
        string = '"' + 'x' * 100000 + '"'
        self.expect(name + ' ' + string, [(name, 'Identifier'), (string, 'String')])

    def test_28_large_source(self):
        result = self.invoke('int x=1;\n' * 5000)
        self.assertEqual(result['summary']['total'], 25000)
        self.assertEqual(result['tokens'][-1]['line'], 5000)

    def test_29_demo_fixture(self):
        result = self.invoke((ROOT / 'samples/demo.c').read_bytes())
        for category in ['Keyword', 'Identifier', 'Integer', 'Float', 'String', 'Character', 'Operator', 'Punctuator']:
            self.assertGreater(result['summary'][category], 0)

    def test_30_error_fixture(self):
        self.assertEqual(self.invoke((ROOT / 'samples/errors.c').read_bytes(), 1)['summary']['errors'], 6)

    def test_31_cli_usage_and_missing_file(self):
        for args in [[], ['--json'], ['a', 'b'], [str(ROOT / 'tests/definitely-not-present.c')]]:
            with self.subTest(args=args):
                process = subprocess.run([str(self.executable), *args], capture_output=True, timeout=10)
                self.assertEqual(process.returncode, 2)
                self.assertTrue(process.stderr)
        self.assertEqual(subprocess.run([str(self.executable), '--help'], capture_output=True).returncode, 0)

    def test_32_table_output(self):
        process = subprocess.run([str(self.executable), str(ROOT / 'samples/demo.c')], capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0)
        self.assertIn(b'Token summary', process.stdout)
        self.assertIn(b'Lexical errors: 0', process.stdout)

    def test_33_random_bytes_terminate_and_preserve_spans(self):
        rng = random.Random(21904)
        for case in range(120):
            source = bytes(rng.randrange(256) for _ in range(rng.randrange(1, 200)))
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'random.c'
                path.write_bytes(source)
                process = subprocess.run([str(self.executable), '--json', str(path)], capture_output=True, timeout=10)
                self.assertIn(process.returncode, (0, 1), process.stderr)
                data = json.loads(process.stdout)
                previous = (0, 0)
                for token in data['tokens']:
                    self.assertTrue(token['lexeme'])
                    position = (token['line'], token['column'])
                    self.assertGreater(position, previous)
                    previous = position

    def test_34_no_preprocessor_evaluation(self):
        self.expect('#define X 2\nX ## y', [('#', 'Punctuator'), ('define', 'Identifier'),
            ('X', 'Identifier'), ('2', 'Integer'), ('X', 'Identifier'), ('##', 'Punctuator'), ('y', 'Identifier')])

    def test_35_raw_nul_in_literal(self):
        self.assertEqual(self.invoke(b'"a\x00b"', 1)['summary']['errors'], 1)

    def test_36_signs_are_separate_tokens(self):
        self.expect('-1 +.5', [('-', 'Operator'), ('1', 'Integer'), ('+', 'Operator'), ('.5', 'Float')])


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id().split('.')[-1])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, default=ROOT / 'build' / ('lexical_analyzer.exe' if os.name == 'nt' else 'lexical_analyzer'))
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    LexerTests.executable = args.exe.resolve()
    if not LexerTests.executable.is_file():
        parser.error('Executable not found; build the C application first')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LexerTests)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'tests_run': result.testsRun, 'successful': result.wasSuccessful(),
            'passed': result.passed, 'failures': [(t.id(), msg) for t, msg in result.failures],
            'errors': [(t.id(), msg) for t, msg in result.errors]}, indent=2) + '\n', encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
