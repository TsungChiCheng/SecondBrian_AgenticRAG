// vocabulary.js - Vocabulary Memory Feature
// Handles word search, daily review, and word relationship visualization

// Global state for flashcard review
let currentReviewWords = [];
let currentReviewIndex = 0;
let reviewStats = { correct: 0, total: 0 };

// API base URL
const API_BASE_URL = '/api';

// Global function to toggle word details in Recent Activity
function toggleWordDetails(wordId) {
    const detailsDiv = document.getElementById('details-' + wordId);
    if (detailsDiv) {
        if (detailsDiv.style.display === 'none') {
            detailsDiv.style.display = 'block';
        } else {
            detailsDiv.style.display = 'none';
        }
    }
}

// Helper function to play pronunciation from Cambridge Dictionary
async function playCambridgeAudio(word) {
    console.log('🎵 Attempting to play pronunciation for:', word);
    
    // Use browser speech synthesis as the primary method
    // Cambridge Dictionary URLs are often blocked by CORS or rate limiting
    try {
        console.log('🔊 Using browser speech synthesis for:', word);
        const utterance = new SpeechSynthesisUtterance(word);
        utterance.lang = 'en-US';
        utterance.rate = 0.9; // Slightly slower for clarity
        
        // Add event listeners for debugging
        utterance.onstart = () => console.log('✅ Speech started');
        utterance.onend = () => console.log('✅ Speech ended');
        utterance.onerror = (event) => console.error('❌ Speech error:', event);
        
        window.speechSynthesis.speak(utterance);
        console.log('✅ Speech synthesis initiated');
    } catch (error) {
        console.error('❌ Error with speech synthesis:', error);
        
        // Fallback: Try Cambridge Dictionary audio as backup
        try {
            console.log('📡 Trying Cambridge Dictionary audio as fallback...');
            const audioUrl = `https://dictionary.cambridge.org/us/media/english/us_pron/${word.charAt(0)}/${word}.mp3`;
            const audio = new Audio(audioUrl);
            
            audio.onerror = () => {
                console.log('❌ Cambridge audio also failed');
            };
            
            await audio.play().catch(err => {
                console.log('❌ Audio play failed:', err);
            });
        } catch (audioError) {
            console.error('❌ Cambridge audio error:', audioError);
        }
    }
}

// Helper function to get auth token from authManager
function getAuthToken() {
    // Use authManager if available (from auth.js)
    if (typeof authManager !== 'undefined' && authManager.getToken) {
        return authManager.getToken();
    }
    // Fallback to localStorage for backward compatibility
    return localStorage.getItem('token');
}

// ==========================================
// AI-Powered Vocabulary Learning
// ==========================================

