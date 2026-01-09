#!/usr/bin/env python3
"""
Notification System Test Script
===============================

Tests all notification types to verify Telegram integration.
Run this to validate your notification setup.

Usage:
    python scripts/test_notifications.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime, timezone
from src.services.notifier import get_notifier
from src.core.enums import ExitReason
from src.core.models import Position
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def test_trade_opened():
    """Test trade opened notification."""
    console.print("\n[bold cyan]Testing: Trade Opened Notification[/bold cyan]")
    
    notifier = get_notifier()
    if not notifier:
        console.print("[yellow]⚠️  Telegram not configured - skipping[/yellow]")
        return False
    
    success = notifier.send_trade_opened(
        symbol="BTC/USDC",
        quantity=0.001,
        entry_price=45000.00,
        trade_id=12345,
    )
    
    if success:
        console.print("[green]✅ Trade opened notification sent successfully[/green]")
    else:
        console.print("[red]❌ Failed to send trade opened notification[/red]")
    
    return success


def test_trade_closed():
    """Test trade closed notification."""
    console.print("\n[bold cyan]Testing: Trade Closed Notification[/bold cyan]")
    
    notifier = get_notifier()
    if not notifier:
        console.print("[yellow]⚠️  Telegram not configured - skipping[/yellow]")
        return False
    
    # Test profitable trade
    success1 = notifier.send_trade_closed(
        symbol="ETH/USDC",
        quantity=0.1,
        entry_price=2500.00,
        exit_price=2600.00,
        pnl_percent=0.04,  # +4%
        reason=ExitReason.VIRTUAL_TP.value,
        trade_id=12346,
    )
    
    # Test losing trade
    success2 = notifier.send_trade_closed(
        symbol="SOL/USDC",
        quantity=1.0,
        entry_price=100.00,
        exit_price=98.00,
        pnl_percent=-0.02,  # -2%
        reason=ExitReason.VIRTUAL_SL.value,
        trade_id=12347,
    )
    
    # Test unknown exit (external close)
    success3 = notifier.send_trade_closed(
        symbol="BTC/USDC",
        quantity=0.001,
        entry_price=45000.00,
        exit_price=None,
        pnl_percent=None,
        reason=ExitReason.EXTERNAL_CLOSE.value,
        trade_id=12348,
    )
    
    if success1 and success2 and success3:
        console.print("[green]✅ All trade closed notifications sent successfully[/green]")
        return True
    else:
        console.print("[red]❌ Some trade closed notifications failed[/red]")
        return False


def test_catastrophe_stop():
    """Test catastrophe stop notification."""
    console.print("\n[bold cyan]Testing: Catastrophe Stop Notification[/bold cyan]")
    
    notifier = get_notifier()
    if not notifier:
        console.print("[yellow]⚠️  Telegram not configured - skipping[/yellow]")
        return False
    
    success = notifier.send_catastrophe_stop(
        symbol="BTC/USDC",
        entry_price=45000.00,
        exit_price=40500.00,  # -10% catastrophe stop
        pnl_percent=-0.10,
        trade_id=12349,
    )
    
    if success:
        console.print("[green]✅ Catastrophe stop notification sent successfully[/green]")
    else:
        console.print("[red]❌ Failed to send catastrophe stop notification[/red]")
    
    return success


def test_external_close():
    """Test external close notification."""
    console.print("\n[bold cyan]Testing: External Close Notification[/bold cyan]")
    
    notifier = get_notifier()
    if not notifier:
        console.print("[yellow]⚠️  Telegram not configured - skipping[/yellow]")
        return False
    
    success = notifier.send_external_close(
        symbol="ETH/USDC",
        quantity=0.1,
        entry_price=2500.00,
        trade_id=12350,
    )
    
    if success:
        console.print("[green]✅ External close notification sent successfully[/green]")
    else:
        console.print("[red]❌ Failed to send external close notification[/red]")
    
    return success


def test_system_failure():
    """Test system failure notification."""
    console.print("\n[bold cyan]Testing: System Failure Notification[/bold cyan]")
    
    notifier = get_notifier()
    if not notifier:
        console.print("[yellow]⚠️  Telegram not configured - skipping[/yellow]")
        return False
    
    success = notifier.send_system_failure(
        component="Database Connection",
        error="Connection timeout after 30 seconds. Database may be unreachable.",
    )
    
    if success:
        console.print("[green]✅ System failure notification sent successfully[/green]")
    else:
        console.print("[red]❌ Failed to send system failure notification[/red]")
    
    return success


def test_exchange_error():
    """Test exchange error notification."""
    console.print("\n[bold cyan]Testing: Exchange Error Notification[/bold cyan]")
    
    notifier = get_notifier()
    if not notifier:
        console.print("[yellow]⚠️  Telegram not configured - skipping[/yellow]")
        return False
    
    # Test rate limit error
    success1 = notifier.send_exchange_error(
        operation="get_balance",
        error="Rate limit exceeded: Too many requests. Please wait 60 seconds.",
    )
    
    # Test network error
    success2 = notifier.send_exchange_error(
        operation="market_buy",
        error="Network error: Connection timeout. Unable to reach Binance API.",
    )
    
    # Test authentication error
    success3 = notifier.send_exchange_error(
        operation="get_balance",
        error="Authentication failed: Invalid API key or secret.",
    )
    
    if success1 and success2 and success3:
        console.print("[green]✅ All exchange error notifications sent successfully[/green]")
        return True
    else:
        console.print("[red]❌ Some exchange error notifications failed[/red]")
        return False


def test_generic_message():
    """Test generic message notification."""
    console.print("\n[bold cyan]Testing: Generic Message Notification[/bold cyan]")
    
    notifier = get_notifier()
    if not notifier:
        console.print("[yellow]⚠️  Telegram not configured - skipping[/yellow]")
        return False
    
    # Test different priority levels
    success1 = notifier.send("This is a CRITICAL message", priority="CRITICAL")
    success2 = notifier.send("This is a HIGH priority message", priority="HIGH")
    success3 = notifier.send("This is an INFO message", priority="INFO")
    
    if success1 and success2 and success3:
        console.print("[green]✅ All generic message notifications sent successfully[/green]")
        return True
    else:
        console.print("[red]❌ Some generic message notifications failed[/red]")
        return False


def check_configuration():
    """Check if Telegram is configured."""
    from src.config import get_settings
    
    settings = get_settings()
    has_token = bool(settings.telegram_bot_token)
    has_chat_id = bool(settings.telegram_chat_id)
    
    table = Table(title="Telegram Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Status", style="green" if (has_token and has_chat_id) else "red")
    
    table.add_row("Bot Token", "✅ Configured" if has_token else "❌ Missing")
    table.add_row("Chat ID", "✅ Configured" if has_chat_id else "❌ Missing")
    
    console.print(table)
    
    if not (has_token and has_chat_id):
        console.print("\n[yellow]⚠️  Telegram notifications are not configured.[/yellow]")
        console.print("[yellow]Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in your .env file.[/yellow]")
        console.print("[yellow]Notifications will be skipped during tests.[/yellow]\n")
        return False
    
    return True


def main():
    """Run all notification tests."""
    console.print(Panel.fit(
        "[bold green]FusionBot Notification System Test[/bold green]\n"
        "This script tests all notification types.\n"
        "Check your Telegram chat for messages.",
        title="Notification Test Suite"
    ))
    
    # Check configuration
    is_configured = check_configuration()
    
    if not is_configured:
        console.print("\n[yellow]Continuing with tests anyway (will show skipped messages)...[/yellow]")
    
    # Run all tests
    results = {
        "Trade Opened": test_trade_opened(),
        "Trade Closed": test_trade_closed(),
        "Catastrophe Stop": test_catastrophe_stop(),
        "External Close": test_external_close(),
        "System Failure": test_system_failure(),
        "Exchange Error": test_exchange_error(),
        "Generic Message": test_generic_message(),
    }
    
    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Test Summary[/bold]")
    console.print("=" * 60)
    
    summary_table = Table()
    summary_table.add_column("Test", style="cyan")
    summary_table.add_column("Result", style="green")
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED" if is_configured else "⏭️  SKIPPED"
        summary_table.add_row(test_name, status)
    
    console.print(summary_table)
    
    # Final status
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    if not is_configured:
        console.print(f"\n[yellow]⚠️  {total} tests skipped (Telegram not configured)[/yellow]")
        console.print("[yellow]Configure Telegram to test notifications.[/yellow]")
    elif passed == total:
        console.print(f"\n[bold green]✅ All {total} tests passed![/bold green]")
        console.print("[green]Check your Telegram chat to verify message formatting.[/green]")
    else:
        console.print(f"\n[bold red]❌ {total - passed} of {total} tests failed[/bold red]")
        console.print("[red]Check the error messages above for details.[/red]")
    
    console.print("\n")


if __name__ == "__main__":
    main()
