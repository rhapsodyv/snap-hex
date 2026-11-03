"""Copy into web/generator/ the generator files the configurator runs in the browser and
list them in web/generator/files.json (paths from web/), so web/ is the whole static
site once pre/ is built too (engine.py pregenerate). Run it again after changing the
generator: python3 web/package.py"""

import json
import shutil
from pathlib import Path

WEB = Path(__file__).parent
GENERATOR = WEB.parent / "generator"
# what engine.py imports, and what they import (build.py, render.py and the validation are not needed)
FILES = ["params.py", "configure.py", "layout.py", "profiles.py", "grid.py", "plug.py", "assembly.py"]


def main():
    out = WEB / "generator"
    if out.is_dir():
        shutil.rmtree(out)
    out.mkdir()
    for f in FILES:
        shutil.copyfile(GENERATOR / f, out / f)
    (out / "files.json").write_text(json.dumps([f"generator/{f}" for f in FILES], indent=1))
    print(f"{len(FILES)} files in {out}")


if __name__ == "__main__":
    main()
