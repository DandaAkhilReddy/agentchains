import pathlib, base64, sys
b = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip()
data = base64.b64decode(b)
p = pathlib.Path(sys.argv[2])
p.write_bytes(data)
print(f"Written {p.stat().st_size} bytes to {p}")
