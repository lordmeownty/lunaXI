import os, sys, tempfile
os.environ.update({"FOUNDRY_ENDPOINT": "", "FOUNDRY_API_KEY": "", "AUTH_MODE": "demo", "ORCHESTRATOR": "builtin",
                   "LUNA_STATE_DIR": tempfile.mkdtemp()})
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
