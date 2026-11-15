"""Verify the Windows package without executing or simulating the GUI."""
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
data=(ROOT/'dist/LexicalAnalyzer.exe').read_bytes()
assert data[:2]==b'MZ'
pe=struct.unpack_from('<I',data,0x3C)[0]
assert data[pe:pe+4]==b'PE\0\0'
machine,sections=struct.unpack_from('<HH',data,pe+4)
assert machine==0x8664,'Expected a Windows x64 package'
optional_size=struct.unpack_from('<H',data,pe+20)[0]
optional=pe+24
assert struct.unpack_from('<H',data,optional)[0]==0x20B
assert struct.unpack_from('<H',data,optional+68)[0]==2,'GUI must not create a console'
table=optional+optional_size
def file_offset(rva):
    for i in range(sections):
        entry=table+i*40
        virtual_size,virtual_address,raw_size,raw_offset=struct.unpack_from('<IIII',data,entry+8)
        if virtual_address <= rva < virtual_address+max(virtual_size,raw_size):
            return raw_offset+rva-virtual_address
    raise AssertionError('Invalid executable directory RVA')
imports=struct.unpack_from('<I',data,optional+112+8)[0]
position=file_offset(imports)
libraries=[]
while any(data[position:position+20]):
    name_rva=struct.unpack_from('<I',data,position+12)[0]
    name_at=file_offset(name_rva)
    libraries.append(data[name_at:data.index(b'\0',name_at)].decode('ascii').lower())
    position+=20
allowed={'kernel32.dll','user32.dll','gdi32.dll','comctl32.dll','comdlg32.dll',
         'shell32.dll','uxtheme.dll','dwmapi.dll','msvcrt.dll','ucrtbase.dll',
         'advapi32.dll','ole32.dll','oleaut32.dll','rpcrt4.dll','ntdll.dll'}
assert all(name in allowed or name.startswith('api-ms-win-') for name in libraries),libraries
assert b'PerMonitorV2' in data and b'asInvoker' in data
for name in ['demo.c','errors.c']:
    assert (ROOT/'dist/samples'/name).read_bytes().replace(b'\r\n',b'\n')==(ROOT/'samples'/name).read_bytes().replace(b'\r\n',b'\n')
assert (ROOT/'dist/run.bat').is_file() and (ROOT/'run.bat').is_file()
assert (ROOT/'dist/lexical_analyzer.exe').is_file()
print('Windows x64 GUI package verified: console-free subsystem, per-monitor DPI manifest, system DLLs only, both real samples and preserved CLI.')
print('Imported system libraries:',', '.join(libraries))
