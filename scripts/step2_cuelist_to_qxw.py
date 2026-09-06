#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 cuelist CSV 轉換成 QLC+ 5 的 Sequence (.qxw)。

CSV 版面 (以 cuelist_transform.csv 為例)::

    自動化表格 60RC舞台燈
    #,Duration(ms),Fade In(ms),Fade Out(ms),LSPA60RC[1-6] Total dimming,...,Note
    1,19030,0,0,255,255,51,183,,,,

* 第一列可以是標題列，程式會自動往下找真正的表頭列。
* 表頭欄位 ``<燈具>[索引] <通道>`` 會被對應到 QLC+ 的 fixture ID 與 channel 編號。
  索引可寫 ``1``、``1-6``、``1~6``、``1;3;5``；省略中括號代表該型號全部燈具。
* 值為空白或 0 的通道不會寫進 Step（與現有 .qxw 的寫法一致），可用 --keep-zeros 保留。

輸出模式::

    workspace  產生一個可直接開啟的完整 .qxw（含 Fixture / BoundScene / Sequence）
    snippet    只輸出 <Function Type="Sequence"> 區塊，方便貼進既有檔案
    merge      把 Scene + Sequence 插進既有 .qxw（自動配發新的 Function ID）

用法::

    python3 step2_cuelist_to_qxw.py cuelist_transform.csv
    python3 step2_cuelist_to_qxw.py any.csv --mode snippet
    python3 step2_cuelist_to_qxw.py any.csv --mode merge --base 舞台燈同步音樂播放_預先建立顏色與模式版本.qxw
