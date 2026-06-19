from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Cursor(Protocol):
    @property
    def rowcount(self) -> int: ...

    @property
    def lastrowid(self) -> int | None: ...

    def fetchone(self) -> Any: ...

    def fetchall(self) -> list[Any]: ...


@runtime_checkable
class Database(Protocol):
    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | list[Any] = (),
    ) -> Cursor: ...

    def executemany(
        self,
        sql: str,
        params: list[tuple[Any, ...]],
    ) -> Cursor: ...

    def executescript(self, sql: str) -> None: ...

    def commit(self) -> None: ...

    def close(self) -> None: ...