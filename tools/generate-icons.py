"""Render the EDGE E mark from rectangles, without editing reference images."""
from pathlib import Path
import struct
import zlib

ROOT=Path(__file__).resolve().parent.parent
def icon(size):
    rows=[]
    for y in range(size):
        row=bytearray([0])
        for x in range(size):
            px,py=x/size,y/size
            mark=(.29<=px<.39 and .25<=py<.75) or (.29<=px<.71 and (.25<=py<.35 or .65<=py<.75)) or (.29<=px<.64 and .45<=py<.55)
            row.extend((255,255,255) if mark else (61,52,224))
        rows.append(row)
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),9))+chunk(b'IEND',b'')

(ROOT/'ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-512@2x.png').write_bytes(icon(1024))
for density,size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
    folder=ROOT/f'android/app/src/main/res/mipmap-{density}'
    for name in ('ic_launcher.png','ic_launcher_round.png','ic_launcher_foreground.png'):(folder/name).write_bytes(icon(size))
print('Rendered EDGE app icons.')
