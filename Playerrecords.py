import requests
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import islice

# Constants
SOLDIER_CLASS = "3"
DEMOMAN_CLASS = "4"
SOLDIER_CSV = "all_maps_soldier_info.csv"
DEMOMAN_CSV = "all_maps_demoman_info.csv"
OUTPUT_CSV = "player_map_records.csv"
FAILED_CSV = "failed_maps.csv"
API_URL_TEMPLATE = "https://tempus2.xyz/api/v0/maps/id/{map_id}/zones/typeindex/map/1/records/player/{player_id}/{class_id}"

USE_THREADS = True
MAX_THREADS = 10
BATCH_SIZE = 10
COOLDOWN_SECONDS = 10
MAX_RETRIES = 5
TIMEOUT_SECONDS = 15


def format_time(seconds):
    """Format time from seconds to HH:MM:SS:MMM."""
    if seconds is None:
        return ""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}:{millis:03}"


def get_user_input():
    """Get player ID and class choice from user."""
    while True:
        player_id = input("Enter player ID (integer): ").strip()
        if player_id.isdigit():
            break
        print("Invalid input. Please enter a valid integer player ID.")
    player_id = int(player_id)

    print("Choose class:\n1 - Soldier\n2 - Demoman")
    while True:
        class_choice = input("Enter 1 or 2: ").strip()
        if class_choice in ("1", "2"):
            break
        print("Invalid input. Please enter 1 or 2.")

    class_id = SOLDIER_CLASS if class_choice == "1" else DEMOMAN_CLASS
    csv_file = SOLDIER_CSV if class_choice == "1" else DEMOMAN_CSV
    class_name = "Soldier" if class_choice == "1" else "Demoman"

    return player_id, class_id, csv_file, class_name


def load_map_data(csv_path):
    """Load map data from the given CSV file."""
    full_path = os.path.join(os.getcwd(), csv_path)
    if not os.path.isfile(full_path):
        print(f"❌ CSV file not found: {full_path}")
        sys.exit(1)

    with open(full_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=';')
        return list(reader)


def fetch_player_record(map_entry, player_id, class_id):
    """Fetch player's record for a given map."""
    map_id = map_entry["map_id"]
    url = API_URL_TEMPLATE.format(map_id=map_id, player_id=player_id, class_id=class_id)

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=TIMEOUT_SECONDS)

            if resp.status_code == 404:
                return map_entry, None, None
            elif resp.status_code == 429:
                wait_time = 6 * (2 ** attempt)
                print(f"⏳ Rate limit hit on map {map_id}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            resp.raise_for_status()
            data = resp.json()
            result = data.get("result")
            if not result:
                return map_entry, None, None

            return map_entry, result.get("duration"), result.get("rank")

        except requests.exceptions.RequestException as e:
            wait_time = 2 * (2 ** attempt)
            print(f"⚠️ Error on map {map_id}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    print(f"❌ Failed after {MAX_RETRIES} retries for map {map_id}")
    return map_entry, None, None


def batched(iterable, n):
    """Yield batches of size `n` from iterable."""
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch


def write_csv(path, fieldnames, rows):
    """Write a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(rows)


def main():
    player_id, class_id, csv_file, class_name = get_user_input()
    print(f"\n📥 Loading map data from '{csv_file}'...")
    maps = load_map_data(csv_file)

    results = []
    failed_maps = []

    print(f"\n🎯 Fetching player records for ID {player_id} ({class_name})...\n")

    if USE_THREADS:
        for batch_num, batch in enumerate(batched(maps, BATCH_SIZE), 1):
            print(f"🚀 Processing batch {batch_num} ({len(batch)} maps)...")
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                futures = {executor.submit(fetch_player_record, m, player_id, class_id): m for m in batch}
                for i, future in enumerate(as_completed(futures), 1):
                    map_entry, time_val, rank_val = future.result()
                    formatted_time = format_time(time_val)

                    results.append({
                        "map_name": map_entry["map_name"],
                        "class": class_name,
                        "tier": map_entry["tier"],
                        "rating": map_entry["rating"],
                        "player_time_formatted": formatted_time,
                        "player_rank": rank_val if rank_val is not None else ""
                    })

                    if time_val is None and rank_val is None:
                        failed_maps.append(map_entry)

                    print(f"[Batch {batch_num}] {map_entry['map_name']} - Time: {formatted_time}, Rank: {rank_val}")

            print(f"⏸️ Cooling down for {COOLDOWN_SECONDS} seconds...\n")
            time.sleep(COOLDOWN_SECONDS)
    else:
        for i, map_entry in enumerate(maps, 1):
            _, time_val, rank_val = fetch_player_record(map_entry, player_id, class_id)
            formatted_time = format_time(time_val)

            results.append({
                "map_name": map_entry["map_name"],
                "class": class_name,
                "tier": map_entry["tier"],
                "rating": map_entry["rating"],
                "player_time_formatted": formatted_time,
                "player_rank": rank_val if rank_val is not None else ""
            })

            if time_val is None and rank_val is None:
                failed_maps.append(map_entry)

            print(f"[{i}/{len(maps)}] {map_entry['map_name']} - Time: {formatted_time}, Rank: {rank_val}")
            time.sleep(0.5)

    # Save results
    write_csv(OUTPUT_CSV,
              ["map_name", "class", "tier", "rating", "player_time_formatted", "player_rank"],
              results)

    if failed_maps:
        write_csv(FAILED_CSV,
                  ["map_id", "map_name", "tier", "rating"],
                  failed_maps)
        print(f"\n⚠️ {len(failed_maps)} maps failed after retries. Logged to: {FAILED_CSV}")
    else:
        print("\n✅ No failed maps!")

    print(f"\n📊 Summary:")
    print(f"✅ Successful maps: {len(results) - len(failed_maps)}")
    print(f"⚠️ Failed maps: {len(failed_maps)}")
    print(f"💾 Results saved to: {OUTPUT_CSV}")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
