// Theme System for Second Brain Frontend
// Based on iOS app theme implementation

class ThemeManager {
    constructor() {
        this.themes = {
            nature: {
                name: 'Nature',
                icon: '🍃',
                description: 'Calm greens and blues inspired by nature (Default)',
                
                // Primary Colors
                primaryColor: 'rgb(51, 153, 102)',        // #339966 - Green
                secondaryColor: 'rgb(102, 179, 230)',     // #66b3e6 - Sky Blue
                accentColor: 'rgb(128, 204, 77)',         // #80cc4d - Light Green
                
                // Background Colors
                backgroundColor: 'rgb(242, 250, 242)',     // #f2faf2 - Light Nature
                secondaryBackgroundColor: 'rgb(230, 242, 230)', // #e6f2e6
                
                // Text Colors
                textColor: 'rgb(26, 51, 128)',            // #1a3380 - Dark Blue
                secondaryTextColor: 'rgb(51, 77, 153)',   // #334d99 - Medium Blue
                
                // Card Colors
                cardColor: 'rgb(255, 255, 255)',          // #ffffff
                
                // UI Elements
                borderColor: 'rgb(217, 230, 217)',        // #d9e6d9
                shadowColor: 'rgba(51, 153, 102, 0.1)',
                
                // Button Colors
                buttonHover: 'rgb(41, 122, 82)',          // Darker green

                // Panel / Card Styling
                panelBackground: 'linear-gradient(135deg, rgba(102, 179, 230, 0.3) 0%, rgba(51, 153, 102, 0.32) 100%)',
                panelBorderColor: 'rgba(51, 153, 102, 0.35)',
                panelHeadingBackground: 'linear-gradient(135deg, rgba(102, 179, 230, 0.3) 0%, rgba(51, 153, 102, 0.28) 100%)',
                panelHeadingColor: 'rgb(26, 51, 128)',
                panelControlBackground: 'linear-gradient(135deg, rgba(255, 255, 255, 0.9) 0%, rgba(102, 179, 230, 0.32) 45%, rgba(51, 153, 102, 0.32) 100%)',
                panelControlHover: 'rgba(51, 153, 102, 0.28)',
                panelShadow: '0 18px 32px rgba(51, 153, 102, 0.22)',
                
                // Font
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                fontStyle: 'rounded'
            },
            
            cyberpunk: {
                name: 'Cyberpunk',
                icon: '🌃',
                description: 'Vibrant neon colors on dark background',
                
                // Primary Colors
                primaryColor: 'rgb(0, 204, 255)',         // #00ccff - Cyan
                secondaryColor: 'rgb(204, 0, 204)',       // #cc00cc - Magenta
                accentColor: 'rgb(255, 0, 128)',          // #ff0080 - Hot Pink
                
                // Background Colors
                backgroundColor: 'rgb(13, 13, 38)',        // #0d0d26 - Dark Blue
                secondaryBackgroundColor: 'rgb(26, 26, 51)', // #1a1a33
                
                // Text Colors
                textColor: 'rgb(255, 255, 255)',          // #ffffff - Pure white
                secondaryTextColor: 'rgb(217, 217, 217)', // #d9d9d9 - Light gray
                
                // Card Colors
                cardColor: 'rgb(38, 38, 71)',             // #26264a
                
                // UI Elements
                borderColor: 'rgb(51, 51, 102)',          // #333366
                shadowColor: 'rgba(0, 204, 255, 0.2)',
                
                // Button Colors
                buttonHover: 'rgb(0, 163, 204)',          // Darker cyan

                // Panel / Card Styling
                panelBackground: 'linear-gradient(135deg, rgba(0, 204, 255, 0.24) 0%, rgba(204, 0, 204, 0.24) 100%)',
                panelBorderColor: 'rgba(0, 204, 255, 0.35)',
                panelHeadingBackground: 'linear-gradient(135deg, rgba(38, 38, 71, 0.9) 0%, rgba(0, 204, 255, 0.25) 100%)',
                panelHeadingColor: 'rgb(0, 204, 255)',
                panelControlBackground: 'linear-gradient(135deg, rgba(38, 38, 71, 0.88) 0%, rgba(0, 204, 255, 0.2) 100%)',
                panelControlHover: 'rgba(0, 163, 204, 0.35)',
                panelShadow: '0 20px 45px rgba(0, 204, 255, 0.25)',
                
                // Font
                fontFamily: '"SF Mono", Monaco, "Cascadia Code", "Roboto Mono", monospace',
                fontStyle: 'monospace'
            },
            
            sakura: {
                name: 'Sakura',
                icon: '🌸',
                description: 'Soft pink tones inspired by cherry blossoms',
                
                // Primary Colors
                primaryColor: 'rgb(255, 128, 179)',       // #ff80b3 - Pink
                secondaryColor: 'rgb(255, 179, 204)',     // #ffb3cc - Light Pink
                accentColor: 'rgb(230, 77, 128)',         // #e64d80 - Deep Pink
                
                // Background Colors
                backgroundColor: 'rgb(255, 242, 247)',     // #fff2f7 - Light Pink White
                secondaryBackgroundColor: 'rgb(250, 230, 240)', // #fae6f0
                
                // Text Colors
                textColor: 'rgb(77, 26, 51)',             // #4d1a33
                secondaryTextColor: 'rgb(128, 77, 102)',  // #804d66
                
                // Card Colors
                cardColor: 'rgb(255, 255, 255)',          // #ffffff
                
                // UI Elements
                borderColor: 'rgb(255, 217, 230)',        // #ffd9e6
                shadowColor: 'rgba(255, 128, 179, 0.1)',
                
                // Button Colors
                buttonHover: 'rgb(230, 102, 153)',        // Darker pink

                // Panel / Card Styling
                panelBackground: 'linear-gradient(135deg, rgba(255, 179, 204, 0.4) 0%, rgba(255, 220, 180, 0.32) 50%, rgba(230, 77, 128, 0.3) 100%)',
                panelBorderColor: 'rgba(230, 102, 153, 0.35)',
                panelHeadingBackground: 'linear-gradient(135deg, rgba(255, 179, 204, 0.45) 0%, rgba(255, 220, 180, 0.4) 100%)',
                panelHeadingColor: 'rgb(128, 77, 102)',
                panelControlBackground: 'linear-gradient(135deg, rgba(255, 255, 255, 0.92) 0%, rgba(255, 200, 210, 0.45) 50%, rgba(255, 220, 180, 0.38) 100%)',
                panelControlHover: 'rgba(255, 179, 204, 0.55)',
                panelShadow: '0 18px 38px rgba(230, 102, 153, 0.28)',
                
                // Font
                fontFamily: 'Georgia, "Times New Roman", serif',
                fontStyle: 'serif'
            }
        };
        
        // Load saved theme or default to nature
        this.currentTheme = localStorage.getItem('selectedTheme') || 'nature';
        this.applyTheme(this.currentTheme);
    }
    
