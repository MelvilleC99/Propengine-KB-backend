# System Health Dashboard - Frontend Implementation Guide

## Backend Endpoints Created ✅

### Main Health Check
```
GET /api/health
```

Returns comprehensive system status with all service health checks.

### Simple Ping
```
GET /api/health/ping
```

Returns simple "ok" for basic uptime monitoring.

---

## Frontend Implementation Examples

### 1. React Component (Recommended)

```tsx
// components/SystemHealthDashboard.tsx
import { useEffect, useState } from 'react';

interface ServiceHealth {
  status: 'healthy' | 'degraded' | 'down';
  message: string;
  response_time_ms?: number;
  model?: string;
  dimensions?: number;
}

interface SystemHealth {
  timestamp: number;
  overall_status: 'healthy' | 'degraded' | 'down';
  services: {
    redis: ServiceHealth;
    firebase: ServiceHealth;
    astra: ServiceHealth;
    openai_chat: ServiceHealth;
    openai_embeddings: ServiceHealth;
  };
  summary: {
    total: number;
    healthy: number;
    degraded: number;
    down: number;
  };
}

export default function SystemHealthDashboard() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check health on mount
    checkHealth();
    
    // Poll every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/health');
      const data = await response.json();
      setHealth(data);
      setLoading(false);
    } catch (error) {
      console.error('Health check failed:', error);
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-green-600 bg-green-50';
      case 'degraded': return 'text-yellow-600 bg-yellow-50';
      case 'down': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return '✅';
      case 'degraded': return '⚠️';
      case 'down': return '❌';
      default: return '❓';
    }
  };

  if (loading) {
    return <div className="p-4">Checking system health...</div>;
  }

  if (!health) {
    return <div className="p-4 text-red-600">Unable to fetch system health</div>;
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Overall Status */}
      <div className={`p-4 rounded-lg mb-6 ${getStatusColor(health.overall_status)}`}>
        <h2 className="text-2xl font-bold mb-2">
          {getStatusIcon(health.overall_status)} System Status: {health.overall_status.toUpperCase()}
        </h2>
        <p className="text-sm">
          {health.summary.healthy}/{health.summary.total} services healthy
          {health.summary.degraded > 0 && ` • ${health.summary.degraded} degraded`}
          {health.summary.down > 0 && ` • ${health.summary.down} down`}
        </p>
      </div>

      {/* Individual Services */}
      <div className="grid gap-4">
        {Object.entries(health.services).map(([name, service]) => (
          <div
            key={name}
            className={`p-4 rounded-lg border-2 ${getStatusColor(service.status)}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{getStatusIcon(service.status)}</span>
                <div>
                  <h3 className="font-semibold capitalize">
                    {name.replace('_', ' ')}
                  </h3>
                  <p className="text-sm">{service.message}</p>
                  {service.model && (
                    <p className="text-xs mt-1 opacity-75">Model: {service.model}</p>
                  )}
                  {service.dimensions && (
                    <p className="text-xs opacity-75">Dimensions: {service.dimensions}</p>
                  )}
                </div>
              </div>
              {service.response_time_ms && (
                <div className="text-right">
                  <p className="text-sm font-mono">
                    {service.response_time_ms.toFixed(0)}ms
                  </p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Last Updated */}
      <p className="text-sm text-gray-500 mt-4 text-center">
        Last checked: {new Date(health.timestamp * 1000).toLocaleTimeString()}
      </p>
    </div>
  );
}
```

---

### 2. Simple Status Badge (For Header/Nav)

```tsx
// components/SystemStatusBadge.tsx
import { useEffect, useState } from 'react';

