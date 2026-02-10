"""Generate RSA key pairs for agent authentication."""
import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_key_pair(agent_name: str, output_dir: str = "."):
    """Generate an RSA key pair and save to PEM files."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path = os.path.join(output_dir, f"{agent_name}_private.pem")
    pub_path = os.path.join(output_dir, f"{agent_name}_public.pem")

    with open(priv_path, "wb") as f:
        f.write(private_pem)
    with open(pub_path, "wb") as f:
        f.write(public_pem)

    print(f"Generated key pair for '{agent_name}':")
    print(f"  Private: {priv_path}")
    print(f"  Public:  {pub_path}")
    return public_pem.decode("utf-8")


if __name__ == "__main__":
    agents = sys.argv[1:] or [
        "web_search_agent",
        "code_analyzer_agent",
        "doc_summarizer_agent",
        "buyer_agent",
    ]
    os.makedirs("keys", exist_ok=True)
    for name in agents:
        generate_key_pair(name, "keys")
    print(f"\nGenerated {len(agents)} key pairs in ./keys/")
