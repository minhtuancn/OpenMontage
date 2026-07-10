# OpenMontage Rollback Guide

## Production Rollback

### List Available Tags
```bash
cd /opt/openmontage
git tag -l 'production-*' --sort=-version:refname | head -10
```

### Rollback to Previous Version
```bash
sudo openmontage-rollback
# Or manually:
git checkout production
git reset --hard production-20260709-120000
git push origin production --force-with-lease
```

### Restart Services After Rollback
```bash
systemctl --user restart openmontage-backlot
```

## GPU Node Rollback

### From DEV Machine
```bash
# Automatic rollback (from deploy script)
# If health check fails after deploy, rollback happens automatically

# Manual rollback:
ssh openmontage-gpu sudo /usr/local/sbin/openmontage-gpu-rollback
```

### From GPU Machine Directly
```bash
sudo /usr/local/sbin/openmontage-gpu-rollback
```

## Full System Rollback

### DEV Machine
```bash
# Restore from backup
ls /srv/backups/openmontage/
sudo openmontage-backup  # Creates a new backup first
# To restore, manually copy from backup directory
```

### GPU Machine
```bash
ssh openmontage-gpu 'ls /srv/backups/openmontage-gpu/'
ssh openmontage-gpu 'cp -r /srv/backups/openmontage-gpu/20260709-120000/services/* /opt/openmontage-gpu/services/'
ssh openmontage-gpu 'systemctl restart openmontage-gpu-api'
```