export default function SystemStatusBadge() {
  const [status, setStatus] = useState<'healthy' | 'degraded' | 'down' | null>(null);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 60000); // Every minute
    return () => clearInterval(interval);
  }, []);

  const checkStatus = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/health');
      const data = await response.json();
      setStatus(data.overall_status);
    } catch {
      setStatus('down');
    }
  };

  const getColor = () => {
    switch (status) {
      case 'healthy': return 'bg-green-500';
      case 'degraded': return 'bg-yellow-500';
      case 'down': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${getColor()}`} />
      <span className="text-sm capitalize">{status || 'checking...'}</span>
    </div>
  );
}
```

---

### 3. Next.js API Route (If using Next.js)

```typescript
// app/api/system-health/route.ts
export async function GET() {
  try {
    const response = await fetch('http://localhost:8000/api/health');
    const data = await response.json();
    
    return Response.json(data);
  } catch (error) {
    return Response.json(
      { error: 'Failed to fetch health status' },
      { status: 500 }
    );
  }
}
```

Then use in component:
```tsx
const response = await fetch('/api/system-health');
const health = await response.json();
```

---

### 4. Vue.js Component

```vue
<!-- components/SystemHealth.vue -->
<template>
  <div class="health-dashboard">
    <div :class="['status-banner', overallStatus]">
      <h2>{{ statusIcon }} System Status: {{ overallStatus }}</h2>
      <p>{{ summary }}</p>
    </div>

    <div class="services">
      <div
        v-for="(service, name) in services"
        :key="name"
        :class="['service', service.status]"
      >
        <span class="icon">{{ getIcon(service.status) }}</span>
        <div class="info">
          <h3>{{ formatName(name) }}</h3>
          <p>{{ service.message }}</p>
          <small v-if="service.response_time_ms">
            {{ service.response_time_ms }}ms
          </small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

const overallStatus = ref('checking');
const services = ref({});
const summary = ref('');
let interval: any;

onMounted(() => {
  checkHealth();
  interval = setInterval(checkHealth, 30000);
});

onUnmounted(() => {
  clearInterval(interval);
});

async function checkHealth() {
  try {
    const response = await fetch('http://localhost:8000/api/health');
    const data = await response.json();
    
    overallStatus.value = data.overall_status;
    services.value = data.services;
    summary.value = `${data.summary.healthy}/${data.summary.total} healthy`;
  } catch (error) {
    console.error('Health check failed:', error);
  }
}

function getIcon(status: string) {
  return status === 'healthy' ? '✅' : status === 'degraded' ? '⚠️' : '❌';
}

function formatName(name: string) {
  return name.replace('_', ' ').split(' ')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}
</script>
```

---

## Testing the Endpoints

### Using cURL
```bash
# Check full health
curl http://localhost:8000/api/health | jq

# Simple ping
curl http://localhost:8000/api/health/ping
```

### Using Browser
```
http://localhost:8000/api/health
```

### Expected Response
```json
{
  "timestamp": 1706368800,
  "overall_status": "degraded",
  "services": {
    "redis": {
      "status": "healthy",
      "message": "Connected",
      "response_time_ms": 5.23
    },
    "firebase": {
      "status": "healthy",
      "message": "Connected",
      "response_time_ms": 145.67
    },
    "astra": {
      "status": "down",
      "message": "Vector store not connected",
      "response_time_ms": null
    },
    "openai_chat": {
      "status": "healthy",
      "message": "Chat completions working",
      "model": "gpt-4o-mini",
      "response_time_ms": 892.34
    },
    "openai_embeddings": {
      "status": "down",
      "message": "Deployment not found for model: text-embedding-3-large",
      "model": "text-embedding-3-large",
      "dimensions": null,
      "response_time_ms": null
    }
  },
  "summary": {
    "total": 5,
    "healthy": 3,
    "degraded": 0,
    "down": 2
  }
}
```

---

## Integration Steps

1. **Backend is ready** ✅ - Routes created and registered
2. **Restart your backend** to load the new routes
3. **Choose a frontend approach** from examples above
4. **Test the endpoint** using curl or browser
5. **Implement the component** in your frontend
6. **Add to your dashboard** or navigation

---

## Monitoring Options

### Option 1: Dashboard Page
Create a dedicated `/system-status` page for admins

### Option 2: Header Badge
Show small status indicator in nav bar for all users

### Option 3: Alert Banner
Show warning banner when services are down

### Option 4: External Monitoring
Use the `/api/health/ping` endpoint with services like:
- UptimeRobot
- Pingdom
- Better Uptime
- Status Page

---

## Tips

- **Polling Frequency**: 30-60 seconds is good for dashboard
- **Error Handling**: Always handle fetch errors gracefully
- **User Visibility**: Consider showing to admins only
- **Caching**: Consider caching health data for 10-30 seconds
- **Notifications**: Can trigger alerts when status changes

