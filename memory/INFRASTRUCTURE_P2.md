# BidVex Performance — Infrastructure Recommendations (P2)

## 1. Cloudflare CDN Setup for bidvex.com

### Step-by-Step:
1. **Create Cloudflare account** at https://dash.cloudflare.com/sign-up (free tier)
2. **Add site**: Enter `bidvex.com` → Cloudflare scans existing DNS records
3. **Update nameservers**: Change your domain registrar's nameservers to the pair Cloudflare provides (e.g., `adam.ns.cloudflare.com`, `betty.ns.cloudflare.com`)
4. **Verify propagation**: Wait 24-48h, check status in Cloudflare dashboard
5. **Configure SSL**: Dashboard → SSL/TLS → Set to "Full (strict)"
6. **Enable caching**:
   - Page Rules: `bidvex.com/static/*` → Cache Level: Cache Everything, Edge TTL: 1 month
   - Page Rules: `bidvex.com/api/*` → Cache Level: Bypass (dynamic content)
7. **Enable compression**: Speed → Optimization → Enable Brotli
8. **Enable HTTP/3**: Network → Enable HTTP/3 (QUIC)
9. **Enable Auto Minify**: Speed → Optimization → Enable JS/CSS/HTML minification
10. **Enable Rocket Loader**: Speed → Optimization → Enable (defers JS loading)

### Expected Impact:
- 40-60% latency reduction for Canadian users (Toronto, Montreal, Vancouver edge nodes)
- Automatic DDoS protection
- Free SSL certificate management

---

## 2. React Query Migration Plan

### Estimated Effort: 2-3 days

### Installation:
```bash
yarn add @tanstack/react-query @tanstack/react-query-devtools
```

### Architecture:
```
src/
├── providers/
│   └── QueryProvider.js     # Wrap app with QueryClientProvider
├── hooks/
│   ├── useListings.js       # useQuery for listings
│   ├── useCategories.js     # useQuery with 5min staleTime
│   ├── useMarketplace.js    # useInfiniteQuery for pagination
│   └── useBids.js           # useMutation for placing bids
```

### Migration Steps:
1. Install and wrap App with `QueryClientProvider` (30 min)
2. Create `useCategories` hook — replace all `fetchCategories` calls (1 hour)
3. Create `useListings` hook — replace marketplace data fetching (2 hours)
4. Create `useInfiniteQuery` for infinite scroll on marketplace (2 hours)
5. Create bid mutations with optimistic updates (2 hours)
6. Add `prefetchQuery` on link hover for anticipated navigation (1 hour)
7. Remove all manual `useState` + `useEffect` data fetching patterns (2 hours)

### Key Configuration:
```js
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,      // 30s before refetch
      gcTime: 5 * 60 * 1000,     // 5min garbage collection
      refetchOnWindowFocus: true,
      retry: 2,
    },
  },
});
```

---

## 3. Cursor Pagination Spec for /api/listings

### Current State:
- Uses `skip` + `limit` offset pagination (O(n) for deep pages)

### Proposed: Cursor-based Pagination

#### API Contract:
```
GET /api/marketplace/search?limit=20&cursor={last_item_cursor}&sort=created_at&direction=desc
```

#### Response:
```json
{
  "items": [...],
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wMy0yMFQxMjowMDowMFoiLCJpZCI6ImFiYzEyMyJ9",
  "has_more": true,
  "total_count": 1234
}
```

#### Backend Implementation:
```python
@router.get("/marketplace/search")
async def search_listings(
    limit: int = Query(20, le=50),
    cursor: str = Query(None),
    sort: str = Query("created_at"),
    direction: str = Query("desc"),
):
    query = {"status": "active"}
    
    if cursor:
        decoded = json.loads(base64.b64decode(cursor))
        sort_field = decoded["sort_field"]
        sort_value = decoded["sort_value"]
        item_id = decoded["id"]
        
        if direction == "desc":
            query["$or"] = [
                {sort: {"$lt": sort_value}},
                {sort: sort_value, "id": {"$lt": item_id}}
            ]
        else:
            query["$or"] = [
                {sort: {"$gt": sort_value}},
                {sort: sort_value, "id": {"$gt": item_id}}
            ]
    
    sort_dir = -1 if direction == "desc" else 1
    items = await db.listings.find(query, {"_id": 0}) \
        .sort([(sort, sort_dir), ("id", sort_dir)]) \
        .limit(limit + 1) \
        .to_list(limit + 1)
    
    has_more = len(items) > limit
    items = items[:limit]
    
    next_cursor = None
    if has_more and items:
        last = items[-1]
        cursor_data = {"sort_field": sort, "sort_value": last[sort], "id": last["id"]}
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()
    
    return {"items": items, "next_cursor": next_cursor, "has_more": has_more}
```

#### Frontend Integration with React Query:
```js
const { data, fetchNextPage, hasNextPage } = useInfiniteQuery({
  queryKey: ['marketplace', filters],
  queryFn: ({ pageParam }) => fetchListings({ ...filters, cursor: pageParam }),
  getNextPageParam: (lastPage) => lastPage.has_more ? lastPage.next_cursor : undefined,
});
```

### Estimated Effort: 1-2 days
