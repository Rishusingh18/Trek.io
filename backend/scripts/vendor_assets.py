"""
Vendors external assets for Trek.io frontend:
1. Downloads logo and avatar images to frontend/assets/images/
2. Downloads / generates prebuilt Tailwind CSS to frontend/assets/css/tailwind.min.css
"""
import os
import sys
import urllib.request
import ssl
import tempfile
import shutil

# Retain default SSL context with certificate and hostname verification
ctx = ssl.create_default_context()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

IMAGES = {
    "logo.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuDYW78FMppEUOqjaPpsZg_YC9O53ts4TpsztNzLQDCL5ns9xg-PfyTfhPAw19BBZXSFthSv2Xo6tZ4XvlQGDoeW7qd9nMfaj4DZ3YQX71k8T04d9JJJHIpO2PAXvg9MUXymatINMxbS7pcG_F6JqWRZoP4c7QqfVraOwAZ_sEKQ19c3BmOxvME4n5j4Wl-0Y1ZJ_wozyz7ZpTS5t0poYjnvyytSptr1r3l18mWFLMI2nPGKJA117yg",
    "avatar_asha.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuCWQx0OAXOVc7yQntjz8bEdI1HuPBJisZWaaqsLjR7M6yCE3Jcbiz20hrtlB7iKYnBAhiont1sO5uduCcmhoU2KPVCcRf_UbhIY9HT9-tpcl3jyvqDKXOBzH7mnKrP3pyLP1jwsNrs6Tjr-5uIanVOoVIHwMRrz8wmN8DvwWrorQ78gU1HLNyxOR_UHY6Yc6HaxHDIuMmaC1dl7rYCqrDBN1xDpzXDzsFkvHy_QfY1ekHv-b-_exms",
    "avatar_instructor.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuA_zBllp4c0_TY803f62qX4RoZvkhTbpRmqXf_vyx5jEKuOAThpTtZzvZkCO8aC84aNRFXHbXHfIL33lmslCJZVcTacwpe-a91QUDCuWDy52DmcLwDAr8_8nio3CqLaaiO_zsLJo0SCOa6k_tnu3OoaDMT5OsF2Br0JfhaXa-ZQRfc7LS04-IU6oyppUpBozaG6T_pZn3HzDklOBG85N1XHukhPOG8a0xBjXLFAo6sSs0MeOE7yWcA",
    "avatar_marcus.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuDCesAlbRDDHDfZv8rJg0BXP6eUb-tI7rZlzq9MV5yADqmSMmD9jkH3L2C5W2eX0sSXBwzRTTcl0nFiBw_Kf_BXkhjC6ULcSIYcFnRE7nrxP_r91Ikj1qEXWLFi32yPTldD7WiI7DAK3iGT2V2_PM950rWuZtYxPQ_jARJHEChBj9I7bs3vV2aTXUi1yJHbCFrjG_ULjXk9AejrUxjFmU0p950K3xgD048bBBGNVwvKWox5uwQh3HU",
    "avatar_priya.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuBLrn4oVH-O-f8tqg83Udx2bfg4QVw0Vo6P5_QhgPmLggRTzykyKNR6XWDZE6KuYwcp08I-k3cmA13paMuivFI3TRqbSIOf8m2kPCUTtCyEyStbL-ZMgFvr-AVXOsQqIT-d9hlUvgQyRHO0Oj_SeaOhlbp_ECK166lUtssISGceFsaLXgQHG80T9GE0CehzSXig4oJ9YN-r8HwwwCNEUqbKNhs-oI-LS_NyaQmvRVCgp6gHzBFVUB0",
    "avatar_ethan.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuDqpX-KdVnt1soqEeKC6v-e5fjxQJOtHe5OhZ-TycWXcUeeVgkWtQFAhlSVhw6ZeZvSvtaRU1Gj9gY85iap6rK1bWdN_9kt7D6jXxf7PuqBmqukPNVOPd8s8uemzBEOBo5fVVEjz5M_2CQmEtT_L0sXoFXmLwzQGd9UbxWR_1GypdID76EAC2R0LyOCFnwEeqxvt8xPi9nebx4glpzqjacXWYw6ydlRuMmp46B3C4jyaO_JuoweJNw",
    "avatar_samantha.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuC-Am_JXES272SEQ7oa-kYmDtdSpeChRc5z5oWLJjR5xLX8NPS-Qskwz-oxwJ37WV4p47aC5ojEPOHbXfWk5TW_jouTCJvv7OEaLhRi5ii2Nmekqs79OCsxgfLdYLh6xNgcpMsR_xDSDWU6w3j7nqRG5uFb_zNrxw4Msk7OlJk4AneZ4VGkZ7h5uz8PlhfMI4F_2qv1iEASxKTSbVz_KInMIGjdXBQIxt5lk_7nr7LFu6STjPtftlg",
    "avatar_kofi.png": "https://lh3.googleusercontent.com/aida-public/AB6AXuC9xY0j0vDcqJaj2tS-DerPC9nk_qfFBjMRFfj2c8QNA4fUZPNK9Kv15mTSJu7FdirsaubaUW5xP0qJe9QHhJ961gn4bkH7TiJdvl5V3CQo-WNGJA_O-6-8lx2t8Cj47rRH8CFpV-JviPPXC4jO7oZ-s_NnzJ8Ja3vwpSZmc_6e0ZCtU10iTG5OWJ8jB8-gZ74473mscr2_5nrTL0OkdkmWa93Ko3yX04WLWVm5PPsl01ytqqWqvDc"
}

def is_decodable_image(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False

def download_file(url, out_path):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        data = resp.read()
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"Downloaded: {os.path.basename(out_path)} ({len(data)} bytes)")