"""

from __future__ import annotations

import argparse
import csv
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape, quoteattr


# --------------------------------------------------------------------------
# 燈具定義（對應 舞台燈同步音樂播放_預先建立顏色與模式版本.qxw）
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Head:
    """單一燈具在 workspace 中的身分。"""
    fixture_id: int
    address: int
    name: str


@dataclass(frozen=True)
class Profile:
    key: str                    # 正規化後的型號代碼
    manufacturer: str
    model: str
    mode: str
    channels: Tuple[str, ...]   # channel 0..N-1 的名稱
    heads: Dict[int, Head]      # 表頭索引 -> Head
    aliases: Tuple[str, ...] = ()
    exclude_fade: Optional[int] = None

    @property
    def channel_count(self) -> int:
        return len(self.channels)


PROFILES: Tuple[Profile, ...] = (
    Profile(
        key="LSPA60RC",
        manufacturer="LSPA",
        model="60RC",
        mode="mode1",
        channels=("Total dimming", "Red", "Green", "Blue",
                  "Stroboscopic", "Function", "Speed"),
        heads={
            1: Head(2, 0, "LSPA60RC [1]"),
            2: Head(3, 7, "LSPA60RC [2]"),
            3: Head(4, 14, "LSPA60RC [3]"),
            4: Head(5, 21, "LSPA60RC [4]"),
            5: Head(6, 28, "LSPA60RC [5]"),
            6: Head(7, 35, "LSPA60RC [6]"),
        },
        aliases=("LSPA60RC", "60RC", "LSPA"),
        exclude_fade=5,
    ),
    Profile(
        key="ER554",
        manufacturer="Guangzhou Enran",
        model="ER-554",
        mode="New mode",
        channels=("Total dimming", "Red", "Green", "Blue", "White",
                  "Stroboscopic", "Function", "Speed"),
        # ER-554[0] = 左台面燈 (ID 9, addr 48), ER-554[1] = 右台面燈 (ID 8, addr 56)。
        # 依 DMX address 由小到大排；workspace 裡的顯示名稱與此相反，
        # 但 Sequence達達團_面光燈2 (ID 37) 的實際數值證實是這個順序。
        heads={
            0: Head(9, 48, "ER-554 [1]"),
            1: Head(8, 56, "ER-554 [2]"),
        },
        aliases=("ER554", "ER-554", "ER", "台面燈"),
    ),
)


# QLC+ 用 UINT_MAX 表示「沒有指定 function」
NO_FUNCTION_ID = 4294967295


# channel 名稱別名 -> profile.channels 裡的正式名稱
CHANNEL_ALIASES: Dict[str, str] = {}


def _register_channel_aliases() -> None:
    groups = {
        "total dimming": ("totaldimming", "dimming", "dimmer", "dim", "intensity",
                          "master", "亮度", "總亮度", "調光"),
        "red": ("red", "r", "紅"),
        "green": ("green", "g", "綠"),
        "blue": ("blue", "b", "藍"),
        "white": ("white", "w", "白"),
        "stroboscopic": ("stroboscopic", "strobe", "strobo", "頻閃", "閃燈"),
        "function": ("function", "func", "mode", "模式", "功能"),
        "speed": ("speed", "spd", "速度"),
    }
    for canonical, names in groups.items():
        for name in names:
            CHANNEL_ALIASES[normalize(name)] = canonical


def normalize(text: str) -> str:
    """去掉空白/標點並轉小寫，用於寬鬆比對。"""
    return re.sub(r"[\s\-_()（）./\ufeff]+", "", (text or "").strip().lower())


_register_channel_aliases()

PROFILE_BY_ALIAS: Dict[str, Profile] = {}
for _p in PROFILES:
    for _alias in (_p.key, _p.model, *_p.aliases):
        PROFILE_BY_ALIAS[normalize(_alias)] = _p


def strip_profile_prefix(title: str, alias: str) -> Optional[str]:
    """若 title 正規化後以 alias 開頭，回傳原字串剩下的部分，否則 None。

    不能直接用 len(alias) 去切原字串：正規化會拿掉 ``-`` 之類的字元，
    ``ER-554 Dim`` 配上別名 ``er554`` 會切成 ``54 Dim``。
    """
    for i in range(len(title)):
        consumed = normalize(title[:i + 1])
        if consumed == alias:
            return title[i + 1:]
        if not alias.startswith(consumed):
            return None
    return None


def resolve_channel(profile: Profile, token: str) -> Optional[int]:
    """把表頭裡的通道文字轉成 channel 編號。"""
    token = (token or "").strip()
    if not token:
        return None
    key = normalize(token)

    # 直接寫數字或 ch4 / channel4
    m = re.fullmatch(r"(?:ch|channel|通道)?(\d+)", key)
    if m:
        index = int(m.group(1))
        return index if 0 <= index < profile.channel_count else None

    canonical = CHANNEL_ALIASES.get(key, key)
    for index, name in enumerate(profile.channels):
        if normalize(name) == normalize(canonical):
            return index
    return None


# --------------------------------------------------------------------------
# CSV 解析
# --------------------------------------------------------------------------

HEADER_RE = re.compile(
    r"^(?P<model>.*?)\s*[\[\［](?P<spec>[^\]\］]*)[\]\］]\s*(?P<channel>.*)$"
)

META_COLUMNS = {
    "#": "index", "no": "index", "step": "index", "序號": "index",
    "duration": "duration", "durationms": "duration", "hold": "duration", "時間": "duration",
    "fadein": "fade_in", "fadeinms": "fade_in", "淡入": "fade_in",
    "fadeout": "fade_out", "fadeoutms": "fade_out", "淡出": "fade_out",
    "note": "note", "notes": "note", "備註": "note",
}


@dataclass(frozen=True)
class ColumnSpec:
    """一個資料欄位：某盞（或某幾盞）燈的某個通道。"""
    column: int
    profile: Profile
    heads: Tuple[Head, ...]
    channel: int
    label: str


class CsvFormatError(ValueError):
    pass


def parse_index_spec(spec: str, profile: Profile) -> Tuple[int, ...]:
    """解析 ``1``、``1-6``、``1~6``、``1;3;5``；空字串代表全部。

    分隔符號接受 ``; + 、``；``,`` 只在該欄有被引號包起來時才安全（CSV 會把
    未加引號的逗號當成欄位分隔）。
    """
    spec = (spec or "").strip()
    if not spec:
        return tuple(sorted(profile.heads))

    out: List[int] = []
    for token in re.split(r"[;；+,、，]+", spec):
        token = token.strip()
        if not token:
            continue
        m = re.fullmatch(r"(\d+)\s*[-~–—－至]\s*(\d+)", token)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            step = 1 if end >= start else -1
            out.extend(range(start, end + step, step))
            continue
        if token.isdigit():
            out.append(int(token))
            continue
        raise CsvFormatError(f"無法解析燈具索引: {token!r}")

    unknown = [i for i in out if i not in profile.heads]
    if unknown:
        known = ", ".join(str(i) for i in sorted(profile.heads))
        raise CsvFormatError(
            f"{profile.model} 沒有索引 {unknown}（可用的索引: {known}）"
        )
    # 去重但保留順序
    return tuple(dict.fromkeys(out))


def parse_header(header: List[str]) -> Tuple[Dict[str, int], List[ColumnSpec], List[str]]:
    meta: Dict[str, int] = {}
    columns: List[ColumnSpec] = []
    unknown: List[str] = []

    for col, raw in enumerate(header):
        title = (raw or "").replace("\ufeff", "").strip()
        if not title:
            continue

        role = META_COLUMNS.get(normalize(title))
        if role:
            meta.setdefault(role, col)
            continue

        m = HEADER_RE.match(title)
        if m:
            profile = PROFILE_BY_ALIAS.get(normalize(m.group("model")))
            channel_token = m.group("channel")
            index_spec = m.group("spec")
        else:
            # 沒有中括號時，嘗試把開頭當成型號
            profile = None
            channel_token = ""
            index_spec = ""
            for alias, candidate in sorted(PROFILE_BY_ALIAS.items(),
                                           key=lambda kv: -len(kv[0])):
                rest = strip_profile_prefix(title, alias)
                if rest is not None:
                    profile = candidate
                    channel_token = rest
                    break

        if profile is None:
            unknown.append(title)
            continue

        channel = resolve_channel(profile, channel_token)
        if channel is None:
            unknown.append(title)
            continue

        heads = tuple(profile.heads[i] for i in parse_index_spec(index_spec, profile))
        columns.append(ColumnSpec(col, profile, heads, channel, title))

    if not columns:
        raise CsvFormatError(
            "表頭裡找不到任何燈具通道欄位，"
            "請確認格式類似 'LSPA60RC[1-6] Red' 或 'ER-554[0] Blue'。"
        )
    return meta, columns, unknown


def is_header_row(row: List[str]) -> bool:
    """判斷這一列是不是表頭列。"""
    keys = {normalize(cell) for cell in row if cell and cell.strip()}
    return bool(keys & {"duration", "durationms", "hold", "時間"}) or \
        "#" in {(c or "").strip() for c in row}


def looks_like_title(row: List[str]) -> bool:
    """判斷這一列是標題列，而不是上一張表的最後一列資料。

    標題列的特徵是只有零星一兩格有字，而且開頭不是數字；
    資料列則會填滿一整排數值（含 ``#`` 欄的流水號）。
    """
    filled = [(c or "").replace("\ufeff", "").strip() for c in row]
    filled = [c for c in filled if c]
    if not filled:
        return False
    if any(t.startswith(prefix) for t in filled for prefix in TITLE_PREFIXES):
        return True
    if len(filled) > 2:
        return False
    return not re.fullmatch(r"[\d.]+", filled[0])


TITLE_PREFIXES = ("自動化表格", "自動化表單", "表格")


def row_title(row: List[str]) -> str:
    """取這一列的標題。

    Excel 版面左邊還有一張給人看的中文表，所以標題列可能長成
    ``['染色燈', '', ..., '自動化表格 60RC舞台燈']``。
    優先取「自動化表格 …」那一格，才不會抓到隔壁表的欄位名稱。
    """
    # 把多份匯出檔疊在一起時，中間會夾帶 BOM
    texts = [(cell or "").replace("\ufeff", "").strip() for cell in row]
    texts = [t for t in texts if t]
    for text in texts:
        if any(text.startswith(prefix) for prefix in TITLE_PREFIXES):
            return text
    return texts[0] if texts else ""


@dataclass
class RawBlock:
    """CSV 裡的一張「工作表」：一列表頭加上它底下的資料列。"""
    title: str
    header: List[str]
    rows: List[List[str]]


def split_blocks(rows: List[List[str]]) -> List[RawBlock]:
    """把一份 CSV 切成多個區塊，每個表頭列開啟一個新區塊。

    區塊之間靠表頭列辨識，所以同一個檔案裡可以直接把多張表上下疊起來；
    表頭上面那一列若有文字，會被當成該區塊的名稱。
    """
    header_indices = [i for i, row in enumerate(rows) if is_header_row(row)]
    if not header_indices:
        return []

    blocks: List[RawBlock] = []
    for order, start in enumerate(header_indices):
        end = header_indices[order + 1] if order + 1 < len(header_indices) else len(rows)
        title = ""
        if start > 0 and looks_like_title(rows[start - 1]):
            title = row_title(rows[start - 1])
        blocks.append(RawBlock(title=title, header=rows[start], rows=rows[start + 1:end]))
    return blocks


def block_title(raw: RawBlock) -> str:
    """取表格自己的標題（去掉開頭的「自動化表格」）；沒有就回空字串。"""
    title = raw.title
    for prefix in TITLE_PREFIXES:
        if title.startswith(prefix):
            title = title[len(prefix):].strip()
            break
    return title.strip(" -_:：")


def to_int(raw: Optional[str], default: Optional[int] = None) -> Optional[int]:
    text = (raw or "").strip().replace(",", "")
    if not text:
        return default
    try:
        return int(round(float(text)))
    except ValueError:
        return default


def clamp_dmx(value: int) -> int:
    return max(0, min(255, value))


# --------------------------------------------------------------------------
# Step 產生
# --------------------------------------------------------------------------

@dataclass
class Step:
    hold: int
    fade_in: int
    fade_out: int
    values: Dict[int, Dict[int, int]]   # fixture_id -> {channel: value}
    note: str = ""

    def signature(self) -> str:
        return render_values(self.values)


def render_values(values: Dict[int, Dict[int, int]]) -> str:
    """輸出 QLC+ 的 ``id:ch,val,ch,val:id:...`` 字串。"""
    chunks = []
    for fixture_id in sorted(values):
        channels = values[fixture_id]
        if not channels:
            continue
        body = ",".join(f"{ch},{channels[ch]}" for ch in sorted(channels))
        chunks.append(f"{fixture_id}:{body}")
    return ":".join(chunks)


def build_steps(rows: List[List[str]], meta: Dict[str, int],
                columns: List[ColumnSpec], keep_zeros: bool) -> List[Step]:
    steps: List[Step] = []

    for row in rows:
        def cell(role: str) -> Optional[str]:
            col = meta.get(role)
            return row[col] if col is not None and col < len(row) else None

        values: Dict[int, Dict[int, int]] = {}
        has_value = False
        for spec in columns:
            raw = row[spec.column] if spec.column < len(row) else None
            value = to_int(raw)
            if value is None:
                continue
            has_value = True
            value = clamp_dmx(value)
            if value == 0 and not keep_zeros:
                continue
            for head in spec.heads:
                values.setdefault(head.fixture_id, {})[spec.channel] = value

        duration = to_int(cell("duration"))
        if duration is None and not has_value:
            continue    # 整列空白，略過

        steps.append(Step(
            hold=max(0, duration or 0),
            fade_in=max(0, to_int(cell("fade_in"), 0) or 0),
            fade_out=max(0, to_int(cell("fade_out"), 0) or 0),
            values=values,
            note=(cell("note") or "").strip(),
        ))

    return steps


def trim_padding(steps: List[Step]) -> List[Step]:
    """砍掉表格尾端「沒有時間、而且內容跟前一步一模一樣」的填充列。"""
    while len(steps) > 1 and steps[-1].hold == 0 and \
            steps[-1].signature() == steps[-2].signature():
        steps.pop()
    return steps


# --------------------------------------------------------------------------
# XML 產生
# --------------------------------------------------------------------------

@dataclass
class Block:
    """一張表轉出來的東西：一條 Sequence 加上它專屬的 BoundScene。"""
    name: str
    columns: List[ColumnSpec]
    steps: List[Step]
    unknown: List[str]
    sheet: str = ""
    title: str = ""
    group: str = ""     # 專案模式下的子資料夾名稱

    @property
    def total_ms(self) -> int:
        return sum(step.hold for step in self.steps)


@dataclass
class AudioSpec:
    """一首要掛進 Show 的配樂。"""
    name: str            # QLC+ 函式名稱（沿用檔名）
    source: str          # 寫進 <Source> 的路徑
    duration_ms: int


@dataclass
class ShowSpec:
    """一個子資料夾：一首配樂加上它的多條 Sequence。

    ``name`` 為空時不產生 Show 函式（單檔轉換就是這種情況）。
    """
    blocks: List[Block]
    name: str = ""
    audio: Optional[AudioSpec] = None


# MP3 frame header 對照表（Layer III）
_MP3_BITRATES = {
    1: (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0),
    2: (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0),
}
_MP3_RATES = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000),
              0: (11025, 12000, 8000)}


def mp3_duration_ms(path: Path) -> Optional[int]:
    """算出 mp3 長度（毫秒），只用標準函式庫。

    先跳過 ID3 標籤找到第一個 frame header，若有 Xing/Info/VBRI 表頭就用
    frame 數換算（VBR 準確），否則用 bitrate 與檔案大小推估（CBR）。
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None

    start, end = 0, len(data)
    if data[:3] == b"ID3" and len(data) > 10:
        size = 0
        for byte in data[6:10]:
            size = (size << 7) | (byte & 0x7F)
        start = 10 + size + (10 if data[5] & 0x10 else 0)
    if end - 128 > start and data[end - 128:end - 125] == b"TAG":
        end -= 128

    for i in range(start, min(start + 200000, max(start, end - 4))):
        if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
            continue
        header = data[i:i + 4]
        version = (header[1] >> 3) & 0x03
        layer = (header[1] >> 1) & 0x03
        rate_index = (header[2] >> 2) & 0x03
        bitrate_index = (header[2] >> 4) & 0x0F
        if version == 1 or layer == 0 or rate_index == 3 or bitrate_index in (0, 15):
            continue

        rate = _MP3_RATES[version][rate_index]
        bitrate = _MP3_BITRATES[1 if version == 3 else 2][bitrate_index] * 1000
        if layer == 3:                      # Layer I
            samples = 384
        elif layer == 2:                    # Layer II
            samples = 1152
        else:                               # Layer III
            samples = 1152 if version == 3 else 576

        mono = ((header[3] >> 6) & 0x03) == 3
        side = (17 if mono else 32) if version == 3 else (9 if mono else 17)
        tag = i + 4 + side
        if data[tag:tag + 4] in (b"Xing", b"Info"):
            flags = int.from_bytes(data[tag + 4:tag + 8], "big")
            if flags & 1:
                frames = int.from_bytes(data[tag + 8:tag + 12], "big")
                if frames:
                    return round(frames * samples * 1000 / rate)
        if data[i + 36:i + 40] == b"VBRI":
            frames = int.from_bytes(data[i + 78:i + 82], "big")
            if frames:
                return round(frames * samples * 1000 / rate)
        return round((end - i) * 8 * 1000 / bitrate) if bitrate else None
    return None


