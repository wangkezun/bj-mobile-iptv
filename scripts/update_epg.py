#!/usr/bin/env python3
"""合并公开 XMLTV 源，并生成只包含北京移动列表频道的 EPG。"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
BRACKET_RE = re.compile(r"\[[^\]]*]")


@dataclass
class GuideChannel:
    source: int
    channel_id: str
    names: list[str]
    element: ET.Element
    programmes: list[ET.Element]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist", required=True, type=Path)
    parser.add_argument("--source", required=True, action="append", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mapping-output", required=True, type=Path)
    return parser.parse_args()


def normalize(value: str) -> str:
    value = BRACKET_RE.sub("", value).upper().replace("记录", "纪录")
    return re.sub(r"[\s_()（）\-—·]+", "", value)


def open_xml(path: Path):
    with path.open("rb") as stream:
        compressed = stream.read(2) == b"\x1f\x8b"
    return gzip.open(path, "rb") if compressed else path.open("rb")


def load_guide(path: Path, source: int) -> list[GuideChannel]:
    with open_xml(path) as stream:
        root = ET.parse(stream).getroot()

    programmes: dict[str, list[ET.Element]] = defaultdict(list)
    for programme in root.findall("programme"):
        programmes[programme.get("channel", "")].append(programme)

    result: list[GuideChannel] = []
    for channel in root.findall("channel"):
        channel_id = channel.get("id", "")
        names = [
            (node.text or "").strip()
            for node in channel.findall("display-name")
            if (node.text or "").strip()
        ]
        result.append(
            GuideChannel(
                source,
                channel_id,
                names,
                channel,
                programmes.get(channel_id, []),
            )
        )
    return result


def playlist_channels(text: str) -> list[tuple[str, str]]:
    result = []
    for line in text.splitlines():
        if not line.startswith("#EXTINF:"):
            continue
        attrs = dict(ATTR_RE.findall(line))
        title = line.split(",", 1)[1].strip() if "," in line else ""
        result.append((attrs.get("tvg-name", ""), title))
    return result


def candidate_names(tvg_name: str, title: str) -> list[str]:
    aliases = {
        "北京卫视": ["BRTV北京卫视"],
        "BTV新闻": ["BRTV新闻", "北京新闻"],
        "BTV影视": ["BRTV影视", "北京影视"],
        "BTV文艺": ["BRTV文艺", "北京文艺"],
        "BTV财经": ["BRTV财经", "北京财经"],
        "BTV生活": ["BRTV生活", "北京生活"],
        "BTV科教": ["BRTV纪实科教", "北京纪实科教"],
        "卡酷动画": ["BRTV卡酷少儿", "卡酷少儿"],
        "BTV体育": ["BRTV体育休闲", "北京体育休闲"],
        "旅游卫视": ["海南卫视"],
        "CGTN": ["CGTN英语"],
        "CGTNDocumentary": ["CGTN纪录", "CGTN记录"],
        "中国教育1台": ["CETV1", "教育1台"],
        "中国教育2台": ["CETV2", "教育2台"],
        "中国教育4台": ["CETV4", "教育4台"],
    }
    names: list[str] = []
    if tvg_name and tvg_name != "该频道节目单尚无":
        names.append(tvg_name)
        names.extend(aliases.get(tvg_name, []))
    title_without_quality = BRACKET_RE.sub("", title).strip()
    names.extend((title_without_quality, title_without_quality.replace(" ", "")))
    title_aliases = {
        "CGTN 阿拉伯语": ["CGTN阿语"],
    }
    names.extend(title_aliases.get(title_without_quality, []))
    return list(dict.fromkeys(name for name in names if name))


def choose_channels(
    playlist: list[tuple[str, str]],
    guides: list[list[GuideChannel]],
) -> tuple[dict[str, GuideChannel], dict[tuple[int, str], str]]:
    indexes: list[dict[str, list[GuideChannel]]] = []
    for channels in guides:
        index: dict[str, list[GuideChannel]] = defaultdict(list)
        for channel in channels:
            for name in (channel.channel_id, *channel.names):
                key = normalize(name)
                if key:
                    index[key].append(channel)
        indexes.append(index)

    selected_by_title: dict[str, GuideChannel] = {}
    output_ids: dict[tuple[int, str], str] = {}
    for position, (tvg_name, title) in enumerate(playlist, start=1):
        selected = None
        for index in indexes:
            matches: list[GuideChannel] = []
            for name in candidate_names(tvg_name, title):
                matches.extend(index.get(normalize(name), []))
            if matches:
                unique = {(item.source, item.channel_id): item for item in matches}
                with_programmes = [
                    item for item in unique.values() if item.programmes
                ]
                if not with_programmes:
                    continue
                selected = max(
                    with_programmes,
                    key=lambda item: (len(item.programmes), len(item.names)),
                )
                break
        if not selected:
            continue
        selected_by_title[title] = selected
        key = (selected.source, selected.channel_id)
        if key not in output_ids:
            output_ids[key] = f"bj-mobile-{position:03d}"
    return selected_by_title, output_ids


def write_guide(
    output: Path,
    selected: dict[str, GuideChannel],
    output_ids: dict[tuple[int, str], str],
) -> tuple[int, int]:
    root = ET.Element(
        "tv",
        {
            "generator-info-name": "bj-mobile-iptv",
            "generator-info-url": "https://github.com/wangkezun/bj-mobile-iptv",
        },
    )
    unique = {
        (channel.source, channel.channel_id): channel
        for channel in selected.values()
    }
    programme_count = 0
    for key, channel in unique.items():
        element = copy.deepcopy(channel.element)
        element.set("id", output_ids[key])
        root.append(element)
    for key, channel in unique.items():
        for programme in channel.programmes:
            element = copy.deepcopy(programme)
            element.set("channel", output_ids[key])
            root.append(element)
            programme_count += 1

    ET.indent(root, space="  ")
    xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(
            filename="", fileobj=raw, mode="wb", mtime=0
        ) as compressed:
            compressed.write(xml)
    return len(unique), programme_count


def write_mapping(
    output: Path,
    selected: dict[str, GuideChannel],
    output_ids: dict[tuple[int, str], str],
) -> None:
    channels = {}
    for title, channel in selected.items():
        key = (channel.source, channel.channel_id)
        channels[title] = {
            "tvg-id": output_ids[key],
            "tvg-name": channel.names[0] if channel.names else channel.channel_id,
        }
    output.write_text(
        json.dumps({"channels": channels}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_epg(
    playlist_text: str,
    source_paths: list[Path],
    output: Path,
    mapping_output: Path,
) -> tuple[int, int, int]:
    guides = [load_guide(path, index) for index, path in enumerate(source_paths)]
    playlist = playlist_channels(playlist_text)
    selected, output_ids = choose_channels(playlist, guides)
    guide_channels, programmes = write_guide(output, selected, output_ids)
    write_mapping(mapping_output, selected, output_ids)
    return len(selected), guide_channels, programmes


def main() -> None:
    args = parse_args()
    matched, channels, programmes = build_epg(
        args.playlist.read_text(encoding="utf-8-sig"),
        args.source,
        args.output,
        args.mapping_output,
    )
    print(
        f"已生成 {args.output}: 匹配 {matched} 个播放项，"
        f"{channels} 个节目单频道，{programmes} 条节目"
    )


if __name__ == "__main__":
    main()
