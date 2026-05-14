from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import vulpcode.tools  # noqa: F401  (registers tools)
from vulpcode.tools import get_tool


@pytest.mark.asyncio
async def test_grep_multiline(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")
    cls = get_tool("Grep")
    res = await cls().run(
        cls.Input(
            pattern=r"def \w+\(\):\n\s+pass",
            path=str(tmp_path),
            multiline=True,
        )
    )
    # Either backend should match the multiline pattern
    assert res.is_error is False
    assert "foo" in res.output or "bar" in res.output


@pytest.mark.asyncio
async def test_grep_head_limit(tmp_path: Path):
    f = tmp_path / "lots.py"
    f.write_text("\n".join(f"hit_{i}" for i in range(50)))
    cls = get_tool("Grep")
    res = await cls().run(
        cls.Input(pattern="hit_", path=str(tmp_path), head_limit=5)
    )
    assert res.is_error is False
    # 5 content lines + at most one trailing truncation note
    assert res.output.count("\n") <= 6


@pytest.mark.asyncio
async def test_grep_lookahead(tmp_path: Path):
    f = tmp_path / "look.py"
    f.write_text(
        "def keep_me_alpha():\n"
        "    return 1\n"
        "def drop_me_beta():\n"
        "    return 2\n"
    )
    cls = get_tool("Grep")
    # Match `def NAME` only when followed somewhere by "alpha"
    res = await cls().run(
        cls.Input(
            pattern=r"def \w+(?=.*alpha)",
            path=str(tmp_path),
        )
    )
    assert res.is_error is False
    assert "keep_me_alpha" in res.output
    assert "drop_me_beta" not in res.output


@pytest.mark.asyncio
async def test_grep_case_insensitive(tmp_path: Path):
    f = tmp_path / "ci.txt"
    f.write_text("Hello\nhello\nHELLO\n")
    cls = get_tool("Grep")
    res = await cls().run(
        cls.Input(pattern="hello", path=str(tmp_path), **{"-i": True})
    )
    assert res.is_error is False
    # All three variants should match under case-insensitive search
    assert res.output.lower().count("hello") >= 3


def _fake_proc(stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.returncode = returncode
    return proc


@pytest.mark.asyncio
async def test_grep_uses_ripgrep_backend_when_available(tmp_path: Path):
    """Force the rg backend on; assert flags are forwarded and output parsed."""
    cls = get_tool("Grep")
    captured: dict = {}

    async def fake_create(*cmd, **_kw):
        captured["cmd"] = cmd
        return _fake_proc(stdout=b"sample.py:1:def foo():\n")

    with patch("vulpcode.tools.grep.shutil.which", return_value="/usr/bin/rg"), patch(
        "vulpcode.tools.grep.asyncio.create_subprocess_exec",
        side_effect=fake_create,
    ):
        res = await cls().run(
            cls.Input(
                pattern="def",
                path=str(tmp_path),
                glob="*.py",
                multiline=True,
                **{"-i": True, "-C": 2},
            )
        )

    assert res.is_error is False
    assert res.metadata["backend"] == "ripgrep"
    assert "def foo()" in res.output
    cmd = captured["cmd"]
    assert cmd[0] == "rg"
    assert "-i" in cmd
    assert "-U" in cmd
    assert "--multiline-dotall" in cmd
    assert "-g" in cmd and "*.py" in cmd
    assert "-C" in cmd and "2" in cmd


@pytest.mark.asyncio
async def test_grep_ripgrep_no_matches(tmp_path: Path):
    cls = get_tool("Grep")

    async def fake_create(*_cmd, **_kw):
        return _fake_proc(stdout=b"", returncode=1)

    with patch("vulpcode.tools.grep.shutil.which", return_value="/usr/bin/rg"), patch(
        "vulpcode.tools.grep.asyncio.create_subprocess_exec",
        side_effect=fake_create,
    ):
        res = await cls().run(cls.Input(pattern="xx", path=str(tmp_path)))

    assert res.is_error is False
    assert "No matches" in res.output


@pytest.mark.asyncio
async def test_grep_ripgrep_error(tmp_path: Path):
    cls = get_tool("Grep")

    async def fake_create(*_cmd, **_kw):
        return _fake_proc(stdout=b"", stderr=b"rg: bad regex", returncode=2)

    with patch("vulpcode.tools.grep.shutil.which", return_value="/usr/bin/rg"), patch(
        "vulpcode.tools.grep.asyncio.create_subprocess_exec",
        side_effect=fake_create,
    ):
        res = await cls().run(cls.Input(pattern="xx", path=str(tmp_path)))

    assert res.is_error is True
    assert "bad regex" in (res.error or "")


@pytest.mark.asyncio
async def test_grep_ripgrep_files_with_matches(tmp_path: Path):
    cls = get_tool("Grep")

    async def fake_create(*_cmd, **_kw):
        return _fake_proc(stdout=b"a.py\nb.py\n")

    with patch("vulpcode.tools.grep.shutil.which", return_value="/usr/bin/rg"), patch(
        "vulpcode.tools.grep.asyncio.create_subprocess_exec",
        side_effect=fake_create,
    ):
        res = await cls().run(
            cls.Input(
                pattern="x",
                path=str(tmp_path),
                output_mode="files_with_matches",
            )
        )

    assert res.is_error is False
    assert "a.py" in res.output
    assert "b.py" in res.output


@pytest.mark.asyncio
async def test_grep_ripgrep_count_mode_with_head_limit(tmp_path: Path):
    cls = get_tool("Grep")

    async def fake_create(*_cmd, **_kw):
        body = "\n".join(f"file{i}.py:3" for i in range(10)) + "\n"
        return _fake_proc(stdout=body.encode())

    with patch("vulpcode.tools.grep.shutil.which", return_value="/usr/bin/rg"), patch(
        "vulpcode.tools.grep.asyncio.create_subprocess_exec",
        side_effect=fake_create,
    ):
        res = await cls().run(
            cls.Input(
                pattern="x",
                path=str(tmp_path),
                output_mode="count",
                head_limit=3,
            )
        )

    assert res.is_error is False
    assert "truncated to 3" in res.output
