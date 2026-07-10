# OpenMontage Operations Guide

## Daily Operations

### Check System Status
```bash
sudo openmontage-status          # Full system status
openmontage-gpu-status            # GPU node status only
```

### Launch Agent Session
```bash
openmontage-agent                 # Launches/attaches tmux session
```

### View Logs
```bash
# DEV machine
tail -f /srv/openmontage/logs/*.log
journalctl --user -u openmontage-backlot -n 100 --no-pager

# GPU machine
ssh openmontage-gpu
tail -f /opt/openmontage-gpu/logs/gpu_api.log
journalctl -u openmontage-gpu-api -n 100 --no-pager
```

### Start/Stop Services
```bash
# Backlot (DEV)
systemctl --user start openmontage-backlot
systemctl --user stop openmontage-backlot
systemctl --user restart openmontage-backlot

# GPU API
ssh openmontage-gpu 'systemctl restart openmontage-gpu-api'
```

## Git Workflow

### Check Current Branch
```bash
cd /opt/openmontage && git branch
```

### Update from Upstream
```bash
sudo openmontage-check-update     # Check for updates
sudo openmontage-update-staging   # Pull and merge updates
```

### Deploy to Production
```bash
git checkout production && git merge --no-ff develop
git tag production-$(date +%Y%m%d-%H%M%S)
git push origin production --tags
```

### Deploy Code to GPU
```bash
sudo openmontage-deploy-gpu       # Push GPU services to GPU node
```

### Backup
```bash
sudo openmontage-backup           # Backup config and projects
```

### Rollback
```bash
sudo openmontage-rollback         # List and rollback to previous tag
```

## GPU Node Operations

### Check GPU Status
```bash
openmontage-gpu-status
# Or directly:
ssh openmontage-gpu nvidia-smi
```

### Restart GPU Services
```bash
ssh openmontage-gpu 'systemctl restart openmontage-gpu-api'
```

### Test GPU API
```bash
curl -fsS http://10.20.10.210:8750/health
curl -fsS http://10.20.10.210:8750/gpu
```

## SSH Tunnel for Backlot

```bash
ssh -N -L 4750:127.0.0.1:4750 dev@10.20.10.103
# Then open http://127.0.0.1:4750 in browser
```
