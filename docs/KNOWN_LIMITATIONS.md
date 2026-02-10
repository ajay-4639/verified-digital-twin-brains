# Known Limitations & Constraints

**Document Version:** 1.0.0  
**Last Updated:** 2026-02-09  

---

## X (Twitter) / Twitter Ingestion

### Status: ⚠️ UNRELIABLE

X/Twitter ingestion is **not guaranteed to work** due to active anti-scraping measures implemented by X. This is a known limitation affecting all third-party tools.

### Why It Fails

1. **Rate Limiting**: X aggressively rate-limits non-authenticated requests
2. **Bot Detection**: Automated requests are detected and blocked
3. **Authentication Walls**: Many tweets now require login to view
4. **IP Reputation**: Cloud/server IPs are often blacklisted

### Fallback Strategies (Implemented)

The system implements 4 fallback strategies (in order):

1. **Syndication API** (`cdn.syndication.twimg.com`)
   - Official embed API
   - Often blocked for new tweets
   - Works for older content

2. **Nitter Instances** (Public Twitter readers)
   - `nitter.privacydev.net`
   - `nitter.poast.org`
   - `nitter.1d4.us`
   - Often rate-limited or offline

3. **FxTwitter API** (`api.fxtwitter.com`)
   - Third-party embed service
   - Blocked by X's CORS policies

4. **VxTwitter API** (`api.vxtwitter.com`)
   - Alternative embed service
   - Similar limitations

### User Workaround

If X ingestion fails, users can:

1. **Copy tweet text manually** and upload as a text file
2. **Screenshot the tweet** and upload as image (limited text extraction)
3. **Use X's official API** (requires developer account and separate integration)

### Error Message

When X ingestion fails, users see:

> "Could not extract X thread content. X/Twitter may be blocking requests from this server. Try copying the tweet text manually and uploading it as a text file."

### Technical Details

```python
# Error Code: X_BLOCKED_OR_UNSUPPORTED
# File: backend/modules/ingestion.py:1052-1075
```

### Future Considerations

- **X API v2**: Would require paid API access ($100+/month basic tier)
- **Browser Automation**: Would violate X ToS and be unreliable
- **User-Provided Cookies**: Security risk, not recommended

---

## LinkedIn Ingestion

### Status: ⚠️ LIMITED

LinkedIn only allows public OpenGraph metadata extraction. Full profile content requires:
- LinkedIn partnership agreement
- Compliance with LinkedIn ToS
- User consent and data export

### What Works
- Public profile metadata (name, headline, summary)
- OpenGraph tags

### What Doesn't Work
- Full profile content
- Connections/Network data
- Private profiles
- Login-walled content

### User Workaround

Users should export their LinkedIn profile as PDF and upload that.

---

## YouTube Ingestion

### Status: ✅ MOSTLY RELIABLE

YouTube ingestion has multiple fallback strategies and is generally reliable, but may fail for:

### Failure Cases

1. **Age-Restricted Videos**: Require authentication
2. **Private/Deleted Videos**: No access
3. **Live Streams**: Only processable after stream ends
4. **Region-Blocked**: Geographic restrictions

### Fallback Strategies

1. **YouTube Transcript API** (fastest)
   - Free, no API key needed
   - May be blocked for some videos

2. **Direct HTTP Fetch**
   - Extracts captions from page
   - Bypasses some API blocks

3. **yt-dlp Download + Transcription** (slowest)
   - Downloads audio
   - Transcribes with Whisper
   - 30-60 seconds per video

### Configuration Options

```bash
# Optional: Use cookies for age-restricted videos
YOUTUBE_COOKIES_FILE=/path/to/cookies.txt

# Optional: Use proxy for IP reputation
YOUTUBE_PROXY=http://proxy:8080
```

---

## File Upload Constraints

### Supported Formats
- PDF (text-based, not scanned images)
- DOCX (Microsoft Word)
- XLSX (Microsoft Excel)
- TXT (Plain text)

### Limitations

1. **Scanned PDFs**: Text extraction fails if PDF is image-only
   - Error: `FILE_EXTRACTION_EMPTY`
   - Solution: Use OCR software first

2. **Large Files**: Processing time increases linearly
   - 10MB file ≈ 2-3 minutes
   - 50MB file ≈ 10-15 minutes

3. **Encoding Issues**: Non-UTF8 files may have garbled text

---

## Rate Limits & Quotas

### OpenAI (Embeddings)
- Rate: 3,000 RPM (requests per minute) for paid accounts
- Current usage: ~1-2 requests per chunk
- Limit: Typically not hit unless bulk importing

### Pinecone
- Free tier: 100,000 vectors
- Paid: Scales with plan
- Upsert: 100 vectors per request (batched)

### Supabase
- Free tier: 500MB database, 2GB storage
- Connection limit: 60 concurrent

---

## Multi-Tenant Isolation

### Verified
- ✅ Pinecone namespace = twin_id
- ✅ All queries filtered by twin_id
- ✅ RLS policies on Supabase tables

### Edge Cases
- **Shared Sources**: Not supported (each twin has own copy)
- **Cross-Twin Search**: Not supported by design

---

## Job Processing

### Worker Capacity
- Single worker processes 1 job at a time
- No horizontal scaling without Redis
- DB polling fallback: 1-5 second latency

### Retry Behavior
- Max retries: 3 attempts
- Backoff: 30s, 60s, 120s (with jitter)
- Non-retryable errors: See `should_retry_job()` in training_jobs.py

### Dead Letter Queue
- Jobs exceeding max retries go to DLQ
- Manual replay possible via API
- No automatic DLQ cleanup (manual management required)

---

## Streaming Response Limits

### Chat Streaming
- Timeout: 60 seconds idle
- Max message size: None (streaming)
- Connection: Keep-alive with ping packets

### Browser Compatibility
- Requires EventSource or fetch with ReadableStream
- IE11: Not supported
- Safari: Supported (iOS 14+)

---

## Known Bugs (Unfixed)

| Bug | Impact | Workaround |
|-----|--------|------------|
| X ingestion unreliable | High | Manual text upload |
| Large PDFs timeout | Medium | Split into smaller files |
| Worker memory growth | Low | Restart worker periodically |

---

## Support Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| YouTube ingestion | ✅ Stable | Multiple fallbacks |
| File upload (PDF/DOCX) | ✅ Stable | SHA-256 dedup |
| X ingestion | ⚠️ Unreliable | Anti-scraping blocks |
| LinkedIn ingestion | ⚠️ Limited | Public metadata only |
| Podcast RSS | ✅ Stable | Audio transcription |
| Generic web URLs | ✅ Stable | Basic text extraction |

---

*Last reviewed: 2026-02-09*
