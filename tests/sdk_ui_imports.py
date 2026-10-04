"""Import shim: sdk-ui/gateway is not a pip package (hyphenated dir per
roadmap 07), so tests add sdk-ui to sys.path and import the gateway package.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SDK_UI = Path(__file__).parent.parent / "sdk-ui"
if str(_SDK_UI) not in sys.path:
    sys.path.insert(0, str(_SDK_UI))

from gateway import (  # noqa: E402,F401
    SdkChatGateway,
    ClineSdkRuntime,
    FakeAgentRuntime,
    SYSTEM_PROMPT,
    TOOL_INPUT_SCHEMAS,
    TOOL_NAMES,
    execute_tool,
)