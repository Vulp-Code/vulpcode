"""NotebookEdit tool: edit cells in Jupyter .ipynb files."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from vulpcode.tools.base import Tool, ToolResult, tool


@tool(
    name="NotebookEdit",
    description=(
        "Edit cells in a Jupyter .ipynb file. Modes: replace (default), insert, "
        "delete. Cell can be located by cell_id or cell_number (0-based)."
    ),
    requires_confirm=True,
)
class NotebookEditTool(Tool):
    """Edit cells in a Jupyter ``.ipynb`` notebook.

    Three edit modes:

    - ``replace`` (default) — overwrite ``new_source`` into a target cell.
    - ``insert`` — add a new cell at the given position.
    - ``delete`` — remove a target cell.

    The target cell is located by ``cell_id`` (preferred when stable) or
    ``cell_number`` (0-based index). ``cell_type`` is required for ``insert``;
    ignored otherwise. Marked ``requires_confirm=True``.
    """

    class Input(BaseModel):
        notebook_path: str
        new_source: str = ""
        cell_id: str | None = None
        cell_number: int | None = None
        cell_type: Literal["code", "markdown"] | None = None
        edit_mode: Literal["replace", "insert", "delete"] = "replace"

        @model_validator(mode="after")
        def _check_locator(self):
            if self.edit_mode == "delete" and (self.cell_id is None and self.cell_number is None):
                raise ValueError("delete requires cell_id or cell_number")
            if self.edit_mode == "replace" and (self.cell_id is None and self.cell_number is None):
                raise ValueError("replace requires cell_id or cell_number")
            return self

    async def run(self, args: BaseModel) -> ToolResult:  # type: ignore[override]
        assert isinstance(args, NotebookEditTool.Input)
        path = Path(args.notebook_path).expanduser().resolve()
        if not path.exists():
            return ToolResult(error=f"Notebook does not exist: {path}", is_error=True)
        try:
            with path.open("r", encoding="utf-8") as fh:
                nb = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            return ToolResult(error=f"Cannot parse notebook: {exc}", is_error=True)

        cells = nb.get("cells")
        if cells is None:
            return ToolResult(error="Notebook has no 'cells' key", is_error=True)

        idx = self._find_index(cells, args)
        if args.edit_mode != "insert" and idx is None:
            return ToolResult(error="Cell not found by id or number", is_error=True)

        if args.edit_mode == "delete":
            removed = cells.pop(idx)
            metadata = {"cell_id": removed.get("id"), "removed_index": idx}
        elif args.edit_mode == "insert":
            new_cell = self._make_cell(args.cell_type or "code", args.new_source)
            insert_at = idx if idx is not None else len(cells)
            cells.insert(insert_at, new_cell)
            metadata = {"cell_id": new_cell["id"], "inserted_at": insert_at}
        else:  # replace
            cell = cells[idx]
            cell["source"] = self._split_source(args.new_source)
            if args.cell_type is not None:
                cell["cell_type"] = args.cell_type
                if args.cell_type == "markdown":
                    cell.pop("outputs", None)
                    cell.pop("execution_count", None)
            metadata = {"cell_id": cell.get("id"), "replaced_index": idx}

        try:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(nb, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
        except OSError as exc:
            return ToolResult(error=f"Failed to write: {exc}", is_error=True)

        return ToolResult(
            output=f"Notebook {path} updated ({args.edit_mode})",
            metadata={"notebook_path": str(path), "edit_mode": args.edit_mode, **metadata},
        )

    @staticmethod
    def _find_index(cells: list[dict[str, Any]], args: "NotebookEditTool.Input") -> int | None:
        if args.cell_id is not None:
            for i, c in enumerate(cells):
                if c.get("id") == args.cell_id:
                    return i
            return None
        if args.cell_number is not None:
            if 0 <= args.cell_number < len(cells):
                return args.cell_number
            return None
        return None

    @staticmethod
    def _split_source(text: str) -> list[str]:
        if not text:
            return []
        return text.splitlines(keepends=True)

    @staticmethod
    def _make_cell(cell_type: str, source: str) -> dict[str, Any]:
        cell: dict[str, Any] = {
            "id": str(uuid.uuid4())[:8],
            "cell_type": cell_type,
            "metadata": {},
            "source": NotebookEditTool._split_source(source),
        }
        if cell_type == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
        return cell
