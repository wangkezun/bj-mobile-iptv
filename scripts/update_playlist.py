#!/usr/bin/env python3
"""更新北京移动 IPTV 列表，并从参考列表补全可匹配的台标。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit


EXTINF_RE = re.compile(r"^#EXTINF:")
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
BRACKET_RE = re.compile(r"\[[^\]]*]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path, help="北京移动源 M3U")
    parser.add_argument("--logo-list", required=True, type=Path, help="myTVlogo 文件清单")
    parser.add_argument("--epg-map", required=True, type=Path, help="EPG 频道映射")
    parser.add_argument("--output", required=True, type=Path, help="输出 M3U")
    parser.add_argument(
        "--logo-base",
        default="https://cdn.jsdelivr.net/gh/mytv-android/myTVlogo@main/img",
        help="myTVlogo 图片目录",
    )
    parser.add_argument(
        "--epg-url",
        required=True,
        help="HTTPS EPG 地址",
    )
    return parser.parse_args()


def attributes(line: str) -> dict[str, str]:
    return dict(ATTR_RE.findall(line))


def display_name(line: str) -> str:
    return line.split(",", 1)[1].strip() if "," in line else ""


def build_logo_index(text: str) -> tuple[set[str], dict[str, str]]:
    filenames = {line.strip() for line in text.splitlines() if line.strip()}
    casefolded: dict[str, str] = {}
    for filename in sorted(filenames):
        casefolded.setdefault(filename.casefold(), filename)
    return filenames, casefolded


def resolve_logo(
    line: str,
    index: tuple[set[str], dict[str, str]],
    logo_base: str,
) -> str | None:
    attrs = attributes(line)
    name = attrs.get("tvg-name", "")
    aliases = {
        "北京卫视": ["BRTV北京卫视"],
        "BTV新闻": ["BRTV新闻"],
        "BTV影视": ["BRTV影视"],
        "BTV文艺": ["BRTV文艺"],
        "BTV财经": ["BRTV财经"],
        "BTV生活": ["BRTV生活"],
        "BTV科教": ["BRTV纪实科教"],
        "卡酷动画": ["BRTV卡酷少儿"],
        "BTV体育": ["BRTV体育休闲"],
        "旅游卫视": ["海南卫视"],
        "CGTNDocumentary": ["CGTN纪录"],
        "中国教育1台": ["CETV1"],
        "中国教育2台": ["CETV2"],
        "中国教育4台": ["CETV4"],
    }
    display = BRACKET_RE.sub("", display_name(line)).strip()
    names: list[str] = []
    if name and name != "该频道节目单尚无":
        names.append(name)
        names.extend(aliases.get(name, []))
    names.extend((display, display.replace(" ", "")))
    display_aliases = {
        "光影": ["光影Y"],
        "密云电视台": ["密云"],
        "房山电视台": ["北京房山有线"],
        "延庆电视台": ["延庆1"],
        "早教": ["早教频道"],
        "美妆": ["美妆频道"],
        "鉴赏": ["鉴赏频道"],
    }
    names.extend(display_aliases.get(display, []))

    exact, casefolded = index
    for candidate in names:
        filename = candidate if candidate in exact else casefolded.get(candidate.casefold())
        if filename:
            return f"{logo_base.rstrip('/')}/{quote(filename, safe='')}.png"
    return None


def add_logo(line: str, logo: str) -> str:
    attrs = attributes(line)
    if attrs.get("tvg-logo"):
        old = attrs["tvg-logo"]
        return line.replace(f'tvg-logo="{old}"', f'tvg-logo="{logo}"', 1)

    match = re.search(r'tvg-name="[^"]*"', line)
    if match:
        return f'{line[:match.end()]} tvg-logo="{logo}"{line[match.end():]}'

    comma = line.find(",")
    if comma >= 0:
        return f'{line[:comma]} tvg-logo="{logo}"{line[comma:]}'
    return f'{line} tvg-logo="{logo}"'


def set_attribute(line: str, name: str, value: str) -> str:
    pattern = re.compile(rf'{re.escape(name)}="[^"]*"')
    replacement = f'{name}="{value}"'
    if pattern.search(line):
        return pattern.sub(replacement, line, count=1)

    marker = re.search(r'tvg-name="[^"]*"', line)
    if marker:
        return f"{line[:marker.start()]}{replacement} {line[marker.start():]}"
    comma = line.find(",")
    if comma >= 0:
        return f"{line[:comma]} {replacement}{line[comma:]}"
    return f"{line} {replacement}"


def validate_epg_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or not parsed.path.endswith(".xml.gz"):
        raise ValueError(f"EPG 必须是 HTTPS .xml.gz 地址: {value}")
    return value


def update_playlist(
    playlist: str,
    logo_list: str,
    epg_mapping: dict,
    epg_url: str,
    logo_base: str = "https://cdn.jsdelivr.net/gh/mytv-android/myTVlogo@main/img",
) -> tuple[str, int, int, int]:
    index = build_logo_index(logo_list)
    channel_mapping = epg_mapping.get("channels", {})
    output: list[str] = []
    active_channels = 0
    logo_count = 0
    epg_count = 0

    for line in playlist.splitlines():
        if line.startswith("#EXTM3U"):
            target = validate_epg_url(epg_url)
            if 'x-tvg-url="' in line:
                line = re.sub(r'x-tvg-url="[^"]*"', f'x-tvg-url="{target}"', line, count=1)
            else:
                line = f'{line} x-tvg-url="{target}"'
        elif EXTINF_RE.match(line):
            active_channels += 1
            logo = resolve_logo(line, index, logo_base)
            if logo:
                line = add_logo(line, logo)
            mapping = channel_mapping.get(display_name(line))
            if mapping:
                line = set_attribute(line, "tvg-id", mapping["tvg-id"])
                line = set_attribute(line, "tvg-name", mapping["tvg-name"])
                epg_count += 1
            if attributes(line).get("tvg-logo"):
                logo_count += 1
        output.append(line)

    return "\n".join(output) + "\n", active_channels, logo_count, epg_count


def main() -> None:
    args = parse_args()
    result, channels, logos, epg_channels = update_playlist(
        args.input.read_text(encoding="utf-8-sig"),
        args.logo_list.read_text(encoding="utf-8-sig"),
        json.loads(args.epg_map.read_text(encoding="utf-8")),
        args.epg_url,
        args.logo_base,
    )
    args.output.write_text(result, encoding="utf-8")
    print(
        f"已生成 {args.output}: {channels} 个有效频道，"
        f"{logos} 个频道带台标，{epg_channels} 个频道匹配节目单"
    )


if __name__ == "__main__":
    main()
