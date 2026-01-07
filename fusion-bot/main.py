#!/usr/bin/env python3
"""
FusionBot - AI-Powered Crypto Trading Bot
==========================================

Entry point for the FusionBot trading system.

Usage:
    # Paper trading (default, safe)
    python main.py

    # Paper trading with verbose output
    python main.py --verbose

    # Live trading (use with caution!)
    python main.py --live

    # Show status and exit
    python main.py --status

    # Force close all positions
    python main.py --close-all
"""

import argparse
import signal
import sys
import time
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table

from src.config import get_settings
from src.config.settings import Settings
from src.utils.logging import setup_logging, get_logger
from src.infrastructure.database import get_db_manager
from src.infrastructure.exchange import BinanceClient, PaperExchange
from src.strategies import FusionStrategy

console = Console()
logger = None  # Initialized after logging setup

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    if shutdown_requested:
        console.print("\n[red]Force exit![/red]")
        sys.exit(1)
    console.print("\n[yellow]Shutdown requested. Finishing current cycle...[/yellow]")
    shutdown_requested = True


def create_status_table(strategy: FusionStrategy) -> Table:
    """Create a status table for display."""
    status = strategy.get_status()
    
    table = Table(title="FusionBot Status", show_header=True)
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    table.add_row("Mode", str(status["mode"]))
    table.add_row("Cycles", str(status["cycle_count"]))
    table.add_row("Open Positions", str(status["positions"]["open_positions"]))
    table.add_row("Exchange", "✅" if status["health"]["exchange"] else "❌")
    table.add_row("Database", "✅" if status["health"]["database"] else "❌")
    table.add_row("AI (Gemini)", "✅" if status["health"]["ai"] else "⚠️ Optional")
    
    return table


def run_bot(settings: Settings, verbose: bool = False):
    """
    Run the trading bot main loop.
    
    Args:
        settings: Application settings
        verbose: Enable verbose output
    """
    global shutdown_requested
    
    console.print(Panel.fit(
        "[bold white]FusionBot[/bold white] - AI-Powered Crypto Trading\n"
        f"Mode: [yellow]{settings.trading_mode.upper()}[/yellow]\n"
        f"Watchlist: [cyan]{settings.watchlist}[/cyan]",
        title="🤖 Starting",
        border_style="blue",
    ))
    
    # Initialize database
    console.print("Initializing database...", end=" ")
    db = get_db_manager()
    db.init_db()
    console.print("[green]✓[/green]")
    
    # Initialize exchange
    console.print("Connecting to exchange...", end=" ")
    if settings.is_paper_mode:
        exchange = PaperExchange(initial_balance=10000)
        console.print("[green]✓[/green] (Paper Mode)")
    else:
        exchange = BinanceClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
            testnet=settings.binance_testnet,
        )
        mode_str = "Testnet" if settings.binance_testnet else "[red]LIVE[/red]"
        console.print(f"[green]✓[/green] ({mode_str})")
    
    # Initialize strategy
    console.print("Initializing strategy...", end=" ")
    strategy = FusionStrategy(exchange)
    console.print("[green]✓[/green]")
    
    # Health check
    console.print("Running health check...", end=" ")
    health = strategy.health_check()
    if health["overall"]:
        console.print("[green]✓[/green]")
    else:
        console.print("[yellow]⚠️ Some checks failed[/yellow]")
        if not health["exchange"]:
            console.print("  [red]• Exchange connection failed[/red]")
        if not health["database"]:
            console.print("  [red]• Database connection failed[/red]")
    
    console.print("\n[bold green]Bot started![/bold green] Press Ctrl+C to stop.\n")
    
    # Main loop
    interval = settings.main_loop_interval_seconds
    
    try:
        while not shutdown_requested:
            cycle_start = time.time()
            
            # Run strategy cycle
            results = strategy.run_cycle()
            
            if verbose:
                console.print(
                    f"[dim]Cycle {results['cycle']}:[/dim] "
                    f"Mode={results['mode']}, "
                    f"Positions={results['positions_checked']}, "
                    f"Trades={results['trades_opened']}, "
                    f"Duration={results['duration_ms']}ms"
                )
            
            # Sleep until next cycle
            elapsed = time.time() - cycle_start
            sleep_time = max(0, interval - elapsed)
            
            if sleep_time > 0 and not shutdown_requested:
                # Sleep in small increments to respond to shutdown quickly
                for _ in range(int(sleep_time)):
                    if shutdown_requested:
                        break
                    time.sleep(1)
    
    except KeyboardInterrupt:
        pass
    
    finally:
        # Graceful shutdown
        console.print("\n[yellow]Shutting down...[/yellow]")
        strategy.shutdown()
        db.close()
        console.print("[green]Goodbye![/green]")


