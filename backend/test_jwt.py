"""
JWT Debug Script - Test if JWT validation is working
Run from backend folder: python test_jwt.py
"""
import os
from dotenv import load_dotenv
from jose import jwt, JWTError

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "")
ALGORITHM = "HS256"

print("=" * 60)
print("JWT DEBUG")
print("=" * 60)
print(f"JWT_SECRET length: {len(JWT_SECRET)}")
print(f"JWT_SECRET first 10 chars: {JWT_SECRET[:10]}...")
print(f"JWT_SECRET last 5 chars: ...{JWT_SECRET[-5:]}")
print()

# Get a sample token - you'll need to paste one from browser
sample_token = input("Paste a token from browser (or press Enter to skip): ").strip()

if sample_token:
    print()
    print("Attempting to decode token...")
    try:
        # Try to decode without verification first to see contents
        unverified = jwt.get_unverified_claims(sample_token)
        print(f"Token claims (unverified): {unverified}")
        print(f"Token subject (user_id): {unverified.get('sub')}")
        print(f"Token issuer: {unverified.get('iss')}")
        print()
        
        # Now try with verification
        payload = jwt.decode(sample_token, JWT_SECRET, algorithms=[ALGORITHM])
        print("✅ TOKEN VERIFIED SUCCESSFULLY!")
        print(f"Verified payload: {payload}")
    except jwt.ExpiredSignatureError:
        print("❌ Token has EXPIRED")
    except JWTError as e:
        print(f"❌ JWT Verification FAILED: {e}")
        print()
        print("This means your JWT_SECRET doesn't match the one Supabase used to sign the token.")
        print("Double-check: Supabase Dashboard → Settings → API → JWT Secret")
else:
    print("Skipped token test.")
    print()
    print("To get a token:")
    print("1. Open browser DevTools (F12)")
    print("2. Go to Application → Local Storage → your site")
    print("3. Find 'sb-*-auth-token' key")
    print("4. Copy the 'access_token' value")
