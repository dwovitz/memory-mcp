import sys
from pathlib import Path

# Allow 'hooks' package imports in tests
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
