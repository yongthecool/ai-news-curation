document.addEventListener("DOMContentLoaded", () => {
  const keywordInput = document.getElementById("input-keyword");
  const filterPromptInput = document.getElementById("input-filter-prompt");
  const submitBtn = document.getElementById("btn-submit-curate");
  const loadingBox = document.getElementById("loading-state-box");
  const loadingStepText = document.getElementById("loading-step-text");
  const resultsContainer = document.getElementById("results-container");
  const alertContainer = document.getElementById("dynamic-alert-container");

  // Preset filter pills click event
  const presetPills = document.querySelectorAll(".preset-pill");
  presetPills.forEach(pill => {
    pill.addEventListener("click", () => {
      const promptText = pill.getAttribute("data-prompt");
      if (promptText && filterPromptInput) {
        filterPromptInput.value = promptText;
        filterPromptInput.focus();
      }
    });
  });

  // Helper: Get CSRF Token
  function getCsrfToken() {
    const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
    return csrfInput ? csrfInput.value : "";
  }

  // Helper: Run curation request via fetch AJAX
  async function executeCuration() {
    const keyword = keywordInput.value.trim();
    const filterPrompt = filterPromptInput.value.trim();

    if (!keyword) {
      alert("검색 키워드를 입력해 주세요.");
      keywordInput.focus();
      return;
    }

    if (!filterPrompt) {
      alert("AI 선별 프롬프트를 입력해 주세요.");
      filterPromptInput.focus();
      return;
    }

    // UI State: Loading on
    if (alertContainer) alertContainer.innerHTML = "";
    if (loadingBox) loadingBox.style.display = "block";
    if (resultsContainer) resultsContainer.style.opacity = "0.2";

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <span class="btn-content">
          <svg style="animation: spin 1s linear infinite; width: 1.25rem; height: 1.25rem; display: inline-block;" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="12" cy="12" r="10" stroke-width="4" stroke="currentColor" stroke-dasharray="32" stroke-linecap="round"></circle>
          </svg>
          <span>AI 큐레이션 및 요약 생성 중...</span>
        </span>
      `;
    }

    // Progress animation steps
    let step = 0;
    const steps = [
      "실시간 최신 기사 20건을 수집하고 있습니다...",
      "AI가 필터링 기준에 맞춰 20개 기사를 다각도 심층 분석 중입니다...",
      "최적의 기사 3개 엄선 및 본문 3줄 핵심 요약을 작성하고 있습니다..."
    ];

    if (loadingStepText) loadingStepText.textContent = steps[0];

    const stepInterval = setInterval(() => {
      step++;
      if (step < steps.length && loadingStepText) {
        loadingStepText.textContent = steps[step];
      }
    }, 2800);

    try {
      const response = await fetch("/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
          keyword: keyword,
          filter_prompt: filterPrompt
        }),
      });

      clearInterval(stepInterval);
      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "처리 중 오류가 발생했습니다.");
      }

      // Render results cleanly (without any technical/API messages)
      renderResults(data);

      if (resultsContainer) {
        resultsContainer.style.opacity = "1";
        resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
      }

    } catch (err) {
      clearInterval(stepInterval);
      showErrorAlert(err.message);
      if (resultsContainer) resultsContainer.style.opacity = "1";
    } finally {
      if (loadingBox) loadingBox.style.display = "none";
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `
          <span class="btn-glow"></span>
          <span class="btn-content">
            <svg class="btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
            </svg>
            <span>기사 20건 수집 & AI TOP 3 큐레이션 시작</span>
          </span>
        `;
      }
    }
  }

  // Render HTML for results
  function renderResults(data) {
    if (!resultsContainer) return;

    let cardsHtml = "";
    data.curated_articles.forEach((article, index) => {
      const rank = index + 1;
      const rankClass = `rank-${rank}`;
      const bestBadge = rank === 1 ? `<span class="rank-crown">BEST PICK</span>` : "";

      let summaryItems = "";
      if (article.summary_points && article.summary_points.length > 0) {
        summaryItems = article.summary_points.map((pt, i) => `
          <li class="summary-step-item">
            <span class="step-num">${i + 1}</span>
            <span class="step-text">${escapeHtml(pt)}</span>
          </li>
        `).join("");
      } else {
        summaryItems = `
          <li class="summary-step-item">
            <span class="step-num">1</span>
            <span class="step-text">${escapeHtml(article.description || "기사 원문을 참조해 주시기 바랍니다.")}</span>
          </li>
        `;
      }

      let tagsHtml = "";
      if (article.keywords && article.keywords.length > 0) {
        tagsHtml = article.keywords.map(kw => `<span class="meta-tag">#${escapeHtml(kw)}</span>`).join("");
      }

      let curatorTakeHtml = "";
      if (article.curator_take) {
        curatorTakeHtml = `
          <div class="editor-take">
            <strong>시사점:</strong> ${escapeHtml(article.curator_take)}
          </div>
        `;
      }

      cardsHtml += `
        <article class="curated-card ${rankClass}">
          <div class="card-header">
            <div class="rank-indicator ${rankClass}">
              <span class="rank-num">TOP #${rank}</span>
              ${bestBadge}
            </div>
            <div class="card-timestamp">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              <span>${escapeHtml(article.pub_date || "")}</span>
            </div>
          </div>

          <h3 class="card-title">
            <a href="${escapeHtml(article.link)}" target="_blank" rel="noopener noreferrer">
              ${escapeHtml(article.title)}
            </a>
          </h3>

          <div class="curator-insight-box">
            <div class="insight-label">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
              </svg>
              <span>에디터 선정 근거</span>
            </div>
            <p class="insight-text">${escapeHtml(article.selection_reason)}</p>
            ${curatorTakeHtml}
          </div>

          <div class="summary-section">
            <div class="summary-title">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="8" y1="6" x2="21" y2="6"></line>
                <line x1="8" y1="12" x2="21" y2="12"></line>
                <line x1="8" y1="18" x2="21" y2="18"></line>
                <line x1="3" y1="6" x2="3.01" y2="6"></line>
                <line x1="3" y1="12" x2="3.01" y2="12"></line>
                <line x1="3" y1="18" x2="3.01" y2="18"></line>
              </svg>
              <span>핵심 3줄 요약</span>
            </div>
            <ol class="summary-steps">
              ${summaryItems}
            </ol>
          </div>

          <div class="card-footer">
            <div class="keyword-tags">
              ${tagsHtml}
            </div>
            <a href="${escapeHtml(article.link)}" target="_blank" rel="noopener noreferrer" class="read-original-btn">
              <span>기사 전문 보기</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="7" y1="17" x2="17" y2="7"></line>
                <polyline points="7 7 17 7 17 17"></polyline>
              </svg>
            </a>
          </div>
        </article>
      `;
    });

    let rawListHtml = "";
    if (data.all_articles && data.all_articles.length > 0) {
      const selectedIds = new Set(data.curated_articles.map(a => a.id));

      const itemsHtml = data.all_articles.map(item => {
        const isSel = selectedIds.has(item.id);
        const selBadge = isSel ? `<span class="top-selected-badge">⭐ TOP 선정</span>` : "";

        return `
          <div class="raw-row-item">
            <span class="raw-number">${item.id}</span>
            <div class="raw-main">
              <a href="${escapeHtml(item.link)}" target="_blank" rel="noopener noreferrer" class="raw-link">${escapeHtml(item.title)}</a>
              ${selBadge}
            </div>
          </div>
        `;
      }).join("");

      rawListHtml = `
        <div class="raw-section" id="accordion-20-section">
          <button type="button" class="raw-accordion-trigger" id="accordion-20-header">
            <div class="raw-trigger-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
              </svg>
              <span>분석 대상 전체 기사 목록</span>
              <span class="raw-count-chip">${data.all_articles.length}건</span>
            </div>
            <span class="accordion-arrow" id="accordion-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </span>
          </button>
          <div class="raw-accordion-body" id="accordion-20-content">
            <p class="raw-intro">
              아래 전체 기사 ${data.all_articles.length}건을 바탕으로 AI가 심층 분석하여 위의 TOP 3 기사를 선정하였습니다.
            </p>
            <div class="raw-list-grid">
              ${itemsHtml}
            </div>
          </div>
        </div>
      `;
    }

    resultsContainer.innerHTML = `
      <section class="results-header-bar">
        <div class="results-title-group">
          <div class="results-badge">CURATED SELECTION</div>
          <h2 class="results-main-title">
            <span>"${escapeHtml(data.keyword)}"</span> 관련 AI 엄선 TOP 3 리포트
          </h2>
          <p class="results-sub">
            수집된 20개 기사 중 지정하신 기준에 가장 부합하는 핵심 기사 3건을 엄선하여 브리핑합니다.
          </p>
        </div>
      </section>

      <div class="curated-deck">
        ${cardsHtml}
      </div>

      ${rawListHtml}
    `;

    // Rebind accordion
    bindAccordion();
  }

  // Accordion event
  function bindAccordion() {
    const trigger = document.getElementById("accordion-20-header");
    const body = document.getElementById("accordion-20-content");

    if (trigger && body) {
      trigger.addEventListener("click", () => {
        const isOpen = body.classList.contains("open");
        if (isOpen) {
          body.classList.remove("open");
          trigger.classList.remove("active");
        } else {
          body.classList.add("open");
          trigger.classList.add("active");
        }
      });
    }
  }

  // Show error alert
  function showErrorAlert(message) {
    if (!alertContainer) return;

    alertContainer.innerHTML = `
      <div class="luxury-alert alert-error" id="alert-error-message">
        <div class="alert-icon-wrap">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
        <div class="alert-content">
          <strong>안내:</strong> ${escapeHtml(message)}
        </div>
      </div>
    `;

    alertContainer.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Helper escape HTML
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Bind submit button
  if (submitBtn) {
    submitBtn.addEventListener("click", () => {
      executeCuration();
    });
  }

  // Initial binding for accordion if already rendered
  bindAccordion();
});
