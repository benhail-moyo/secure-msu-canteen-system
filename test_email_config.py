import os
from config import config
from flask import Flask

# Check environment variables
print("=== EMAIL CONFIGURATION DIAGNOSTIC ===\n")

print("1. Environment Variables:")
print(f"   MAIL_USERNAME: {os.environ.get('MAIL_USERNAME', 'NOT SET')}")
print(f"   MAIL_PASSWORD: {'SET' if os.environ.get('MAIL_PASSWORD') else 'NOT SET'}")
print(f"   MAIL_SERVER: {os.environ.get('MAIL_SERVER', 'NOT SET')}")
print(f"   MAIL_PORT: {os.environ.get('MAIL_PORT', 'NOT SET')}")

# Create Flask app and check config
app = Flask(__name__)
app.config.from_object(config['development'])

print("\n2. Flask App Configuration:")
print(f"   MAIL_USERNAME: {app.config.get('MAIL_USERNAME', 'NOT SET')}")
print(f"   MAIL_PASSWORD: {'SET' if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
print(f"   MAIL_SERVER: {app.config.get('MAIL_SERVER', 'NOT SET')}")
print(f"   MAIL_PORT: {app.config.get('MAIL_PORT', 'NOT SET')}")
print(f"   MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS', 'NOT SET')}")
print(f"   MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER', 'NOT SET')}")

print("\n3. Email Configuration Status:")
if app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'):
    print("   ✓ Email is CONFIGURED - emails will be sent")
else:
    print("   ✗ Email is NOT CONFIGURED - emails will NOT be sent (debug mode)")
    print("   → Set MAIL_USERNAME and MAIL_PASSWORD environment variables to enable email")

print("\n=== HOW TO FIX ===")
print("\nBefore running the app, set these PowerShell environment variables:")
print('  $env:MAIL_USERNAME="your-email@gmail.com"')
print('  $env:MAIL_PASSWORD="your-app-password"')
print('  .\.venv\Scripts\python.exe app.py')
