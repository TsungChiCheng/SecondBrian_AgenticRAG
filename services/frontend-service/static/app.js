// Second Brain - Frontend JavaScript
class SecondBrainApp {
    constructor() {
        this.apiBase = this.getApiBase();
        this.sessionId = localStorage.getItem('sbSessionId') || null; // Persist conversation
        this.initializeElements();
        this.bindEvents();
        this.initializeTabs();
        this.initializePage();
        this.setExportAvailable(Boolean(this.sessionId));
    }

    getApiBase() {
        // Priority order:
        // 1. localStorage override (for debugging)
        // 2. Environment configuration from server
        // 3. Smart guess based on current host/port (helps with forwarded URLs like Codespaces)
        // 4. Default fallback
        const overrideApi = localStorage.getItem('apiBaseUrl');
        if (overrideApi) {
            console.log('🔧 Using API URL from localStorage:', overrideApi);
            return overrideApi;
        }

        // Use configuration from server (environment variable)
        if (window.APP_CONFIG && window.APP_CONFIG.apiBaseUrl) {
            console.log('✅ Using API URL from environment:', window.APP_CONFIG.apiBaseUrl);
            return window.APP_CONFIG.apiBaseUrl;
        }

        // Try to infer API URL from current location (common when ports are forwarded)
        const { protocol, hostname, port } = window.location;

        // If we have a numeric port (e.g., 8000 for frontend), assume API is next port (8001)
        if (port) {
            const portNumber = parseInt(port, 10);
            if (!Number.isNaN(portNumber)) {
                const guessedApi = `${protocol}//${hostname}:${portNumber + 1}`;
                console.log('🔧 Guessing API URL from port:', guessedApi);
                return guessedApi;
            }
        }

        // Handle forwarded hostnames like xxxx-8000.app.github.dev ➜ xxxx-8001.app.github.dev
        const forwardedMatch = hostname.match(/-(\d+)(?=\.)/);
        if (forwardedMatch) {
            const currentPort = parseInt(forwardedMatch[1], 10);
            const apiHost = hostname.replace(`-${forwardedMatch[1]}`, `-${currentPort + 1}`);
            const guessedApi = `${protocol}//${apiHost}`;
            console.log('🔧 Guessing API URL from forwarded host:', guessedApi);
            return guessedApi;
        }

        // Fallback
        const fallbackApi = `${protocol}//${hostname}:8001`;
        console.warn('⚠️ No API configuration found, using fallback:', fallbackApi);
        return fallbackApi;
    }

    getAuthHeaders() {
        // Get JWT token from session storage
        const session = localStorage.getItem('secondBrainSession');
        if (!session) {
            console.warn('⚠️ No authentication session found');
            return {};
        }

        try {
            const sessionData = JSON.parse(session);
            if (sessionData.token) {
                return {
                    'Authorization': `Bearer ${sessionData.token}`
                };
            }
        } catch (e) {
            console.error('Error parsing session:', e);
        }
        return {};
    }

    // ================================
    // Markdown Parsing Utility
    // ================================
    parseMarkdown(text) {
        if (!text) return '';
        
        // Extract markdown content from code blocks if present
        // Check for ```markdown ... ``` pattern
        const markdownBlockRegex = /```markdown\s*([\s\S]*?)\s*```/;
        const match = text.match(markdownBlockRegex);
        
        if (match) {
            console.log('📦 Found markdown code block, extracting content');
            text = match[1]; // Extract content inside the code block
        }
        
        // Check if libraries are loaded
        if (typeof marked === 'undefined') {
            console.warn('⚠️ marked.js not loaded, falling back to HTML escaping');
            return this.escapeHtml(text);
        }
        
        try {
            let html;
            
            // Handle different marked.js versions
            if (typeof marked === 'function') {
                // Older versions: marked is a function directly
                marked.setOptions && marked.setOptions({
                    breaks: true,
                    gfm: true,
                    headerIds: false,
                    mangle: false
                });
                html = marked(text);
                console.log('✅ Using marked() function API');
            } else if (typeof marked === 'object' && typeof marked.parse === 'function') {
                // Newer versions: marked is an object with parse method
                marked.use && marked.use({
                    breaks: true,
                    gfm: true,
                    headerIds: false,
                    mangle: false
                });
                html = marked.parse(text);
                console.log('✅ Using marked.parse() API');
            } else {
                console.error('❌ marked.js API not recognized. Type:', typeof marked);
                return this.escapeHtml(text);
            }
            
            // Sanitize HTML to prevent XSS attacks
            if (typeof DOMPurify !== 'undefined') {
                html = DOMPurify.sanitize(html, {
                    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'a', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'div', 'span'],
                    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'style', 'align']
                });
                console.log('✅ HTML sanitized with DOMPurify');
            } else {
                console.warn('⚠️ DOMPurify not loaded, skipping sanitization');
            }
            