async function learnVocabulary() {
    const word = document.getElementById('vocab-learn-word').value.trim();
    const language = document.getElementById('vocab-learn-language').value;
    const statusDiv = document.getElementById('vocab-learn-status');
    const resultDiv = document.getElementById('vocab-learn-result');
    
    // Validate
    if (!word) {
        statusDiv.textContent = '❌ Please enter a word to learn';
        statusDiv.style.color = 'red';
        return;
    }
    
    // Check authentication
    const token = getAuthToken();
    if (!token) {
        statusDiv.textContent = '🔐 Please sign in to use AI learning';
        statusDiv.style.color = 'orange';
        return;
    }
    
    statusDiv.textContent = '🤖 AI is teaching you about this word...';
    statusDiv.style.color = 'blue';
    resultDiv.innerHTML = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/vocabulary/learn?word=${encodeURIComponent(word)}&language=${language}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            statusDiv.textContent = `✅ ${data.message}`;
            statusDiv.style.color = 'green';
            
            // Fetch the newly created vocabulary entry to display it
            const vocabResponse = await fetch(`${API_BASE_URL}/vocabulary/${data.vocab_id}`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
            const vocabData = await vocabResponse.json();
            
            if (vocabResponse.ok && vocabData.success) {
                const entry = vocabData.data;
                
                // Display the learned vocabulary in a nice format
                resultDiv.innerHTML = `
                    <div style="border: 2px solid #4caf50; border-radius: 8px; padding: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);">
                        <h3 style="margin: 0 0 15px 0; color: #2c3e50; font-size: 2em;">
                            ${entry.word}
                            ${entry.pronunciation ? `
                                <span onclick="playCambridgeAudio('${entry.word.toLowerCase()}')" style="text-decoration: none; margin-left: 10px; cursor: pointer; color: #7f8c8d; font-size: 0.6em;" title="Listen pronunciation">
                                    🗣️ ${entry.pronunciation}
                                </span>
                            ` : ''}
                        </h3>
                        
                        <div style="margin: 15px 0;">
                            <strong style="color: #3498db;">📖 Definition:</strong>
                            <p style="margin: 5px 0; font-size: 1.1em; line-height: 1.6;">${entry.definition}</p>
                        </div>
                        
                        ${entry.sample_sentence ? `
                            <div style="margin: 15px 0;">
                                <strong style="color: #9b59b6;">💬 Example:</strong>
                                <p style="margin: 5px 0; font-style: italic; font-size: 1.05em; line-height: 1.6;">"${entry.sample_sentence}"</p>
                            </div>
                        ` : ''}
                        
                        ${entry.related_words && entry.related_words.length > 0 ? `
                            <div style="margin: 15px 0;">
                                <strong style="color: #e67e22;">🔗 Related Words:</strong>
                                <p style="margin: 5px 0;">${entry.related_words.join(', ')}</p>
                            </div>
                        ` : ''}
                        
                        ${entry.difficulty ? `
                            <div style="margin: 15px 0;">
                                <span style="background: #3498db; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.9em;">
                                    ${entry.difficulty.toUpperCase()}
                                </span>
                            </div>
                        ` : ''}
                        
                        ${entry.tags && entry.tags.length > 0 ? `
                            <div style="margin: 15px 0;">
                                ${entry.tags.map(tag => `<span style="background: #ecf0f1; color: #2c3e50; padding: 4px 10px; border-radius: 10px; font-size: 0.85em; margin-right: 5px;">#${tag}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                `;
            }
            
            // Clear input
            document.getElementById('vocab-learn-word').value = '';
            
            // Auto-load Today's Activity to show the newly learned word
            // Wait 2 seconds to ensure database has been updated
            setTimeout(() => {
                console.log('Auto-loading Today\'s Activity after learning word...');
                loadTodayActivity();
            }, 2000);
            
        } else {
            throw new Error(data.message || data.detail || 'Failed to learn vocabulary');
        }
    } catch (error) {
        console.error('Error learning vocabulary:', error);
        statusDiv.textContent = `❌ Error: ${error.message}`;
        statusDiv.style.color = 'red';
    }
}

// ==========================================
// Add Vocabulary Functionality (Manual)
// ==========================================

async function addVocabulary() {
    const statusDiv = document.getElementById('vocab-add-status');
    
    // Get form values
    const word = document.getElementById('vocab-add-word').value.trim();
    const definition = document.getElementById('vocab-add-definition').value.trim();
    const pronunciation = document.getElementById('vocab-add-pronunciation').value.trim();
    const sampleSentence = document.getElementById('vocab-add-sentence').value.trim();
    const language = document.getElementById('vocab-add-language').value;
    const difficulty = document.getElementById('vocab-add-difficulty').value;
    const relatedWordsInput = document.getElementById('vocab-add-related').value.trim();
    const tagsInput = document.getElementById('vocab-add-tags').value.trim();
    const notes = document.getElementById('vocab-add-notes').value.trim();
    
    // Validate required fields
    if (!word) {
        statusDiv.textContent = '❌ Please enter a word';
        statusDiv.style.color = 'red';
        return;
    }
    
    if (!definition) {
        statusDiv.textContent = '❌ Please enter a definition';
        statusDiv.style.color = 'red';
        return;
    }
    
    // Check authentication
    const token = getAuthToken();
    if (!token) {
        statusDiv.textContent = '🔐 Please sign in to add vocabulary';
        statusDiv.style.color = 'orange';
        return;
    }
    
    // Parse comma-separated inputs
    const relatedWords = relatedWordsInput ? relatedWordsInput.split(',').map(w => w.trim()).filter(w => w) : [];
    const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(t => t) : [];
    
    statusDiv.textContent = '⏳ Adding vocabulary...';
    statusDiv.style.color = 'blue';
    
    try {
        const response = await fetch(`${API_BASE_URL}/vocabulary/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                word: word,
                definition: definition,
                pronunciation: pronunciation || null,
                sample_sentence: sampleSentence || null,
                related_words: relatedWords,
                language: language,
                difficulty: difficulty || null,
                tags: tags,
                notes: notes || null
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            statusDiv.textContent = `✅ ${data.message}`;
            statusDiv.style.color = 'green';
            
            // Clear form
            document.getElementById('vocab-add-word').value = '';
            document.getElementById('vocab-add-definition').value = '';
            document.getElementById('vocab-add-pronunciation').value = '';
            document.getElementById('vocab-add-sentence').value = '';
            document.getElementById('vocab-add-language').value = 'english';
            document.getElementById('vocab-add-difficulty').value = '';
            document.getElementById('vocab-add-related').value = '';
            document.getElementById('vocab-add-tags').value = '';
            document.getElementById('vocab-add-notes').value = '';
            
            // Show success for 3 seconds
            setTimeout(() => {
                statusDiv.textContent = '';
            }, 3000);
        } else {
            throw new Error(data.message || 'Failed to add vocabulary');
        }
    } catch (error) {
        console.error('Error adding vocabulary:', error);
        statusDiv.textContent = `❌ Error: ${error.message}`;
        statusDiv.style.color = 'red';
    }
}

// ==========================================
// Word Search Functionality
// ==========================================

async function searchVocabulary() {
    const query = document.getElementById('vocab-search-query').value.trim();
    const semanticSearch = document.getElementById('vocab-semantic-search').checked;
    const statusDiv = document.getElementById('vocab-search-status');
    const resultsDiv = document.getElementById('vocab-search-results');

    if (!query) {
        statusDiv.textContent = '⚠️ Please enter a word or meaning to search';
        statusDiv.style.color = 'orange';
        return;
    }

    statusDiv.textContent = '🔍 Searching vocabulary...';
    statusDiv.style.color = '#64b5f6';
    resultsDiv.innerHTML = '';

    try {
        const token = getAuthToken();
        if (!token) {
            statusDiv.textContent = '🔐 Please sign in to search vocabulary';
            statusDiv.style.color = '#ff9800';
            return;
        }

        const response = await fetch(`${API_BASE_URL}/vocabulary/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                query: query,
                limit: 10,
                use_semantic_search: semanticSearch,
                exact_match: !semanticSearch
            })
        });

        if (!response.ok) {
            throw new Error(`Search failed: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.results && data.results.length > 0) {
            statusDiv.textContent = `✅ Found ${data.results.length} word(s)`;
            statusDiv.style.color = '#4caf50';
            displaySearchResults(data.results, semanticSearch);
        } else {
            statusDiv.textContent = '📭 No words found matching your search';
            statusDiv.style.color = '#ff9800';
        }
    } catch (error) {
        console.error('Search error:', error);
        statusDiv.textContent = `❌ Error: ${error.message}`;
        statusDiv.style.color = '#f44336';
    }
}

function displaySearchResults(results, isSemanticSearch) {
    const resultsDiv = document.getElementById('vocab-search-results');
    
    let html = '<div class="vocab-search-list">';
    
    results.forEach((result, index) => {
        // API returns {entry: {...}, relevance_score: 0.5}
        const entry = result.entry || result;
        const score = result.relevance_score || result.score || 0;
        const scoreDisplay = isSemanticSearch && score ? ` (${(score * 100).toFixed(1)}% match)` : '';
        
        html += `
            <div class="vocab-item" data-word-id="${entry.vocab_id || entry.id || ''}">
                <div class="vocab-item-header">
                    <h4 class="vocab-word">${entry.word}${scoreDisplay}</h4>
                    ${entry.pronunciation ? `<span class="vocab-pronunciation"><span onclick="playCambridgeAudio('${entry.word.toLowerCase()}')" style="cursor: pointer; text-decoration: none; color: inherit;" title="Listen pronunciation">🗣️</span> [${entry.pronunciation}]</span>` : ''}
                </div>
                <div class="vocab-definition"><strong>Definition:</strong> ${entry.definition || ''}</div>
                ${entry.sample_sentence ? `<div class="vocab-example"><strong>Example:</strong> "${entry.sample_sentence}"</div>` : ''}
                ${entry.related_words && entry.related_words.length > 0 ? `
                    <div class="vocab-related">
                        <strong>🔗 Similar Words:</strong> ${entry.related_words.join(', ')}
                    </div>
                ` : ''}
                <div class="vocab-meta">
                    ${entry.review_count !== undefined ? `<span>📊 Reviewed: ${entry.review_count} times</span>` : ''}
                    ${entry.next_review_date ? `<span>⏰ Next review: ${new Date(entry.next_review_date).toLocaleDateString()}</span>` : ''}
                </div>
                <div class="vocab-actions">
                    <button class="btn-secondary btn-sm" onclick="showRelatedWords('${entry.word}', ${entry.vocab_id || entry.id || 'null'})">
                        🌐 Show Related
                    </button>
                    ${entry.vocab_id || entry.id ? `
                        <button class="btn-secondary btn-sm" onclick="deleteWord(${entry.vocab_id || entry.id})">
                            🗑️ Delete
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    resultsDiv.innerHTML = html;
}

// ==========================================
// Daily Review Functionality (Flashcards)
// ==========================================

async function loadReviewWords() {
    const statusDiv = document.getElementById('vocab-review-status');
    const resultsDiv = document.getElementById('vocab-review-results');

    statusDiv.textContent = '📚 Loading all words due for review...';
    statusDiv.style.color = '#64b5f6';
    // Don't clear resultsDiv here - it contains the flashcards div we need!

    try {
        // Check if user is logged in
        const token = getAuthToken();
        if (!token) {
            statusDiv.textContent = '🔐 Please sign in to review words';
            statusDiv.style.color = '#ff9800';
            return;
        }

        const response = await fetch(`${API_BASE_URL}/vocabulary/review/due`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({})
        });

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Please sign in again - your session may have expired');
            }
            throw new Error(`Failed to load review words (${response.status})`);
        }

        const data = await response.json();
        // API returns {data: Array} not {words: Array}
        currentReviewWords = data.data || data.words || [];
        
        console.log('Review API response:', data);
        console.log('Review words loaded:', currentReviewWords.length);

        if (currentReviewWords.length > 0) {
            statusDiv.textContent = `✅ Loaded ${currentReviewWords.length} word(s) for review`;
            statusDiv.style.color = '#4caf50';
            currentReviewIndex = 0;
            reviewStats = { correct: 0, total: 0 };
            showFlashcard();
        } else {
            statusDiv.textContent = '🎉 No words due for review! Great job!';
            statusDiv.style.color = '#4caf50';
            resultsDiv.innerHTML = '<div class="info-message">🎯 All caught up! Check back tomorrow.</div>';
        }
    } catch (error) {
        console.error('Review load error:', error);
        statusDiv.textContent = `❌ Error: ${error.message}`;
        statusDiv.style.color = '#f44336';
    }
}

function showFlashcard() {
    const flashcardsDiv = document.getElementById('review-flashcards');
    const resultsDiv = document.getElementById('vocab-review-results');
    
    if (!flashcardsDiv || !resultsDiv) {
        console.error('Flashcard elements not found');
        return;
    }
    
    if (currentReviewIndex >= currentReviewWords.length) {
        // Review complete
        flashcardsDiv.style.display = 'none';
        const accuracy = reviewStats.total > 0 ? ((reviewStats.correct / reviewStats.total) * 100).toFixed(1) : 0;
        resultsDiv.innerHTML = `
            <div class="review-complete">
                <h3>🎉 Review Complete!</h3>
                <div class="review-stats">
                    <div class="stat-item">
                        <span class="stat-label">Words Reviewed:</span>
                        <span class="stat-value">${reviewStats.total}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Correct:</span>
                        <span class="stat-value">${reviewStats.correct}</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Accuracy:</span>
                        <span class="stat-value">${accuracy}%</span>
                    </div>
                </div>
                <button class="btn-primary" onclick="loadReviewWords()">
                    🔄 Start New Review
                </button>
            </div>
        `;
        return;
    }

    const word = currentReviewWords[currentReviewIndex];
    const progress = `${currentReviewIndex + 1} / ${currentReviewWords.length}`;

    flashcardsDiv.style.display = 'block';
    
    flashcardsDiv.innerHTML = `
        <div class="flashcard">
            <div class="flashcard-progress">${progress}</div>
            <div class="flashcard-front" id="flashcard-front">
                <h2 class="flashcard-word">${word.word}</h2>
                ${word.pronunciation ? `
                    <div class="flashcard-pronunciation">
                        <span onclick="playCambridgeAudio('${word.word.toLowerCase()}')" style="cursor: pointer; font-size: 1.5em;" title="Listen pronunciation">🗣️</span>
                        <span style="margin-left: 10px;">[${word.pronunciation}]</span>
                    </div>
                ` : ''}
                <button class="btn-primary btn-lg" onclick="flipFlashcard()">
                    🔄 Show Definition
                </button>
            </div>
            <div class="flashcard-back" id="flashcard-back" style="display: none;">
                <h3 class="flashcard-word">${word.word}</h3>
                ${word.pronunciation ? `
                    <div class="flashcard-pronunciation">
                        <span onclick="playCambridgeAudio('${word.word.toLowerCase()}')" style="cursor: pointer; font-size: 1.3em;" title="Listen pronunciation">🗣️</span>
                        <span style="margin-left: 10px;">[${word.pronunciation}]</span>
                    </div>
                ` : ''}
                <div class="flashcard-definition"><strong>📖 Definition:</strong> ${word.definition}</div>
                ${word.sample_sentence ? `<div class="flashcard-example"><strong>💬 Example:</strong> "${word.sample_sentence}"</div>` : ''}
                ${word.related_words && word.related_words.length > 0 ? `
                    <div class="flashcard-related">
                        <strong>🔗 Similar Words:</strong> ${word.related_words.join(', ')}
                    </div>
                ` : ''}
                <div class="flashcard-actions">
                    <button class="btn-secondary btn-lg" onclick="rateFlashcard(${word.id}, 'again')">
                        😞 Again
                    </button>
                    <button class="btn-secondary btn-lg" onclick="rateFlashcard(${word.id}, 'hard')">
                        😐 Hard
                    </button>
                    <button class="btn-primary btn-lg" onclick="rateFlashcard(${word.id}, 'good')">
                        😊 Good
                    </button>
                    <button class="btn-primary btn-lg" onclick="rateFlashcard(${word.id}, 'easy')">
                        😄 Easy
                    </button>
                </div>
            </div>
        </div>
    `;
}

function flipFlashcard() {
    document.getElementById('flashcard-front').style.display = 'none';
    document.getElementById('flashcard-back').style.display = 'block';
}

async function rateFlashcard(wordId, quality) {
    const statusDiv = document.getElementById('vocab-review-status');
    
    try {
        const qualityMap = { 'again': 0, 'hard': 1, 'good': 3, 'easy': 5 };
        const qualityScore = qualityMap[quality] || 3;

        const response = await fetch(`${API_BASE_URL}/vocabulary/${wordId}/review`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify({ quality: qualityScore })
        });

        if (!response.ok) {
            throw new Error('Failed to update review');
        }

        // Update stats
        reviewStats.total++;
        if (quality === 'good' || quality === 'easy') {
            reviewStats.correct++;
        }

        // Move to next card
        currentReviewIndex++;
        showFlashcard();

    } catch (error) {
        console.error('Review update error:', error);
        statusDiv.textContent = `⚠️ Error updating review: ${error.message}`;
        statusDiv.style.color = '#f44336';
    }
}

// ==========================================
// Word Distance Visualization
// ==========================================

let vocabGraph = null;
let vocabZoom = null;

// Helper function to learn a word and then visualize its relationships
async function learnWordAndVisualize(word) {
    const statusDiv = document.getElementById('vocab-distance-status');
    const language = document.getElementById('vocab-learn-language')?.value || 'en';
    
    // Clear previous content and show loading
    statusDiv.innerHTML = `<span style="color: #2196f3;">🤖 Learning "${word}" with AI...</span>`;
    
    try {
        const response = await fetch(`${API_BASE_URL}/vocabulary/learn?word=${encodeURIComponent(word)}&language=${language}`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`
            }
        });
        
        const data = await response.json();
        console.log('Learn API response:', data);
        
        if (response.ok && data.success) {
            statusDiv.innerHTML = `<span style="color: #4caf50;">✅ Learned "${word}"! Now building relationship graph...</span>`;
            
            // Wait longer for the database and vector indexing to complete
            // Show countdown to give user feedback
            let countdown = 8;
            const countdownInterval = setInterval(() => {
                countdown--;
                if (countdown > 0) {
                    statusDiv.innerHTML = `<span style="color: #4caf50;">✅ Learned "${word}"! Preparing visualization in ${countdown}s...</span>`;
                }
            }, 1000);
            
            setTimeout(async () => {
                clearInterval(countdownInterval);
                // Set the word in the input field
                document.getElementById('vocab-center-word').value = word;
                
                // Try to visualize, with retry logic
                const maxRetries = 2;
                let retryCount = 0;
                
                while (retryCount <= maxRetries) {
                    try {
                        statusDiv.innerHTML = `<span style="color: #2196f3;">🔍 Searching for "${word}"${retryCount > 0 ? ` (attempt ${retryCount + 1})` : ''}...</span>`;
                        
                        // Search for the word
                        const searchResponse = await fetch(`${API_BASE_URL}/vocabulary/search`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${getAuthToken()}`
                            },
                            body: JSON.stringify({ 
                                query: word, 
                                limit: 1,
                                exact_match: true,
                                use_semantic_search: false
                            })
                        });
                        
                        const searchData = await searchResponse.json();
                        console.log(`Search attempt ${retryCount + 1} for "${word}":`, searchData);
                        
                        if (searchData.results && searchData.results.length > 0) {
                            // Found it! Now visualize
                            await visualizeWordDistance(true);
                            break;
                        } else if (retryCount < maxRetries) {
                            // Not found yet, wait and retry
                            retryCount++;
                            await new Promise(resolve => setTimeout(resolve, 2000));
                        } else {
                            // Final retry failed
                            statusDiv.innerHTML = `<span style="color: #ff9800;">⚠️ Word "${word}" was learned but not yet indexed. Please try the "Show Word Relationships" button in a few seconds.</span>`;
                            break;
                        }
                    } catch (error) {
                        console.error('Error in retry logic:', error);
                        retryCount++;
                        if (retryCount > maxRetries) {
                            throw error;
                        }
                        await new Promise(resolve => setTimeout(resolve, 2000));
                    }
                }
            }, 8000); // Increased from 6000ms to 8000ms
        } else {
            const errorMsg = data.detail || data.message || 'Failed to learn word';
            throw new Error(errorMsg);
        }
    } catch (error) {
        console.error('Error learning word:', error);
        statusDiv.innerHTML = `<span style="color: #f44336;">❌ Error: ${error.message}</span>`;
    }
}

async function visualizeWordDistance(fromLearn = false) {
    const centerWord = document.getElementById('vocab-center-word').value.trim();
    const limit = 10; // Fixed number of related words to display
    const statusDiv = document.getElementById('vocab-distance-status');
    const vizDiv = document.getElementById('vocab-distance-visualization');

    if (!centerWord) {
        statusDiv.textContent = '⚠️ Please enter a center word';
        statusDiv.style.color = 'orange';
        return;
    }

    // Save to search history
    saveRelationshipSearch(centerWord);

    // Only show loading if not coming from learn (which already shows status)
    if (!fromLearn) {
        statusDiv.textContent = '🌐 Loading word relationships...';
        statusDiv.style.color = '#64b5f6';
    }
    vizDiv.style.display = 'none';

    try {
        // First, search for the center word to get its ID
        // Use exact match to find the specific word
        const searchResponse = await fetch(`${API_BASE_URL}/vocabulary/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify({ 
                query: centerWord, 
                limit: 1,
                exact_match: true,  // Use exact match to find the word
                use_semantic_search: false  // Don't use semantic search for finding the center word
            })
        });

        if (!searchResponse.ok) {
            throw new Error('Failed to find center word');
        }

        const searchData = await searchResponse.json();
        console.log('Search response for center word:', searchData);
        
        if (!searchData.results || searchData.results.length === 0) {
            // Word not found - offer to learn it
            statusDiv.innerHTML = `
                <div style="padding: 15px; background: #fff3cd; border-radius: 8px; border: 1px solid #ffc107;">
                    <p style="margin: 0 0 10px 0;">⚠️ Word "<strong>${centerWord}</strong>" not found in your vocabulary.</p>
                    <button class="btn-primary" onclick="learnWordAndVisualize('${centerWord}')">
                        🤖 Learn "${centerWord}" with AI
                    </button>
                </div>
            `;
            statusDiv.style.color = '#856404';
            return; // Exit early, don't throw error
        }

        // Extract the actual entry from the search result
        const searchResult = searchData.results[0];
        const centerWordData = searchResult.entry || searchResult;  // Handle both formats
        console.log('Center word data:', centerWordData);

        // Get related words
        const relatedResponse = await fetch(`${API_BASE_URL}/vocabulary/${centerWordData.id}/related?limit=${limit}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`
            }
        });

        if (!relatedResponse.ok) {
            console.error('Failed to load related words, status:', relatedResponse.status);
            throw new Error('Failed to load related words');
        }

        const relatedData = await relatedResponse.json();
        console.log('Related words API response:', relatedData);
        
        // Handle the response structure with proper distance scores
        let relatedWords = relatedData.related_words || [];
        
        // Transform the response to include both entry and distance
        if (relatedWords.length > 0) {
            // Check if we have the new format with entry and distance
            if (relatedWords[0].hasOwnProperty('entry') && relatedWords[0].hasOwnProperty('distance')) {
                // New format: already has entry and distance
                relatedWords = relatedWords.map(item => ({
                    ...item.entry,
                    distance: item.distance,
                    word: item.entry.word,
                    definition: item.entry.definition,
                    pronunciation: item.entry.pronunciation,
                    sample_sentence: item.entry.sample_sentence,
                    id: item.entry.id
                }));
            } else if (!relatedWords[0].hasOwnProperty('distance')) {
                // Old format or fallback: add mock distance
                relatedWords = relatedWords.map((entry, index) => ({
                    ...entry,
                    distance: 0.3 + (index * 0.1), // Mock increasing distance
                    word: entry.word,
                    definition: entry.definition,
                    pronunciation: entry.pronunciation,
                    sample_sentence: entry.sample_sentence,
                    id: entry.id
                }));
            }
        }
        
        console.log('Processed related words:', relatedWords);

        if (relatedWords && relatedWords.length > 0) {
            statusDiv.textContent = `✅ Found ${relatedWords.length} related word(s)`;
            statusDiv.style.color = '#4caf50';
            renderWordGraph(centerWordData, relatedWords);
            vizDiv.style.display = 'block';
        } else {
            // No related words yet - this is normal for newly learned words
            // Show the center word alone in the graph
            statusDiv.innerHTML = `
                <div style="padding: 15px; background: #e3f2fd; border-radius: 8px; border: 1px solid #2196f3;">
                    <p style="margin: 0;">ℹ️ Word "<strong>${centerWord}</strong>" is in your vocabulary!</p>
                    <p style="margin: 10px 0 0 0; font-size: 0.9em; color: #666;">
                        No related words found yet. Learn more vocabulary to build relationships! Related words are discovered based on semantic similarity.
                    </p>
                </div>
            `;
            statusDiv.style.color = '#1976d2';
            
            // Still show the visualization with just the center word
            renderWordGraph(centerWordData, []);
            vizDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Visualization error:', error);
        statusDiv.textContent = `❌ Error: ${error.message}`;
        statusDiv.style.color = '#f44336';
    }
}

function renderWordGraph(centerWord, relatedWords) {
    const container = document.getElementById('vocab-graph-viz');
    const infoDiv = document.getElementById('vocab-graph-info');
    
    // Clear previous graph
    container.innerHTML = '';
    infoDiv.innerHTML = '';

    // Prepare graph data
    const nodes = [
        { id: centerWord.word, word: centerWord.word, type: 'center', ...centerWord }
    ];

    const links = [];

    relatedWords.forEach((related, index) => {
        nodes.push({
            id: related.word,
            word: related.word,
            type: 'related',
            ...related
        });

        links.push({
            source: centerWord.word,
            target: related.word,
            distance: related.distance || 0.5
        });
    });

    // Set up SVG
    const width = container.clientWidth || 800;
    const height = 600;

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create zoom behavior
    vocabZoom = d3.zoom()
        .scaleExtent([0.5, 5])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });

    svg.call(vocabZoom);

    const g = svg.append('g');

    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links)
            .id(d => d.id)
            .distance(d => (1 - d.distance) * 200 + 100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(50));

    // Create links
    const link = g.append('g')
        .selectAll('line')
        .data(links)
        .enter()
        .append('line')
        .attr('stroke', '#999')
        .attr('stroke-opacity', 0.6)
        .attr('stroke-width', d => (1 - d.distance) * 3 + 1);

    // Create nodes
    const node = g.append('g')
        .selectAll('g')
        .data(nodes)
        .enter()
        .append('g')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));

    // Add circles to nodes
    node.append('circle')
        .attr('r', d => d.type === 'center' ? 30 : 20)
        .attr('fill', d => d.type === 'center' ? '#64b5f6' : '#90caf9')
        .attr('stroke', '#fff')
        .attr('stroke-width', 2);

    // Add text labels
    node.append('text')
        .text(d => d.word)
        .attr('x', 0)
        .attr('y', d => d.type === 'center' ? 40 : 30)
        .attr('text-anchor', 'middle')
        .attr('fill', '#fff')
        .attr('font-size', d => d.type === 'center' ? '14px' : '12px')
        .attr('font-weight', d => d.type === 'center' ? 'bold' : 'normal');

    // Add click handler for nodes
    node.on('click', (event, d) => {
        showWordInfo(d, infoDiv);
    });

    // Update positions on simulation tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Drag functions
    function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
    }

    function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
    }

    function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
    }

    vocabGraph = { simulation, svg, g };
    
    // Show initial info about the center word
    if (relatedWords.length === 0) {
        infoDiv.innerHTML = `
            <div class="word-info-panel">
                <h4>${centerWord.word}</h4>
                ${centerWord.pronunciation ? `<div class="pronunciation">[${centerWord.pronunciation}]</div>` : ''}
                <div class="definition">${centerWord.definition || 'No definition available'}</div>
                ${centerWord.sample_sentence ? `<div class="example">"${centerWord.sample_sentence}"</div>` : ''}
                <div style="margin-top: 15px; padding: 10px; background: #e3f2fd; border-radius: 6px; font-size: 0.9em;">
                    💡 <strong>Tip:</strong> Learn more vocabulary words to see relationships appear in the graph!
                </div>
            </div>
        `;
    }
}

