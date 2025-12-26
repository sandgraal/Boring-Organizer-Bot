/**
 * B.O.B API Client
 * Handles all communication with the local B.O.B API server.
 */

const API = {
  baseUrl: "", // Same origin

  /**
   * Make a fetch request with error handling.
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const config = {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new APIError(
          error.detail || `Request failed: ${response.status}`,
          response.status,
          error
        );
      }

      return await response.json();
    } catch (err) {
      if (err instanceof APIError) {
        throw err;
      }
      throw new APIError(`Network error: ${err.message}`, 0, null);
    }
  },

  /**
   * Health check.
   */
  async health() {
    return this.request("/health");
  },

  /**
   * Ask a question.
   * @param {string} query - The question to ask.
   * @param {Object} filters - Optional filters.
   * @param {number} topK - Number of results (default 5).
   * @param {boolean|null} coachModeEnabled - Coach Mode override.
   * @param {boolean} coachShowAnyway - Bypass cooldown.
   */
  async ask(
    query,
    filters = {},
    topK = 5,
    coachModeEnabled = null,
    coachShowAnyway = false
  ) {
    return this.request("/ask", {
      method: "POST",
      body: JSON.stringify({
        query,
        filters: {
          projects: filters.projects || null,
          types: filters.types || null,
          date_after: filters.dateAfter || null,
          date_before: filters.dateBefore || null,
          language: filters.language || null,
        },
        top_k: topK,
        coach_mode_enabled: coachModeEnabled,
        coach_show_anyway: coachShowAnyway,
      }),
    });
  },

  /**
   * List all projects.
   */
  async getProjects() {
    return this.request("/projects");
  },

  /**
   * List documents with optional filters.
   * @param {Object} params - Query parameters.
   */
  async getDocuments(params = {}) {
    const query = new URLSearchParams();
    if (params.project) query.set("project", params.project);
    if (params.sourceType || params.type) {
      query.set("source_type", params.sourceType || params.type);
    }
    if (params.page) query.set("page", params.page);
    if (params.pageSize) query.set("page_size", params.pageSize);

    const queryString = query.toString();
    return this.request(`/documents${queryString ? "?" + queryString : ""}`);
  },

  /**
   * Run a routine action (daily check-in, debrief, etc.).
   * @param {string} action - Routine action name (e.g., daily-checkin).
   * @param {Object} payload - Optional routine parameters.
   */
  async runRoutine(action, payload = {}) {
    return this.request(`/routines/${action}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch the Fix Queue health dashboard signals.
   */
  async getFixQueue() {
    return this.request("/health/fix-queue");
  },

  /**
   * Start an indexing job.
   * @param {string} path - Path to index.
   * @param {string} project - Project name.
   */
  async startIndex(path, project) {
    return this.request("/index", {
      method: "POST",
      body: JSON.stringify({ path, project }),
    });
  },

  /**
   * Get indexing job status.
   * @param {string} jobId - The job ID.
   */
  async getIndexJob(jobId) {
    return this.request(`/index/${jobId}`);
  },

  /**
   * Request to open a file at a specific location.
   * @param {string} filePath - Path to the file.
   * @param {Object} locator - Locator information.
   * @param {string} editor - Preferred editor.
   */
  async openFile(filePath, locator = null, editor = null) {
    return this.request("/open", {
      method: "POST",
      body: JSON.stringify({
        file_path: filePath,
        line: locator?.start_line || null,
        editor: editor,
      }),
    });
  },

  /**
   * Get Coach Mode settings.
   */
  async getSettings() {
    return this.request("/settings");
  },

  /**
   * Update Coach Mode settings.
   * @param {Object} settings - Coach settings payload.
   */
  async updateSettings(settings) {
    return this.request("/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
  },

  /**
   * Get permission scope configuration.
   */
  async getPermissions() {
    return this.request("/permissions");
  },

  /**
   * Dismiss a Coach Mode suggestion.
   * @param {string} suggestionId - Suggestion fingerprint.
   * @param {Object} payload - Optional dismiss payload.
   */
  async dismissSuggestion(suggestionId, payload = null) {
    return this.request(`/suggestions/${suggestionId}/dismiss`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  /**
   * Submit feedback for an answer.
   * @param {Object} payload - Feedback request body.
   */
  async submitFeedback(payload) {
    return this.request("/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Create a note from a canonical template.
   * @param {Object} payload - Note creation request body.
   */
  async createNote(payload) {
    return this.request("/notes/create", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};

/**
 * Custom API Error class.
 */
class APIError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.data = data;
  }
}

// Export for use in other modules
window.API = API;
window.APIError = APIError;
