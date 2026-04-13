"""
organizer_core.py
-----------------
OSMO Pocket データ整理ツールのビジネスロジック。
UI (tkinter) に依存せず、ユニットテスト可能な純粋関数を提供する。
"""

import os
from pathlib import Path
from datetime import datetime

from mutagen.mp4 import MP4
from PIL import Image


# ──────────────────────────────────────────────
# メタデータ取得
# ──────────────────────────────────────────────

def get_media_date(filepath: Path) -> str:
    """メディアファイルから撮影日のメタデータ YYYY-MM-DD を抽出する。
    取得不能時はファイル更新日時を使用する。

    Args:
        filepath: 対象ファイルのパス

    Returns:
        YYYY-MM-DD 形式の日付文字列
    """
    ext = filepath.suffix.lower()
    try:
        if ext == '.mp4':
            audio = MP4(filepath)
            if audio.tags and '\xa9day' in audio.tags:
                date_str = audio.tags['\xa9day'][0]
                if len(date_str) >= 10:
                    return date_str[:10].replace(":", "-")  # YYYY-MM-DD
        elif ext in ['.jpg', '.jpeg']:
            with Image.open(filepath) as img:
                exif = img.getexif()
                if exif and 36867 in exif:  # DateTimeOriginal
                    date_str = exif[36867]
                    if len(date_str) >= 10:
                        return date_str.split()[0].replace(":", "-")
    except Exception:
        pass

    # フォールバック (更新日時)
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


# ──────────────────────────────────────────────
# フォーマット・パースユーティリティ
# ──────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    """バイト数を人間が読みやすい文字列に変換する。

    Args:
        size_bytes: バイト数

    Returns:
        "xxx B" / "xxx KB" / "xxx MB" / "xxx GB" 形式の文字列
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def parse_exts(ext_str: str) -> list[str]:
    """カンマ区切りの拡張子文字列を正規化されたリストに変換する。

    ドットなし・大文字・前後スペースをすべて正規化する。例::

        parse_exts(".MP4, JPG")  # → ['.mp4', '.jpg']
        parse_exts("")           # → []

    Args:
        ext_str: カンマ区切りの拡張子文字列

    Returns:
        小文字・ドット付きに正規化された拡張子のリスト
    """
    result = []
    for token in ext_str.split(','):
        token = token.strip()
        if not token:
            continue
        if not token.startswith('.'):
            token = '.' + token
        result.append(token.lower())
    return result


# ──────────────────────────────────────────────
# 整理先パス生成
# ──────────────────────────────────────────────

def build_dest_path(
    file_path: Path,
    date: str,
    file_type: str,
    group_date: bool,
    date_format: str,
    split_type: bool,
    video_folder: str,
    photo_folder: str,
    misc_folder: str,
    group_ext: bool,
    folder_order: str,
) -> Path:
    """ファイル情報と整理設定から整理先の相対パスを生成する。

    Args:
        file_path:    元ファイルのパス（ファイル名取得に使用）
        date:         YYYY-MM-DD 形式の撮影日文字列
        file_type:    ファイル種別（"動画" / "写真" / "その他"）
        group_date:   日付ごとにフォルダ分けするか
        date_format:  日付フォルダ名の形式 ("YYYYMMDD" | "YYYY-MM-DD")
        split_type:   動画/写真を別フォルダにするか
        video_folder: 動画フォルダ名
        photo_folder: 写真フォルダ名
        misc_folder:  その他フォルダ名
        group_ext:    拡張子ごとにフォルダ分けするか
        folder_order: 階層順序文字列（例: "日付 > 種類 > 拡張子"）

    Returns:
        ファイル名を含む整理先の相対 Path オブジェクト
    """
    # 日付セグメントの生成
    d_seg = date
    if date_format == "YYYYMMDD":
        d_seg = d_seg.replace("-", "")

    date_seg = d_seg if group_date else None

    # 種類セグメントの生成
    type_seg = None
    if split_type:
        v_name = video_folder or "Videos"
        p_name = photo_folder or "Photos"
        m_name = misc_folder or "Misc"
        type_seg = (
            v_name if file_type == "動画" else
            p_name if file_type == "写真" else
            m_name
        )

    # 拡張子セグメントの生成
    ext_seg = file_path.suffix[1:].upper() if group_ext else None

    # 階層順序に従ってセグメントを結合
    order_parts = [p.strip() for p in folder_order.split(">")]
    segments: list[str] = []
    for part in order_parts:
        if part == "日付" and date_seg:
            segments.append(date_seg)
        elif part == "種類" and type_seg:
            segments.append(type_seg)
        elif part == "拡張子" and ext_seg:
            segments.append(ext_seg)

    if segments:
        return Path(*segments) / file_path.name
    else:
        return Path(file_path.name)
