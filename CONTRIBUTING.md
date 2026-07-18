# Contributing to robopay

Thanks for helping build open payment rails for robots.

## Dev environment
1. Install Docker Desktop + VS Code + the **Dev Containers** extension.
2. Clone this repo and open it in VS Code.
3. Run **"Reopen in Container"** - you get ROS 2 Humble preinstalled.
4. Build and test:
   ```bash
   colcon build
   colcon test && colcon test-result --verbose
   ```

## Before opening a PR
- `pre-commit run --all-files` (ruff lint + format).
- Add or update tests; pure-Python logic should be testable without ROS.
- Keep public service/action interfaces stable - changes there need discussion.

## Ground rules
- Never put a private key, mnemonic, Entity Secret, or any secret on a ROS topic. Addresses only.
- Never commit secrets. The `.gitignore` blocks the usual files - keep it that way.
