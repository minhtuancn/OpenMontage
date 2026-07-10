# OpenMontage Security Guide

## SSH Security

### Key-Based Authentication
- Dedicated SSH key for DEV→GPU: `/home/dev/.ssh/openmontage_gpu`
- Password login on GPU is disabled after SSH key verification
- SSH config at `~/.ssh/config` with `IdentitiesOnly yes`

### SSH Configuration
```
Host openmontage-gpu
    HostName 10.20.10.210
    User root
    IdentityFile /home/dev/.ssh/openmontage_gpu
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    ConnectTimeout 10
```

## Network Security

### GPU Node Firewall (UFW)
```
Status: active
Default: deny (incoming), allow (outgoing)
Rules:
  22/tcp                     ALLOW IN    Anywhere
  8750/tcp                   ALLOW IN    10.20.10.0/23
```

### GPU API Security
- Shared secret authentication via `Authorization: Bearer <secret>`
- IP-restricted to LAN subnet (10.20.10.0/23)
- Not exposed to Internet

### Backlot Security
- Binds to 127.0.0.1 only
- Accessible via SSH tunnel
- No direct network exposure

## Secrets Management

### What NOT to Commit
- API keys
- SSH keys
- Passwords
- Environment secrets (.env)
- GPU API shared secret

### File Permissions
```bash
.env                    chmod 600
SSH private keys        chmod 600
SSH public keys         chmod 644
SSH config              chmod 600
```

## Service Security

- DEV services run as user `dev` (not root)
- GPU API runs as root (requires GPU access)
- No production services run as root unnecessarily

## Incident Response

1. **SSH compromised**: Revoke keys, update firewall, audit logs
2. **GPU API exposed**: Change shared secret, update firewall
3. **Data breach**: Rotate all API keys, audit access logs
4. **Service failure**: Check logs, restart service, rollback if needed
