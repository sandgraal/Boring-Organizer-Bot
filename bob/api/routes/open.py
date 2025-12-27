"""Open endpoint for opening files at specific locators."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class OpenRequest(BaseModel):
    """Request body for POST /open."""

    file_path: str = Field(..., description="Path to the file to open")
    line: int | None = Field(None, description="Line number to jump to")
    editor: str | None = Field(None, description="Preferred editor (vscode, cursor, etc)")


class OpenResponse(BaseModel):
    """Response body for POST /open."""

    success: bool
    message: str
    command: str | None = None


def _get_editor_command(editor: str | None, file_path: str, line: int | None) -> list[str]:
    """Get the command to open a file in an editor.

    Args:
        editor: Preferred editor name.
        file_path: Path to the file.
        line: Line number to jump to.

    Returns:
        Command list to execute.
    """
    location = f"{file_path}:{line}" if line else file_path

    # Check for common editors
    if editor:
        editor = editor.lower()
        if editor in ("vscode", "code"):
            return ["code", "--goto", location]
        elif editor == "cursor":
            return ["cursor", "--goto", location]
        elif editor in ("vim", "nvim", "neovim"):
            if line:
                return [editor if editor != "neovim" else "nvim", f"+{line}", file_path]
            return [editor if editor != "neovim" else "nvim", file_path]
        elif editor == "emacs":
            if line:
                return ["emacs", f"+{line}", file_path]
            return ["emacs", file_path]
        elif editor == "sublime":
            return ["subl", location]
        else:
            # Try using the editor name directly
            return [editor, file_path]

    # Try to detect available editors
    system = platform.system()

    # Check environment variable
    env_editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if env_editor:
        if ("vim" in env_editor or "nvim" in env_editor) and line:
            return [env_editor, f"+{line}", file_path]
        return [env_editor, file_path]

    # Check for common editors in PATH
    editors_to_try = [
        ("code", ["code", "--goto", location]),
        ("cursor", ["cursor", "--goto", location]),
        ("subl", ["subl", location]),
    ]

    for cmd, full_cmd in editors_to_try:
        if _command_exists(cmd):
            return full_cmd

    # Fallback to system default
    if system == "Darwin":  # macOS
        return ["open", file_path]
    elif system == "Windows":
        return ["start", "", file_path]
    else:  # Linux and others
        return ["xdg-open", file_path]


def _command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH.

    Uses shutil.which() for cross-platform compatibility.
    """
    return shutil.which(cmd) is not None


@router.post("/open", response_model=OpenResponse)
def open_file(request: OpenRequest) -> OpenResponse:
    """Open a file at a specific location.

    This endpoint attempts to open the file in a suitable editor.
    It returns instructions if the file cannot be opened automatically.

    Args:
        request: Open request with file path and optional line number.

    Returns:
        Result indicating success or instructions for manual opening.
    """
    file_path = request.file_path
    path = Path(file_path)

    # Check if file exists
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {file_path}",
        )

    # Get the command to open the file
    try:
        cmd = _get_editor_command(request.editor, str(path.absolute()), request.line)
    except Exception as e:
        return OpenResponse(
            success=False,
            message=f"Could not determine editor: {e}",
            command=None,
        )

    # Try to execute the command
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        cmd_str = " ".join(cmd)
        location_msg = f" at line {request.line}" if request.line else ""
        return OpenResponse(
            success=True,
            message=f"Opened {file_path}{location_msg}",
            command=cmd_str,
        )

    except FileNotFoundError:
        # Editor not found, return manual instructions
        location_msg = f" at line {request.line}" if request.line else ""
        return OpenResponse(
            success=False,
            message=f"Please open {file_path}{location_msg} manually. Editor '{cmd[0]}' not found.",
            command=None,
        )

    except Exception as e:
        return OpenResponse(
            success=False,
            message=f"Failed to open file: {e}",
            command=None,
        )
