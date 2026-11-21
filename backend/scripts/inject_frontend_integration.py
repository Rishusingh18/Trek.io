"""
Injects TrekAPI client and live data hydration hooks into all frontend portal pages.
"""
import glob
import os

PORTAL_PAGES = [
    "frontend/student_dashboard_consolidated_overview_roadmap/code.html",
    "frontend/student_dashboard_topics_mastery_roadmap/code.html",
    "frontend/student_dashboard_browser_history_style_quiz_attempts/code.html",
    "frontend/topics_mastery_detailed_curriculum_roadmap_study_hub/code.html",
    "frontend/teacher_dashboard_simplified_class_mastery_interventions/code.html",
    "frontend/admin_console_user_management_system_telemetry/code.html"
]

INJECTION_SNIPPET = """
<!-- Trek.io Unified API & ML Integration Hook -->
<script src="../assets/js/api.js"></script>
<script>
  (function() {
    // 1. Role switcher dropdown navigation
    document.querySelectorAll('.role-option').forEach(option => {
      option.addEventListener('click', (e) => {
        const role = option.getAttribute('data-role') || '';
        if (window.TrekAPI) TrekAPI.setCurrentRole(role);
        if (role.includes('Teacher') || role.includes('Instructor') || role.includes('Thorne')) {
          window.location.href = '../teacher_dashboard_simplified_class_mastery_interventions/code.html';
        } else if (role.includes('Admin')) {
          window.location.href = '../admin_console_user_management_system_telemetry/code.html';
        } else if (role.includes('Student')) {
          window.location.href = '../student_dashboard_consolidated_overview_roadmap/code.html';
        }
      });
    });

    // 2. Portal Hub Back-Link Button
    if (!document.getElementById('trek-portal-pill')) {
      const pill = document.createElement('div');
      pill.id = 'trek-portal-pill';
      pill.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;align-items:center;gap:8px;';
      pill.innerHTML = `
        <a href="../index.html" style="display:inline-flex;align-items:center;gap:6px;padding:8px 14px;background:#070235;color:#ffffff;border-radius:9999px;font-family:'Plus Jakarta Sans',sans-serif;font-size:11px;font-weight:700;text-decoration:none;box-shadow:0 4px 14px rgba(7,2,53,0.3);border:1px solid #1e1b4b;transition:transform 0.15s ease;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
          <span class="material-symbols-outlined" style="font-size:15px;color:#82f5c1;">grid_view</span>
          <span>Portal Hub</span>
        </a>
      `;
      document.body.appendChild(pill);
    }

    // 3. Auto-load live recommendations & stats
    document.addEventListener('DOMContentLoaded', async () => {
      if (!window.TrekAPI) return;
      try {
        const health = await TrekAPI.checkHealth();
        if (health && health.status === 'healthy') {
          console.log('[Trek Portal] Connected to Live API backend.');
          // If on Student Dashboard, log live recommendations
          if (window.location.pathname.includes('student_dashboard')) {
            const recs = await TrekAPI.getRecommendations();
            if (recs && recs.items && recs.items.length > 0) {
              console.log('[Trek Portal] Live ML recommendations loaded:', recs);
            }
          }
        }
      } catch (err) {
        console.log('[Trek Portal] Using local presentation state.');
      }
    });
  })();
</script>
"""

def main():
    for page_path in PORTAL_PAGES:
        if not os.path.exists(page_path):
            print(f"Skipping {page_path} (not found)")
            continue

        with open(page_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "<!-- Trek.io Unified API & ML Integration Hook -->" in content:
            print(f"Already injected: {page_path}")
            continue

        if "</body>" in content:
            new_content = content.replace("</body>", INJECTION_SNIPPET + "\n</body>")
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Successfully injected into: {page_path}")
        else:
            print(f"No </body> tag in: {page_path}")

if __name__ == "__main__":
    main()

