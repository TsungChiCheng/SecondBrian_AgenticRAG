// Internationalization (i18n) - English and Traditional Chinese
const translations = {
    en: {
        // Header
        title: "Second Brain",
        subtitle: "Your AI-powered knowledge assistant that learns from multiple AI models",
        theme: "Theme",
        language: "Language",
        
        // Themes
        "theme.nature": "🍃 Nature",
        "theme.sakura": "🌸 Sakura",
        "theme.cyberpunk": "🌃 Cyberpunk",
        
        // Tab Navigation
        "tab.ask": "Ask AI",
        "tab.search": "Search & Browse",
        "tab.vocabulary": "Vocabulary",
        "tab.summary": "Daily Summary",
        "tab.graph": "Knowledge Graph",
        
        // Ask AI Tab
        "ask.label": "Ask your question or upload an image:",
        "ask.placeholder": "Ask anything... I'll consult multiple AI models and give you a comprehensive answer.\n\nOr upload an image below to analyze it!\n\nTip: Press Ctrl+Enter to send quickly!",
        "ask.uploadImage": "Upload Image (Optional)",
        "ask.dragDrop": "or drag & drop here",
        "ask.responseMode": "Response Mode",
        "ask.selectModels": "Select AI Models to Use:",
        "ask.send": "🚀 Send",
        "ask.summaryTitle": "Summary & Consensus",
        "ask.summaryPlaceholder": "(Ask a question or upload an image to see the AI consensus summary)",
        "ask.responsesTitle": "AI Model Responses",
        "ask.responsesPlaceholder": "Ask a question or upload an image to see answers from multiple AI models",
        "ask.imageAnalysisTitle": "Image Analysis & Search",
        "ask.exportLlmWiki": "Export LLM Wiki",
        
        // Search Tab
        "search.smartTitle": "Smart Search",
        "search.smartDesc": "Search through your accumulated knowledge base using natural language",
        "search.placeholder": "Search your knowledge...",
        "search.button": "Search Knowledge",
        "search.topicsTitle": "Browse Topics",
        "search.topicsDesc": "Explore all topics in your knowledge base",
        "search.topicsButton": "Load All Topics",
        "search.statsTitle": "Knowledge Stats",
        "search.statsDesc": "View statistics about your knowledge base",
        "search.statsButton": "Load Stats",
        
        // Vocabulary Tab
        "vocab.searchTitle": "🔍 Word Search",
        "vocab.searchDesc": "Search your vocabulary by word or meaning (semantic search)",
        "vocab.searchPlaceholder": "Enter word or meaning to search...",
        "vocab.semanticSearch": "Semantic Search (find by meaning)",
        "vocab.searchButton": "🔍 Search Vocabulary",
        "vocab.reviewTitle": "📖 Daily Review",
        "vocab.reviewDesc": "Get words due for review based on spaced repetition",
        "vocab.reviewLimit": "Number of words:",
        "vocab.reviewButton": "📚 Get Words to Review",
        "vocab.distanceTitle": "🎯 Word Relationships",
        "vocab.distanceDesc": "Visualize semantic relationships between words using embeddings",
        "vocab.centerWordPlaceholder": "Enter a word to see related words...",
        "vocab.relatedWordsLimit": "Number of related words:",
        "vocab.distanceButton": "🌐 Show Word Relationships",
        "vocab.statsTitle": "📊 My Vocabulary Stats",
        "vocab.statsDesc": "View your vocabulary learning progress and statistics",
        "vocab.statsButton": "📈 Show Statistics",
        
        // Summary Tab
        "summary.dailyTitle": "Daily Summary",
        "summary.dailyDesc": "Summarize your daily Q&A sessions and insights",
        "summary.dateLabel": "Select date to summarize",
        "summary.button": "Summarize Day",
        
        // Graph Tab
        "graph.title": "Knowledge Graph",
        "graph.desc": "Interactive visualization of concept relationships in your knowledge base",
        "graph.button": "Show Knowledge Graph",
        "graph.zoomIn": "Zoom In",
        "graph.zoomOut": "Zoom Out",
        "graph.center": "Center",
        "graph.close": "Close",
        
        // Footer
        "footer.text": "Powered by multiple AI models • Built with ❤️ for knowledge workers",
        
        // AI Models
        "model.openai": "OpenAI",
        "model.claude": "Claude",
        "model.gemini": "Gemini",
        "model.grok": "Grok",
        "mode.fast": "Fast (OpenAI + Grok)",
        "mode.llmWiki": "Advance (llm-wiki)",
        
        // Status Messages
        "status.ready": "Ready to help! Ask me anything...",
        "status.pleaseEnter": "Please enter a question or upload an image.",
        "status.pleaseSelect": "Please select at least one AI model.",
        "status.consulting": "Consulting {models}... This may take a moment.",
        "status.complete": "✅ Complete! New insights added to your knowledge base.",
        "status.error": "❌ Something went wrong. Please try again.",
        "status.clearing": "Clearing memory...",
        "status.cleared": "✅ Memory cleared! Starting fresh.",
        "status.resetFailed": "❌ Reset failed: {error}",
        "status.noImage": "❌ No image selected",
        "status.analyzing": "🔍 Analyzing image with {models}...",
        "status.analysisComplete": "✅ Image analysis complete!",
        "status.analysisFailed": "❌ Analysis failed: {error}"
    },
    zh_TW: {
        // Header
        title: "第二大腦",
        subtitle: "您的 AI 知識助手",
        theme: "主題",
        language: "語言",
        
        // Themes
        "theme.nature": "🍃 自然",
        "theme.sakura": "🌸 櫻花",
        "theme.cyberpunk": "🌃 賽博龐克",
        
        // Tab Navigation
        "tab.ask": "問 AI",
        "tab.search": "搜尋與瀏覽",
        "tab.vocabulary": "詞彙記憶",
        "tab.summary": "每日摘要",
        "tab.graph": "知識圖譜",
        
        // Ask AI Tab
        "ask.label": "提出您的問題或上傳圖片：",
        "ask.placeholder": "問任何問題...我會諮詢多個 AI 模型並給您全面的答案。\n\n或在下方上傳圖片進行分析！\n\n提示：按 Ctrl+Enter 快速發送！",
        "ask.uploadImage": "上傳圖片（選填）",
        "ask.dragDrop": "或拖放至此",
        "ask.responseMode": "回應模式",
        "ask.selectModels": "選擇要使用的 AI 模型：",
        "ask.send": "🚀 發送",
        "ask.summaryTitle": "摘要與共識",
        "ask.summaryPlaceholder": "（提出問題或上傳圖片以查看 AI 共識摘要）",
        "ask.responsesTitle": "AI 模型回應",
        "ask.responsesPlaceholder": "提出問題或上傳圖片以查看多個 AI 模型的答案",
        "ask.imageAnalysisTitle": "圖片分析與搜尋",
        "ask.exportLlmWiki": "匯出 LLM Wiki",
        
        // Search Tab
        "search.smartTitle": "智慧搜尋",
        "search.smartDesc": "使用自然語言搜尋您累積的知識庫",
        "search.placeholder": "搜尋您的知識...",
        "search.button": "搜尋知識",
        "search.topicsTitle": "瀏覽主題",
        "search.topicsDesc": "探索知識庫中的所有主題",
        "search.topicsButton": "載入所有主題",
        "search.statsTitle": "知識統計",
        "search.statsDesc": "查看知識庫的統計資料",
        "search.statsButton": "載入統計",
        
        // Vocabulary Tab
        "vocab.searchTitle": "🔍 單字搜尋",
        "vocab.searchDesc": "按單字或意思搜尋您的詞彙（語義搜尋）",
        "vocab.searchPlaceholder": "輸入單字或意思進行搜尋...",
        "vocab.semanticSearch": "語義搜尋（按意思查找）",
        "vocab.searchButton": "🔍 搜尋詞彙",
        "vocab.reviewTitle": "📖 每日複習",
        "vocab.reviewDesc": "根據間隔重複獲取需要複習的單字",
        "vocab.reviewLimit": "單字數量：",
        "vocab.reviewButton": "📚 獲取複習單字",
        "vocab.distanceTitle": "🎯 單字關聯",
        "vocab.distanceDesc": "使用嵌入向量視覺化單字之間的語義關係",
        "vocab.centerWordPlaceholder": "輸入一個單字以查看相關單字...",
        "vocab.relatedWordsLimit": "相關單字數量：",
        "vocab.distanceButton": "🌐 顯示單字關聯",
        "vocab.statsTitle": "📊 我的詞彙統計",
        "vocab.statsDesc": "查看您的詞彙學習進度和統計資料",
        "vocab.statsButton": "📈 顯示統計",
        
        // Summary Tab
        "summary.dailyTitle": "每日摘要",
        "summary.dailyDesc": "總結您的每日問答和見解",
        "summary.dateLabel": "選擇要總結的日期",
        "summary.button": "總結當天",
        
        // Graph Tab
        "graph.title": "知識圖譜",
        "graph.desc": "知識庫中概念關係的互動視覺化",
        "graph.button": "顯示知識圖譜",
        "graph.zoomIn": "放大",
        "graph.zoomOut": "縮小",
        "graph.center": "居中",
        "graph.close": "關閉",
        
        // Footer
        "footer.text": "由多個 AI 模型提供支持 • 為知識工作者打造",
        
        // AI Models
        "model.openai": "OpenAI",
        "model.claude": "Claude",
        "model.gemini": "Gemini",
        "model.grok": "Grok",
        "mode.fast": "快速（OpenAI + Grok）",
        "mode.llmWiki": "進階（llm-wiki）",
        
        // Status Messages
        "status.ready": "準備就緒！隨時為您服務...",
        "status.pleaseEnter": "請輸入問題或上傳圖片。",
        "status.pleaseSelect": "請至少選擇一個 AI 模型。",
        "status.consulting": "正在諮詢 {models}... 這可能需要一點時間。",
        "status.complete": "✅ 完成！新的見解已添加到您的知識庫。",
        "status.error": "❌ 出現問題。請重試。",
        "status.clearing": "正在清除記憶...",
        "status.cleared": "✅ 記憶已清除！重新開始。",
        "status.resetFailed": "❌ 重置失敗：{error}",
        "status.noImage": "❌ 未選擇圖片",
        "status.analyzing": "🔍 正在使用 {models} 分析圖片...",
        "status.analysisComplete": "✅ 圖片分析完成！",
        "status.analysisFailed": "❌ 分析失敗：{error}"
    }
};

