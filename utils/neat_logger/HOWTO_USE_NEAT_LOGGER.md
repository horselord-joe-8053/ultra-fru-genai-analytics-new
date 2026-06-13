<h1 id="howto-use-neat-logger" style="color:#0d47a1;font-size:1.5em;font-weight:700;border-bottom:2px solid #90caf9;padding-bottom:0.25em;margin-top:0">Using <code>neat_logger</code> (portable CLI logging)</h1>

**Type:** how-to — **Audience:** any Python project that copies the `utils/` tree.

`neat_logger` is a **small CLI helper** for **colored, timestamped terminal output** (stdout / stderr), optional **mirror to a plain log file**, optional **phase** / **operation** markers, and a **heartbeat** thread for long-running work (optional YAML config; falls back to JSON or defaults). This document matches **`neat_logger.py`** in the `neat_logger` package; you can copy **`utils/`** into another repository if the parent of `utils` is on `sys.path`.

---

<h2 id="document-outline" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">Document outline</h2>

1. [Purpose and scope](#1-purpose-and-scope) — what the module is; portability goal.
    1.1 [Logging philosophy (flow, debugging, density)](#11-logging-philosophy-flow-debugging-density) — when and how much to log.
2. [Package layout](#2-package-layout) — files and the `logger` re-export.
3. [Making imports work](#3-making-imports-work) — `sys.path` and `utils` name collisions.
4. [Import styles](#4-import-styles) — recommended and direct imports.
    4.1 [Recommended `from … import logger`](#41-recommended-from--import-logger) — stable public surface.
    4.2 [Direct symbols and module alias](#42-direct-symbols-and-module-alias) — explicit API.
5. [API reference](#5-api-reference) — functions, streams, `Heartbeat`, parameters.
    5.1 [Timestamp and stream behavior](#51-timestamp-and-stream-behavior) — prefix and TTY.
    5.2 [Basic log lines](#52-basic-log-lines) — `info` / `success` / `warning` / `error`.
    5.3 [Step highlight](#53-step-highlight) — `step`.
    5.4 [Phase boundaries](#54-phase-boundaries) — `phase_start` / `phase_end`.
    5.5 [Operation boundaries](#55-operation-boundaries) — `operation_start` / `operation_end`.
    5.6 [`Heartbeat`](#56-heartbeat) — context manager and threading.
    5.7 [Optional `neat_logger_fallback_config.yaml`](#57-optional-neat_logger_fallback_configyaml) — heartbeat + optional file mirror + env overrides.
6. [Color constants](#6-color-constants) — optional ANSI snippets.
7. [Limitations and practices](#7-limitations-and-practices) — not stdlib `logging`, tests, signals.
8. [Minimal example](#8-minimal-example) — end-to-end script.
9. [Files to copy](#9-files-to-copy) — minimum reuse bundle.
10. [Self-check (authoring)](#10-self-check-authoring) — merge checklist for this doc.

---

<h2 id="1-purpose-and-scope" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">1. Purpose and scope</h2>

| Aspect | Detail |
| --- | --- |
| **Goal** | Readable terminal logs without configuring `logging.handlers`. |
| **Dependencies** | Mostly stdlib (`sys`, `time`, …); optional PyYAML loads **`neat_logger_fallback_config.yaml`** (or legacy **`neat_logger_config.yaml`**); legacy JSON config still supported. |
| **Output** | Prints with **`flush=True`**; **`error`** writes to **stderr**; other helpers to **stdout**. |
| **Reuse** | Copy **`utils/neat_logger/`** (and optionally all of **`utils/`**) into another project; ensure imports resolve (see [section 3](#3-making-imports-work)). |

<h3 id="11-logging-philosophy-flow-debugging-density" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">1.1 Logging philosophy (flow, debugging, density)</h3>

Use **`neat_logger`** so a **log file or terminal scroll** reads like a **story**: ordered milestones, **decision points**, **inputs that matter** (paths, sizes, ids — trimmed if huge), and **outcomes**. Someone debugging a failure should see **where** the run was and **what** happened last without turning logging back on.

- **Enough signal:** At **every important transition** (start/end of a phase, branch taken, external call, batch progress), emit **one** informative line (`info`, `step`, or phase helpers). On errors, log **context** before **`error`** returns or raises.
- **Not a novel:** Avoid repeating the same line in a tight loop; summarize counts or use **`Heartbeat`** for **long-running** work so silence does not look like a hang.
- **Heartbeats:** Any stretch that can exceed tens of seconds without other output should use **`Heartbeat`** with the **default interval** from **`neat_logger_fallback_config.yaml`** ([section 5.7](#57-optional-neat_logger_fallback_configyaml)), or pass an explicit `interval_sec`.
- **Debuggability:** Prefer messages that would still make sense in a **shared** excerpt (repository-relative paths, canonical identifiers).

---

<h2 id="2-package-layout" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">2. Package layout</h2>

Typical tree after copy:

```text
utils/
  __init__.py                 # optional; marks ``utils`` as a package
  neat_logger/
    __init__.py               # re-exports implementation as `logger`
    neat_logger.py            # implementation module (functions + Heartbeat)
    neat_logger_fallback_config.yaml  # optional: defaults + heartbeat + stdout/file routing
    HOWTO_USE_NEAT_LOGGER.md
```

The package **`__init__.py`** binds the implementation module to the name **`logger`** so callers use **`from utils.neat_logger import logger`** and then **`logger.info(...)`**. That symbol is the **`neat_logger.py`** module object — **not** an instance of **`logging.Logger`**.

---

<h2 id="3-making-imports-work" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">3. Making imports work</h2>

The directory that **contains** the **`utils`** folder must be on **`sys.path`** (commonly the project root when you run `python -m myapp` or `python script.py` from that root).

**Prepend the root once** (depth of `parents[…]` depends on your file layout):

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # adjust to your entrypoint
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

**Name collision:** a PyPI distribution named **`utils`** can shadow a local package. If that happens, rename your tree (e.g. `myproj_utils/`) and update import paths.

---

<h2 id="4-import-styles" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">4. Import styles</h2>

<h3 id="41-recommended-from--import-logger" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">4.1 Recommended `from … import logger`</h3>

```python
from utils.neat_logger import logger

logger.info("hello")
logger.error("something went wrong")
```

<h3 id="42-direct-symbols-and-module-alias" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">4.2 Direct symbols and module alias</h3>

```python
from utils.neat_logger.neat_logger import info, error, Heartbeat, step
```

Or import the implementation module explicitly:

```python
from utils.neat_logger import neat_logger as nl

nl.info("hello")
with nl.Heartbeat("training epoch", interval_sec=30):
    train()
```

<h3 id="43-scoped-instance-factory" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">4.3 Role loggers (`NeatLoggerFactory`)</h3>

Use a **shared role logger** (class-oriented ``NeatLogger`` instances), not ad-hoc ``create`` per script:

| Role | Factory | Log file | Who |
| --- | --- | --- | --- |
| **ApiNeatLogger** | `NeatLoggerFactory.api()` | `logs/api.log` | `apps/api` — ``from utils.neat_logger import logger`` delegates here |
| **OpsRunTestsLogger** | `NeatLoggerFactory.ops_run_tests(component)` | `logs/ops/run_tests_only.log` | `resall`, `all-test` runner, other **test-only** ops rituals |
| **OpsRunAllLogger** | `NeatLoggerFactory.ops_run_all(component)` | `logs/ops/run_all.log` | `run_all.py` start/stop/restart/e2e dispatch |

```python
from utils.neat_logger import NeatLoggerFactory

log = NeatLoggerFactory.ops_run_tests("RESALL_RUNNER")
log.info("phase milestone")  # [OPS][RESALL_RUNNER] … → run_tests_only.log
with log.heartbeat("2 of 16 phases completed; running: unittest discover"):
    run_child()
```

**Not migrated yet:** most `ops/*.py` still use ``print``; API modules still use module ``logger`` (same sink as ``api()``). See **`cursor_gen/refactor_plans/wip/REFACTOR_NEAT_LOGGER_INSTANCE_OPS_TESTS.md`**.

---

<h2 id="5-api-reference" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">5. API reference</h2>

All callables below live on **`neat_logger.py`**, whether imported as **`logger`** or **`neat_logger`**.

<h3 id="51-timestamp-and-stream-behavior" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">5.1 Timestamp and stream behavior</h3>

Each line starts with a **local** timestamp (milliseconds), **timezone** abbreviation from **`time.tzname`** (fallback **`UTC`**), and a **colored** level label (ANSI). Colors assume a capable terminal.

| Kind | Stream | Typical use |
| --- | --- | --- |
| `info`, `success`, `warning`, `step`, phase/operation helpers | stdout | Normal progress |
| `error` | stderr | Failures |

<h3 id="52-basic-log-lines" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">5.2 Basic log lines</h3>

| Function | Level shown | Role |
| --- | --- | --- |
| `info(msg)` | INFO | General information |
| `success(msg)` | SUCCESS | Positive outcome |
| `warning(msg)` | WARNING | Non-fatal issues |
| `error(msg)` | ERROR | Errors (**stderr**) |

<h3 id="53-step-highlight" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">5.3 Step highlight</h3>

**`step(msg)`** prints a highlighted line (arrow + colored message). Use for coarse milestones inside a script.

<h3 id="54-phase-boundaries" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">5.4 Phase boundaries</h3>

```python
phase_start(phase_num=1, total=3, name="Fetch dependencies")
# ... work ...
phase_end(phase_num=1, total=3, name="Fetch dependencies", duration_sec=42)
```

**`duration_sec`** displays as seconds, or **`XmYs`** when ≥ 60.

<h3 id="55-operation-boundaries" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">5.5 Operation boundaries</h3>

```python
operation_start(operation="Deploy", scope="api", env="staging", region="us-east-1")
# ... work ...
operation_end(
    operation="Deploy",
    scope="api",
    env="staging",
    region="us-east-1",
    duration_sec=120,
    ok=True,
)
```

Use **`ok=False`** for failure; the closing line uses the **ERROR**-style prefix when appropriate.

<h3 id="56-heartbeat" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">5.6 `Heartbeat`</h3>

Wrap blocking work so the terminal stays alive on an interval:

```python
from utils.neat_logger import logger

with logger.Heartbeat("compress archive", soft_wall_sec=300):
    run_compression()
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| `message` | required | Short label on each heartbeat line |
| `interval_sec` | from **`neat_logger_fallback_config.yaml`** (falls back to **`20.0`**) | Seconds between lines; omit to use config; explicit values clamped ≥ **`1`** |
| `soft_wall_sec` | `None` | After this elapsed time, emit **one** `warning` (does not stop work) |
| `announce_complete` | `True` | On exit, log success or failure with elapsed time |

Heartbeat lines prefix the tag **`[HEARTBEAT]`** in **purple** (ANSI violet) so they scan distinctly from normal **`INFO`** text.

**Threading:** a **daemon** thread fires on the interval; on context exit the thread is stopped and joined briefly. Exceptions in the `with` body propagate; with **`announce_complete`**, failures call **`error`**.

<h3 id="57-optional-neat_logger_fallback_configyaml" style="color:#00695c;font-size:1.05em;font-weight:600;margin-top:0.85em">5.7 Optional `neat_logger_fallback_config.yaml`</h3>

Place **`neat_logger_fallback_config.yaml`** next to **`neat_logger.py`**. If missing or invalid, the module tries legacy **`neat_logger_config.yaml`**, then legacy **`neat_logger_config.json`**, then built-in defaults.

**Path semantics (`log_root`):** Under **portuguese-learn**, **`log_root`** is **repository-root-relative**: the implementation resolves **`(REPO_ROOT / log_root)`** when **`REPO_ROOT`** is set, otherwise **`get_repo_root()`**-equivalent intrinsic layout from **`utils/neat_logger/`** (three parents up). Absolute paths expand and resolve normally. **`log_root` is created if missing** when writing the file sink.

| Env (optional) | Effect |
| --- | --- |
| **`NEAT_LOGGER_LOG_ROOT`** | Overrides YAML **`log_root`** (same semantics: repo-relative unless absolute). |
| **`NEAT_LOGGER_LOG_OUTPUT`** | **`stdout`** · **`file`** · **`both`** — overrides **`log_output`**. |
| **`NEAT_LOGGER_LOG_FILE_NAME`** | Overrides **`log_file_name`**. |
| **`NEAT_LOGGER_HEARTBEAT_INTERVAL_SEC`** | Overrides **`heartbeat_interval_sec`** (invalid values ignored). |

**API launcher:** **`apps/api/run_api.py`** calls **`require_repo_root()`** so **`REPO_ROOT`** is set for predictable paths (see **`app/repo_root.py`**). **`ops/local/run_backend.py`** seeds **`REPO_ROOT`** when unset. Tests use **`tests/conftest.py`** to default **`REPO_ROOT`**.

| Key | Type | Default (in-repo fallback YAML) | Meaning |
| --- | --- | --- | --- |
| `heartbeat_interval_sec` | number | **`20.0`** | Default **`Heartbeat`** interval when **`interval_sec`** omitted |
| `log_output` | string | **`both`** | **`stdout`** · **`file`** · **`both`** |
| `log_root` | string | **`logs`** | Under repo root unless absolute |
| `log_file_name` | string | **`api.log`** | Plain-text log under **`log_root`** (ANSI stripped for file) |

Example (this repo):

```yaml
log_root: logs
log_output: both
log_file_name: api.log
heartbeat_interval_sec: 20.0
```

Use **`NEAT_LOGGER_LOG_OUTPUT=stdout`** in tests to skip writing **`api.log`**. Call **`reload_config()`** after changing the YAML or env overrides in long-lived processes.

---

<h2 id="6-color-constants" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">6. Color constants</h2>

Module-level ANSI fragments: **`RED`**, **`GREEN`**, **`YELLOW`**, **`BLUE`**, **`VIOLET`**, **`NC`** (reset). Reuse in custom **`print`** calls if you want consistent styling. Behavior on legacy Windows consoles varies; most modern terminals and CI runners accept ANSI.

---

<h2 id="7-limitations-and-practices" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">7. Limitations and practices</h2>

1. **Not `logging`** — no handlers, rotation, or logger hierarchy; intentional minimal surface.
2. **ANSI on console** — file mirror writes **plain** prefixes (ANSI stripped).
3. **Heartbeat + signals** — daemon threads do not replace normal interrupt semantics on the main thread.
4. **Testing** — capture **stdout**/**stderr** or patch module functions when asserting on output.

---

<h2 id="8-minimal-example" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">8. Minimal example</h2>

```python
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.neat_logger import logger

def main() -> None:
    logger.step("Example job")
    logger.info("Configuration loaded")
    with logger.Heartbeat("simulated work", interval_sec=2, soft_wall_sec=5):
        time.sleep(6)
    logger.success("Done")

if __name__ == "__main__":
    main()
```

---

<h2 id="9-files-to-copy" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">9. Files to copy</h2>

Minimum for reuse:

- `utils/neat_logger/neat_logger.py`
- `utils/neat_logger/__init__.py`

Include **`neat_logger_fallback_config.yaml`** when you want defaults + optional file routing (recommended for this repo). Include **`HOWTO_USE_NEAT_LOGGER.md`** beside the code when copying **`utils/neat_logger/`**. An empty **`utils/__init__.py`** is enough for many layouts so **`utils`** is a normal package.

---

<h2 id="10-self-check-authoring" style="color:#1565c0;font-size:1.22em;font-weight:650;border-left:4px solid #42a5f5;padding-left:10px;margin-top:1.1em">10. Self-check (authoring)</h2>

- [ ] **Outline + numbering:** Document outline is first after title; body sections numbered `1.` … `10.` with matching **`id`** anchors.
- [ ] **Three levels:** One **`h1`**, major sections **`h2`**, subsections **`h3`** (palette from project **mrkd-markdown-authoring.mdc** rule).
- [ ] **Outline sub-rows:** `4.1` / `5.1` … as **indented plain lines** under item **4.** / **5.** (no nested Markdown ordered list).
- [ ] **Code fences:** Language tags **`text`**, **`python`**, **`bash`** as appropriate.
- [ ] **Tables:** Used where they compress reference material (streams, API tables).
- [ ] **Portable wording:** No dependency on a specific application repo beyond `utils/` layout.
