import requests
import csv
import os
import sys

# === CONFIG ===
CSV_FILENAME = "all_maps_soldier_info.csv"
MAP_LIST_URL = "https://tempus2.xyz/api/v0/maps/detailedList"
SOLDIER_CLASS_KEY = "3"
SAVE_PATH = os.getcwd()  # Save in the folder where the script is run

# === FUNCTIONS ===

def fetch_map_data():
    try:
        print("📡 Fetching data from Tempus API...")
        response = requests.get(MAP_LIST_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching map data: {e}")
        sys.exit(1)

def extract_soldier_data(map_data):
    return {
        "map_name": map_data.get("name", "unknown"),
        "map_id": map_data.get("id", -1),
        "tier": map_data.get("tier_info", {}).get(SOLDIER_CLASS_KEY),
        "rating": map_data.get("rating_info", {}).get(SOLDIER_CLASS_KEY),
    }

def save_to_csv(data, path, filename):
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, filename)

    with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=["map_name", "map_id", "tier", "rating"],
            delimiter=';'
        )
        writer.writeheader()
        writer.writerows(data)

    print(f"✅ Saved {len(data)} maps to: {file_path}")

# === MAIN ===

def main():
    maps = fetch_map_data()

    if not isinstance(maps, list):
        print("❌ Unexpected data format received from API.")
        sys.exit(1)

    soldier_map_data = [extract_soldier_data(m) for m in maps]
    print(f"✅ Extracted data for {len(soldier_map_data)} maps.")

    save_to_csv(soldier_map_data, SAVE_PATH, CSV_FILENAME)

if __name__ == "__main__":
    main()
