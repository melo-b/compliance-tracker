"""Where uploaded files live.

Services talk to the `Storage` interface, never to the disk directly, so the local-disk
implementation below can later be swapped for object storage (S3, Azure Blob, ...) without
touching any business code.

Note: on Render's free tier the container's disk is wiped on every deploy, so uploaded files do
not survive a redeploy there. The database rows do, which is why downloads report a missing
file clearly instead of failing. Use object storage for anything that must persist.
"""

from functools import lru_cache
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import get_settings
from app.core.exceptions import PayloadTooLargeError

CHUNK_SIZE = 64 * 1024


class Storage(Protocol):
    def save(self, key: str, stream: BinaryIO, max_bytes: int) -> int:
        """Stores the stream under `key` and returns its size in bytes.

        Raises PayloadTooLargeError (and stores nothing) if it exceeds `max_bytes`.
        """

    def open(self, key: str) -> BinaryIO:
        """Opens the stored file for reading. Raises FileNotFoundError if it is gone."""

    def delete(self, key: str) -> None:
        """Removes the stored file. Does nothing if it is already gone."""


class LocalStorage:
    """Stores files in a directory on the local disk."""

    def __init__(self, base_dir: str | Path):
        self.base = Path(base_dir).resolve()

    def _inside_base(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.base):
            raise ValueError("Storage key points outside the storage directory")
        return resolved

    def _locate(self, key: str) -> Path:
        # Documents uploaded before this abstraction existed stored "uploads/<name>", relative
        # to the working directory; newer keys are plain names relative to the storage folder.
        for root in (self.base, Path.cwd()):
            try:
                candidate = self._inside_base(root / key)
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
        return self._inside_base(self.base / key)

    def save(self, key: str, stream: BinaryIO, max_bytes: int) -> int:
        path = self._inside_base(self.base / key)
        path.parent.mkdir(parents=True, exist_ok=True)

        written = 0
        try:
            with path.open("wb") as target:
                while chunk := stream.read(CHUNK_SIZE):
                    written += len(chunk)
                    if written > max_bytes:
                        raise PayloadTooLargeError(
                            f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit"
                        )
                    target.write(chunk)
        except BaseException:
            path.unlink(missing_ok=True)  # never leave a partial file behind
            raise
        return written

    def open(self, key: str) -> BinaryIO:
        return self._locate(key).open("rb")

    def delete(self, key: str) -> None:
        try:
            self._locate(key).unlink(missing_ok=True)
        except ValueError:
            pass  # a key outside the storage directory is never deleted


@lru_cache
def _local_storage(upload_dir: str) -> LocalStorage:
    return LocalStorage(upload_dir)


def get_storage() -> Storage:
    """FastAPI dependency; tests override it to use a temporary directory."""
    return _local_storage(get_settings().upload_dir)
