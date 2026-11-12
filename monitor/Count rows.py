"""Count ALL rows in a daily zip, and how many have DE in territorial_scope. Do not commit."""
import sys
import tempfile
import zipfile
from pathlib import Path

import duckdb

total = with_de = empty_scope = 0
with zipfile.ZipFile(sys.argv[1]) as outer:
    for name in sorted(i.filename for i in outer.infolist() if not i.is_dir()):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(outer.extract(name, tmp))
            if path.suffix.lower() == ".zip":
                with zipfile.ZipFile(path) as inner:
                    inner.extractall(Path(tmp) / "x")
                path.unlink()
                files = list((Path(tmp) / "x").rglob("*.csv"))
            else:
                files = [path]
            for f in files:
                src = f"read_csv('{f.as_posix()}', all_varchar=true, null_padding=true)"
                t, d, e = duckdb.sql(
                    f"SELECT count(*), "
                    f"count(*) FILTER (WHERE territorial_scope LIKE '%\"DE\"%'), "
                    f"count(*) FILTER (WHERE coalesce(territorial_scope, '[]') = '[]') FROM {src}"
                ).fetchall()[0]
                total += t; with_de += d; empty_scope += e
print("all rows:", total)
print("rows with DE in scope:", with_de)
print("rows with empty scope:", empty_scope)
print("rows without DE:", total - with_de)