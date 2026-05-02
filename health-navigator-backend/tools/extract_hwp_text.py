from __future__ import annotations

import argparse
import io
import struct
import zlib
from pathlib import Path


FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
MINISECT = 0xFFFFFFFC


class CfbFile:
    def __init__(self, path: Path):
        self.data = path.read_bytes()
        if self.data[:8] != bytes.fromhex("D0CF11E0A1B11AE1"):
            raise ValueError(f"{path} is not an OLE/CFB file")

        self.sector_shift = struct.unpack_from("<H", self.data, 30)[0]
        self.sector_size = 1 << self.sector_shift
        self.mini_sector_shift = struct.unpack_from("<H", self.data, 32)[0]
        self.mini_sector_size = 1 << self.mini_sector_shift
        self.num_fat_sectors = struct.unpack_from("<I", self.data, 44)[0]
        self.first_dir_sector = struct.unpack_from("<I", self.data, 48)[0]
        self.mini_stream_cutoff = struct.unpack_from("<I", self.data, 56)[0]
        self.first_mini_fat_sector = struct.unpack_from("<I", self.data, 60)[0]
        self.num_mini_fat_sectors = struct.unpack_from("<I", self.data, 64)[0]
        self.first_difat_sector = struct.unpack_from("<I", self.data, 68)[0]
        self.num_difat_sectors = struct.unpack_from("<I", self.data, 72)[0]

        self.fat = self._load_fat()
        self.entries = self._load_directory()
        self.root_entry = next((e for e in self.entries if e["type"] == 5), None)
        self.mini_fat = self._load_mini_fat()
        self.mini_stream = (
            self._read_regular_stream(self.root_entry["start"], self.root_entry["size"])
            if self.root_entry
            else b""
        )

    def _sector_offset(self, sector: int) -> int:
        return 512 + sector * self.sector_size

    def _read_sector(self, sector: int) -> bytes:
        offset = self._sector_offset(sector)
        return self.data[offset : offset + self.sector_size]

    def _chain(self, start: int, table: list[int] | None = None) -> list[int]:
        if start in (FREESECT, ENDOFCHAIN):
            return []
        table = table or self.fat
        out = []
        seen = set()
        cur = start
        while cur not in (FREESECT, ENDOFCHAIN) and cur not in seen:
            seen.add(cur)
            out.append(cur)
            if cur >= len(table):
                break
            cur = table[cur]
        return out

    def _load_fat(self) -> list[int]:
        difat = list(struct.unpack_from("<109I", self.data, 76))
        difat = [x for x in difat if x != FREESECT]

        cur = self.first_difat_sector
        for _ in range(self.num_difat_sectors):
            sec = self._read_sector(cur)
            entries = struct.unpack("<" + "I" * (self.sector_size // 4), sec)
            difat.extend(x for x in entries[:-1] if x != FREESECT)
            cur = entries[-1]
            if cur == ENDOFCHAIN:
                break

        fat = []
        for sector in difat[: self.num_fat_sectors]:
            sec = self._read_sector(sector)
            fat.extend(struct.unpack("<" + "I" * (self.sector_size // 4), sec))
        return fat

    def _load_directory(self) -> list[dict]:
        directory = b"".join(self._read_sector(s) for s in self._chain(self.first_dir_sector))
        entries = []
        for i in range(0, len(directory), 128):
            raw = directory[i : i + 128]
            if len(raw) < 128:
                continue
            name_len = struct.unpack_from("<H", raw, 64)[0]
            name = raw[: max(0, name_len - 2)].decode("utf-16le", errors="ignore")
            entries.append(
                {
                    "name": name,
                    "type": raw[66],
                    "left": struct.unpack_from("<I", raw, 68)[0],
                    "right": struct.unpack_from("<I", raw, 72)[0],
                    "child": struct.unpack_from("<I", raw, 76)[0],
                    "start": struct.unpack_from("<I", raw, 116)[0],
                    "size": struct.unpack_from("<Q", raw, 120)[0],
                }
            )
        return entries

    def _load_mini_fat(self) -> list[int]:
        sectors = self._chain(self.first_mini_fat_sector)
        raw = b"".join(self._read_sector(s) for s in sectors[: self.num_mini_fat_sectors])
        if not raw:
            return []
        return list(struct.unpack("<" + "I" * (len(raw) // 4), raw))

    def _read_regular_stream(self, start: int, size: int) -> bytes:
        raw = b"".join(self._read_sector(s) for s in self._chain(start))
        return raw[:size]

    def _read_mini_stream(self, start: int, size: int) -> bytes:
        chunks = []
        for sector in self._chain(start, self.mini_fat):
            offset = sector * self.mini_sector_size
            chunks.append(self.mini_stream[offset : offset + self.mini_sector_size])
        return b"".join(chunks)[:size]

    def read_stream(self, path: str) -> bytes:
        parts = path.split("/")
        entry = self._find(parts)
        if entry is None:
            raise KeyError(path)
        if entry["size"] < self.mini_stream_cutoff and entry["type"] == 2:
            return self._read_mini_stream(entry["start"], entry["size"])
        return self._read_regular_stream(entry["start"], entry["size"])

    def _children(self, storage_index: int) -> list[int]:
        if storage_index >= len(self.entries):
            return []
        child = self.entries[storage_index]["child"]
        out = []

        def walk(idx: int):
            if idx in (FREESECT, ENDOFCHAIN) or idx >= len(self.entries):
                return
            walk(self.entries[idx]["left"])
            out.append(idx)
            walk(self.entries[idx]["right"])

        walk(child)
        return out

    def _find(self, parts: list[str]) -> dict | None:
        current_idx = 0
        for part in parts:
            found = None
            for child_idx in self._children(current_idx):
                if self.entries[child_idx]["name"] == part:
                    found = child_idx
                    break
            if found is None:
                return None
            current_idx = found
        return self.entries[current_idx]

    def list_paths(self) -> list[str]:
        paths = []

        def walk(idx: int, prefix: str):
            for child_idx in self._children(idx):
                entry = self.entries[child_idx]
                path = f"{prefix}/{entry['name']}" if prefix else entry["name"]
                paths.append(path)
                if entry["type"] == 1:
                    walk(child_idx, path)

        walk(0, "")
        return paths


def is_compressed(cfb: CfbFile) -> bool:
    header = cfb.read_stream("FileHeader")
    props = struct.unpack_from("<I", header, 36)[0]
    return bool(props & 1)


def decompress_section(raw: bytes) -> bytes:
    for wbits in (-15, 15):
        try:
            return zlib.decompress(raw, wbits)
        except zlib.error:
            pass
    output = io.BytesIO()
    obj = zlib.decompressobj(-15)
    output.write(obj.decompress(raw))
    output.write(obj.flush())
    return output.getvalue()


def extract_para_text(section: bytes) -> list[str]:
    texts = []
    pos = 0
    while pos + 4 <= len(section):
        header = struct.unpack_from("<I", section, pos)[0]
        pos += 4
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if pos + 4 > len(section):
                break
            size = struct.unpack_from("<I", section, pos)[0]
            pos += 4
        payload = section[pos : pos + size]
        pos += size

        if tag_id != 67:
            continue

        text = payload.decode("utf-16le", errors="ignore")
        text = (
            text.replace("\r", "\n")
            .replace("\x0b", "\n")
            .replace("\x00", "")
            .strip()
        )
        if text:
            texts.append(text)
    return texts


def extract_hwp_text(path: Path) -> str:
    cfb = CfbFile(path)
    compressed = is_compressed(cfb)
    section_paths = sorted(
        p for p in cfb.list_paths() if p.startswith("BodyText/Section")
    )
    chunks = []
    for section_path in section_paths:
        raw = cfb.read_stream(section_path)
        data = decompress_section(raw) if compressed else raw
        chunks.extend(extract_para_text(data))
    return "\n".join(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("extracted_docs"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for file_path in args.files:
        text = extract_hwp_text(file_path)
        out_path = args.out_dir / f"{file_path.stem}.txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"{file_path.name}: {len(text)} chars -> {out_path}")


if __name__ == "__main__":
    main()
