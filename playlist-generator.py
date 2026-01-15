import os
import json

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "config.json")
BASE_DIR = ""

if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        BASE_DIR = config.get("path", "")

if not BASE_DIR or not os.path.exists(BASE_DIR):
    print("Hiba: Nem található érvényes útvonal a config.json-ban vagy a mappa nem létezik.")
    exit(1)

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac"}

for folder in os.listdir(BASE_DIR):
    folder_path = os.path.join(BASE_DIR, folder)

    if not os.path.isdir(folder_path):
        continue

    audio_files = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, BASE_DIR)
                audio_files.append(rel_path)

    if not audio_files:
        continue

    audio_files.sort()

    playlist_path = os.path.join(BASE_DIR, f"{folder}.m3u8")

    with open(playlist_path, "w", encoding="utf-8") as playlist:
        playlist.write("#EXTM3U\n")
        for track in audio_files:
            playlist.write(track + "\n")

    print(f"Készült: {playlist_path}")
