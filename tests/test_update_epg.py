import gzip
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_epg import build_epg  # noqa: E402


class UpdateEpgTest(unittest.TestCase):
    def test_filters_guide_and_creates_stable_mapping(self):
        playlist = """#EXTM3U
#EXTINF:-1 tvg-name="CCTV1",CCTV-1 综合[高清]
rtp://228.1.1.28:8008
#EXTINF:-1 tvg-name="该频道节目单尚无",不存在[高清]
rtp://228.1.1.29:8008
"""
        guide = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="CCTV1"><display-name>CCTV1</display-name></channel>
  <channel id="OTHER"><display-name>别的频道</display-name></channel>
  <programme channel="CCTV1" start="20260720000000 +0800" stop="20260720010000 +0800">
    <title>测试节目</title>
  </programme>
  <programme channel="OTHER" start="20260720000000 +0800" stop="20260720010000 +0800">
    <title>不应保留</title>
  </programme>
</tv>
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.xml"
            output = root / "output.xml.gz"
            mapping = root / "mapping.json"
            source.write_text(guide, encoding="utf-8")

            matched, channels, programmes = build_epg(
                playlist, [source], output, mapping
            )

            self.assertEqual((matched, channels, programmes), (1, 1, 1))
            with gzip.open(output, "rb") as stream:
                tree = ET.parse(stream)
            self.assertEqual(tree.find("channel").get("id"), "bj-mobile-001")
            self.assertEqual(
                tree.find("programme").get("channel"), "bj-mobile-001"
            )
            data = json.loads(mapping.read_text(encoding="utf-8"))
            self.assertEqual(
                data["channels"]["CCTV-1 综合[高清]"]["tvg-id"],
                "bj-mobile-001",
            )


if __name__ == "__main__":
    unittest.main()
