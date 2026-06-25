"""Poll the live feed locally; production uses the scheduled GitHub workflow."""

import os
import time

from sync_live_data import refresh_files, sync_database


INTERVAL_SECONDS = int(os.getenv("LIVE_SYNC_INTERVAL_SECONDS", "60"))


if __name__ == "__main__":
    print(f"Watching live scores every {INTERVAL_SECONDS} seconds. Press Ctrl+C to stop.")
    try:
        while True:
            started = time.monotonic()
            try:
                refresh_files()
                sync_database()
            except Exception as error:
                print(f"Live sync failed: {error}")
            elapsed = time.monotonic() - started
            time.sleep(max(1, INTERVAL_SECONDS - elapsed))
    except KeyboardInterrupt:
        print("Live score watcher stopped")
