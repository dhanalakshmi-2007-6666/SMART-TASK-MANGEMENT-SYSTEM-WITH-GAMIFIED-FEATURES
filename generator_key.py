from py_vapid import Vapid
from cryptography.hazmat.primitives import serialization
from base64 import urlsafe_b64encode

vapid = Vapid()
vapid.generate_keys()

# Proper enum usage
public_bytes = vapid.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)

private_bytes = vapid.private_key.private_numbers().private_value.to_bytes(32, 'big')

public_key = urlsafe_b64encode(public_bytes).decode('utf-8').rstrip("=")
private_key = urlsafe_b64encode(private_bytes).decode('utf-8').rstrip("=")

print("PUBLIC KEY:\n", public_key)
print("\nPRIVATE KEY:\n", private_key)