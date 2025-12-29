/**
 * B.O.B Main Application
 * Handles UI interactions and state management.
 */

(function () {
  "use strict";

  const ROUTINE_GROUPS = [
    {
      id: "daily",
      label: "Daily",
      icon: "sun",
    },
    {
      id: "weekly",
      label: "Weekly",
      icon: "calendar",
    },
    {
      id: "meeting",
      label: "Meetings",
      icon: "users",
    },
    {
      id: "decision",
      label: "Decisions",
      icon: "check-circle",
    },
    {
      id: "trip",
      label: "Trips",
      icon: "map",
    },
  ];

  const ROUTINE_ACTIONS = [
    {
      id: "daily-checkin",
      label: "Morning Check-in",
      group: "daily",
      cadence: "Daily",
      shortDescription: "Start your day with focus",
      description: "Review open loops and set your focus for today.",
    },
    {
      id: "daily-debrief",
      label: "Evening Debrief",
      group: "daily",
      cadence: "Daily",
      shortDescription: "Capture wins and lessons",
      description: "Record what went well, what you learned, and what's next.",
    },
    {
      id: "weekly-review",
      label: "Weekly Review",
      group: "weekly",
      cadence: "Weekly",
      shortDescription: "Big picture check-in",
      description: "Review highlights, stale decisions, and plan next week.",
    },
    {
      id: "meeting-prep",
      label: "Meeting Prep",
      group: "meeting",
      cadence: "Meeting",
      shortDescription: "Get ready with context",
      description: "Gather relevant decisions and questions before a meeting.",
    },
    {
      id: "meeting-debrief",
      label: "Meeting Debrief",
      group: "meeting",
      cadence: "Meeting",
      shortDescription: "Capture outcomes",
      description: "Record decisions, action items, and key takeaways.",
    },
    {
      id: "new-decision",
      label: "New Decision",
      group: "decision",
      cadence: "Ad hoc",
      shortDescription: "Document a choice",
      description: "Record a decision with context, evidence, and alternatives considered.",
    },
    {
      id: "trip-plan",
      label: "Trip Plan",
      group: "trip",
      cadence: "Trip",
      shortDescription: "Prepare for adventure",
      description: "Plan logistics, packing, and questions based on past trips.",
    },
    {
      id: "trip-debrief",
      label: "Trip Debrief",
      group: "trip",
      cadence: "Trip",
      shortDescription: "Preserve learnings",
      description: "Turn experiences into reusable lessons and checklists.",
    },
  ];

  const NOTE_TEMPLATES = [
    {
      id: "daily",
      label: "Daily Check-in",
      pathTemplate: "routines/daily/{{date}}.md",
      fields: [],
    },
    {
      id: "daily-debrief",
      label: "End-of-Day Debrief",
      pathTemplate: "routines/daily/{{date}}-debrief.md",
      fields: [],
    },
    {
      id: "weekly",
      label: "Weekly Review",
      pathTemplate: "routines/weekly/{{week}}.md",
      fields: [
        { key: "week_range", label: "Week range", type: "text", auto: "week_range" },
      ],
    },
    {
      id: "meeting",
      label: "Meeting Capture",
      pathTemplate: "meetings/{{project}}/meeting-{{date}}.md",
      fields: [
        { key: "meeting_date", label: "Meeting date", type: "date", auto: "date" },
        { key: "participant_1", label: "Participant", type: "text" },
      ],
    },
    {
      id: "decision",
      label: "Decision Record",
      pathTemplate: "decisions/decision-{{date}}.md",
      fields: [],
    },
    {
      id: "trip",
      label: "Trip Debrief",
      pathTemplate: "trips/trip-{{date}}/debrief.md",
      fields: [{ key: "trip_name", label: "Trip name", type: "text" }],
    },
    {
      id: "trip-plan",
      label: "Trip Plan",
      pathTemplate: "trips/trip-{{date}}/plan.md",
      fields: [
        { key: "trip_name", label: "Trip name", type: "text" },
        { key: "trip_dates", label: "Trip dates", type: "text" },
      ],
    },
    {
      id: "experiment",
      label: "Experiment Log",
      pathTemplate: "experiments/experiment-{{date}}.md",
      fields: [],
    },
    {
      id: "recipe",
      label: "Recipe",
      pathTemplate: "recipes/recipe-{{date}}.md",
      fields: [],
    },
  ];

  const DEFAULT_ROUTINE_ID = ROUTINE_ACTIONS[0]?.id ?? null;
  const DEFAULT_NOTE_TEMPLATE_ID = NOTE_TEMPLATES[0]?.id ?? null;

  // State
  const state = {
    currentPage: "ask",
    projects: [],
    documents: [],
    documentPage: 1,
    documentPageSize: 20,
    currentJobId: null,
    jobPollInterval: null,
    settings: null,
    coachModeOverride: null,
    lastAsk: null,
    selectedRoutineId: DEFAULT_ROUTINE_ID,
    routineResponses: {},
    routineLoading: false,
    fixQueue: null,
    fixQueueLoading: false,
    fixQueueProject: null,
    fixQueueProjectLoaded: null,
    noteTemplateId: DEFAULT_NOTE_TEMPLATE_ID,
    noteResultPath: null,
    noteModalOpen: false,
    shortcutsModalOpen: false,
    permissions: null,
    permissionsLoading: false,
  };

  const JOB_STORAGE_KEY = "bob_current_index_job";
  const HISTORY_STORAGE_KEY = "bob_index_job_history";
  const HISTORY_LIMIT = 5;

  // DOM Elements
  const elements = {};

  /**
   * Initialize the application.
   */
  async function init() {
    cacheElements();
    setupEventListeners();
    setupNavigation();
    await loadProjects();
    setupNoteModal();
    await loadSettings();
    await restoreSavedJob();
    renderJobHistory();
    renderRoutineActions();
    renderRoutineDetails();
    renderWelcomeStats();

    // Check if we have a hash route
    const hash = window.location.hash.slice(1) || "ask";
    navigateTo(hash);
  }

  /**
   * Cache DOM elements for quick access.
   */
  function cacheElements() {
    // Navigation
    elements.navLinks = document.querySelectorAll(".nav-link");
    elements.pages = document.querySelectorAll(".page");

    // Ask page
    elements.askForm = document.getElementById("ask-form");
    elements.queryInput = document.getElementById("query-input");
    elements.submitBtn = document.getElementById("submit-btn");
    elements.projectFilters = document.getElementById("project-filters");
    elements.welcomeState = document.getElementById("welcome-state");
    elements.answerContent = document.getElementById("answer-content");
    elements.answerText = document.getElementById("answer-text");
    elements.answerFooter = document.getElementById("answer-footer");
    elements.sourceCount = document.getElementById("source-count");
    elements.dateConfidence = document.getElementById("date-confidence");
    elements.outdatedWarningContainer = document.getElementById(
      "outdated-warning-container"
    );
    elements.answerFeedback = document.getElementById("answer-feedback");
    elements.feedbackButtons = document.getElementById("feedback-buttons");
    elements.feedbackStatus = document.getElementById("feedback-status");
    elements.coachToggle = document.getElementById("coach-toggle");
    elements.coachModeStatus = document.getElementById("coach-mode-status");
    elements.coachSuggestions = document.getElementById("coach-suggestions");
    elements.coachSuggestionsList = document.getElementById(
      "coach-suggestions-list"
    );
    elements.copyReportBtn = document.getElementById("copy-report-btn");
    elements.copyReportStatus = document.getElementById("copy-report-status");
    elements.notFoundState = document.getElementById("not-found-state");
    elements.notFoundQuery = document.getElementById("not-found-query");
    elements.loadingState = document.getElementById("loading-state");
    elements.errorState = document.getElementById("error-state");
    elements.errorMessage = document.getElementById("error-message");
    elements.sourcesList = document.getElementById("sources-list");
    elements.auditList = document.getElementById("audit-list");
    elements.sourcesPanel = document.getElementById("sources-panel");
    elements.auditPanel = document.getElementById("audit-panel");
    elements.sidebarTabs = document.querySelectorAll(".sidebar-tab");

    // Library page
    elements.libraryProjectFilter = document.getElementById(
      "library-project-filter"
    );
    elements.libraryTypeFilter = document.getElementById("library-type-filter");
    elements.librarySort = document.getElementById("library-sort");
    elements.documentCount = document.getElementById("document-count");
    elements.documentList = document.getElementById("document-list");
    elements.loadMoreContainer = document.getElementById("load-more-container");
    elements.loadMoreBtn = document.getElementById("load-more-btn");

    // Indexing page
    elements.indexForm = document.getElementById("index-form");
    elements.indexPath = document.getElementById("index-path");
    elements.pathOpenBtn = document.getElementById("path-open-btn");
    elements.indexProject = document.getElementById("index-project");
    elements.projectSuggestions = document.getElementById("index-project-options");
    elements.indexFeedback = document.getElementById("index-feedback");
    elements.startIndexBtn = document.getElementById("start-index-btn");
    elements.jobProgress = document.getElementById("job-progress");
    elements.progressBar = document.getElementById("progress-bar");
    elements.progressStatus = document.getElementById("progress-status");
    elements.progressPercent = document.getElementById("progress-percent");
    elements.progressFiles = document.getElementById("progress-files");
    elements.jobPath = document.getElementById("job-path");
    elements.jobProject = document.getElementById("job-project");
    elements.jobStarted = document.getElementById("job-started");
    elements.jobTotalFiles = document.getElementById("job-total-files");
    elements.jobProcessedFiles = document.getElementById("job-processed-files");
    elements.jobResult = document.getElementById("job-result");
    elements.resultFiles = document.getElementById("result-files");
    elements.resultDocuments = document.getElementById("result-documents");
    elements.resultChunks = document.getElementById("result-chunks");
    elements.jobErrors = document.getElementById("job-errors");
    elements.lastIndexSummary = document.getElementById("last-index-summary");
    elements.jobHistoryList = document.getElementById("job-history-list");
    elements.clearHistoryBtn = document.getElementById("clear-history-btn");

    // Routines page
    elements.routineActionsList = document.getElementById("routine-actions-list");
    elements.routinePreviewTitle = document.getElementById("routine-preview-title");
    elements.routinePreviewDescription = document.getElementById(
      "routine-preview-description"
    );
    elements.runRoutineBtn = document.getElementById("run-selected-routine");
    elements.routineProjectInput = document.getElementById("routine-project-input");
    elements.routineProjectOptions = document.getElementById("routine-project-options");
    elements.routineDateInput = document.getElementById("routine-date-input");
    elements.routineTopKInput = document.getElementById("routine-topk-input");
    elements.routineMeetingSlug = document.getElementById("routine-meeting-slug");
    elements.routineMeetingDate = document.getElementById("routine-meeting-date");
    elements.routineMeetingParticipants = document.getElementById(
      "routine-meeting-participants"
    );
    elements.routineDecisionTitle = document.getElementById(
      "routine-decision-title"
    );
    elements.routineDecisionSlug = document.getElementById("routine-decision-slug");
    elements.routineTripName = document.getElementById("routine-trip-name");
    elements.routineTripSlug = document.getElementById("routine-trip-slug");
    elements.routineTripDates = document.getElementById("routine-trip-dates");
    elements.routineFieldLabels = document.querySelectorAll(".routine-field");
    elements.routineStatus = document.getElementById("routine-status");
    elements.routineWarnings = document.getElementById("routine-warnings");
    elements.routinePreviewContent = document.getElementById("routine-preview-content");
    elements.routinePreviewInfo = document.getElementById("routine-preview-info");
    elements.routineRetrievals = document.getElementById("routine-retrievals");

    // Settings page
    elements.settingsDefaultMode = document.getElementById(
      "settings-coach-default"
    );
    elements.settingsCooldown = document.getElementById(
      "settings-coach-cooldown"
    );
    elements.settingsProjectModes = document.getElementById(
      "settings-project-modes"
    );
    elements.settingsSaveBtn = document.getElementById("settings-save-btn");
    elements.settingsStatus = document.getElementById("settings-status");
    elements.permissionsScope = document.getElementById("permissions-scope");
    elements.permissionsVaultRoot = document.getElementById("permissions-vault-root");
    elements.permissionsPaths = document.getElementById("permissions-paths");
    elements.permissionsConnectors = document.getElementById("permissions-connectors");

    // Connector actions
    elements.connectorsAvailability = document.getElementById(
      "connectors-availability"
    );
    elements.connectorsBookmarksPath = document.getElementById(
      "connectors-bookmarks-path"
    );
    elements.connectorsBookmarksProject = document.getElementById(
      "connectors-bookmarks-project"
    );
    elements.connectorsBookmarksLanguage = document.getElementById(
      "connectors-bookmarks-language"
    );
    elements.connectorsBookmarksImportBtn = document.getElementById(
      "connectors-bookmarks-import-btn"
    );
    elements.connectorsBookmarksStatus = document.getElementById(
      "connectors-bookmarks-status"
    );
    elements.connectorsHighlightText = document.getElementById(
      "connectors-highlight-text"
    );
    elements.connectorsHighlightUrl = document.getElementById(
      "connectors-highlight-url"
    );
    elements.connectorsHighlightProject = document.getElementById(
      "connectors-highlight-project"
    );
    elements.connectorsHighlightLanguage = document.getElementById(
      "connectors-highlight-language"
    );
    elements.connectorsHighlightSaveBtn = document.getElementById(
      "connectors-highlight-save-btn"
    );
    elements.connectorsHighlightStatus = document.getElementById(
      "connectors-highlight-status"
    );

    // New note modal
    elements.newNoteBtn = document.getElementById("new-note-btn");
    elements.noteModal = document.getElementById("note-modal");
    elements.noteModalClose = document.getElementById("note-modal-close");
    elements.noteForm = document.getElementById("note-form");
    elements.noteTemplate = document.getElementById("note-template");
    elements.noteTemplateHint = document.getElementById("note-template-hint");
    elements.noteTargetPath = document.getElementById("note-target-path");
    elements.noteProject = document.getElementById("note-project");
    elements.noteProjectOptions = document.getElementById("note-project-options");
    elements.noteDate = document.getElementById("note-date");
    elements.noteLanguage = document.getElementById("note-language");
    elements.noteExtraFields = document.getElementById("note-extra-fields");
    elements.noteCancelBtn = document.getElementById("note-cancel-btn");
    elements.noteStatus = document.getElementById("note-status");
    elements.noteResult = document.getElementById("note-result");
    elements.noteResultPath = document.getElementById("note-result-path");
    elements.noteResultWarnings = document.getElementById("note-result-warnings");
    elements.noteOpenBtn = document.getElementById("note-open-btn");

    // Shortcuts modal
    elements.shortcutsModal = document.getElementById("shortcuts-modal");
    elements.shortcutsModalClose = document.getElementById("shortcuts-modal-close");
    elements.shortcutsBtn = document.getElementById("shortcuts-btn");

    // Health page
    elements.failureSignalsList = document.getElementById("failure-signals-list");
    elements.fixQueueTasksList = document.getElementById("fixqueue-tasks-list");
    elements.refreshFixQueueBtn = document.getElementById("refresh-fixqueue-btn");
    elements.fixQueueProjectFilter = document.getElementById("fixqueue-project-filter");
  }

  /**
   * Set up event listeners.
   */
  function setupEventListeners() {
    // Ask form
    elements.askForm.addEventListener("submit", handleAskSubmit);
    elements.projectFilters?.addEventListener("change", handleProjectFilterChange);
    elements.coachToggle?.addEventListener("change", handleCoachToggle);
    elements.sidebarTabs?.forEach((tab) =>
      tab.addEventListener("click", handleSidebarTabClick)
    );
    elements.copyReportBtn?.addEventListener("click", handleCopyReport);
    elements.feedbackButtons?.addEventListener("click", handleFeedbackClick);

    // Library filters
    elements.libraryProjectFilter?.addEventListener(
      "change",
      handleLibraryFilterChange
    );
    elements.libraryTypeFilter?.addEventListener(
      "change",
      handleLibraryFilterChange
    );
    elements.librarySort?.addEventListener("change", handleLibraryFilterChange);
    elements.loadMoreBtn?.addEventListener("click", loadMoreDocuments);

    // Index form
    elements.indexForm?.addEventListener("submit", handleIndexSubmit);
    elements.pathOpenBtn?.addEventListener("click", handleOpenPath);

    // Settings save
    elements.settingsSaveBtn?.addEventListener("click", handleSettingsSave);
    elements.connectorsBookmarksImportBtn?.addEventListener(
      "click",
      handleBookmarksImport
    );
    elements.connectorsHighlightSaveBtn?.addEventListener(
      "click",
      handleHighlightSave
    );

    elements.routineActionsList?.addEventListener(
      "click",
      handleRoutineActionsClick
    );
    elements.runRoutineBtn?.addEventListener("click", handleRunSelectedRoutine);
    elements.refreshFixQueueBtn?.addEventListener("click", () => loadFixQueue(true));
    elements.fixQueueProjectFilter?.addEventListener(
      "change",
      handleFixQueueProjectChange
    );
    elements.fixQueueTasksList?.addEventListener("click", handleFixQueueTaskClick);

    // New note modal
    elements.newNoteBtn?.addEventListener("click", openNoteModal);
    elements.noteModalClose?.addEventListener("click", closeNoteModal);
    elements.noteCancelBtn?.addEventListener("click", closeNoteModal);
    elements.noteModal?.addEventListener("click", handleNoteModalBackdrop);
    elements.noteForm?.addEventListener("submit", handleNoteSubmit);
    elements.noteTemplate?.addEventListener("change", handleNoteTemplateChange);
    elements.noteDate?.addEventListener("change", handleNoteDateChange);
    elements.noteProject?.addEventListener("input", updateNoteTemplateHint);
    elements.noteOpenBtn?.addEventListener("click", handleOpenCreatedNote);
    document.addEventListener("keydown", handleNoteModalKeydown);
    document.addEventListener("keydown", handleGlobalKeydown);

    // Shortcuts modal
    elements.shortcutsBtn?.addEventListener("click", openShortcutsModal);
    elements.shortcutsModalClose?.addEventListener("click", closeShortcutsModal);
    elements.shortcutsModal?.addEventListener("click", handleShortcutsModalBackdrop);

    elements.clearHistoryBtn?.addEventListener("click", handleClearHistory);
  }

  /**
   * Set up navigation.
   */
  function setupNavigation() {
    elements.navLinks.forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const page = link.dataset.page;
        navigateTo(page);
      });
    });

    // Handle browser back/forward
    window.addEventListener("hashchange", () => {
      const hash = window.location.hash.slice(1) || "ask";
      navigateTo(hash, false);
    });
  }

  /**
   * Navigate to a page.
   */
  function navigateTo(page, updateHash = true) {
    state.currentPage = page;

    // Update URL hash
    if (updateHash) {
      window.location.hash = page;
    }

    // Update nav links
    elements.navLinks.forEach((link) => {
      link.classList.toggle("active", link.dataset.page === page);
    });

    // Show/hide pages
    elements.pages.forEach((pageEl) => {
      pageEl.classList.toggle("active", pageEl.id === `page-${page}`);
    });

    // Page-specific initialization
    if (page === "library") {
      loadDocuments();
    }
    if (page === "settings") {
      loadSettings();
      loadPermissions();
    }
    if (page === "routines") {
      renderRoutineActions();
      renderRoutineDetails();
    }
    if (page === "health") {
      loadFixQueue();
    }
  }

  /**
   * Load projects from API.
   */
  async function loadProjects() {
    try {
      const response = await API.getProjects();
      const rawProjects = response.projects || [];
      const normalized = rawProjects
        .map((project) => normalizeProjectName(project))
        .filter(Boolean);
      state.projects = Array.from(new Set(normalized));
      renderProjectFilters();
      renderLibraryProjectOptions();
      renderFixQueueProjectOptions();
    } catch (err) {
      console.error("Failed to load projects:", err);
      elements.projectFilters.innerHTML =
        '<div class="loading-placeholder">Failed to load</div>';
    }
  }

  function normalizeProjectName(project) {
    if (!project) return null;
    if (typeof project === "string") return project;
    if (typeof project === "object" && project.name) {
      return String(project.name);
    }
    return null;
  }

  /**
   * Render project filter checkboxes.
   */
  function renderProjectFilters() {
    if (state.projects.length === 0) {
      elements.projectFilters.innerHTML =
        '<div class="loading-placeholder">No projects indexed</div>';
      renderProjectSuggestions();
      return;
    }

    elements.projectFilters.innerHTML = state.projects
      .map(
        (project) => `
            <label class="checkbox-item">
                <input type="checkbox" name="project" value="${escapeHtml(
                  project
                )}" checked>
                <span>${escapeHtml(project)}</span>
            </label>
        `
      )
      .join("");
    renderProjectSuggestions();
  }

  function renderProjectSuggestions() {
    const options = state.projects
      .map((project) => `<option value="${escapeHtml(project)}">`)
      .join("");

    if (elements.projectSuggestions) {
      elements.projectSuggestions.innerHTML = options;
    }

    if (elements.routineProjectOptions) {
      elements.routineProjectOptions.innerHTML = options;
    }

    if (elements.noteProjectOptions) {
      elements.noteProjectOptions.innerHTML = options;
    }
  }

  /**
   * Render welcome stats showing indexed content summary.
   */
  async function renderWelcomeStats() {
    const welcomeStats = document.getElementById("welcome-stats");
    if (!welcomeStats) return;

    try {
      const response = await API.getHealth();
      const projectCount = state.projects.length;
      const documentCount = response.indexed_documents || 0;

      if (documentCount === 0 && projectCount === 0) {
        welcomeStats.innerHTML = `
          <div class="welcome-empty-state">
            <p>No documents indexed yet.</p>
            <a href="#indexing" class="btn btn-primary btn-sm">Index your first folder</a>
          </div>
        `;
        return;
      }

      welcomeStats.innerHTML = `
        <div class="welcome-stat">
          <span class="welcome-stat-value">${documentCount}</span>
          <span class="welcome-stat-label">Documents</span>
        </div>
        <div class="welcome-stat">
          <span class="welcome-stat-value">${projectCount}</span>
          <span class="welcome-stat-label">${projectCount === 1 ? 'Project' : 'Projects'}</span>
        </div>
      `;
    } catch (err) {
      console.error("Failed to load welcome stats:", err);
      welcomeStats.innerHTML = "";
    }
  }

  function setupNoteModal() {
    if (!elements.noteTemplate) return;
    renderNoteTemplateOptions();
    if (state.noteTemplateId) {
      elements.noteTemplate.value = state.noteTemplateId;
    }
    if (elements.noteDate && !elements.noteDate.value) {
      elements.noteDate.value = formatDateLocal(new Date());
    }
    updateNoteTemplateUI(true);
  }

  function renderNoteTemplateOptions() {
    if (!elements.noteTemplate) return;
    elements.noteTemplate.innerHTML = NOTE_TEMPLATES.map(
      (template) =>
        `<option value="${escapeHtml(template.id)}">${escapeHtml(
          template.label
        )}</option>`
    ).join("");
  }

  function openNoteModal() {
    if (!elements.noteModal) return;
    elements.noteModal.classList.remove("hidden");
    elements.noteModal.setAttribute("aria-hidden", "false");
    state.noteModalOpen = true;

    if (elements.noteProject && !elements.noteProject.value) {
      elements.noteProject.value = getSelectedProject() || "";
    }
    if (elements.noteDate && !elements.noteDate.value) {
      elements.noteDate.value = formatDateLocal(new Date());
    }
    if (elements.noteLanguage && !elements.noteLanguage.value) {
      elements.noteLanguage.value = "en";
    }
    updateNoteTemplateUI(false);
    clearNoteStatus();
    clearNoteResult();
    elements.noteTargetPath?.focus();
  }

  function closeNoteModal() {
    if (!elements.noteModal) return;
    elements.noteModal.classList.add("hidden");
    elements.noteModal.setAttribute("aria-hidden", "true");
    state.noteModalOpen = false;
  }

  function handleNoteModalBackdrop(event) {
    if (event.target === elements.noteModal) {
      closeNoteModal();
    }
  }

  function handleNoteModalKeydown(event) {
    if (event.key === "Escape" && state.noteModalOpen) {
      closeNoteModal();
    }
  }

  // Shortcuts modal functions
  function openShortcutsModal() {
    if (!elements.shortcutsModal) return;
    elements.shortcutsModal.classList.remove("hidden");
    elements.shortcutsModal.setAttribute("aria-hidden", "false");
    state.shortcutsModalOpen = true;
  }

  function closeShortcutsModal() {
    if (!elements.shortcutsModal) return;
    elements.shortcutsModal.classList.add("hidden");
    elements.shortcutsModal.setAttribute("aria-hidden", "true");
    state.shortcutsModalOpen = false;
  }

  function handleShortcutsModalBackdrop(event) {
    if (event.target === elements.shortcutsModal) {
      closeShortcutsModal();
    }
  }

  function handleNoteTemplateChange() {
    if (!elements.noteTemplate) return;
    state.noteTemplateId = elements.noteTemplate.value;
    updateNoteTemplateUI(true);
  }

  function handleNoteDateChange() {
    updateNoteAutoFields();
    updateNoteTemplateHint(false);
  }

  function updateNoteTemplateUI(updateTargetPath) {
    const template = getNoteTemplate();
    renderNoteExtraFields(template);
    updateNoteAutoFields();
    updateNoteTemplateHint(updateTargetPath);
  }

  function updateNoteTemplateHint(updateTargetPath) {
    if (!elements.noteTemplateHint) return;
    const template = getNoteTemplate();
    const suggestion = buildNotePathSuggestion(template);
    elements.noteTemplateHint.textContent = suggestion
      ? `Suggested path: ${suggestion}`
      : "";
    if (elements.noteTargetPath) {
      if (suggestion) {
        elements.noteTargetPath.placeholder = suggestion;
      }
      if (updateTargetPath || !elements.noteTargetPath.value.trim()) {
        elements.noteTargetPath.value = suggestion;
      }
    }
  }

  function renderNoteExtraFields(template) {
    if (!elements.noteExtraFields) return;
    if (!template || !template.fields || template.fields.length === 0) {
      elements.noteExtraFields.innerHTML = "";
      return;
    }
    elements.noteExtraFields.innerHTML = template.fields
      .map((field) => {
        const inputType = field.type || "text";
        const inputClass = inputType === "date" ? "date-input" : "text-input";
        return `
          <div class="form-group">
            <label class="filter-label" for="note-extra-${escapeHtml(field.key)}">
              ${escapeHtml(field.label)}
            </label>
            <input
              id="note-extra-${escapeHtml(field.key)}"
              class="${inputClass}"
              type="${escapeHtml(inputType)}"
              data-note-key="${escapeHtml(field.key)}"
              autocomplete="off"
            />
          </div>
        `;
      })
      .join("");
  }

  function updateNoteAutoFields() {
    if (!elements.noteExtraFields) return;
    const dateValue = getNoteDateValue();
    const date = parseDateInput(dateValue);
    const meetingDate = formatDateLocal(date);
    const weekRange = getWeekRange(date);
    const fields = elements.noteExtraFields.querySelectorAll("[data-note-key]");
    fields.forEach((field) => {
      const key = field.dataset.noteKey;
      if (key === "meeting_date") {
        setAutoFieldValue(field, meetingDate);
      }
      if (key === "week_range") {
        setAutoFieldValue(field, weekRange);
      }
    });
  }

  function setAutoFieldValue(field, value) {
    const previousAuto = field.dataset.autoValue;
    if (!field.value || (previousAuto && field.value === previousAuto)) {
      field.value = value;
    }
    field.dataset.autoValue = value;
  }

  function collectNoteExtraValues() {
    if (!elements.noteExtraFields) return {};
    const values = {};
    elements.noteExtraFields
      .querySelectorAll("[data-note-key]")
      .forEach((field) => {
        const key = field.dataset.noteKey;
        const value = field.value?.trim();
        if (key && value) {
          values[key] = value;
        }
      });
    return values;
  }

  function buildNotePathSuggestion(template) {
    if (!template) return "";
    const dateValue = getNoteDateValue();
    const date = parseDateInput(dateValue);
    const dateLabel = formatDateLocal(date);
    const weekLabel = getIsoWeekLabel(date);
    const projectValue =
      elements.noteProject?.value || getSelectedProject() || "project";
    const projectLabel = slugifyPathSegment(projectValue);

    return (template.pathTemplate || "")
      .replace("{{date}}", dateLabel)
      .replace("{{week}}", weekLabel)
      .replace("{{project}}", projectLabel);
  }

  function handleNoteSubmit(event) {
    event.preventDefault();
    if (!elements.noteTemplate || !elements.noteTargetPath) return;
    const template = elements.noteTemplate.value;
    const targetPath = elements.noteTargetPath.value.trim();
    if (!targetPath) {
      setNoteStatus("Target path is required to create a note.", "error");
      return;
    }

    updateNoteAutoFields();
    const values = collectNoteExtraValues();
    if (template === "weekly" && !values.week_range) {
      values.week_range = getWeekRange(parseDateInput(getNoteDateValue()));
    }

    const project = elements.noteProject?.value.trim();
    const noteDate = elements.noteDate?.value;
    const language = elements.noteLanguage?.value.trim();

    const payload = {
      template,
      target_path: targetPath,
      project: project || null,
      date: noteDate || null,
      language: language || null,
      values,
    };

    submitNote(payload);
  }

  async function submitNote(payload) {
    setNoteStatus("Creating note...", null);
    const submitButton = elements.noteForm?.querySelector('button[type="submit"]');
    submitButton?.setAttribute("disabled", "true");
    try {
      const response = await API.createNote(payload);
      setNoteStatus("Note created.", "success");
      setNoteResult(response);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to create note.";
      setNoteStatus(message, "error");
    } finally {
      submitButton?.removeAttribute("disabled");
    }
  }

  async function handleOpenCreatedNote() {
    if (!state.noteResultPath) return;
    try {
      await API.openFile(state.noteResultPath);
    } catch (err) {
      console.error("Failed to open created note:", err);
      alert(
        `Could not open file: ${state.noteResultPath}\n\nYou can open it manually.`
      );
    }
  }

  function setNoteStatus(message, type) {
    if (!elements.noteStatus) return;
    elements.noteStatus.textContent = message;
    elements.noteStatus.classList.remove("hidden", "success", "error");
    if (type === "success") {
      elements.noteStatus.classList.add("success");
    } else if (type === "error") {
      elements.noteStatus.classList.add("error");
    }
  }

  function clearNoteStatus() {
    if (!elements.noteStatus) return;
    elements.noteStatus.classList.add("hidden");
    elements.noteStatus.textContent = "";
    elements.noteStatus.classList.remove("success", "error");
  }

  function setNoteResult(response) {
    if (!elements.noteResult || !elements.noteResultPath) return;
    state.noteResultPath = response.file_path;
    elements.noteResultPath.textContent = response.file_path;
    const warnings = response.warnings || [];
    if (elements.noteResultWarnings) {
      elements.noteResultWarnings.textContent = warnings.join(" ");
    }
    elements.noteResult.classList.remove("hidden");
  }

  function clearNoteResult() {
    if (!elements.noteResult || !elements.noteResultPath) return;
    state.noteResultPath = null;
    elements.noteResultPath.textContent = "";
    if (elements.noteResultWarnings) {
      elements.noteResultWarnings.textContent = "";
    }
    elements.noteResult.classList.add("hidden");
  }

  function getNoteTemplate() {
    const templateId = elements.noteTemplate?.value || state.noteTemplateId;
    return NOTE_TEMPLATES.find((template) => template.id === templateId) || null;
  }

  function getNoteDateValue() {
    return elements.noteDate?.value || formatDateLocal(new Date());
  }

  function parseDateInput(value) {
    if (!value) return new Date();
    const parts = value.split("-");
    if (parts.length !== 3) return new Date();
    const year = Number(parts[0]);
    const month = Number(parts[1]) - 1;
    const day = Number(parts[2]);
    return new Date(year, month, day);
  }

  function formatDateLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function getIsoWeekLabel(date) {
    const utcDate = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = utcDate.getUTCDay() || 7;
    utcDate.setUTCDate(utcDate.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(utcDate.getUTCFullYear(), 0, 1));
    const week = Math.ceil(((utcDate - yearStart) / 86400000 + 1) / 7);
    return `${utcDate.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
  }

  function getWeekRange(date) {
    const day = (date.getDay() + 6) % 7;
    const start = new Date(date);
    start.setDate(date.getDate() - day);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return `${formatDateLocal(start)} - ${formatDateLocal(end)}`;
  }

  function slugifyPathSegment(value) {
    const normalized = String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "");
    return normalized || "project";
  }

  function getRoutineAction(actionId) {
    return ROUTINE_ACTIONS.find((action) => action.id === actionId) || null;
  }

  /**
   * Derive unique groups from ROUTINE_ACTIONS.
   * Falls back to ROUTINE_GROUPS for metadata (label, icon) if defined.
   */
  function getRoutineGroups() {
    const seenGroups = new Set();
    const groups = [];
    for (const action of ROUTINE_ACTIONS) {
      if (action.group && !seenGroups.has(action.group)) {
        seenGroups.add(action.group);
        const meta = ROUTINE_GROUPS.find((g) => g.id === action.group);
        groups.push({
          id: action.group,
          label: meta?.label || action.group,
          icon: meta?.icon || null,
        });
      }
    }
    return groups;
  }

  /**
   * Create a routine card element safely using DOM APIs.
   */
  function createRoutineCard(action, isActive) {
    const card = document.createElement("div");
    card.className = "routine-card" + (isActive ? " active" : "");
    card.dataset.action = action.id;

    const header = document.createElement("div");
    header.className = "routine-card-header";

    const label = document.createElement("span");
    label.className = "routine-card-label";
    label.textContent = action.label;
    header.appendChild(label);

    card.appendChild(header);

    if (action.shortDescription) {
      const short = document.createElement("p");
      short.className = "routine-card-short";
      short.textContent = action.shortDescription;
      card.appendChild(short);
    }

    return card;
  }

  /**
   * Create a routine group element safely using DOM APIs.
   */
  function createRoutineGroup(group, actions) {
    const groupEl = document.createElement("div");
    groupEl.className = "routine-group";

    const headerEl = document.createElement("div");
    headerEl.className = "routine-group-header";

    const iconEl = document.createElement("span");
    iconEl.className = "routine-group-icon";
    if (group.icon) {
      iconEl.dataset.icon = group.icon;
    }
    headerEl.appendChild(iconEl);

    const labelEl = document.createElement("span");
    labelEl.className = "routine-group-label";
    labelEl.textContent = group.label;
    headerEl.appendChild(labelEl);

    groupEl.appendChild(headerEl);

    const itemsEl = document.createElement("div");
    itemsEl.className = "routine-group-items";

    for (const action of actions) {
      const isActive = state.selectedRoutineId === action.id;
      itemsEl.appendChild(createRoutineCard(action, isActive));
    }

    groupEl.appendChild(itemsEl);
    return groupEl;
  }

  function renderRoutineActions() {
    if (!elements.routineActionsList) return;

    // Clear existing content safely
    elements.routineActionsList.textContent = "";

    const groups = getRoutineGroups();
    for (const group of groups) {
      const groupActions = ROUTINE_ACTIONS.filter((a) => a.group === group.id);
      if (groupActions.length === 0) continue;
      elements.routineActionsList.appendChild(createRoutineGroup(group, groupActions));
    }
  }

  function updateRoutineFieldVisibility(actionId) {
    if (!elements.routineFieldLabels) return;
    elements.routineFieldLabels.forEach((field) => {
      const targets = field.dataset.routines || "";
      const targetList = targets.split(/\s+/).filter(Boolean);
      const isVisible = targetList.includes(actionId);
      field.classList.toggle("hidden", !isVisible);
    });
  }

  function renderRoutineDetails() {
    const actionId = state.selectedRoutineId || DEFAULT_ROUTINE_ID;
    const action = getRoutineAction(actionId);
    updateRoutineFieldVisibility(action?.id);

    if (elements.routinePreviewTitle) {
      elements.routinePreviewTitle.textContent =
        action?.label || "Select a routine";
    }

    if (elements.routinePreviewDescription) {
      elements.routinePreviewDescription.textContent =
        action?.description || "Preview and run.";
    }

    const responseEntry = action ? state.routineResponses[action.id] : null;
    const response = responseEntry?.response;

    if (elements.routinePreviewContent) {
      elements.routinePreviewContent.textContent =
        response?.content?.trim() || "Run to preview the generated note.";
    }

    if (elements.routinePreviewInfo) {
      elements.routinePreviewInfo.textContent = response
        ? `File: ${response.file_path} • Template: ${response.template}`
        : "No runs yet. Run the routine to see the rendered template.";
    }

    renderRoutineWarnings(response?.warnings || []);
    renderRoutineRetrievals(response?.retrievals || []);
    updateRoutineRunButton();
  }

  function renderRoutineWarnings(warnings) {
    if (!elements.routineWarnings) return;
    if (!warnings.length) {
      elements.routineWarnings.innerHTML = "";
      return;
    }
    elements.routineWarnings.innerHTML = warnings
      .map((warning) => `<div class="routine-warning">${escapeHtml(warning)}</div>`)
      .join("");
  }

  function renderRoutineRetrievals(retrievals) {
    if (!elements.routineRetrievals) return;
    if (!retrievals || retrievals.length === 0) {
      elements.routineRetrievals.innerHTML = `
        <div class="routine-citations-empty">
          <span class="routine-citations-empty-icon">📎</span>
          <p>Run a routine to see cited sources here.</p>
        </div>
      `;
      return;
    }

    const html = retrievals
      .map((bucket) => {
        const sourcesList = bucket.sources || [];
        const totalSources = sourcesList.length;
        const sources = sourcesList
          .slice(0, 3)
          .map(
            (source) =>
              `<li>${escapeHtml(source.file_path)} (${escapeHtml(
                source.date_confidence || "UNKNOWN"
              )}) • ${escapeHtml(formatLocator(source.locator))}</li>`
          )
          .join("");
        const moreSources =
          totalSources > 3
            ? `<li>+${totalSources - 3} more sources</li>`
            : "";
        return `
          <div class="routine-retrieval-card">
            <strong>${escapeHtml(bucket.name)} (${totalSources} sources)</strong>
            <div class="routine-retrieval-meta">
              Query: ${escapeHtml(bucket.query)}
            </div>
            <ul class="routine-retrieval-sources">
              ${sources}
              ${moreSources}
            </ul>
          </div>
        `;
      })
      .join("");

    elements.routineRetrievals.innerHTML = html;
  }

  function selectRoutine(actionId) {
    if (!actionId) return;
    state.selectedRoutineId = actionId;
    renderRoutineActions();
    renderRoutineDetails();
  }

  function updateRoutineRunButton() {
    if (!elements.runRoutineBtn) return;
    elements.runRoutineBtn.disabled =
      state.routineLoading || !state.selectedRoutineId;
    elements.runRoutineBtn.textContent = state.routineLoading
      ? "Running..."
      : "Run routine";
  }

  function isRoutineFieldVisible(element) {
    return element && !element.closest(".hidden");
  }

  function buildRoutinePayload(overrides = {}) {
    const payload = { ...overrides };
    if (!("project" in payload)) {
      const project = elements.routineProjectInput?.value.trim();
      if (project) {
        payload.project = project;
      }
    }
    if (!("date" in payload)) {
      const date = elements.routineDateInput?.value;
      if (date) {
        payload.date = date;
      }
    }
    if (!("top_k" in payload)) {
      const topK = parseInt(elements.routineTopKInput?.value, 10);
      if (!Number.isNaN(topK) && topK > 0) {
        payload.top_k = topK;
      }
    }
    if (!("meeting_slug" in payload) && isRoutineFieldVisible(elements.routineMeetingSlug)) {
      const meetingSlug = elements.routineMeetingSlug?.value.trim();
      if (meetingSlug) {
        payload.meeting_slug = meetingSlug;
      }
    }
    if (!("meeting_date" in payload) && isRoutineFieldVisible(elements.routineMeetingDate)) {
      const meetingDate = elements.routineMeetingDate?.value;
      if (meetingDate) {
        payload.meeting_date = meetingDate;
      }
    }
    if (
      !("participants" in payload) &&
      isRoutineFieldVisible(elements.routineMeetingParticipants)
    ) {
      const participantsRaw = elements.routineMeetingParticipants?.value || "";
      const participants = participantsRaw
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean);
      if (participants.length > 0) {
        payload.participants = participants;
      }
    }
    if (
      !("title" in payload) &&
      isRoutineFieldVisible(elements.routineDecisionTitle)
    ) {
      const decisionTitle = elements.routineDecisionTitle?.value.trim();
      if (decisionTitle) {
        payload.title = decisionTitle;
      }
    }
    if (
      !("decision_slug" in payload) &&
      isRoutineFieldVisible(elements.routineDecisionSlug)
    ) {
      const decisionSlug = elements.routineDecisionSlug?.value.trim();
      if (decisionSlug) {
        payload.decision_slug = decisionSlug;
      }
    }
    if (!("trip_name" in payload) && isRoutineFieldVisible(elements.routineTripName)) {
      const tripName = elements.routineTripName?.value.trim();
      if (tripName) {
        payload.trip_name = tripName;
      }
    }
    if (!("trip_slug" in payload) && isRoutineFieldVisible(elements.routineTripSlug)) {
      const tripSlug = elements.routineTripSlug?.value.trim();
      if (tripSlug) {
        payload.trip_slug = tripSlug;
      }
    }
    if (!("trip_dates" in payload) && isRoutineFieldVisible(elements.routineTripDates)) {
      const tripDates = elements.routineTripDates?.value.trim();
      if (tripDates) {
        payload.trip_dates = tripDates;
      }
    }
    return payload;
  }

  async function executeRoutine(actionId, overrides = {}) {
    const action = getRoutineAction(actionId);
    if (!action) return;

    const payload = buildRoutinePayload(overrides);
    state.routineLoading = true;
    selectRoutine(action.id);
    setRoutineStatus("", null);

    try {
      const response = await API.runRoutine(action.id, payload);
      state.routineResponses[action.id] = {
        response,
        executedAt: new Date().toISOString(),
      };
      renderRoutineDetails();
      setRoutineStatus(`Routine wrote ${response.file_path}.`, "success");
    } catch (err) {
      console.error("Routine failed:", err);
      const message =
        err instanceof Error ? err.message : "Failed to run routine.";
      setRoutineStatus(message, "error");
    } finally {
      state.routineLoading = false;
      updateRoutineRunButton();
    }
  }

  function handleRoutineActionsClick(event) {
    const runTrigger = event.target.closest("[data-run-action]");
    if (runTrigger) {
      const actionId = runTrigger.dataset.runAction;
      if (actionId) {
        executeRoutine(actionId);
      }
      return;
    }
    const card = event.target.closest(".routine-card");
    const actionId = card?.dataset?.action;
    if (actionId) {
      selectRoutine(actionId);
    }
  }

  function handleRunSelectedRoutine(event) {
    event?.preventDefault();
    if (!state.selectedRoutineId) return;
    executeRoutine(state.selectedRoutineId);
  }

  function setRoutineStatus(message, type) {
    if (!elements.routineStatus) return;
    if (!message) {
      elements.routineStatus.classList.add("hidden");
      elements.routineStatus.textContent = "";
      elements.routineStatus.classList.remove("success", "error");
      return;
    }
    elements.routineStatus.classList.remove("hidden");
    elements.routineStatus.textContent = message;
    elements.routineStatus.classList.toggle("success", type === "success");
    elements.routineStatus.classList.toggle("error", type === "error");
  }

  function handleFixQueueProjectChange() {
    const value = elements.fixQueueProjectFilter?.value || "";
    state.fixQueueProject = value ? value : null;
    loadFixQueue(true);
  }

  async function loadFixQueue(force = false) {
    if (
      !elements.failureSignalsList ||
      !elements.fixQueueTasksList ||
      state.fixQueueLoading
    ) {
      return;
    }

    const selectedProject = state.fixQueueProject || null;
    if (
      !force &&
      state.fixQueue &&
      state.fixQueueProjectLoaded === selectedProject
    ) {
      renderFailureSignals(state.fixQueue.failure_signals);
      renderFixQueueTasks(state.fixQueue.tasks);
      return;
    }

    state.fixQueueLoading = true;
    elements.failureSignalsList.innerHTML =
      '<div class="loading-placeholder loading" role="status" aria-busy="true" aria-label="Loading health metrics"></div>';
    elements.fixQueueTasksList.innerHTML =
      '<div class="loading-placeholder loading" role="status" aria-busy="true" aria-label="Loading Fix Queue tasks"></div>';
    elements.refreshFixQueueBtn?.setAttribute("disabled", "true");

    try {
      const response = await API.getFixQueue(selectedProject);
      state.fixQueue = response;
      state.fixQueueProjectLoaded = selectedProject;
      renderFailureSignals(response.failure_signals);
      renderFixQueueTasks(response.tasks);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Unable to load Fix Queue.";
      elements.failureSignalsList.innerHTML = `<div class="loading-placeholder">${escapeHtml(
        message
      )}</div>`;
      elements.fixQueueTasksList.innerHTML = `<div class="loading-placeholder">${escapeHtml(
        message
      )}</div>`;
    } finally {
      state.fixQueueLoading = false;
      elements.refreshFixQueueBtn?.removeAttribute("disabled");
    }
  }

  function renderFailureSignals(signals) {
    if (!elements.failureSignalsList) return;
    if (!signals || signals.length === 0) {
      elements.failureSignalsList.innerHTML = `
        <div class="health-empty-state">
          <div class="health-empty-icon">✓</div>
          <strong>All clear</strong>
          <p>No issues detected in your knowledge base.</p>
        </div>
      `;
      return;
    }

    elements.failureSignalsList.innerHTML = signals
      .map(
        (signal) => `
          <div class="health-signal-card">
            <strong>${escapeHtml(signal.name)}</strong>
            <div>Value: ${escapeHtml(String(signal.value))}</div>
            <div>${escapeHtml(signal.details || "No details provided.")}</div>
          </div>
        `
      )
      .join("");
  }

  function renderFixQueueTasks(tasks) {
    if (!elements.fixQueueTasksList) return;
    if (!tasks || tasks.length === 0) {
      elements.fixQueueTasksList.innerHTML = `
        <div class="health-empty-state">
          <div class="health-empty-icon">🎉</div>
          <strong>Nothing to fix</strong>
          <p>Your notes are in good shape. Keep capturing!</p>
        </div>
      `;
      return;
    }

    const sortedTasks = [...tasks].sort((a, b) => a.priority - b.priority);
    elements.fixQueueTasksList.innerHTML = sortedTasks
      .map((task) => {
        const actionButton = getFixQueueActionButton(task);
        const projectMeta = task.project
          ? `<span>Project: ${escapeHtml(task.project)}</span>`
          : "";
        return `
          <div class="fixqueue-task-card">
            <div><strong>${escapeHtml(task.reason)}</strong></div>
            <div class="fixqueue-task-meta">
              <span>Action: ${escapeHtml(task.action)}</span>
              <span>Target: ${escapeHtml(task.target)}</span>
              ${projectMeta}
              <span class="priority-badge">P${escapeHtml(
                String(task.priority)
              )}</span>
            </div>
            <div class="fixqueue-task-actions">
              ${actionButton}
            </div>
          </div>
        `;
      })
      .join("");
  }

  function getFixQueueActionButton(task) {
    const projectAttr = task.project
      ? `data-fixqueue-project="${escapeHtml(task.project)}"`
      : "";
    const routineTarget = extractRoutineIdFromTarget(task.target);
    if (task.action === "run_routine" && routineTarget) {
      return `<button type="button" class="btn btn-primary btn-sm" data-fixqueue-run="${escapeHtml(
        task.target
      )}" ${projectAttr}>
         Run routine
       </button>`;
    }
    if (task.action === "run_query") {
      return `<button type="button" class="btn btn-primary btn-sm" data-fixqueue-query="${escapeHtml(
        task.target
      )}" ${projectAttr}>
         Run query
       </button>`;
    }
    if (task.action === "run_routine") {
      return `<button type="button" class="btn btn-primary btn-sm" data-fixqueue-query="${escapeHtml(
        task.target
      )}" ${projectAttr}>
         Run query
       </button>`;
    }
    if (
      task.action === "fix_metadata" ||
      task.action === "fix_capture" ||
      task.action === "open_file"
    ) {
      return `<button type="button" class="btn btn-secondary btn-sm" data-fixqueue-open="${escapeHtml(
        task.target
      )}">
         Open file
       </button>`;
    }
    if (task.action === "open_indexing") {
      return `<button type="button" class="btn btn-secondary btn-sm" data-fixqueue-indexing="${escapeHtml(
        task.target
      )}" ${projectAttr}>
         Open indexing
       </button>`;
    }
    if (
      task.action === "raise_scope" ||
      task.action === "allow_path" ||
      task.action === "review_permissions"
    ) {
      return `<button type="button" class="btn btn-secondary btn-sm" data-fixqueue-settings="permissions">
         Open settings
       </button>`;
    }
    return "";
  }

  function handleFixQueueTaskClick(event) {
    const runButton = event.target.closest("[data-fixqueue-run]");
    if (runButton) {
      const target = runButton.dataset.fixqueueRun;
      const project = runButton.dataset.fixqueueProject || null;
      if (target) {
        handleFixQueueRun(target, project);
      }
      return;
    }

    const queryButton = event.target.closest("[data-fixqueue-query]");
    if (queryButton) {
      const target = queryButton.dataset.fixqueueQuery;
      const project = queryButton.dataset.fixqueueProject || null;
      if (target) {
        handleFixQueueQuery(target, project);
      }
      return;
    }

    const indexButton = event.target.closest("[data-fixqueue-indexing]");
    if (indexButton) {
      const target = indexButton.dataset.fixqueueIndexing;
      const project = indexButton.dataset.fixqueueProject || null;
      if (target) {
        handleFixQueueIndexing(target, project);
      } else {
        handleFixQueueIndexing("", project);
      }
      return;
    }

    const settingsButton = event.target.closest("[data-fixqueue-settings]");
    if (settingsButton) {
      navigateTo("settings");
      return;
    }

    const openButton = event.target.closest("[data-fixqueue-open]");
    if (!openButton) return;
    const target = openButton.dataset.fixqueueOpen;
    if (target) {
      handleFixQueueOpen(target);
    }
  }

  function handleFixQueueIndexing(target, projectOverride = null) {
    navigateTo("indexing");
    const project = projectOverride || target;
    if (elements.indexProject) {
      elements.indexProject.value = project && project !== "unknown" ? project : "";
    }
    elements.indexPath?.focus();
  }

  async function handleFixQueueRun(target, project = null) {
    const actionId = extractRoutineIdFromTarget(target);
    if (!actionId) {
      setRoutineStatus("Cannot map Fix Queue task to a routine.", "error");
      return;
    }
    const overrides = project ? { project } : {};
    await executeRoutine(actionId, overrides);
    loadFixQueue(true);
  }

  async function handleFixQueueOpen(target) {
    try {
      await API.openFile(target);
    } catch (err) {
      console.error("Failed to open file:", err);
      alert(
        `Could not open file: ${target}\n\nYou can manually navigate to this file.`
      );
    }
  }

  async function handleFixQueueQuery(target, project = null) {
    navigateTo("ask");
    if (elements.queryInput) {
      elements.queryInput.value = target;
    }
    const filters = getAskFilters();
    if (project) {
      filters.projects = [project];
    }
    await submitAsk({ query: target, filters, showAnyway: false });
  }

  function extractRoutineIdFromTarget(target) {
    const match = target?.match(/routines\/([\w-]+)/);
    return match ? match[1] : null;
  }

  /**
   * Render library project select options.
   */
  function renderLibraryProjectOptions() {
    if (!elements.libraryProjectFilter) return;

    const options = ['<option value="">All Projects</option>'];
    state.projects.forEach((project) => {
      options.push(
        `<option value="${escapeHtml(project)}">${escapeHtml(project)}</option>`
      );
    });
    elements.libraryProjectFilter.innerHTML = options.join("");
  }

  function renderFixQueueProjectOptions() {
    if (!elements.fixQueueProjectFilter) return;
    const options = ['<option value="">All Projects</option>'];
    state.projects.forEach((project) => {
      options.push(
        `<option value="${escapeHtml(project)}">${escapeHtml(project)}</option>`
      );
    });
    elements.fixQueueProjectFilter.innerHTML = options.join("");
    if (state.fixQueueProject) {
      elements.fixQueueProjectFilter.value = state.fixQueueProject;
    }
  }

  /**
   * Load Coach Mode settings.
   */
  async function loadSettings() {
    if (!elements.settingsDefaultMode) return;

    try {
      const settings = await API.getSettings();
      state.settings = settings;
      renderSettings();
      syncCoachToggle();
    } catch (err) {
      console.error("Failed to load settings:", err);
      if (elements.settingsStatus) {
        elements.settingsStatus.textContent = "Failed to load settings.";
      }
    }
  }

  /**
   * Load permission configuration for display.
   */
  async function loadPermissions() {
    if (
      !elements.permissionsScope ||
      !elements.permissionsVaultRoot ||
      !elements.permissionsPaths ||
      !elements.permissionsConnectors ||
      state.permissionsLoading
    ) {
      return;
    }

    state.permissionsLoading = true;
    try {
      const permissions = await API.getPermissions();
      state.permissions = permissions;
      renderPermissions();
    } catch (err) {
      console.error("Failed to load permissions:", err);
      renderPermissionsError();
    } finally {
      state.permissionsLoading = false;
    }
  }

  /**
   * Render settings form values.
   */
  function renderSettings() {
    if (!state.settings || !elements.settingsDefaultMode) return;

    elements.settingsDefaultMode.value = state.settings.coach_mode_default;
    elements.settingsCooldown.value = state.settings.coach_cooldown_days;

    if (!elements.settingsProjectModes) return;

    const perProject = state.settings.per_project_mode || {};
    elements.settingsProjectModes.innerHTML = state.projects
      .map((project) => {
        const enabled = perProject[project] === "coach";
        return `
          <label class="checkbox-item">
            <input type="checkbox" data-project="${escapeHtml(project)}" ${
          enabled ? "checked" : ""
        }>
            <span>${escapeHtml(project)}</span>
          </label>
        `;
      })
      .join("");
  }

  function renderPermissions() {
    if (!state.permissions) {
      renderPermissionsError();
      return;
    }

    elements.permissionsScope.textContent = String(
      state.permissions.default_scope
    );
    elements.permissionsVaultRoot.textContent = state.permissions.vault_root;
    renderPermissionsList(
      elements.permissionsPaths,
      state.permissions.allowed_vault_paths,
      "No allowed paths configured.",
      true
    );
    renderPermissionsList(
      elements.permissionsConnectors,
      formatConnectorStatus(state.permissions.enabled_connectors),
      "No connectors configured.",
      false
    );
    updateConnectorAvailability();
  }

  function renderPermissionsError() {
    if (!elements.permissionsScope) return;
    elements.permissionsScope.textContent = "Unavailable";
    if (elements.permissionsVaultRoot) {
      elements.permissionsVaultRoot.textContent = "Unavailable";
    }
    renderPermissionsList(elements.permissionsPaths, [], "Unavailable", true);
    renderPermissionsList(
      elements.permissionsConnectors,
      [],
      "Unavailable",
      false
    );
    updateConnectorAvailability();
  }

  function renderPermissionsList(container, items, emptyMessage, useMono) {
    if (!container) return;
    if (!items || items.length === 0) {
      container.innerHTML = `<span class="pill">${escapeHtml(
        emptyMessage
      )}</span>`;
      return;
    }
    container.innerHTML = items
      .map(
        (item) =>
          `<span class="pill${useMono ? " mono" : ""}">${escapeHtml(
            String(item)
          )}</span>`
      )
      .join("");
  }

  function formatConnectorStatus(connectors) {
    if (!connectors) return [];
    return Object.entries(connectors).map(
      ([name, enabled]) => `${name}: ${enabled ? "on" : "off"}`
    );
  }

  function setConnectorStatus(element, message, type) {
    if (!element) return;
    element.textContent = message || "";
    element.classList.remove("success", "error");
    if (type === "success") {
      element.classList.add("success");
    } else if (type === "error") {
      element.classList.add("error");
    }
  }

  function updateConnectorAvailability() {
    const enabled =
      state.permissions?.enabled_connectors?.browser_saves === true;
    const scopeLevel = Number(state.permissions?.default_scope || 0);
    const scopeOk = scopeLevel >= 2;
    const available = enabled && scopeOk;
    if (elements.connectorsAvailability) {
      if (available) {
        setConnectorStatus(
          elements.connectorsAvailability,
          "Connectors are enabled.",
          "success"
        );
      } else if (!enabled) {
        setConnectorStatus(
          elements.connectorsAvailability,
          "Enable browser_saves in bob.yaml to use connectors.",
          "error"
        );
      } else {
        setConnectorStatus(
          elements.connectorsAvailability,
          "Raise permission scope to level 2 or higher to use connectors.",
          "error"
        );
      }
    }
    if (elements.connectorsBookmarksImportBtn) {
      elements.connectorsBookmarksImportBtn.disabled = !available;
    }
    if (elements.connectorsHighlightSaveBtn) {
      elements.connectorsHighlightSaveBtn.disabled = !available;
    }
  }

  /**
   * Handle saving settings.
   */
  async function handleSettingsSave(e) {
    e.preventDefault();
    if (!elements.settingsDefaultMode) return;

    const perProject = {};
    elements.settingsProjectModes
      ?.querySelectorAll('input[type="checkbox"][data-project]')
      .forEach((checkbox) => {
        const project = checkbox.dataset.project;
        perProject[project] = checkbox.checked ? "coach" : "boring";
      });

    const payload = {
      coach_mode_default: elements.settingsDefaultMode.value,
      per_project_mode: perProject,
      coach_cooldown_days: parseInt(elements.settingsCooldown.value, 10) || 7,
    };

    try {
      await API.updateSettings(payload);
      state.settings = payload;
      state.coachModeOverride = null;
      syncCoachToggle();
      if (elements.settingsStatus) {
        elements.settingsStatus.textContent = "Settings saved.";
      }
    } catch (err) {
      if (elements.settingsStatus) {
        elements.settingsStatus.textContent = "Failed to save settings.";
      }
    }
  }

  async function handleBookmarksImport(event) {
    event.preventDefault();
    if (!elements.connectorsBookmarksPath) return;

    const sourcePath = elements.connectorsBookmarksPath.value.trim();
    if (!sourcePath) {
      setConnectorStatus(
        elements.connectorsBookmarksStatus,
        "Bookmarks path is required.",
        "error"
      );
      return;
    }

    const project =
      elements.connectorsBookmarksProject?.value.trim() ||
      state.projects[0] ||
      "main";
    const language =
      elements.connectorsBookmarksLanguage?.value.trim() || "en";

    setConnectorStatus(
      elements.connectorsBookmarksStatus,
      "Importing bookmarks...",
      null
    );
    elements.connectorsBookmarksImportBtn?.setAttribute("disabled", "true");

    try {
      const response = await API.importBookmarks({
        source_path: sourcePath,
        project: project || null,
        language: language || null,
      });
      const warnings = response.warnings || [];
      const warningNote =
        warnings.length > 0 ? ` Warnings: ${warnings.join(" ")}` : "";
      setConnectorStatus(
        elements.connectorsBookmarksStatus,
        `Imported ${response.imported || 0} bookmarks.${warningNote}`,
        "success"
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to import bookmarks.";
      setConnectorStatus(elements.connectorsBookmarksStatus, message, "error");
    } finally {
      updateConnectorAvailability();
    }
  }

  async function handleHighlightSave(event) {
    event.preventDefault();
    if (!elements.connectorsHighlightText) return;

    const text = elements.connectorsHighlightText.value.trim();
    if (!text) {
      setConnectorStatus(
        elements.connectorsHighlightStatus,
        "Highlight text is required.",
        "error"
      );
      return;
    }

    const sourceUrl = elements.connectorsHighlightUrl?.value.trim() || null;
    const project =
      elements.connectorsHighlightProject?.value.trim() ||
      state.projects[0] ||
      "main";
    const language =
      elements.connectorsHighlightLanguage?.value.trim() || "en";

    setConnectorStatus(
      elements.connectorsHighlightStatus,
      "Saving highlight...",
      null
    );
    elements.connectorsHighlightSaveBtn?.setAttribute("disabled", "true");

    try {
      const response = await API.saveHighlight({
        text,
        source_url: sourceUrl,
        project: project || null,
        language: language || null,
      });
      setConnectorStatus(
        elements.connectorsHighlightStatus,
        `Highlight saved to ${response.file_path}.`,
        "success"
      );
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to save highlight.";
      setConnectorStatus(elements.connectorsHighlightStatus, message, "error");
    } finally {
      updateConnectorAvailability();
    }
  }

  /**
   * Resolve Coach Mode for current selection.
   */
  function resolveCoachMode() {
    if (state.coachModeOverride !== null) {
      return state.coachModeOverride;
    }

    const selectedProject = getSelectedProject();
    const perProject = state.settings?.per_project_mode || {};
    if (selectedProject && perProject[selectedProject]) {
      return perProject[selectedProject] === "coach";
    }

    return state.settings?.coach_mode_default === "coach";
  }

  /**
   * Sync Coach toggle with current settings.
   */
  function syncCoachToggle() {
    if (!elements.coachToggle) return;
    const enabled = resolveCoachMode();
    elements.coachToggle.checked = enabled;
    updateCoachStatus(enabled);
  }

  /**
   * Update Coach toggle status label.
   */
  function updateCoachStatus(enabled) {
    if (!elements.coachModeStatus) return;
    elements.coachModeStatus.textContent = enabled ? "On" : "Off";
    elements.coachModeStatus.classList.toggle("coach-mode-on", enabled);
    elements.coachModeStatus.setAttribute(
      "aria-label",
      enabled ? "Coach Mode: On" : "Coach Mode: Off"
    );
  }

  /**
   * Handle project filter change.
   */
  function handleProjectFilterChange() {
    if (state.coachModeOverride === null) {
      syncCoachToggle();
    }
  }

  /**
   * Handle Coach toggle change.
   */
  function handleCoachToggle(e) {
    const enabled = e.target.checked;
    state.coachModeOverride = enabled;
    updateCoachStatus(enabled);
  }

  function setIndexFeedback(message, type = "error") {
    if (!elements.indexFeedback) return;
    elements.indexFeedback.textContent = message;
    elements.indexFeedback.classList.remove("hidden");
    elements.indexFeedback.classList.toggle("error", type === "error");
    elements.indexFeedback.classList.toggle("info", type === "info");
  }

  function clearIndexFeedback() {
    if (!elements.indexFeedback) return;
    elements.indexFeedback.textContent = "";
    elements.indexFeedback.classList.add("hidden");
    elements.indexFeedback.classList.remove("error");
    elements.indexFeedback.classList.remove("info");
  }

  /**
   * Handle ask form submission.
   */
  async function handleAskSubmit(e) {
    e.preventDefault();

    const query = elements.queryInput.value.trim();
    if (!query) return;

    // Get filters
    const filters = getAskFilters();
    const finalQuery = applyDecisionStatusFilter(query);
    state.lastAsk = { query: finalQuery, filters };

    await submitAsk({ query: finalQuery, filters, showAnyway: false });
  }

  async function handleGlobalKeydown(event) {
    if (state.noteModalOpen) return;

    // Handle shortcuts modal
    if (state.shortcutsModalOpen) {
      if (event.key === "Escape" || event.key === "?") {
        event.preventDefault();
        closeShortcutsModal();
      }
      return;
    }

    const target = event.target;
    const tagName = target?.tagName || "";
    const isEditable =
      target?.isContentEditable ||
      tagName === "INPUT" ||
      tagName === "TEXTAREA" ||
      tagName === "SELECT";

    // Open shortcuts help with ?
    if (event.key === "?" && !isEditable) {
      event.preventDefault();
      openShortcutsModal();
      return;
    }

    if (event.key === "/" && !isEditable) {
      if (state.currentPage === "ask") {
        event.preventDefault();
        elements.queryInput?.focus();
      }
      return;
    }

    if (!isEditable && state.currentPage === "ask" && /^[1-9]$/.test(event.key)) {
      const index = Number.parseInt(event.key, 10) - 1;
      event.preventDefault();
      await openSourceByIndex(index);
      return;
    }

    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      if (state.currentPage !== "ask") return;
      const query = elements.queryInput?.value.trim();
      if (!query) return;
      event.preventDefault();
      const filters = getAskFilters();
      const finalQuery = applyDecisionStatusFilter(query);
      state.lastAsk = { query: finalQuery, filters };
      submitAsk({ query: finalQuery, filters, showAnyway: false });
      return;
    }

    if (event.key === "Escape" && state.currentPage === "ask") {
      if (isEditable && target !== elements.queryInput) {
        return;
      }
      resetAskState();
    }
  }

  /**
   * Submit an ask request with optional overrides.
   */
  async function submitAsk({ query, filters, showAnyway }) {
    // Show loading state
    setAskLoading(true);
    showLoadingState();

    try {
      const finalQuery = applyDecisionStatusFilter(query);
      const coachModeEnabled = elements.coachToggle?.checked ?? false;
      const response = await API.ask(
        finalQuery,
        filters,
        5,
        coachModeEnabled,
        showAnyway
      );
      state.lastAsk = { query: finalQuery, filters, response };

      if (response.footer?.not_found) {
        renderNotFoundResponse(response, finalQuery);
      } else {
        renderAnswer(response);
      }

      renderCoachSuggestions(response);
    } catch (err) {
      renderError(err.message);
    } finally {
      setAskLoading(false);
    }
  }

  /**
   * Get current ask filters.
   */
  function getAskFilters() {
    const projects = [];
    const types = [];

    document.querySelectorAll('input[name="project"]:checked').forEach((cb) => {
      projects.push(cb.value);
    });

    document.querySelectorAll('input[name="type"]:checked').forEach((cb) => {
      types.push(cb.value);
    });

    const dateAfter = document.getElementById("date-after")?.value || null;
    const dateBefore = document.getElementById("date-before")?.value || null;
    const language =
      document.getElementById("language-filter")?.value.trim() || null;

    return {
      projects: projects.length > 0 ? projects : null,
      types: types.length > 0 ? types : null,
      dateAfter,
      dateBefore,
      language,
    };
  }

  function applyDecisionStatusFilter(query) {
    const status =
      document.getElementById("decision-status-filter")?.value.trim() || "";
    if (!status) {
      return query;
    }
    if (/\bdecision:\S+/i.test(query)) {
      return query;
    }
    return `decision:${status} ${query}`.trim();
  }

  /**
   * Set loading state for ask form.
   */
  function setAskLoading(loading) {
    elements.submitBtn.disabled = loading;
    elements.submitBtn
      .querySelector(".submit-text")
      .classList.toggle("hidden", loading);
    elements.submitBtn
      .querySelector(".submit-loading")
      .classList.toggle("hidden", !loading);
  }

  function setCopyReportEnabled(enabled) {
    if (!elements.copyReportBtn) return;
    elements.copyReportBtn.disabled = !enabled;
  }

  function showCopyReportStatus(message) {
    if (!elements.copyReportStatus) return;
    elements.copyReportStatus.textContent = message;
    elements.copyReportStatus.classList.remove("hidden");
    setTimeout(() => {
      elements.copyReportStatus?.classList.add("hidden");
    }, 2000);
  }

  async function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }

    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    const success = document.execCommand("copy");
    textarea.remove();
    return success;
  }

  function buildReport(query, response) {
    const lines = [];
    lines.push(`Question: ${query}`);
    if (response.footer?.not_found) {
      lines.push(response.footer?.not_found_message || "Not found in sources.");
    } else {
      lines.push(`Answer: ${response.answer || ""}`);
    }

    lines.push("");
    lines.push("Sources:");
    const sources = response.sources || [];
    if (sources.length === 0) {
      lines.push("  None");
    } else {
      sources.forEach((source, index) => {
        const locator = formatLocator(source.locator);
        const date = source.date || "Unknown date";
        lines.push(`  ${index + 1}. [${source.file_path}] ${locator}`);
        lines.push(
          `     Date: ${date} | Confidence: ${source.date_confidence || "UNKNOWN"}`
        );
        if (source.may_be_outdated) {
          lines.push("     NOTE: This may be outdated");
        }
      });
    }

    lines.push("");
    lines.push(`Date Confidence: ${response.footer?.date_confidence || "UNKNOWN"}`);
    if (response.footer?.may_be_outdated) {
      lines.push(
        `Outdated Sources: ${response.footer?.outdated_source_count || 0}`
      );
    }

    const audit = response.audit;
    if (audit && audit.retrieved && audit.retrieved.length > 0) {
      lines.push("");
      lines.push("Audit:");
      const usedIds = (audit.used || []).map((chunk) => `#${chunk.rank}`);
      const retrievedIds = (audit.retrieved || []).map((chunk) => `#${chunk.rank}`);
      lines.push(`  Used: ${usedIds.join(", ") || "None"}`);
      lines.push(`  Retrieved: ${retrievedIds.join(", ") || "None"}`);
    }

    return lines.join("\n");
  }

  /**
   * Hide all answer states.
   */
  function hideAllStates() {
    elements.welcomeState.classList.add("hidden");
    elements.loadingState?.classList.add("hidden");
    elements.answerContent.classList.add("hidden");
    elements.notFoundState.classList.add("hidden");
    elements.errorState.classList.add("hidden");
    elements.coachSuggestions?.classList.add("hidden");
    if (elements.coachSuggestionsList) {
      elements.coachSuggestionsList.innerHTML = "";
    }
    setFeedbackVisible(false);
    setFeedbackButtonsEnabled(false);
    setFeedbackStatus("");
    setCopyReportEnabled(false);
  }

  /**
   * Show the loading state.
   */
  function showLoadingState() {
    hideAllStates();
    elements.loadingState?.classList.remove("hidden");
  }

  function resetAskState() {
    if (elements.queryInput) {
      elements.queryInput.value = "";
    }
    hideAllStates();
    elements.welcomeState.classList.remove("hidden");
    state.lastAsk = null;
  }

  async function openSourceByIndex(index) {
    const sources = state.lastAsk?.response?.sources || [];
    const source = sources[index];
    if (!source) return;

    const line = source.locator?.start_line;
    try {
      await API.openFile(source.file_path, line ? { start_line: line } : null);
    } catch (err) {
      console.error("Failed to open file:", err);
      alert(
        `Could not open file: ${source.file_path}\n\nYou can manually navigate to this file.`
      );
    }
  }

  /**
   * Handle sidebar tab switching.
   */
  function handleSidebarTabClick(event) {
    const panel = event.currentTarget?.dataset?.panel;
    if (!panel) return;
    setSidebarPanel(panel);
  }

  /**
   * Activate a sidebar panel by name.
   */
  function setSidebarPanel(panel) {
    elements.sidebarTabs?.forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.panel === panel);
    });
    if (elements.sourcesPanel) {
      elements.sourcesPanel.classList.toggle("active", panel === "sources");
    }
    if (elements.auditPanel) {
      elements.auditPanel.classList.toggle("active", panel === "audit");
    }
  }

  /**
   * Render answer with sources.
   */
  function renderAnswer(response) {
    // Render answer text with inline citations
    let answerHtml = escapeHtml(response.answer);

    // Replace [1], [2], etc. with clickable citations
    answerHtml = answerHtml.replace(/\[(\d+)\]/g, (match, num) => {
      return `<span class="citation" data-source="${num}" title="View source ${num}">${num}</span>`;
    });

    const unsupported = response.audit?.unsupported_spans || [];
    if (unsupported.length > 0) {
      const warning =
        '<div class="answer-unsupported-banner">⚠️ Unsupported text detected. See Audit for details.</div>';
      answerHtml = `${warning}<div class="answer-unsupported-text">${answerHtml}</div>`;
    }

    elements.answerText.innerHTML = answerHtml;

    // Render footer
    elements.sourceCount.textContent = response.footer.source_count;

    const confidenceValue = response.footer.date_confidence || "UNKNOWN";
    const confidenceClass = confidenceValue.toLowerCase();
    elements.dateConfidence.textContent = confidenceValue;
    elements.dateConfidence.className = `confidence-badge ${confidenceClass}`;

    // Outdated warning
    if (response.footer.may_be_outdated) {
      elements.outdatedWarningContainer.innerHTML = `
                <span class="outdated-warning">⚠️ ${response.footer.outdated_source_count} source(s) may be outdated</span>
            `;
    } else {
      elements.outdatedWarningContainer.innerHTML = "";
    }

    // Render sources
    renderSources(response.sources);
    renderAudit(response.audit);
    setFeedbackVisible(true);
    setFeedbackButtonsEnabled(true);
    setFeedbackStatus("");

    // Add citation click handlers
    document.querySelectorAll(".citation").forEach((el) => {
      el.addEventListener("click", () => {
        const sourceNum = el.dataset.source;
        const sourceCard = document.querySelector(
          `.source-card[data-source="${sourceNum}"]`
        );
        if (sourceCard) {
          sourceCard.scrollIntoView({ behavior: "smooth", block: "center" });
          sourceCard.classList.add("highlight");
          setTimeout(() => sourceCard.classList.remove("highlight"), 1000);
        }
      });
    });

    // Show answer
    elements.answerContent.classList.remove("hidden");
    setCopyReportEnabled(true);
  }

  /**
   * Render a not-found response using the standard footer.
   */
  function renderNotFoundResponse(response, query) {
    const message =
      response.footer?.not_found_message || "Not found in sources.";
    elements.answerText.textContent = `${message} Query: "${query}"`;

    elements.sourceCount.textContent = response.footer?.source_count || 0;
    elements.dateConfidence.textContent = "UNKNOWN";
    elements.dateConfidence.className = "confidence-badge unknown";
    elements.outdatedWarningContainer.innerHTML = "";

    renderSources([]);
    renderAudit(null);
    setFeedbackVisible(true);
    setFeedbackButtonsEnabled(true);
    setFeedbackStatus("");
    elements.answerContent.classList.remove("hidden");
    setCopyReportEnabled(true);
  }

  function setFeedbackVisible(visible) {
    if (!elements.answerFeedback) return;
    elements.answerFeedback.classList.toggle("hidden", !visible);
  }

  function setFeedbackButtonsEnabled(enabled) {
    if (!elements.feedbackButtons) return;
    elements.feedbackButtons
      .querySelectorAll("button")
      .forEach((button) => (button.disabled = !enabled));
  }

  function setFeedbackStatus(message, type = null) {
    if (!elements.feedbackStatus) return;
    if (!message) {
      elements.feedbackStatus.textContent = "";
      elements.feedbackStatus.classList.add("hidden");
      elements.feedbackStatus.classList.remove("error");
      return;
    }
    elements.feedbackStatus.textContent = message;
    elements.feedbackStatus.classList.remove("hidden");
    elements.feedbackStatus.classList.toggle("error", type === "error");
  }

  function getFeedbackProject() {
    const response = state.lastAsk?.response;
    const fromSource = response?.sources?.find((source) => source.project)?.project;
    if (fromSource) return fromSource;
    const fromFilters = state.lastAsk?.filters?.projects?.[0];
    if (fromFilters) return fromFilters;
    return getSelectedProject();
  }

  async function handleFeedbackClick(event) {
    const button = event.target.closest("[data-feedback]");
    if (!button) return;

    const reason = button.dataset.feedback;
    const question = state.lastAsk?.query || elements.queryInput?.value.trim();
    if (!reason || !question) return;

    const response = state.lastAsk?.response;
    const retrievedSourceIds = (response?.sources || [])
      .map((source) => source.chunk_id)
      .filter((id) => Number.isInteger(id));
    const project = getFeedbackProject();

    setFeedbackButtonsEnabled(false);
    setFeedbackStatus("Sending feedback...");

    try {
      await API.submitFeedback({
        question,
        project: project || null,
        answer_id: response?.answer_id || null,
        feedback_reason: reason,
        retrieved_source_ids: retrievedSourceIds,
      });
      setFeedbackStatus("Thanks for the feedback.");
    } catch (err) {
      console.error("Failed to send feedback:", err);
      setFeedbackStatus("Unable to send feedback.", "error");
      setFeedbackButtonsEnabled(true);
    }
  }

  /**
   * Render Coach Mode suggestions.
   */
  function buildCoachActionButton(suggestion, suggestionProject) {
    const action = suggestion.action;
    if (!action) return "";
    const target = suggestion.target || "";
    const labels = {
      run_query: "Run query",
      open_indexing: "Open indexing",
      open_health: "Open health",
      open_settings: "Open settings",
      open_file: "Open file",
    };
    const label = labels[action] || "Run action";
    const targetAttr = target
      ? `data-coach-target="${escapeHtml(target)}"`
      : "";
    let projectValue = suggestionProject || "";
    if (action === "open_indexing" && target) {
      projectValue = target;
    }
    const projectAttr = projectValue
      ? `data-coach-project="${escapeHtml(projectValue)}"`
      : "";
    return `<button type="button" class="btn btn-secondary btn-sm coach-action" data-coach-action="${escapeHtml(
      action
    )}" ${targetAttr} ${projectAttr}>
        ${label}
      </button>`;
  }

  function renderCoachSuggestions(response) {
    if (!elements.coachSuggestions || !elements.coachSuggestionsList) return;

    if (!response.coach_mode_enabled) {
      elements.coachSuggestions.classList.add("hidden");
      return;
    }

    const suggestions = response.suggestions || [];
    const selectedProject = getSelectedProject();

    if (suggestions.length === 0) {
      elements.coachSuggestionsList.innerHTML = `
        <li class="coach-suggestion-empty">
          No suggestions available.
          <button class="btn btn-secondary btn-sm" id="coach-show-anyway">
            Show anyway
          </button>
        </li>
      `;
      const showAnywayBtn = document.getElementById("coach-show-anyway");
      showAnywayBtn?.addEventListener("click", handleCoachShowAnyway);
      elements.coachSuggestions.classList.remove("hidden");
      return;
    }

    elements.coachSuggestionsList.innerHTML = suggestions
      .map((suggestion) => {
        const citations = suggestion.citations || [];
        const citationText =
          citations.length > 0
            ? `Citations: ${citations.map((c) => c.id).join(", ")}`
            : "";
        const hypothesis = suggestion.hypothesis
          ? '<span class="coach-hypothesis">Hypothesis</span>'
          : "";
        const suggestionProject = suggestion.project || selectedProject || "";
        const routineAction = suggestion.routine_action;
        const routineButton = routineAction
          ? `<button type="button" class="btn btn-primary btn-sm coach-run" data-routine="${escapeHtml(
              routineAction
            )}" data-project="${escapeHtml(suggestionProject)}">
              Run routine
            </button>`
          : "";
        const actionButton = buildCoachActionButton(
          suggestion,
          suggestionProject
        );
        return `
          <li class="coach-suggestion-item">
            <div class="coach-suggestion-text">${escapeHtml(
              suggestion.text
            )}</div>
            <div class="coach-suggestion-why">Why: ${escapeHtml(
              suggestion.why
            )}</div>
            <div class="coach-suggestion-meta">
              ${hypothesis}
              ${
                citationText
                  ? `<span class="coach-citations">${escapeHtml(
                      citationText
                    )}</span>`
                  : ""
              }
            </div>
            <div class="coach-suggestion-actions">
              ${routineButton}
              ${actionButton}
              <button class="btn btn-secondary btn-sm coach-dismiss" data-id="${
                suggestion.id
              }" data-type="${suggestion.type}" data-project="${escapeHtml(
                suggestionProject
              )}">
                Dismiss
              </button>
            </div>
          </li>
        `;
      })
      .join("");

    elements.coachSuggestions
      .querySelectorAll(".coach-dismiss")
      .forEach((btn) => {
        btn.addEventListener("click", async () => {
          const suggestionId = btn.dataset.id;
          const suggestionType = btn.dataset.type;
          const project = btn.dataset.project || null;
          try {
            await API.dismissSuggestion(suggestionId, {
              suggestion_type: suggestionType,
              project,
            });
            btn.closest(".coach-suggestion-item")?.remove();
          } catch (err) {
            console.error("Failed to dismiss suggestion:", err);
          }
        });
      });

    elements.coachSuggestions
      .querySelectorAll(".coach-run")
      .forEach((btn) => {
        btn.addEventListener("click", async () => {
          const actionId = btn.dataset.routine;
          if (!actionId) return;
          const project = btn.dataset.project || null;
          const overrides = project ? { project } : {};
          navigateTo("routines");
          await executeRoutine(actionId, overrides);
        });
      });

    elements.coachSuggestions
      .querySelectorAll(".coach-action")
      .forEach((btn) => {
        btn.addEventListener("click", async () => {
          const action = btn.dataset.coachAction;
          if (!action) return;
          const target = btn.dataset.coachTarget || "";
          const project = btn.dataset.coachProject || null;
          if (action === "run_query") {
            await handleFixQueueQuery(target, project);
            return;
          }
          if (action === "open_indexing") {
            handleFixQueueIndexing(target, project);
            return;
          }
          if (action === "open_file") {
            if (target) {
              await handleFixQueueOpen(target);
            }
            return;
          }
          if (action === "open_health") {
            navigateTo("health");
            await loadFixQueue(true);
            return;
          }
          if (action === "open_settings") {
            navigateTo("settings");
          }
        });
      });

    elements.coachSuggestions.classList.remove("hidden");
  }

  /**
   * Get the first selected project (if any).
   */
  function getSelectedProject() {
    const checked = document.querySelectorAll('input[name="project"]:checked');
    return checked.length > 0 ? checked[0].value : null;
  }

  /**
   * Handle "Show anyway" for Coach Mode.
   */
  async function handleCoachShowAnyway(e) {
    e.preventDefault();
    if (!state.lastAsk) return;
    await submitAsk({
      query: state.lastAsk.query,
      filters: state.lastAsk.filters,
      showAnyway: true,
    });
  }

  /**
   * Handle "Copy as report" action.
   */
  async function handleCopyReport() {
    if (!state.lastAsk || !state.lastAsk.response) {
      showCopyReportStatus("No report available");
      return;
    }

    const report = buildReport(state.lastAsk.query, state.lastAsk.response);
    try {
      const success = await copyToClipboard(report);
      showCopyReportStatus(success ? "Copied" : "Copy failed");
    } catch (err) {
      console.error("Failed to copy report:", err);
      showCopyReportStatus("Copy failed");
    }
  }

  /**
   * Render sources list.
   */
  function renderSources(sources) {
    if (!sources || sources.length === 0) {
      elements.sourcesList.innerHTML =
        '<div class="sources-empty"><p>No sources found.</p></div>';
      return;
    }

    elements.sourcesList.innerHTML = sources
      .map((source, index) => {
        const locatorText = formatLocator(source.locator);
        const confidence = source.date_confidence.toLowerCase();
        const date = source.date || "Unknown date";

        return `
                <div class="source-card" data-source="${index + 1}">
                    <div class="source-header">
                        <span class="source-number">${index + 1}</span>
                    </div>
                    <div class="source-file">${escapeHtml(
                      source.file_path
                    )}</div>
                    <div class="source-locator">${escapeHtml(locatorText)}</div>
                    <div class="source-meta">
                        <span class="confidence-badge ${confidence}">${
          source.date_confidence
        }</span>
                        <span>${escapeHtml(date)}</span>
                    </div>
                    ${
                      source.may_be_outdated
                        ? '<div class="source-outdated">⚠️ May be outdated</div>'
                        : ""
                    }
                    <button class="source-open-btn" data-path="${escapeHtml(
                      source.file_path
                    )}" data-line="${source.locator?.start_line || ""}">
                        Open in Editor
                    </button>
                </div>
            `;
      })
      .join("");

    // Add open button handlers
    elements.sourcesList.querySelectorAll(".source-open-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const path = btn.dataset.path;
        const line = btn.dataset.line ? parseInt(btn.dataset.line) : null;

        try {
          await API.openFile(path, line ? { start_line: line } : null);
        } catch (err) {
          console.error("Failed to open file:", err);
          alert(
            `Could not open file: ${path}\n\nYou can manually navigate to this file.`
          );
        }
      });
    });
  }

  /**
   * Render audit payload for retrieved vs used chunks.
   */
  function renderAudit(audit) {
    if (!elements.auditList) return;
    if (!audit || !audit.retrieved || audit.retrieved.length === 0) {
      elements.auditList.innerHTML =
        '<div class="sources-empty"><p>No audit data available.</p></div>';
      return;
    }

    const used = audit.used || [];
    const retrieved = audit.retrieved || [];
    const unsupported = audit.unsupported_spans || [];

    const renderChunk = (chunk, isUsed) => {
      const locator = formatLocator(chunk.locator);
      const score = typeof chunk.score === "number" ? chunk.score.toFixed(3) : "-";
      return `
        <div class="audit-card ${isUsed ? "used" : ""}">
          <div class="audit-card-header">
            <span class="audit-rank">#${chunk.rank}</span>
            <span>Source ${chunk.source_id}</span>
            <span>Score ${score}</span>
          </div>
          <div class="audit-path">${escapeHtml(chunk.file_path)}</div>
          <div class="audit-locator">${escapeHtml(locator)}</div>
          <div class="audit-snippet">${escapeHtml(chunk.snippet)}</div>
        </div>
      `;
    };

    const renderSection = (title, chunks, markUsed) => {
      const body =
        chunks.length === 0
          ? '<div class="sources-empty"><p>No chunks in this section.</p></div>'
          : chunks.map((chunk) => renderChunk(chunk, markUsed)).join("");
      return `
        <div class="audit-section">
          <div class="audit-section-title">${escapeHtml(title)}</div>
          ${body}
        </div>
      `;
    };

    const sections = [
      renderSection(`Used in Answer (${used.length})`, used, true),
      renderSection(`Retrieved (${retrieved.length})`, retrieved, false),
    ];

    if (unsupported.length > 0) {
      const unsupportedCards = unsupported
        .map(
          (span) => `
            <div class="audit-unsupported">
              <div><strong>Unsupported:</strong> ${escapeHtml(span.text)}</div>
              <div>${escapeHtml(span.reason)}</div>
            </div>
          `
        )
        .join("");
      sections.push(`
        <div class="audit-section">
          <div class="audit-section-title">Unsupported Spans</div>
          ${unsupportedCards}
        </div>
      `);
    }

    elements.auditList.innerHTML = sections.join("");
  }

  /**
   * Format locator for display.
   */
  function formatLocator(locator) {
    if (!locator) return "";

    switch (locator.type) {
      case "heading": {
        const heading = locator.heading || "";
        const lines =
          locator.start_line && locator.end_line
            ? ` (lines ${locator.start_line}-${locator.end_line})`
            : "";
        const gitLabel = locator.git_file
          ? `${locator.git_file}${locator.git_commit ? `@${locator.git_commit}` : ""} `
          : "";
        return `${gitLabel}heading: "${heading}"${lines}`;
      }
      case "page":
        return `page ${locator.page}/${locator.total_pages}`;
      case "sheet":
        return `sheet: "${locator.sheet_name}" (${locator.row_count} rows)`;
      case "paragraph":
        return `paragraph ${locator.paragraph_index}${
          locator.parent_heading ? ` under "${locator.parent_heading}"` : ""
        }`;
      case "section":
        return `section: "${locator.section || ""}"`;
      case "line": {
        const start = locator.start_line || locator.line || "";
        const end = locator.end_line || "";
        const lineLabel = end ? `${start}-${end}` : `${start}`;
        const gitLabel = locator.git_file
          ? `${locator.git_file}${locator.git_commit ? `@${locator.git_commit}` : ""} `
          : "";
        return `${gitLabel}lines ${lineLabel}`.trim();
      }
      default:
        return locator.type || "";
    }
  }

  /**
   * Render not found state.
   */
  function renderNotFound(query) {
    elements.notFoundQuery.textContent = `"${query}"`;
    elements.notFoundState.classList.remove("hidden");
    elements.sourcesList.innerHTML =
      '<div class="sources-empty"><p>No sources found.</p></div>';
    renderAudit(null);
    setFeedbackVisible(false);
    setFeedbackButtonsEnabled(false);
    setFeedbackStatus("");
    setCopyReportEnabled(false);
  }

  /**
   * Render error state.
   */
  function renderError(message) {
    elements.errorMessage.textContent = message;
    elements.errorState.classList.remove("hidden");
    renderSources([]);
    renderAudit(null);
    setFeedbackVisible(false);
    setFeedbackButtonsEnabled(false);
    setFeedbackStatus("");
    setCopyReportEnabled(false);
  }

  /**
   * Load documents for library page.
   */
  async function loadDocuments(append = false) {
    if (!append) {
      state.documentPage = 1;
      elements.documentList.innerHTML =
        '<div class="loading-placeholder loading" role="status" aria-busy="true" aria-label="Loading documents"></div>';
    }

    const project = elements.libraryProjectFilter?.value || null;
    const type = elements.libraryTypeFilter?.value || null;

    try {
      const response = await API.getDocuments({
        project,
        sourceType: type,
        page: state.documentPage,
        pageSize: state.documentPageSize,
      });

      const newDocuments = response.documents || [];
      state.documents = append
        ? [...state.documents, ...newDocuments]
        : newDocuments;

      renderDocuments(append, newDocuments);

      // Update count
      elements.documentCount.textContent = `${state.documents.length} of ${response.total} documents`;

      // Show/hide load more button
      const hasMore = state.documents.length < response.total;
      elements.loadMoreContainer.classList.toggle("hidden", !hasMore);
    } catch (err) {
      console.error("Failed to load documents:", err);
      elements.documentList.innerHTML =
        '<div class="loading-placeholder">Failed to load documents</div>';
    }
  }

  /**
   * Render documents list.
   */
  function renderDocuments(append = false, newDocuments = null) {
    if (!append) {
      elements.documentList.innerHTML = "";
      if (state.documents.length === 0) {
        elements.documentList.innerHTML = `
          <div class="library-empty-state">
            <div class="library-empty-icon">📚</div>
            <h3>Your library is empty</h3>
            <p>Index some documents to get started. Point B.O.B at your notes, docs, or recipes.</p>
            <a href="#indexing" class="btn btn-primary">Go to Indexing</a>
          </div>
        `;
        return;
      }
    }

    const docsToRender = append ? newDocuments || [] : state.documents;
    if (append && docsToRender.length === 0) {
      return;
    }

    const html = docsToRender
      .map((doc) => {
        const icon = getDocumentIcon(doc.source_type);
        const date =
          doc.source_date || doc.updated_at || doc.created_at || "Unknown";

        return `
                <div class="document-card">
                    <div class="document-header">
                        <span class="document-icon">${icon}</span>
                        <div class="document-info">
                            <div class="document-name">${escapeHtml(
                              doc.source_path
                            )}</div>
                            <div class="document-meta">
                                <span>Project: ${escapeHtml(doc.project)}</span>
                                <span>Type: ${escapeHtml(doc.source_type)}</span>
                                <span>${escapeHtml(String(date))}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
      })
      .join("");

    if (append) {
      elements.documentList.insertAdjacentHTML("beforeend", html);
    } else {
      elements.documentList.innerHTML = html;
    }
  }

  /**
   * Get icon for document type.
   */
  function getDocumentIcon(type) {
    const icons = {
      markdown: "📄",
      pdf: "📕",
      word: "📝",
      excel: "📊",
      recipe: "📋",
      git: "🧩",
    };
    return icons[type] || "📄";
  }

  /**
   * Handle library filter change.
   */
  function handleLibraryFilterChange() {
    loadDocuments();
  }

  /**
   * Load more documents.
   */
  function loadMoreDocuments() {
    state.documentPage += 1;
    loadDocuments(true);
  }

  /**
   * Handle index form submission.
   */
  async function handleIndexSubmit(e) {
    e.preventDefault();

    const path = elements.indexPath.value.trim();
    const project = elements.indexProject.value.trim();

    if (!path || !project) {
      setIndexFeedback("Please enter both a path and project name.", "error");
      return;
    }

    clearIndexFeedback();

    // Disable form
    elements.startIndexBtn.disabled = true;
    elements.startIndexBtn.textContent = "Starting...";

    // Hide previous results
    elements.jobProgress?.classList.add("hidden");
    elements.jobResult?.classList.add("hidden");
    elements.jobErrors?.classList.add("hidden");

    try {
      const response = await API.startIndex(path, project);
      state.currentJobId = response.job_id;
      storeCurrentJobId(response.job_id);

      // Show progress
      elements.jobProgress.classList.remove("hidden");
      elements.progressBar.style.width = "0%";
      elements.progressStatus.textContent = getJobStatusLabel(response.status);
      elements.progressPercent.textContent = "0%";
      renderJobMetadata(response);
      updateJobProgress(response);

      // Start polling
      startJobPolling();
    } catch (err) {
      console.error("Failed to start indexing:", err);
      const detail =
        err instanceof APIError && err.data?.error?.message
          ? err.data.error.message
          : err.message || "Failed to start indexing.";
      setIndexFeedback(detail, "error");
      elements.startIndexBtn.disabled = false;
      elements.startIndexBtn.textContent = "Start Indexing";
    }
  }

  async function handleOpenPath(e) {
    e.preventDefault();
    const path = elements.indexPath.value.trim();

    if (!path) {
      setIndexFeedback("Please enter a path before opening it in Explorer.", "error");
      return;
    }

    try {
      const response = await API.openFile(path);
      if (response.success) {
        setIndexFeedback(`Opened ${path}`, "info");
      } else {
        setIndexFeedback(response.message, "error");
      }
    } catch (err) {
      console.error("Failed to open path:", err);
      const detail =
        err instanceof APIError && err.message
          ? err.message
          : "Could not open the selected path.";
      setIndexFeedback(detail, "error");
    }
  }

  /**
   * Start polling for job status.
   */
  function startJobPolling() {
    if (state.jobPollInterval) {
      clearInterval(state.jobPollInterval);
    }

    state.jobPollInterval = setInterval(async () => {
      try {
        const job = await API.getIndexJob(state.currentJobId);
        updateJobProgress(job);

        if (job.status === "completed" || job.status === "failed") {
          stopJobPolling();
          showJobResult(job);
        }
      } catch (err) {
        console.error("Failed to get job status:", err);
        stopJobPolling();
      }
    }, 1000);
  }

  /**
   * Stop polling for job status.
   */
  function stopJobPolling() {
    if (state.jobPollInterval) {
      clearInterval(state.jobPollInterval);
      state.jobPollInterval = null;
    }
    elements.startIndexBtn.disabled = false;
    elements.startIndexBtn.textContent = "Start Indexing";
  }

  /**
   * Update job progress display.
   */
  function updateJobProgress(job) {
    const progress = job.progress || {};
    elements.jobProgress?.classList.remove("hidden");
    renderJobMetadata(job);

    const percent = progress.percent ?? 0;
    elements.progressBar.style.width = `${percent}%`;
    elements.progressPercent.textContent = `${Math.round(percent)}%`;
    elements.progressStatus.textContent = getJobStatusLabel(job.status);

    if (elements.jobTotalFiles) {
      elements.jobTotalFiles.textContent = progress.total_files ?? 0;
    }
    if (elements.jobProcessedFiles) {
      elements.jobProcessedFiles.textContent = progress.processed_files ?? 0;
    }

    const currentFile = progress.current_file;
    elements.progressFiles.textContent = currentFile
      ? `Processing: ${escapeHtml(currentFile)}`
      : "Preparing files…";
  }

  /**
   * Show job result.
   */
  function showJobResult(job) {
    elements.jobProgress.classList.add("hidden");
    elements.jobResult.classList.remove("hidden");

    elements.resultFiles.textContent = job.progress?.processed_files ?? 0;
    elements.resultDocuments.textContent = job.stats?.documents ?? 0;
    elements.resultChunks.textContent = job.stats?.chunks ?? 0;

    if (job.errors && job.errors.length > 0) {
      elements.jobErrors.classList.remove("hidden");
      elements.jobErrors.innerHTML = `
                <strong>Errors:</strong>
                <ul>${job.errors
                  .map(
                    (error) =>
                      `<li><strong>${escapeHtml(error.file)}</strong>: ${escapeHtml(
                        error.error
                      )}</li>`
                  )
                  .join("")}</ul>
            `;
    } else {
      elements.jobErrors.classList.add("hidden");
    }

    recordJobHistory(job);
    clearStoredJobId();
    state.currentJobId = null;

    // Refresh projects list
    loadProjects();

    // Refresh health metrics so Fix Queue reflects new indexing
    state.fixQueue = null;
    state.fixQueueProjectLoaded = null;
    if (state.currentPage === "health") {
      loadFixQueue(true);
    }
  }

  /**
   * Update metadata labels for the current job.
   */
  function renderJobMetadata(job) {
    if (elements.jobPath) {
      elements.jobPath.textContent = job.path || "—";
    }
    if (elements.jobProject) {
      elements.jobProject.textContent = job.project || "—";
    }
    if (elements.jobStarted) {
      elements.jobStarted.textContent = formatDateTime(job.started_at);
    }
  }

  /**
   * Format an ISO timestamp for display.
   */
  function formatDateTime(value) {
    if (!value) {
      return "—";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value;
    }
    return parsed.toLocaleString();
  }

  /**
   * Map job status codes to human-friendly labels.
   */
  function getJobStatusLabel(status) {
    switch (status) {
      case "started":
        return "Preparing files…";
      case "running":
        return "Indexing files…";
      case "completed":
        return "Completed";
      case "failed":
        return "Failed";
      default:
        return status ? status.charAt(0).toUpperCase() + status.slice(1) : "Unknown";
    }
  }

  function getStoredJobId() {
    try {
      return localStorage.getItem(JOB_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function storeCurrentJobId(jobId) {
    try {
      localStorage.setItem(JOB_STORAGE_KEY, jobId);
    } catch {
      // ignore
    }
  }

  function clearStoredJobId() {
    try {
      localStorage.removeItem(JOB_STORAGE_KEY);
    } catch {
      // ignore
    }
  }

  async function restoreSavedJob() {
    const jobId = getStoredJobId();
    if (!jobId) {
      return;
    }
    try {
      const job = await API.getIndexJob(jobId);
      state.currentJobId = job.job_id;
      elements.jobProgress?.classList.remove("hidden");
      updateJobProgress(job);
      if (job.status === "running" || job.status === "started") {
        startJobPolling();
      } else {
        showJobResult(job);
      }
    } catch (err) {
      console.warn("Unable to resume indexing job:", err);
      clearStoredJobId();
    }
  }

  function getJobHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  function persistJobHistory(history) {
    try {
      localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
    } catch {
      // ignore
    }
  }

  function recordJobHistory(job) {
    const history = getJobHistory();
    const entry = {
      jobId: job.job_id,
      path: job.path || "—",
      project: job.project || "—",
      status: job.status,
      startedAt: job.started_at,
      completedAt: job.completed_at,
      filesProcessed: job.progress?.processed_files ?? 0,
      totalFiles: job.progress?.total_files ?? 0,
      documents: job.stats?.documents ?? 0,
      chunks: job.stats?.chunks ?? 0,
      errors: job.errors?.length ?? 0,
    };

    const filtered = history.filter((item) => item.jobId !== entry.jobId);
    const updated = [entry, ...filtered].slice(0, HISTORY_LIMIT);
    persistJobHistory(updated);
    renderJobHistory(updated);
  }

  function updateLastSummary(entry) {
    if (!elements.lastIndexSummary) return;
    if (!entry) {
      elements.lastIndexSummary.textContent =
        "No indexing activity recorded yet. Once you run a job, results will surface here.";
      return;
    }
    const statusText = entry.status === "failed" ? "Last run failed" : "Last run completed";
    elements.lastIndexSummary.textContent = `${statusText} on ${formatDateTime(
      entry.completedAt || entry.startedAt
    )} • ${entry.path} (project ${entry.project}, ${entry.filesProcessed}/${entry.totalFiles} files).`;
  }

  function renderJobHistory(history = getJobHistory()) {
    if (!elements.jobHistoryList) return;

    if (!history || history.length === 0) {
      elements.jobHistoryList.innerHTML =
        '<div class="history-empty">Recent jobs will appear here along with stats and errors.</div>';
      updateLastSummary(null);
      return;
    }

    elements.jobHistoryList.innerHTML = history
      .map((entry) => {
        const icon = entry.status === "failed" ? "⚠️" : "✅";
        return `
          <div class="history-card">
            <div class="history-row">
              <span class="history-status">${icon}</span>
              <span>${formatDateTime(entry.completedAt || entry.startedAt)}</span>
            </div>
            <div class="history-meta">${escapeHtml(entry.path)}</div>
            <div class="history-stats">
              <span>${entry.filesProcessed}/${entry.totalFiles} files</span>
              <span>${entry.documents} docs</span>
              <span>${entry.chunks} chunks</span>
              <span>${entry.errors} errors</span>
            </div>
          </div>
        `;
      })
      .join("");

    updateLastSummary(history[0]);
  }

  function handleClearHistory() {
    persistJobHistory([]);
    renderJobHistory([]);
    setIndexFeedback("Index history cleared.", "info");
  }
  /**
   * Escape HTML to prevent XSS.
   */
  function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  // Initialize on DOM ready
  document.addEventListener("DOMContentLoaded", init);
})();
