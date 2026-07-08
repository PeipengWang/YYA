import os
from typing import List, Dict

SUPPORT_FORMAT = (".mp3", ".wav", ".flac", ".m4a")


def scan_music_dir(folder: str) -> List[Dict]:
    music_list = []
    if not os.path.exists(folder):
        return music_list
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(SUPPORT_FORMAT):
                full_path = os.path.abspath(os.path.join(root, file))
                music_list.append({
                    "name": file,
                    "path": full_path
                })
    return music_list