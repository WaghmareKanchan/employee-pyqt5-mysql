import smtplib, socket, ssl, sys
sys.path.insert(0, ".")
from app.core import config

host, user, pw = config.SMTP_HOST, config.SMTP_USERNAME, config.SMTP_PASSWORD
print("host:", host, "| user:", user, "| password length:", len(pw), "(Gmail App Password should be 16)")
print(".env says: port", config.SMTP_PORT, "TLS", config.SMTP_USE_TLS, "SSL", config.SMTP_USE_SSL)
ctx = ssl.create_default_context()

for port in (587, 465):
    print(f"\n--- port {port}: raw connection")
    try:
        socket.create_connection((host, port), timeout=10).close()
        print("   reachable")
    except Exception as e:
        print("   BLOCKED:", e)
        continue
    try:
        if port == 587:
            s = smtplib.SMTP(host, 587, timeout=15)
            s.ehlo(); s.starttls(context=ctx); s.ehlo()
        else:
            s = smtplib.SMTP_SSL(host, 465, timeout=15, context=ctx)
        s.login(user, pw)
        print("   LOGIN OK  -> use these settings")
        s.quit()
    except Exception as e:
        print("   FAILED:", type(e).__name__, e)