function showWordInfo(wordData, infoDiv) {
    const distance = wordData.distance !== undefined ? `${(wordData.distance * 100).toFixed(1)}%` : 'Center';
    
    infoDiv.innerHTML = `
        <div class="word-info-panel">
            <h4>${wordData.word}</h4>
            ${wordData.pronunciation ? `<div class="pronunciation">[${wordData.pronunciation}]</div>` : ''}
            <div class="definition">${wordData.definition || 'No definition available'}</div>
            ${wordData.example_sentence ? `<div class="example">"${wordData.example_sentence}"</div>` : ''}
            <div class="distance-info">
                <strong>Semantic Distance:</strong> ${distance}
            </div>
        </div>
    `;
}

function vocabZoomIn() {
    if (vocabZoom && vocabGraph) {
        vocabGraph.svg.transition().call(vocabZoom.scaleBy, 1.3);
    }
}

function vocabZoomOut() {
    if (vocabZoom && vocabGraph) {
        vocabGraph.svg.transition().call(vocabZoom.scaleBy, 0.7);
    }
}

function vocabCenter() {
    if (vocabZoom && vocabGraph) {
        const width = vocabGraph.svg.node().clientWidth;
        const height = vocabGraph.svg.node().clientHeight;
        vocabGraph.svg.transition()
            .call(vocabZoom.transform, d3.zoomIdentity.translate(0, 0).scale(1));
    }
}

