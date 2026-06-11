import urllib.request
import os

def download_adventureworks():
    # URL to the AdventureWorks SQLite database
    # Martin Andersen's port is widely used and reliable
    url = "https://raw.githubusercontent.com/martinandersen3d/AdventureWorks-for-SQLite/main/AdventureWorks-sqlite.db"
    output_path = "data/AdventureWorks.db"
    
    os.makedirs("data", exist_ok=True)
    
    if not os.path.exists(output_path):
        print(f"Downloading AdventureWorks DB from {url}...")
        try:
            urllib.request.urlretrieve(url, output_path)
            print("Download complete!")
        except Exception as e:
            print(f"Failed to download: {e}")
    else:
        print("AdventureWorks DB already exists.")

if __name__ == "__main__":
    download_adventureworks()
