import socket, ssl

print("--- port 587 (plain, should print: 220 smtp.gmail.com ESMTP ...)")
try:
    s = socket.create_connection(("smtp.gmail.com", 587), timeout=10)
    s.settimeout(10)
    print(repr(s.recv(200)))
    s.close()
except Exception as e:
    print("FAILED:", type(e).__name__, e)

print("--- port 465 (TLS, should print the same 220 line)")
try:
    ctx = ssl.create_default_context()
    s = ctx.wrap_socket(socket.create_connection(("smtp.gmail.com", 465), timeout=10),
                        server_hostname="smtp.gmail.com")
    print(repr(s.recv(200)))
    s.close()
except Exception as e:
    print("FAILED:", type(e).__name__, e)