// Authentication and Session Management for Second Brain

class AuthManager {
    constructor() {
        this.session = null;
        this.loadSession();
    }

    // Load session from localStorage
    loadSession() {
        try {
            const sessionData = localStorage.getItem('secondBrainSession');
            if (sessionData) {
                this.session = JSON.parse(sessionData);

                // Check if session is expired (24 hours)
                const loginTime = new Date(this.session.loginTime);
                const now = new Date();
                const hoursSinceLogin = (now - loginTime) / (1000 * 60 * 60);

                if (hoursSinceLogin >= 24) {
                    console.log('Session expired, logging out');
                    this.logout();
                    return false;
                }

                return true;
            }
            return false;
        } catch (e) {
            console.error('Error loading session:', e);
            this.logout();
            return false;
        }
    }

    // Check if user is authenticated
    isAuthenticated() {
        return this.session !== null && this.session.user !== null;
    }

    // Get current user info
    getUser() {
        return this.session?.user || null;
    }

    // Get authentication token
    getToken() {
        return this.session?.token || null;
    }

    // Logout and clear session
    logout() {
        this.session = null;
        localStorage.removeItem('secondBrainSession');
        localStorage.removeItem('second-brain-draft'); // Clear any saved drafts
        window.location.href = '/login.html';
    }

    // Require authentication (redirect to login if not authenticated)
    requireAuth() {
        if (!this.isAuthenticated()) {
            console.log('Not authenticated, redirecting to login');
            window.location.href = '/login.html';
            return false;
        }
        return true;
    }

    // Initialize user profile display
    initUserProfile() {
        if (!this.isAuthenticated()) {
            return;
        }

        const user = this.getUser();

        // Create user profile dropdown in header
        const header = document.querySelector('.header');
        if (header) {
            // Remove existing profile if any
            const existingProfile = document.getElementById('user-profile');
            if (existingProfile) {
                existingProfile.remove();
            }

            const profileHTML = `
                <div id="user-profile" style="
                    position: absolute;
                    top: 1rem;
                    right: 2rem;
                    display: flex;
                    align-items: center;
                    gap: 1rem;
                ">
                    <div style="text-align: right;">
                        <div style="font-weight: 600; color: var(--text-primary);">${this.escapeHtml(user.name)}</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary);">${this.escapeHtml(user.email)}</div>
                    </div>
                    <div style="position: relative;">
                        <img src="${user.picture}" 
                             alt="Profile" 
                             style="
                                width: 48px;
                                height: 48px;
                                border-radius: 50%;
                                border: 3px solid var(--primary-color);
                                cursor: pointer;
                                transition: var(--transition);
                             "
                             id="profile-picture"
                             title="Click for options">
                        <div id="profile-dropdown" style="
                            display: none;
                            position: absolute;
                            right: 0;
                            top: 60px;
                            background: var(--card-background);
                            border: 1px solid var(--border-color);
                            border-radius: var(--border-radius);
                            box-shadow: var(--shadow-lg);
                            min-width: 200px;
                            z-index: 1000;
                        ">
                            <div style="padding: 1rem; border-bottom: 1px solid var(--border-color);">
                                <div style="font-weight: 600; margin-bottom: 0.25rem;">${this.escapeHtml(user.name)}</div>
                                <div style="font-size: 0.85rem; color: var(--text-secondary);">${this.escapeHtml(user.email)}</div>
                            </div>
                            <button id="logout-btn" style="
                                width: 100%;
                                padding: 0.75rem 1rem;
                                border: none;
                                background: transparent;
                                text-align: left;
                                cursor: pointer;
                                transition: var(--transition);
                                font-size: 0.95rem;
                                color: var(--error-color);
                                font-weight: 500;
                            ">
                                🚪 Sign Out
                            </button>
                        </div>
                    </div>
                </div>
            `;

            header.style.position = 'relative';
            header.insertAdjacentHTML('beforeend', profileHTML);

            // Add dropdown toggle functionality
            const profilePic = document.getElementById('profile-picture');
            const dropdown = document.getElementById('profile-dropdown');
            const logoutBtn = document.getElementById('logout-btn');

            if (profilePic && dropdown) {
                profilePic.addEventListener('click', (e) => {
                    e.stopPropagation();
                    dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
                });

                // Hover effect for profile picture
                profilePic.addEventListener('mouseenter', () => {
                    profilePic.style.transform = 'scale(1.05)';
                    profilePic.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.3)';
                });

                profilePic.addEventListener('mouseleave', () => {
                    profilePic.style.transform = 'scale(1)';
                    profilePic.style.boxShadow = 'none';
                });

                // Hover effect for logout button
                if (logoutBtn) {
                    logoutBtn.addEventListener('mouseenter', () => {
                        logoutBtn.style.background = 'rgba(220, 38, 38, 0.1)';
                    });

                    logoutBtn.addEventListener('mouseleave', () => {
                        logoutBtn.style.background = 'transparent';
                    });
                }

                // Close dropdown when clicking outside
                document.addEventListener('click', () => {
                    dropdown.style.display = 'none';
                });

                dropdown.addEventListener('click', (e) => {
                    e.stopPropagation();
                });
            }

            if (logoutBtn) {
                logoutBtn.addEventListener('click', () => {
                    if (confirm('Are you sure you want to sign out?')) {
                        this.logout();
                    }
                });
            }
        }
    }

    // Escape HTML to prevent XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Get authorization header for API calls
    getAuthHeader() {
        const token = this.getToken();
        if (token) {
            return {
                'Authorization': `Bearer ${token}`
            };
        }
        return {};
    }
}

// Create global auth manager instance
window.authManager = new AuthManager();

//=================================================================================
// TEST MODE: Set to true to bypass authentication for local development
// WARNING: Never enable in production!
//=================================================================================
const TEST_MODE = true; // Set to false to re-enable Google authentication
//=================================================================================

// Initialize auth on page load
document.addEventListener('DOMContentLoaded', () => {
    // Skip auth check on login page
    if (window.location.pathname === '/login.html') {
        return;
    }

    // TEST MODE: Bypass authentication check
    if (TEST_MODE) {
        console.log('⚠️  TEST MODE: Authentication bypassed for local development');
        // Create a fake session for test mode
        window.authManager.session = {
            user: {
                name: 'Local Test User',
                email: 'test@localhost',
                picture: 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"%3E%3Ctext y=".9em" font-size="90"%3E👤%3C/text%3E%3C/svg%3E'
            },
            token: 'test-mode-token',
            loginTime: new Date().toISOString()
        };
        window.authManager.initUserProfile();
        console.log('✅ Test user initialized:', window.authManager.getUser().email);
        return;
    }

    // Require authentication for all other pages
    if (window.authManager.requireAuth()) {
        // Initialize user profile display
        window.authManager.initUserProfile();

        console.log('✅ User authenticated:', window.authManager.getUser().email);
    }
});