def main():
    img_dir = os.path.abspath("frontend/assets/images")
    css_dir = os.path.abspath("frontend/assets/css")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(css_dir, exist_ok=True)

    print("--- 1. Downloading Images ---")
    for filename, url in IMAGES.items():
        dest = os.path.join(img_dir, filename)
        temp_dest = None
        try:
            fd, temp_dest = tempfile.mkstemp(suffix=os.path.splitext(filename)[1], dir=img_dir)
            os.close(fd)
            download_file(url, temp_dest)
            if is_decodable_image(temp_dest):
                shutil.move(temp_dest, dest)
                temp_dest = None
            else:
                raise ValueError(f"Downloaded content for {filename} is not a decodable image.")
        except Exception as e:
            if is_decodable_image(dest):
                print(f"Download failed for {filename} ({e}), but usable existing image found. Preserving.")
            else:
                print(f"Failed to download {filename} and no usable existing image found: {e}")
                raise RuntimeError(f"Missing required image asset {filename}: {e}")
        finally:
            if temp_dest and os.path.exists(temp_dest):
                try:
                    os.remove(temp_dest)
                except Exception:
                    pass

    print("\n--- 2. Downloading Prebuilt Tailwind CSS ---")
    tw_dest = os.path.join(css_dir, "tailwind.min.css")
    tw_urls = [
        "https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css",
        "https://unpkg.com/tailwindcss@2.2.19/dist/tailwind.min.css"
    ]
    def is_valid_stylesheet(path: str) -> bool:
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            return False
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(4096)
                if "<!DOCTYPE" in content.upper() or "<HTML" in content.upper():
                    return False
                if "{" not in content or "}" not in content:
                    return False
            return True
        except Exception:
            return False

    download_success = False
    for url in tw_urls:
        temp_dest = None
        try:
            fd, temp_dest = tempfile.mkstemp(suffix=".css", dir=css_dir)
            os.close(fd)
            download_file(url, temp_dest)
            if is_valid_stylesheet(temp_dest):
                shutil.move(temp_dest, tw_dest)
                try:
                    os.chmod(tw_dest, 0o644)
                except Exception:
                    pass
                temp_dest = None
                download_success = True
                break
            else:
                print(f"Downloaded content from {url} is not a valid stylesheet.")
        except Exception as e:
            print(f"Failed {url}: {e}")
        finally:
            if temp_dest and os.path.exists(temp_dest):
                try:
                    os.remove(temp_dest)
                except Exception:
                    pass

    # Track whether either CDN download or existing local stylesheet provides a usable stylesheet
    has_usable_stylesheet = download_success or is_valid_stylesheet(tw_dest)
    if not has_usable_stylesheet:
        print("ERROR: Neither CDN download nor existing local stylesheet provides a usable stylesheet.")
        sys.exit(1)

    # Regenerate Academic Precision theme utilities using append_theme_css process
    script_dir = os.path.dirname(__file__)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    import append_theme_css
    append_theme_css.main()

    # Ensure required custom project arbitrary utilities are included in local prebuilt stylesheet
    custom_utilities = """
/* Project Custom Utilities */
.h-\\[750px\\] { height: 750px; }
.h-\\[98px\\] { height: 98px; }
.max-w-\\[100px\\] { max-width: 100px; }
.min-h-\\[650px\\] { min-height: 650px; }
.min-w-\\[130px\\] { min-width: 130px; }
.min-w-\\[140px\\] { min-width: 140px; }
.min-w-\\[700px\\] { min-width: 700px; }
.min-w-\\[860px\\] { min-width: 860px; }
.min-w-\\[880px\\] { min-width: 880px; }
.rounded-\\[2px\\] { border-radius: 2px; }
.rounded-\\[3px\\] { border-radius: 3px; }
.w-\\[82\\%\\] { width: 82%; }
.text-\\[8px\\] { font-size: 8px; }
.text-\\[10px\\] { font-size: 10px; }
.text-\\[11px\\] { font-size: 11px; }
.text-\\[12px\\] { font-size: 12px; }
.text-\\[13px\\] { font-size: 13px; }
.text-\\[14px\\] { font-size: 14px; }
.text-\\[15px\\] { font-size: 15px; }
.text-\\[16px\\] { font-size: 16px; }
.text-\\[18px\\] { font-size: 18px; }
.text-\\[20px\\] { font-size: 20px; }
.text-\\[22px\\] { font-size: 22px; }
.text-\\[24px\\] { font-size: 24px; }
.text-\\[26px\\] { font-size: 26px; }
.after\\:content-\\[\\'\\'\\]::after { content: ''; }
.after\\:left-\\[2px\\]::after { left: 2px; }
.after\\:top-\\[2px\\]::after { top: 2px; }
.bg-\\[\\#c4c1fb\\] { background-color: #c4c1fb; }
.bg-\\[\\#cf7100\\] { background-color: #cf7100; }
.bg-\\[\\#ffdcc3\\] { background-color: #ffdcc3; }
.text-\\[\\#82f5c1\\] { color: #82f5c1; }
.text-\\[\\#cf7100\\] { color: #cf7100; }
"""
    if os.path.exists(tw_dest):
        with open(tw_dest, "r", encoding="utf-8") as f:
            content = f.read()
        missing_utilities = []
        for line in custom_utilities.strip().splitlines():
            if line.startswith(".") and "{" in line:
                selector = line.split("{")[0].strip()
                if selector not in content:
                    missing_utilities.append(line)
        if missing_utilities:
            with open(tw_dest, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(missing_utilities) + "\n")
            print(f"Appended {len(missing_utilities)} missing custom utilities to tailwind.min.css.")
        try:
            os.chmod(tw_dest, 0o644)
        except Exception:
            pass

if __name__ == "__main__":
    main()

