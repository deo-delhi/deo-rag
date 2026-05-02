# 1. 
The live retrieval was doing plain semantic search even when the user clearly named a document, e.g. Sahodara Devi Vs GoI. Because terms like Devi, GoI, Government of India, Union of India occur across many legal PDFs, the vector search pulled unrelated cases first. The LLM then answered from those unrelated chunks, which is exactly what your screenshot shows.

I confirmed:

Sahodara Devi Vs GoI.pdf is present.
Its PDF text is extractable (~17.6k chars).
The vector DB has 18 chunks for it.
The bad answer came because retrieval included Ibrahim Uddin, Nagubai Ammal, Ashoka Marketing, etc. before/alongside Sahodara.
I changed retrieval so that when the question strongly matches an uploaded PDF filename/title, it uses a metadata filter and retrieves chunks only from that matching document. I also updated /debug/retrieve to show this same production retrieval behavior.

# 2.
backend/hybrid_retrieval.py (new): BM25 + dense vector with Reciprocal Rank Fusion; BM25 index built lazily per PG-Vector collection from the existing langchain_pg_embedding rows; cache invalidated on re-ingest. Industry-standard fix; the legal-domain benchmark in the cited sources reports +27% nDCG vs. dense-only.
backend/rag_pipeline.py: replaced the loose grounding prompt with a strict one. Snippets are labelled [snippet N] source: <filename> | page: <P>. Hard rules: only use snippets whose source matches the named document, never use prior knowledge, abstain with a fixed phrase if evidence is missing, end with a Sources: line.
backend/app.py:
_retrieve_for_libraries now uses hybrid_retrieve for both branches; named-document branch additionally filters by source metadata.
/ask short-circuits to an honest abstention when the question clearly names a document but no chunk from that document survived retrieval (no more "summarise X" pulling from Y/Z).
Honest "Insufficient evidence …" abstentions are no longer "rescued" by stitching unrelated sentences (the old extractive rescue was reintroducing hallucinations).
On ingest completion, the BM25 cache is invalidated for that collection.




# 3.
If summaries ever feel too thin
That's almost always a top-k question, not a model question. Open Settings → Retriever top-k and try 10 or 12. The hybrid retriever already pulls a wider candidate pool internally (max(top_k * 5, 20)) and fuses, so increasing top-k mostly just lets more of those candidates reach the LLM context.

You don't need to touch:

OLLAMA_NUM_CTX (8192 is fine for any single-doc summary)
OLLAMA_NUM_PREDICT (2048 is plenty for 500-word answers)
LLM_TEMPERATURE (keep at 0 for grounded summarisation)
So: send your prompt as-is on a freshly restarted backend, and you should see a Sahodara-only summary about Rule 27 of the Cantonment Land Administration Rules, the discretion vs. mandatory question, and the High Court's direction to reconsider — followed by a Sources: Sahodara Devi Vs GoI.pdf (page 1) line.


# 4. Docker Desktop "failed to connect to the docker API" on first run (fresh machine)
Symptom on a brand-new Windows box:

```
Successfully installed                       <-- Docker Desktop just installed
docker : failed to connect to the docker API at npipe:////./pipe/docker_engine;
check if the path is correct and if the daemon is running:
open //./pipe/docker_engine: The system cannot find the file specified.
At C:\data\code\DEO-RAG\install-and-run.ps1:169 char:5
```
Cause: Docker Desktop's installer turns on the WSL2 / VirtualMachinePlatform / Hyper-V Windows features. Those features only become active **after a reboot** — until then the WSL2 backend has no kernel and `\\.\pipe\docker_engine` doesn't exist, so `docker info` fails. Manually rebooting + re-running the script worked because that's exactly what was missing.

