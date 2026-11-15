"""Windows-only integration tests of the real native application.

The test process targets only windows belonging to the child executable it starts.
No tokenization is implemented here: expected aggregates come from the real CLI.
Screenshots are actual OS PrintWindow captures, encoded losslessly as PNG.
"""
import argparse
import csv
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
if os.name != 'nt':
    raise SystemExit('Native GUI integration tests require Windows')
U = C.WinDLL('user32', use_last_error=True)
G = C.WinDLL('gdi32', use_last_error=True)
CALLBACK = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
U.EnumWindows.argtypes = [CALLBACK, W.LPARAM]
U.EnumChildWindows.argtypes = [W.HWND, CALLBACK, W.LPARAM]
U.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
U.GetWindowThreadProcessId.restype = W.DWORD
U.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
U.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
U.GetWindowTextLengthW.argtypes = [W.HWND]
U.GetDlgItem.argtypes = [W.HWND, C.c_int]
U.GetDlgItem.restype = W.HWND
U.GetDlgCtrlID.argtypes = [W.HWND]
U.GetParent.argtypes = [W.HWND]
U.GetParent.restype = W.HWND
U.IsWindowVisible.argtypes = [W.HWND]
U.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
U.SendMessageW.restype = C.c_ssize_t
U.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
U.PostMessageW.restype = W.BOOL
U.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
U.GetWindowDC.argtypes = [W.HWND]
U.GetWindowDC.restype = W.HDC
U.ReleaseDC.argtypes = [W.HWND, W.HDC]
U.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
U.PrintWindow.restype = W.BOOL
U.SetWindowPos.argtypes = [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT]
U.UpdateWindow.argtypes = [W.HWND]
G.CreateCompatibleDC.argtypes = [W.HDC]
G.CreateCompatibleDC.restype = W.HDC
G.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
G.CreateCompatibleBitmap.restype = W.HBITMAP
G.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
G.SelectObject.restype = W.HGDIOBJ
G.DeleteObject.argtypes = [W.HGDIOBJ]
G.DeleteDC.argtypes = [W.HDC]
G.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT]


def window_text(hwnd):
    length = U.SendMessageW(hwnd, 0x000E, 0, 0)
    buffer = C.create_unicode_buffer(max(1, length + 1))
    U.SendMessageW(hwnd, 0x000D, len(buffer), C.cast(buffer, C.c_void_p).value)
    return buffer.value


def class_name(hwnd):
    buffer = C.create_unicode_buffer(256)
    U.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def descendants(hwnd):
    items = []
    callback = CALLBACK(lambda child, _: items.append(child) or True)
    U.EnumChildWindows(hwnd, callback, 0)
    return items


def owned_windows(pid):
    items = []
    def visit(hwnd, _):
        owner = W.DWORD()
        U.GetWindowThreadProcessId(hwnd, C.byref(owner))
        if owner.value == pid:
            items.append(hwnd)
        return True
    U.EnumWindows(CALLBACK(visit), 0)
    return items


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.04)
    raise AssertionError('Timed out waiting for the native application')


def send_text(hwnd, value):
    buffer = C.create_unicode_buffer(value)
    U.SendMessageW(hwnd, 0x000C, 0, C.cast(buffer, C.c_void_p).value)


def png_capture(hwnd, output):
    rect = W.RECT()
    assert U.GetWindowRect(hwnd, C.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    U.UpdateWindow(hwnd)
    time.sleep(.15)
    dc = U.GetWindowDC(hwnd)
    memory = G.CreateCompatibleDC(dc)
    bitmap = G.CreateCompatibleBitmap(dc, width, height)
    old = G.SelectObject(memory, bitmap)
    try:
        assert U.PrintWindow(hwnd, memory, 2), 'Windows could not capture the rendered application'
        G.SelectObject(memory, old)
        header = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, width*height*4, 0, 0, 0, 0)
        info = C.create_string_buffer(header + bytes(12))
        pixels = C.create_string_buffer(width*height*4)
        assert G.GetDIBits(memory, bitmap, 0, height, pixels, info, 0) == height
        bgra = pixels.raw
        rgb = bytearray(width*height*3)
        rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
        rows = b''.join(b'\x00' + rgb[y*width*3:(y+1)*width*3] for y in range(height))
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data) & 0xFFFFFFFF)
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0)) + chunk(b'IDAT',zlib.compress(rows)) + chunk(b'IEND',b'')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(png)
        assert len(png) > 15000, 'The screenshot is unexpectedly blank'
    finally:
        G.SelectObject(memory, old)
        G.DeleteObject(bitmap)
        G.DeleteDC(memory)
        U.ReleaseDC(hwnd, dc)


