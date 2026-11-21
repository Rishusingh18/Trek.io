import os
import re

URL_TO_FILENAME = {
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDYW78FMppEUOqjaPpsZg_YC9O53ts4TpsztNzLQDCL5ns9xg-PfyTfhPAw19BBZXSFthSv2Xo6tZ4XvlQGDoeW7qd9nMfaj4DZ3YQX71k8T04d9JJJHIpO2PAXvg9MUXymatINMxbS7pcG_F6JqWRZoP4c7QqfVraOwAZ_sEKQ19c3BmOxvME4n5j4Wl-0Y1ZJ_wozyz7ZpTS5t0poYjnvyytSptr1r3l18mWFLMI2nPGKJA117yg": "logo.png",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuCWQx0OAXOVc7yQntjz8bEdI1HuPBJisZWaaqsLjR7M6yCE3Jcbiz20hrtlB7iKYnBAhiont1sO5uduCcmhoU2KPVCcRf_UbhIY9HT9-tpcl3jyvqDKXOBzH7mnKrP3pyLP1jwsNrs6Tjr-5uIanVOoVIHwMRrz8wmN8DvwWrorQ78gU1HLNyxOR_UHY6Yc6HaxHDIuMmaC1dl7rYCqrDBN1xDpzXDzsFkvHy_QfY1ekHv-b-_exms": "avatar_asha.png",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuA_zBllp4c0_TY803f62qX4RoZvkhTbpRmqXf_vyx5jEKuOAThpTtZzvZkCO8aC84aNRFXHbXHfIL33lmslCJZVcTacwpe-a91QUDCuWDy52DmcLwDAr8_8nio3CqLaaiO_zsLJo0SCOa6k_tnu3OoaDMT5OsF2Br0JfhaXa-ZQRfc7LS04-IU6oyppUpBozaG6T_pZn3HzDklOBG85N1XHukhPOG8a0xBjXLFAo6sSs0MeOE7yWcA": "avatar_instructor.png",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDCesAlbRDDHDfZv8rJg0BXP6eUb-tI7rZlzq9MV5yADqmSMmD9jkH3L2C5W2eX0sSXBwzRTTcl0nFiBw_Kf_BXkhjC6ULcSIYcFnRE7nrxP_r91Ikj1qEXWLFi32yPTldD7WiI7DAK3iGT2V2_PM950rWuZtYxPQ_jARJHEChBj9I7bs3vV2aTXUi1yJHbCFrjG_ULjXk9AejrUxjFmU0p950K3xgD048bBBGNVwvKWox5uwQh3HU": "avatar_marcus.png",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuBLrn4oVH-O-f8tqg83Udx2bfg4QVw0Vo6P5_QhgPmLggRTzykyKNR6XWDZE6KuYwcp08I-k3cmA13paMuivFI3TRqbSIOf8m2kPCUTtCyEyStbL-ZMgFvr-AVXOsQqIT-d9hlUvgQyRHO0Oj_SeaOhlbp_ECK166lUtssISGceFsaLXgQHG80T9GE0CehzSXig4oJ9YN-r8HwwwCNEUqbKNhs-oI-LS_NyaQmvRVCgp6gHzBFVUB0": "avatar_priya.png",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDqpX-KdVnt1soqEeKC6v-e5fjxQJOtHe5OhZ-TycWXcUeeVgkWtQFAhlSVhw6ZeZvSvtaRU1Gj9gY85iap6rK1bWdN_9kt7D6jXxf7PuqBmqukPNVOPd8s8uemzBEOBo5fVVEjz5M_2CQmEtT_L0sXoFXmLwzQGd9UbxWR_1GypdID76EAC2R0LyOCFnwEeqxvt8xPi9nebx4glpzqjacXWYw6ydlRuMmp46B3C4jyaO_JuoweJNw": "avatar_ethan.png",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuC-Am_JXES272SEQ7oa-kYmDtdSpeChRc5z5oWLJjR5xLX8NPS-Qskwz-oxwJ37WV4p47aC5ojEPOHbXfWk5TW_jouTCJvv7OEaLhRi5ii2Nmekqs79OCsxgfLdYLh6xNgcpMsR_xDSDWU6w3j7nqRG5uFb_zNrxw4Msk7OlJk4AneZ4VGkZ7h5uz8PlhfMI4F_2qv1iEASxKTSbVz_KInMIGjdXBQIxt5lk_7nr7LFu6STjPtftlg": "avatar_samantha.png",
    "https://lh3.googleusercontent.com/aida-public/AB6AXuC9xY0j0vDcqJaj2tS-DerPC9nk_qfFBjMRFfj2c8QNA4fUZPNK9Kv15mTSJu7FdirsaubaUW5xP0qJe9QHhJ961gn4bkH7TiJdvl5V3CQo-WNGJA_O-6-8lx2t8Cj47rRH8CFpV-JviPPXC4jO7oZ-s_NnzJ8Ja3vwpSZmc_6e0ZCtU10iTG5OWJ8jB8-gZ74473mscr2_5nrTL0OkdkmWa93Ko3yX04WLWVm5PPsl01ytqqWqvDc": "avatar_kofi.png",
}

FILES = [
    "frontend/student_dashboard_consolidated_overview_roadmap/code.html",
    "frontend/student_dashboard_topics_mastery_roadmap/code.html",
    "frontend/student_dashboard_browser_history_style_quiz_attempts/code.html",
    "frontend/topics_mastery_detailed_curriculum_roadmap_study_hub/code.html",
    "frontend/teacher_dashboard_simplified_class_mastery_interventions/code.html",
    "frontend/admin_console_user_management_system_telemetry/code.html",
    "frontend/index.html",
]

def update_files():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    for rel_path in FILES:
        abs_path = os.path.join(base_dir, rel_path.replace("/", os.sep))
        if not os.path.exists(abs_path):
            print(f"Skipping missing: {abs_path}")
            continue
            
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Determine prefix for assets
        # If file is frontend/index.html -> './assets/'
        # If file is frontend/<folder>/code.html -> '../assets/'
        rel_from_frontend = os.path.relpath(abs_path, os.path.join(base_dir, "frontend"))
        depth = len(rel_from_frontend.split(os.sep)) - 1
        prefix = ("../" * depth) + "assets/" if depth > 0 else "./assets/"
        
        css_replacement = f'<link rel="stylesheet" href="{prefix}css/tailwind.min.css">\n<script>window.tailwind = window.tailwind || {{}};</script>'
        
        # Replace Tailwind CDN
        new_content = re.sub(
            r'<script\s+src=["\']https://cdn\.tailwindcss\.com(\?[^"\']*)?["\']\s*></script>',
            css_replacement,
            content
        )
        
        # Replace images
        img_count = 0
        for hotlink_url, filename in URL_TO_FILENAME.items():
            local_url = f"{prefix}images/{filename}"
            if hotlink_url in new_content:
                count = new_content.count(hotlink_url)
                img_count += count
                new_content = new_content.replace(hotlink_url, local_url)
                
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Updated {rel_path}:")
        print(f"  Prefix: {prefix}")
        print(f"  Images replaced: {img_count}")
        print(f"  Tailwind CDN remaining: {'cdn.tailwindcss.com' in new_content}")
        print(f"  Hotlinked images remaining: {'lh3.googleusercontent.com' in new_content}")

if __name__ == "__main__":
    update_files()

