# 北京移动 IPTV 组播列表

本项目自动获取 [qwerttvv/Beijing-IPTV](https://github.com/qwerttvv/Beijing-IPTV)
中的北京移动组播列表，并使用
[mytv-android/myTVlogo](https://github.com/mytv-android/myTVlogo)
统一补充 `tvg-logo`。

生成结果：

- `bj-mobile-iptv.m3u`
- `bj-mobile-epg.xml.gz`

最新版本可以从
[GitHub Releases](https://github.com/wangkezun/bj-mobile-iptv/releases/latest)
下载：

- [播放列表](https://github.com/wangkezun/bj-mobile-iptv/releases/latest/download/bj-mobile-iptv.m3u)
- [节目单](https://github.com/wangkezun/bj-mobile-iptv/releases/latest/download/bj-mobile-epg.xml.gz)

处理规则：

- 保留原始 `rtp://228.1.1.x` 北京移动组播地址；
- 优先按 `tvg-name` 匹配 `myTVlogo` 文件名，再按去除清晰度标记后的
  频道显示名及少量已确认别名匹配；
- 不使用“该频道节目单尚无”作为匹配键，防止不同频道误用同一台标；
- 台标统一使用 jsDelivr CDN 提供的 `myTVlogo` 图片；
- 合并 [EPG.PW 中国节目单](https://epg.pw/xmltv/epg_CN.xml.gz) 和
  [suzukua/epg](https://epg.zsdc.eu.org/t.xml.gz)，只保留本列表能匹配的频道；
- 为匹配成功的频道生成稳定 `tvg-id`，并修正无效的 `tvg-name`；
- M3U 通过 HTTPS 直接引用仓库中的压缩节目单，不再依赖
  `iptv.home.wkz.io` 反向代理；
- 每天北京时间 04:00 自动更新播放列表、台标映射和节目单，并发布带日期
  标签的 GitHub Release；同一天重复运行会覆盖当天 Release 的资产。

> 组播地址只能在能够访问北京移动 IPTV 组播网络的环境中播放。这里的
> HTTPS 地址仅用于 EPG 与台标资源，不会把组播流转换成公网单播流。

## 本地生成

```bash
curl -fsSL \
  https://raw.githubusercontent.com/qwerttvv/Beijing-IPTV/master/IPTV-Mobile-Multicast.m3u \
  -o /tmp/mobile.m3u
curl -fsSL \
  https://raw.githubusercontent.com/mytv-android/myTVlogo/main/logo_list.txt \
  -o /tmp/logo-list.txt
curl -fsSL https://epg.pw/xmltv/epg_CN.xml.gz -o /tmp/epg-primary.xml.gz
curl -fsSL https://epg.zsdc.eu.org/t.xml.gz -o /tmp/epg-fallback.xml.gz

python scripts/update_epg.py \
  --playlist /tmp/mobile.m3u \
  --source /tmp/epg-primary.xml.gz \
  --source /tmp/epg-fallback.xml.gz \
  --output bj-mobile-epg.xml.gz \
  --mapping-output /tmp/epg-map.json

python scripts/update_playlist.py \
  --input /tmp/mobile.m3u \
  --logo-list /tmp/logo-list.txt \
  --epg-map /tmp/epg-map.json \
  --output bj-mobile-iptv.m3u \
  --epg-url https://github.com/wangkezun/bj-mobile-iptv/releases/latest/download/bj-mobile-epg.xml.gz
```
