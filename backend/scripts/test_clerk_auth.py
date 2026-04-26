import os
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

def test_clerk_verification_logic():
    # 1. Generate a test RSA key pair (RS256 requires RSA)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # 2. Get Public Key in PEM format (this is what settings.CLERK_JWT_SIGNING_KEY would be)
    public_key_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

    # 3. Get Private Key in PEM format for signing
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")

    # 4. Create a test payload matching the Clerk template expectations
    test_payload = {
        "user_id": "user_test_12345",
        "email": "test@example.com",
        "exp": 9999999999 # Far future
    }

    # 5. Sign the token with RS256
    token = jwt.encode(test_payload, private_key_pem, algorithm="RS256")

    print("--- JWT Verification Test ---")
    try:
        # 6. Verify and decode using the Public Key (Simulating get_current_user logic)
        decoded_payload = jwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )
        
        print("Clerk JWT verification logic: OK")
        print(f"Extracted user_id: {decoded_payload.get('user_id')}")
        print(f"Extracted email: {decoded_payload.get('email')}")
        
    except Exception as e:
        print(f"Clerk JWT verification logic: FAILED")
        print(f"Error: {e}")

if __name__ == "__main__":
    test_clerk_verification_logic()
