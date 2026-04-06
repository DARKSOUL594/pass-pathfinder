const bodyPage = document.body.dataset.page;
const byId = (id) => document.getElementById(id);
const SUPPORTS_FINE_POINTER = window.matchMedia("(pointer:fine)").matches;
const PREFERS_REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const MOTION_MODE = (!SUPPORTS_FINE_POINTER || PREFERS_REDUCED_MOTION || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4))
    ? "lite"
    : "full";

let AI_STATUS = {
    enabled: false,
    provider: "local-fallback",
    model: "rule-engine",
    image_model: "svg-visualizer",
};

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function renderList(items) {
    return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function getActiveUser() {
    return localStorage.getItem("user") || "";
}

function getPreset(name) {
    return new URLSearchParams(window.location.search).get(name) || "";
}

function applyPresetValue(id, value) {
    const node = byId(id);
    if (!node || !value) {
        return;
    }

    if (node.tagName === "SELECT") {
        const match = Array.from(node.options).some((option) => option.value === value);
        if (match) {
            node.value = value;
        }
        return;
    }

    node.value = value;
}

function artifactLabel(type) {
    const labels = {
        notes: "Notes",
        pass_pathfinder: "Pass Pathfinder",
        pyq_lab: "PYQ Lab",
        video_notes: "Video Notes",
        summary: "Summary",
        war_room: "War Room",
        trend_lab: "Trend Lab",
        professor_lab: "Professor Lab",
        ai_studio: "AI Studio",
    };
    return labels[type] || type;
}

function renderArtifactCard(item) {
    return `
        <article class="artifact-card">
            <div class="artifact-top">
                <span class="chip">${escapeHtml(artifactLabel(item.artifact_type))}</span>
                <span class="artifact-time">${escapeHtml(item.created_at)}</span>
            </div>
            <h3>${escapeHtml(item.title)}</h3>
            <p>${escapeHtml(item.preview || item.summary || "Saved study artifact")}</p>
            ${item.source_topic ? `<span class="chip">${escapeHtml(item.source_topic)}</span>` : ""}
        </article>
    `;
}

function providerChip(provider) {
    return `<span class="chip chip-provider">${escapeHtml(provider || "local")}</span>`;
}

function renderVisualBlock(targetId, payload) {
    const target = byId(targetId);
    if (!target) {
        return;
    }
    target.innerHTML = `
        <div class="visual-shell">
            <div class="artifact-top">
                <span class="chip">Visual Explainer</span>
                ${providerChip(payload.provider)}
            </div>
            <p>${escapeHtml(payload.summary || "Visual generated successfully.")}</p>
            <img class="visual-canvas" src="${payload.data_url}" alt="Study visual explainer">
        </div>
    `;
}

function apply3DTilt() {
    if (!SUPPORTS_FINE_POINTER || MOTION_MODE === "lite") {
        return;
    }
    const surfaces = document.querySelectorAll(".panel-hero, .panel-display, .feature-card, .hero-strip");
    let activeSurface = null;
    let frameRequested = false;
    let pointerX = 0;
    let pointerY = 0;

    const clearSurface = (surface) => {
        if (!surface) {
            return;
        }
        surface.style.transform = "";
        surface.style.removeProperty("--glow-x");
        surface.style.removeProperty("--glow-y");
    };

    const render = () => {
        frameRequested = false;
        if (!activeSurface) {
            return;
        }
        const bounds = activeSurface.getBoundingClientRect();
        const x = (pointerX - bounds.left) / bounds.width;
        const y = (pointerY - bounds.top) / bounds.height;
        const rotateY = (x - 0.5) * 5;
        const rotateX = (0.5 - y) * 5;
        activeSurface.style.setProperty("--glow-x", `${x * 100}%`);
        activeSurface.style.setProperty("--glow-y", `${y * 100}%`);
        activeSurface.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(0)`;
    };

    surfaces.forEach((surface) => {
        surface.addEventListener("pointermove", (event) => {
            activeSurface = surface;
            pointerX = event.clientX;
            pointerY = event.clientY;
            if (!frameRequested) {
                frameRequested = true;
                window.requestAnimationFrame(render);
            }
        });

        surface.addEventListener("pointerleave", () => {
            clearSurface(surface);
            if (activeSurface === surface) {
                activeSurface = null;
            }
        });
    });
}

function initCursorGlow() {
    const glow = byId("cursorGlow");
    if (!glow || !SUPPORTS_FINE_POINTER) {
        return;
    }
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 3;
    let ticking = false;

    const render = () => {
        ticking = false;
        glow.style.opacity = "1";
        glow.style.transform = `translate(${mouseX}px, ${mouseY}px) translate(-50%, -50%)`;
        if (MOTION_MODE === "full") {
            document.body.style.setProperty("--mouse-x", `${mouseX}px`);
            document.body.style.setProperty("--mouse-y", `${mouseY}px`);
        }
    };

    window.addEventListener("mousemove", (event) => {
        mouseX = event.clientX;
        mouseY = event.clientY;
        if (!ticking) {
            ticking = true;
            window.requestAnimationFrame(render);
        }
    }, { passive: true });

    document.addEventListener("mouseleave", () => {
        glow.style.opacity = "0";
    });
}

function initScrollProgress() {
    const bar = byId("scrollProgress");
    if (!bar) {
        return;
    }
    let ticking = false;

    const update = () => {
        ticking = false;
        const scrollTop = window.scrollY;
        const maxScroll = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
        const ratio = Math.min(scrollTop / maxScroll, 1);
        bar.style.width = `${ratio * 100}%`;
    };

    update();
    window.addEventListener("scroll", () => {
        if (!ticking) {
            ticking = true;
            window.requestAnimationFrame(update);
        }
    }, { passive: true });
    window.addEventListener("resize", update);
}

function initRevealMotion() {
    if (PREFERS_REDUCED_MOTION) {
        return;
    }
    const items = document.querySelectorAll(".panel, .feature-card, .atlas-card, .signal-card");
    if (!items.length) {
        return;
    }

    items.forEach((item, index) => {
        item.classList.add("reveal-up");
        item.style.transitionDelay = `${Math.min(index * 35, 280)}ms`;
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.14 });

    items.forEach((item) => observer.observe(item));
}

function initMagneticButtons() {
    if (!SUPPORTS_FINE_POINTER || MOTION_MODE === "lite") {
        return;
    }

    document.querySelectorAll(".hero-actions .btn, .button-row .btn-primary").forEach((button) => {
        let ticking = false;
        let offsetX = 0;
        let offsetY = 0;

        const render = () => {
            ticking = false;
            button.style.transform = `translate3d(${offsetX}px, ${offsetY}px, 0)`;
        };

        button.addEventListener("mousemove", (event) => {
            const bounds = button.getBoundingClientRect();
            const x = (event.clientX - bounds.left - bounds.width / 2) / bounds.width;
            const y = (event.clientY - bounds.top - bounds.height / 2) / bounds.height;
            offsetX = x * 8;
            offsetY = y * 8;
            if (!ticking) {
                ticking = true;
                window.requestAnimationFrame(render);
            }
        });

        button.addEventListener("mouseleave", () => {
            button.style.transform = "";
        });
    });
}

async function postJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || data.notes || data.summary || "Something went wrong.");
    }
    return data;
}

async function postFormData(url, formData) {
    const response = await fetch(url, {
        method: "POST",
        body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || "Something went wrong.");
    }
    return data;
}

async function fetchAiStatus() {
    try {
        const response = await fetch("/api/ai-status");
        AI_STATUS = await response.json();
    } catch (_error) {
        AI_STATUS = {
            enabled: false,
            provider: "local-fallback",
            model: "rule-engine",
            image_model: "svg-visualizer",
        };
    }
}

async function saveArtifact(payload, statusId) {
    const statusNode = byId(statusId);
    if (statusNode) {
        statusNode.textContent = "Saving to Vault...";
    }
    try {
        await postJson("/api/save-artifact", {
            username: getActiveUser(),
            ...payload,
        });
        if (statusNode) {
            statusNode.textContent = "Saved to Vault successfully.";
        }
    } catch (error) {
        if (statusNode) {
            statusNode.textContent = error.message;
        }
    }
}

function initNotesPage() {
    const form = byId("notesForm");
    const output = byId("notesOutput");
    if (!form || !output) {
        return;
    }

    applyPresetValue("topic", getPreset("topic"));
    applyPresetValue("notesExam", getPreset("exam"));
    applyPresetValue("notesGoal", getPreset("goal"));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Forging your notes architecture...</div>`;

        try {
            const payload = await postJson("/api/notes", {
                topic: byId("topic").value,
                exam: byId("notesExam").value,
                goal: byId("notesGoal").value,
                depth: byId("notesDepth").value,
            });

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">${escapeHtml(payload.mode)}</p>
                        <h2>${escapeHtml(payload.title)}</h2>
                        <p>${escapeHtml(payload.spark)}</p>
                    </div>
                    <div class="badge-row">
                        ${providerChip(payload.provider)}
                        <span class="chip">${escapeHtml(payload.exam)}</span>
                        <span class="chip">${escapeHtml(payload.goal)}</span>
                    </div>
                    <div class="module-grid">
                        ${payload.modules.map((module) => `
                            <section class="result-card">
                                <h3>${escapeHtml(module.label)}</h3>
                                <ul>${renderList(module.points)}</ul>
                            </section>
                        `).join("")}
                    </div>
                    <section class="result-card emphasis-card">
                        <h3>Memory Hook</h3>
                        <p>${escapeHtml(payload.memory_hook)}</p>
                    </section>
                    <section class="result-card">
                        <h3>Concept Web</h3>
                        <div class="badge-row">${payload.concept_web.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>
                    </section>
                    <section class="result-card">
                        <h3>Professor Pitch</h3>
                        <p>${escapeHtml(payload.professor_pitch)}</p>
                    </section>
                    <section class="result-card">
                        <h3>Rapid Fire Recall</h3>
                        <ul>${renderList(payload.rapid_fire)}</ul>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="saveNotesBtn" type="button">Save To Vault</button>
                        <button class="btn btn-secondary" id="visualNotesBtn" type="button">Visual Explain</button>
                        <a class="btn btn-secondary" href="/professor-lab">Open Professor Lab</a>
                    </div>
                    <p id="notesSaveStatus" class="status-line"></p>
                    <div id="notesVisual" class="visual-slot"></div>
                </div>
            `;

            byId("saveNotesBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "notes",
                        title: payload.title,
                        source_topic: byId("topic").value,
                        summary: payload.spark,
                        content: JSON.stringify(payload, null, 2),
                        metadata: { exam: payload.exam, goal: payload.goal, provider: payload.provider },
                    },
                    "notesSaveStatus"
                );
            });

            byId("visualNotesBtn").addEventListener("click", async () => {
                const target = byId("notesVisual");
                target.innerHTML = `<div class="loading-card compact-empty">Building visual explainer...</div>`;
                const visual = await postJson("/api/visual-explainer", {
                    topic: byId("topic").value,
                    context: `${payload.spark}\n${payload.modules.flatMap((module) => module.points).join("\n")}`,
                    exam: byId("notesExam").value,
                });
                renderVisualBlock("notesVisual", visual);
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initVideoNotesPage() {
    const form = byId("videoNotesForm");
    const output = byId("videoNotesOutput");
    if (!form || !output) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Transforming the video into notes...</div>`;

        try {
            const payload = await postJson("/api/video-notes", {
                video_url: byId("videoUrl").value,
                exam: byId("videoExam").value,
                focus: byId("videoFocus").value,
                style: byId("videoStyle").value,
                transcript: byId("videoTranscript").value,
            });

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">${escapeHtml(payload.capture_mode)}</p>
                        <h2>${escapeHtml(payload.title)}</h2>
                        <p>${escapeHtml(payload.overview)}</p>
                    </div>
                    <div class="badge-row">
                        ${providerChip(payload.provider)}
                        <span class="chip">${escapeHtml(payload.exam)}</span>
                        <span class="chip">${escapeHtml(payload.style)}</span>
                        <span class="chip">${escapeHtml(payload.creator)}</span>
                    </div>
                    ${payload.thumbnail_url ? `<img class="visual-canvas" src="${escapeHtml(payload.thumbnail_url)}" alt="Video thumbnail">` : ""}
                    <section class="result-card">
                        <h3>Important Notes</h3>
                        <ul>${renderList(payload.important_notes)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Keyword Stack</h3>
                        <div class="badge-row">${payload.keywords.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>
                    </section>
                    <section class="result-card">
                        <h3>Lecture Blocks</h3>
                        <div class="plan-grid">
                            ${payload.study_blocks.map((block) => `
                                <article class="plan-card">
                                    <div class="plan-day">${escapeHtml(block.label)}</div>
                                    <h3>${escapeHtml(block.focus)}</h3>
                                    <ul>${renderList(block.takeaways)}</ul>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card emphasis-card">
                        <h3>Memory Hook</h3>
                        <p>${escapeHtml(payload.memory_hook)}</p>
                    </section>
                    <section class="result-card">
                        <h3>Exam Questions From This Video</h3>
                        <ul>${renderList(payload.exam_questions)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Action Stack</h3>
                        <ul>${renderList(payload.action_stack)}</ul>
                        <p>${escapeHtml(payload.transcript_tip)}</p>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="saveVideoNotesBtn" type="button">Save To Vault</button>
                        <button class="btn btn-secondary" id="visualVideoNotesBtn" type="button">Visual Explain</button>
                        <a class="btn btn-secondary" href="/notes?exam=${encodeURIComponent(byId("videoExam").value)}&topic=${encodeURIComponent(payload.focus)}">Forge Topic Notes</a>
                    </div>
                    <p id="videoNotesSaveStatus" class="status-line"></p>
                    <div id="videoNotesVisual" class="visual-slot"></div>
                </div>
            `;

            byId("saveVideoNotesBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "video_notes",
                        title: payload.title,
                        source_topic: payload.focus,
                        summary: payload.overview,
                        content: JSON.stringify(payload, null, 2),
                        metadata: {
                            exam: payload.exam,
                            creator: payload.creator,
                            style: payload.style,
                            provider: payload.provider,
                        },
                    },
                    "videoNotesSaveStatus"
                );
            });

            byId("visualVideoNotesBtn").addEventListener("click", async () => {
                const target = byId("videoNotesVisual");
                target.innerHTML = `<div class="loading-card compact-empty">Generating concept visual...</div>`;
                const visual = await postJson("/api/visual-explainer", {
                    topic: payload.focus || payload.title,
                    context: [payload.overview, ...payload.important_notes].join("\n"),
                    exam: payload.exam,
                });
                renderVisualBlock("videoNotesVisual", visual);
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initPyqLabPage() {
    const form = byId("pyqLabForm");
    const output = byId("pyqLabOutput");
    const examSelect = byId("pyqExam");
    const subjectSelect = byId("pyqSubject");
    const chapterSelect = byId("pyqChapter");
    if (!form || !output || !examSelect || !subjectSelect || !chapterSelect || !window.EXAM_CATALOG) {
        return;
    }

    function getActiveExam() {
        return window.EXAM_CATALOG.find((item) => item.exam === examSelect.value);
    }

    function loadSubjects() {
        const activeExam = getActiveExam();
        const subjectOptions = activeExam
            ? activeExam.subjects.map((subject) => {
                const countLabel = subject.count ? `${subject.count}Q` : "AI";
                return `<option value="${escapeHtml(subject.name)}">${escapeHtml(subject.name)} (${countLabel})</option>`;
            }).join("")
            : `<option value="">Choose subject</option>`;
        subjectSelect.innerHTML = subjectOptions || `<option value="">Choose subject</option>`;
    }

    function loadChapters() {
        const activeExam = getActiveExam();
        const activeSubject = activeExam
            ? activeExam.subjects.find((item) => item.name === subjectSelect.value)
            : null;
        const topics = activeSubject ? [...new Set(activeSubject.topics || [])] : [];
        chapterSelect.innerHTML = `<option value="">Full subject scan</option>${
            topics.map((topic) => `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`).join("")
        }`;
    }

    applyPresetValue("pyqExam", getPreset("exam"));
    loadSubjects();
    applyPresetValue("pyqSubject", getPreset("subject"));
    loadChapters();
    applyPresetValue("pyqChapter", getPreset("topic"));

    examSelect.addEventListener("change", () => {
        loadSubjects();
        loadChapters();
    });

    subjectSelect.addEventListener("change", () => {
        loadChapters();
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Mapping topic-wise previous questions and repeat zones...</div>`;

        try {
            const payload = await postJson("/api/pyq-lab", {
                exam: examSelect.value,
                subject: subjectSelect.value,
                chapter: chapterSelect.value,
                question_count: byId("pyqCount").value,
                difficulty: byId("pyqDifficulty").value,
            });

            const focusTopic = chapterSelect.value || payload.visual_topic || subjectSelect.value;
            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">${escapeHtml(payload.source_mode)}</p>
                        <h2>${escapeHtml(payload.headline)}</h2>
                        <p>${escapeHtml(payload.summary)}</p>
                    </div>
                    <div class="badge-row">
                        ${providerChip(payload.provider)}
                        <span class="chip">${escapeHtml(payload.coverage.exam)}</span>
                        <span class="chip">${escapeHtml(payload.coverage.subject)}</span>
                        <span class="chip">${payload.coverage.question_total} questions</span>
                        <span class="chip">${escapeHtml(payload.coverage.difficulty)}</span>
                    </div>
                    <section class="result-card">
                        <h3>Most Important Topics</h3>
                        <div class="badge-row">${payload.most_important_topics.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>
                    </section>
                    <section class="result-card">
                        <h3>Chapter Radar</h3>
                        <div class="plan-grid">
                            ${payload.chapter_cards.map((card) => `
                                <article class="plan-card">
                                    <div class="plan-day">${card.count} question(s)</div>
                                    <h3>${escapeHtml(card.chapter)}</h3>
                                    <p>${escapeHtml(card.mastery_signal)}</p>
                                    <p>${escapeHtml(card.difficulty)} difficulty signal</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>Topic-Wise Previous Questions</h3>
                        <div class="result-stack">
                            ${payload.chapter_cards.map((card) => `
                                <article class="review-card">
                                    <div class="artifact-top">
                                        <strong>${escapeHtml(card.chapter)}</strong>
                                        <span class="artifact-time">${card.count} mapped</span>
                                    </div>
                                    <p>${escapeHtml(card.mastery_signal)}</p>
                                    <div class="result-stack">
                                        ${card.questions.map((entry) => `
                                            <section class="result-card">
                                                <h3>${escapeHtml(entry.question)}</h3>
                                                <p><strong>Answer:</strong> ${escapeHtml(entry.answer)}</p>
                                                <p>${escapeHtml(entry.explanation)}</p>
                                            </section>
                                        `).join("")}
                                    </div>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card emphasis-card">
                        <h3>Most Probable Next Questions</h3>
                        <ul>${renderList(payload.probable_next)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Rapid Revision Ladder</h3>
                        <ul>${renderList(payload.rapid_revision)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Practice Sprints</h3>
                        <div class="plan-grid">
                            ${payload.practice_lanes.map((lane) => `
                                <article class="plan-card">
                                    <div class="plan-day">${escapeHtml(lane.label)}</div>
                                    <h3>${escapeHtml(lane.focus)}</h3>
                                    <ul>${renderList(lane.drills)}</ul>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="savePyqLabBtn" type="button">Save To Vault</button>
                        <button class="btn btn-secondary" id="visualPyqLabBtn" type="button">Visual Explain</button>
                        <a class="btn btn-secondary" href="/mock?exam=${encodeURIComponent(examSelect.value)}&subject=${encodeURIComponent(subjectSelect.value)}&topic=${encodeURIComponent(focusTopic)}">Practice Now</a>
                        <a class="btn btn-secondary" href="/notes?exam=${encodeURIComponent(examSelect.value)}&topic=${encodeURIComponent(focusTopic)}">Forge Notes</a>
                    </div>
                    <p id="pyqLabSaveStatus" class="status-line"></p>
                    <div id="pyqLabVisual" class="visual-slot"></div>
                </div>
            `;

            byId("savePyqLabBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "pyq_lab",
                        title: payload.headline,
                        source_topic: focusTopic,
                        summary: payload.summary,
                        content: JSON.stringify(payload, null, 2),
                        metadata: {
                            exam: examSelect.value,
                            subject: subjectSelect.value,
                            chapter: chapterSelect.value,
                            provider: payload.provider,
                        },
                    },
                    "pyqLabSaveStatus"
                );
            });

            byId("visualPyqLabBtn").addEventListener("click", async () => {
                const target = byId("pyqLabVisual");
                target.innerHTML = `<div class="loading-card compact-empty">Building chapter visual...</div>`;
                const visual = await postJson("/api/visual-explainer", {
                    topic: focusTopic,
                    context: [payload.summary, ...payload.probable_next, ...payload.rapid_revision].join("\n"),
                    exam: examSelect.value,
                });
                renderVisualBlock("pyqLabVisual", visual);
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initSummaryPage() {
    const form = byId("summaryForm");
    const output = byId("summaryOutput");
    if (!form || !output) {
        return;
    }

    applyPresetValue("summaryInput", getPreset("text"));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Compressing your text into an exam brief...</div>`;

        try {
            const sourceText = byId("summaryInput").value;
            const payload = await postJson("/api/summarize", { text: sourceText });
            const battlecards = await postJson("/api/battlecards", { text: sourceText });

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">Compressed Overview</p>
                        <h2>${escapeHtml(payload.overview)}</h2>
                    </div>
                    <div class="badge-row">
                        ${providerChip(payload.provider)}
                        <span class="chip">${payload.stats.words} words</span>
                        <span class="chip">${payload.stats.reading_minutes} min read</span>
                    </div>
                    <section class="result-card">
                        <h3>Key Bullets</h3>
                        <ul>${renderList(payload.bullet_points)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Keywords</h3>
                        <div class="badge-row">${payload.keywords.map((word) => `<span class="chip">${escapeHtml(word)}</span>`).join("")}</div>
                    </section>
                    <section class="result-card">
                        <h3>Flashcards</h3>
                        <div class="flash-grid">
                            ${payload.flashcards.map((card) => `
                                <article class="flash-card">
                                    <strong>${escapeHtml(card.q)}</strong>
                                    <p>${escapeHtml(card.a)}</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>Lecture Outline</h3>
                        <ul>${renderList(payload.lecture_outline)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Exam Prompts</h3>
                        <ul>${renderList(payload.exam_questions)}</ul>
                    </section>
                    <section class="result-card emphasis-card">
                        <h3>${escapeHtml(battlecards.title)}</h3>
                        <p>${escapeHtml(battlecards.memory_system)}</p>
                        <div class="flash-grid">
                            ${battlecards.cards.map((card) => `
                                <article class="flash-card">
                                    <strong>${escapeHtml(card.trigger)}</strong>
                                    <p>${escapeHtml(card.response)}</p>
                                    <p><em>${escapeHtml(card.trap)}</em></p>
                                </article>
                            `).join("")}
                        </div>
                        <p>${escapeHtml(battlecards.power_move)}</p>
                    </section>
                    <section class="result-card">
                        <h3>Professor Take</h3>
                        <p>${escapeHtml(payload.professor_take)}</p>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="saveSummaryBtn" type="button">Save To Vault</button>
                        <button class="btn btn-secondary" id="visualSummaryBtn" type="button">Visual Explain</button>
                        <a class="btn btn-secondary" href="/professor-lab">Check Your Answer</a>
                    </div>
                    <p id="summarySaveStatus" class="status-line"></p>
                    <div id="summaryVisual" class="visual-slot"></div>
                </div>
            `;

            byId("saveSummaryBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "summary",
                        title: payload.overview,
                        source_topic: payload.keywords[0] || "Summary",
                        summary: payload.bullet_points[0] || payload.overview,
                        content: JSON.stringify({ summary: payload, battlecards }, null, 2),
                        metadata: { keywords: payload.keywords, provider: payload.provider },
                    },
                    "summarySaveStatus"
                );
            });

            byId("visualSummaryBtn").addEventListener("click", async () => {
                const target = byId("summaryVisual");
                target.innerHTML = `<div class="loading-card compact-empty">Rendering concept visual...</div>`;
                const visual = await postJson("/api/visual-explainer", {
                    topic: payload.keywords[0] || "Study concept",
                    context: `${payload.overview}\n${payload.bullet_points.join("\n")}`,
                });
                renderVisualBlock("summaryVisual", visual);
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initAuthPage() {
    const loginBtn = byId("loginBtn");
    const registerBtn = byId("registerBtn");
    const message = byId("authMessage");
    if (!loginBtn || !registerBtn || !message) {
        return;
    }

    const getPayload = () => ({
        username: byId("authUsername").value.trim(),
        password: byId("authPassword").value.trim(),
    });

    loginBtn.addEventListener("click", async () => {
        message.textContent = "Checking access...";
        try {
            const data = await postJson("/login_user", getPayload());
            if (data.msg === "success") {
                localStorage.setItem("user", getPayload().username);
                message.textContent = "Login successful. Redirecting to dashboard...";
                window.location.href = "/dashboard";
            } else {
                message.textContent = "Invalid username or password.";
            }
        } catch (error) {
            message.textContent = error.message;
        }
    });

    registerBtn.addEventListener("click", async () => {
        message.textContent = "Creating account...";
        try {
            const data = await postJson("/register", getPayload());
            if (data.msg === "ok") {
                message.textContent = "Registered successfully. You can log in now and start building momentum.";
            } else if (data.msg === "exists") {
                message.textContent = "Username already exists.";
            } else {
                message.textContent = "Username 3 chars aur password 4 chars minimum rakho.";
            }
        } catch (error) {
            message.textContent = error.message;
        }
    });
}

function initMockPage() {
    const examSelect = byId("mockExam");
    const subjectSelect = byId("mockSubject");
    const startBtn = byId("startMockBtn");
    const output = byId("mockOutput");
    const engineStatus = byId("mockEngineStatus");
    if (!examSelect || !subjectSelect || !startBtn || !output || !window.EXAM_CATALOG) {
        return;
    }

    const state = {
        questions: [],
        answers: [],
        currentIndex: 0,
        activeExam: "",
        activeSubject: "",
        setTitle: "",
        provider: "local",
        timerId: null,
        secondsLeft: 0,
    };

    engineStatus.textContent = AI_STATUS.enabled
        ? `AI live: ${AI_STATUS.model} | image model: ${AI_STATUS.image_model}`
        : "AI API key not configured. Local fallback and classic bank still work smoothly.";

    function clearTimer() {
        if (state.timerId) {
            window.clearInterval(state.timerId);
            state.timerId = null;
        }
    }

    function loadSubjects() {
        const selectedExam = examSelect.value;
        const match = window.EXAM_CATALOG.find((item) => item.exam === selectedExam);
        subjectSelect.innerHTML = match
            ? match.subjects.map((subject) => {
                const countLabel = subject.count ? `${subject.count}` : "AI";
                return `<option value="${escapeHtml(subject.name)}">${escapeHtml(subject.name)} (${countLabel})</option>`;
            }).join("")
            : "";
    }

    function startPerQuestionTimer() {
        clearTimer();
        if (byId("mockMode").value !== "mock") {
            return;
        }
        state.secondsLeft = byId("mockDifficulty").value === "hard" ? 30 : byId("mockDifficulty").value === "easy" ? 50 : 40;
        const node = byId("mockTimer");
        if (node) {
            node.textContent = `${state.secondsLeft}s`;
        }
        state.timerId = window.setInterval(() => {
            state.secondsLeft -= 1;
            const liveNode = byId("mockTimer");
            if (liveNode) {
                liveNode.textContent = `${state.secondsLeft}s`;
            }
            if (state.secondsLeft <= 0) {
                clearTimer();
                state.answers[state.currentIndex] = "";
                state.currentIndex += 1;
                if (state.currentIndex < state.questions.length) {
                    renderQuestion();
                } else {
                    submitMock();
                }
            }
        }, 1000);
    }

    function renderQuestion() {
        const question = state.questions[state.currentIndex];
        output.innerHTML = `
            <div class="quiz-shell">
                <div class="quiz-topline">
                    ${providerChip(state.provider)}
                    <span class="chip">${escapeHtml(state.activeExam)}</span>
                    <span class="chip">${escapeHtml(state.activeSubject)}</span>
                    <span class="chip">Q ${state.currentIndex + 1}/${state.questions.length}</span>
                    ${byId("mockMode").value === "mock" ? `<span class="chip timer-chip" id="mockTimer"></span>` : ""}
                </div>
                <h2>${escapeHtml(question.question)}</h2>
                <p class="mini-note">${escapeHtml(state.setTitle)}</p>
                <div class="option-grid">
                    ${question.options.map((option) => `
                        <button class="option-btn" data-option="${escapeHtml(option)}">${escapeHtml(option)}</button>
                    `).join("")}
                </div>
            </div>
        `;

        output.querySelectorAll(".option-btn").forEach((button) => {
            button.addEventListener("click", () => {
                clearTimer();
                state.answers[state.currentIndex] = button.dataset.option;
                state.currentIndex += 1;
                if (state.currentIndex < state.questions.length) {
                    renderQuestion();
                } else {
                    submitMock();
                }
            });
        });
        startPerQuestionTimer();
    }

    async function showReview(index) {
        const target = byId(`review-${index}`);
        if (!target) {
            return;
        }
        target.innerHTML = `<div class="loading-card compact-empty">Analyzing mistake...</div>`;
        const review = await postJson("/api/question-review", {
            question: state.questions[index],
            selected: state.answers[index] || "No answer",
            exam: state.activeExam,
            subject: state.activeSubject,
        });
        target.innerHTML = `
            <div class="result-card">
                <div class="badge-row">
                    ${providerChip(review.provider)}
                    <span class="chip">Correct: ${escapeHtml(review.correct_answer)}</span>
                </div>
                <p>${escapeHtml(review.why_wrong)}</p>
                <p>${escapeHtml(review.explanation)}</p>
                <ul>${renderList(review.repair_steps)}</ul>
            </div>
        `;
    }

    async function showVisual(index) {
        const target = byId(`visual-${index}`);
        if (!target) {
            return;
        }
        target.innerHTML = `<div class="loading-card compact-empty">Generating visual explainer...</div>`;
        const visual = await postJson("/api/visual-explainer", {
            topic: state.questions[index].topic || state.activeSubject,
            context: `${state.questions[index].question}\n${state.questions[index].explanation || ""}`,
            exam: state.activeExam,
        });
        renderVisualBlock(`visual-${index}`, visual);
    }

    async function submitMock() {
        clearTimer();
        output.innerHTML = `<div class="loading-card">Scoring your attempt and mapping weak areas...</div>`;
        try {
            const payload = await postJson("/submit_mock", {
                questions: state.questions,
                answers: state.answers,
                username: getActiveUser(),
                exam: state.activeExam,
                subject: state.activeSubject,
            });
            localStorage.setItem("weakTopics", JSON.stringify(payload.weak_topics || []));

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">Session Complete</p>
                        <h2>${payload.score}/${payload.total} scored | ${payload.percent}%</h2>
                        <p>${escapeHtml(payload.recommendation)}</p>
                    </div>
                    <section class="result-card">
                        <h3>Weak Topic Radar</h3>
                        <div class="badge-row">${payload.weak_topics.length ? payload.weak_topics.map((topic) => `<span class="chip">${escapeHtml(topic)}</span>`).join("") : `<span class="chip">No weak topics detected</span>`}</div>
                    </section>
                    <section class="result-card">
                        <h3>Wrong Answer Studio</h3>
                        ${payload.weak.length ? payload.weak.map((item, index) => `
                            <article class="review-card">
                                <strong>${escapeHtml(item.question)}</strong>
                                <p>Correct: ${escapeHtml(item.correct)}</p>
                                ${item.explanation ? `<p>${escapeHtml(item.explanation)}</p>` : ""}
                                <div class="button-row review-actions">
                                    <button class="btn btn-secondary review-btn" data-index="${index}" type="button">AI Analyze</button>
                                    <button class="btn btn-secondary visual-btn" data-index="${index}" type="button">Visual Explain</button>
                                </div>
                                <div id="review-${index}" class="visual-slot"></div>
                                <div id="visual-${index}" class="visual-slot"></div>
                            </article>
                        `).join("") : `<p>Clean attempt. You can now increase both difficulty and speed.</p>`}
                    </section>
                    <div class="button-row">
                        <a class="btn btn-secondary" href="/notes">Forge notes for weak areas</a>
                        <a class="btn btn-secondary" href="/war-room">Build recovery plan</a>
                        <a class="btn btn-secondary" href="/professor-lab">Check an answer</a>
                        <button class="btn btn-primary" id="restartMockBtn" type="button">Try Another Session</button>
                    </div>
                </div>
            `;

            output.querySelectorAll(".review-btn").forEach((button) => {
                button.addEventListener("click", () => showReview(Number(button.dataset.index)));
            });
            output.querySelectorAll(".visual-btn").forEach((button) => {
                button.addEventListener("click", () => showVisual(Number(button.dataset.index)));
            });
            byId("restartMockBtn").addEventListener("click", startSession);
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    }

    async function startSession() {
        output.innerHTML = `<div class="loading-card">Generating your session...</div>`;
        state.activeExam = examSelect.value;
        state.activeSubject = subjectSelect.value;
        state.currentIndex = 0;
        state.answers = [];

        try {
            const payload = await postJson("/api/practice-set", {
                exam: state.activeExam,
                subject: state.activeSubject,
                topic: byId("mockTopic").value,
                difficulty: byId("mockDifficulty").value,
                question_count: byId("mockCount").value,
                engine: byId("mockEngine").value,
            });
            state.questions = payload.questions;
            state.setTitle = payload.set_title;
            state.provider = payload.provider || "local";

            if (!state.questions.length) {
                output.innerHTML = `<div class="empty-state">No questions were generated for this session.</div>`;
                return;
            }
            renderQuestion();
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    }

    examSelect.addEventListener("change", loadSubjects);
    startBtn.addEventListener("click", startSession);

    applyPresetValue("mockExam", getPreset("exam"));
    loadSubjects();
    applyPresetValue("mockSubject", getPreset("subject"));
    applyPresetValue("mockTopic", getPreset("topic"));
    applyPresetValue("mockDifficulty", getPreset("difficulty"));
    applyPresetValue("mockCount", getPreset("count"));
}

async function initDashboardPage() {
    const greeting = byId("dashboardGreeting");
    const mission = byId("dashboardMission");
    const personalPulse = byId("personalPulse");
    const examRadar = byId("examRadar");
    const leaders = byId("dashboardLeaders");
    const questNode = byId("dashboardQuest");
    const recentNode = byId("dashboardRecent");
    if (!greeting || !mission || !personalPulse || !examRadar || !leaders || !questNode || !recentNode) {
        return;
    }

    const response = await fetch(`/api/dashboard?username=${encodeURIComponent(getActiveUser())}`);
    const payload = await response.json();

    greeting.textContent = getActiveUser() ? `Welcome back, ${getActiveUser()}.` : "Build momentum, then protect it.";
    mission.textContent = payload.mission;
    byId("statUsers").textContent = payload.stats.total_users;
    byId("statSubjects").textContent = payload.stats.total_subjects;
    byId("statQuestions").textContent = payload.stats.total_questions;
    byId("statExams").textContent = payload.stats.exam_count;
    byId("statVault").textContent = payload.stats.vault_items;

    personalPulse.innerHTML = payload.user ? `
        <div class="pulse-grid">
            <div class="result-card"><h3>Best Score</h3><p>${payload.user.best_score}%</p></div>
            <div class="result-card"><h3>Attempts</h3><p>${payload.user.attempts}</p></div>
            <div class="result-card"><h3>Last Exam</h3><p>${escapeHtml(payload.user.last_exam)}</p></div>
            <div class="result-card"><h3>Weak Areas</h3><div class="badge-row">${payload.user.weak_areas.length ? payload.user.weak_areas.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("") : `<span class="chip">Build new streak</span>`}</div></div>
        </div>
    ` : `Log in and complete a mock attempt to unlock personalized recovery insights here.`;

    examRadar.innerHTML = payload.exam_radar.map((item) => `
        <div class="exam-card">
            <div><strong>${escapeHtml(item.exam)}</strong><span>${item.question_count ? `${item.question_count} questions` : "AI infinite"}</span></div>
            <p>${item.subjects.map((subject) => escapeHtml(subject.name)).join(" / ")}</p>
        </div>
    `).join("");

    leaders.innerHTML = payload.top_users.length
        ? payload.top_users.map((user, index) => `
            <div class="leader-row">
                <span>#${index + 1}</span>
                <strong>${escapeHtml(user.username)}</strong>
                <em>${user.best_score}%</em>
            </div>
        `).join("")
        : `<p class="muted-copy">The leaderboard is still warming up.</p>`;

    questNode.innerHTML = `
        <div class="quest-card">
            <h3>${escapeHtml(payload.quest.title)}</h3>
            <ul>${renderList(payload.quest.steps)}</ul>
        </div>
    `;

    recentNode.innerHTML = payload.recent_artifacts.length
        ? payload.recent_artifacts.map(renderArtifactCard).join("")
        : `<div class="empty-state compact-empty">Nothing is saved yet. Save notes, summaries, plans, and professor reviews to start building your Vault.</div>`;
}

function initPassPathfinderPage() {
    const form = byId("pathfinderForm");
    const output = byId("pathfinderOutput");
    if (!form || !output) {
        return;
    }

    applyPresetValue("pathExam", getPreset("exam"));
    applyPresetValue("pathUniversity", getPreset("university"));
    applyPresetValue("pathSemester", getPreset("semester"));
    applyPresetValue("pathSubject", getPreset("subject"));
    applyPresetValue("pathDays", getPreset("days"));
    applyPresetValue("pathHours", getPreset("hours"));
    applyPresetValue("pathStart", getPreset("start"));
    applyPresetValue("pathTarget", getPreset("target"));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Building your zero-to-pass roadmap...</div>`;
        try {
            const payload = await postJson("/api/pass-pathfinder", {
                exam: byId("pathExam").value,
                university: byId("pathUniversity").value,
                semester: byId("pathSemester").value,
                subject: byId("pathSubject").value,
                days: byId("pathDays").value,
                hours: byId("pathHours").value,
                syllabus: byId("pathSyllabus").value,
                start_level: byId("pathStart").value,
                target_mode: byId("pathTarget").value,
            });

            const leadTopic = payload.visual_topic || byId("pathSubject").value;
            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">${escapeHtml(payload.coverage.mode)}</p>
                        <h2>${escapeHtml(payload.headline)}</h2>
                        <p>${escapeHtml(payload.mission)}</p>
                    </div>
                    <div class="badge-row">
                        ${providerChip(payload.provider)}
                        <span class="chip">${escapeHtml(payload.coverage.exam)}</span>
                        <span class="chip">${escapeHtml(payload.coverage.subject)}</span>
                        <span class="chip">${payload.coverage.days} days</span>
                        <span class="chip">${payload.coverage.hours} hr/day</span>
                        <span class="chip">${escapeHtml(payload.coverage.syllabus_source)}</span>
                    </div>
                    <section class="result-card emphasis-card">
                        <h3>Confidence Note</h3>
                        <p>${escapeHtml(payload.confidence_note)}</p>
                    </section>
                    <section class="result-card">
                        <h3>How To Start</h3>
                        <ul>${renderList(payload.orientation)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Detected Syllabus Map</h3>
                        <div class="plan-grid">
                            ${payload.chapter_map.map((item) => `
                                <article class="plan-card">
                                    <div class="plan-day">${escapeHtml(item.priority)} Priority</div>
                                    <h3>${escapeHtml(item.unit)}</h3>
                                    <p>${escapeHtml(item.why)}</p>
                                    <p>${item.hours} hour focus block</p>
                                    <ul>${renderList(item.likely_questions)}</ul>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>Likely Questions You Should Prepare</h3>
                        <ul>${renderList(payload.question_stack)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Study Windows</h3>
                        <div class="plan-grid">
                            ${payload.study_windows.map((item) => `
                                <article class="plan-card">
                                    <div class="plan-day">${escapeHtml(item.label)}</div>
                                    <h3>${escapeHtml(item.focus)}</h3>
                                    <p>${escapeHtml(item.topic)}</p>
                                    <ul>${renderList(item.actions)}</ul>
                                    <p>${escapeHtml(item.checkpoint)}</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>3D Visual Learning Scenes</h3>
                        <div class="plan-grid">
                            ${payload.visual_scenes.map((scene) => `
                                <article class="plan-card">
                                    <div class="plan-day">${escapeHtml(scene.label)}</div>
                                    <h3>${escapeHtml(scene.topic)}</h3>
                                    <p>${escapeHtml(scene.direction)}</p>
                                    <p>${escapeHtml(scene.benefit)}</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>Survival Rules</h3>
                        <ul>${renderList(payload.survival_rules)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Next Actions</h3>
                        <ul>${renderList(payload.next_actions)}</ul>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="savePathfinderBtn" type="button">Save To Vault</button>
                        <button class="btn btn-secondary" id="visualPathfinderBtn" type="button">Visual Explain</button>
                        <a class="btn btn-secondary" href="/notes?exam=${encodeURIComponent(byId("pathExam").value)}&topic=${encodeURIComponent(leadTopic)}">Forge Notes</a>
                        <a class="btn btn-secondary" href="/pyq-lab?exam=${encodeURIComponent(byId("pathExam").value)}&subject=${encodeURIComponent(byId("pathSubject").value)}&topic=${encodeURIComponent(leadTopic)}">Open PYQ Lab</a>
                        <a class="btn btn-secondary" href="/war-room?exam=${encodeURIComponent(byId("pathExam").value)}&days=${encodeURIComponent(byId("pathDays").value)}&topics=${encodeURIComponent(payload.chapter_map.map((item) => item.unit).slice(0, 3).join(', '))}">Build War Room</a>
                    </div>
                    <p id="pathfinderSaveStatus" class="status-line"></p>
                    <div id="pathfinderVisual" class="visual-slot"></div>
                </div>
            `;

            byId("savePathfinderBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "pass_pathfinder",
                        title: payload.headline,
                        source_topic: leadTopic,
                        summary: payload.mission,
                        content: JSON.stringify(payload, null, 2),
                        metadata: {
                            exam: payload.coverage.exam,
                            university: payload.coverage.university,
                            semester: payload.coverage.semester,
                            subject: payload.coverage.subject,
                            provider: payload.provider,
                        },
                    },
                    "pathfinderSaveStatus"
                );
            });

            byId("visualPathfinderBtn").addEventListener("click", async () => {
                const target = byId("pathfinderVisual");
                target.innerHTML = `<div class="loading-card compact-empty">Generating your concept scene...</div>`;
                const visual = await postJson("/api/visual-explainer", {
                    topic: leadTopic,
                    context: [payload.mission, ...payload.question_stack.slice(0, 4), ...payload.survival_rules].join("\n"),
                    exam: byId("pathExam").value || payload.coverage.exam,
                });
                renderVisualBlock("pathfinderVisual", visual);
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initWarRoomPage() {
    const form = byId("warRoomForm");
    const output = byId("warRoomOutput");
    if (!form || !output) {
        return;
    }

    const savedWeakTopics = JSON.parse(localStorage.getItem("weakTopics") || "[]");
    applyPresetValue("warExam", getPreset("exam"));
    applyPresetValue("warDays", getPreset("days"));
    applyPresetValue("warHours", getPreset("hours"));
    applyPresetValue("warTopics", getPreset("topics"));
    if (byId("warTopics") && savedWeakTopics.length && !byId("warTopics").value.trim()) {
        byId("warTopics").value = savedWeakTopics.join(", ");
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Building your attack blueprint...</div>`;
        try {
            const payload = await postJson("/api/war-room", {
                exam: byId("warExam").value,
                days: byId("warDays").value,
                hours: byId("warHours").value,
                topics: byId("warTopics").value,
                energy: byId("warEnergy").value,
                weak_areas: savedWeakTopics,
            });

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">${escapeHtml(payload.mode)}</p>
                        <h2>${escapeHtml(payload.exam)} Attack Plan</h2>
                        <p>${escapeHtml(payload.focus_statement)}</p>
                    </div>
                    <div class="badge-row">
                        <span class="chip">${payload.days} days</span>
                        <span class="chip">${payload.hours} hr/day</span>
                    </div>
                    <section class="result-card">
                        <h3>Execution Rituals</h3>
                        <ul>${renderList(payload.ritual_stack)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Risk Alerts</h3>
                        <ul>${renderList(payload.risk_alerts)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Scoreboard System</h3>
                        <ul>${renderList(payload.scoreboard)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Daily Strike Map</h3>
                        <div class="plan-grid">
                            ${payload.daily_plan.map((day) => `
                                <article class="plan-card">
                                    <div class="plan-day">Day ${day.day}</div>
                                    <h3>${escapeHtml(day.theme)}</h3>
                                    <p>${escapeHtml(day.focus)}</p>
                                    <ul>${renderList(day.sprints)}</ul>
                                    <p>${escapeHtml(day.output)}</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="saveWarBtn" type="button">Save To Vault</button>
                    </div>
                    <p id="warSaveStatus" class="status-line"></p>
                </div>
            `;

            byId("saveWarBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "war_room",
                        title: `${payload.exam} Attack Plan`,
                        source_topic: byId("warTopics").value || payload.exam,
                        summary: payload.focus_statement,
                        content: JSON.stringify(payload, null, 2),
                        metadata: { days: payload.days, hours: payload.hours },
                    },
                    "warSaveStatus"
                );
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initProfessorLabPage() {
    const form = byId("professorForm");
    const output = byId("professorOutput");
    if (!form || !output) {
        return;
    }

    applyPresetValue("profExam", getPreset("exam"));
    applyPresetValue("profQuestion", getPreset("question"));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Professor is reviewing your answer...</div>`;
        try {
            const payload = await postJson("/api/professor-lab", {
                exam: byId("profExam").value,
                tone: byId("profTone").value,
                question: byId("profQuestion").value,
                answer: byId("profAnswer").value,
            });

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">${escapeHtml(payload.band)}</p>
                        <h2>${payload.overall_score}/100</h2>
                        <p>${escapeHtml(payload.verdict)}</p>
                    </div>
                    <section class="result-card">
                        <h3>Rubric</h3>
                        <div class="rubric-grid">
                            ${payload.rubric.map((item) => `
                                <article class="meter-card">
                                    <strong>${escapeHtml(item.label)}</strong>
                                    <div class="meter-track"><div class="meter-fill" style="width:${item.score * 4}%"></div></div>
                                    <span>${item.score}/25</span>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>Strengths</h3>
                        <ul>${renderList(payload.strengths)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Fixes</h3>
                        <ul>${renderList(payload.fixes)}</ul>
                    </section>
                    <section class="result-card emphasis-card">
                        <h3>Improved Answer Frame</h3>
                        <pre class="answer-pre">${escapeHtml(payload.improved_answer)}</pre>
                    </section>
                    <section class="result-card">
                        <h3>Viva Questions</h3>
                        <ul>${renderList(payload.viva_questions)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Professor Note</h3>
                        <p>${escapeHtml(payload.professor_note)}</p>
                        <div class="badge-row">${payload.question_keywords.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="saveProfessorBtn" type="button">Save To Vault</button>
                        <button class="btn btn-secondary" id="visualProfessorBtn" type="button">Visual Explain</button>
                    </div>
                    <p id="professorSaveStatus" class="status-line"></p>
                    <div id="professorVisual" class="visual-slot"></div>
                </div>
            `;

            byId("saveProfessorBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "professor_lab",
                        title: `Professor Review - ${payload.band}`,
                        source_topic: byId("profQuestion").value.slice(0, 90),
                        summary: payload.verdict,
                        content: JSON.stringify(payload, null, 2),
                        metadata: { exam: byId("profExam").value, tone: byId("profTone").value },
                    },
                    "professorSaveStatus"
                );
            });

            byId("visualProfessorBtn").addEventListener("click", async () => {
                const target = byId("professorVisual");
                target.innerHTML = `<div class="loading-card compact-empty">Generating teaching visual...</div>`;
                const visual = await postJson("/api/visual-explainer", {
                    topic: payload.question_keywords[0] || "Answer concept",
                    context: `${byId("profQuestion").value}\n${payload.improved_answer}`,
                    exam: byId("profExam").value,
                });
                renderVisualBlock("professorVisual", visual);
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initExamAtlasPage() {
    const grid = byId("atlasGrid");
    const search = byId("atlasSearch");
    const filter = byId("atlasFilter");
    if (!grid || !search || !filter || !window.EXAM_ATLAS) {
        return;
    }

    const tracks = window.EXAM_ATLAS.tracks || [];

    const render = () => {
        const query = search.value.trim().toLowerCase();
        const mode = filter.value;
        const filtered = tracks.filter((track) => {
            const pool = [
                track.exam,
                track.signature,
                ...track.subjects.map((subject) => subject.name),
                ...track.subjects.flatMap((subject) => subject.topics || []),
            ].join(" ").toLowerCase();

            if (mode === "classic" && !track.question_count) {
                return false;
            }
            if (mode === "ai_only" && track.question_count) {
                return false;
            }
            return !query || pool.includes(query);
        });

        grid.innerHTML = filtered.length
            ? filtered.map((track) => {
                const primarySubject = track.subjects[0] || { name: "General", topics: [] };
                const leadTopic = primarySubject.topics[0] || primarySubject.name || track.exam;
                return `
                    <article class="atlas-card">
                        <div class="atlas-card-top">
                            <div>
                                <h3>${escapeHtml(track.exam)}</h3>
                                <p>${escapeHtml(track.signature)}</p>
                            </div>
                            <div class="badge-row">
                                <span class="chip">${track.subject_count} subjects</span>
                                <span class="chip">${track.topic_count} topics</span>
                                <span class="chip">${track.question_count ? `${track.question_count} classic` : "AI infinite"}</span>
                            </div>
                        </div>
                        <div class="badge-row">
                            ${track.study_modes.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}
                        </div>
                        <div class="subject-cloud">
                            ${track.subjects.map((subject) => `
                                <article class="subject-pill">
                                    <div class="artifact-top">
                                        <strong>${escapeHtml(subject.name)}</strong>
                                        <span class="artifact-time">${subject.count ? `${subject.count}Q` : "AI"}</span>
                                    </div>
                                    <div class="topic-cloud">
                                        ${(subject.topics || []).length
                                            ? subject.topics.slice(0, 4).map((topic) => `<span class="chip">${escapeHtml(topic)}</span>`).join("")
                                            : `<span class="chip">Custom AI topic ready</span>`}
                                    </div>
                                </article>
                            `).join("")}
                        </div>
                        <div class="button-row">
                            <a class="btn btn-secondary" href="/notes?exam=${encodeURIComponent(track.exam)}&topic=${encodeURIComponent(leadTopic)}">Forge Notes</a>
                            <a class="btn btn-secondary" href="/mock?exam=${encodeURIComponent(track.exam)}&subject=${encodeURIComponent(primarySubject.name)}&topic=${encodeURIComponent(leadTopic)}">Practice Now</a>
                            <a class="btn btn-secondary" href="/war-room?exam=${encodeURIComponent(track.exam)}&topics=${encodeURIComponent(leadTopic)}">Build War Room</a>
                        </div>
                    </article>
                `;
            }).join("")
            : `<div class="empty-state compact-empty">No direct match was found for this search. Try a different topic or a broader exam keyword.</div>`;
    };

    search.addEventListener("input", render);
    filter.addEventListener("change", render);
    render();
}

function initAiStudioPage() {
    const form = byId("studioForm");
    const output = byId("studioOutput");
    if (!form || !output) {
        return;
    }

    applyPresetValue("studioTopic", getPreset("topic"));
    applyPresetValue("studioExam", getPreset("exam"));
    applyPresetValue("studioStyle", getPreset("style"));
    applyPresetValue("studioGoal", getPreset("goal"));

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Building immersive study deck...</div>`;

        try {
            const payload = await postJson("/api/ai-studio", {
                topic: byId("studioTopic").value,
                exam: byId("studioExam").value,
                style: byId("studioStyle").value,
                goal: byId("studioGoal").value,
            });

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">Immersive Concept Deck</p>
                        <h2>${escapeHtml(payload.title)}</h2>
                        <p>${escapeHtml(payload.hook)}</p>
                    </div>
                    <div class="badge-row">
                        ${providerChip(payload.provider)}
                        <span class="chip">${escapeHtml(payload.style)}</span>
                        <span class="chip">${escapeHtml(payload.goal)}</span>
                    </div>
                    <section class="result-card">
                        <h3>Learning Path</h3>
                        <ul>${renderList(payload.learning_path)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Board Flow</h3>
                        <div class="board-grid">
                            ${payload.board_flow.map((item) => `
                                <article class="plan-card">
                                    <div class="plan-day">${escapeHtml(item.label)}</div>
                                    <p>${escapeHtml(item.detail)}</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card emphasis-card">
                        <h3>Memory Anchors</h3>
                        <ul>${renderList(payload.memory_anchors)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Rapid Check</h3>
                        <ul>${renderList(payload.rapid_check)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Challenge Prompts</h3>
                        <ul>${renderList(payload.challenge_prompts)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Professor Bridge</h3>
                        <p>${escapeHtml(payload.professor_bridge)}</p>
                    </section>
                    <section class="result-card">
                        <h3>Campus Pitch</h3>
                        <p>${escapeHtml(payload.campus_pitch)}</p>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="saveStudioBtn" type="button">Save To Vault</button>
                        <button class="btn btn-secondary" id="remixStudioVisualBtn" type="button">Remix Visual</button>
                        <a class="btn btn-secondary" href="/mock?exam=${encodeURIComponent(byId("studioExam").value)}&topic=${encodeURIComponent(byId("studioTopic").value)}">Open Mock Arena</a>
                        <a class="btn btn-secondary" href="/professor-lab?exam=${encodeURIComponent(byId("studioExam").value)}&question=${encodeURIComponent(`Explain ${byId("studioTopic").value}`)}">Professor Check</a>
                    </div>
                    <p id="studioSaveStatus" class="status-line"></p>
                    <div id="studioVisual" class="visual-slot"></div>
                </div>
            `;

            renderVisualBlock("studioVisual", payload.visual);

            byId("saveStudioBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "ai_studio",
                        title: payload.title,
                        source_topic: byId("studioTopic").value,
                        summary: payload.hook,
                        content: JSON.stringify(payload, null, 2),
                        metadata: {
                            exam: byId("studioExam").value,
                            style: payload.style,
                            goal: payload.goal,
                            provider: payload.provider,
                        },
                    },
                    "studioSaveStatus"
                );
            });

            byId("remixStudioVisualBtn").addEventListener("click", async () => {
                const target = byId("studioVisual");
                target.innerHTML = `<div class="loading-card compact-empty">Rendering fresh study visual...</div>`;
                const visual = await postJson("/api/visual-explainer", {
                    topic: byId("studioTopic").value,
                    context: [payload.hook, ...payload.learning_path, ...payload.memory_anchors].join("\n"),
                    exam: byId("studioExam").value,
                });
                renderVisualBlock("studioVisual", visual);
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

function initTrendLabPage() {
    const form = byId("trendLabForm");
    const output = byId("trendLabOutput");
    if (!form || !output) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        output.innerHTML = `<div class="loading-card">Analyzing paper trends and predicting likely questions...</div>`;

        try {
            const formData = new FormData();
            formData.append("exam", byId("trendExam").value);
            formData.append("course_title", byId("trendCourseTitle").value);
            formData.append("goal", byId("trendGoal").value);
            formData.append("papers_text", byId("trendPapersText").value);
            Array.from(byId("trendFiles").files || []).forEach((file) => formData.append("papers", file));

            const payload = await postFormData("/api/trend-lab", formData);
            const leadTopic = payload.most_important_topics[0] || byId("trendCourseTitle").value || byId("trendExam").value;

            output.innerHTML = `
                <div class="result-stack">
                    <div class="result-head">
                        <p class="eyebrow">Predictive Analysis</p>
                        <h2>${escapeHtml(payload.headline)}</h2>
                        <p>${escapeHtml(payload.trend_summary)}</p>
                    </div>
                    <div class="badge-row">
                        ${providerChip(payload.provider)}
                        <span class="chip">${payload.years_covered.length} source(s)</span>
                        <span class="chip">${payload.question_volume} questions</span>
                        <span class="chip">${escapeHtml(payload.difficulty_profile.dominant)} dominant difficulty</span>
                    </div>
                    ${payload.warnings && payload.warnings.length ? `
                        <section class="result-card">
                            <h3>Upload Notes</h3>
                            <ul>${renderList(payload.warnings)}</ul>
                        </section>
                    ` : ""}
                    <section class="result-card">
                        <h3>Most Important Chapters</h3>
                        <div class="plan-grid">
                            ${payload.chapter_priority.map((item) => `
                                <article class="plan-card">
                                    <div class="plan-day">Weight ${item.weight}</div>
                                    <h3>${escapeHtml(item.chapter)}</h3>
                                    <p>${escapeHtml(item.reason)}</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>Topic Heatmap</h3>
                        <div class="flash-grid">
                            ${payload.topic_heatmap.map((item) => `
                                <article class="flash-card">
                                    <strong>${escapeHtml(item.topic)}</strong>
                                    <p>${escapeHtml(item.chapter)}</p>
                                    <p>${item.frequency} repeats | ${escapeHtml(item.trend)} | ${escapeHtml(item.difficulty)}</p>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card">
                        <h3>Topic-Wise Previous Questions</h3>
                        <div class="result-stack">
                            ${payload.topicwise_groups.map((group) => `
                                <article class="review-card">
                                    <div class="artifact-top">
                                        <strong>${escapeHtml(group.topic)}</strong>
                                        <span class="artifact-time">${group.count} question(s)</span>
                                    </div>
                                    <p>${escapeHtml(group.chapter)} | ${escapeHtml(group.difficulty)}</p>
                                    <ul>${renderList(group.questions)}</ul>
                                </article>
                            `).join("")}
                        </div>
                    </section>
                    <section class="result-card emphasis-card">
                        <h3>Most Probable Questions</h3>
                        <ul>${renderList(payload.probable_questions)}</ul>
                    </section>
                    <section class="result-card">
                        <h3>Must-Prepare Topics</h3>
                        <div class="badge-row">${payload.most_important_topics.map((item) => `<span class="chip">${escapeHtml(item)}</span>`).join("")}</div>
                    </section>
                    <section class="result-card">
                        <h3>Study Plan</h3>
                        <ul>${renderList(payload.study_plan)}</ul>
                        <p>${escapeHtml(payload.confidence_note)}</p>
                    </section>
                    <section class="result-card">
                        <h3>Practice Pack</h3>
                        <ul>${renderList(payload.practice_pack)}</ul>
                    </section>
                    <div class="button-row">
                        <button class="btn btn-primary" id="saveTrendLabBtn" type="button">Save To Vault</button>
                        <a class="btn btn-secondary" href="/notes?exam=${encodeURIComponent(byId("trendExam").value)}&topic=${encodeURIComponent(leadTopic)}">Build Notes</a>
                        <a class="btn btn-secondary" href="/mock?exam=${encodeURIComponent(byId("trendExam").value)}&topic=${encodeURIComponent(leadTopic)}">Practice Probables</a>
                    </div>
                    <p id="trendLabSaveStatus" class="status-line"></p>
                </div>
            `;

            byId("saveTrendLabBtn").addEventListener("click", () => {
                saveArtifact(
                    {
                        artifact_type: "trend_lab",
                        title: payload.headline,
                        source_topic: leadTopic,
                        summary: payload.trend_summary,
                        content: JSON.stringify(payload, null, 2),
                        metadata: {
                            exam: byId("trendExam").value,
                            course_title: byId("trendCourseTitle").value,
                            provider: payload.provider,
                        },
                    },
                    "trendLabSaveStatus"
                );
            });
        } catch (error) {
            output.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
        }
    });
}

async function initVaultPage() {
    const grid = byId("vaultGrid");
    const spotlight = byId("vaultSpotlight");
    if (!grid || !spotlight) {
        return;
    }

    const response = await fetch(`/api/vault?username=${encodeURIComponent(getActiveUser())}`);
    const payload = await response.json();

    byId("vaultTotal").textContent = payload.stats.total;
    byId("vaultNotes").textContent = payload.stats.notes;
    byId("vaultSummaries").textContent = payload.stats.summaries;
    byId("vaultPlans").textContent = payload.stats.plans;
    if (byId("vaultVideo")) {
        byId("vaultVideo").textContent = payload.stats.video || 0;
    }
    if (byId("vaultPredictors")) {
        byId("vaultPredictors").textContent = payload.stats.predictors || 0;
    }
    byId("vaultProfessor").textContent = payload.stats.professor;
    if (byId("vaultStudio")) {
        byId("vaultStudio").textContent = payload.stats.studio || 0;
    }

    spotlight.innerHTML = payload.spotlight
        ? `
            <div class="artifact-card artifact-spotlight">
                <div class="artifact-top">
                    <span class="chip">${escapeHtml(artifactLabel(payload.spotlight.artifact_type))}</span>
                    <span class="artifact-time">${escapeHtml(payload.spotlight.created_at)}</span>
                </div>
                <h2>${escapeHtml(payload.spotlight.title)}</h2>
                <p>${escapeHtml(payload.spotlight.preview)}</p>
                ${payload.is_guest ? `<p class="mini-note">Log in to maintain your own named personal vault.</p>` : ""}
            </div>
        `
        : `<div class="empty-state">Your Vault is empty. Save notes, summaries, war plans, and professor reviews to populate it.</div>`;

    grid.innerHTML = payload.items.length
        ? payload.items.map(renderArtifactCard).join("")
        : `<div class="empty-state compact-empty">No saved artifacts yet.</div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
    document.body.dataset.motion = MOTION_MODE;
    await fetchAiStatus();
    initCursorGlow();
    initScrollProgress();
    initRevealMotion();
    initMagneticButtons();
    apply3DTilt();

    if (bodyPage === "notes") {
        initNotesPage();
    }
    if (bodyPage === "pyq_lab") {
        initPyqLabPage();
    }
    if (bodyPage === "video_notes") {
        initVideoNotesPage();
    }
    if (bodyPage === "exam_atlas") {
        initExamAtlasPage();
    }
    if (bodyPage === "summarizer") {
        initSummaryPage();
    }
    if (bodyPage === "ai_studio") {
        initAiStudioPage();
    }
    if (bodyPage === "trend_lab") {
        initTrendLabPage();
    }
    if (bodyPage === "login") {
        initAuthPage();
    }
    if (bodyPage === "mock") {
        initMockPage();
    }
    if (bodyPage === "dashboard") {
        initDashboardPage();
    }
    if (bodyPage === "pass_pathfinder") {
        initPassPathfinderPage();
    }
    if (bodyPage === "war_room") {
        initWarRoomPage();
    }
    if (bodyPage === "professor_lab") {
        initProfessorLabPage();
    }
    if (bodyPage === "vault") {
        initVaultPage();
    }
});