def used_fixtures(columns: List[ColumnSpec]) -> List[Tuple[Profile, Head]]:
    seen: Dict[int, Tuple[Profile, Head]] = {}
    for spec in columns:
        for head in spec.heads:
            seen.setdefault(head.fixture_id, (spec.profile, head))
    return [seen[fid] for fid in sorted(seen)]


def all_blocks(shows: List[ShowSpec]) -> List[Block]:
    return [block for show in shows for block in show.blocks]


def all_fixtures(shows: List[ShowSpec]) -> List[Tuple[Profile, Head]]:
    """所有表格用到的燈具聯集（同一盞只會出現一次）。"""
    seen: Dict[int, Tuple[Profile, Head]] = {}
    for block in all_blocks(shows):
        for profile, head in used_fixtures(block.columns):
            seen.setdefault(head.fixture_id, (profile, head))
    return [seen[fid] for fid in sorted(seen)]


def render_sequence(steps: List[Step], columns: List[ColumnSpec], *,
                    function_id: int, name: str, bound_scene: int,
                    run_order: str, direction: str, folder: str = "",
                    indent: str = "  ") -> str:
    total_channels = sum(profile.channel_count for profile, _ in used_fixtures(columns))
    default_duration = steps[0].hold if steps else 0

    # QLC+ 的「資料夾」就是 Function 上的 Path 屬性；巢狀資料夾用 / 分隔。
    # 屬性順序比照 QLC+ 自己存檔的寫法：ID, Type, Name, Path, BoundScene。
    path_attr = f" Path={quoteattr(folder)}" if folder else ""

    lines = [
        f'{indent}<Function ID="{function_id}" Type="Sequence" '
        f'Name={quoteattr(name)}{path_attr} BoundScene="{bound_scene}">',
        f'{indent} <Speed FadeIn="0" FadeOut="0" Duration="{default_duration}"/>',
        f'{indent} <Direction>{direction}</Direction>',
        f'{indent} <RunOrder>{run_order}</RunOrder>',
        f'{indent} <SpeedModes FadeIn="PerStep" FadeOut="PerStep" Duration="PerStep"/>',
    ]
    for number, step in enumerate(steps):
        lines.append(
            f'{indent} <Step Number="{number}" FadeIn="{step.fade_in}" '
            f'Hold="{step.hold}" FadeOut="{step.fade_out}" '
            f'Values="{total_channels}">{escape(step.signature())}</Step>'
        )
    lines.append(f'{indent}</Function>')
    return "\n".join(lines)


