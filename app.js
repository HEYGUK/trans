document.addEventListener("DOMContentLoaded", () => {
    // ==================== 元素引用 ====================
    const $ = (sel) => document.querySelector(sel);
    const sourceText    = $("#source-text");
    const resultText    = $("#result-text");
    const charCount     = $("#char-count");
    const translateTime = $("#translate-time");
    const langPair      = $("#lang-pair");
    const subjectSel    = $("#subject");
    const btnTranslate  = $("#btn-translate");
    const btnClear      = $("#btn-clear");
    const btnPaste      = $("#btn-paste");
    const btnCopy       = $("#btn-copy");
    const btnSwap       = $("#btn-swap");
    const btnTerms      = $("#btn-terms");
    const termsPanel    = $("#terms-panel");
    const termsContent  = $("#terms-content");
    const btnCloseTerms = $("#btn-close-terms");
    const historyList   = $("#history-list");
    const btnClearHist  = $("#btn-clear-history");
    const modelBadge    = $("#model-badge");
    const modeTabs      = document.querySelectorAll(".mode-tab");

    let currentMode  = "general";
    let isTranslating = false;
    let history = JSON.parse(localStorage.getItem("th") || "[]");

    const MODE_LABELS = {
        general: "通用", academic: "学术",
        daily: "日常", email: "邮件", polish: "润色",
    };

    // ==================== 初始化 ====================
    renderHistory();
    fetchModelInfo();

    async function fetchModelInfo() {
        try {
            const res = await fetch("/api/model-info");
            const data = await res.json();
            modelBadge.textContent = `⭐ ${data.model}`;
        } catch {
            modelBadge.textContent = "⭐ OpenRouter";
        }
    }

    // ==================== 模式切换 ====================
    modeTabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            modeTabs.forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");
            currentMode = tab.dataset.mode;
        });
    });

    // ==================== 字数统计 ====================
    sourceText.addEventListener("input", () => {
        const len = sourceText.value.length;
        charCount.textContent = `${len} / 10000`;
        charCount.style.color = len > 9000 ? "var(--danger)" : "";
    });

    // ==================== 清空 ====================
    btnClear.addEventListener("click", () => {
        sourceText.value = "";
        resultText.innerHTML = '<p class="placeholder-text">翻译结果将显示在这里...</p>';
        charCount.textContent = "0 / 10000";
        translateTime.textContent = "";
    });

    // ==================== 粘贴 ====================
    btnPaste.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            sourceText.value = text;
            sourceText.dispatchEvent(new Event("input"));
            showToast("已粘贴", "success");
        } catch {
            showToast("无法读取剪贴板", "error");
        }
    });

    // ==================== 复制 ====================
    btnCopy.addEventListener("click", () => {
        const text = resultText.innerText;
        if (!text || text.includes("翻译结果将显示在这里")) return;
        navigator.clipboard.writeText(text).then(() => {
            showToast("✅ 已复制到剪贴板", "success");
        });
    });

    // ==================== 语言互换 ====================
    btnSwap.addEventListener("click", () => {
        const val = langPair.value;
        if (val === "auto") {
            showToast("自动模式无法互换", "info");
            return;
        }
        const [src, tgt] = val.split("-");
        const swapped = `${tgt}-${src}`;
        // 检查是否存在该选项
        const opt = [...langPair.options].find((o) => o.value === swapped);
        if (opt) {
            langPair.value = swapped;
            // 把译文放到原文框
            const resultContent = resultText.innerText;
            if (resultContent && !resultContent.includes("翻译结果将显示在这里")) {
                sourceText.value = resultContent;
                sourceText.dispatchEvent(new Event("input"));
                resultText.innerHTML = '<p class="placeholder-text">点击翻译...</p>';
            }
            showToast("🔄 已互换语言方向", "info");
        } else {
            showToast("不支持该语言方向互换", "error");
        }
    });

    // ==================== 翻译（流式） ====================
    btnTranslate.addEventListener("click", startTranslate);

    sourceText.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            startTranslate();
        }
    });

    async function startTranslate() {
        const text = sourceText.value.trim();
        if (!text) {
            showToast("请输入要翻译的文本", "error");
            return;
        }
        if (isTranslating) return;

        setLoading(true);
        resultText.innerHTML = "";
        translateTime.textContent = "";
        const startTime = Date.now();

        try {
            const response = await fetch("/api/translate/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text,
                    lang_pair: langPair.value,
                    mode: currentMode,
                    subject: subjectSel.value,
                }),
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullResult = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split("\n");

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.error) {
                            resultText.innerHTML = `<span style="color:var(--danger)">❌ ${data.error}</span>`;
                            break;
                        }
                        if (data.text) {
                            fullResult += data.text;
                            resultText.innerText = fullResult;
                            resultText.scrollTop = resultText.scrollHeight;
                        }
                    } catch { /* skip bad json */ }
                }
            }

            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
            translateTime.textContent = `${elapsed}s`;

            if (fullResult) {
                addHistory(text, fullResult, currentMode);
            }
        } catch (e) {
            resultText.innerHTML = `<span style="color:var(--danger)">❌ 请求失败: ${e.message}</span>`;
        } finally {
            setLoading(false);
        }
    }

    function setLoading(state) {
        isTranslating = state;
        btnTranslate.disabled = state;
        btnTranslate.querySelector(".btn-icon").style.display = state ? "none" : "";
        btnTranslate.querySelector(".btn-text").style.display = state ? "none" : "";
        btnTranslate.querySelector(".btn-loading").style.display = state ? "flex" : "none";
    }

    // ==================== 术语提取 ====================
    btnTerms.addEventListener("click", async () => {
        const text = sourceText.value.trim();
        if (!text) {
            showToast("请先输入文本", "error");
            return;
        }

        termsContent.innerHTML = '<p class="placeholder-text">⏳ 正在提取术语...</p>';
        termsPanel.classList.remove("hidden");

        try {
            const res = await fetch("/api/detect-terms", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, subject: subjectSel.value }),
            });
            const data = await res.json();

            if (data.error) {
                termsContent.innerHTML = `<p style="color:var(--danger)">❌ ${data.error}</p>`;
                return;
            }

            if (data.terms && data.terms.length > 0) {
                let html = `<table>
                    <thead><tr><th>术语原文</th><th>翻译</th></tr></thead><tbody>`;
                data.terms.forEach((t) => {
                    html += `<tr><td>${escapeHtml(t.term)}</td><td>${escapeHtml(t.translation)}</td></tr>`;
                });
                html += "</tbody></table>";
                termsContent.innerHTML = html;
            } else {
                termsContent.innerHTML = '<p class="placeholder-text">未检测到专业术语</p>';
            }
        } catch (e) {
            termsContent.innerHTML = `<p style="color:var(--danger)">❌ ${e.message}</p>`;
        }
    });

    btnCloseTerms.addEventListener("click", () => {
        termsPanel.classList.add("hidden");
    });

    // ==================== 历史记录 ====================
    function addHistory(source, result, mode) {
        const item = {
            source: source.substring(0, 200),
            result: result.substring(0, 200),
            fullSource: source,
            fullResult: result,
            mode,
            time: new Date().toLocaleString("zh-CN"),
        };
        history.unshift(item);
        if (history.length > 30) history.pop();
        localStorage.setItem("th", JSON.stringify(history));
        renderHistory();
    }

    function renderHistory() {
        if (history.length === 0) {
            historyList.innerHTML = '<p class="placeholder-text">暂无翻译历史</p>';
            return;
        }
        historyList.innerHTML = history
            .map(
                (h, i) => `
            <div class="history-item" data-idx="${i}">
                <div class="meta">
                    <span>${h.time}</span>
                    <span class="tag">${MODE_LABELS[h.mode] || h.mode}</span>
                </div>
                <div class="preview">${escapeHtml(h.source)}</div>
            </div>`
            )
            .join("");

        historyList.querySelectorAll(".history-item").forEach((el) => {
            el.addEventListener("click", () => {
                const item = history[el.dataset.idx];
                sourceText.value = item.fullSource;
                resultText.innerText = item.fullResult;
                sourceText.dispatchEvent(new Event("input"));
                showToast("已加载历史记录", "info");
            });
        });
    }

    btnClearHist.addEventListener("click", () => {
        if (history.length === 0) return;
        history = [];
        localStorage.removeItem("th");
        renderHistory();
        showToast("历史已清空", "success");
    });

    // ==================== 工具函数 ====================
    function showToast(msg, type = "success") {
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2600);
    }

    function escapeHtml(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
