# Local runtime

This repository can run as a host-managed local instance on Linux. This document records the non-secret runtime topology; it does not contain credentials, bot IDs, model keys, or external URLs.

## Source and runtime separation

```text
source:    /opt/projects/develop/Avatar
runtime:   /srv/secrets/Avatar/production/app/mykey.py
workspace: /srv/datas/Avatar/production/workspace
web:       127.0.0.1:19180
```

The source tree must not contain `mykey.py`. The runtime config is mounted into the source tree through a local symlink and exposed to the Feishu frontend through `GA_WORKSPACE_ROOT/ga_config/mykey.py`.

## Services

```text
avatar-web.service      # Streamlit, loopback-only on port 19180
avatar-feishu.service   # Feishu long-connection frontend
```

Both use Avatar's own virtual environment and workspace. They must not share another GA instance's source tree, persistent workspace, HTTP port, or IM process.

## Operations

```bash
systemctl status avatar-web.service avatar-feishu.service
journalctl -u avatar-web.service -u avatar-feishu.service --since '10 minutes ago' --no-pager
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:19180/
```

Before starting a second Feishu service for the same app, stop the existing Feishu consumer. A single Feishu app must have exactly one intended long-connection owner.

## Source update boundary

Use `docs/fork-maintenance.md` for upstream synchronization. A source update is not a runtime cutover: validate the branch first, then decide explicitly whether the runtime should be restarted.