Fix: `install-and-run.ps1` now does this automatically.
- Before running `winget install Docker.DockerDesktop`, it remembers whether `Docker Desktop.exe` already existed and whether Windows already had a pending reboot.
- It runs `wsl --install --no-distribution` first when WSL2 isn't present, so the kernel components are queued before Docker Desktop installs on top.
- Right after the Docker Desktop install, if Docker Desktop was newly installed *or* `Test-PendingReboot` now returns true, the script:
  1. Persists state to `C:\ProgramData\DEO-RAG-Installer\state.json` (so it knows it has already taken the "post-Docker reboot" once and won't loop).
  2. Registers a Task Scheduler ONLOGON task `DEO-RAG-Installer-Resume` that re-launches `install-and-run.bat` elevated at the next user logon.
  3. Calls `shutdown /r /t 30` and prints a clear yellow notice (with `shutdown /a` as a manual escape hatch).
- The script exits. Windows reboots ~30 s later. After login, the scheduled task fires, the bat re-elevates, and the script picks up where it left off — Docker Desktop now starts cleanly because WSL2 is live.
- As a defensive net, if the `Wait-DockerDaemon` poll still fails after we've already done the post-install reboot, the script will auto-reboot one more time (max 2 reboots total) before throwing.
- On a fully successful run, the resume task and the state file are both removed so they don't trigger on every future logon.

End result: a truly one-click install on a fresh Windows machine. The user double-clicks `install-and-run.bat` once; the only "interaction" left is the Windows login prompt after the automatic reboot.


# 5. Installer crashed on `wsl --status` even though the situation was recoverable
Symptom on a machine where Ollama / CUDA / Node had already been installed in a prior pass:

```
WARNING:   [winget] OpenJS.NodeJS.LTS returned exit -1978335189 (likely already installed).
WARNING:   [winget] Nvidia.CUDA returned exit -1978335189 (likely already installed).
WARNING:   [winget] Ollama.Ollama returned exit -1978335189 (likely already installed).
wsl.exe : The Windows Subsystem for Linux is not installed. You
can install by running 'wsl.exe --install'.
At C:\data\code\DEO-RAG\install-and-run.ps1:360 char:5
+     & wsl.exe --status *> $null
```
Two separate problems:

1. **Noisy "warnings" for things that aren't problems.** winget exit code `-1978335189` (`APPINSTALLER_CLI_ERROR_UPDATE_NOT_APPLICABLE`) just means the package is already installed and there is no newer version. It was being printed as `WARNING:` which made every successful re-run look like it had failed.
2. **Hard stop on `wsl --status`.** On Windows PowerShell 5.1 with `$ErrorActionPreference = "Stop"`, when a native exe writes to stderr (here, "The Windows Subsystem for Linux is not installed.") PowerShell wraps that line as a `NativeCommandError` that *does* honour `Stop`. `*> $null` suppresses the visible output but doesn't prevent the wrap, so the script terminated even though the WSL-missing case is exactly what `Install-Wsl2IfNeeded` wants to handle.

Fix - made the installer truly tolerant of native-command stderr:
- Added `Invoke-NativeSafe`: runs a native exe with `$ErrorActionPreference` locally lowered to `Continue`, swallows all streams, and returns `$LASTEXITCODE`. Now used for every `docker info`, `docker compose version`, and the winget install call.
- Added `Test-WingetPackageInstalled` (uses `winget list --id <id> -e` with safe stderr handling) and a `WingetBenignExitCodes` whitelist (`0`, `-1978335189`, `-1978335212`, `-1978335215`, `-1978335135`). `Install-WingetPackage` now:
  1. Probes first; if the package is already installed, prints `[winget] X already installed - skipping.` (no warning) and moves on.
  2. Otherwise installs, then treats benign exit codes (or a positive post-install probe) as success with a friendly `[winget] X already present - continuing.` message.
  3. Only emits `WARNING` for genuinely unexpected exit codes.
- Rewrote `Install-Wsl2IfNeeded` and added `Test-Wsl2Installed` to do the WSL probe via `cmd /c "wsl --status >nul 2>&1"`. cmd.exe owns the redirection inside its own process, so PowerShell never receives the WSL stderr - no more `NativeCommandError`, no more crash.
- Wrapped the entire main `try { ... }` block with a top-level `catch { ... }` that prints a clean red error box, the call site, and a yellow "what to do next" hint (re-run the bat - it's idempotent), then `exit 1`. No more raw PowerShell stack traces dumped at the user.

Smoke-tested: a synthetic native command writing to stderr + exiting 7, a real `docker info` call, and `wsl --status` on a box with WSL absent - all three now report cleanly and the script keeps going. Previously each of them could terminate the run on the wrong host.

