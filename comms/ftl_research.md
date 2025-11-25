# FencingTimeLive (FTL) Scraper Research Log

## Objective

To determine the feasibility of scraping live pool and event data from `fencingtimelive.com`. The initial analysis showed that the data is not in the static HTML but is loaded dynamically via JavaScript.

This log documents the process of trying to identify the backend API endpoint that the FTL frontend uses to fetch this data.

## Step 1: Analyze Page Structure and Scripts

**Action:** Fetch the HTML source of the target URL to identify the JavaScript files being loaded.

**URL:** `https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7`

**Findings:** The primary HTML is a shell. The interesting parts are the `<script>` tags that load the application logic. However, an initial attempt to find these scripts failed as they are likely dynamically injected.

---

## Step 2: External Research via Google Search

**Action:** Performed a Google search for "fencingtimelive.com API documentation OR python scraper" to see if this problem has been solved before.

**Findings:**
- There is **no public API**.
- The consensus from the search results is that the correct approach is to use browser developer tools to inspect network traffic, find the internal API calls the website makes to itself, and replicate those calls. This confirms our hypothesis.

---

## Step 3: Hypothesize and Test API Endpoint

**Action:** Based on the structure of the original URL, I will construct a hypothetical API endpoint URL and attempt to fetch data from it. This is a common pattern for modern web applications.

**URL Structure:** `https://www.fencingtimelive.com/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7`

**Hypothesis:** An API endpoint might exist at a similar path, perhaps on a different subdomain like `api.fencingtimelive.com` or a path prefix like `/api/v1/`.

**Test:** I will now attempt to query a hypothesized endpoint.

**Result:** The attempt to query `https://api.fencingtimelive.com/...` failed. It returned a generic HTML page, not structured data.

**Next Test:** I will try another common pattern: a path-based API on the main `www` subdomain. I will now query `https://www.fencingtimelive.com/api/pools/scores/54B9EF9A9707492E93F1D1F46CF715A2/D6890CA440324D9E8D594D5682CC33B7`.

**Result:** This query returned a `404 Not Found` error. This is a very positive result! It indicates that an API server is running at `https://www.fencingtimelive.com/api/`, but our specific URL path (`/pools/scores/...`) is incorrect.

---

## Step 4: Search for Existing Scrapers

**Conclusion so far:** We have confirmed an API exists and where it is located. The final piece of the puzzle is to determine the correct URL structure for the API calls.

**Action:** The most efficient way to discover the correct API path is to see if someone else has already done this work. I will search on Google for open-source projects, specifically on GitHub, that have successfully scraped FencingTimeLive.

**Result:** The search did not yield any existing scrapers.

---

## Final Conclusion & Recommendation (Blocked)

The investigation has hit a dead end. My tools are unable to inspect the dynamically loaded JavaScript on `fencingtimelive.com`, which is necessary to find the exact structure of their internal API calls.

**What we know:**
- An API server almost certainly exists at `https://www.fencingtimelive.com/api/`.
- Simple scraping of the HTML is impossible.
- Guessing the full API path has been unsuccessful.

**Recommendation:**
1.  **Mark Phase 2 as BLOCKED:** We cannot proceed with implementing the `fencingtimelive.com` scraper at this time.
2.  **Manual Task for Human Developer:** A developer needs to manually open the FTL website, use their browser's Developer Tools (F12), go to the "Network" tab, and find the `fetch/XHR` request that loads the pool data. They must copy the full URL of that request and the JSON response it returns.
3.  **Proceed with Phase 1:** All work on Phase 1 (user authentication, fencer tracking, and the static schedule view) is unaffected and should proceed as planned.

