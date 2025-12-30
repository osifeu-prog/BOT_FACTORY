import os
print("py exe OK")
print("ADMIN_USER_ID:", os.getenv("ADMIN_USER_ID"))
print("OPENAI_API_KEY set:", bool((os.getenv("OPENAI_API_KEY") or "").strip()))