def render_bound_scene(columns: List[ColumnSpec], *, scene_id: int,
                       name: str = "New Scene", indent: str = "  ") -> str:
    """Sequence 需要一個隱藏 Scene 當容器，把用到的通道歸零列出來。"""
    lines = [
        f'{indent}<Function ID="{scene_id}" Type="Scene" '
        f'Name={quoteattr(name)} Hidden="True">',
        f'{indent} <Speed FadeIn="0" FadeOut="0" Duration="0"/>',
    ]
    for profile, head in used_fixtures(columns):
        body = ",".join(f"{ch},0" for ch in range(profile.channel_count))
        lines.append(f'{indent} <FixtureVal ID="{head.fixture_id}">{body}</FixtureVal>')
    lines.append(f'{indent}</Function>')
    return "\n".join(lines)


def render_fixtures(shows: List[ShowSpec], indent: str = "  ") -> str:
    lines = []
    for profile, head in all_fixtures(shows):
        lines.append(f'{indent}<Fixture>')
        lines.append(f'{indent} <Manufacturer>{escape(profile.manufacturer)}</Manufacturer>')
        lines.append(f'{indent} <Model>{escape(profile.model)}</Model>')
        lines.append(f'{indent} <Mode>{escape(profile.mode)}</Mode>')
        lines.append(f'{indent} <ID>{head.fixture_id}</ID>')
        lines.append(f'{indent} <Name>{escape(head.name)}</Name>')
        lines.append(f'{indent} <Universe>0</Universe>')
        lines.append(f'{indent} <Address>{head.address}</Address>')
        lines.append(f'{indent} <Channels>{profile.channel_count}</Channels>')
        if profile.exclude_fade is not None:
            lines.append(f'{indent} <ExcludeFade>{profile.exclude_fade}</ExcludeFade>')
        lines.append(f'{indent}</Fixture>')
    return "\n".join(lines)


AUDIO_TRACK_COLOR = "#608053"
SEQUENCE_TRACK_COLOR = "#646464"


def render_audio(audio: AudioSpec, *, function_id: int, folder: str,
                 indent: str = "  ") -> str:
    path_attr = f" Path={quoteattr(folder)}" if folder else ""
    return "\n".join((
        f'{indent}<Function ID="{function_id}" Type="Audio" '
        f'Name={quoteattr(audio.name)}{path_attr}>',
        f'{indent} <Speed FadeIn="0" FadeOut="0" Duration="{audio.duration_ms}"/>',
        f'{indent} <RunOrder>SingleShot</RunOrder>',
        f'{indent} <Source>{escape(audio.source)}</Source>',
        f'{indent}</Function>',
    ))


def render_show(name: str, tracks: List[Tuple[int, int, str]], *, function_id: int,
                folder: str, indent: str = "  ") -> str:
    """產生一個 Show。

    ``tracks`` 是 (函式 ID, 長度 ms, 顏色)，每個各佔一條軌、
    全部從時間 0 開始，所以在 Show Manager 裡是並排的。
    """
    path_attr = f" Path={quoteattr(folder)}" if folder else ""
    lines = [
        f'{indent}<Function ID="{function_id}" Type="Show" '
        f'Name={quoteattr(name)}{path_attr}>',
        f'{indent} <TimeDivision Type="Time" BPM="120"/>',
    ]
    for order, (ref_id, duration, color) in enumerate(tracks):
        lines.append(f'{indent} <Track ID="{order}" Name="Track {order + 1}" isMute="0">')
        lines.append(f'{indent}  <ShowFunction ID="{ref_id}" StartTime="0" '
                     f'Duration="{duration}" Color="{color}"/>')
        lines.append(f'{indent} </Track>')
    lines.append(f'{indent}</Function>')
    return "\n".join(lines)


