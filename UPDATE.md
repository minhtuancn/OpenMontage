# OpenMontage Update Guide

## Updating from Upstream

### 1. Check for Updates
```bash
sudo openmontage-check-update
```

### 2. Update Staging Branch
```bash
sudo openmontage-update-staging
```
This will:
- Fetch upstream/main
- Reset upstream-main to match
- Merge into custom branch
- Merge into develop branch

### 3. Resolve Conflicts (if any)
```bash
cd /opt/openmontage
git status  # Check for conflicted files
# Edit conflicted files
git add <file>
git commit -m "Resolve merge conflicts"
```

### 4. Test
```bash
source .venv/bin/activate
make test
```

### 5. Deploy to Production
```bash
git checkout production
git merge --no-ff develop
git tag production-$(date +%Y%m%d-%H%M%S)
git push origin production --tags
```

## Deploying to GPU Node

```bash
sudo openmontage-deploy-gpu
```

This will:
1. Check working tree is clean
2. Push GPU services to GPU node
3. Create backup of current GPU services
4. Restart GPU API service
5. Run health check
6. Rollback if health check fails

## Manual Update Steps

```bash
cd /opt/openmontage
git fetch upstream --prune
git checkout upstream-main
git reset --hard upstream/main
git push origin upstream-main --force-with-lease
git checkout custom
git merge --no-ff upstream-main
```
