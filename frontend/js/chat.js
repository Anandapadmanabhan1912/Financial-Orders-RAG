const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const asOfDateInput = document.getElementById('as-of-date-input');
const clearDateBtn = document.getElementById('clear-date-btn');

if (clearDateBtn) {
    clearDateBtn.addEventListener('click', () => {
        asOfDateInput.value = '';
    });
}

function sendSuggestedQuery(text) {
    chatInput.value = text;
    handleSend();
}

if (sendBtn) {
    sendBtn.addEventListener('click', handleSend);
}

if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });
}

async function handleSend() {
    const query = chatInput.value.trim();
    if (!query) return;

    const asOfDate = asOfDateInput ? asOfDateInput.value : '';

    // Append User Message
    appendUserMessage(query, asOfDate);
    chatInput.value = '';

    // Append Loading Indicator
    const loadingId = appendLoadingMessage();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                as_of_date: asOfDate || null
            })
        });

        const data = await res.json();
        removeLoadingMessage(loadingId);

        if (res.ok) {
            appendAssistantMessage(data);
        } else {
            appendErrorMessage(data.detail || "Failed to process chat query.");
        }
    } catch (e) {
        removeLoadingMessage(loadingId);
        appendErrorMessage("Network error connecting to ORDERWISE backend.");
    }
}

function appendUserMessage(text, asOfDate) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user-message';
    
    let dateTag = asOfDate ? `<div style="font-size:0.75rem; color:#93c5fd; margin-bottom:0.2rem;">⏳ As-Of Date: ${asOfDate}</div>` : '';
    
    msgDiv.innerHTML = `
        <div class="avatar">You</div>
        <div class="message-content">
            ${dateTag}
            <div>${text}</div>
        </div>
    `;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendLoadingMessage() {
    const id = 'msg-loading-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.id = id;
    msgDiv.className = 'message assistant-message';
    msgDiv.innerHTML = `
        <div class="avatar">OW</div>
        <div class="message-content">
            <div style="display:flex; align-items:center; gap:0.5rem;">
                <div class="spinner" style="width:16px; height:16px;"></div>
                <span style="font-size:0.85rem; color:var(--text-secondary);">Traversing version DAG, evaluating BM25 & Vector candidates...</span>
            </div>
        </div>
    `;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeLoadingMessage(id) {
    const elem = document.getElementById(id);
    if (elem) elem.remove();
}

function appendErrorMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant-message';
    msgDiv.innerHTML = `
        <div class="avatar">OW</div>
        <div class="message-content" style="border-color:#ef4444; background:rgba(239,68,68,0.1);">
            <div style="color:#fca5a5; font-size:0.85rem;">⚠️ ${text}</div>
        </div>
    `;
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatMarkdown(text) {
    if (!text) return '';
    if (typeof marked !== 'undefined' && marked.parse) {
        try {
            return marked.parse(text);
        } catch (e) {
            console.error("marked.parse error:", e);
        }
    }
    // Simple fallback renderer
    let html = text
        .replace(/### (.*?)\n/g, '<h3>$1</h3>')
        .replace(/#### (.*?)\n/g, '<h4>$1</h4>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n\n/g, '<br/><br/>');
    return html;
}

function appendAssistantMessage(data) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant-message';

    const status = data.status || 'CURRENT';
    const formattedAnswer = formatMarkdown(data.answer || '');
    
    // Format sources
    let sourcesHtml = '';
    if (data.sources && data.sources.length > 0) {
        sourcesHtml = '<div class="sources-list">';
        data.sources.forEach(s => {
            const cleanGo = s.go_number || s.document_id;
            sourcesHtml += `
                <button class="source-chip" onclick="openSourceDrawer('${s.document_id}', ${s.page || 1}, \`${(s.snippet || '').replace(/`/g, "'")}\`, '${cleanGo}')">
                    📄 ${cleanGo} (Pg ${s.page || 1})
                </button>
            `;
        });
        sourcesHtml += '</div>';
    }

    // Format tool trace
    let traceHtml = '';
    if (data.tool_trace) {
        const t = data.tool_trace;
        traceHtml = `
            <details class="tool-trace-toggle">
                <summary>🛠️ Tool Execution & Retrieval Trace (BM25: ${t.bm25_matches}, Vector: ${t.vector_matches})</summary>
                <div class="tool-trace-body">
                    <div><b>RRF Merged Evidence Candidates:</b> ${t.candidate_chunks} chunks evaluated</div>
                    ${t.evidence_used.map(e => `<div>• Doc: <b>${e.go_number}</b> (Pg ${e.page}) | RRF Score: ${e.rrf_score}</div>`).join('')}
                </div>
            </details>
        `;
    }

    // Format warnings
    let warningsHtml = '';
    if (data.warnings && data.warnings.length > 0) {
        warningsHtml = data.warnings.map(w => `<div class="warning-box">⚠️ ${w}</div>`).join('');
    }

    // Format Version History
    let historyHtml = '';
    if (data.version_history && data.version_history.length > 0) {
        historyHtml = `
            <div style="margin-top:0.75rem; font-size:0.8rem; background:var(--bg-main); padding:0.5rem; border-radius:4px;">
                <div style="font-weight:600; color:var(--text-muted); margin-bottom:0.25rem;">VERSION HISTORY DAG</div>
                ${data.version_history.map(vh => `<div>• ${vh}</div>`).join('')}
            </div>
        `;
    }

    msgDiv.innerHTML = `
        <div class="avatar">OW</div>
        <div class="message-content">
            <span class="answer-status-pill ${status}">${status}</span>
            <div class="markdown-body">${formattedAnswer}</div>
            
            ${historyHtml}
            ${warningsHtml}
            ${sourcesHtml}
            ${traceHtml}
        </div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}
