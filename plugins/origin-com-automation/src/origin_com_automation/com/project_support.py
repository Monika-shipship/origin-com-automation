"""Stateless helpers for Origin COM collections and project paths."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(obj, name)
        return value() if callable(value) and name in {"Count"} else value
    except Exception:
        return default


def safe_call(obj: Any, name: str, *args: Any, default: Any = None) -> Any:
    try:
        method = getattr(obj, name)
        if not callable(method):
            return default
        return method(*args)
    except Exception:
        return default


def collection_items(collection: Any) -> list[Any]:
    if collection is None:
        return []
    count = safe_attr(collection, "Count")
    if count is not None:
        items: list[Any] = []
        for index in range(int(count)):
            try:
                item = collection.Item(index)
            except Exception:
                try:
                    item = collection(index)
                except Exception:
                    continue
            if item is not None:
                items.append(item)
        return items
    try:
        return list(collection)
    except Exception:
        return []


def find_collection_item(collection: Any, reference: str) -> Any | None:
    if collection is None:
        return None
    try:
        item = collection.Item(reference)
        if item is not None:
            return item
    except Exception:
        pass
    normalized = reference.strip().casefold()
    for item in collection_items(collection):
        names = {
            str(safe_attr(item, "Name", "")).strip().casefold(),
            str(safe_attr(item, "LongName", "")).strip().casefold(),
        }
        if normalized in names:
            return item
    return None


def required_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        value = getattr(obj, name)
    except AttributeError:
        return default
    return value() if callable(value) and name == "Count" else value


def required_collection_items(collection: Any) -> list[Any]:
    if collection is None:
        return []
    count = required_attr(collection, "Count")
    if count is None:
        return list(collection)
    try:
        item_method = getattr(collection, "Item")
    except AttributeError:
        item_method = None
    items: list[Any] = []
    for index in range(int(count)):
        if callable(item_method):
            item = item_method(index)
        elif callable(collection):
            item = collection(index)
        else:
            raise TypeError("Origin COM collection exposes Count but no Item accessor")
        if item is not None:
            items.append(item)
    return items


def project_path_parts(path: str) -> list[str]:
    return [part for part in path.replace("\\", "/").split("/") if part]


def resolve_root_folder(root: Any, path: str) -> Any | None:
    current = root
    for part in project_path_parts(path):
        current = find_collection_item(safe_attr(current, "Folders"), part)
        if current is None:
            return None
    return current


def ensure_root_folder(root: Any, path: str) -> Any | None:
    current = root
    for part in project_path_parts(path):
        folders = safe_attr(current, "Folders")
        child = find_collection_item(folders, part)
        if child is None:
            child = safe_call(folders, "Add", part, default=None)
        if child is None:
            return None
        current = child
    return current


def same_origin_object(left: Any, right: Any) -> bool:
    if left is right:
        return True
    try:
        return bool(left == right)
    except Exception:
        return False


def labtalk_quote(value: str | Path) -> str:
    text = str(value).replace("\\", "/").replace('"', '\\"')
    return f'"{text}"'


def same_file_path(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return left.resolve() == right.resolve()


def file_identity(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return int(stat.st_dev), int(stat.st_ino)