            console.log('✅ Markdown parsed successfully, length:', html.length, 'chars');
            return html;
        } catch (error) {
            console.error('❌ Error parsing markdown:', error);
            console.error('   Text preview:', text.substring(0, 100));
            console.error('   Text length:', text.length);
            return this.escapeHtml(text);
        }
    }

    // ================================
    // HTML Utilities
    // ================================

    initializeElements() {
        // Chat elements
        this.promptInput = document.getElementById('prompt');
        this.sendBtn = document.getElementById('send');
        this.newSessionBtn = document.getElementById('new-session');
        this.summaryEl = document.getElementById('summary');
        this.answersEl = document.getElementById('answers');
        this.statusEl = document.getElementById('status');
        this.exportMarkdownBtn = document.getElementById('export-markdown');
        this.exportAvailable = false;
        this.isExportingMarkdown = false;
        
        // LLM selection checkboxes
        this.openaiCheck = document.getElementById('openai-check');
        // this.claudeCheck = document.getElementById('claude-check'); // Claude hidden from UI
        this.geminiCheck = document.getElementById('gemini-check');
        this.grokCheck = document.getElementById('grok-check');
        this.modelModeRadios = document.querySelectorAll('input[name="model-mode"]');

        // Search elements
        this.searchQuery = document.getElementById('search-query');
        this.vectorSearchBtn = document.getElementById('vector-search');
        this.loadTopicsBtn = document.getElementById('load-topics');
        this.loadStatsBtn = document.getElementById('load-stats');
        this.searchResults = document.getElementById('search-results');
        this.topicsResults = document.getElementById('topics-results');
        this.statsResults = document.getElementById('stats-results');

        // Tool elements
        this.dayInput = document.getElementById('day-input');
        this.summarizeBtn = document.getElementById('summarize');
        this.summaryResults = document.getElementById('summary-results');

        // Knowledge Graph elements
        this.showGraphBtn = document.getElementById('show-graph');
        this.zoomInGraphBtn = document.getElementById('zoom-in-graph');
        this.zoomOutGraphBtn = document.getElementById('zoom-out-graph');
        this.centerGraphBtn = document.getElementById('center-graph');
        this.closeGraphBtn = document.getElementById('close-graph');
        this.graphContainer = document.getElementById('knowledge-graph');
        this.graphVisualization = document.getElementById('graph-visualization');
        this.graphInfo = document.getElementById('graph-info');
        this.graphStatus = document.getElementById('graph-status');
        
        // Image search elements (now in main Ask section)
        this.imageInput = document.getElementById('image-input');
        this.selectImageBtn = document.getElementById('select-image');
        this.dropZone = document.getElementById('drop-zone');
        this.imagePreview = document.getElementById('image-preview');
        this.previewImg = document.getElementById('preview-img');
        this.clearImageBtn = document.getElementById('clear-image');
        this.imageAnalysisCard = document.getElementById('image-analysis-results');
        this.imageResultsContent = document.getElementById('image-results-content');
        this.imageAnalysisResults = document.getElementById('image-analysis-results'); // For clearing
        this.imageSearchResults = document.getElementById('image-results-content'); // For clearing and displaying search results
        this.imageStatus = document.getElementById('image-status'); // Optional status area (may be absent)
        this.selectedImageFile = null;
        this.cachedImageBase64 = null; // Initialize cached image data
        
        // Theme selector elements
        this.themeButtons = document.querySelectorAll('.theme-btn-inline');

        // Initialize response mode (default fast)
        this.initializeModelMode();
    }

    bindEvents() {
        // Chat events
        this.sendBtn.addEventListener('click', () => this.handleSendMessage());
        this.newSessionBtn?.addEventListener('click', () => this.handleNewSession());
        this.exportMarkdownBtn?.addEventListener('click', () => this.handleExportMarkdown());
        this.modelModeRadios?.forEach((radio) => {
            radio.addEventListener('change', () => {
                if (!radio.checked) return;
                const mode = radio.value === 'llm-wiki' ? 'llm-wiki' : 'fast';
                localStorage.setItem('sbModelMode', mode);
                this.applyModelMode(mode);
            });
        });
        this.promptInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.handleSendMessage();
            }
        });

        // Search events
        this.vectorSearchBtn.addEventListener('click', () => this.handleVectorSearch());
        this.loadTopicsBtn.addEventListener('click', () => this.handleLoadTopics());
        this.loadStatsBtn.addEventListener('click', () => this.handleLoadStats());
        this.searchQuery.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.handleVectorSearch();
            }
        });

        // Tool events
        this.summarizeBtn.addEventListener('click', () => this.handleDailySummarize());

        // Knowledge Graph events
        this.showGraphBtn.addEventListener('click', () => this.handleToggleGraph());
        this.zoomInGraphBtn.addEventListener('click', () => this.handleZoomInGraph());
        this.zoomOutGraphBtn.addEventListener('click', () => this.handleZoomOutGraph());
        this.centerGraphBtn.addEventListener('click', () => this.handleCenterGraph());
        this.closeGraphBtn.addEventListener('click', () => this.handleCloseGraph());
        
        // Image upload events (in main Ask section)
        console.log('📷 Setting up image events:');
        console.log('  selectImageBtn:', this.selectImageBtn);
        console.log('  imageInput:', this.imageInput);
        console.log('  clearImageBtn:', this.clearImageBtn);
        console.log('  dropZone:', this.dropZone);
        this.selectImageBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event from bubbling to dropZone
            console.log('📷 selectImageBtn clicked, triggering imageInput.click()');
            this.imageInput.click();
        });
        this.imageInput.addEventListener('change', (e) => {
            console.log('📷 imageInput change event fired, files:', e.target.files);
            this.handleImageSelect(e);
        });
        this.clearImageBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event from bubbling to dropZone
            this.handleClearImage();
        });
        
        // Drag and drop events
        // Only allow clicking drop zone if no image is selected
        this.dropZone.addEventListener('click', () => {
            console.log('📷 dropZone clicked, selectedImageFile:', this.selectedImageFile);
            if (!this.selectedImageFile) {
                this.imageInput.click();
            }
        });
        this.dropZone.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.dropZone.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.dropZone.addEventListener('drop', (e) => this.handleDrop(e));
        
        // Theme selector events
        console.log('🎨 Setting up theme buttons, found:', this.themeButtons.length);
        this.themeButtons.forEach((btn, index) => {
            console.log(`  Theme button ${index}:`, btn.dataset.theme, btn.textContent);
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const themeName = btn.dataset.theme;
                console.log('🎨 Theme button clicked:', themeName);
                if (window.themeManager) {
                    console.log('  Calling themeManager.setTheme...');
                    window.themeManager.setTheme(themeName);
                    console.log('  Calling updateActiveThemeButton...');
                    this.updateActiveThemeButton(themeName);
                    console.log('  ✅ Theme change complete');
                } else {
                    console.error('❌ ThemeManager not loaded!');
                }
            });
        });
    }

    initializeTabs() {
        console.log('🔧 Initializing tabs...');
        
        // Get all tab buttons and content sections
        const tabButtons = document.querySelectorAll('.tab-button');
        const tabContents = document.querySelectorAll('.tab-content');
        
        console.log(`📊 Found ${tabButtons.length} tab buttons`);
        console.log(`📊 Found ${tabContents.length} tab content sections`);

        // Add click event to each tab button
        tabButtons.forEach((button, index) => {
            console.log(`📌 Setting up tab button ${index}: ${button.getAttribute('data-tab')}`);
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const targetTab = button.getAttribute('data-tab');
                console.log(`🎯 Tab clicked: ${targetTab}`);
                
                // Remove active class from all buttons and contents
                tabButtons.forEach(btn => {
                    btn.classList.remove('active');
                    console.log(`  ➖ Removed active from button: ${btn.getAttribute('data-tab')}`);
                });
                tabContents.forEach(content => {
                    content.classList.remove('active');
                    console.log(`  ➖ Removed active from content: ${content.id}`);
                });
                
                // Add active class to clicked button and corresponding content
                button.classList.add('active');
                const targetContent = document.getElementById(`tab-${targetTab}`);
                if (targetContent) {
                    targetContent.classList.add('active');
                    console.log(`  ✅ Activated tab: ${targetTab}`);
                    console.log(`  ✅ Activated content: tab-${targetTab}`);
                } else {
                    console.error(`  ❌ Could not find content element: tab-${targetTab}`);
                }
                
                // Save active tab to localStorage
                localStorage.setItem('activeTab', targetTab);
            });
        });

        // Restore last active tab from localStorage
        const savedTab = localStorage.getItem('activeTab');
        if (savedTab) {
            console.log(`💾 Restoring saved tab: ${savedTab}`);
            const savedButton = document.querySelector(`[data-tab="${savedTab}"]`);
            if (savedButton) {
                savedButton.click();
            }
        } else {
            console.log('ℹ️ No saved tab found, using default');
        }
        
        console.log('✅ Tab initialization complete');
    }

    initializePage() {
        // Set current date as default
        const today = new Date().toISOString().split('T')[0];
        this.dayInput.value = today;
        
        // Check if markdown libraries are loaded
        console.log('📚 Checking markdown libraries...');
        console.log('  marked.js:', typeof marked !== 'undefined' ? '✅ Loaded' : '❌ Not loaded');
        if (typeof marked !== 'undefined') {
            console.log('  marked type:', typeof marked);
            console.log('  marked.parse:', typeof marked.parse);
            console.log('  marked object keys:', Object.keys(marked).slice(0, 10));
        }
        console.log('  DOMPurify:', typeof DOMPurify !== 'undefined' ? '✅ Loaded' : '❌ Not loaded');
        
        // Test markdown parsing
        const testMarkdown = '**Bold** and *italic*';
        console.log('🧪 Testing markdown parsing...');
        const testResult = this.parseMarkdown(testMarkdown);
        console.log('  Input:', testMarkdown);
        console.log('  Output:', testResult);
        
        // Clear any existing content
        this.clearResults();
        this.showStatus(window.languageManager.t('status.ready'), 'info');
        
        // Initialize theme selector UI
        this.initializeThemeSelector();

        // Verify backend reachability early and surface helpful error if misconfigured
        this.verifyApiReachability();
    }

    async verifyApiReachability() {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 4000);

        try {
            const response = await fetch(`${this.apiBase}/health`, { signal: controller.signal });
            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`${response.status} ${response.statusText}`);
            }

            console.log('✅ API reachable at', this.apiBase);
        } catch (error) {
            clearTimeout(timeoutId);
            console.error('❌ API unreachable at', this.apiBase, error);
            this.showStatus(
                `❌ Cannot reach API at ${this.apiBase}. Set API_BASE_URL or localStorage "apiBaseUrl" to the exposed backend URL.`,
                'error'
            );
        }
    }
    
    initializeThemeSelector() {
        if (!window.themeManager) {
            console.warn('ThemeManager not loaded yet');
            return;
        }
        
        // Update initial active state
        this.updateActiveThemeButton(window.themeManager.currentTheme);
        console.log('✅ Theme selector initialized with theme:', window.themeManager.currentTheme);
    }
    
    updateActiveThemeButton(themeName) {
        this.themeButtons.forEach(btn => {
            if (btn.dataset.theme === themeName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    async postJSON(endpoint, payload = {}) {
        const controller = new AbortController();
        // Use configured timeout or default to 150s (150000ms)
        const timeout = window.APP_CONFIG?.timeout || 150000;
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        // Get authentication token
        const authHeaders = this.getAuthHeaders();

        try {
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders  // ← Add authentication headers
                },
                body: JSON.stringify(payload),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            // Handle 401 Unauthorized - redirect to login
            if (response.status === 401) {
                console.warn('Authentication required, redirecting to login...');
                window.location.href = '/login.html';
                throw new Error('Authentication required. Redirecting to login...');
            }

            if (!response.ok) {
                let errorMessage = `${response.status} ${response.statusText}`;
                try {
                    const data = await response.json();
                    if (data.detail) {
                        errorMessage += `\n${data.detail}`;
                    }
                } catch (e) {
                    // Could not parse error JSON, use status text
                }
                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            console.error('❌ postJSON error:', error);  // Debug logging
            if (error.name === 'AbortError') {
                throw new Error('Request timed out. Please try again.');
            }
            throw error;
        }
    }

    setExportAvailable(available) {
        if (!this.exportMarkdownBtn) return;
        this.exportAvailable = Boolean(available);
        this.exportMarkdownBtn.disabled = this.isExportingMarkdown;
        this.exportMarkdownBtn.setAttribute('aria-disabled', String(!this.exportAvailable));
        this.exportMarkdownBtn.classList.toggle('is-unavailable', !this.exportAvailable);
        this.exportMarkdownBtn.title = available
            ? 'Download the current session as an LLM Wiki markdown file'
            : 'Ask a question or analyze an image before exporting an LLM Wiki';
    }

    setExportLoading(loading) {
        if (!this.exportMarkdownBtn) return;
        this.isExportingMarkdown = Boolean(loading);
        this.exportMarkdownBtn.disabled = this.isExportingMarkdown;
        this.exportMarkdownBtn.classList.toggle('is-loading', this.isExportingMarkdown);
        this.exportMarkdownBtn.textContent = this.isExportingMarkdown
            ? 'Exporting...'
            : window.languageManager.t('ask.exportLlmWiki');
    }

    getDownloadFilename(contentDisposition) {
        if (!contentDisposition) return null;
        const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (utf8Match) return decodeURIComponent(utf8Match[1]);
        const asciiMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
        return asciiMatch ? asciiMatch[1] : null;
    }

    async handleExportMarkdown() {
        if (this.isExportingMarkdown) return;

        if (!this.sessionId || !this.exportAvailable) {
            this.showStatus('Ask a question or analyze an image before exporting an LLM Wiki.', 'error');
            return;
        }

        this.setExportLoading(true);
        this.showStatus('Preparing LLM Wiki zip. Graphify can take several minutes for larger sessions or images...', 'info');

        try {
            const response = await fetch(`${this.apiBase}/sessions/${encodeURIComponent(this.sessionId)}/wiki-export.zip`, {
                method: 'GET',
                headers: this.getAuthHeaders()
            });

            if (response.status === 401) {
                window.location.href = '/login.html';
                throw new Error('Authentication required. Redirecting to login...');
            }

            if (!response.ok) {
                let errorMessage = `${response.status} ${response.statusText}`;
                const text = await response.text();
                if (text) {
                    try {
                        const data = JSON.parse(text);
                        if (data.detail) errorMessage += `\n${data.detail}`;
                    } catch (e) {
                        errorMessage += `\n${text}`;
                    }
                }
                throw new Error(errorMessage);
            }

            const blob = await response.blob();
            const filename = this.getDownloadFilename(response.headers.get('Content-Disposition'))
                || `second-brain-session-${this.sessionId}.zip`;
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();

            const safeFilename = this.escapeHtml(filename);
            const safeUrl = this.escapeHtml(url);
            this.showStatus(
                `LLM Wiki zip ready. <a href="${safeUrl}" download="${safeFilename}">Download again</a>`,
                'success',
                60000
            );
            setTimeout(() => URL.revokeObjectURL(url), 60000);
        } catch (error) {
            console.error('LLM Wiki export error:', error);
            this.showStatus(`LLM Wiki export failed: ${this.escapeHtml(error.message)}`, 'error');
        } finally {
            this.setExportLoading(false);
            this.setExportAvailable(Boolean(this.sessionId));
        }
    }

    initializeModelMode() {
        if (!this.modelModeRadios || this.modelModeRadios.length === 0) return;

        const savedMode = localStorage.getItem('sbModelMode');
        const mode = (savedMode === 'llm-wiki' || savedMode === 'quality') ? 'llm-wiki' : 'fast';
        this.modelModeRadios.forEach((radio) => {
            radio.checked = (radio.value === mode);
        });
        this.applyModelMode(mode);
    }

    getCurrentModelMode() {
        if (!this.modelModeRadios || this.modelModeRadios.length === 0) return null;
        const selected = Array.from(this.modelModeRadios).find((radio) => radio.checked);
        return selected?.value === 'llm-wiki' ? 'llm-wiki' : 'fast';
    }

    applyModelMode(mode) {
        if (!this.openaiCheck || !this.geminiCheck || !this.grokCheck) return;

        if (mode === 'llm-wiki') {
            this.openaiCheck.checked = true;
            this.geminiCheck.checked = true;
            this.grokCheck.checked = true;
            return;
        }

        // Fast mode: keep the low-latency model set without Gemini.
        this.openaiCheck.checked = true;
        this.geminiCheck.checked = false;
        this.grokCheck.checked = true;
    }

    getSelectedModels() {
        const mode = this.getCurrentModelMode();
        if (mode) {
            this.applyModelMode(mode);
            if (mode === 'llm-wiki') return ['OpenAI', 'Gemini', 'Grok'];
            return ['OpenAI', 'Grok'];
        }

        const selected = [];
        if (this.openaiCheck.checked) selected.push('OpenAI');
        // if (this.claudeCheck.checked) selected.push('Claude'); // Claude hidden from UI
        if (this.geminiCheck.checked) selected.push('Gemini');
        if (this.grokCheck.checked) selected.push('Grok');
        return selected;
    }

    async handleSendMessage() {
        const prompt = this.promptInput.value.trim();
        const hasImage = this.selectedImageFile !== null;
        
        console.log('📤 handleSendMessage - hasImage:', hasImage, 'selectedImageFile:', this.selectedImageFile);
        
        // If there's an image, handle image analysis
        if (hasImage) {
            console.log('📷 Routing to handleImageAnalysis');
            await this.handleImageAnalysis();
            return;
        }
        
        // Otherwise, handle text question
        if (!prompt) {
            this.showStatus(window.languageManager.t('status.pleaseEnter'), 'error');
            this.promptInput.focus();
            return;
        }

        const selectedModels = this.getSelectedModels();
        const responseMode = this.getCurrentModelMode() === 'llm-wiki' ? 'llm-wiki' : 'fast';
        if (selectedModels.length === 0) {
            this.showStatus(window.languageManager.t('status.pleaseSelect'), 'error');
            return;
        }

        this.setLoadingState(true);
        this.clearResults();
        this.showStatus(window.languageManager.t('status.consulting', {models: selectedModels.join(', ')}), 'info');

        try {
            const data = await this.postJSON('/ask', { 
                user_input: prompt,
                selected_models: selectedModels,
                session_id: this.sessionId,
                response_mode: responseMode
            });
            
            // Cache session id returned by API (auto-created on first turn)
            if (data.session_id) {
                this.sessionId = data.session_id;
                localStorage.setItem('sbSessionId', data.session_id);
            }
            this.setExportAvailable(Boolean(this.sessionId));
            
            this.displaySummary(data.summary);
            this.displayAnswers(data.answers, data.related_knowledge, data.suggested_topics);
            this.showStatus(window.languageManager.t('status.complete'), 'success');
            
            // Clear text input on success
            this.promptInput.value = '';
            
        } catch (error) {
            console.error('❌ handleSendMessage error:', error);  // Debug logging
            this.displayError(error.message);
            this.showStatus(window.languageManager.t('status.error'), 'error');
        } finally {
            this.setLoadingState(false);
        }
    }

    async handleNewSession() {
        this.showStatus('Starting a fresh session...', 'info');
        try {
            const data = await this.postJSON('/sessions/new', {
                previous_session_id: this.sessionId
            });
            if (data.session_id) {
                this.sessionId = data.session_id;
                localStorage.setItem('sbSessionId', data.session_id);
                this.setExportAvailable(true);
            } else {
                this.sessionId = null;
                localStorage.removeItem('sbSessionId');
                this.setExportAvailable(false);
            }
            this.clearResults();
            this.promptInput.value = '';
            this.handleClearImage();
            this.showStatus('✅ New session started', 'success');
        } catch (error) {
            console.error('New session error:', error);
            this.showStatus(`❌ ${error.message}`, 'error');
        }
    }

    async handleDailySummarize() {
        const day = this.dayInput.value;
        if (!day) {
            this.showToolStatus('summarize', 'Please select a date first.', 'error');
            return;
        }

        this.setToolLoading('summarize', true);
        this.summaryResults.innerHTML = '';

        try {
            const data = await this.postJSON('/tools/daily_summarizer', { day });
            
            if (data.items && data.items.length > 0) {
                this.displayTopicSummary(data.items);
                this.showToolStatus('summarize', 
                    `✅ Summarized ${data.entries_count} Q&A items into ${data.items.length} topics`, 
                    'success'
                );
            } else {
                this.summaryResults.innerHTML = '<p>No data found for this date.</p>';
                this.showToolStatus('summarize', 'No entries found for the selected date.', 'info');
            }
        } catch (error) {
            this.showToolStatus('summarize', `❌ ${error.message}`, 'error');
        } finally {
            this.setToolLoading('summarize', false);
        }
    }

    async handleVectorSearch() {
        const query = this.searchQuery.value.trim();
        if (!query) {
            this.showToolStatus('search', 'Please enter a search query.', 'error');
            return;
        }

        this.setToolLoading('vector-search', true);
        this.searchResults.innerHTML = '';
        this.searchResults.style.display = 'block';

        try {
            const data = await this.postJSON('/vector/search', { 
                query: query,
                limit: 10,
                score_threshold: 0.25 
            });
            
            if (data.results && data.results.length > 0) {
                this.searchResults.innerHTML = `
                    <div class="search-header">
                        <h4>Found ${data.results.length} similar entries</h4>
                        ${data.execution_time_ms ? `<small>Search took ${data.execution_time_ms}ms</small>` : '<small>Search completed</small>'}
                    </div>
                    ${data.results.map(result => `
                        <div class="search-result-item" style="margin-bottom: 12px; padding: 12px; background: #f8fafc; border-radius: 6px; border-left: 3px solid #3b82f6;">
                            <div style="font-weight: 600; margin-bottom: 6px; color: #000000;">${this.escapeHtml(result.content || result.user_input || 'No title')}</div>
                            <div style="color: #000000; font-size: 0.9em; margin-bottom: 8px;">${this.escapeHtml(result.content || result.summary || 'No content')}</div>
                            <div style="display: flex; justify-content: between; align-items: center; font-size: 0.8em; color: #94a3b8;">
                                <span>Topics: ${this.getTopicsFromResult(result)}</span>
                                <span style="margin-left: auto;">${result.created_at ? new Date(result.created_at).toLocaleDateString() : 'No date'}</span>
                            </div>
                        </div>
                    `).join('')}
                `;
                
                this.showToolStatus('search', 
                    `✅ Found ${data.results.length} relevant entries`, 
                    'success'
                );
            } else {
                this.searchResults.innerHTML = '<p style="text-align: center; color: #64748b;">No similar entries found. Try different search terms.</p>';
                this.showToolStatus('search', 'No results found. Try different search terms.', 'info');
            }
        } catch (error) {
            this.showToolStatus('search', `❌ ${error.message}`, 'error');
        } finally {
            this.setToolLoading('vector-search', false);
        }
    }

    async handleLoadTopics() {
        this.setToolLoading('load-topics', true);
        this.topicsResults.innerHTML = '';
        this.topicsResults.style.display = 'block';

        try {
            const data = await this.postJSON('/vector/topics');
            
            if (data.topics && data.topics.length > 0) {
                this.topicsResults.innerHTML = `
                    <div class="topics-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px;">
                        ${data.topics.map(topicData => `
                            <div class="topic-badge" style="background: #e0e7ff; color: #3730a3; padding: 8px 12px; border-radius: 8px; text-align: center; cursor: pointer;" 
                                 onclick="app.searchByTopic('${topicData.topic}')">
                                <div style="font-weight: 600;">${this.escapeHtml(topicData.topic)}</div>
                                <div style="font-size: 0.8em; opacity: 0.8;">${topicData.count} entries</div>
                            </div>
                        `).join('')}
                    </div>
                `;
                
                this.showToolStatus('topics', 
                    `✅ Loaded ${data.topics.length} topics`, 
                    'success'
                );
            } else {
                this.topicsResults.innerHTML = '<p style="text-align: center; color: #64748b;">No topics found yet. Ask some questions first!</p>';
                this.showToolStatus('topics', 'No topics found yet.', 'info');
            }
        } catch (error) {
            this.showToolStatus('topics', `❌ ${error.message}`, 'error');
        } finally {
            this.setToolLoading('load-topics', false);
        }
    }

    async handleLoadStats() {
        this.setToolLoading('load-stats', true);
        this.statsResults.innerHTML = '';
        this.statsResults.style.display = 'block';

        try {
            const data = await this.postJSON('/vector/stats');
            
            this.statsResults.innerHTML = `
                <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                    <div class="stat-card" style="background: #f0f9ff; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 2em; font-weight: bold; color: #0369a1;">${data.total_entries}</div>
                        <div style="color: #64748b;">Total Entries</div>
                    </div>
                    <div class="stat-card" style="background: #f0fdf4; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 2em; font-weight: bold; color: #059669;">${data.topics.length}</div>
                        <div style="color: #64748b;">Unique Topics</div>
                    </div>
                    <div class="stat-card" style="background: #fefce8; padding: 16px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 2em; font-weight: bold; color: #ca8a04;">${data.recent_entries_count}</div>
                        <div style="color: #64748b;">Recent (7 days)</div>
                    </div>
                </div>
                <div style="margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 6px;">
                    <h5 style="margin-bottom: 8px;">Most Active Topics</h5>
                    ${data.topics.slice(0, 5).map(topic => `
                        <div style="display: flex; justify-content: space-between; padding: 4px 0;">
                            <span>${this.escapeHtml(topic.topic)}</span>
                            <span style="color: #64748b;">${topic.count} entries</span>
                        </div>
                    `).join('')}
                </div>
            `;
            
            this.showToolStatus('stats', 
                `✅ Loaded knowledge base statistics`, 
                'success'
            );
        } catch (error) {
            this.showToolStatus('stats', `❌ ${error.message}`, 'error');
        } finally {
            this.setToolLoading('load-stats', false);
        }
    }

    async searchByTopic(topic) {
        // Set the search query and perform a topic-based search
        this.searchQuery.value = topic;
        
        this.setToolLoading('vector-search', true);
        this.searchResults.innerHTML = '';
        this.searchResults.style.display = 'block';

        try {
            const data = await this.postJSON('/vector/by-topic', { 
                topic: topic,
                limit: 15
            });
            
            if (data.results && data.results.length > 0) {
                this.searchResults.innerHTML = `
                    <div class="search-header">
                        <h4>Topic: "${topic}" (${data.results.length} entries)</h4>
                    </div>
                    ${data.results.map(result => `
                        <div class="search-result-item" style="margin-bottom: 12px; padding: 12px; background: #f8fafc; border-radius: 6px; border-left: 3px solid #7c3aed;">
                            <div style="font-weight: 600; margin-bottom: 6px; color: #000000;">${this.escapeHtml(result.user_input)}</div>
                            <div style="color: #000000; font-size: 0.9em; margin-bottom: 8px;">${this.escapeHtml(result.summary)}</div>
                            <div style="display: flex; justify-content: between; align-items: center; font-size: 0.8em; color: #94a3b8;">
                                <span>Topics: ${this.getTopicsFromResult(result)}</span>
                                <span style="margin-left: auto;">${new Date(result.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                    `).join('')}
                `;
                
                this.showToolStatus('search', 
                    `✅ Found ${data.results.length} entries for topic "${topic}"`, 
                    'success'
                );
            } else {
                this.searchResults.innerHTML = `<p style="text-align: center; color: #64748b;">No entries found for topic "${topic}".</p>`;
            }
        } catch (error) {
            this.showToolStatus('search', `❌ ${error.message}`, 'error');
        } finally {
            this.setToolLoading('vector-search', false);
        }
    }

    displaySummary(summary) {
        this.summaryEl.innerHTML = `<div class="markdown-content">${this.parseMarkdown(summary || '(No summary available)')}</div>`;
        this.summaryEl.classList.add('fade-in');
    }

    displayAnswers(answers, relatedKnowledge = [], suggestedTopics = []) {
        this.answersEl.innerHTML = '';

        if (!answers || typeof answers !== 'object') {
            this.answersEl.innerHTML = '<div class="answer-item">No answers available</div>';
            return;
        }

        const shouldHide = (text) => {
            const lower = (text || '').toLowerCase();
            return (
                !text ||
                lower.includes('429') ||
                lower.includes('rate limit') ||
                lower.includes('quota') ||
                lower.includes('unavailable') ||
                lower.startsWith('error')
            );
        };

        // Display AI model answers
        if (Array.isArray(answers)) {
            answers.forEach((item, idx) => {
                const answerDiv = document.createElement('div');
                answerDiv.className = 'answer-item fade-in';
                answerDiv.innerHTML = `
                    <div class="answer-source">Response ${idx + 1}</div>
                    <div class="answer-text markdown-content">${this.parseMarkdown(item)}</div>
                `;
                this.answersEl.appendChild(answerDiv);
            });
        } else {
            Object.entries(answers).forEach(([source, text]) => {
                if (shouldHide(text)) return;

                const answerDiv = document.createElement('div');
                answerDiv.className = 'answer-item fade-in';
                
                // Add model-specific styling and icons
                const sourceClass = source.toLowerCase();
                const icon = this.getModelIcon(source);
                
                answerDiv.innerHTML = `
                    <div class="answer-source ${sourceClass}">${icon} ${this.escapeHtml(source)}</div>
                    <div class="answer-text markdown-content">${this.parseMarkdown(text)}</div>
                `;
                this.answersEl.appendChild(answerDiv);
            });
        }

        // If nothing was appended, show a friendly message
        if (this.answersEl.innerHTML.trim() === '') {
            this.answersEl.innerHTML = '<div class="answer-item">No successful model responses (rate limited or unavailable).</div>';
        }

        // Display related knowledge if available
        if (relatedKnowledge && relatedKnowledge.length > 0) {
            const relatedDiv = document.createElement('div');
            relatedDiv.className = 'answer-item fade-in related-knowledge';
            
            let relatedHtml = '<div class="answer-source related">🔍 Related Knowledge</div><div class="answer-text">';
            relatedKnowledge.forEach((entry, idx) => {
                relatedHtml += `
                    <div class="related-item">
                        <div class="related-title">Related ${idx + 1}: ${this.escapeHtml(entry.summary || 'No summary available')}</div>
                        <div class="related-meta">Topics: ${this.getTopicsFromResult(entry)} | Created: ${entry.created_at ? new Date(entry.created_at).toLocaleDateString() : 'Unknown'}</div>
                    </div>
                `;
            });
            relatedHtml += '</div>';
            relatedDiv.innerHTML = relatedHtml;
            this.answersEl.appendChild(relatedDiv);
        }

        // Display suggested topics if available
        if (suggestedTopics && suggestedTopics.length > 0) {
            const topicsDiv = document.createElement('div');
            topicsDiv.className = 'answer-item fade-in suggested-topics';
            
            topicsDiv.innerHTML = `
                <div class="answer-source topics">🏷️ Suggested Topics</div>
                <div class="answer-text">
                    <div class="topic-tags">
                        ${suggestedTopics.map(topic => `<span class="topic-tag">${this.escapeHtml(topic)}</span>`).join('')}
                    </div>
                </div>
            `;
            this.answersEl.appendChild(topicsDiv);
        }
    }

    displayTopicSummary(topics) {
        if (!topics || topics.length === 0) {
            this.summaryResults.innerHTML = '<p>No topics found for this date.</p>';
            return;
        }

        // Create interactive topic buttons
        const topicsHtml = topics.map((topic, index) => `
            <div class="topic-item">
                <button class="topic-button" onclick="window.app.toggleTopic(${index})">
                    <span class="topic-icon">📋</span>
                    <span class="topic-title">${this.escapeHtml(topic.topic)}</span>
                    <span class="topic-chevron" id="chevron-${index}">▼</span>
                </button>
                <div class="topic-content" id="content-${index}">
                    <div class="knowledge-point markdown-content">
                        ${this.parseMarkdown(topic.knowledge_point)}
                    </div>
                </div>
            </div>
        `).join('');

        this.summaryResults.innerHTML = `
            <div class="topics-container">
                ${topicsHtml}
            </div>
        `;

        // Store topics for toggle functionality
        this.currentTopics = topics;
    }

    toggleTopic(index) {
        const content = document.getElementById(`content-${index}`);
        const chevron = document.getElementById(`chevron-${index}`);
        
        if (!content || !chevron) {
            console.error('Topic elements not found for index:', index);
            return;
        }
        
        // Check if currently collapsed
        const computedStyle = window.getComputedStyle(content);
        const isCollapsed = computedStyle.display === 'none';
        
        if (isCollapsed) {
            // Expanding
            content.style.display = 'block';
            content.style.maxHeight = '0px';
            content.style.opacity = '0';
            content.style.overflow = 'hidden';
            
            // Force browser reflow
            void content.offsetHeight;
            
            // Animate to full height
            const fullHeight = content.scrollHeight;
            requestAnimationFrame(() => {
                content.style.transition = 'max-height 0.4s ease-out, opacity 0.4s ease-out';
                content.style.maxHeight = fullHeight + 'px';
                content.style.opacity = '1';
            });
            
            // Update chevron
            chevron.textContent = '▲';
            chevron.style.transition = 'transform 0.3s ease';
            chevron.style.transform = 'rotate(180deg)';
        } else {
            // Collapsing
            content.style.transition = 'max-height 0.4s ease-out, opacity 0.4s ease-out';
            content.style.maxHeight = '0px';
            content.style.opacity = '0';
            
            // Hide after animation completes
            setTimeout(() => {
                content.style.display = 'none';
            }, 400);
            
            // Update chevron
            chevron.textContent = '▼';
            chevron.style.transition = 'transform 0.3s ease';
            chevron.style.transform = 'rotate(0deg)';
        }
    }

    displayError(message) {
        this.summaryEl.textContent = '(Error occurred)';
        this.answersEl.innerHTML = `
            <div class="answer-item">
                <div class="answer-source">Error</div>
                <div class="answer-text">${this.escapeHtml(message)}</div>
            </div>
        `;
    }

    clearResults() {
        this.summaryEl.textContent = window.languageManager.t('ask.summaryPlaceholder');
        this.answersEl.innerHTML = `<div class="answer-item">${window.languageManager.t('ask.responsesPlaceholder')}</div>`;
        this.setExportAvailable(false);
        if (this.imageAnalysisCard) {
            this.imageAnalysisCard.style.display = 'none';
            this.imageResultsContent.innerHTML = '';
        }
    }

    showStatus(message, type = 'info', durationMs = 5000) {
        this.statusEl.innerHTML = `<div class="status-message status-${type}">${message}</div>`;
        if (durationMs > 0) {
            setTimeout(() => {
                if (this.statusEl.innerHTML.includes(message)) {
                    this.statusEl.innerHTML = '';
                }
            }, durationMs);
        }
    }

    showToolStatus(tool, message, type = 'info') {
        let statusEl;
        
        switch(tool) {
            case 'summarize':
                statusEl = document.getElementById('summarize-status');
                break;
            case 'sync':
                statusEl = document.getElementById('sync-status');
                break;
            case 'search':
                statusEl = document.getElementById('search-status');
                break;
            case 'topics':
                statusEl = document.getElementById('topics-status');
                break;
            case 'stats':
                statusEl = document.getElementById('stats-status');
                break;
            default:
                statusEl = null;
        }
        
        if (statusEl) {
            statusEl.innerHTML = `<div class="status-message status-${type}">${message}</div>`;
            setTimeout(() => {
                if (statusEl.innerHTML.includes(message)) {
                    statusEl.innerHTML = '';
                }
            }, 5000);
        }
    }

    setLoadingState(loading) {
        this.sendBtn.disabled = loading;
        this.sendBtn.innerHTML = loading ? 
            '<span class="loading"></span> Thinking...' : 
            '🚀 Send';
        this.promptInput.disabled = loading;
    }

    setToolLoading(tool, loading) {
        if (tool === 'summarize') {
            this.summarizeBtn.disabled = loading;
            this.summarizeBtn.innerHTML = loading ? 
                '<span class="loading"></span> Summarizing...' : 
                '📊 Summarize Day';
        } else if (tool === 'vector-search') {
            this.vectorSearchBtn.disabled = loading;
            this.vectorSearchBtn.innerHTML = loading ? 
                '<span class="loading"></span> Searching...' : 
                '🔍 Search Knowledge';
        } else if (tool === 'load-topics') {
            this.loadTopicsBtn.disabled = loading;
            this.loadTopicsBtn.innerHTML = loading ? 
                '<span class="loading"></span> Loading...' : 
                '📋 Load All Topics';
        } else if (tool === 'load-stats') {
            this.loadStatsBtn.disabled = loading;
            this.loadStatsBtn.innerHTML = loading ? 
                '<span class="loading"></span> Loading...' : 
                '📊 Load Stats';
        }
    }

    getModelIcon(modelName) {
        const icons = {
            'OpenAI': '🤖',
            'Claude': '🎭', 
            'Gemini': '💎',
            'Grok': '🚀'
        };
        return icons[modelName] || '🧠';
    }

    // Knowledge Graph Methods
    async handleToggleGraph() {
        // If graph is visible, hide it
        if (this.graphContainer.style.display === 'block') {
            this.handleCloseGraph();
        } else {
            // If graph is hidden, show and auto-load it
            await this.handleShowGraph();
        }
    }

    async handleShowGraph() {
        console.log('handleShowGraph called');
        console.log('graphVisualization element:', this.graphVisualization);
        console.log('graphContainer element:', this.graphContainer);
        
        this.setGraphStatus('Loading knowledge graph...', 'info');
        this.showGraphBtn.disabled = true;
        this.showGraphBtn.innerHTML = '<span class="loading"></span> Loading Graph...';
        // Ensure container is visible before measuring widths in displayKnowledgeGraph
        this.graphContainer.style.display = 'block';
        
        try {
            console.log('Fetching from:', `${this.apiBase}/vector/knowledge-graph`);
            const authHeaders = this.getAuthHeaders();
            const response = await fetch(`${this.apiBase}/vector/knowledge-graph`, {
                method: 'GET',
                headers: authHeaders
            });
            console.log('Response status:', response.status);
            
            if (response.status === 401) {
                console.log('Unauthorized - redirecting to login');
                window.location.href = '/login.html';
                return;
            }
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const graphData = await response.json();
            console.log('Graph data received:', graphData);
            console.log('Nodes:', graphData.nodes?.length, 'Edges:', graphData.edges?.length);
            
            console.log('Calling displayKnowledgeGraph...');
            this.displayKnowledgeGraph(graphData);
            console.log('displayKnowledgeGraph completed');
            
            this.setGraphStatus('Knowledge graph loaded successfully', 'success');
            
        } catch (error) {
            console.error('Error loading knowledge graph:', error);
            this.setGraphStatus(`Error loading graph: ${error.message}`, 'error');
            // Hide container if we failed to load anything
            this.graphContainer.style.display = 'none';
            this.showGraphBtn.innerHTML = '🌐 Show Knowledge Graph';
        } finally {
            this.showGraphBtn.disabled = false;
            if (this.graphContainer.style.display === 'block') {
                this.showGraphBtn.innerHTML = '🌐 Hide Knowledge Graph';
            }
        }
    }

    handleZoomInGraph() {
        if (this.currentSvg && this.currentZoom) {
            this.currentSvg.transition()
                .duration(300)
                .call(this.currentZoom.scaleBy, 1.4);
        }
    }

    handleZoomOutGraph() {
        if (this.currentSvg && this.currentZoom) {
            this.currentSvg.transition()
                .duration(300)
                .call(this.currentZoom.scaleBy, 1 / 1.4);
        }
    }

    handleCenterGraph() {
        if (!this.currentSvg || !this.currentZoom || !this.graphData || !this.graphData.nodes) {
            return;
        }

        const width = this.graphVisualization.offsetWidth || this.graphVisualization.clientWidth || 800;
        const height = 500;
        
        // Calculate bounds of all nodes
        const nodes = this.graphData.nodes;
        if (nodes.length === 0) return;

        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        nodes.forEach(node => {
            if (node.x < minX) minX = node.x;
            if (node.x > maxX) maxX = node.x;
            if (node.y < minY) minY = node.y;
            if (node.y > maxY) maxY = node.y;
        });

        const nodeWidth = maxX - minX;
        const nodeHeight = maxY - minY;
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;

        // Calculate scale to fit all nodes with padding
        const padding = 50;
        const scaleX = (width - padding * 2) / nodeWidth;
        const scaleY = (height - padding * 2) / nodeHeight;
        const scale = Math.min(scaleX, scaleY, 2); // Cap at 2x zoom

        // Calculate translation to center the nodes
        const translateX = width / 2 - centerX * scale;
        const translateY = height / 2 - centerY * scale;

        // Apply transform with smooth transition
        this.currentSvg.transition()
            .duration(750)
            .call(this.currentZoom.transform, d3.zoomIdentity
                .translate(translateX, translateY)
                .scale(scale));

        // Add red center marker
        this.addCenterMarker(width / 2, height / 2);

        // Restart simulation gently to improve layout
        if (this.simulation) {
            this.simulation.alpha(0.1).restart();
        }
    }

    addCenterMarker(x, y) {
        // Remove existing center marker
        d3.select(this.graphVisualization).select(".center-marker").remove();

        // Add red 'X' marker at center - append to SVG root, not inside zoom container
        const marker = this.currentSvg.append("g")
            .attr("class", "center-marker")
            .attr("transform", `translate(${x}, ${y})`)
            .style("pointer-events", "none"); // Don't interfere with zooming

        // Create red X shape
        marker.append("path")
            .attr("d", "M-10,-10 L10,10 M-10,10 L10,-10")
            .attr("stroke", "#dc2626")
            .attr("stroke-width", 4)
            .attr("stroke-linecap", "round");

        // Add subtle background circle
        marker.append("circle")
            .attr("r", 15)
            .attr("fill", "rgba(220, 38, 38, 0.15)")
            .attr("stroke", "#dc2626")
            .attr("stroke-width", 2);

        // Auto-hide marker after 3 seconds
        setTimeout(() => {
            marker.transition()
                .duration(1000)
                .style("opacity", 0)
                .on("end", function() { d3.select(this).remove(); });
        }, 3000);
    }

    handleCloseGraph() {
        this.graphContainer.style.display = 'none';
        this.setGraphStatus('', '');
        this.showGraphBtn.innerHTML = '🌐 Show Knowledge Graph';
        if (this.simulation) {
            this.simulation.stop();
        }
        // Clean up tooltip if exists
        d3.selectAll(".graph-tooltip").remove();
    }

    displayKnowledgeGraph(graphData) {
        console.log('displayKnowledgeGraph called with:', graphData);
        
        // Store graph data for later use (zoom, center, etc.)
        this.graphData = graphData;
        
        console.log('Clearing previous graph...');
        // Clear previous graph
        d3.select(this.graphVisualization).selectAll("*").remove();
        
        if (!graphData.nodes || graphData.nodes.length === 0) {
            console.log('No nodes found, showing empty state');
            // Check for error or informational messages in metadata
            const message = graphData.metadata?.message || graphData.metadata?.error || 
                          'No concepts found. Ask some questions to build your knowledge graph!';
            this.graphVisualization.innerHTML = `
                <div class="graph-loading" style="
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 500px;
                    color: #64748b;
                    font-size: 16px;
                    text-align: center;
                    padding: 40px;
                ">
                    <div style="font-size: 48px; margin-bottom: 20px;">🌐</div>
                    <div style="max-width: 500px;">${this.escapeHtml(message)}</div>
                    ${!graphData.metadata?.error ? '<div style="margin-top: 20px; font-size: 14px; opacity: 0.7;">💡 Tip: Use the Ask tab to add knowledge to your graph</div>' : ''}
                </div>
            `;
            return;
        }

        console.log('Creating graph with', graphData.nodes.length, 'nodes and', graphData.edges.length, 'edges');
        
        const width = this.graphVisualization.offsetWidth;
        const height = 500;
        
        console.log('Graph dimensions:', width, 'x', height);
        
        // IMPORTANT: Give nodes initial positions so they're visible immediately
        // Without this, they might start at (0,0) or undefined positions
        graphData.nodes.forEach((node, i) => {
            const angle = (i / graphData.nodes.length) * 2 * Math.PI;
            const radius = Math.min(width, height) / 4;
            node.x = width / 2 + radius * Math.cos(angle);
            node.y = height / 2 + radius * Math.sin(angle);
        });
        console.log('Initialized node positions in circle layout');

        // Create SVG with zoom functionality
        console.log('Creating SVG...');
        this.currentSvg = d3.select(this.graphVisualization)
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .style("background", "#f8fafc");  // Ensure background is visible
        
        console.log('SVG created with dimensions:', width, 'x', height);

        // Create a container group for all graph elements (before zoom!)
        console.log('Creating container...');
        const container = this.currentSvg.append("g");
        console.log('Container created');

        // Add zoom behavior
        console.log('Adding zoom behavior...');
        this.currentZoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => {
                container.attr("transform", event.transform);
            });

        this.currentSvg.call(this.currentZoom);
        console.log('Zoom behavior added');

        // Create simulation
        console.log('Creating force simulation...');
        this.simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.edges).id(d => d.id).distance(80))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(20));
        
        console.log('Simulation created');

        // Create links
        console.log('Creating links...');
        const link = container.append("g")
            .attr("class", "links-group")
            .selectAll("line")
            .data(graphData.edges)
            .enter().append("line")
            .attr("class", d => `graph-link ${d.type}`)
            .attr("stroke", "#94a3b8")  // Explicitly set color
            .attr("stroke-width", d => Math.max(2, Math.sqrt(d.weight * 3)));
        
        console.log('Links created:', graphData.edges.length, 'lines');

        // Create nodes
        console.log('Creating nodes...');
        const node = container.append("g")
            .attr("class", "nodes-group")
            .selectAll("circle")
            .data(graphData.nodes)
            .enter().append("circle")
            .attr("class", d => `graph-node ${d.type}`)
            .attr("r", d => Math.max(8, Math.min(d.size || 12, 20)))
            .attr("fill", d => {
                // Explicit colors based on type
                if (d.type === 'qa_concept') return '#7c3aed';
                if (d.type === 'concept') return '#2563eb';
                if (d.type === 'document') return '#059669';
                return '#d97706';
            })
            .call(this.createDragBehavior());
        
        console.log('Nodes created:', graphData.nodes.length, 'circles');
        console.log('Sample node data:', graphData.nodes[0]);

        // Add labels
        console.log('Creating labels...');
        const label = container.append("g")
            .selectAll("text")
            .data(graphData.nodes)
            .enter().append("text")
            .attr("class", "graph-text")
            .text(d => d.label.length > 20 ? d.label.substring(0, 20) + "..." : d.label);
        
        console.log('Labels created');

        // Add tooltip
        console.log('Creating tooltip...');
        const tooltip = d3.select("body").append("div")
            .attr("class", "graph-tooltip")
            .style("opacity", 0);

        node.on("mouseover", (event, d) => {
            tooltip.transition().duration(200).style("opacity", .9);
            tooltip.html(`<strong>${d.label}</strong><br/>${d.content}`)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", (d) => {
            tooltip.transition().duration(500).style("opacity", 0);
        });
        
        console.log('Tooltip created');

        // Update positions on simulation tick
        console.log('Setting up tick handler...');
        this.simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);

            label
                .attr("x", d => d.x)
                .attr("y", d => d.y + 3);
        });
        
        console.log('Tick handler set');

        // Update graph info
        console.log('Updating graph info...');
        this.graphInfo.innerHTML = `
            <span>Nodes: ${graphData.nodes.length} | Edges: ${graphData.edges.length}</span>
            <span>🖱️ Drag nodes • 🔍 Scroll to zoom • 🎯 Use Center button to reset view</span>
        `;
        
        console.log('displayKnowledgeGraph completed successfully!');
    }

    createDragBehavior() {
        return d3.drag()
            .on("start", (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on("drag", (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on("end", (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
    }

    setGraphStatus(message, type) {
        if (!this.graphStatus) return;
        
        this.graphStatus.innerHTML = message;
        this.graphStatus.className = `status-message ${type}`;
        
        if (message && type !== 'info') {
            setTimeout(() => {
                this.graphStatus.innerHTML = '';
                this.graphStatus.className = '';
            }, 5000);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // ========== Image Search Methods ==========
    
    handleImageSelect(event) {
        const file = event.target.files[0];
        if (file && file.type.startsWith('image/')) {
            this.displayImagePreview(file);
        }
    }
    
    handleDragOver(event) {
        event.preventDefault();
        event.stopPropagation();
        this.dropZone.classList.add('drag-over');
    }
    
    handleDragLeave(event) {
        event.preventDefault();
        event.stopPropagation();
        this.dropZone.classList.remove('drag-over');
    }
    
    handleDrop(event) {
        event.preventDefault();
        event.stopPropagation();
        this.dropZone.classList.remove('drag-over');
        
        const files = event.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) {
            this.displayImagePreview(files[0]);
        }
    }
    
    displayImagePreview(file) {
        console.log('📷 displayImagePreview called with file:', file.name, file.type, file.size);
        this.selectedImageFile = file;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            this.cachedImageBase64 = e.target.result; // Cache the base64 data
            console.log('📷 Image loaded, base64 length:', this.cachedImageBase64?.length);
            this.previewImg.src = this.cachedImageBase64;
            this.dropZone.style.display = 'none';
            this.imagePreview.style.display = 'block';
            if (this.imageAnalysisResults) this.imageAnalysisResults.innerHTML = '';
            if (this.imageSearchResults) this.imageSearchResults.innerHTML = '';
        };
        reader.readAsDataURL(file);
    }
    
    handleClearImage() {
        this.selectedImageFile = null;
        this.cachedImageBase64 = null; // Clear cached data
        this.previewImg.src = '';
        this.imageInput.value = '';
        this.dropZone.style.display = 'flex';
        this.imagePreview.style.display = 'none';
        if (this.imageAnalysisResults) this.imageAnalysisResults.innerHTML = '';
        if (this.imageSearchResults) this.imageSearchResults.innerHTML = '';
        if (this.imageStatus) this.imageStatus.innerHTML = '';
    }
    
    async handleImageAnalysis() {
        if (!this.selectedImageFile) {
            this.showStatus(window.languageManager.t('status.noImage'), 'error');
            return;
        }
        
        // Get selected models from main LLM checkboxes
        const selectedModels = this.getSelectedModels();
        const responseMode = this.getCurrentModelMode() === 'llm-wiki' ? 'llm-wiki' : 'fast';
        
        if (selectedModels.length === 0) {
            this.showStatus(window.languageManager.t('status.pleaseSelect'), 'error');
            return;
        }
        
        this.setLoadingState(true);
        this.clearResults();
        this.showStatus(window.languageManager.t('status.analyzing', {models: selectedModels.join(', ')}), 'info');
        
        try {
            // Use cached base64 data from preview (no need to read file again!)
            let base64Image = this.cachedImageBase64;
            
            // Fallback: if not cached, read it now
            if (!base64Image) {
                base64Image = await this.fileToBase64(this.selectedImageFile);
            }
            
            const base64Data = base64Image.split(',')[1]; // Remove data:image/jpeg;base64, prefix
            
            // Determine MIME type
            const mimeType = this.selectedImageFile.type;
            
            // Get authentication headers
            const authHeaders = this.getAuthHeaders();
            
            // Call analyze-image endpoint
            const response = await fetch(`${this.apiBase}/analyze-image`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...authHeaders
                },
                body: JSON.stringify({
                    image_base64: base64Data,
                    mime_type: mimeType,
                    prompt: "Describe what's in this image in detail. Extract any text, concepts, or key information that could be searched.",
                    session_id: this.sessionId,
                    selected_models: selectedModels,
                    response_mode: responseMode
                })
            });
            
            if (!response.ok) {
                throw new Error(`Analysis failed: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // Cache session id returned (align with text flow)
            if (result.session_id) {
                this.sessionId = result.session_id;
                localStorage.setItem('sbSessionId', result.session_id);
            }
            this.setExportAvailable(Boolean(this.sessionId));
            
            // Display in main results section
            this.displaySummary(result.summary);
            this.displayImageAnalysisAsAnswers(result.descriptions);
            
            // Show image-specific results
            this.displayImageSearchResults(result);
            
            this.showStatus(window.languageManager.t('status.analysisComplete'), 'success');
            
            // Clear the uploaded image after successful analysis
            this.handleClearImage();
            this.promptInput.value = '';
            
        } catch (error) {
            console.error('Image analysis error:', error);
            this.showStatus(window.languageManager.t('status.analysisFailed', {error: error.message}), 'error');
        } finally {
            this.setLoadingState(false);
        }
    }
    
    displayImageAnalysisAsAnswers(descriptions) {
        if (!descriptions || Object.keys(descriptions).length === 0) return;
        
        let html = '';
        for (const [model, description] of Object.entries(descriptions)) {
            const colorClass = model.toLowerCase();
            html += `
                <div class="answer-item ${colorClass}">
                    <div class="answer-header">
                        <span class="answer-model">${this.escapeHtml(model)}</span>
                    </div>
                    <div class="answer-content">
                        ${this.escapeHtml(description)}
                    </div>
                </div>
            `;
        }
        this.answersEl.innerHTML = html;
    }
    
    displayImageSearchResults(result) {
        // Show image analysis card
        this.imageAnalysisCard.style.display = 'block';
        
        let html = '';
        
        // Suggested queries
        if (result.suggested_search_queries && result.suggested_search_queries.length > 0) {
            html += '<div class="suggested-queries" style="margin-top: 1rem;">';
            html += '<strong>💡 Suggested Searches:</strong><br>';
            result.suggested_search_queries.forEach(query => {
                html += `<span class="query-chip" onclick="app.searchWithImageQuery('${this.escapeHtml(query)}')">${this.escapeHtml(query)}</span>`;
            });
            html += '</div>';
            
            // Automatically search with first query
            if (result.suggested_search_queries[0]) {
                this.searchWithImageQuery(result.suggested_search_queries[0]);
            }
        }
        
        this.imageResultsContent.innerHTML = html;
    }
    
    async searchWithImageQuery(query) {
        try {
            const authHeaders = this.getAuthHeaders();
            const response = await fetch(`${this.apiBase}/search`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...authHeaders
                },
                body: JSON.stringify({ query, limit: 5 })
            });
            
            if (!response.ok) throw new Error('Search failed');
            
            const data = await response.json();
            
            if (data.results && data.results.length > 0) {
                let searchHtml = '<div style="margin-top: 1.5rem;"><strong>🔍 Related Knowledge:</strong>';
                data.results.forEach(result => {
                    searchHtml += `
                        <div style="padding: 12px; background: var(--background-light); border-radius: 8px; margin-top: 8px;">
                            <div style="font-size: 0.9rem; color: var(--text-primary);">${this.escapeHtml(result.content)}</div>
                            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 4px;">
                                Score: ${result.score?.toFixed(3) || 'N/A'}
                                ${result.metadata?.tags ? ' • Tags: ' + result.metadata.tags.join(', ') : ''}
                            </div>
                        </div>
                    `;
                });
                searchHtml += '</div>';
                this.imageResultsContent.innerHTML += searchHtml;
            }
        } catch (error) {
            console.error('Search error:', error);
        }
    }
    
    fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
    
    async searchWithQuery(query) {
        this.setImageStatus(`🔍 Searching for: "${query}"...`, 'info');
        
        try {
            const authHeaders = this.getAuthHeaders();
            const response = await fetch(`${this.apiBase}/search/${encodeURIComponent(query)}`, {
                headers: authHeaders
            });
            
            if (!response.ok) {
                throw new Error(`Search failed: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.displayImageSearchResults(query, data.results || []);
            this.setImageStatus(`✅ Found ${data.count || 0} results`, 'success');
        } catch (error) {
            console.error('Search error:', error);
            this.setImageStatus(`❌ Search failed: ${error.message}`, 'error');
        }
    }
    
    displayImageSearchResults(query, results) {
        if (!results || results.length === 0) {
            this.imageSearchResults.innerHTML = `
                <div class="empty-state">
                    <p>No results found for "${this.escapeHtml(query)}"</p>
                    <p style="font-size: 0.9em; color: var(--text-secondary);">Try adding more knowledge to your Second Brain first.</p>
                </div>
            `;
            return;
        }
        
        let html = `<h4 style="margin-top: 1.5rem;">🔍 Search Results (${results.length})</h4>`;
        
        results.forEach((result, index) => {
            html += `
                <div class="result-item" style="margin: 1rem 0; padding: 1rem; background: var(--background-light); border-radius: var(--border-radius); border-left: 4px solid var(--primary-color);">
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">
                        ${result.title || `Result ${index + 1}`}
                    </div>
                    <div style="color: var(--text-secondary); margin-bottom: 0.5rem;">
                        ${this.escapeHtml(result.summary || result.content || 'No description')}
                    </div>
                    ${result.topics && result.topics.length > 0 ? `
                        <div style="margin-top: 0.5rem;">
                            ${result.topics.map(topic => 
                                `<span style="display: inline-block; background: var(--primary-color); color: white; padding: 0.25rem 0.5rem; border-radius: 12px; font-size: 0.8rem; margin-right: 0.25rem;">${this.escapeHtml(topic)}</span>`
                            ).join('')}
                        </div>
                    ` : ''}
                    ${result.distance !== undefined ? `
                        <div style="margin-top: 0.5rem; font-size: 0.85em; color: var(--text-secondary);">
                            Similarity: ${Math.round((1 - result.distance) * 100)}%
                        </div>
                    ` : ''}
                </div>
            `;
        });
        
        this.imageSearchResults.innerHTML = html;
    }
    
    setImageStatus(message, type) {
        if (!this.imageStatus) return;
        this.imageStatus.innerHTML = message;
        this.imageStatus.className = `status-message ${type}`;
        
        if (message && type !== 'info') {
            setTimeout(() => {
                this.imageStatus.innerHTML = '';
                this.imageStatus.className = '';
            }, 5000);
        }
    }

    getTopicsFromResult(result) {
        // Handle array format (result.topics)
        if (result.topics && Array.isArray(result.topics)) {
            return result.topics.join(', ');
        }
        
        // Handle metadata format (result.metadata.topic, result.metadata.category)
        if (result.metadata) {
            const topics = [];
            if (result.metadata.topic) topics.push(result.metadata.topic);
            if (result.metadata.category) topics.push(result.metadata.category);
            return topics.join(', ') || 'None';
        }
        
        // Handle direct topic field
        if (result.topic) {
            return result.topic;
        }
        
        return 'None';
    }
}

// Initialize the app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new SecondBrainApp();
    window.app = app; // Make globally available
    
    // Debug function to test tabs
    window.testTabs = () => {
        console.log('=== Tab Diagnostic ===');
        console.log('Tab buttons:', document.querySelectorAll('.tab-button').length);
        console.log('Tab contents:', document.querySelectorAll('.tab-content').length);
        document.querySelectorAll('.tab-button').forEach(btn => {
            console.log(`Button: ${btn.getAttribute('data-tab')}, Active: ${btn.classList.contains('active')}`);
        });
        document.querySelectorAll('.tab-content').forEach(content => {
            console.log(`Content: ${content.id}, Active: ${content.classList.contains('active')}, Display: ${window.getComputedStyle(content).display}`);
        });
    };
    
    // Auto-run diagnostic
    setTimeout(() => {
        console.log('🔍 Auto-running tab diagnostic...');
        window.testTabs();
    }, 1000);
});

// Add some utility functions for enhanced UX
window.addEventListener('beforeunload', (e) => {
    const promptInput = document.getElementById('prompt');
    if (promptInput && promptInput.value.trim()) {
        e.preventDefault();
        e.returnValue = 'You have unsaved text. Are you sure you want to leave?';
    }
});

// Auto-save draft to localStorage
setInterval(() => {
    const promptInput = document.getElementById('prompt');
    if (promptInput && promptInput.value.trim()) {
        localStorage.setItem('second-brain-draft', promptInput.value);
    }
}, 5000);

// Restore draft on page load
document.addEventListener('DOMContentLoaded', () => {
    const draft = localStorage.getItem('second-brain-draft');
    const promptInput = document.getElementById('prompt');
    if (draft && promptInput && !promptInput.value) {
        promptInput.value = draft;
    }
});
