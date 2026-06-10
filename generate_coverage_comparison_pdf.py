"""Generate SEO_GEO_Coverage_Comparison.pdf from the markdown source.

Usage:
    python3 generate_coverage_comparison_pdf.py [output.pdf]

Default output:
    ~/Documents/Heuristics AI LLC/SEOGEO Audit/SEO_GEO_Coverage_Comparison.pdf
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "SEO_GEO_Coverage_Comparison.md"
DEFAULT_OUT = Path.home() / "Documents" / "Heuristics AI LLC" / "SEOGEO Audit" / "SEO_GEO_Coverage_Comparison.pdf"


def main() -> None:
    out = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(ROOT / "generate_pdf.py"), str(SRC), str(out)],
        check=True,
    )


if __name__ == "__main__":
    main()
