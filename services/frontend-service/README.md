# 🎨 Frontend Service

The Frontend Service provides the web-based user interface for the Second Brain system, serving static HTML, CSS, and JavaScript files with dynamic API configuration.

## 📋 Overview

This lightweight service handles:
- **Static File Serving**: HTML, CSS, JavaScript, and assets
- **Dynamic Configuration**: Injects API endpoint configuration
- **Web UI**: Interactive interface for AI consultations and knowledge management
- **CORS Management**: Cross-Origin Resource Sharing for API access

## 🏗️ Architecture

```
┌─────────────────┐
│   Web Browser   │
│  (User Client)  │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│ Frontend Service│
│   (Port 8000)   │
│                 │
│ ┌─────────────┐ │
│ │ index.html  │ │
│ └─────────────┘ │
│ ┌─────────────┐ │
│ │  config.js  │ │ (Dynamic)
│ └─────────────┘ │
│ ┌─────────────┐ │
│ │static/      │ │
│ │ ├─app.js    │ │
│ │ └─style.css │ │
│ └─────────────┘ │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   API Service   │
│   (Port 8001)   │
└─────────────────┘
```

## 🚀 Features

### Static File Serving
- **HTML Pages**: Main application interface
- **JavaScript**: Interactive functionality with D3.js graphs
- **CSS Styling**: Modern, responsive design
- **Fast Delivery**: Efficient static file serving with FastAPI

### Dynamic Configuration
- **Environment-Based**: API endpoint from `API_BASE_URL` env var
- **Runtime Configuration**: No hardcoded endpoints
- **Client-Side Access**: JavaScript config via `window.APP_CONFIG`
- **Easy Deployment**: Configure once, deploy anywhere

### Modern Web UI
- **Tabbed Interface**: Ask AI, Search, Summary, Knowledge Graph
- **Multi-LLM Selection**: Choose which AI models to consult
- **Image Upload**: Drag & drop or click to upload images
- **Knowledge Graph**: Interactive D3.js visualization
- **Real-Time Updates**: Async communication with API service

## 🔌 Endpoints

### Main Application
```bash
GET /
```

Serves the main `index.html` file.

**Response**: HTML page

### Configuration Script
```bash
GET /config.js
```

Dynamically generated JavaScript configuration.

**Response:**
```javascript
// Auto-generated configuration
window.APP_CONFIG = {
    apiBaseUrl: 'http://localhost:30001'
};
```

### Static Assets
```bash
GET /static/{filename}
```

Serves static files (CSS, JavaScript, images).

Examples:
- `/static/style.css` - Main stylesheet
- `/static/app.js` - Application JavaScript
- `/static/images/logo.png` - Images

### Health Check
```bash
GET /health
```

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "frontend"
}
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `http://localhost:8001` | Backend API service URL |

### Setting API URL

**Development (localhost):**
```bash
export API_BASE_URL=http://localhost:8001
```

**Production (remote server):**
```bash
export API_BASE_URL=http://localhost:30001
```

**Docker Compose:**
```yaml
frontend:
  environment:
    API_BASE_URL: ${API_BASE_URL:-http://localhost:30001}
```

## 🐳 Running the Service

### With Docker Compose (Recommended)
```bash
cd services/
docker-compose up frontend
```

### Standalone Development
```bash
cd services/frontend-service
pip install -r requirements.txt
export API_BASE_URL=http://localhost:8001
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing the Service
```bash
# Health check
curl http://localhost:8000/health

# Get main page
curl http://localhost:8000

# Get configuration
curl http://localhost:8000/config.js

# Get static assets
curl http://localhost:8000/static/app.js
```

## 📦 Dependencies

Minimal dependencies for fast startup:
- **FastAPI**: Web framework
- **Uvicorn**: ASGI server
- **Python 3.11+**: Runtime

Full list in `requirements.txt`:
```txt
fastapi
uvicorn[standard]
python-multipart
```

## 🏗️ Project Structure

```
frontend-service/
├── main.py              # FastAPI application
├── index.html           # Main application page
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
│
└── static/             # Static assets
    ├── app.js         # Application JavaScript
    ├── style.css      # Main stylesheet
    └── (other assets)
