import smtplib, ssl

ctx = ssl.create_default_context()

print("=========== PORT 587 (STARTTLS) ===========")
try:
    s = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
    s.set_debuglevel(1)
    s.ehlo()
    s.starttls(context=ctx)
    s.ehlo()
    print(">>> reached the end without login: OK")
    s.quit()
except Exception as e:
    print(">>> FAILED:", type(e).__name__, e)

print("\n=========== PORT 465 (SSL) ===========")
try:
    s = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15, context=ctx)
    s.set_debuglevel(1)
    s.ehlo()
    print(">>> reached the end without login: OK")
    s.quit()
except Exception as e:
    print(">>> FAILED:", type(e).__name__, e)