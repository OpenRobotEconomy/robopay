"""robopay command-line interface
    robopay wallet create
    robopay wallet list
    robopay balance <address>
    robopay fund <address>
"""

import time
import qrcode
import typer
from rich.console import Console
from rich.table import Table

from robopay_core.chain_client import ChainClient
from robopay_core.secrets import PassphraseUnavailable, get_passphrase, prompt_new_passphrase
from robopay_core.wallets.registry import WalletRegistry
from robopay_core.wallets.self_custody import SelfCustodyProvider

app = typer.Typer(help="robopay - open payment rails for robots", no_args_is_help=True)
wallet_app = typer.Typer(help="create and inspect robot wallets", no_args_is_help=True)
app.add_typer(wallet_app, name="wallet")

console = Console()
DEFAULT_CHAIN = "base-sepolia"


@wallet_app.command("create")
def wallet_create(
    label: str = typer.Option("robot", "--label", "-l",
                              help="a name for this wallet, e.g. 'delivery-bot-3'"),
) -> None:
    """Create a new wallet. The private key is encrypted with a passphrase."""
    try:
        passphrase = prompt_new_passphrase()
    except PassphraseUnavailable as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    provider = SelfCustodyProvider()
    address = provider.create(label=label, passphrase=passphrase)

    console.print()
    console.print("[green]wallet created[/green]")
    console.print(f"  address: [bold]{address}[/bold]")
    console.print(f"  label:   {label}")
    console.print()
    console.print("[dim]The private key is encrypted at "
                  "~/.robopay/wallets/ - keep your passphrase safe. "
                  "Without it the wallet cannot be recovered.[/dim]")
    console.print()
    console.print(f"Next: fund it with  [bold]robopay fund {address}[/bold]")


@wallet_app.command("list")
def wallet_list() -> None:
    """List the wallets stored on this machine."""
    wallets = WalletRegistry().list_wallets()
    if not wallets:
        console.print("[yellow]no wallets yet[/yellow] - "
                      "create one with [bold]robopay wallet create[/bold]")
        return

    table = Table(title="robopay wallets")
    table.add_column("label", style="cyan")
    table.add_column("address")
    for w in wallets:
        table.add_row(w.get("label") or "-", w["address"])
    console.print(table)


@app.command("balance")
def balance(
    address: str = typer.Argument(..., help="the wallet address to check"),
    chain: str = typer.Option(DEFAULT_CHAIN, "--chain", "-c"),
) -> None:
    """Show a wallet's USDC and gas balances."""
    client = ChainClient(chain)
    usdc = client.token_balance(address, "USDC")
    gas = client.native_balance(address)

    console.print()
    console.print(f"[bold]{address}[/bold]  [dim]on {chain}[/dim]")
    console.print(f"  USDC: [green]{usdc}[/green]")
    console.print(f"  ETH:  [green]{gas}[/green]  [dim](for gas)[/dim]")
    if float(gas) == 0:
        console.print()
        console.print("[yellow]no ETH - transactions will fail without gas[/yellow]")


@app.command("fund")
def fund(
    address: str = typer.Argument(..., help="the wallet address to fund"),
    chain: str = typer.Option(DEFAULT_CHAIN, "--chain", "-c"),
    watch: bool = typer.Option(True, "--watch/--no-watch",
                               help="wait and report when funds arrive"),
) -> None:
    """Show how to fund a wallet, and watch for the money arriving."""
    client = ChainClient(chain)
    testnet = "sepolia" in chain

    usdc_before = client.token_balance(address, "USDC")
    gas_before = client.native_balance(address)

    console.print()
    console.print(f"[bold]Fund this wallet[/bold]  [dim]on {chain}[/dim]")
    console.print()
    console.print(f"  [bold cyan]{address}[/bold cyan]")
    console.print()

    qr = qrcode.QRCode(border=1)
    qr.add_data(address)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    console.print()
    console.print("This wallet needs two things:")
    console.print("  [green]USDC[/green]  - what it pays with")
    console.print("  [green]ETH[/green]   - a small amount, to pay gas fees")
    console.print()
    console.print(f"  current: {usdc_before} USDC, {gas_before} ETH")
    console.print()

    if testnet:
        console.print("[bold]Testnet faucets (free):[/bold]")
        console.print("  USDC  https://faucet.circle.com  [dim](pick Base Sepolia)[/dim]")
        console.print("  ETH   https://portal.cdp.coinbase.com/products/faucet")
    else:
        console.print("[bold]Send real USDC and a little ETH to the address above.[/bold]")
        console.print("[yellow]Mainnet: this is real money. Double-check the address.[/yellow]")

    if not watch:
        return

    console.print()
    console.print("[dim]watching for funds… (Ctrl+C to stop)[/dim]")
    try:
        while True:
            time.sleep(5)
            usdc_now = client.token_balance(address, "USDC")
            gas_now = client.native_balance(address)
            if usdc_now != usdc_before:
                console.print(f"[green]✓ USDC arrived[/green] - balance now {usdc_now}")
                usdc_before = usdc_now
            if gas_now != gas_before:
                console.print(f"[green]✓ ETH arrived[/green] - balance now {gas_now}")
                gas_before = gas_now
            if float(usdc_now) > 0 and float(gas_now) > 0:
                console.print()
                console.print("[bold green]wallet is funded and ready[/bold green]")
                return
    except KeyboardInterrupt:
        console.print("\n[dim]stopped watching[/dim]")





def main() -> None:
    app()


if __name__ == "__main__":
    main()
