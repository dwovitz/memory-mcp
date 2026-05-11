import sys
from pathlib import Path

# Allow 'hooks' package to be imported in tests
sys.path.insert(0, str(Path(__file__).parent))
