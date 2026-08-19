# Environment and portability notes

Everything here was measured on the development machine, not assumed. Your setup
will differ; what matters are the constraints and the traps, which are general.

## Game machine (Windows)

| Item | Value used during development |
|------|-------------------------------|
| X4 install | default Steam location under `steamapps/common/X4 Foundations` |
| `version.dat` | `900` (version 9.00) |
| Build | 611726, patched June 2026 |
| RAM | 15 GB total, roughly 1.6 GB free with X4 running |
| Python | 3.14, venv in `.venv/` |

Set the `X4_DIR` environment variable if your installation lives somewhere else.

### Finding the save folder is not trivial

X4 stores saves under `<Documents>/Egosoft/X4/<profile id>/save/`, but
`<Documents>` is not reliably `~/Documents`. Windows folder redirection, which
OneDrive sets up by default in many configurations, can move it to another
drive entirely. On the development machine it pointed at a OneDrive folder on a
different volume, and code that assumed the home directory silently found
nothing.

Resolve it at runtime instead:

* Python: read `Personal` from
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders`
  (this is what `save_parser.documents_dir()` does).
* PowerShell: `[Environment]::GetFolderPath('MyDocuments')`.

The profile folder is named after your Steam account id. Note that stale profile
folders from older installs can linger and are easy to mistake for the live one:
check modification times, not folder order.

A useful cross-check is
`Steam/userdata/<account id>/392160/remotecache.vdf`, which lists the
cloud-synced save names, sizes and timestamps.

### If your saves are inside OneDrive

Sync introduces behaviour worth planning for: files can be cloud-only
placeholders, and a file watcher on the folder will see sync events as well as
real saves.

### Memory: streaming is mandatory

A late-game save is 40 to 70 MB gzipped, expanding to hundreds of megabytes of
XML. Loading one as a full `lxml.etree` needs far more RAM than a typical
machine has spare while the game itself is running. Every parser in this repo
therefore streams with `iterparse` and releases finished subtrees. Measured: a
42 MB save parses in 18.8 s with flat memory.

### DLCs change the data

The development install had all DLCs enabled. Wares, sectors and ship macros
differ per DLC, and `libraries/mapdefaults.xml` exists once in the base game
plus once per DLC as a patch. `gamedata.py` merges all copies; reading only the
base game gives an incomplete map.

## Inference host

The planner runs against [Ollama](https://ollama.com) over the network, on a
separate machine with a 24 GB GPU. Point `X4_OLLAMA_URL` at yours; it defaults
to `http://localhost:11434`.

Two things cost real debugging time and are worth knowing up front:

* Reasoning models return **empty content** unless `think: false` is passed on
  the native `/api/chat` endpoint.
* `num_ctx` must be set explicitly and generously. Ollama truncates silently
  when the prompt exceeds the context window, and what falls off is the front of
  the prompt, which is exactly where the guidelines sit.

## Reference corpus

Development used eleven saves from a single profile folder, spanning X4 6.20,
7.00, 8.00 and 9.00, from a 20-second fresh start to a 188 million credit empire
with 220 ships. The parser runs unmodified across all of them, which is the
cheapest regression suite available: if you have played the game for a while,
you already own one too. `evaluate.py` runs the whole loop over it.
