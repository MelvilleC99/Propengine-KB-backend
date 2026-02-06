# Deployment Checklist - Debug Metrics Fixes

**Date:** February 1, 2026
**Commit:** 3191c44
**Branch:** main

---

## Changes Deployed

### Bug Fixes ✅
1. **Context-based responses now track response_generation_time_ms**
   - Fixed: context_responder.py

2. **Fallback responses now track timing and tokens**
   - Fixed: orchestrator.py, response_generator.py

3. **Query intelligence optimized (single LLM call)**
   - New: query_intelligence.py
   - Updated: Metrics field names

---

## Pre-Deployment Checklist

- [ ] **Environment Variables**
  - [ ] OPENAI_API_KEY set
  - [ ] OPENAI_BASE_URL set
  - [ ] OPENAI_MODEL = gpt-4o-mini
  - [ ] ASTRA_DB credentials configured
  - [ ] REDIS_URL configured

- [ ] **Dependencies**
  ```bash
  # Verify all packages installed
  pip install -r requirements.txt
  ```

- [ ] **Database Connections**
  - [ ] Redis connection working
  - [ ] AstraDB connection working
  - [ ] Test query returns results

- [ ] **Backend Health Check**
  ```bash
  # Test the API is running
  curl http://localhost:8000/health

  # Should return: {"status": "healthy"}
  ```

---

## Deployment Steps

### 1. Stop Current Service
```bash
# If using systemd
sudo systemctl stop propengine-backend

# If using Docker
docker-compose down

# If running manually
pkill -f "uvicorn src.main:app"
```

### 2. Pull Latest Code
```bash
cd /Users/melville/Documents/Propengine-KB-backend
git pull origin main

# Verify commit
git log --oneline -1
# Should show: 3191c44 FIX: Complete debug metrics timing and token tracking
```

### 3. Clear Python Cache
```bash
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
```

### 4. Restart Service
```bash
# If using systemd
sudo systemctl start propengine-backend
sudo systemctl status propengine-backend

# If using Docker
docker-compose up -d

# If running manually
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Verify Service Started
```bash
# Check if running
curl http://localhost:8000/health

# Check logs
tail -f logs/app.log

# Or if using systemd
sudo journalctl -u propengine-backend -f
```

---

## Post-Deployment Verification

### Test 1: Simple Query
```bash
curl -X POST http://localhost:8000/api/agent/test \
  -H "Content-Type: application/json" \
  -d '{
    "message": "how do I upload photos",
    "session_id": "deploy_test_1"
  }'
```

**Expected:**
- Response contains `debug_metrics`
- `query_intelligence_time_ms` is present (not 0)
- `response_generation_time_ms` is present (not 0)
- `total_time_ms` is reasonable (<10s)

### Test 2: Check Debug Metrics Structure
```bash
# Run test script
cd /Users/melville/Documents/Propengine-KB-backend/claude_code
python3 test_debug_metrics.py
```

**Expected output:**
```
✅ query_intelligence_time_ms present: ~2000ms
✅ Response generation time present: ~1500ms
⚠️  Total time: ~6000ms (acceptable)
```

### Test 3: Check Frontend Integration
- [ ] Frontend displays query_intelligence_time_ms
- [ ] Frontend displays all timing fields
- [ ] No missing metrics
- [ ] Cost breakdown shows correctly

---

## Rollback Plan (If Issues)

If deployment has issues:

```bash
# 1. Stop service
sudo systemctl stop propengine-backend

# 2. Revert to previous commit
git revert 3191c44

# 3. Clear cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# 4. Restart service
sudo systemctl start propengine-backend

# 5. Verify rollback
git log --oneline -1
```

---

## Known Issues Post-Deployment

### Issue 1: Frontend Missing query_intelligence_time_ms Display
**Status:** Expected - Frontend update needed
**Action:** Update frontend to add this field to debug UI

### Issue 2: Query Performance (~6-7 seconds)
**Status:** Known - Within acceptable range but can be improved
**Action:** Audit scheduled post-deployment

---

## Monitoring After Deployment

### Metrics to Watch (First Hour)

1. **Average Query Time**
   - Target: <8 seconds
   - Alert if: >10 seconds

2. **Error Rate**
   - Target: <1%
   - Alert if: >5%

3. **Debug Metrics Completeness**
   - Check: All timing fields populated
   - Alert if: Any fields showing 0 unexpectedly

4. **Memory Usage**
   - Check: No memory leaks
   - Alert if: Steadily increasing

### Log Monitoring
```bash
# Watch for errors
tail -f logs/app.log | grep ERROR

# Watch for timing logs
tail -f logs/app.log | grep "TIMING BREAKDOWN"
```

---

## Success Criteria ✅

Deployment is successful if:
- ✅ Service starts without errors
- ✅ Health check returns 200 OK
- ✅ Test queries return responses
- ✅ Debug metrics are complete (no 0s for major operations)
- ✅ No increase in error rate
- ✅ Query times within acceptable range (<10s)

---

## Next Steps After Deployment

1. **Monitor for 1 hour**
   - Watch logs
   - Check error rates
   - Verify query times

2. **Update Frontend**
   - Add `query_intelligence_time_ms` to debug display
   - Test with real queries

3. **Performance Audit**
   - Run audit scripts (in claude_code/)
   - Identify system overhead bottleneck
   - Create optimization plan

4. **User Acceptance Testing**
   - Have team test queries
   - Verify debug metrics show correctly
   - Collect feedback

---

## Contact

If issues occur during deployment:
- Check logs first
- Review this checklist
- Roll back if critical
- Document issues for audit

**Ready to deploy!** 🚀
