import pytest
from vulpcode.tools import get_tool
import vulpcode.tools.write_pdf  # noqa: F401  (registers WritePdf)

pypdf = pytest.importorskip("pypdf")
# Require at least one PDF backend
pytest.importorskip("reportlab", reason="reportlab (or weasyprint) required for WritePdf")


@pytest.mark.asyncio
async def test_write_pdf_simple_markdown(tmp_path):
    cls = get_tool("WritePdf")
    target = tmp_path / "doc.pdf"
    res = await cls().run(cls.Input(
        file_path=str(target),
        markdown="# Hello\n\nThis is a paragraph.\n",
        title="Test Doc",
    ))
    assert res.is_error is False
    assert target.exists()
    assert target.stat().st_size > 100


@pytest.mark.asyncio
async def test_write_pdf_output_is_valid_pdf(tmp_path):
    cls = get_tool("WritePdf")
    target = tmp_path / "valid.pdf"
    res = await cls().run(cls.Input(
        file_path=str(target),
        markdown="## Section\n\nContent here.\n",
    ))
    assert res.is_error is False
    # Verify it's a real PDF
    import io
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(target.read_bytes()))
    assert reader.get_num_pages() >= 1
