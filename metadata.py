import os
import re
import sys
import json
import inquirer
import requests
from mutagen.id3 import ID3, TPE1, TIT2, TALB, TDRC, APIC
from mutagen.mp3 import MP3
import musicbrainzngs

# --- Szélességi Konstansok a Konzolos Menühöz ---
MAX_ARTIST_WIDTH = 30
MAX_TITLE_WIDTH = 40
MAX_ALBUM_WIDTH = 30
YEAR_WIDTH = 4

# --- MusicBrainz konfiguráció és User-Agent beállítás ---
USER_AGENT_STRING = "MP3_Metadata_Interactive_Updater/1.4 (email@example.com)"
musicbrainzngs.set_useragent(
    "MP3_Metadata_Interactive_Updater",
    "1.4",
    "email@example.com" # Kérlek, cseréld le a saját címedre!
)

# --- Segédfüggvények ---

def extract_title_from_filename(filename):
    """Kinyeri a szám címét a fájlnévből."""
    name_without_ext = os.path.splitext(filename)[0]
    cleaned_name = re.sub(r'^\s*\d{1,3}\s*[\.\-]\s*', '', name_without_ext).strip()

    if ' - ' in cleaned_name:
        return cleaned_name.split(' - ', 1)[1].strip()
    return cleaned_name

def search_tracks_by_title(title):
    """
    Keresést végez a MusicBrainz adatbázisban cím alapján.
    Mentjük a 'release_id'-t is a borítókép kereséséhez.
    """
    try:
        result = musicbrainzngs.search_recordings(query=title, limit=10)

        tracks = []
        for recording in result.get('recording-list', []):
            track_info = {
                'title': recording.get('title'),
                'artist': recording.get('artist-credit-phrase'),
                'album': 'Nincs Album Információ',
                'year': None,
                'release_id': None,
                'id': recording.get('id')
            }
            if 'release-list' in recording and recording['release-list']:
                release = recording['release-list'][0]
                track_info['album'] = release.get('title', track_info['album'])
                track_info['release_id'] = release.get('id')
                if 'date' in release:
                    match = re.match(r'(\d{4})', release['date'])
                    if match:
                        track_info['year'] = match.group(1)
            tracks.append(track_info)
        return tracks

    except musicbrainzngs.MusicBrainzError as e:
        print(f"Hiba történt a MusicBrainz API hívásakor: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Váratlan hiba a keresés során: {e}", file=sys.stderr)
        return []

def get_cover_art_data(release_id):
    """Letölti az első borítóképet a Cover Art Archive-ból a Release ID alapján."""
    if not release_id:
        return None, None

    caa_url = f"http://coverartarchive.org/release/{release_id}/front"

    try:
        headers = {'User-Agent': USER_AGENT_STRING}
        response = requests.get(caa_url, headers=headers, allow_redirects=True, timeout=10)

        if response.status_code == 200:
            mime_type = response.headers.get('Content-Type')
            if mime_type and 'image' in mime_type:
                return response.content, mime_type

        if response.status_code == 404:
            return None, None

        print(f"Sikertelen borítókép letöltés. HTTP Status: {response.status_code}")
        return None, None

    except requests.exceptions.RequestException as e:
        print(f"Hiba a borítókép letöltésekor: {e}")
        return None, None

def get_inquirer_selection(tracks):
    """
    Megjeleníti a lehetséges találatokat Inquirer menüben, oszlopos formázással.
    """
    choices = []

    # Oszlopfecet/Header hozzáadása
    header_artist = "ELŐADÓ".ljust(MAX_ARTIST_WIDTH)
    header_title = "CÍM".ljust(MAX_TITLE_WIDTH)
    header_album = "ALBUM".ljust(MAX_ALBUM_WIDTH)
    header_year = "ÉV".ljust(YEAR_WIDTH)

    header_label = f"| {header_artist} | {header_title} | {header_album} | {header_year} |"

    print("\n--- Több találat érkezett! Válassz a listából: ---")
    print(header_label)
    print("-" * len(header_label))

    # 1. Előkészítjük a menü opcióit
    for track in tracks:
        artist = track['artist'] if track['artist'] else 'Ismeretlen'
        title = track['title'] if track['title'] else 'Ismeretlen Cím'
        album = track['album'] if track['album'] else 'Nincs Album'
        year = track['year'] if track['year'] else '----'

        # RÖVIDÍTÉS és KITÖLTÉS (Padding)
        artist_display = (artist[:MAX_ARTIST_WIDTH-3] + '...') if len(artist) > MAX_ARTIST_WIDTH else artist
        title_display = (title[:MAX_TITLE_WIDTH-3] + '...') if len(title) > MAX_TITLE_WIDTH else title
        album_display = (album[:MAX_ALBUM_WIDTH-3] + '...') if len(album) > MAX_ALBUM_WIDTH else album

        artist_padded = artist_display.ljust(MAX_ARTIST_WIDTH)
        title_padded = title_display.ljust(MAX_TITLE_WIDTH)
        album_padded = album_display.ljust(MAX_ALBUM_WIDTH)
        year_padded = year.ljust(YEAR_WIDTH)

        label = f"| {artist_padded} | {title_padded} | {album_padded} | {year_padded} |"

        choices.append((label, track))

    # Hozzáadjuk a kihagyás opciót
    choices.append(('Kihagyás (nem ír be semmit)', None))

    # 2. Létrehozzuk az Inquirer listát
    questions = [
        inquirer.List(
            'selection',
            message="Kérlek, válaszd ki a megfelelő zeneszámot",
            choices=choices,
        )
    ]

    # 3. Futtatjuk a menüt
    try:
        answers = inquirer.prompt(questions)

        if answers and 'selection' in answers:
            return answers['selection']

        return None

    except KeyboardInterrupt:
        print("\nMegszakítás a felhasználó által.")
        return None
    except Exception as e:
        print(f"Hiba az Inquirer menü futtatásakor: {e}", file=sys.stderr)
        return None


