/**
 * Trek.io API Client
 * Seamlessly connects the Stitch frontend to the FastAPI + ML Recommender backend.
 */
(function(window) {
  // Use same-origin /v1 and /health when served by the backend, or explicitly configured backend origin
  // When running standalone frontend on port 3000, fallback to http://localhost:8000
  const isFileOrigin = typeof window !== 'undefined' && window.location.protocol === 'file:';
  const isPort3000 = typeof window !== 'undefined' && window.location.port === '3000';
  const configuredOrigin = (typeof window !== 'undefined' && window.TREK_BACKEND_URL) || ((isFileOrigin || isPort3000) ? 'http://localhost:8000' : '');
  const API_BASE = configuredOrigin ? `${configuredOrigin}/v1` : '/v1';
  const HEALTH_URL = configuredOrigin ? `${configuredOrigin}/health` : '/health';

  const DEMO_CREDENTIALS = {
    'Student': { email: 'asha@campus.edu', password: 'password123', name: 'Asha Sharma', role: 'learner' },
    'Teacher / Dr. Thorne': { email: 'profr@campus.edu', password: 'password123', name: 'Prof. Rao / Dr. Thorne', role: 'instructor' },
    'Instructor': { email: 'profr@campus.edu', password: 'password123', name: 'Prof. Rao', role: 'instructor' },
    'Admin': { name: 'System Administrator', role: 'administrator' } // Administrator credentials managed server-side
  };

  const TrekAPI = {
    API_BASE: API_BASE,
    HEALTH_URL: HEALTH_URL,

    _normalizeRoleKey: function(role) {
      if (!role) return 'learner';
      const r = role.toLowerCase();
      if (r.includes('teacher') || r.includes('instructor') || r.includes('thorne')) return 'instructor';
      if (r.includes('admin')) return 'admin';
      return 'learner';
    },

    getToken: function(role = null) {
      if (role) {
        const key = `trek_access_token_${this._normalizeRoleKey(role)}`;
        const roleToken = localStorage.getItem(key);
        if (roleToken) return roleToken;

        // Verify legacy token belongs to requested role before returning it
        const legacyToken = localStorage.getItem('trek_access_token');
        if (legacyToken) {
          try {
            const parts = legacyToken.split('.');
            if (parts.length === 3) {
              const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
              if (payload && payload.role && this._normalizeRoleKey(payload.role) === this._normalizeRoleKey(role)) {
                return legacyToken;
              }
            }
          } catch (e) {}
        }
        return null;
      }
      return localStorage.getItem('trek_access_token');
    },

    setToken: function(token, role = null) {
      const key = role ? `trek_access_token_${this._normalizeRoleKey(role)}` : null;
      if (token) {
        localStorage.setItem('trek_access_token', token);
        if (key) localStorage.setItem(key, token);
      } else {
        localStorage.removeItem('trek_access_token');
        if (key) localStorage.removeItem(key);
      }
    },

    getCurrentRole: function() {
      return localStorage.getItem('trek_current_role') || 'Student';
    },

    setCurrentRole: function(role) {
      localStorage.setItem('trek_current_role', role);
    },

    getAuthHeaders: function(role = null) {
      const headers = { 'Content-Type': 'application/json' };
      const token = this.getToken(role);
      if (token) {
        headers['Authorization'] = 'Bearer ' + token;
      }
      return headers;
    },

    checkHealth: async function() {
      try {
        const resp = await fetch(HEALTH_URL, { method: 'GET' });
        if (resp.ok) {
          return await resp.json();
        }
        return { status: 'degraded' };
      } catch (err) {
        return { status: 'offline', error: err.message };
      }
    },

    login: async function(email, password, role = null) {
      try {
        const resp = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email, password: password })
        });
        if (!resp.ok) {
          throw new Error(`Login failed with status ${resp.status}`);
        }
        const data = await resp.json();
        this.setToken(data.access_token, role);
        return data;
      } catch (err) {
        console.warn('[TrekAPI] Direct login failed; operating in resilient fallback mode.', err);
        return null;
      }
    },

    isTokenExpired: function(token) {
      if (!token) return true;
      try {
        const parts = token.split('.');
        if (parts.length !== 3) return false;
        const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
        if (payload && payload.exp) {
          const now = Math.floor(Date.now() / 1000);
          return now >= payload.exp;
        }
      } catch (e) {
        return true;
      }
      return false;
    },

    ensureAuthenticated: async function(roleName = null) {
      const targetRole = roleName || this.getCurrentRole();
      const roleKey = this._normalizeRoleKey(targetRole);
      const token = this.getToken(roleKey);
      const creds = DEMO_CREDENTIALS[targetRole] || DEMO_CREDENTIALS['Student'];

      // Preserve existing token if already authenticated for the requested role and not expired
      if (token && !this.isTokenExpired(token)) {
        return creds;
      }

      if (creds.email && creds.password) {
        const result = await this.login(creds.email, creds.password, roleKey);
        if (result && result.access_token) {
          localStorage.setItem('trek_authenticated_role', targetRole);
          this.setCurrentRole(targetRole);
        }
      }
      return creds;
    },

    resolveActiveCourseId: async function() {
      let cached = localStorage.getItem('trek_active_course_id');
      if (cached) return cached;
      try {
        const resp = await fetch(`${API_BASE}/courses`, { headers: this.getAuthHeaders('learner') });
        if (resp.ok) {
          const courses = await resp.json();
          if (courses && courses.length > 0) {
            cached = courses[0].course_id;
            localStorage.setItem('trek_active_course_id', cached);
            return cached;
          }
        }
      } catch (e) {
        console.warn('[TrekAPI] Could not resolve course from catalog, using seeded fallback.', e);
      }
      return '4a8a62a3-19e8-4221-a7ce-59e22953f64c';
    },

    // ---------------- Learner & ML Recommender API ----------------
    getMyMastery: async function() {
      await this.ensureAuthenticated('Student');
      try {
        const resp = await fetch(`${API_BASE}/me/mastery`, {
          headers: this.getAuthHeaders('learner')
        });
        if (resp.ok) return await resp.json();
      } catch (err) {
        console.warn('[TrekAPI] getMyMastery error:', err);
      }
      return null;
    },

    getRecommendations: async function(courseId = null, limit = 4) {
      await this.ensureAuthenticated('Student');
      const authHeaders = this.getAuthHeaders('learner');
      try {
        const targetCourseId = courseId || (await this.resolveActiveCourseId());
        const resp = await fetch(`${API_BASE}/courses/${targetCourseId}/recommendations?limit=${limit}`, {
          headers: authHeaders
        });
        if (resp.ok) return await resp.json();
      } catch (err) {
        console.warn('[TrekAPI] getRecommendations error:', err);
      }
      return null;
    },

    dismissRecommendation: async function(recId) {
      await this.ensureAuthenticated('Student');
      try {
        const resp = await fetch(`${API_BASE}/recommendations/${recId}/dismiss`, {
          method: 'POST',
          headers: this.getAuthHeaders('learner')
        });
        return resp.ok;
      } catch (err) {
        console.warn('[TrekAPI] dismissRecommendation error:', err);
        return false;
      }
    },

    // ---------------- Adaptive Quiz Engine (IRT) ----------------
    startDiagnostic: async function(courseId = null) {
      await this.ensureAuthenticated('Student');
      const targetCourseId = courseId || (await this.resolveActiveCourseId());
      try {
        const resp = await fetch(`${API_BASE}/courses/${targetCourseId}/diagnostic`, {
          method: 'POST',
          headers: this.getAuthHeaders('learner')
        });
        if (resp.ok) return await resp.json();
      } catch (err) {
        console.warn('[TrekAPI] startDiagnostic error:', err);
      }
      return null;
    },

    // Cache pending submission attempt_ids across retries to prevent duplicate mutations on the backend
    _pendingAttemptIds: {},

    submitAnswer: async function(sessionId, questionId, selectedAnswer, timeTaken = 30, attemptId = null) {
      await this.ensureAuthenticated('Student');
      const dedupeKey = `${sessionId}:${questionId}`;
      let uniqueAttemptId = attemptId || this._pendingAttemptIds[dedupeKey];
      if (!uniqueAttemptId) {
        uniqueAttemptId = (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function')
          ? crypto.randomUUID()
          : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
              const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
              return v.toString(16);
            });
        this._pendingAttemptIds[dedupeKey] = uniqueAttemptId;
      }
      try {
        const resp = await fetch(`${API_BASE}/quiz-sessions/${sessionId}/answers`, {
          method: 'POST',
          headers: this.getAuthHeaders('learner'),
          body: JSON.stringify({
            attempt_id: uniqueAttemptId,
            question_id: questionId,
            submitted_answer: selectedAnswer,
            time_taken: timeTaken
          })
        });
        if (resp.ok) {
          const data = await resp.json();
          delete this._pendingAttemptIds[dedupeKey];
          return data;
        }
      } catch (err) {
        console.warn('[TrekAPI] submitAnswer error:', err);
      }
      return null;
    },

    // ---------------- Instructor Analytics & Interventions ----------------
    getInstructorHeatmap: async function(courseId = null) {
      await this.ensureAuthenticated('Teacher / Dr. Thorne');
      const targetCourseId = courseId || (await this.resolveActiveCourseId());
      try {
        const resp = await fetch(`${API_BASE}/instructor/courses/${targetCourseId}/heatmap`, {
          headers: this.getAuthHeaders('instructor')
        });
        if (resp.ok) return await resp.json();
      } catch (err) {
        console.warn('[TrekAPI] getInstructorHeatmap error:', err);
      }
      return null;
    },

    getAtRiskLearners: async function(courseId = null) {
      await this.ensureAuthenticated('Teacher / Dr. Thorne');
      const targetCourseId = courseId || (await this.resolveActiveCourseId());
      try {
        const resp = await fetch(`${API_BASE}/instructor/courses/${targetCourseId}/at-risk`, {
          headers: this.getAuthHeaders('instructor')
        });
        if (resp.ok) return await resp.json();
      } catch (err) {
        console.warn('[TrekAPI] getAtRiskLearners error:', err);
      }
      return null;
    },

    // ---------------- Admin Console & Strategy Switchboard ----------------
    toggleStrategy: async function(strategyName) {
      await this.ensureAuthenticated('Admin');
      try {
        const resp = await fetch(`${API_BASE}/admin/config/strategy`, {
          method: 'POST',
          headers: this.getAuthHeaders('admin'),
          body: JSON.stringify({ strategy: strategyName })
        });
        if (resp.ok) return await resp.json();
      } catch (err) {
        console.warn('[TrekAPI] toggleStrategy error:', err);
      }
      return null;
    },

    createUserCredentials: async function(email, role, password = 'Password123!') {
      await this.ensureAuthenticated('Admin');
      try {
        const resp = await fetch(`${API_BASE}/auth/register`, {
          method: 'POST',
          headers: this.getAuthHeaders('admin'),
          body: JSON.stringify({ email: email, password: password, role: role })
        });
        if (resp.ok) return await resp.json();
      } catch (err) {
        console.warn('[TrekAPI] createUserCredentials error:', err);
      }
      return null;
    }
  };

  window.TrekAPI = TrekAPI;

  // Auto-init connection indicator if status pill present
  document.addEventListener('DOMContentLoaded', async () => {
    const statusPills = document.querySelectorAll('.backend-status-indicator');
    if (statusPills.length > 0) {
      const health = await TrekAPI.checkHealth();
      statusPills.forEach(pill => {
        if (health && health.status === 'healthy') {
          pill.innerHTML = '<span class=\"w-2 h-2 rounded-full bg-secondary animate-pulse\"></span><span class=\"text-secondary font-bold\">API Live • v1.0.0</span>';
        } else {
          pill.innerHTML = '<span class=\"w-2 h-2 rounded-full bg-[#cf7100]\"></span><span class=\"text-[#cf7100] font-medium\">Local Demo Mode</span>';
        }
      });
    }
  });

})(window);

