// Use environment variable for API URL, fallback to production URL
const API_BASE = process.env.REACT_APP_BACKEND_URL 
  ? `${process.env.REACT_APP_BACKEND_URL}/api`
  : "https://bidvexcom-production.up.railway.app/api";
export default API_BASE;