class LanguageManager {
    constructor() {
        // Get saved language or default to English
        const savedLang = localStorage.getItem('preferredLanguage');
        const browserLang = navigator.language || navigator.userLanguage;
        
        // Default to English if no saved preference
        this.currentLanguage = savedLang || 'en';
        
        console.log('🌐 LanguageManager initialized:', {
            saved: savedLang,
            browser: browserLang,
            current: this.currentLanguage
        });
    }
    
    setLanguage(lang) {
        if (!translations[lang]) {
            console.error('❌ Language not supported:', lang);
            return;
        }
        
        this.currentLanguage = lang;
        localStorage.setItem('preferredLanguage', lang);
        console.log('✅ Language changed to:', lang);
        
        // Update UI
        this.updateUI();
        
        // Update HTML lang attribute
        document.documentElement.lang = lang === 'zh_TW' ? 'zh-TW' : lang;
    }
    
    t(key, params = {}) {
        let translation = translations[this.currentLanguage][key];
        if (!translation) {
            console.warn(`⚠️ Translation missing for key: ${key} in language: ${this.currentLanguage}`);
            return key;
        }
        
        // Replace parameters in the translation string
        Object.keys(params).forEach(param => {
            translation = translation.replace(`{${param}}`, params[param]);
        });
        
        return translation;
    }
    