def render_functions(shows: List[ShowSpec], *, first_id: int, run_order: str,
                     direction: str, folder: str = "", music_folder: str = "",
                     show_folder: str = "", indent: str = "  ") -> str:
    """產生所有函式，ID 連號配發。

    每個 ShowSpec 依序輸出：各表格的 BoundScene + Sequence、配樂 Audio，
    最後是把它們並排在時間 0 的 Show。BoundScene 是隱藏函式，不給 Path。
    """
    chunks: List[str] = []
    next_id = first_id

    for show in shows:
        tracks: List[Tuple[int, int, str]] = []

        if show.audio is not None:
            audio_id = next_id
            next_id += 1
            chunks.append(render_audio(show.audio, function_id=audio_id,
                                       folder=music_folder, indent=indent))
            tracks.append((audio_id, show.audio.duration_ms, AUDIO_TRACK_COLOR))

        for block in show.blocks:
            scene_id, sequence_id = next_id, next_id + 1
            next_id += 2
            chunks.append(render_bound_scene(
                block.columns, scene_id=scene_id,
                name=f"{block.name} Scene", indent=indent))
            chunks.append(render_sequence(
                block.steps, block.columns, function_id=sequence_id, name=block.name,
                bound_scene=scene_id, run_order=run_order, direction=direction,
                folder=folder, indent=indent))
            tracks.append((sequence_id, block.total_ms, SEQUENCE_TRACK_COLOR))

        if show.name and tracks:
            chunks.append(render_show(show.name, tracks, function_id=next_id,
                                      folder=show_folder, indent=indent))
            next_id += 1

    return "\n".join(chunks)


def render_workspace(shows: List[ShowSpec], *, run_order: str, direction: str,
                     folder: str = "", music_folder: str = "",
                     show_folder: str = "") -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Workspace>
<Workspace xmlns="http://www.qlcplus.org/Workspace" CurrentWindow="FunctionManager">
 <Creator>
  <Name>Q Light Controller Plus</Name>
  <Version>5.2.2</Version>
  <Author>step2_cuelist_to_qxw.py</Author>
 </Creator>
 <Engine>
  <InputOutputMap>
   <BeatGenerator BeatType="Disabled" BPM="120"/>
   <Universe Name="Universe 1" ID="0"/>
   <Universe Name="Universe 2" ID="1"/>
   <Universe Name="Universe 3" ID="2"/>
   <Universe Name="Universe 4" ID="3"/>
  </InputOutputMap>
{render_fixtures(shows)}
{render_functions(shows, first_id=0, run_order=run_order, direction=direction, folder=folder, music_folder=music_folder, show_folder=show_folder)}
 </Engine>
 <VirtualConsole>
  <Frame Caption="" ID="0">
   <Appearance>
    <FrameStyle>None</FrameStyle>
   </Appearance>
  </Frame>
  <Properties>
   <Size Width="1920" Height="1080"/>
  </Properties>
 </VirtualConsole>
 <SimpleDesk>
  <Engine/>
 </SimpleDesk>
