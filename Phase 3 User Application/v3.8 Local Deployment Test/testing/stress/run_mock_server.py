import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from testing.shared.harness import configure_test_environment, install_test_ai


def main():
    sandbox_root = PROJECT_ROOT / "testing" / "artifacts" / "stress-runtime"
    install_test_ai()
    configure_test_environment(sandbox_root)

    from main import create_app

    app = create_app()
    host = os.getenv("CONVOEASE_HOST", "127.0.0.1")
    port = int(os.getenv("CONVOEASE_PORT", "5000"))
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
