# Sential CLI – Technical Specification (v0.1)

## 1. Core Assumptions & Constraints

- **Execution Root:** The CLI is always run from the root of the target repository.

- **Git Requirement:** The target folder MUST be a Git repository. We rely on `.git/index` for performance. If `git status` fails, the tool exits.

- **Single Language Focus:** The user must specify (via flag or menu) **one** primary language to target (e.g., Python). We do not support "everything at once" in a single pass.

- **Pragmatic Ignore:** We trust the user's `.gitignore`. If they ignored it, we don't see it.

## 2. The Execution Pipeline (The Logic Flow)

This is the exact sequence of events when the user runs `sential bridge`.

### Step 1: The Raw Inventory (Git Sieve)

**Goal:** Get a fast, clean list of potential files.

- **Action:** Run `git ls-files --cached --others --exclude-standard`.

- **Why:** Instantly gives us all tracked files + new files, while automatically removing `node_modules`, `venv`, and other `.gitignore` junk.

- **Output:** A list of 10,000+ file paths.

### Step 2: Module Discovery (The Radar)

**Goal:** Identify which folders are "Modules" (groups of features) vs just random subdirectories.

- **Input:** The list from Step 1 + The User's Selected Language (e.g., "Python").

- **Heuristic:**

  - **Manifest Check:** Does the folder contain a known anchor? (Python: `requirements.txt`, `pyproject.toml`; JS: `package.json`, etc.)
  - **Structure Check:** (Fallback) Does the folder contain >3 files with the target extension (`.py)`?

- **Output:** A list of "Candidate Roots" (e.g., `["backend/api", "backend/worker"]`).

### Step 3: User Scoping (The Interaction)

**Goal:** Filter the noise. Monorepos have too many modules; we only want the relevant ones.

- **Action:** Present the list from Step 2 to the user.

- **UI:** "We found these modules. Which ones are you working on?" (Checkbox selection).

- **Output:** A list of Selected Scopes (e.g., `["backend/api"]`).

### Step 4: The Refined Inventory (Language Sieve)

**Goal:** Prepare the final file list for analysis.

- **Action:**

  1. Take the Raw Inventory (from Step 1).
  2. **Filter 1:** Keep only files that start with a Selected Scope path.
  3. **Filter 2:** Keep only files matching the Target Language Extensions (e.g., `.py`).

- **Result:** We discard `logo.png`, `deploy.sh`, `styles.css`. We keep `main.py`.

- **Output:** The **Final File List** (e.g., 50 specific python files).

### Step 5: The Payload (The Bridge)

**Goal:** Send data to the Brain.

- **Action:**

  1. Generate a JSON map of the **Final File List**.
  2. (Future) Run `ctags` to extract function signatures.
  3. Send to Sential Backend API.

## 3. Heuristic Configuration (The "Brain")

We define "Modules" based strictly on this table.

| Language       | Manifest Anchors (Strong Signal)                  | Extensions (Source Code)      |
| -------------- | ------------------------------------------------- | ----------------------------- |
| **Python**     | `requirements.txt`, `pyproject.toml`, `setup.py ` | `.py,` `.pyi `                |
| **JavaScript** | `package.json`, `deno.json`, `tsconfig.json`      | `.js`, `.ts`, `.jsx`, `.tsx ` |
| **Go**         | `go.mod`, `main.go`                               | `.go `                        |
| **Java**       | `pom.xml`, `build.gradle`                         | `.java `                      |
| **C#**         | `_.csproj`, `_.sln `                              | `.cs`                         |

## 4. Project Roadmap (Checklist)

- [x] **Phase 1: The Scanner (Implemented)**

  - Can list files via Git.
  - Can detect modules based on Manifests.

- [ ] **Phase 2: The Selector (In Progress)**

  - Interactive menu to pick languages.
  - Interactive menu to pick scopes.

- [ ] **Phase 3: The Filter (Todo)**

  - Implement "Refined Inventory" logic (removing non-language files).

- [ ] **Phase 4: The Connector (Todo)**
  - POST request to Backend API.
