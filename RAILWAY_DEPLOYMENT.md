# Railway Deployment Guide

## Issue: Process Killed with Exit Code -9

Your logs show `process exited with non-zero exit code -9`, which means the inference subprocess is being **killed due to Out of Memory (OOM)**.

## Root Cause

The LiveKit agent with AI models (Anthropic Claude, Silero VAD, turn detector) requires significant RAM for:
- Loading AI models into memory
- Running inference
- Processing voice data

Railway's default memory allocation is insufficient.

## Solutions

### 1. **Increase Memory in Railway (REQUIRED)**

In your Railway dashboard:

1. Go to your service/deployment
2. Click on **Settings** → **Resources**
3. Increase **Memory** to at minimum **2GB** (recommended: **4GB** or **8GB**)
4. Click **Save**
5. Redeploy

### 2. **Monitor Memory Usage**

After deployment, check Railway logs:
- Look for "process exited with non-zero exit code -9" - this indicates OOM
- Check for "Failed to get memory info for process" warnings
- Watch for "initializing process" followed by immediate crashes

### 3. **Alternative: Use Railway Pro Plan**

The free tier has memory limitations. Consider upgrading to:
- **Pro Plan**: Higher memory limits
- **Better performance** for AI workloads

## What Was Done

### Dockerfile Optimizations:
- `MALLOC_ARENA_MAX=2`: Reduces memory fragmentation
- `PYTHONUNBUFFERED=1`: Prevents output buffering (better logs)
- Added proper port exposure for health checks

### Startup Script:
- Downloads model files at startup
- Automatically detects production environment
- Runs agent in production mode (not dev/simulation mode)

## Expected Behavior After Fix

Once you increase the memory, you should see:
```
🚀 Production environment detected, using 'start' mode...
starting worker
preloading plugins
starting inference executor
initializing process
[No crashes, agent stays running and waits for LiveKit connections]
```

## Environment Variables Needed

Make sure these are set in Railway:
- `LIVEKIT_URL`: Your LiveKit server URL
- `LIVEKIT_API_KEY`: Your API key
- `LIVEKIT_API_SECRET`: Your API secret
- `ANTHROPIC_API_KEY`: For Claude
- `TAVILY_API_KEY`: For web search (if used)
- Any other service-specific keys in your `.env`

## Troubleshooting

If still crashing after memory increase:
1. Check if all environment variables are set
2. Verify LiveKit credentials are correct
3. Check Railway build logs for dependency installation errors
4. Ensure all required files downloaded successfully

## Contact
If issues persist, check:
- LiveKit server status
- API key validity
- Railway service logs for specific errors