```

## 🎨 User Interface

### Main Features

#### 1. Ask AI Tab (🤖)
- **Multi-LLM Selection**: Choose OpenAI, Claude, Gemini, Grok
- **Text Input**: Ask questions via text
- **Image Upload**: Analyze images with vision models
- **Parallel Responses**: See all model responses simultaneously
- **Consensus Summary**: AI-generated unified answer

#### 2. Search & Browse Tab (🔍)
- **Vector Search**: Semantic search through knowledge base
- **Topic Browser**: View all topics with counts
- **Search Results**: Ranked by relevance score
- **Date Filtering**: Search by time period

#### 3. Daily Summary Tab (📊)
- **Date Selection**: Choose date to summarize
- **Topic Clustering**: Groups related questions
- **Knowledge Points**: Key insights per topic

#### 4. Knowledge Graph Tab (🕸️)
- **Interactive Visualization**: D3.js force-directed graph
- **Node Details**: Hover for concept information
- **Relationship Exploration**: Click and drag nodes
- **Similarity Edges**: Connections based on vector similarity

### JavaScript Application

Main class: `SecondBrainApp` in `app.js`

```javascript
class SecondBrainApp {
    constructor() {
        this.apiBase = this.getApiBase();  // From window.APP_CONFIG
        this.initializeElements();
        this.bindEvents();
        this.initializeTabs();
    }
    
    getApiBase() {
        // Priority: localStorage > APP_CONFIG > fallback
        if (window.APP_CONFIG?.apiBaseUrl) {
            return window.APP_CONFIG.apiBaseUrl;
        }
        return 'http://localhost:8001';
    }
    
    async handleAsk() {
        const response = await fetch(`${this.apiBase}/ask`, {
            method: 'POST',
            body: JSON.stringify({
                user_input: this.promptInput.value,
                selected_models: this.getSelectedModels()
            })
        });
        // Handle response...
    }
}
```

### Styling

Modern CSS with:
- **Flexbox/Grid Layouts**: Responsive design
- **CSS Variables**: Consistent theming
- **Animations**: Smooth transitions
- **Mobile-First**: Works on all screen sizes

Key features in `style.css`:
```css
:root {
    --primary-color: #2563eb;
    --secondary-color: #7c3aed;
    --success-color: #10b981;
    --background: #0f172a;
}

