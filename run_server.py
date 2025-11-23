import uvicorn
from app.server import app

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 Jarvis OAuth Server Starting...")
    print("="*60)
    print("\n📍 Server URL: http://localhost:8000")
    print("📧 Gmail auth: http://localhost:8000/gmail/auth")
    print("📅 Calendar auth: http://localhost:8000/calendar/auth")
    print("\n💡 Tip: Leave this server running while using the voice agent")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

