/**
 * B.O.B Main Application
 * Handles UI interactions and state management.
 */

(function () {
  "use strict";

  // State
  const state = {
    currentPage: "ask",
    projects: [],
    documents: [],
    documentOffset: 0,
    documentLimit: 20,
    currentJobId: null,
    jobPollInterval: null,
  };

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
    elements.notFoundState = document.getElementById("not-found-state");
    elements.notFoundQuery = document.getElementById("not-found-query");
    elements.errorState = document.getElementById("error-state");
    elements.errorMessage = document.getElementById("error-message");
    elements.sourcesList = document.getElementById("sources-list");

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
    elements.indexProject = document.getElementById("index-project");
    elements.startIndexBtn = document.getElementById("start-index-btn");
    elements.jobProgress = document.getElementById("job-progress");
    elements.progressBar = document.getElementById("progress-bar");
    elements.progressStatus = document.getElementById("progress-status");
    elements.progressPercent = document.getElementById("progress-percent");
    elements.progressFiles = document.getElementById("progress-files");
    elements.jobResult = document.getElementById("job-result");
    elements.resultFiles = document.getElementById("result-files");
    elements.resultChunks = document.getElementById("result-chunks");
    elements.jobErrors = document.getElementById("job-errors");
  }

  /**
   * Set up event listeners.
   */
  function setupEventListeners() {
    // Ask form
    elements.askForm.addEventListener("submit", handleAskSubmit);

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
  }

  /**
   * Load projects from API.
   */
  async function loadProjects() {
    try {
      const response = await API.getProjects();
      state.projects = response.projects || [];
      renderProjectFilters();
      renderLibraryProjectOptions();
    } catch (err) {
      console.error("Failed to load projects:", err);
      elements.projectFilters.innerHTML =
        '<div class="loading-placeholder">Failed to load</div>';
    }
  }

  /**
   * Render project filter checkboxes.
   */
  function renderProjectFilters() {
    if (state.projects.length === 0) {
      elements.projectFilters.innerHTML =
        '<div class="loading-placeholder">No projects indexed</div>';
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

  /**
   * Handle ask form submission.
   */
  async function handleAskSubmit(e) {
    e.preventDefault();

    const query = elements.queryInput.value.trim();
    if (!query) return;

    // Get filters
    const filters = getAskFilters();

    // Show loading state
    setAskLoading(true);
    hideAllStates();

    try {
      const response = await API.ask(query, filters);

      if (response.sources && response.sources.length > 0) {
        renderAnswer(response);
      } else {
        renderNotFound(query);
      }
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

    return {
      projects: projects.length > 0 ? projects : null,
      types: types.length > 0 ? types : null,
      dateAfter,
      dateBefore,
    };
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

  /**
   * Hide all answer states.
   */
  function hideAllStates() {
    elements.welcomeState.classList.add("hidden");
    elements.answerContent.classList.add("hidden");
    elements.notFoundState.classList.add("hidden");
    elements.errorState.classList.add("hidden");
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

    elements.answerText.innerHTML = answerHtml;

    // Render footer
    elements.sourceCount.textContent = response.footer.source_count;

    const confidence = response.footer.date_confidence.toLowerCase();
    elements.dateConfidence.textContent = response.footer.date_confidence;
    elements.dateConfidence.className = `confidence-badge ${confidence}`;

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
   * Format locator for display.
   */
  function formatLocator(locator) {
    if (!locator) return "";

    switch (locator.type) {
      case "heading":
        return `heading: "${locator.heading}" (lines ${locator.start_line}-${locator.end_line})`;
      case "page":
        return `page ${locator.page}/${locator.total_pages}`;
      case "sheet":
        return `sheet: "${locator.sheet_name}" (${locator.row_count} rows)`;
      case "paragraph":
        return `paragraph ${locator.paragraph_index}${
          locator.parent_heading ? ` under "${locator.parent_heading}"` : ""
        }`;
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
  }

  /**
   * Render error state.
   */
  function renderError(message) {
    elements.errorMessage.textContent = message;
    elements.errorState.classList.remove("hidden");
  }

  /**
   * Load documents for library page.
   */
  async function loadDocuments(append = false) {
    if (!append) {
      state.documentOffset = 0;
      elements.documentList.innerHTML =
        '<div class="loading-placeholder">Loading documents...</div>';
    }

    const project = elements.libraryProjectFilter?.value || null;
    const type = elements.libraryTypeFilter?.value || null;

    try {
      const response = await API.getDocuments({
        project,
        type,
        limit: state.documentLimit,
        offset: state.documentOffset,
      });

      state.documents = append
        ? [...state.documents, ...response.documents]
        : response.documents;

      renderDocuments(append);

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
  function renderDocuments(append = false) {
    if (!append) {
      elements.documentList.innerHTML = "";
    }

    if (state.documents.length === 0) {
      elements.documentList.innerHTML =
        '<div class="loading-placeholder">No documents indexed yet.</div>';
      return;
    }

    const html = state.documents
      .slice(append ? state.documentOffset : 0)
      .map((doc) => {
        const icon = getDocumentIcon(doc.file_type);
        const date = doc.source_date || doc.indexed_at || "Unknown";

        return `
                <div class="document-card">
                    <div class="document-header">
                        <span class="document-icon">${icon}</span>
                        <div class="document-info">
                            <div class="document-name">${escapeHtml(
                              doc.file_path
                            )}</div>
                            <div class="document-meta">
                                <span>Project: ${escapeHtml(doc.project)}</span>
                                <span>${doc.chunk_count || 0} chunks</span>
                                <span>${escapeHtml(date)}</span>
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
      docx: "📝",
      xlsx: "📊",
      yaml: "📋",
      json: "📋",
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
    state.documentOffset += state.documentLimit;
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
      alert("Please enter both a path and project name.");
      return;
    }

    // Disable form
    elements.startIndexBtn.disabled = true;
    elements.startIndexBtn.textContent = "Starting...";

    // Hide previous results
    elements.jobProgress.classList.add("hidden");
    elements.jobResult.classList.add("hidden");

    try {
      const response = await API.startIndex(path, project);
      state.currentJobId = response.job_id;

      // Show progress
      elements.jobProgress.classList.remove("hidden");
      elements.progressBar.style.width = "0%";
      elements.progressStatus.textContent = "Starting...";
      elements.progressPercent.textContent = "0%";

      // Start polling
      startJobPolling();
    } catch (err) {
      console.error("Failed to start indexing:", err);
      alert(`Failed to start indexing: ${err.message}`);
      elements.startIndexBtn.disabled = false;
      elements.startIndexBtn.textContent = "Start Indexing";
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
    const progress = job.progress || 0;
    elements.progressBar.style.width = `${progress}%`;
    elements.progressPercent.textContent = `${Math.round(progress)}%`;
    elements.progressStatus.textContent = job.status_message || job.status;

    if (job.current_file) {
      elements.progressFiles.textContent = `Processing: ${job.current_file}`;
    }
  }

  /**
   * Show job result.
   */
  function showJobResult(job) {
    elements.jobProgress.classList.add("hidden");
    elements.jobResult.classList.remove("hidden");

    elements.resultFiles.textContent = job.files_processed || 0;
    elements.resultChunks.textContent = job.chunks_created || 0;

    if (job.errors && job.errors.length > 0) {
      elements.jobErrors.classList.remove("hidden");
      elements.jobErrors.innerHTML = `
                <strong>Errors:</strong>
                <ul>${job.errors
                  .map((e) => `<li>${escapeHtml(e)}</li>`)
                  .join("")}</ul>
            `;
    } else {
      elements.jobErrors.classList.add("hidden");
    }

    // Refresh projects list
    loadProjects();
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