def update_mp3_metadata(filepath, auto_mode=False):
    """
    Frissíti egy adott MP3 fájl ID3 tagjeit, beleértve a borítóképet is.
    """
    filename = os.path.basename(filepath)
    print(f"\n--- Fájl feldolgozása: {filename} ---")

    title_guess = extract_title_from_filename(filename)

    if not title_guess:
        print(f"Nem sikerült kinyerni a címet a fájlnévből. Keresés kihagyva.")
        return

    print(f"Online keresés indítása a címre: '{title_guess}'")

    track_data_list = search_tracks_by_title(title_guess)

    if not track_data_list:
        print("Nincs találat a MusicBrainz adatbázisban.")
        return

    selected_track = None
    if len(track_data_list) == 1:
        selected_track = track_data_list[0]
        print(f"Egyetlen találat: {selected_track['artist']} - {selected_track['title']}, automatikus kiválasztás.")
    elif auto_mode and track_data_list:
        selected_track = track_data_list[0]
        print(f"Automatikus mód: Első találat kiválasztva: {selected_track['artist']} - {selected_track['title']}")
    else:
        selected_track = get_inquirer_selection(track_data_list)

    if not selected_track:
        print("A fájl frissítése kihagyva.")
        return

    # 4. Tag-ek frissítése
    try:
        audio = MP3(filepath, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()

        artist_text = selected_track['artist'] if selected_track['artist'] else 'Ismeretlen'
        album_text = selected_track['album'] if selected_track['album'] else 'Ismeretlen Album'

        # Text Tag-ek beírása
        audio.tags.add(TPE1(encoding=3, text=[artist_text]))
        audio.tags.add(TIT2(encoding=3, text=[selected_track['title']]))
        audio.tags.add(TALB(encoding=3, text=[album_text]))

        if selected_track['year']:
            audio.tags.add(TDRC(encoding=3, text=[selected_track['year']]))

        # --- Borítókép (APIC) beírása ---
        if selected_track['release_id']:
            print("Keresés a borítóképre...")
            image_data, mime_type = get_cover_art_data(selected_track['release_id'])

            if image_data and mime_type:
                # Eltávolítjuk a régi borítóképet, ha van
                if 'APIC:' in audio.tags:
                    # Kikeressük az összes APIC tag-et és töröljük.
                    apic_keys = [k for k in audio.tags.keys() if k.startswith('APIC:')]
                    for key in apic_keys:
                        del audio.tags[key]

                audio.tags.add(
                    APIC(
                        encoding=3,       # UTF-8
                        mime=mime_type,   # Kép típusa (pl. 'image/jpeg')
                        type=3,           # 3 = Elülső borító (Front Cover)
                        desc='Cover',
                        data=image_data   # A kép bináris adata
                    )
                )
                print("Borítókép sikeresen beágyazva.")
            else:
                print("Borítókép nem található vagy beágyazása sikertelen.")


        # Mentés
        audio.save()
        print(f"A metadata sikeresen frissítve: {artist_text} - {selected_track['title']}.")

    except Exception as e:
        print(f"Hiba történt a tag-ek beírása közben: {e}")

def main():
    """A fő funkció."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    target_dir = script_dir
    auto_mode = "--auto" in sys.argv

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                target_dir = config.get("path", script_dir)
        except Exception as e:
            print(f"Hiba a config.json olvasásakor: {e}")

    print(f"Keresés indítása a mappában: {target_dir}")

    if not os.path.exists(target_dir):
        print(f"A megadott mappa nem létezik: {target_dir}")
        return

    mp3_files = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.lower().endswith('.mp3'):
                mp3_files.append(os.path.join(root, f))

    if not mp3_files:
        print("Nincs MP3 fájl a megadott mappában.")
        return

    for filepath in mp3_files:
        update_mp3_metadata(filepath, auto_mode=auto_mode)

    print("\n--- A munka befejeződött! ---")

if __name__ == "__main__":
    main()