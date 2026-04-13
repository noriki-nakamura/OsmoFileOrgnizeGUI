"""
tests/test_core.py
------------------
organizer_core.py のユニットテスト。

テスト対象:
    - format_size()       : バイト数のフォーマット
    - parse_exts()        : 拡張子文字列のパース
    - get_media_date()    : メディアファイルからの日付取得
    - build_dest_path()   : 整理先パスの生成
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# テスト対象モジュール
from organizer_core import (
    format_size,
    parse_exts,
    get_media_date,
    build_dest_path,
)


# ══════════════════════════════════════════════
# format_size() のテスト
# ══════════════════════════════════════════════

class TestFormatSize:
    """format_size() の境界値・正常系テスト"""

    def test_zero_bytes(self):
        assert format_size(0) == "0 B"

    def test_less_than_1kb(self):
        assert format_size(999) == "999 B"

    def test_exactly_1kb(self):
        assert format_size(1024) == "1.0 KB"

    def test_less_than_1mb(self):
        assert format_size(1024 * 512) == "512.0 KB"

    def test_exactly_1mb(self):
        assert format_size(1024 * 1024) == "1.0 MB"

    def test_less_than_1gb(self):
        assert format_size(1024 * 1024 * 500) == "500.0 MB"

    def test_exactly_1gb(self):
        assert format_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_multi_gb(self):
        assert format_size(1024 * 1024 * 1024 * 2) == "2.0 GB"


# ══════════════════════════════════════════════
# parse_exts() のテスト
# ══════════════════════════════════════════════

class TestParseExts:
    """parse_exts() のパース・正規化テスト"""

    def test_single_ext_with_dot(self):
        assert parse_exts(".MP4") == [".mp4"]

    def test_single_ext_without_dot(self):
        assert parse_exts("MP4") == [".mp4"]

    def test_multiple_exts(self):
        assert parse_exts(".MP4, .JPG") == [".mp4", ".jpg"]

    def test_mixed_dot_nodot(self):
        assert parse_exts("MP4, .JPG, DNG") == [".mp4", ".jpg", ".dng"]

    def test_with_extra_spaces(self):
        assert parse_exts("  .MP4 ,  JPG  ") == [".mp4", ".jpg"]

    def test_empty_string(self):
        assert parse_exts("") == []

    def test_only_comma(self):
        assert parse_exts(",") == []

    def test_lowercase_preserved(self):
        result = parse_exts(".mp4")
        assert result == [".mp4"]

    def test_mixed_case_normalized(self):
        result = parse_exts(".LRF, .THM")
        assert result == [".lrf", ".thm"]


# ══════════════════════════════════════════════
# get_media_date() のテスト
# ══════════════════════════════════════════════

class TestGetMediaDate:
    """get_media_date() のメタデータ取得とフォールバックのテスト"""

    def test_fallback_uses_mtime(self, tmp_path):
        """EXIFもmp4タグもないファイルはファイル更新日時を返す"""
        dummy = tmp_path / "dummy.txt"
        dummy.write_bytes(b"\x00" * 100)

        # ファイルの更新日時を固定値に設定
        target_dt = datetime(2024, 5, 10)
        ts = target_dt.timestamp()
        os.utime(dummy, (ts, ts))

        result = get_media_date(dummy)
        assert result == "2024-05-10"

    def test_mp4_with_valid_tag(self, tmp_path):
        """MP4 で ©day タグがある場合はタグの日付を返す"""
        mp4_file = tmp_path / "video.mp4"
        mp4_file.write_bytes(b"\x00" * 100)

        mock_tags = {"\xa9day": ["2024:06:15 10:00:00"]}
        mock_audio = MagicMock()
        mock_audio.tags = mock_tags

        with patch("organizer_core.MP4", return_value=mock_audio):
            result = get_media_date(mp4_file)

        assert result == "2024-06-15"

    def test_mp4_without_tag_falls_back(self, tmp_path):
        """MP4 で ©day タグがない場合はファイル更新日時を返す"""
        mp4_file = tmp_path / "video.mp4"
        mp4_file.write_bytes(b"\x00" * 100)

        target_dt = datetime(2024, 7, 1)
        os.utime(mp4_file, (target_dt.timestamp(), target_dt.timestamp()))

        mock_audio = MagicMock()
        mock_audio.tags = {}  # タグなし

        with patch("organizer_core.MP4", return_value=mock_audio):
            result = get_media_date(mp4_file)

        assert result == "2024-07-01"

    def test_mp4_exception_falls_back(self, tmp_path):
        """MP4 モジュールが例外を投げた場合はファイル更新日時を返す"""
        mp4_file = tmp_path / "broken.mp4"
        mp4_file.write_bytes(b"\x00" * 100)

        target_dt = datetime(2024, 8, 20)
        os.utime(mp4_file, (target_dt.timestamp(), target_dt.timestamp()))

        with patch("organizer_core.MP4", side_effect=Exception("read error")):
            result = get_media_date(mp4_file)

        assert result == "2024-08-20"

    def test_jpg_with_exif_date(self, tmp_path):
        """JPEG で DateTimeOriginal (36867) がある場合はその日付を返す"""
        jpg_file = tmp_path / "photo.jpg"
        jpg_file.write_bytes(b"\x00" * 100)

        mock_exif = {36867: "2024:03:22 15:30:00"}
        mock_img = MagicMock()
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_img.getexif.return_value = mock_exif

        with patch("organizer_core.Image.open", return_value=mock_img):
            result = get_media_date(jpg_file)

        assert result == "2024-03-22"

    def test_jpg_without_exif_falls_back(self, tmp_path):
        """JPEG で EXIF がない場合はファイル更新日時を返す"""
        jpg_file = tmp_path / "photo.jpg"
        jpg_file.write_bytes(b"\x00" * 100)

        target_dt = datetime(2024, 9, 5)
        os.utime(jpg_file, (target_dt.timestamp(), target_dt.timestamp()))

        mock_img = MagicMock()
        mock_img.__enter__ = MagicMock(return_value=mock_img)
        mock_img.__exit__ = MagicMock(return_value=False)
        mock_img.getexif.return_value = {}  # EXIFなし

        with patch("organizer_core.Image.open", return_value=mock_img):
            result = get_media_date(jpg_file)

        assert result == "2024-09-05"


# ══════════════════════════════════════════════
# build_dest_path() のテスト
# ══════════════════════════════════════════════

class TestBuildDestPath:
    """build_dest_path() のフォルダ構成生成テスト"""

    # ── 共通フィクスチャ ──────────────────────
    @pytest.fixture
    def video_file(self, tmp_path):
        f = tmp_path / "DJI_0001.MP4"
        f.touch()
        return f

    @pytest.fixture
    def photo_file(self, tmp_path):
        f = tmp_path / "DJI_0002.JPG"
        f.touch()
        return f

    @pytest.fixture
    def misc_file(self, tmp_path):
        f = tmp_path / "DJI_0003.LRF"
        f.touch()
        return f

    def _build(self, file_path, file_type="動画", date="2024-05-10", **kwargs):
        """build_dest_path をデフォルト引数付きで呼ぶヘルパー"""
        defaults = dict(
            group_date=True,
            date_format="YYYYMMDD",
            split_type=True,
            video_folder="Videos",
            photo_folder="Photos",
            misc_folder="Misc",
            group_ext=False,
            folder_order="日付 > 種類",
        )
        defaults.update(kwargs)
        return build_dest_path(
            file_path=file_path,
            date=date,
            file_type=file_type,
            **defaults,
        )

    # ── 基本シナリオ ──────────────────────────

    def test_date_and_type_video(self, video_file):
        """日付 > 種類、動画ファイルの標準ケース"""
        result = self._build(video_file, file_type="動画")
        assert result == Path("20240510") / "Videos" / "DJI_0001.MP4"

    def test_date_and_type_photo(self, photo_file):
        """日付 > 種類、写真ファイルの標準ケース"""
        result = self._build(photo_file, file_type="写真")
        assert result == Path("20240510") / "Photos" / "DJI_0002.JPG"

    def test_date_and_type_misc(self, misc_file):
        """日付 > 種類、その他ファイルの標準ケース"""
        result = self._build(misc_file, file_type="その他")
        assert result == Path("20240510") / "Misc" / "DJI_0003.LRF"

    # ── 日付フォーマット ──────────────────────

    def test_date_format_yyyymmdd(self, video_file):
        """YYYYMMDD 形式（ハイフンなし）のフォルダ名"""
        result = self._build(video_file, date_format="YYYYMMDD")
        assert "20240510" in str(result)

    def test_date_format_yyyy_mm_dd(self, video_file):
        """YYYY-MM-DD 形式（ハイフンあり）のフォルダ名"""
        result = self._build(video_file, date_format="YYYY-MM-DD")
        assert "2024-05-10" in str(result)

    # ── 日付グループのON/OFF ─────────────────

    def test_no_date_grouping(self, video_file):
        """日付グループOFF → 日付フォルダなし"""
        result = self._build(video_file, group_date=False)
        assert "20240510" not in str(result)
        assert "Videos" in str(result)

    def test_no_type_split(self, video_file):
        """種類分けOFF → 種類フォルダなし"""
        result = self._build(video_file, split_type=False)
        assert "Videos" not in str(result)
        assert "20240510" in str(result)

    def test_all_off_flat(self, video_file):
        """全部OFF → ファイル名のみ"""
        result = self._build(video_file, group_date=False, split_type=False)
        assert result == Path("DJI_0001.MP4")

    # ── 階層順序 ─────────────────────────────

    def test_order_type_then_date(self, video_file):
        """種類 > 日付 の順序"""
        result = self._build(video_file, folder_order="種類 > 日付")
        parts = result.parts
        assert parts[0] == "Videos"
        assert parts[1] == "20240510"
        assert parts[-1] == "DJI_0001.MP4"

    def test_order_date_then_type_default(self, video_file):
        """日付 > 種類 の順序（デフォルト）"""
        result = self._build(video_file, folder_order="日付 > 種類")
        parts = result.parts
        assert parts[0] == "20240510"
        assert parts[1] == "Videos"

    # ── 拡張子ごとの整理 ─────────────────────

    def test_group_by_ext(self, video_file):
        """拡張子グループON → 拡張子フォルダが追加される"""
        result = self._build(
            video_file,
            group_ext=True,
            folder_order="日付 > 種類 > 拡張子"
        )
        parts = result.parts
        assert "MP4" in parts

    def test_group_by_ext_order(self, photo_file):
        """日付 > 種類 > 拡張子 の順序確認"""
        result = self._build(
            photo_file,
            file_type="写真",
            group_ext=True,
            folder_order="日付 > 種類 > 拡張子"
        )
        parts = result.parts
        assert parts[0] == "20240510"
        assert parts[1] == "Photos"
        assert parts[2] == "JPG"
        assert parts[-1] == "DJI_0002.JPG"

    # ── カスタムフォルダ名 ────────────────────

    def test_custom_video_folder_name(self, video_file):
        """動画フォルダ名をカスタム設定した場合"""
        result = self._build(video_file, video_folder="Clips")
        assert "Clips" in str(result)

    def test_custom_photo_folder_name(self, photo_file):
        """写真フォルダ名をカスタム設定した場合"""
        result = self._build(photo_file, file_type="写真", photo_folder="Images")
        assert "Images" in str(result)

    def test_custom_misc_folder_name(self, misc_file):
        """その他フォルダ名をカスタム設定した場合"""
        result = self._build(misc_file, file_type="その他", misc_folder="Others")
        assert "Others" in str(result)

    def test_empty_video_folder_falls_back(self, video_file):
        """動画フォルダ名が空の場合はデフォルト "Videos" を使用"""
        result = self._build(video_file, video_folder="")
        assert "Videos" in str(result)

    def test_empty_photo_folder_falls_back(self, photo_file):
        """写真フォルダ名が空の場合はデフォルト "Photos" を使用"""
        result = self._build(photo_file, file_type="写真", photo_folder="")
        assert "Photos" in str(result)

    # ── ファイル名が末端にある ────────────────

    def test_filename_is_last_part(self, video_file):
        """結果パスの末尾が常にファイル名"""
        result = self._build(video_file)
        assert result.name == "DJI_0001.MP4"

    def test_different_date(self, video_file):
        """異なる日付が正しくフォルダ名に反映される"""
        result = self._build(video_file, date="2025-12-31", date_format="YYYY-MM-DD")
        assert "2025-12-31" in str(result)
