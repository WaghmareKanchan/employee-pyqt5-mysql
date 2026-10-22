import base64, os, smtplib, ssl, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.core import config

user, pw = config.SMTP_USERNAME, config.SMTP_PASSWORD
print("username:", repr(user))
print("password: length", len(pw), "| ascii only:", pw.isascii(), "| contains whitespace:", any(c.isspace() for c in pw))
ctx = ssl.create_default_context()


def attempt(method):
    print(f"\n--- AUTH {method}")
    s = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
    try:
        s.ehlo(); s.starttls(context=ctx); s.ehlo()
        if method == "PLAIN":
            code, msg = s.docmd("AUTH PLAIN " + base64.b64encode(f"\0{user}\0{pw}".encode()).decode())
        else:
            s.docmd("AUTH LOGIN")
            s.docmd(base64.b64encode(user.encode()).decode())
            code, msg = s.docmd(base64.b64encode(pw.encode()).decode())
        print("Gmail answered:", code, msg.decode(errors="replace")[:150])
    except Exception as e:
        print("FAILED:", type(e).__name__, e)
    finally:
        try:
            s.close()
        except Exception:
            pass


attempt("PLAIN")
attempt("LOGIN")