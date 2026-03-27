# BidVex Test Credentials

## Admin Account
- Email: `charbeladmin@bidvex.com`
- Password: `Admin123!`
- Role: admin

## Real User Account
- Email: `charbel911@gmail.com`
- Role: user (no test password available - uses production password)

## Auth Route
- Login page: `/auth`
- Login API: `POST /api/auth/login` with `{"email":"...","password":"..."}`
- Returns: `access_token` (JWT Bearer token)

## Site Mode
- API: `GET /api/site-mode` (public)
- Admin toggle: `PUT /api/admin/site-mode` with `{"mode":"live"|"coming_soon"|"maintenance"}`