</Workspace>
'''


def merge_into_workspace(base_path: Path, shows: List[ShowSpec],
                         *, run_order: str, direction: str, folder: str = "",
                         music_folder: str = "", show_folder: str = "") -> str:
    text = base_path.read_text(encoding="utf-8")

    marker = "</Engine>"
    at = text.rindex(marker)

    # 只掃 <Engine> 區塊裡的 Function ID：VirtualConsole 會用 4294967295
    # 這個「未指定 function」的哨兵值，不能拿來當發號的依據。
    used_ids = {int(i) for i in re.findall(r'<Function ID="(\d+)"', text[:at])}
    used_ids.discard(NO_FUNCTION_ID)
    first_id = max(used_ids, default=-1) + 1

    body = render_functions(shows, first_id=first_id, run_order=run_order,
                            direction=direction, folder=folder,
                            music_folder=music_folder, show_folder=show_folder)

    # 對齊 </Engine> 前的縮排
    line_start = text.rfind("\n", 0, at) + 1
    return text[:line_start] + body + "\n" + text[line_start:]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def read_csv(path: Path) -> List[List[str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [row for row in csv.reader(fh)]


def _tag(element: ET.Element) -> str:
    """取 XML 標籤的本名。

    .xlsx 內部的 XML 帶有命名空間前綴，ElementTree 會把標籤展開成
    ``{命名空間}row`` 這種形式。這裡只比對最後的本名（``row``），
    就不必把命名空間字串寫死，不同版本的 Excel 產生的檔案也都吃得下。
    """
    return element.tag.rpartition("}")[2]


def _children(parent: ET.Element, name: str) -> List[ET.Element]:
    """直接子元素中，標籤本名相符的那些。"""
    return [child for child in parent if _tag(child) == name]


def _descendants(parent: ET.Element, name: str) -> List[ET.Element]:
    """所有後代元素中，標籤本名相符的那些。"""
    return [node for node in parent.iter() if _tag(node) == name]


def _relationship_id(attrib: Dict[str, str]) -> str:
    """取 ``r:id`` 屬性，同樣不寫死命名空間。"""
    for key, value in attrib.items():
        if key.rpartition("}")[2] == "id":
            return value
    return ""


def _cell_column(ref: str) -> int:
    """把 ``N7`` 這種儲存格位址換成 0-based 欄號。"""
    letters = re.match(r"([A-Za-z]+)", ref or "")
    if not letters:
        return 0
    value = 0
    for ch in letters.group(1).upper():
        value = value * 26 + (ord(ch) - 64)
    return value - 1


def _resolve_part(target: str, base: str = "xl") -> str:
    """把 relationship 的 Target 換算成 zip 裡的實際路徑。

    Excel 寫的是相對於 ``xl/`` 的相對路徑（``worksheets/sheet1.xml``），
    openpyxl 則寫套件根目錄的絕對路徑（``/xl/worksheets/sheet1.xml``），
    兩種都要吃得下。
    """
    target = (target or "").replace("\\", "/")
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    return posixpath.normpath(f"{base}/{target}")


def _shared_strings(zf: zipfile.ZipFile) -> List[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return ["".join(node.text or "" for node in _descendants(si, "t"))
            for si in _children(root, "si")]


def read_xlsx(path: Path) -> List[Tuple[str, List[List[str]]]]:
    """讀 .xlsx，回傳 [(工作表名稱, 列資料), ...]，順序同活頁簿。

    只用標準函式庫，不需要 openpyxl。
    """
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        strings = _shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = {rel.attrib["Id"]: rel.attrib["Target"]
                for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
                if "Id" in rel.attrib and "Target" in rel.attrib}

        sheets: List[Tuple[str, List[List[str]]]] = []
        for sheet in _descendants(workbook, "sheet"):
            target = rels.get(_relationship_id(sheet.attrib))
            if not target:
                continue
            target = _resolve_part(target)
            if target not in names:
                print(f"  ⚠ {path.name} 的工作表「{sheet.attrib.get('name', '')}」"
                      f"找不到對應的資料（{target}）", file=sys.stderr)
                continue

            worksheet = ET.fromstring(zf.read(target))
            rows: List[List[str]] = []
            for row in _descendants(worksheet, "row"):
                cells: Dict[int, str] = {}
                for order, cell in enumerate(_children(row, "c")):
                    index = _cell_column(cell.attrib["r"]) if "r" in cell.attrib else order
                    kind = cell.attrib.get("t")
                    if kind == "inlineStr":
                        text = "".join(node.text or ""
                                       for node in _descendants(cell, "t"))
                    else:
                        value = next(iter(_children(cell, "v")), None)
                        text = value.text if value is not None and value.text else ""
                        if kind == "s" and text:
                            position = int(text)
                            text = strings[position] if 0 <= position < len(strings) else ""
                    if text:
                        cells[index] = text
                width = max(cells) + 1 if cells else 0
                rows.append([cells.get(i, "") for i in range(width)])
            sheets.append((sheet.attrib.get("name", ""), rows))
        return sheets


def read_tables(path: Path) -> List[Tuple[str, List[List[str]]]]:
    """依副檔名讀檔；CSV 只有一張表，xlsx 則每張工作表各算一張。"""
    if path.name.startswith("~$"):
        return []      # Excel 開著檔案時產生的暫存鎖定檔
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            return read_xlsx(path)
        except zipfile.BadZipFile as exc:
            raise CsvFormatError(f"{path} 不是有效的 .xlsx 檔（{exc}）") from exc
    return [("", read_csv(path))]


DEFAULT_INPUTS = (Path("cuelist_transform.xlsx"), Path("cuelist_transform.csv"))

# QLC+ 函式樹裡的資料夾名稱
DEFAULT_FOLDER = "Sequence_Cuelist"
DEFAULT_MUSIC_FOLDER = "Music"
DEFAULT_SHOW_FOLDER = "Show"


def default_inputs() -> List[Path]:
    """沒指定來源時，優先用 .xlsx，沒有才退回 .csv。"""
    return [path for path in DEFAULT_INPUTS if path.exists()][:1]


def pick_name(sheet: str, title: str, stem: str, order: int, name_from: str) -> str:
    """決定一個表格的 Sequence 名稱。

    ``name_from="sheet"`` 用工作表名稱（CSV 沒有工作表，退回表格標題／檔名），
    ``name_from="title"`` 則用表格自己的「自動化表格 …」標題。
    """
    if name_from == "sheet":
        candidates = (sheet, title, stem)
    else:
        candidates = (title, sheet, stem)
    for candidate in candidates:
        if candidate:
            return candidate
    return f"Sequence_{order + 1}"


def load_blocks(paths: List[Path], *, keep_zeros: bool, trim: bool,
                names: Optional[List[str]] = None,
                only_sheets: Optional[List[str]] = None,
                name_from: str = "sheet", group: str = "",
                resolve: bool = True) -> List[Block]:
    """把每個檔案、每張工作表、每個自動化表格，各轉成一個 Block。"""
    blocks: List[Block] = []

    found_any_table = False

    for path in paths:
        sheets = read_tables(path)
        if not sheets:
            raise CsvFormatError(f"讀不到任何內容: {path}")

        for sheet, rows in sheets:
            if only_sheets and sheet not in only_sheets:
                continue
            raws = split_blocks(rows)
            if not raws:
                # Excel 常有「說明」「下拉選單」這種沒有表格的工作表，直接跳過
                if sheet:
                    continue
                raise CsvFormatError(
                    f"{path}: 找不到表頭列，"
                    "請確認表格含有 '#' 或 'Duration(ms)' 欄位。"
                )
            found_any_table = True

            for order, raw in enumerate(raws):
                title = block_title(raw)
                name = pick_name(sheet, title, path.stem, order, name_from)
                where = f"{path}" + (f" 的工作表「{sheet}」" if sheet else "")

                try:
                    meta, columns, unknown = parse_header(raw.header)
                except CsvFormatError as exc:
                    raise CsvFormatError(f"{where}「{name}」: {exc}") from exc

                steps = build_steps(raw.rows, meta, columns, keep_zeros)
                if not steps:
                    print(f"  ⚠ 略過沒有 Step 的表: {name}", file=sys.stderr)
                    continue
                if trim:
                    steps = trim_padding(steps)

                blocks.append(Block(name=name, columns=columns, steps=steps,
                                    unknown=unknown, sheet=sheet, title=title,
                                    group=group))

    if not found_any_table:
        raise CsvFormatError(
            "找不到任何自動化表格。"
            + (f" 指定的工作表: {', '.join(only_sheets)}" if only_sheets else "")
        )
    if not blocks:
        raise CsvFormatError("所有表格都沒有可用的 Step。")

    if resolve:
        finalize_names(blocks, name_from=name_from, names=names)
    return blocks


def finalize_names(blocks: List[Block], *, name_from: str,
                   names: Optional[List[str]] = None) -> None:
    """把 Sequence 名稱收斂成互不重複的一組。

    先用主要識別字（工作表或表格標題），撞名時依序補上子資料夾名稱與
    另一個識別字，最後才退回 ``_2``、``_3`` 這種數字後綴。
    """
    # --name 指定時直接覆蓋：第一張用原名，後面接 _2、_3 …
    if names:
        for order, block in enumerate(blocks):
            block.name = names[order] if order < len(names) \
                else f"{names[-1]}_{order + 1}"
    else:
        secondary = "title" if name_from == "sheet" else "sheet"
        # 子資料夾名放前面（show1_染色燈），表格標題接後面（染色燈_60RC舞台燈）
        for attribute, prefix in (("group", True), (secondary, False)):
            duplicated = {name for name, count in
                          Counter(b.name for b in blocks).items() if count > 1}
            if not duplicated:
                break
            for block in blocks:
                extra = getattr(block, attribute)
                if block.name not in duplicated or not extra or extra == block.name:
                    continue
                block.name = f"{extra}_{block.name}" if prefix \
                    else f"{block.name}_{extra}"

    # 還是撞號的話補後綴，避免 QLC+ 裡出現兩條同名 Sequence
    seen: Dict[str, int] = {}
    for block in blocks:
        count = seen.get(block.name, 0) + 1
        seen[block.name] = count
        if count > 1:
            block.name = f"{block.name}_{count}"


TABLE_SUFFIXES = (".xlsx", ".xlsm", ".csv")
AUDIO_SUFFIXES = (".mp3",)


def audio_source(mp3: Path, out_path: Path) -> str:
    """決定寫進 <Source> 的路徑。

    QLC+ 會把相對路徑當成相對於 .qxw 所在資料夾，所以只要音檔在輸出檔
    底下就用相對路徑（整個專案搬家也還能播），否則退回絕對路徑。
    """
    mp3 = mp3.resolve()
    base = out_path.resolve().parent
    try:
        return str(mp3.relative_to(base))
    except ValueError:
        return str(mp3)


def find_base_qxw(root: Path, out_path: Path) -> Optional[Path]:
    """找專案資料夾底下的底稿 .qxw（不含子資料夾）。

    找到就拿它當合併底稿，沒有就退回產生獨立的 workspace。
    自動存檔與輸出檔本身都會被排除，免得把產物當成底稿。
    """
    resolved_out = out_path.resolve()
    candidates = sorted(
        (child for child in root.iterdir()
         if child.is_file() and child.suffix.lower() == ".qxw"
         and not child.name.startswith((".", "~$"))
         and ".autosave" not in child.name.lower()
         and child.resolve() != resolved_out),
        key=lambda path: path.name)

    if not candidates:
        return None
    if len(candidates) > 1:
        others = ", ".join(path.name for path in candidates[1:])
        print(f"  ⚠ 底下有多個 .qxw，採用 {candidates[0].name}（略過 {others}）",
              file=sys.stderr)
    return candidates[0]


def base_fixture_ids(base_path: Path) -> set:
    """取出底稿裡已定義的 Fixture ID。"""
    text = base_path.read_text(encoding="utf-8")
    engine = text[:text.rindex("</Engine>")] if "</Engine>" in text else text
    return {int(i) for i in re.findall(r"<Fixture>.*?<ID>(\d+)</ID>", engine, re.S)}


def warn_missing_fixtures(base_path: Path, shows: List["ShowSpec"]) -> None:
    """合併前確認底稿有這些 Sequence 用到的燈具。"""
    try:
        available = base_fixture_ids(base_path)
    except (OSError, ValueError):
        return
    needed = {head.fixture_id: head.name for _, head in all_fixtures(shows)}
    missing = sorted(fid for fid in needed if fid not in available)
    if missing:
        detail = ", ".join(f"{needed[fid]}(ID {fid})" for fid in missing)
        print(f"  ⚠ 底稿 {base_path.name} 沒有這些燈具，合併後這些通道不會生效: "
              f"{detail}", file=sys.stderr)


def scan_project(root: Path, out_path: Path, *, keep_zeros: bool, trim: bool,
                 only_sheets: Optional[List[str]], name_from: str) -> List[ShowSpec]:
    """掃描專案資料夾，每個子資料夾變成一個 Show。

    子資料夾裡的 .xlsx/.csv 會轉成 Sequence，.mp3 會變成配樂；
    若資料夾本身就放著表格，則整個資料夾當成單一個 Show。
    """
    folders = sorted((child for child in root.iterdir()
                      if child.is_dir() and not child.name.startswith(".")),
                     key=lambda path: path.name)
    if not any(child.suffix.lower() in TABLE_SUFFIXES
               for folder in folders for child in folder.iterdir()):
        folders = [root]

    shows: List[ShowSpec] = []
    for folder in folders:
        entries = sorted(folder.iterdir(), key=lambda path: path.name)
        tables = [e for e in entries if e.suffix.lower() in TABLE_SUFFIXES
                  and not e.name.startswith("~$")]
        audios = [e for e in entries if e.suffix.lower() in AUDIO_SUFFIXES]

        if not tables:
            print(f"  ⚠ 略過沒有表格檔的資料夾: {folder.name}", file=sys.stderr)
            continue

        blocks = load_blocks(tables, keep_zeros=keep_zeros, trim=trim,
                             only_sheets=only_sheets, name_from=name_from,
                             group=folder.name, resolve=False)

        audio: Optional[AudioSpec] = None
        if audios:
            if len(audios) > 1:
                print(f"  ⚠ {folder.name} 有多個音檔，只用 {audios[0].name}",
                      file=sys.stderr)
            duration = mp3_duration_ms(audios[0])
            if duration is None:
                print(f"  ⚠ 讀不出長度，略過音檔: {audios[0].name}", file=sys.stderr)
            else:
                audio = AudioSpec(name=audios[0].name,
                                  source=audio_source(audios[0], out_path),
                                  duration_ms=duration)
        else:
            print(f"  ⚠ {folder.name} 沒有 .mp3 配樂", file=sys.stderr)

        shows.append(ShowSpec(blocks=blocks, name=folder.name, audio=audio))

    if not shows:
        raise CsvFormatError(f"{root} 底下找不到任何可以轉換的資料夾。")

    finalize_names(all_blocks(shows), name_from=name_from)
    return shows


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 cuelist CSV 轉成 QLC+ 的 Sequence (.qxw)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="支援 .csv 與 .xlsx。Excel 的每張工作表、每個自動化表格都會變成一條 Sequence。",
    )
    parser.add_argument("csv", type=Path, nargs="*", default=None, metavar="來源",
                        help="專案資料夾，或 .xlsx / .csv 檔（可指定多個）。"
                             "給資料夾時，底下每個子資料夾會變成一個 Show。"
                             f"預設 {DEFAULT_INPUTS[0]}")
    parser.add_argument("--sheet", action="append",
                        help="只轉換指定的 Excel 工作表；可重複指定")
    parser.add_argument("--list", action="store_true", dest="list_only",
                        help="只列出檔案裡有哪些工作表與自動化表格，不做轉換")
    parser.add_argument("-o", "--out", type=Path, help="輸出檔路徑（預設沿用第一個 CSV 檔名）")
    parser.add_argument("--mode", choices=("workspace", "snippet", "merge"),
                        default=None,
                        help="輸出型態。預設會自動判斷：專案資料夾底下有 .qxw "
                             "就用 merge 併進去，否則產生獨立的 workspace")
    parser.add_argument("--base", type=Path,
                        help="merge 模式要插入的既有 .qxw")
    parser.add_argument("--name", action="append",
                        help="Sequence 名稱；可重複指定，依序對應每張表")
    parser.add_argument("--name-from", choices=("sheet", "title"), default="sheet",
                        help="Sequence 名稱的來源：sheet=Excel 工作表名稱（預設）、"
                             "title=表格自己的「自動化表格 …」標題")
    parser.add_argument("--folder", default=DEFAULT_FOLDER,
                        help="把 Sequence 收進這個資料夾（QLC+ 的 Path）；"
                             f"預設 {DEFAULT_FOLDER}，給空字串則不分資料夾")
    parser.add_argument("--music-folder", default=DEFAULT_MUSIC_FOLDER,
                        help=f"配樂放的資料夾（預設 {DEFAULT_MUSIC_FOLDER}）")
    parser.add_argument("--show-folder", default=DEFAULT_SHOW_FOLDER,
                        help=f"Show 放的資料夾（預設 {DEFAULT_SHOW_FOLDER}）")
    parser.add_argument("--run-order", choices=("SingleShot", "Loop", "PingPong"),
                        default="SingleShot")
    parser.add_argument("--direction", choices=("Forward", "Backward"), default="Forward")
    parser.add_argument("--keep-zeros", action="store_true",
                        help="保留數值為 0 的通道（預設略過，與現有 .qxw 一致）")
    parser.add_argument("--no-trim", action="store_true",
                        help="不要砍掉表格尾端重複的填充列")
    parser.add_argument("--stdout", action="store_true", help="輸出到畫面而不是檔案")
    args = parser.parse_args(argv)

    paths = list(args.csv) if args.csv else default_inputs()
    if not paths:
        parser.error(f"找不到預設輸入檔（{' 或 '.join(map(str, DEFAULT_INPUTS))}），"
                     "請直接指定來源檔。")
    for path in paths:
        if not path.exists():
            parser.error(f"找不到來源檔: {path}")
    if args.base and not args.base.exists():
        parser.error(f"找不到 base .qxw: {args.base}")

    if args.list_only:
        for path in paths:
            print(f"{path}")
            if path.is_dir():
                for folder in sorted((c for c in path.iterdir()
                                      if c.is_dir() and not c.name.startswith(".")),
                                     key=lambda c: c.name):
                    entries = sorted(folder.iterdir(), key=lambda c: c.name)
                    tables = [e.name for e in entries
                              if e.suffix.lower() in TABLE_SUFFIXES
                              and not e.name.startswith("~$")]
                    audios = [e.name for e in entries
                              if e.suffix.lower() in AUDIO_SUFFIXES]
                    print(f"  ▸ {folder.name}/")
                    for name in tables:
                        print(f"      表格 {name}")
                    for name in audios:
                        print(f"      配樂 {name}")
                continue
            for sheet, rows in read_tables(path):
                raws = split_blocks(rows)
                label = sheet or "(CSV)"
                if not raws:
                    print(f"  - {label}: 沒有自動化表格")
                    continue
                titles = ", ".join(raw.title or "(無標題)" for raw in raws)
                print(f"  - {label}: {len(raws)} 個表格 [{titles}]")
        return 0

    project = paths[0] if len(paths) == 1 and paths[0].is_dir() else None
    out_path = args.out or (paths[0].with_suffix(".qxw") if project is None
                            else project.resolve().with_suffix(".qxw"))

    try:
        if project is not None:
            shows = scan_project(project, out_path, keep_zeros=args.keep_zeros,
                                 trim=not args.no_trim, only_sheets=args.sheet,
                                 name_from=args.name_from)
        else:
            blocks = load_blocks(paths, keep_zeros=args.keep_zeros,
                                 trim=not args.no_trim, names=args.name,
                                 only_sheets=args.sheet,
                                 name_from=args.name_from)
            shows = [ShowSpec(blocks=blocks)]
    except CsvFormatError as exc:
        parser.error(str(exc))

    # 專案資料夾底下若放了底稿 .qxw，預設就併進去；沒有就產生獨立的 workspace。
    base = args.base
    if base is None and project is not None and args.mode in (None, "merge"):
        base = find_base_qxw(project, out_path)
        if base is not None:
            print(f"  底稿: {base.name}", file=sys.stderr)

    mode = args.mode or ("merge" if base is not None else "workspace")
    if mode == "merge":
        if base is None:
            parser.error("merge 模式需要 --base 指定既有的 .qxw，"
                         "或把底稿放進專案資料夾底下")
        warn_missing_fixtures(base, shows)

    shared = dict(run_order=args.run_order, direction=args.direction,
                  folder=args.folder, music_folder=args.music_folder,
                  show_folder=args.show_folder)

    if mode == "snippet":
        output = render_functions(shows, first_id=0, indent="", **shared) + "\n"
        out_path = args.out or out_path.with_suffix(".xml")
    elif mode == "merge":
        output = merge_into_workspace(base, shows, **shared)
    else:
        output = render_workspace(shows, **shared)

    if args.stdout:
        sys.stdout.write(output)
    else:
        out_path.write_text(output, encoding="utf-8")
        print(f"已輸出: {out_path}")

    folder_note = f"（資料夾 {args.folder}）" if args.folder else "（不分資料夾）"
    total = len(all_blocks(shows))
    if project is not None:
        print(f"  Shows: {len(shows)}（資料夾 {args.show_folder}）／"
              f"Sequences: {total} {folder_note}", file=sys.stderr)
    else:
        print(f"  Sequences: {total} {folder_note}", file=sys.stderr)

    for show in shows:
        if show.name:
            print(f"  ▸ Show {show.name}", file=sys.stderr)
        if show.audio is not None:
            print(f"      ♪ {show.audio.name}: {show.audio.duration_ms} ms "
                  f"（資料夾 {args.music_folder}）", file=sys.stderr)
        for block in show.blocks:
            fixtures = ", ".join(f"{h.name}(ID {h.fixture_id})"
                                 for _, h in used_fixtures(block.columns))
            origin = f"[工作表 {block.sheet}] " if block.sheet else ""
            print(f"      - {origin}{block.name}: {len(block.steps)} steps, "
                  f"{block.total_ms} ms, [{fixtures}]", file=sys.stderr)
            if block.unknown:
                print(f"        略過的欄位: {', '.join(block.unknown)}",
                      file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