    setTheme(themeName) {
        if (!this.themes[themeName]) {
            console.error(`Theme ${themeName} not found`);
            return;
        }
        
        this.currentTheme = themeName;
        localStorage.setItem('selectedTheme', themeName);
        this.applyTheme(themeName);
        
        // Update radio buttons
        const themeRadios = document.querySelectorAll('.theme-radio');
        themeRadios.forEach(radio => {
            radio.checked = (radio.value === themeName);
        });
        
        // Trigger custom event for any listeners
        window.dispatchEvent(new CustomEvent('themeChanged', { 
            detail: { theme: themeName, colors: this.themes[themeName] }
        }));
    }
    
    applyTheme(themeName) {
        const theme = this.themes[themeName];
        if (!theme) return;
        
        const root = document.documentElement;
        
        // Apply CSS custom properties with smooth transition
        root.style.setProperty('--transition-duration', '0.3s');
        
        // Colors
        root.style.setProperty('--primary-color', theme.primaryColor);
        root.style.setProperty('--primary-hover', theme.buttonHover);
        root.style.setProperty('--secondary-color', theme.secondaryColor);
        root.style.setProperty('--accent-color', theme.accentColor);
        root.style.setProperty('--background-light', theme.backgroundColor);
        root.style.setProperty('--background-dark', theme.secondaryBackgroundColor);
        root.style.setProperty('--card-background', theme.cardColor);
        root.style.setProperty('--text-primary', theme.textColor);
        root.style.setProperty('--text-secondary', theme.secondaryTextColor);
        root.style.setProperty('--border-color', theme.borderColor);
        root.style.setProperty('--shadow-color', theme.shadowColor);
        
        // Font
        root.style.setProperty('--font-family', theme.fontFamily);

        // Panel / Card Styling
        root.style.setProperty('--panel-background', theme.panelBackground || theme.cardColor);
        root.style.setProperty('--panel-border', theme.panelBorderColor || theme.borderColor);
        root.style.setProperty('--panel-heading-background', theme.panelHeadingBackground || theme.secondaryBackgroundColor);
        root.style.setProperty('--panel-heading-color', theme.panelHeadingColor || theme.textColor);
        root.style.setProperty('--panel-control-background', theme.panelControlBackground || theme.cardColor);
        root.style.setProperty('--panel-control-hover', theme.panelControlHover || theme.buttonHover);
        root.style.setProperty('--panel-shadow', theme.panelShadow || '0 12px 28px rgba(0, 0, 0, 0.15)');
        
        // Update body gradient based on theme
        document.body.style.background = this.getBackgroundGradient(themeName);
        
        // Update theme selector active state
        this.updateThemeSelectorUI(themeName);
        
        // Add theme class to body for theme-specific styling
        document.body.className = document.body.className
            .replace(/theme-\w+/g, '')
            .trim();
        document.body.classList.add(`theme-${themeName}`);
    }
    
    getBackgroundGradient(themeName) {
        const gradients = {
            nature: 'linear-gradient(135deg, rgb(242, 250, 242) 0%, rgb(224, 231, 255) 100%)',
            cyberpunk: 'linear-gradient(135deg, rgb(13, 13, 38) 0%, rgb(30, 27, 75) 100%)',
            sakura: 'linear-gradient(135deg, rgb(255, 242, 247) 0%, rgb(255, 235, 245) 100%)'
        };
        return gradients[themeName] || gradients.nature;
    }
    
    updateThemeSelectorUI(themeName) {
        document.querySelectorAll('.theme-btn-inline').forEach(btn => {
            if (btn.dataset.theme === themeName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
    
    getCurrentTheme() {
        return this.themes[this.currentTheme];
    }
    
    getAllThemes() {
        return Object.entries(this.themes).map(([key, theme]) => ({
            id: key,
            name: theme.name,
            icon: theme.icon,
            description: theme.description
        }));
    }
}

// Initialize theme manager
const themeManager = new ThemeManager();

// Make it globally available
window.themeManager = themeManager;

// Export for module systems if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ThemeManager;
}