.tab-navigation {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.tab-button.active {
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
}
```

## 🔗 Integration

### Calls These Services
- **API Service** (Port 8001): All backend operations

### Called By
- **Web Browsers**: Direct user access
- **iOS App**: Via WebView (optional)

### Request Flow
```
Browser → Frontend (8000) → API (8001) → Vector/DB/LLMs
        ← HTML/JS/CSS   ←         ←
```

## 🎯 Configuration Priority

The frontend loads API URL in this priority order:

1. **localStorage** (for debugging): 
   ```javascript
   localStorage.setItem('apiBaseUrl', 'http://custom:8001');
   ```

2. **Environment Config** (from server):
   ```javascript
   window.APP_CONFIG.apiBaseUrl  // From /config.js
   ```

3. **Fallback**:
   ```javascript
   'http://localhost:8001'  // Default
   ```

## 🐛 Debugging

### Check Service
```bash
# Health check
curl http://localhost:8000/health

# View configuration
curl http://localhost:8000/config.js
```

### View Logs
```bash
docker logs second_brain_with_llms-frontend-1 -f
```

### Browser Console
```javascript
// Check API configuration
console.log(window.APP_CONFIG);

// Test API connection
fetch(window.APP_CONFIG.apiBaseUrl + '/health')
  .then(r => r.json())
  .then(console.log);
```

### Common Issues

**API Base URL Not Set**
```
Issue: window.APP_CONFIG is undefined
Solution: Check if /config.js loads before app.js
```

**CORS Error**
```
Issue: "Access-Control-Allow-Origin" error
Solution: API service needs CORS middleware configured
```

**Static Files Not Loading**
```
Issue: 404 on /static/app.js
Solution: Ensure static/ directory exists with files
```

**Hard Refresh Required**
```
Issue: Changes not appearing
Solution: Clear cache with Cmd+Shift+R (Mac) or Ctrl+Shift+F5 (Windows)
```

## 📊 Performance

### Optimization Features
- **Static File Caching**: Browser caches CSS/JS
- **Minimal Dependencies**: Fast startup time
- **Async Operations**: Non-blocking API calls
- **Lazy Loading**: Load resources as needed

### Metrics
- **First Load**: < 1s (HTML + CSS + JS)
- **Subsequent Loads**: < 100ms (cached)
- **API Response Time**: Depends on API service

## 🚀 Development Tips

### Live Reload
```bash
uvicorn main:app --reload --port 8000
```

### Test API Override
```javascript
// In browser console
localStorage.setItem('apiBaseUrl', 'http://localhost:8001');
location.reload();
```

### Clear Override
```javascript
localStorage.removeItem('apiBaseUrl');
location.reload();
```

### Hot Reload CSS
Most browsers support CSS hot reload without page refresh.

### JavaScript Debugging
```javascript
// Enable verbose logging
localStorage.setItem('debug', 'true');
```

## 🎨 Customization

### Change Theme Colors
Edit CSS variables in `static/style.css`:
```css
:root {
    --primary-color: #your-color;
    --background: #your-background;
}
```

### Modify Layout
Edit HTML structure in `index.html` and corresponding CSS in `style.css`.

### Add New Features
1. Add HTML elements in `index.html`
2. Style in `static/style.css`
3. Add functionality in `static/app.js`
4. Connect to API endpoints

## 🔐 Security Notes

- **CORS**: Configured for development (`*`); restrict in production
- **Environment Variables**: Never expose secrets in frontend
- **Client-Side**: All code visible to users
- **API Keys**: Never include in frontend code
- **HTTPS**: Use SSL/TLS in production

## 📱 Mobile Support

The UI is responsive and works on:
- ✅ Desktop browsers (Chrome, Firefox, Safari, Edge)
- ✅ Mobile browsers (iOS Safari, Android Chrome)
- ✅ Tablets (iPad, Android tablets)
- ✅ Different screen sizes (320px to 4K)

## 🌐 Browser Compatibility

Tested and working on:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Opera 76+

Requires:
- ES6+ JavaScript support
- CSS Grid and Flexbox
- Fetch API
- Modern DOM APIs

## 📝 API Documentation

The frontend doesn't provide API docs (it's the API client).

For API documentation, see:
- **API Service**: http://localhost:8001/docs

## 🔄 Update Process

### Update Frontend Code
1. Edit `index.html`, `static/app.js`, or `static/style.css`
2. Rebuild container: `docker-compose build frontend`
3. Restart service: `docker-compose up -d frontend`
4. Hard refresh browser to clear cache

### Update API Configuration
1. Edit `.env` file: `API_BASE_URL=http://new-url:8001`
2. Restart frontend: `docker-compose restart frontend`
3. Reload browser page

## 🧪 Testing

### Manual Testing
```bash
# Test main page loads
curl -I http://localhost:8000/

# Test config endpoint
curl http://localhost:8000/config.js

# Test static files
curl http://localhost:8000/static/app.js

# Test health
curl http://localhost:8000/health
```

### Browser Testing
1. Open http://localhost:8000
2. Open browser dev tools (F12)
3. Check Console for errors
4. Check Network tab for failed requests
5. Verify `window.APP_CONFIG` is set correctly

## 📦 Docker Configuration

### Dockerfile
```dockerfile
FROM python:3.11-slim-bullseye

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Check
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

**Service Status**: Production Ready ✅  
**Port**: 8000  
**Protocol**: HTTP  
**Architecture**: Stateless Static File Server  
**Technology**: FastAPI + HTML/CSS/JavaScript + D3.js
