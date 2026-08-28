# Setup Guide: Fresh Environment Installation

If you need to move this project to a new system where you cannot directly clone the repository or download the ZIP, follow these steps to instantly recreate the exact project structure in VS Code and safely install all dependencies.

## Step 1: Open an empty folder in VS Code
1. On your new system, create a brand new, empty folder (e.g., `synthetic-data-agent`).
2. Open VS Code.
3. Go to `File > Open Folder...` and select that new empty folder.

## Step 2: Auto-generate the folder structure
Once you have the empty folder open in VS Code, open the VS Code Terminal (press `` Ctrl + ` `` or go to `Terminal > New Terminal` in the top menu). 

**If you are on Windows (PowerShell):**
Copy and paste this entire block into the terminal and press Enter:
```powershell
New-Item -ItemType Directory -Force -Path "config", "generators", "schemas", "tests"; `
New-Item -ItemType File -Force -Path "api.py", "relationships.py", "validation.py", "LOGIC_EXPLANATION.md", "README.md", "SETUP_GUIDE.md"; `
New-Item -ItemType File -Force -Path "config\industry_profiles.json", "config\relationship_rules.json"; `
New-Item -ItemType File -Force -Path "generators\campaign_logs_gen.py", "generators\customer_profiles_gen.py", "generators\engagement_events_gen.py"; `
New-Item -ItemType File -Force -Path "schemas\campaign_logs.schema.json", "schemas\customer_profiles.schema.json", "schemas\engagement_events.schema.json"; `
New-Item -ItemType File -Force -Path "tests\test_referential_integrity.py"
```

**If you are on Mac/Linux (Bash):**
Copy and paste this entire block into the terminal and press Enter:
```bash
mkdir -p config generators schemas tests && \
touch api.py relationships.py validation.py LOGIC_EXPLANATION.md README.md SETUP_GUIDE.md && \
touch config/industry_profiles.json config/relationship_rules.json && \
touch generators/campaign_logs_gen.py generators/customer_profiles_gen.py generators/engagement_events_gen.py && \
touch schemas/campaign_logs.schema.json schemas/customer_profiles.schema.json schemas/engagement_events.schema.json && \
touch tests/test_referential_integrity.py
```

*You will instantly see all the empty files and folders appear in the VS Code sidebar on the left. You can now click into each file and copy-paste the actual Python/JSON code from GitHub.*

## Step 3: Set up the Virtual Environment (venv)
It is a strict Software Engineering Best Practice to use a virtual environment so your project dependencies (`faker`, `jsonschema`) don't conflict with other Python projects on your computer.

In that same VS Code terminal, run this command to create a virtual environment:
```bash
python -m venv venv
```
*(This creates a folder called `venv` in your project—do not paste any code in there, it is managed by Python automatically).*

## Step 4: Activate the Virtual Environment
Before you install any imports, you need to turn the virtual environment on:

**On Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate
```

**On Mac/Linux (Bash):**
```bash
source venv/bin/activate
```
*(You will know it worked because you will see a green `(venv)` tag appear at the start of your terminal prompt).*

## Step 5: Install the Imports
Now that your virtual environment is active, you can safely install the exact imports required for this pipeline to run:
```bash
pip install faker jsonschema
```

You are now 100% ready to run the pipeline! You can start by testing if your copy-paste was successful:
```bash
python api.py --dry-run
```
