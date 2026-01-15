import os

BASE_DIR = "/home/zeteny/Zenék"
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
