// Navigation Tab Switching
document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-page').forEach(p => p.classList.remove('active'));

        btn.classList.add('active');
        const tabId = btn.getAttribute('data-tab');
        document.getElementById(tabId).classList.add('active');

        if (tabId === 'repository-tab') {
            loadRepositoryDocs();
        }
    });
});

// Load and Render Ingested Documents & Repository
async function loadRepositoryDocs() {
    const repoContainer = document.getElementById('repository-list');
    repoContainer.innerHTML = '<div class="spinner"></div>';

    try {
        const res = await fetch('/api/documents');
        const data = await res.json();

        if (data.status === 'success' && data.documents.length > 0) {
            repoContainer.innerHTML = '';
            data.documents.forEach(doc => {
                const card = document.createElement('div');
                card.className = 'doc-card';

                const statusClass = doc.status || 'CURRENT';
                let paramsHtml = '';

                if (doc.financial_params && Object.keys(doc.financial_params).length > 0) {
                    paramsHtml = '<div class="doc-params"><div class="doc-params-title">EXTRACTED PARAMETERS</div>';
                    if (doc.financial_params.monetary_amounts) {
                        paramsHtml += `<div>💰 <b>Financial Limit / Amount:</b> ${doc.financial_params.monetary_amounts.join(', ')}</div>`;
                    }
                    if (doc.financial_params.schedule_dates) {
                        paramsHtml += '<div>📅 <b>Schedules:</b> ';
                        for (const [dept, dateStr] of Object.entries(doc.financial_params.schedule_dates)) {
                            paramsHtml += `<br/>- ${dept}: <b>${dateStr}</b>`;
                        }
                        paramsHtml += '</div>';
                    }
                    paramsHtml += '</div>';
                }

                card.innerHTML = `
                    <div class="doc-card-header">
                        <div class="doc-go-no">${doc.go_number || doc.id}</div>
                        <span class="answer-status-pill ${statusClass}">${statusClass}</span>
                    </div>
                    <div class="doc-dept">${doc.department || 'FINANCE DEPARTMENT'}</div>
                    <div style="font-size:0.8rem; color:var(--text-muted);">Issued Date: <b>${doc.parsed_date || doc.date_str}</b></div>
                    <div class="doc-abstract">${doc.abstract || 'Kerala Finance Government Order'}</div>
                    ${paramsHtml}
                    <div style="margin-top:auto; padding-top:0.5rem; display:flex; justify-content:space-between; align-items:center;">
                        <button class="source-chip" onclick="openSourceDrawer('${doc.id}', 1, 'GO Government Order Document', '${doc.go_number}')">
                            📄 View Source Page
                        </button>
                    </div>
                `;
                repoContainer.appendChild(card);
            });
        } else {
            repoContainer.innerHTML = '<p style="color:var(--text-secondary)">No government orders ingested yet. Use the Upload tab to add PDFs.</p>';
        }
    } catch (e) {
        console.error("Error loading documents:", e);
        repoContainer.innerHTML = '<p style="color:var(--status-superseded)">Failed to connect to backend engine.</p>';
    }
}

// PDF Document Drag & Drop Uploader
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const uploadStatus = document.getElementById('upload-status');

if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--accent-blue)';
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'var(--border-light)';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border-light)';
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });
}

if (fileInput) {
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileUpload(fileInput.files[0]);
        }
    });
}

async function handleFileUpload(file) {
    if (!file.name.endsWith('.pdf')) {
        alert('Please select a valid PDF file.');
        return;
    }

    uploadStatus.style.display = 'flex';
    document.getElementById('upload-filename').innerText = `Ingesting ${file.name}...`;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        if (res.ok && data.status === 'success') {
            document.getElementById('upload-step').innerText = `Ingestion complete! Indexing GO ${data.details.go_number}...`;
            setTimeout(() => {
                uploadStatus.style.display = 'none';
                alert(`Successfully processed and indexed ${data.details.go_number}!`);
                loadRepositoryDocs();
            }, 1000);
        } else {
            alert(`Upload failed: ${data.detail || 'Unknown error'}`);
            uploadStatus.style.display = 'none';
        }
    } catch (e) {
        console.error("Upload error:", e);
        alert("Upload error. Check backend connection.");
        uploadStatus.style.display = 'none';
    }
}

// Side Drawer for Viewing Original Source PDF Page
function openSourceDrawer(docId, pageNum, snippet, goNo) {
    const drawer = document.getElementById('source-drawer');
    const drawerMeta = document.getElementById('drawer-meta');
    const previewImg = document.getElementById('drawer-preview-img');
    const snippetText = document.getElementById('drawer-snippet-text');

    drawerMeta.innerHTML = `<div><b>Order:</b> ${goNo || docId}</div><div><b>Page:</b> ${pageNum}</div>`;
    previewImg.src = `/api/documents/${docId}/preview/${pageNum}`;
    snippetText.innerText = snippet || 'Page Preview';

    drawer.classList.add('open');
}

function closeSourceDrawer() {
    document.getElementById('source-drawer').classList.remove('open');
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    loadRepositoryDocs();
});
