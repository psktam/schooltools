"""Encrypts a phone-banking script"""
import os

import arguably

from cryptography.fernet import Fernet


@arguably.command
def encrypt(
    input_file: str, 
    key: str, *, 
    output_folder: str = "data/phonebank_scripts/"
):
    """Encrypt a given file"""
    cipher_suite = Fernet(key)
    base_fname = os.path.split(input_file)[1]
    output_path = os.path.join(output_folder, base_fname)
    with open(input_file, 'rb') as fh, open(output_path, 'wb') as wh:
        raw_text = fh.read()
        encrypted = cipher_suite.encrypt(raw_text)

        wh.write(encrypted)


@arguably.command
def decrypt(
    input_file: str, 
    output_file: str,
    key: str
):
    """Decrypt a given file"""
    cipher_suite = Fernet(key)
    with open(input_file, 'rb') as fh, open(output_file, 'wb') as wh:
        cipher_text = fh.read()
        decrypted = cipher_suite.decrypt(cipher_text)
        wh.write(decrypted)


if __name__ == "__main__":
    arguably.run()
    