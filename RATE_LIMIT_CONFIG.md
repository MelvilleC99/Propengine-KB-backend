# Rate Limiting Configuration

## 📁 Location
**`/src/config/rate_limits.py`**

All rate limiting settings are centralized in this single configuration file.

---

## ⚙️ Quick Start - How to Change Limits

### **Option 1: Modify Values Directly**

Open `/src/config/rate_limits.py` and edit the `RATE_LIMITS` dictionary:

```python
RATE_LIMITS = {
    "query": {
        "requests": 200,      # ← Change from 100 to 200
        "window": 86400       # Keep 24 hours
    },
}
```

### **Option 2: Switch to Pre-defined Profiles**

Change the `ACTIVE_LIMITS` assignment:

```python
# For development/testing (no limits)
ACTIVE_LIMITS = DEV_LIMITS

# For high volume internal use
ACTIVE_LIMITS = HIGH_VOLUME_LIMITS

# For strict external user limits
ACTIVE_LIMITS = STRICT_LIMITS

# For standard production (default)
ACTIVE_LIMITS = RATE_LIMITS
```

---

## 📊 Current Limits (Production)

| Endpoint | Limit | Window | What It Limits |
|----------|-------|--------|----------------|
| `query` | 100 | 24 hours | Agent queries (all 3 agents) |
| `feedback` | 50 | 24 hours | Thumbs up/down submissions |
| `ticket` | 10 | 24 hours | Failure reports & tickets |
| `default` | 100 | 5 minutes | Any unconfigured endpoint |

---

## 🎯 Pre-defined Profiles

### **DEV_LIMITS** (Testing)
```python
"query": 10,000/day
"feedback": 10,000/day
"ticket": 10,000/day
```

### **HIGH_VOLUME_LIMITS** (Internal)
```python
"query": 1,000/day
"feedback": 500/day
"ticket": 100/day
```

### **STRICT_LIMITS** (External)
```python
"query": 50/day
"feedback": 20/day
"ticket": 5/day
```

---

## 🔧 Making Changes

### **To change a single limit:**
```python
RATE_LIMITS["query"]["requests"] = 500
```

### **To change time window:**
```python
RATE_LIMITS["query"]["window"] = ONE_WEEK  # Use helper constants
```

### **To add a new endpoint type:**
```python
RATE_LIMITS["new_endpoint"] = {
    "requests": 50,
    "window": ONE_HOUR,
    "description": "My new endpoint"
}
```

---

## ⏰ Time Window Constants

Use these for readability:
```python
ONE_MINUTE = 60
FIVE_MINUTES = 300
THIRTY_MINUTES = 1800
ONE_HOUR = 3600
TWELVE_HOURS = 43200
ONE_DAY = 86400
ONE_WEEK = 604800
```

Example:
```python
"window": ONE_DAY  # Instead of 86400
```

---

## 🚀 After Making Changes

**Restart the backend server:**
```bash
# The new limits will be loaded on startup
python main.py
```

**No Redis restart needed** - changes take effect immediately on server restart.

---

## 💡 Best Practices

1. **Use pre-defined profiles** for quick switching
2. **Use time constants** for readability (`ONE_DAY` vs `86400`)
3. **Add descriptions** to custom limits
4. **Test changes** in development before production
5. **Document custom limits** in comments

---

## 🔍 Checking Current Limits

From Python:
```python
from src.config.rate_limits import get_rate_limits, get_limit_for_endpoint

# Get all limits
limits = get_rate_limits()

# Get specific endpoint
query_limit = get_limit_for_endpoint("query")
print(f"Query limit: {query_limit['requests']}/{query_limit['window']}s")
```

From Redis CLI:
```bash
# See all active rate limit keys
redis-cli KEYS "rate_limit:*"

# Check specific user's count
redis-cli GET "rate_limit:query:agent:PlTZWNC6HAeeomJdjnRlCv8nCgk2"
```

---

## ⚠️ Important Notes

- All limits are **per user** (agent_id), not per session
- Cannot be bypassed by creating new sessions
- Automatically reset after the time window expires
- Tracked in Redis with automatic TTL cleanup
- If Redis is unavailable, rate limiting is disabled (fail-open)

---

## 📝 Example Configurations

### **For Internal Beta Testing**
```python
ACTIVE_LIMITS = {
    "query": {"requests": 500, "window": ONE_DAY},
    "feedback": {"requests": 200, "window": ONE_DAY},
    "ticket": {"requests": 50, "window": ONE_DAY},
}
```

### **For Production Launch**
```python
ACTIVE_LIMITS = {
    "query": {"requests": 100, "window": ONE_DAY},
    "feedback": {"requests": 50, "window": ONE_DAY},
    "ticket": {"requests": 10, "window": ONE_DAY},
}
```

### **For Load Testing**
```python
ACTIVE_LIMITS = DEV_LIMITS  # Essentially no limits
```