function closeVocabVisualization() {
    const vizDiv = document.getElementById('vocab-distance-visualization');
    vizDiv.style.display = 'none';
    if (vocabGraph && vocabGraph.simulation) {
        vocabGraph.simulation.stop();
    }
}

// ==========================================
// Vocabulary Statistics
// ==========================================

async function loadVocabularyStats() {
    const statusDiv = document.getElementById('vocab-stats-status');
    const resultsDiv = document.getElementById('vocab-stats-results');

    statusDiv.textContent = '📊 Loading statistics...';
    statusDiv.style.color = '#64b5f6';
    resultsDiv.innerHTML = '';

    try {
        const response = await fetch(`${API_BASE_URL}/vocabulary/stats/summary`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to load statistics');
        }

        const stats = await response.json();

        statusDiv.textContent = '✅ Statistics loaded';
        statusDiv.style.color = '#4caf50';

        resultsDiv.innerHTML = `
            <div class="vocab-stats-grid">
                <div class="stat-card">
                    <div class="stat-icon">📚</div>
                    <div class="stat-label">Total Words</div>
                    <div class="stat-value">${stats.total_words || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">⏰</div>
                    <div class="stat-label">Due for Review</div>
                    <div class="stat-value">${stats.words_due_today || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">✅</div>
                    <div class="stat-label">Total Reviews</div>
                    <div class="stat-value">${stats.total_reviews || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">🎯</div>
                    <div class="stat-label">Mastered Words</div>
                    <div class="stat-value">${stats.mastered_words || 0}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">📅</div>
                    <div class="stat-label">Study Streak</div>
                    <div class="stat-value">${stats.study_streak || 0} days</div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon">⭐</div>
                    <div class="stat-label">Average Ease</div>
                    <div class="stat-value">${stats.average_ease ? stats.average_ease.toFixed(1) : 'N/A'}</div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Stats error:', error);
        statusDiv.textContent = `❌ Error: ${error.message}`;
        statusDiv.style.color = '#f44336';
    }
}

// ==========================================
// Helper Functions
// ==========================================

async function showRelatedWords(word, wordId) {
    if (!wordId) {
        alert('Cannot show related words: word ID not available');
        return;
    }

    document.getElementById('vocab-center-word').value = word;
    document.getElementById('vocab-distance-btn').click();
    
    // Scroll to visualization
    setTimeout(() => {
        document.getElementById('vocab-distance-visualization').scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
        });
    }, 500);
}

async function deleteWord(wordId) {
    if (!confirm('Are you sure you want to delete this word?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/vocabulary/${wordId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to delete word');
        }

        alert('✅ Word deleted successfully');
        
        // Refresh search results
        const searchBtn = document.getElementById('vocab-search-btn');
        if (searchBtn) {
            searchBtn.click();
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert(`❌ Error: ${error.message}`);
    }
}

// ==========================================
// Event Listeners Setup
// ==========================================

document.addEventListener('DOMContentLoaded', () => {
    // Word Search
    const searchBtn = document.getElementById('vocab-search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', searchVocabulary);
    }

    const searchInput = document.getElementById('vocab-search-query');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchVocabulary();
        });
    }

    // Daily Review
    const reviewBtn = document.getElementById('vocab-review-btn');
    if (reviewBtn) {
        reviewBtn.addEventListener('click', loadReviewWords);
    }

    // Word Distance Visualization
    const distanceBtn = document.getElementById('vocab-distance-btn');
    if (distanceBtn) {
        distanceBtn.addEventListener('click', visualizeWordDistance);
    }

    const centerWordInput = document.getElementById('vocab-center-word');
    if (centerWordInput) {
        centerWordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') visualizeWordDistance();
        });
    }

    // Visualization Controls
    const zoomInBtn = document.getElementById('vocab-zoom-in');
    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', vocabZoomIn);
    }

    const zoomOutBtn = document.getElementById('vocab-zoom-out');
    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', vocabZoomOut);
    }

    const centerBtn = document.getElementById('vocab-center');
    if (centerBtn) {
        centerBtn.addEventListener('click', vocabCenter);
    }

    const closeVizBtn = document.getElementById('vocab-close-viz');
    if (closeVizBtn) {
        closeVizBtn.addEventListener('click', closeVocabVisualization);
    }

    // Statistics
    const statsBtn = document.getElementById('vocab-stats-btn');
    if (statsBtn) {
        statsBtn.addEventListener('click', loadVocabularyStats);
    }
});

// Make functions globally accessible
window.playCambridgeAudio = playCambridgeAudio;
window.searchVocabulary = searchVocabulary;
window.loadReviewWords = loadReviewWords;
window.flipFlashcard = flipFlashcard;
window.rateFlashcard = rateFlashcard;
window.visualizeWordDistance = visualizeWordDistance;
window.learnWordAndVisualize = learnWordAndVisualize;
window.vocabZoomIn = vocabZoomIn;
window.vocabZoomOut = vocabZoomOut;
window.vocabCenter = vocabCenter;
window.closeVocabVisualization = closeVocabVisualization;
window.loadVocabularyStats = loadVocabularyStats;
window.showRelatedWords = showRelatedWords;
window.deleteWord = deleteWord;
window.loadTodayActivity = loadTodayActivity;
window.loadRelationshipHistory = loadRelationshipHistory;

// ==========================================
// Today's Activity Feature
// ==========================================

async function loadTodayActivity() {
    const resultsDiv = document.getElementById('today-activity-results');
    resultsDiv.innerHTML = '<div style="color: #64b5f6; padding: 10px;">⏳ Loading today\'s activity...</div>';
    
    try {
        // Check if user is logged in
        const token = getAuthToken();
        if (!token) {
            resultsDiv.innerHTML = `
                <div style="padding: 15px; text-align: center; color: #ff9800;">
                    <div style="font-size: 2em; margin-bottom: 10px;">🔐</div>
                    <div><strong>Please sign in to view your activity</strong></div>
                    <div style="font-size: 0.9em; margin-top: 5px;">Click "Sign in with Google" at the top right</div>
                </div>
            `;
            return;
        }
        
        // Get today's date in local timezone - use last 48 hours to handle timezone issues
        const now = new Date();
        const twoDaysAgo = new Date(now.getTime() - (48 * 60 * 60 * 1000)); // 48 hours ago
        
        console.log('Filtering words from:', twoDaysAgo, 'to now:', now);
        
        // Fetch all vocabulary words added/modified today
        const response = await fetch(`${API_BASE_URL}/vocabulary/list`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                skip: 0,
                limit: 100,
                sort_by: 'created_at',
                sort_order: 'desc'
            })
        });

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Please sign in again - your session may have expired');
            }
            throw new Error(`Failed to load activity (${response.status})`);
        }

        const data = await response.json();
        
        console.log('API Response:', data);
        // FIX: API returns data.data, not data.words
        const allWords = data.data || data.words || [];
        console.log('Total words fetched:', allWords.length);
        
        // Just show words from last 24 hours (not strict "today")
        const oneDayAgo = new Date(now.getTime() - (24 * 60 * 60 * 1000));
        const recentWords = allWords.filter(word => {
            const wordDate = new Date(word.created_at);
            const isRecent = wordDate >= oneDayAgo;
            console.log(`Word "${word.word}" created_at:`, word.created_at, 'parsed as:', wordDate, 'is in last 24h?', isRecent);
            return isRecent;
        });
        
        console.log('Words from last 24 hours:', recentWords.length);

        if (recentWords.length === 0) {
            resultsDiv.innerHTML = `
                <div style="padding: 15px; text-align: center; color: #666;">
                    <div style="font-size: 2em; margin-bottom: 10px;">📭</div>
                    <div>No words learned in the last 24 hours.</div>
                    <div style="font-size: 0.9em; margin-top: 5px;">Start adding some vocabulary!</div>
                </div>
            `;
            return;
        }

        let html = `
            <div style="padding: 10px; background: white; border-radius: 6px; margin-top: 10px;">
                <div style="font-weight: 600; color: #4caf50; margin-bottom: 10px;">
                    ✅ ${recentWords.length} word(s) in last 24 hours
                </div>
                <div style="max-height: 300px; overflow-y: auto;">
        `;
        
        recentWords.forEach(word => {
            // Format time in user's local timezone with both date and time
            // Append 'Z' to indicate UTC time if not present
            const timestamp = word.created_at.endsWith('Z') ? word.created_at : word.created_at + 'Z';
            const localDate = new Date(timestamp);
            const timeStr = localDate.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });
            
            // Create expandable card with details (onclick to show full details)
            html += `
                <div style="padding: 8px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; border-left: 3px solid #64b5f6; cursor: pointer; transition: all 0.2s;" 
                     onmouseover="this.style.background='#e3f2fd'; this.style.transform='translateX(4px)';" 
                     onmouseout="this.style.background='#f5f5f5'; this.style.transform='translateX(0)';"
                     onclick="toggleWordDetails('${word.id}')">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span onclick="event.stopPropagation(); playCambridgeAudio('${word.word.toLowerCase()}')" style="cursor: pointer; font-size: 1.2em;" title="Listen pronunciation">🗣️</span>
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #333;">${word.word} ${word.pronunciation ? `<span style="color: #7f8c8d; font-size: 0.85em;">[${word.pronunciation}]</span>` : ''}</div>
                            <div style="font-size: 0.85em; color: #666; margin-top: 3px;">${word.definition.substring(0, 80)}${word.definition.length > 80 ? '...' : ''}</div>
                            <div style="font-size: 0.75em; color: #999; margin-top: 3px;">
                                🕒 ${timeStr}
                                ${word.category ? `• 📂 ${word.category}` : ''}
                                ${word.difficulty_level ? `• ⭐ Level ${word.difficulty_level}` : ''}
                            </div>
                        </div>
                        <div style="color: #64b5f6; font-size: 0.8em;">▶</div>
                    </div>
                    <div id="details-${word.id}" style="display: none; margin-top: 10px; padding: 10px; background: white; border-radius: 6px; border: 2px solid #4caf50;">
                        <div style="margin: 8px 0;">
                            <strong style="color: #3498db;">📖 Definition:</strong>
                            <div style="margin-top: 4px; line-height: 1.4;">${word.definition}</div>
                        </div>
                        ${word.sample_sentence ? `
                            <div style="margin: 8px 0;">
                                <strong style="color: #9b59b6;">💬 Example:</strong>
                                <div style="margin-top: 4px; font-style: italic; line-height: 1.4;">"${word.sample_sentence}"</div>
                            </div>
                        ` : ''}
                        ${word.related_words && word.related_words.length > 0 ? `
                            <div style="margin: 8px 0;">
                                <strong style="color: #e67e22;">🔗 Related:</strong>
                                <div style="margin-top: 4px;">${word.related_words.join(', ')}</div>
                            </div>
                        ` : ''}
                        ${word.difficulty ? `
                            <div style="margin-top: 8px;">
                                <span style="background: #3498db; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.85em;">
                                    ${word.difficulty.toUpperCase()}
                                </span>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
        
        resultsDiv.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading today activity:', error);
        resultsDiv.innerHTML = `
            <div style="padding: 10px; color: #f44336;">
                ❌ Error: ${error.message}
            </div>
        `;
    }
}

// ==========================================
// Relationship Search History Feature
// ==========================================

// Store search history in localStorage
function saveRelationshipSearch(word) {
    try {
        let history = JSON.parse(localStorage.getItem('vocab_relationship_history') || '[]');
        
        // Add new search with timestamp
        const entry = {
            word: word,
            timestamp: new Date().toISOString()
        };
        
        // Remove duplicates (keep most recent)
        history = history.filter(item => item.word.toLowerCase() !== word.toLowerCase());
        
        // Add to beginning
        history.unshift(entry);
        
        // Keep only last 50 searches
        history = history.slice(0, 50);
        
        localStorage.setItem('vocab_relationship_history', JSON.stringify(history));
    } catch (error) {
        console.error('Error saving search history:', error);
    }
}

async function loadRelationshipHistory() {
    const resultsDiv = document.getElementById('relationship-history-results');
    
    try {
        const history = JSON.parse(localStorage.getItem('vocab_relationship_history') || '[]');
        
        if (history.length === 0) {
            resultsDiv.innerHTML = `
                <div style="padding: 15px; text-align: center; color: #666;">
                    <div style="font-size: 2em; margin-bottom: 10px;">🔍</div>
                    <div>No relationship searches yet.</div>
                    <div style="font-size: 0.9em; margin-top: 5px;">Search for word relationships to build your history!</div>
                </div>
            `;
            return;
        }

        let html = `
            <div style="padding: 10px; background: white; border-radius: 6px; margin-top: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <div style="font-weight: 600; color: #7c3aed;">
                        📋 ${history.length} search(es) in history
                    </div>
                    <button onclick="clearRelationshipHistory()" style="padding: 4px 8px; font-size: 0.8em; background: #ff5252; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        🗑️ Clear History
                    </button>
                </div>
                <div style="max-height: 300px; overflow-y: auto;">
        `;
        
        history.forEach((entry, index) => {
            const date = new Date(entry.timestamp);
            const isToday = date.toDateString() === new Date().toDateString();
            const timeStr = isToday 
                ? date.toLocaleTimeString() 
                : date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
            
            html += `
                <div style="padding: 8px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; border-left: 3px solid #7c3aed; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 600; color: #333;">${entry.word}</div>
                        <div style="font-size: 0.75em; color: #999; margin-top: 3px;">
                            🕒 ${timeStr}
                        </div>
                    </div>
                    <button onclick="repeatRelationshipSearch('${entry.word}')" style="padding: 6px 12px; font-size: 0.85em; background: #7c3aed; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        🔄 Search Again
                    </button>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
        
        resultsDiv.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading relationship history:', error);
        resultsDiv.innerHTML = `
            <div style="padding: 10px; color: #f44336;">
                ❌ Error: ${error.message}
            </div>
        `;
    }
}

function clearRelationshipHistory() {
    if (confirm('Are you sure you want to clear your relationship search history?')) {
        localStorage.removeItem('vocab_relationship_history');
        loadRelationshipHistory();
    }
}

function repeatRelationshipSearch(word) {
    document.getElementById('vocab-center-word').value = word;
    visualizeWordDistance();
}

window.clearRelationshipHistory = clearRelationshipHistory;
window.repeatRelationshipSearch = repeatRelationshipSearch;

// ==========================================
// Event Listeners - Initialize when DOM is loaded
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    // Learn vocabulary button (AI-powered)
    const learnBtn = document.getElementById('vocab-learn-btn');
    if (learnBtn) {
        learnBtn.addEventListener('click', learnVocabulary);
    }
    
    // Add vocabulary button (manual - kept for backward compatibility)
    const addBtn = document.getElementById('vocab-add-btn');
    if (addBtn) {
        addBtn.addEventListener('click', addVocabulary);
    }
    
    // Search vocabulary button
    const searchBtn = document.getElementById('vocab-search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', searchVocabulary);
    }
    
    // Review button
    const reviewBtn = document.getElementById('vocab-review-btn');
    if (reviewBtn) {
        reviewBtn.addEventListener('click', loadReviewWords);
    }
    
    // Distance/relationship button
    const distanceBtn = document.getElementById('vocab-distance-btn');
    if (distanceBtn) {
        distanceBtn.addEventListener('click', visualizeWordDistance);
    }
    
    // Stats button
    const statsBtn = document.getElementById('vocab-stats-btn');
    if (statsBtn) {
        statsBtn.addEventListener('click', loadVocabularyStats);
    }
    
    // Enter key support for search
    const searchInput = document.getElementById('vocab-search-query');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchVocabulary();
            }
        });
    }
    
    // Enter key support for learn word (AI)
    const learnInput = document.getElementById('vocab-learn-word');
    if (learnInput) {
        learnInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                learnVocabulary();
            }
        });
    }
    
    // Enter key support for add word (manual)
    const addWordInput = document.getElementById('vocab-add-word');
    if (addWordInput) {
        addWordInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                // Focus on definition field when pressing Enter in word field
                document.getElementById('vocab-add-definition').focus();
            }
        });
    }
});
