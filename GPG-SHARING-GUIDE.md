# Secure GPG Key Sharing via GitHub

This setup allows you to securely share GPG keys between devices using your public GitHub repo.

## How it works

1. **Public keys**: Stored unencrypted (they're meant to be public)
2. **Private keys**: Encrypted with AES-256 using a strong passphrase
3. **Bootstrap**: Use the passphrase to decrypt keys on new devices

## Exporting keys (first device)

```bash
./install.sh gpg-export-list           # List your GPG keys
./install.sh gpg-export YOUR_KEY_ID    # Export specific key
```

When prompted, enter a **strong, memorable passphrase**. This is what you'll need on new devices.

## Setting up new devices

1. Clone your dotfiles repo
2. Import the keys:
   ```bash
   ./install.sh gpg-import-list                    # See available keys
   ./install.sh gpg-import gpg-key-KEYID.pub       # Import public key
   ./install.sh gpg-import gpg-key-KEYID.sec.gpg   # Import private key (will prompt for passphrase)
   ```

## Security considerations

✅ **Safe to commit to public GitHub**:
- Private keys are encrypted with AES-256
- Uses strong key derivation (65M iterations)
- Only you know the passphrase

⚠️ **Passphrase security**:
- Use a strong, memorable passphrase
- Store it securely (password manager)
- Don't write it down in the repo

## Alternative: Age encryption

For even simpler setup, consider using `age` with a password file:

```bash
# Install age
sudo pacman -S age  # or brew install age

# Export with age
gpg --export-secret-keys KEYID | age -p > keys/KEYID.age
```

## Backup strategy

1. **Primary**: Encrypted keys in GitHub repo
2. **Secondary**: Store passphrase in password manager  
3. **Emergency**: Keep one plaintext backup on secure offline storage