def show_status(settings: Settings):
    """Show current bot status."""
    console.print("Fetching status...\n")
    
    try:
        # Initialize components just for status check
        db = get_db_manager()
        
        if settings.is_paper_mode:
            exchange = PaperExchange()
        else:
            exchange = BinanceClient(testnet=settings.binance_testnet)
        
        strategy = FusionStrategy(exchange)
        
        # Display status
        table = create_status_table(strategy)
        console.print(table)
        
        # Show positions
        positions = strategy.position_manager.get_open_positions()
        if positions:
            console.print("\n[bold]Open Positions:[/bold]")
            pos_table = Table()
            pos_table.add_column("ID")
            pos_table.add_column("Symbol")
            pos_table.add_column("Entry")
            pos_table.add_column("Current")
            pos_table.add_column("P&L")
            pos_table.add_column("Age")
            
            for pos in positions:
                try:
                    ticker = exchange.get_ticker(pos.symbol)
                    current = ticker.last
                    pnl = (current - pos.entry_price) / pos.entry_price
                    pnl_str = f"[{'green' if pnl > 0 else 'red'}]{pnl:+.2%}[/]"
                except:
                    current = "N/A"
                    pnl_str = "N/A"
                
                pos_table.add_row(
                    str(pos.id),
                    pos.symbol,
                    f"${pos.entry_price:,.2f}",
                    f"${current:,.2f}" if isinstance(current, float) else current,
                    pnl_str,
                    f"{pos.age_hours:.1f}h",
                )
            
            console.print(pos_table)
        else:
            console.print("\n[dim]No open positions[/dim]")
        
        db.close()
        
    except Exception as e:
        console.print(f"[red]Error fetching status: {e}[/red]")


def close_all_positions(settings: Settings):
    """Force close all positions."""
    console.print("[yellow]⚠️  This will close ALL open positions![/yellow]")
    confirm = input("Type 'CLOSE ALL' to confirm: ")
    
    if confirm != "CLOSE ALL":
        console.print("Cancelled.")
        return
    
    try:
        db = get_db_manager()
        
        if settings.is_paper_mode:
            exchange = PaperExchange()
        else:
            exchange = BinanceClient(testnet=settings.binance_testnet)
        
        strategy = FusionStrategy(exchange)
        
        closed = strategy.position_manager.force_close_all("Manual close via CLI")
        console.print(f"[green]Closed {closed} positions[/green]")
        
        db.close()
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def main():
    """Main entry point."""
    global logger
    
    parser = argparse.ArgumentParser(
        description="FusionBot - AI-Powered Crypto Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live trading (default: paper trading)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status and exit",
    )
    parser.add_argument(
        "--close-all",
        action="store_true",
        help="Force close all positions",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Override log level",
    )
    
    args = parser.parse_args()
    
    # Load settings
    settings = get_settings()
    
    # Override settings from CLI
    if args.live:
        settings.trading_mode = "live"
    if args.log_level:
        settings.log_level = args.log_level
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else settings.log_level
    setup_logging(log_level=log_level, log_path=settings.log_path)
    logger = get_logger(__name__)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Route to appropriate action
    if args.status:
        show_status(settings)
    elif args.close_all:
        close_all_positions(settings)
    else:
        # Safety check for live trading
        if settings.is_live_mode:
            console.print(Panel.fit(
                "[bold red]⚠️  LIVE TRADING MODE ⚠️[/bold red]\n\n"
                "You are about to trade with REAL MONEY.\n"
                "Make sure you understand the risks!",
                border_style="red",
            ))
            confirm = input("Type 'I UNDERSTAND' to continue: ")
            if confirm != "I UNDERSTAND":
                console.print("Cancelled.")
                return
        
        run_bot(settings, verbose=args.verbose)


if __name__ == "__main__":
    main()

