---
name: diplomat-service
description: Start, stop, or check the Diplomat bot service
---

Manage the Diplomat bot on the Pi. Run ONE of these commands based on what the user asked:

**Start:**
```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start
```

**Stop:**
```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh stop
```

**Status:**
```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh status
```

**Logs (last 50 lines):**
```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh logs 50
```

**Restart:**
```bash
incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh restart
```

Report the output to the user.