    updateUI() {
        console.log('🔄 Updating UI with language:', this.currentLanguage);
        
        // Update all elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            const translation = this.t(key);
            
            // Update text content or placeholder based on element type
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                if (element.placeholder !== undefined) {
                    element.placeholder = translation;
                }
            } else if (element.hasAttribute('title')) {
                element.title = translation;
            } else {
                // Preserve emojis and icons
                const hasEmoji = /[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]/u.test(element.textContent);
                if (hasEmoji) {
                    const emoji = element.textContent.match(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]/u)?.[0] || '';
                    element.textContent = `${emoji} ${translation}`;
                } else {
                    element.textContent = translation;
                }
            }
        });
        
        // Update language radio buttons
        const langRadios = document.querySelectorAll('.language-radio');
        langRadios.forEach(radio => {
            radio.checked = (radio.value === this.currentLanguage);
        });
        
        console.log('✅ UI updated');
    }
    
    getCurrentLanguage() {
        return this.currentLanguage;
    }
    
    getLanguageName(lang) {
        const names = {
            en: 'English',
            zh_TW: '繁體中文'
        };
        return names[lang] || lang;
    }
}

// Create global instance
window.languageManager = new LanguageManager();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🌐 Initializing language system...');
    
    // Apply translations immediately
    window.languageManager.updateUI();
    
    // Set up language radio buttons
    const langRadios = document.querySelectorAll('.language-radio');
    if (langRadios.length > 0) {
        // Set the checked state based on current language
        const currentLang = window.languageManager.getCurrentLanguage();
        langRadios.forEach(radio => {
            radio.checked = (radio.value === currentLang);
            radio.addEventListener('change', (e) => {
                if (e.target.checked) {
                    console.log('🌐 Language changed to:', e.target.value);
                    window.languageManager.setLanguage(e.target.value);
                }
            });
        });
    }
    
    console.log('✅ Language system initialized');
});

// Export for use in other scripts
window.translations = translations;
