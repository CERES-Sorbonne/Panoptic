"""Protocol constants shared by the SDK and documented in technical_docs/rust_port/PLUGIN_PROTOCOL.md."""
from __future__ import annotations

PROTOCOL_VERSION = "1.0"
SDK_NAME = "panoptic-plugin-sdk"
SDK_VERSION = "1.0.0a1"

# Largest WebSocket message either side accepts (bytes).
MAX_MESSAGE_SIZE = 64 * 1024 * 1024

# --- environment set by the backend when it spawns a plugin process -------------------------
ENV_URL = "PANOPTIC_PLUGIN_URL"                # ws://127.0.0.1:<port>/plugin
ENV_TOKEN = "PANOPTIC_PLUGIN_TOKEN"            # per-process secret
ENV_NAME = "PANOPTIC_PLUGIN_NAME"              # registered plugin id (PluginKey.id)
ENV_ENTRY = "PANOPTIC_PLUGIN_ENTRY"            # optional "module:Class" or a plugin folder path
ENV_PROJECT_ID = "PANOPTIC_PROJECT_ID"
ENV_PROJECT_PATH = "PANOPTIC_PROJECT_PATH"     # project folder holding data.db / media.db / project.db
ENV_DATA_DIR = "PANOPTIC_PLUGIN_DATA_DIR"      # <project>/plugin_data/<slug>
ENV_SOURCE_PATH = "PANOPTIC_PLUGIN_SOURCE"     # where the plugin was installed from (informative)
ENV_PROTOCOL = "PANOPTIC_PROTOCOL_VERSION"
ENV_LOG_LEVEL = "PANOPTIC_LOG_LEVEL"
ENV_PARENT_PID = "PANOPTIC_PARENT_PID"
ENV_RECONNECT_TIMEOUT = "PANOPTIC_RECONNECT_TIMEOUT"   # seconds, default 15

# Entry point group a plugin distribution declares in its pyproject.toml.
ENTRY_POINT_GROUP = "panoptic.plugins"

# --- JSON-RPC error codes ----------------------------------------------------------------------
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

UNAUTHORIZED = -32000           # bad token / hello missing
NOT_READY = -32001              # project.open not done yet / plugin stopping
TIMEOUT = -32002
CANCELLED = -32003              # request cancelled with $/cancel
CONNECTION_LOST = -32004        # peer went away (crash, disconnect) while the request was in flight
ACTION_NOT_FOUND = -32010
ACTION_FAILED = -32011          # the action raised: data = {type, message, traceback}
INVALID_INPUT = -32012          # ui_inputs could not be coerced to the declared types
COMMIT_REJECTED = -32020
NOT_FOUND = -32021              # unknown task id, vector type, map...
FORBIDDEN = -32022              # e.g. touching another plugin's vector type
PROTOCOL_UNSUPPORTED = -32030
PARAMS_INVALID = -32040

# Operation constants of the data DB (entity_schema.py)
OP_CREATE = 1
OP_UPDATE = 0
OP_DELETE = -1

# Hooks understood by the frontend action UI (actionStore.ts defaultActions + text_search)
KNOWN_HOOKS = ("similar", "group", "execute", "import", "export", "vector_type", "vector", "map",
               "text_search")
