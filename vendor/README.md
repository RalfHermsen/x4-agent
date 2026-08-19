# vendor/

Third-party code, committed here to pin the version. Do not edit, except where
noted below.

## X4_Python_Pipe_Server

From **[bvbohnen/x4-projects](https://github.com/bvbohnen/x4-projects)**, master
branch, fetched 2026-08-19. Licence: **MIT** (see the source repository).

This is the Python host that serves the named pipes to X4, and it is the piece
that makes this whole project possible. Credit for it goes to that project and
to SirNukes, not to this repo.

It is committed rather than pulled as a dependency because the GitHub releases
of that project date from 2020 while master carries the current working code:
without pinning you would later have no way to tell which version you ran.

**Our one change:** `permissions.json` has `x4_agent_bridge` added. The host
only loads Python modules from extensions whose `content.xml` id is listed
there, and without that line it rejects our module silently.

Running it (PowerShell):

```powershell
$env:PYTHONPATH = "vendor"
.venv\Scripts\python.exe -u -m X4_Python_Pipe_Server.Main -v
```

The `-u` is not a detail. Without unbuffered output you see nothing at all when
something goes wrong.
