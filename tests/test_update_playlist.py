import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_playlist import update_playlist  # noqa: E402


class UpdatePlaylistTest(unittest.TestCase):
    def test_adds_logo_epg_mapping_and_https_url(self):
        source = """#EXTM3U x-tvg-url="http://epg.51zmt.top:8000/e.xml.gz"
#EXTINF:-1 tvg-name="CCTV1",CCTV-1 综合[高清]
rtp://228.1.1.28:8008
"""
        logos = "CCTV1\n"
        mapping = {
            "channels": {
                "CCTV-1 综合[高清]": {
                    "tvg-id": "bj-mobile-001",
                    "tvg-name": "CCTV1",
                }
            }
        }
        result, channels, logo_count, epg_count = update_playlist(
            source,
            logos,
            mapping,
            "https://raw.githubusercontent.com/example/repo/main/epg.xml.gz",
        )
        self.assertIn(
            'x-tvg-url="https://raw.githubusercontent.com/example/'
            'repo/main/epg.xml.gz"',
            result,
        )
        self.assertIn('tvg-id="bj-mobile-001"', result)
        self.assertIn(
            'tvg-logo="https://cdn.jsdelivr.net/gh/mytv-android/'
            'myTVlogo@main/img/CCTV1.png"',
            result,
        )
        self.assertIn("rtp://228.1.1.28:8008", result)
        self.assertEqual((channels, logo_count, epg_count), (1, 1, 1))

    def test_does_not_use_placeholder_epg_name_for_matching(self):
        source = """#EXTM3U
#EXTINF:-1 tvg-name="该频道节目单尚无",完全不存在[高清]
rtp://228.1.1.2:8000
"""
        logos = "别的频道\n"
        result, _, logo_count, epg_count = update_playlist(
            source,
            logos,
            {"channels": {}},
            "https://example.com/epg.xml.gz",
        )
        self.assertNotIn("tvg-logo=", result)
        self.assertEqual(logo_count, 0)
        self.assertEqual(epg_count, 0)

    def test_replaces_existing_logo_with_mytvlogo(self):
        source = """#EXTM3U
#EXTINF:-1 tvg-name="北京卫视" tvg-logo="https://old.example/logo.png",BRTV北京卫视[高清]
rtp://228.1.1.235:8002
"""
        result, _, logo_count, _ = update_playlist(
            source,
            "北京卫视\nBRTV北京卫视\n",
            {"channels": {}},
            "https://example.com/epg.xml.gz",
        )
        self.assertNotIn("old.example", result)
        self.assertIn("myTVlogo@main/img/%E5%8C%97%E4%BA%AC%E5%8D%AB%E8%A7%86.png", result)
        self.assertEqual(logo_count, 1)

    def test_uses_verified_display_name_alias(self):
        source = """#EXTM3U
#EXTINF:-1 tvg-name="该频道节目单尚无",密云电视台[高清]
rtp://228.1.1.62:8002
"""
        result, _, logo_count, _ = update_playlist(
            source,
            "密云\n",
            {"channels": {}},
            "https://example.com/epg.xml.gz",
        )
        self.assertIn(
            "myTVlogo@main/img/%E5%AF%86%E4%BA%91.png",
            result,
        )
        self.assertEqual(logo_count, 1)

    def test_rejects_non_https_epg_url(self):
        with self.assertRaises(ValueError):
            update_playlist(
                "#EXTM3U\n",
                "CCTV1\n",
                {"channels": {}},
                "http://example.com/epg.xml.gz",
            )


if __name__ == "__main__":
    unittest.main()
