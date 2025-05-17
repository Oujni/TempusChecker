import requests
import csv
import os
import sys
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import islice
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# === CONFIGURATION ===
SOLDIER_CLASS = "3"
DEMOMAN_CLASS = "4"
SOLDIER_CSV = "all_maps_soldier_info.csv"
DEMOMAN_CSV = "all_maps_demoman_info.csv"
OUTPUT_CSV = "player_map_records.csv"
FAILED_CSV = "failed_maps.csv"
LOG_FILE = "app.log"

API_URL_TEMPLATE = (
    "https://tempus2.xyz/api/v0/maps/id/{map_id}/zones/typeindex/map/1/records/player/{player_id}/{class_id}"
)

USE_THREADS = True
MAX_THREADS = 10
BATCH_SIZE = 10
COOLDOWN_SECONDS = 10
MAX_RETRIES = 5
TIMEOUT_SECONDS = 15

# === LOGGING ===
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === TIME FORMATTER ===
def format_time(seconds):
    if seconds is None:
        return ""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 100)

    if hours > 0:
        return f"{hours}:{minutes:02}:{secs:02}.{millis:02}"
    elif minutes > 0:
        return f"{minutes}:{secs:02}.{millis:02}"
    else:
        return f"{secs}.{millis:02}"

# === CORE LOGIC ===
def load_map_data(csv_path):
    full_path = os.path.join(os.getcwd(), csv_path)
    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"CSV not found: {full_path}")
    with open(full_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader)

def fetch_player_record(map_entry, player_id, class_id, log_fn):
    map_id = map_entry["map_id"]
    url = API_URL_TEMPLATE.format(map_id=map_id, player_id=player_id, class_id=class_id)

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=TIMEOUT_SECONDS)
            if resp.status_code == 404:
                return map_entry, None, None
            if resp.status_code == 429:
                wait_time = 6 * (2 ** attempt)
                log_fn(f"⏳ Rate limit on map {map_id}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            resp.raise_for_status()
            data = resp.json()
            result = data.get("result")
            if not result:
                return map_entry, None, None

            duration = result.get("duration")
            rank = result.get("rank")
            return map_entry, duration, rank

        except requests.exceptions.RequestException as e:
            wait_time = 2 * (2 ** attempt)
            log_fn(f"⚠️ Error on map {map_id}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    log_fn(f"❌ Failed after {MAX_RETRIES} retries for map {map_id}")
    return map_entry, None, None

def batched(iterable, n):
    it = iter(iterable)
    while batch := list(islice(it, n)):
        yield batch

# === GUI APP ===
class TempusApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tempus Player Map Records")
        self.geometry("700x500")
        self.configure(padx=20, pady=20)

        self.stop_requested = False
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="Player ID:").grid(row=0, column=0, sticky="w")
        self.player_id_entry = tk.Entry(self, width=30)
        self.player_id_entry.grid(row=0, column=1, sticky="w")

        tk.Label(self, text="Class:").grid(row=1, column=0, sticky="w")
        self.class_choice = ttk.Combobox(self, values=["Soldier", "Demoman"], state="readonly")
        self.class_choice.current(0)
        self.class_choice.grid(row=1, column=1, sticky="w")

        self.start_button = ttk.Button(self, text="Start", command=self.start_process)
        self.start_button.grid(row=2, column=0, pady=10)

        self.stop_button = ttk.Button(self, text="Stop", command=self.request_stop, state="disabled")
        self.stop_button.grid(row=2, column=1, pady=10)

        self.progress = ttk.Progressbar(self, length=500)
        self.progress.grid(row=3, column=0, columnspan=2, pady=10)

        self.log_text = tk.Text(self, height=18, wrap="word")
        self.log_text.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=10)

        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(1, weight=1)

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)
        logging.info(message)

    def request_stop(self):
        self.stop_requested = True
        self.log("⏹️ Stop requested. Finishing current tasks...")

    def start_process(self):
        player_id = self.player_id_entry.get().strip()
        if not player_id.isdigit():
            messagebox.showerror("Input Error", "Player ID must be an integer.")
            return

        self.stop_requested = False
        self.start_button.config(state="disabled")
        self.stop_button.config(state="enabled")

        class_id = SOLDIER_CLASS if self.class_choice.get() == "Soldier" else DEMOMAN_CLASS
        class_name = self.class_choice.get()
        csv_file = SOLDIER_CSV if class_name == "Soldier" else DEMOMAN_CSV

        thread = threading.Thread(
            target=self.run_tempus_fetch,
            args=(int(player_id), class_id, csv_file, class_name),
            daemon=True
        )
        thread.start()

    def run_tempus_fetch(self, player_id, class_id, csv_file, class_name):
        try:
            self.log(f"📥 Loading maps from {csv_file}...")
            maps = load_map_data(csv_file)
            total_maps = len(maps)
            self.progress["maximum"] = total_maps
            self.progress["value"] = 0
        except Exception as e:
            self.log(f"❌ Error loading CSV: {e}")
            self.start_button.config(state="enabled")
            self.stop_button.config(state="disabled")
            return

        results = []
        failed_maps = []

        self.log(f"🚀 Fetching records for Player {player_id} as {class_name}...")

        if USE_THREADS:
            for batch_num, batch in enumerate(batched(maps, BATCH_SIZE), 1):
                if self.stop_requested:
                    self.log("⏹️ Process stopped by user.")
                    break
                self.log(f"⚙️ Processing batch {batch_num} with {len(batch)} maps...")
                with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                    futures = {executor.submit(fetch_player_record, m, player_id, class_id, self.log): m for m in batch}
                    for future in as_completed(futures):
                        if self.stop_requested:
                            self.log("⏹️ Process stopped by user.")
                            break
                        map_entry, time_val, rank_val = future.result()
                        formatted_time = format_time(time_val)

                        self.log(f"▶️ Processing map: {map_entry['map_name']}")

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

                        self.progress["value"] += 1
                        self.update_idletasks()

                if self.stop_requested:
                    break
                time.sleep(COOLDOWN_SECONDS)
        else:
            for i, map_entry in enumerate(maps, 1):
                if self.stop_requested:
                    self.log("⏹️ Process stopped by user.")
                    break
                _, time_val, rank_val = fetch_player_record(map_entry, player_id, class_id, self.log)
                formatted_time = format_time(time_val)

                self.log(f"▶️ Processing map: {map_entry['map_name']}")

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

                self.progress["value"] += 1
                self.update_idletasks()

        if results:
            with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["map_name", "class", "tier", "rating", "player_time_formatted", "player_rank"], delimiter=";")
                writer.writeheader()
                writer.writerows(results)

        if failed_maps:
            with open(FAILED_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["map_id", "map_name", "tier", "rating"], delimiter=";")
                writer.writeheader()
                writer.writerows(failed_maps)
            self.log(f"⚠️ {len(failed_maps)} maps failed. Saved to {FAILED_CSV}")
        else:
            self.log("✅ No failed maps!")

        self.log(f"✅ Process finished! Results saved to {OUTPUT_CSV}")

        self.start_button.config(state="enabled")
        self.stop_button.config(state="disabled")


# === RUN APP ===
if __name__ == "__main__":
    app = TempusApp()
    app.mainloop()
