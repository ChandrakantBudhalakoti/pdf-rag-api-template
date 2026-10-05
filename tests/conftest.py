import shutil
from pathlib import Path

import pytest

PDF_DIR = Path(__file__).resolve().parents[1] / "data" / "pdfs"
SAMPLE_PDFS = (
    "brightleaf_company_profile.pdf",
    "brightleaf_employee_handbook.pdf",
    "brightleaf_support_and_refund_policy.pdf",
)


@pytest.fixture
def sample_pdf_dir(tmp_path: Path) -> Path:
    """A folder with exactly the three sample PDFs, so extra files in data/pdfs don't affect tests."""
    folder = tmp_path / "pdfs"
    folder.mkdir()
    for name in SAMPLE_PDFS:
        shutil.copy(PDF_DIR / name, folder / name)
    return folder