class GuiTests(unittest.TestCase):
    exe = ROOT/'build/LexicalAnalyzer.exe'
    cli = ROOT/'build/lexical_analyzer.exe'
    screenshots = ROOT/'build/screenshots'

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='lexical gui integration ')
        self.source = Path(self.folder.name)/'source with spaces.c'
        self.source.write_bytes((ROOT/'samples/demo.c').read_bytes())
        self.process = subprocess.Popen([str(self.exe), str(self.source)])
        self.hwnd = wait_for(lambda: next((h for h in owned_windows(self.process.pid) if class_name(h) == 'LexicalAnalyzer.Native.C11'), None))
        wait_for(lambda: 'source with spaces.c' in window_text(self.hwnd))
        U.SetWindowPos(self.hwnd,0,0,0,1440,940,0x0002|0x0004)

    def tearDown(self):
        if self.process.poll() is None:
            U.PostMessageW(self.hwnd, 0x0010, 0, 0)
            deadline = time.monotonic() + 5
            while self.process.poll() is None and time.monotonic() < deadline:
                for dialog in owned_windows(self.process.pid):
                    if class_name(dialog) == '#32770':
                        U.PostMessageW(dialog, 0x0111, 7, 0)  # discard unsaved test-only editor content
                time.sleep(.05)
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
        self.folder.cleanup()

    def control(self, identifier):
        hwnd = U.GetDlgItem(self.hwnd, identifier)
        self.assertTrue(hwnd, f'Missing control {identifier}')
        return hwnd

    def click(self, identifier):
        self.assertTrue(U.PostMessageW(self.hwnd, 0x0111, identifier, 0))

    def total(self):
        return window_text(self.control(200))

    def row_count(self, identifier=130):
        return U.SendMessageW(self.control(identifier), 0x1004, 0, 0)

    def analyze(self):
        self.click(115)
        wait_for(lambda: self.total() != '-' and window_text(self.control(141)) != 'ANALYZING')

    def expected(self, source=None):
        path = self.source if source is None else source
        p = subprocess.run([str(self.cli),'--json',str(path)],capture_output=True,timeout=10)
        self.assertIn(p.returncode,(0,1))
        return json.loads(p.stdout)

    def assert_stats(self, data):
        s = data['summary']
        expected = [s['total'],s['Keyword'],s['Identifier'],sum(s[k] for k in ['Integer','Float','String','Character']),s['Operator'],s['Punctuator'],s['errors']]
        self.assertEqual([window_text(self.control(200+i)) for i in range(7)],[str(n) for n in expected])
        self.assertEqual(self.row_count(),len(data['tokens']))
        self.assertEqual(self.row_count(131),s['errors'])

    def choose_dialog_file(self, title, path):
        dialog = wait_for(lambda: next((h for h in owned_windows(self.process.pid) if class_name(h) == '#32770' and window_text(h) == title), None))
        def find_name():
            edits=[h for h in descendants(dialog) if class_name(h).lower() == 'edit' and U.IsWindowVisible(h)]
            prefilled=next((h for h in edits if window_text(h).lower().endswith('.csv')),None)
            if prefilled:
                return prefilled
            exact=next((h for h in edits if U.GetDlgCtrlID(h)==0x480 or U.GetDlgCtrlID(U.GetParent(h))==0x47C),None)
            if exact:
                return exact
            return next((h for h in edits if U.GetDlgCtrlID(h)==1001),None)
        try:
            name=wait_for(find_name,5)
        except AssertionError:
            print('FILE DIALOG CONTROLS:',[(class_name(h),U.GetDlgCtrlID(h),window_text(h)[:160]) for h in descendants(dialog)],flush=True)
            png_capture(dialog,self.screenshots/('dialog-'+title.replace(' ','-')+'.png'))
            raise
        buffer=C.create_unicode_buffer(str(path))
        U.SendMessageW(name,0x00B1,0,-1)  # EM_SETSEL
        U.SendMessageW(name,0x00C2,1,C.cast(buffer,C.c_void_p).value)  # EM_REPLACESEL
        parent=U.GetParent(name)
        if class_name(parent).lower()=='combobox':
            send_text(parent,str(path))
        U.SendMessageW(parent,0x0111,U.GetDlgCtrlID(name)|(0x0300<<16),name)
        print('FILE NAME SET:',title,'id',U.GetDlgCtrlID(name),'parent',class_name(parent),'value',window_text(name),flush=True)
        # Explorer dialogs commit their filename edit on focus change; use the
        # actual dialog button after the edit has accepted the text.
        time.sleep(.15)
        U.PostMessageW(U.GetDlgItem(dialog,1),0x00F5,0,0)
        return dialog

    def test_01_native_launch_and_controls(self):
        data = self.exe.read_bytes()
        pe = struct.unpack_from('<I',data,0x3C)[0]
        self.assertEqual(data[pe:pe+4],b'PE\x00\x00')
        self.assertEqual(struct.unpack_from('<H',data,pe+24+68)[0],2,'The GUI must use the Windows subsystem, without a console')
        for control in [100,110,111,112,113,114,115,116,117,120,121,130,131,140,141]:
            self.control(control)
        self.assertEqual(self.total(),'-')
        self.assertIn('int main',window_text(self.control(100)))
        png_capture(self.hwnd,self.screenshots/'gui-ready.png')

    def test_02_actual_demo_results(self):
        self.analyze()
        self.assert_stats(self.expected())
        self.assertIn('Analysis completed',window_text(self.control(140)))
        png_capture(self.hwnd,self.screenshots/'gui-demo.png')

    def test_03_load_sample_button(self):
        self.click(112)
        wait_for(lambda: 'demo.c' in window_text(self.hwnd))
        self.analyze()
        self.assert_stats(self.expected(ROOT/'samples/demo.c'))

    def test_04_error_sample_and_diagnostics(self):
        self.click(113)
        wait_for(lambda: 'errors.c' in window_text(self.hwnd))
        self.analyze()
        self.assert_stats(self.expected(ROOT/'samples/errors.c'))
        self.assertIn('Errors detected',window_text(self.control(140)))
        png_capture(self.hwnd,self.screenshots/'gui-errors.png')

    def test_05_search_and_category_intersection(self):
        self.analyze()
        U.SendMessageW(self.control(121),0x014E,1,0)
        U.PostMessageW(self.hwnd,0x0111,121 | (1<<16),self.control(121))
        wait_for(lambda:self.row_count()==15)
        send_text(self.control(120),'RETURN')
        wait_for(lambda:self.row_count()==1)
        self.assertEqual(self.total(),'128')
        send_text(self.control(120),'no_such_token')
        wait_for(lambda:self.row_count()==0)
        png_capture(self.hwnd,self.screenshots/'gui-filtered.png')

    def test_06_clear_results_retains_source(self):
        self.analyze()
        original = window_text(self.control(100))
        self.click(116)
        wait_for(lambda:self.total()=='-')
        self.assertEqual(self.row_count(),0)
        self.assertEqual(window_text(self.control(100)),original)

    def test_07_clear_editor_and_empty_analysis(self):
        self.click(114)
        wait_for(lambda:window_text(self.control(100))=='')
        self.analyze()
        self.assertEqual([window_text(self.control(200+i)) for i in range(7)],['0']*7)
        self.assertEqual(self.row_count(),0)
        png_capture(self.hwnd,self.screenshots/'gui-empty.png')

    def test_08_save_file(self):
        send_text(self.control(100),'int saved = 42;\r\n')
        self.click(111)
        wait_for(lambda:'Source saved' in window_text(self.control(140)))
        self.assertEqual(self.source.read_text().strip(),'int saved = 42;')
        self.analyze()
        self.assert_stats(self.expected())

    def test_09_open_file_dialog(self):
        target = Path(self.folder.name)/'another source.c'
        target.write_text('float changed = 2e-3;')
        self.click(110)
        self.choose_dialog_file('Open C Source',target)
        wait_for(lambda:'another source.c' in window_text(self.hwnd))
        self.analyze()
        self.assert_stats(self.expected(target))

    def test_10_export_actual_csv(self):
        self.analyze()
        target = Path(self.folder.name)/'actual results.csv'
        self.click(117)
        self.choose_dialog_file('Export Analysis Results',target)
        try:
            wait_for(lambda:target.exists() and 'Results exported' in window_text(self.control(140)))
        except AssertionError:
            print('EXPORT STATUS:',window_text(self.control(140)),flush=True)
            for dialog in owned_windows(self.process.pid):
                if class_name(dialog)=='#32770':
                    print('EXPORT DIALOG:',window_text(dialog),[(class_name(h),U.GetDlgCtrlID(h),window_text(h)[:160]) for h in descendants(dialog)],flush=True)
                    png_capture(dialog,self.screenshots/'dialog-export-failure.png')
            raise
        with target.open(newline='',encoding='utf-8') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),128)
        self.assertEqual(rows[0]['Lexeme'],'#')
        self.assertEqual(rows[0]['Token Category'],'Punctuator')
        (self.screenshots.parent/'gui-export-results.csv').write_bytes(target.read_bytes())

    def test_11_edit_invalidates_results_and_worker_stays_responsive(self):
        self.analyze()
        send_text(self.control(100),'a'*2500000)
        self.assertEqual(self.total(),'-')
        self.click(115)
        # A real synchronous query must return while the worker is active.
        started=time.monotonic()
        self.assertTrue(self.control(100))
        self.assertLess(time.monotonic()-started,2)
        send_text(self.control(100),'int latest = 1;')
        wait_for(lambda:window_text(self.control(141)) != 'ANALYZING')
        # The worker may start after the edit or finish before it. Both are
        # valid, but an old one-token result must never survive the new edit.
        self.assertIn(self.total(),('-','5'))
        if self.total()=='-':
            self.analyze()
        self.assertEqual(self.total(),'5')

    def test_12_cancel_and_resize(self):
        send_text(self.control(100),'a'*3000000)
        self.click(115)
        self.click(115)
        wait_for(lambda:'cancelled' in window_text(self.control(140)).lower())
        self.assertEqual(self.total(),'-')
        self.assertTrue(U.SetWindowPos(self.hwnd,0,0,0,1100,760,0x0002|0x0004))
        self.assertTrue(self.control(117))
        self.assertTrue(U.SetWindowPos(self.hwnd,0,0,0,1440,940,0x0002|0x0004))

    def test_13_double_click_locates_token(self):
        self.analyze()
        listing=self.control(130)
        header=U.SendMessageW(listing,0x101F,0,0)
        rect=W.RECT(); U.GetWindowRect(header,C.byref(rect))
        position=(20 & 0xFFFF)|((rect.bottom-rect.top+10)<<16)
        U.PostMessageW(listing,0x0201,1,position)
        U.PostMessageW(listing,0x0202,0,position)
        U.PostMessageW(listing,0x0203,1,position)
        wait_for(lambda:U.SendMessageW(self.control(100),0x00B0,0,0) != 0)
        selection=U.SendMessageW(self.control(100),0x00B0,0,0)
        self.assertEqual(selection & 0xFFFF,0)
        self.assertEqual((selection>>16)&0xFFFF,1)


class Recorded(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.passed=[]
    def addSuccess(self,test):
        super().addSuccess(test)
        self.passed.append(test.id().split('.')[-1])


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--exe',type=Path,default=GuiTests.exe)
    p.add_argument('--cli',type=Path,default=GuiTests.cli)
    p.add_argument('--screenshots',type=Path,default=GuiTests.screenshots)
    p.add_argument('--report',type=Path,default=ROOT/'build/gui-test-results.json')
    a=p.parse_args()
    GuiTests.exe=a.exe.resolve(); GuiTests.cli=a.cli.resolve(); GuiTests.screenshots=a.screenshots.resolve()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Recorded).run(unittest.defaultTestLoader.loadTestsFromTestCase(GuiTests))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps({'tests_run':result.testsRun,'successful':result.wasSuccessful(),
        'passed':result.passed,'failures':[(str(t),m) for t,m in result.failures],
        'errors':[(str(t),m) for t,m in result.errors],
        'executable_sha256':hashlib.sha256(GuiTests.exe.read_bytes()).hexdigest()},indent=2)+'\n',encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
