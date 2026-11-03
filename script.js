document.addEventListener('DOMContentLoaded', () => {
    // ---------------------------------------------------------
    // Existing Portal Elements
    // ---------------------------------------------------------
    const lostItemsContainer = document.getElementById('lost-items-container');
    const foundItemsContainer = document.getElementById('found-items-container');
    const itemReportForm = document.getElementById('item-report-form');
    const formMessage = document.getElementById('form-message');

    // ---------------------------------------------------------
    // AI Natural Language Search Elements
    // ---------------------------------------------------------
    const aiSearchInput = document.getElementById('ai-search-input');
    const aiSearchBtn = document.getElementById('ai-search-btn');
    const aiClearBtn = document.getElementById('ai-clear-btn');
    const aiLoading = document.getElementById('ai-loading');
    const aiSetupNotice = document.getElementById('ai-setup-notice');
    const aiErrorNotice = document.getElementById('ai-error-notice');
    const aiErrorText = document.getElementById('ai-error-text');
    const aiSummaryCard = document.getElementById('ai-summary-card');
    const aiSummaryText = document.getElementById('ai-summary-text');
    const aiResultsWrapper = document.getElementById('ai-results-wrapper');
    const aiResultsContainer = document.getElementById('ai-results-container');
    const aiResultsCount = document.getElementById('ai-results-count');
    const aiResetResultsBtn = document.getElementById('ai-reset-results-btn');
    const aiEmptyState = document.getElementById('ai-empty-state');
    const aiEmptyText = document.getElementById('ai-empty-text');

    // ---------------------------------------------------------
    // Admin Authorization & Modal Elements
    // ---------------------------------------------------------
    const adminAuthBtn = document.getElementById('admin-auth-btn');
    const adminBanner = document.getElementById('admin-banner');
    const adminLogoutBtn = document.getElementById('admin-logout-btn');
    const adminModal = document.getElementById('admin-modal');
    const adminModalClose = document.getElementById('admin-modal-close');
    const adminModalCancel = document.getElementById('admin-modal-cancel');
    const adminLoginForm = document.getElementById('admin-login-form');
    const adminKeyInput = document.getElementById('admin-key-input');
    const adminModalError = document.getElementById('admin-modal-error');
    const portalToast = document.getElementById('portal-toast');

    let toastTimer = null;

    // ---------------------------------------------------------
    // Toast Notification Utility
    // ---------------------------------------------------------
    function showToast(message, type = 'info') {
        if (!portalToast) return;
        portalToast.textContent = message;
        portalToast.className = `portal-toast ${type}`;
        portalToast.classList.remove('hidden');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => {
            portalToast.classList.add('hidden');
        }, 4000);
    }

    // ---------------------------------------------------------
    // Safe JSON Fetch Helper (Handles Empty & Non-JSON Responses)
    // ---------------------------------------------------------
    async function safeFetchJson(url, options = {}) {
        let response;
        try {
            response = await fetch(url, options);
        } catch (netErr) {
            const err = new Error('Network error. Unable to connect to server. Please check your connection.');
            err.isNetwork = true;
            throw err;
        }

        const contentType = (response.headers.get('content-type') || '').toLowerCase();
        let text = '';
        try {
            text = await response.text();
        } catch (readErr) {
            text = '';
        }

        let data = null;
        if (text && (contentType.includes('application/json') || text.trim().startsWith('{') || text.trim().startsWith('['))) {
            try {
                data = JSON.parse(text);
            } catch (parseErr) {
                data = null;
            }
        }

        if (!response.ok) {
            let errorMsg = '';
            if (data && typeof data === 'object' && data.message) {
                errorMsg = data.message;
            } else if (response.status === 404) {
                errorMsg = 'Requested resource not found.';
            } else if (response.status === 403 || response.status === 401) {
                errorMsg = 'Unauthorized: Administrative credentials are required or invalid.';
            } else if (response.status >= 500) {
                errorMsg = 'The server encountered an error while processing the request.';
            } else {
                errorMsg = `Server returned status ${response.status}.`;
            }
            const err = new Error(errorMsg);
            err.status = response.status;
            err.data = data;
            throw err;
        }

        if (data === null) {
            return { success: true };
        }
        return data;
    }

    // ---------------------------------------------------------
    // Admin Authorization State Management
    // ---------------------------------------------------------
    function getAdminKey() {
        return sessionStorage.getItem('campus_admin_key') || '';
    }

    function isAdminLoggedIn() {
        return Boolean(getAdminKey());
    }

    function setAdminKey(key) {
        if (key && key.trim()) {
            sessionStorage.setItem('campus_admin_key', key.trim());
        } else {
            sessionStorage.removeItem('campus_admin_key');
        }
        updateAdminUIState();
        fetchItems();
    }

    function updateAdminUIState() {
        const loggedIn = isAdminLoggedIn();
        if (adminAuthBtn) {
            if (loggedIn) {
                adminAuthBtn.innerHTML = '🔓 Staff Mode (Active)';
                adminAuthBtn.classList.add('active');
            } else {
                adminAuthBtn.innerHTML = '🔐 Staff Login';
                adminAuthBtn.classList.remove('active');
            }
        }
        if (adminBanner) {
            if (loggedIn) {
                adminBanner.classList.remove('hidden');
            } else {
                adminBanner.classList.add('hidden');
            }
        }
    }

    function openAdminModal() {
        if (adminModal) {
            adminModal.classList.remove('hidden');
            if (adminModalError) adminModalError.classList.add('hidden');
            if (adminKeyInput) {
                adminKeyInput.value = '';
                setTimeout(() => adminKeyInput.focus(), 50);
            }
        }
    }

    function closeAdminModal() {
        if (adminModal) {
            adminModal.classList.add('hidden');
        }
    }

    if (adminAuthBtn) {
        adminAuthBtn.addEventListener('click', () => {
            if (isAdminLoggedIn()) {
                if (window.confirm('You are currently logged in as Staff. Do you want to log out?')) {
                    setAdminKey('');
                    showToast('Logged out of Staff Mode.', 'info');
                }
            } else {
                openAdminModal();
            }
        });
    }

    if (adminLogoutBtn) {
        adminLogoutBtn.addEventListener('click', () => {
            setAdminKey('');
            showToast('Logged out of Staff Mode.', 'info');
        });
    }

    if (adminModalClose) adminModalClose.addEventListener('click', closeAdminModal);
    if (adminModalCancel) adminModalCancel.addEventListener('click', closeAdminModal);

    if (adminLoginForm) {
        adminLoginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const key = adminKeyInput ? adminKeyInput.value.trim() : '';
            if (!key) return;

            const submitBtn = document.getElementById('admin-modal-submit');
            if (submitBtn) submitBtn.disabled = true;

            try {
                const res = await safeFetchJson('/api/admin/verify', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Admin-Key': key
                    },
                    body: JSON.stringify({ admin_key: key })
                });

                if (res.success) {
                    setAdminKey(key);
                    closeAdminModal();
                    showToast('✅ Administrator authorization verified. Staff Mode active.', 'success');
                } else {
                    if (adminModalError) {
                        adminModalError.textContent = res.message || 'Invalid administrator key.';
                        adminModalError.classList.remove('hidden');
                    }
                }
            } catch (err) {
                if (adminModalError) {
                    adminModalError.textContent = err.message || 'Verification failed. Please check the admin key.';
                    adminModalError.classList.remove('hidden');
                }
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        });
    }

    // ---------------------------------------------------------
    // Secure Item Deletion Handler
    // ---------------------------------------------------------
    async function handleDeleteItem(itemId, itemName, cardElement, deleteBtn) {
        const adminKey = getAdminKey();
        if (!adminKey) {
            showToast('❌ Administrator credentials required to delete items.', 'error');
            openAdminModal();
            return;
        }

        const confirmMsg = `Are you sure you want to permanently delete "${itemName}" (Report #${itemId})?\n\nThis will remove the report, its AI vector embeddings, and related match records. This action cannot be undone.`;
        if (!window.confirm(confirmMsg)) {
            return;
        }

        deleteBtn.disabled = true;
        const originalContent = deleteBtn.innerHTML;
        deleteBtn.innerHTML = '⏳ Deleting...';

        try {
            const res = await safeFetchJson(`/api/items/${itemId}`, {
                method: 'DELETE',
                headers: {
                    'X-Admin-Key': adminKey
                }
            });

            showToast(`✅ ${res.message || 'Item deleted successfully.'}`, 'success');

            // Smoothly remove card from displayed list without requiring full page reload
            if (cardElement) {
                cardElement.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
                cardElement.style.opacity = '0';
                cardElement.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    cardElement.remove();
                }, 250);
            }
        } catch (err) {
            console.error('Item deletion error:', err);
            showToast(`❌ Deletion failed: ${err.message}`, 'error');
            deleteBtn.disabled = false;
            deleteBtn.innerHTML = originalContent;
        }
    }

    // ---------------------------------------------------------
    // AI Natural Search Functions
    // ---------------------------------------------------------
    function updateClearButtonVisibility() {
        if (aiSearchInput.value.trim().length > 0) {
            aiClearBtn.classList.remove('hidden');
        } else {
            aiClearBtn.classList.add('hidden');
        }
    }

    function clearAISearch() {
        aiSearchInput.value = '';
        updateClearButtonVisibility();
        aiLoading.classList.add('hidden');
        aiSetupNotice.classList.add('hidden');
        aiErrorNotice.classList.add('hidden');
        aiSummaryCard.classList.add('hidden');
        aiResultsWrapper.classList.add('hidden');
        aiEmptyState.classList.add('hidden');
        aiResultsContainer.innerHTML = '';
        aiSearchInput.focus();
    }

    async function executeAISearch() {
        const query = aiSearchInput.value.trim();
        if (!query) {
            aiSearchInput.focus();
            aiSearchInput.style.borderColor = '#ef4444';
            setTimeout(() => {
                aiSearchInput.style.borderColor = '';
            }, 1200);
            return;
        }

        const scopeRadio = document.querySelector('input[name="search-scope"]:checked');
        const scope = scopeRadio ? scopeRadio.value : 'all';

        // Reset UI states
        aiErrorNotice.classList.add('hidden');
        aiSetupNotice.classList.add('hidden');
        aiSummaryCard.classList.add('hidden');
        aiResultsWrapper.classList.add('hidden');
        aiEmptyState.classList.add('hidden');
        aiResultsContainer.innerHTML = '';

        // Show loading state
        aiLoading.classList.remove('hidden');
        aiSearchBtn.disabled = true;

        try {
            const data = await safeFetchJson('/api/ai/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: query,
                    scope: scope,
                    limit: 6
                })
            });

            // 1. Check OpenAI API Key status
            if (!data.api_key_configured) {
                aiSetupNotice.classList.remove('hidden');
            } else if (data.llm_response) {
                aiSummaryText.textContent = data.llm_response;
                aiSummaryCard.classList.remove('hidden');
            }

            // 2. Render Results
            const items = data.results || [];
            if (items.length > 0) {
                aiResultsWrapper.classList.remove('hidden');
                aiResultsCount.textContent = `${items.length} Potential Match${items.length > 1 ? 'es' : ''} Retrieved from Database`;

                items.forEach(item => {
                    const card = createResultCard(item);
                    aiResultsContainer.appendChild(card);
                });
            } else {
                aiEmptyState.classList.remove('hidden');
                aiEmptyText.textContent = `No active items in the database match "${query}".`;
            }

        } catch (error) {
            console.error('AI search failed:', error);
            aiErrorText.textContent = error.message || 'An error occurred while connecting to the AI search service.';
            aiErrorNotice.classList.remove('hidden');
        } finally {
            aiLoading.classList.add('hidden');
            aiSearchBtn.disabled = false;
        }
    }

    function createResultCard(item) {
        const card = document.createElement('div');
        card.classList.add('item-card');

        // Score badge calculation
        const scorePct = Math.round((item.similarity_score || 0) * 100);
        let badgeClass = 'low';
        let badgeIcon = 'ℹ️';

        if (scorePct >= 65) {
            badgeClass = 'strong';
            badgeIcon = '🔥';
        } else if (scorePct >= 40) {
            badgeClass = 'possible';
            badgeIcon = '⚡';
        }

        const confidenceLabel = item.confidence || 'Possible match';
        const evidenceList = item.evidence || [];
        const evidenceHtml = evidenceList.length > 0 
            ? `<div class="evidence-box">
                <strong>Matching Evidence:</strong>
                ${evidenceList.map(ev => `<span class="evidence-pill">✓ ${escapeHtml(ev)}</span>`).join('')}
               </div>`
            : '';

        const typeLabel = item.type === 'lost' ? '📱 Lost Report' : '🔍 Found Item';
        const dateStr = item.item_date || (item.reported_at ? item.reported_at.substring(0, 10) : 'Not specified');

        card.innerHTML = `
            <div class="match-score-badge ${badgeClass}">
                ${badgeIcon} ${scorePct}% Match · ${confidenceLabel}
            </div>
            <h3>${escapeHtml(item.item_name || 'Unknown Item')}</h3>
            <p><strong>Type:</strong> ${typeLabel}</p>
            <p><strong>Category:</strong> ${escapeHtml(item.category || 'Other')}</p>
            <p><strong>Description:</strong> ${escapeHtml(item.description || 'No description provided')}</p>
            <p><strong>Location:</strong> ${escapeHtml(item.location || 'Not specified')}</p>
            <p><strong>Date:</strong> ${escapeHtml(dateStr)}</p>
            <p><strong>Status:</strong> <span style="text-transform: capitalize; color: #15803d; font-weight: bold;">${escapeHtml(item.status || 'active')}</span></p>
            ${evidenceHtml}
        `;

        // Admin-only Delete Button
        if (isAdminLoggedIn() && item.id) {
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-item-btn';
            deleteBtn.type = 'button';
            deleteBtn.innerHTML = '🗑️ Delete Report';
            deleteBtn.title = `Delete item #${item.id}`;
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                handleDeleteItem(item.id, item.item_name || 'Item', card, deleteBtn);
            });
            card.appendChild(deleteBtn);
        }

        return card;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // AI Search Event Listeners
    aiSearchBtn.addEventListener('click', executeAISearch);

    aiSearchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            executeAISearch();
        }
    });

    aiSearchInput.addEventListener('input', updateClearButtonVisibility);
    aiClearBtn.addEventListener('click', clearAISearch);
    aiResetResultsBtn.addEventListener('click', clearAISearch);

    // ---------------------------------------------------------
    // Existing Items Browsing & Reporting
    // ---------------------------------------------------------
    async function fetchItems() {
        const headers = {};
        const adminKey = getAdminKey();
        if (adminKey) {
            headers['X-Admin-Key'] = adminKey;
        }

        try {
            const items = await safeFetchJson('/api/items', { headers });

            lostItemsContainer.innerHTML = '';
            foundItemsContainer.innerHTML = '';

            if (!Array.isArray(items) || items.length === 0) {
                lostItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #64748b;">No active lost items reported yet.</p></div>';
                foundItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #64748b;">No active found items reported yet.</p></div>';
                return;
            }

            let lostCount = 0;
            let foundCount = 0;

            items.forEach(item => {
                const itemCard = document.createElement('div');
                itemCard.classList.add('item-card');
                const dateStr = item.reported_at ? new Date(item.reported_at).toLocaleDateString() : 'Not specified';

                itemCard.innerHTML = `
                    <h3>${escapeHtml(item.item_name || item.name || 'Unknown Item')}</h3>
                    <p><strong>Type:</strong> ${item.type === 'lost' ? '📱 Lost Item' : '🔍 Found Item'}</p>
                    <p><strong>Category:</strong> ${escapeHtml(item.category || 'Other')}</p>
                    <p><strong>Description:</strong> ${escapeHtml(item.description || 'No description provided')}</p>
                    <p><strong>Location:</strong> ${escapeHtml(item.location || 'Not specified')}</p>
                    <p><strong>Student:</strong> ${escapeHtml(item.student_name || 'Protected')}</p>
                    <p><strong>Department:</strong> ${escapeHtml(item.department || 'Not specified')}</p>
                    <p><strong>Year:</strong> ${escapeHtml(item.year_of_study || 'Not specified')}</p>
                    <p><strong>Reported:</strong> ${escapeHtml(dateStr)}</p>
                    <p><em>📞 Contact: ${escapeHtml(item.contact_number || 'Protected')}</em></p>
                    <p><em>📧 Email: ${escapeHtml(item.contact_email || 'Protected')}</em></p>
                `;

                // Admin-only Delete Button
                if (isAdminLoggedIn() && item.id) {
                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'delete-item-btn';
                    deleteBtn.type = 'button';
                    deleteBtn.innerHTML = '🗑️ Delete Report';
                    deleteBtn.title = `Delete item #${item.id}`;
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        handleDeleteItem(item.id, item.item_name || item.name || 'Item', itemCard, deleteBtn);
                    });
                    itemCard.appendChild(deleteBtn);
                }

                if (item.type === 'lost') {
                    lostItemsContainer.appendChild(itemCard);
                    lostCount++;
                } else {
                    foundItemsContainer.appendChild(itemCard);
                    foundCount++;
                }
            });

            if (lostCount === 0) {
                lostItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #64748b;">No active lost items reported yet.</p></div>';
            }
            if (foundCount === 0) {
                foundItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #64748b;">No active found items reported yet.</p></div>';
            }
        } catch (error) {
            console.error('Error fetching items:', error);
            lostItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #dc3545;">❌ Could not load lost items. Please try again later.</p></div>';
            foundItemsContainer.innerHTML = '<div class="item-card"><p style="text-align: center; color: #dc3545;">❌ Could not load found items. Please try again later.</p></div>';
        }
    }

    // Function to handle form submission
    itemReportForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const formData = new FormData(itemReportForm);
        const itemData = Object.fromEntries(formData.entries());

        const submitBtn = itemReportForm.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        try {
            const result = await safeFetchJson('/api/items', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(itemData)
            });

            formMessage.textContent = '✅ Item reported successfully! Your report has been saved and indexed for AI search.';
            formMessage.style.color = 'green';
            itemReportForm.reset();
            fetchItems();
            showToast('✅ Report submitted successfully!', 'success');
        } catch (error) {
            console.error('Error submitting report:', error);
            formMessage.textContent = `❌ Error: ${error.message || 'Something went wrong. Please try again.'}`;
            formMessage.style.color = 'red';
            showToast(`❌ Report error: ${error.message}`, 'error');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });

    // Initialize UI
    updateAdminUIState();
    fetchItems();
});