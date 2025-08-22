# 📁 Repository Structure

This project has been split into separate repositories for better deployment and management:

## 🖥️ **Backend Repository** (This Repo)
**Location**: Current repository  
**Purpose**: Python Flask API, research agents, backend logic  
**Deployment**: Heroku (with ZDR configuration)

### Contains:
- ✅ Flask API (`backend/brilliance/api/`)
- ✅ Research agents and workflows
- ✅ Database tools (ArXiv, PubMed, OpenAlex)
- ✅ Celery background tasks
- ✅ Zero Downtime Restart configuration
- ✅ Health monitoring endpoints

### Deployment:
```bash
git push heroku main
```

## 🎨 **Frontend Repository** (Separate)
**Location**: [`https://github.com/ECLLC42/brilliance_frontend`](https://github.com/ECLLC42/brilliance_frontend)  
**Purpose**: React application, user interface  
**Deployment**: Vercel/Netlify

### Contains:
- ✅ React frontend with updated defaults (10 papers, GPT-5)
- ✅ User interface components
- ✅ Auto-migration for user preferences
- ✅ Production build configuration

### Deployment:
```bash
# In the frontend repository
git push origin main
# Then deploy via Vercel/Netlify dashboard
```

## 🔗 **How They Work Together**

```
Frontend (Vercel/Netlify) 
    ↓ API calls
Backend (Heroku)
    ↓ External APIs  
ArXiv, PubMed, OpenAlex
```

### Environment Variables:
- **Backend**: Set API keys, CORS origins
- **Frontend**: Set `REACT_APP_API_URL=https://your-backend.herokuapp.com`

## 🚀 **Development Workflow**

### Backend Changes:
1. Make changes in this repository
2. Test locally: `flask run`
3. Deploy: `git push heroku main`

### Frontend Changes:
1. Clone frontend repo: `git clone https://github.com/ECLLC42/brilliance_frontend`
2. Make changes
3. Test locally: `npm start`
4. Push: `git push origin main`
5. Deploy via Vercel/Netlify

## 📊 **Current Status**

✅ **Backend**: ZDR enabled, health monitoring, log security  
✅ **Frontend**: 10 papers default, user migration, separate deployment  
✅ **Integration**: CORS configured, API communication working  

Both repositories are production-ready! 🎉
