import os, smtplib, socket, ssl, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.core import config

print("Your PC name Python sends to Gmail:", repr(socket.getfqdn()))
ctx = ssl.create_default_context()

for label, kwargs in (("default hostname", {}), ("local_hostname='localhost'", {"local_hostname": "localhost"})):
    try:
        s = smtplib.SMTP(config.SMTP_HOST, 587, timeout=15, **kwargs)
        s.ehlo(); s.starttls(context=ctx); s.ehlo()
        s.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        print(f"{label}: LOGIN OK")
        s.quit()
    except Exception as e:
        print(f"{label}: FAILED -> {type(e).__name__}: {e}")