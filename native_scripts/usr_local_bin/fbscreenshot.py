import sys, struct, zlib

def write_png(filename, width, height, rgba_data):
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0) # filter None
        row = rgba_data[y*stride:(y+1)*stride]
        for x in range(0, stride, 4):
            r, g, b = row[x], row[x+1], row[x+2]
            raw.extend((r, g, b, 255))
            
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 6)
    with open(filename, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', ihdr))
        f.write(chunk(b'IDAT', idat))
        f.write(chunk(b'IEND', b''))

out_file = sys.argv[1] if len(sys.argv) > 1 else '/root/screen.png'
page_size = 480 * 854 * 4

best_buf = None
best_score = -1

with open('/dev/graphics/fb0', 'rb') as f:
    all_data = f.read(page_size * 3)
    for offset in range(0, len(all_data), page_size):
        part = all_data[offset:offset+page_size]
        if len(part) == page_size:
            # Score by RGB brightness (ignoring alpha)
            score = 0
            for i in range(0, len(part), 16):
                r, g, b = part[i], part[i+1], part[i+2]
                score += (r + g + b)
            if score > best_score:
                best_score = score
                best_buf = part

if best_buf is None:
    best_buf = all_data[:page_size]

write_png(out_file, 480, 854, best_buf)
print(f'Saved {out_file} (best_score={best_score})')
