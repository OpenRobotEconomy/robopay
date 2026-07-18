"""robopay command-line interface (Phase 0 skeleton).

The onboarding commands (wallet / fund / init) are a v1 feature. This stub
establishes the `robopay` entry point and the command surface; implementations
land in later phases (typer + rich + qrcode).
"""
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="robopay",
                                     description="Open Robot Economy - robopay CLI")
    parser.add_argument("--version", action="version", version="robopay 0.0.1")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("wallet", help="create/manage a self-custody wallet")
    sub.add_parser("fund", help="fund a wallet (testnet faucet / mainnet watcher)")
    sub.add_parser("init", help="set up a Circle-backed wallet (wizard)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return
    print(f"[robopay] '{args.command}' is planned for v1 and not implemented yet.")


if __name__ == "__main__":
    main()
