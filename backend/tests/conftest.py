"""Mock heavy dependencies before they load."""

import sys
from unittest.mock import MagicMock

# Mock heavy ML/vector-db modules before any import chain pulls them in
for mod_name in [
    "sentence_transformers",
    "chromadb",
    "chromadb.config",
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "transformers",
    "duckduckgo_search",
]:
    sys.modules[mod_name] = MagicMock()
