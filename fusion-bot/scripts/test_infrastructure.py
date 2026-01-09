#!/usr/bin/env python3
"""
Infrastructure Test Script for FusionBot
=========================================

Tests RSS fetching, market data, and database connectivity.
Run this to validate your setup before starting the bot.

Usage:
    python scripts/test_infrastructure.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()


def test_rss_feeds():
    """Test RSS feed fetching."""
    console.print("\n[bold blue]═══ Testing RSS Feeds ═══[/bold blue]\n")
    
    from src.infrastructure.clients.rss_client import RSSClient
    from src.config.constants import RSS_FEEDS
    
    client = RSSClient(timeout=15, cache_seconds=0)  # No cache for testing
    
    # Test each feed individually
    results = []
    for source, url in RSS_FEEDS.items():
        try:
            console.print(f"  Fetching [cyan]{source}[/cyan]...", end=" ")
            items = client.fetch_crypto_news({source: url})
            results.append((source, len(items), "✅"))
            console.print(f"[green]✅ {len(items)} items[/green]")
        except Exception as e:
            results.append((source, 0, f"❌ {str(e)[:50]}"))
            console.print(f"[red]❌ {str(e)[:50]}[/red]")
    
    # Show sample headlines
    console.print("\n[bold]Sample Headlines:[/bold]")
    all_news = client.fetch_crypto_news()
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Source", style="cyan", width=15)
    table.add_column("Title", width=60)
    table.add_column("Symbol", style="green", width=12)
    table.add_column("Age", style="yellow", width=10)
    
    for item in all_news[:10]:
        age = ""
        if item.published_at:
            age_mins = (datetime.now(item.published_at.tzinfo) - item.published_at).total_seconds() / 60
            if age_mins < 60:
                age = f"{int(age_mins)}m ago"
            else:
                age = f"{int(age_mins/60)}h ago"
        
        table.add_row(
            item.source,
            item.title[:58] + "..." if len(item.title) > 58 else item.title,
            item.detected_symbol or "-",
            age,
        )
    
    console.print(table)
    
    return all(r[2] == "✅" for r in results)


def test_market_data():
    """Test market data fetching from Binance."""
    console.print("\n[bold blue]═══ Testing Market Data (Binance) ═══[/bold blue]\n")
    
    from src.infrastructure.exchange.paper import PaperExchange
    
    # Use paper exchange which fetches real market data
    exchange = PaperExchange()
    
    symbols = ["BTC/USDC", "ETH/USDC", "SOL/USDC"]
    
    # Test tickers
    console.print("[bold]Current Prices:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="cyan")
    table.add_column("Bid", justify="right")
    table.add_column("Ask", justify="right")
    table.add_column("Last", justify="right", style="green")
    table.add_column("Volume (24h)", justify="right")
    
    for symbol in symbols:
        try:
            ticker = exchange.get_ticker(symbol)
            table.add_row(
                symbol,
                f"${ticker.bid:,.2f}",
                f"${ticker.ask:,.2f}",
                f"${ticker.last:,.2f}",
                f"${ticker.volume:,.0f}",
            )
        except Exception as e:
            console.print(f"[red]Failed to get {symbol}: {e}[/red]")
    
    console.print(table)
    
    # Test OHLCV
    console.print("\n[bold]OHLCV Data (BTC/USDC 4h, last 5 candles):[/bold]")
    try:
        candles = exchange.get_ohlcv("BTC/USDC", "4h", 5)
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Time", style="cyan")
        table.add_column("Open", justify="right")
        table.add_column("High", justify="right", style="green")
        table.add_column("Low", justify="right", style="red")
        table.add_column("Close", justify="right")
        table.add_column("Volume", justify="right")
        
        for c in candles:
            table.add_row(
                c.timestamp.strftime("%Y-%m-%d %H:%M"),
                f"${c.open:,.2f}",
                f"${c.high:,.2f}",
                f"${c.low:,.2f}",
                f"${c.close:,.2f}",
                f"{c.volume:,.2f}",
            )
        
        console.print(table)
        return True
    except Exception as e:
        console.print(f"[red]Failed to get OHLCV: {e}[/red]")
        return False


def test_paper_trading():
    """Test paper trading simulation."""
    console.print("\n[bold blue]═══ Testing Paper Trading ═══[/bold blue]\n")
    
    from src.infrastructure.exchange.paper import PaperExchange
    
    exchange = PaperExchange(initial_balance=10000)
    
    console.print(f"Initial balance: [green]${exchange.get_balance('USDC').total:,.2f}[/green]")
    
    # Simulate a buy
    console.print("\nSimulating BTC buy...")
    result = exchange.market_buy("BTC/USDC", 0.01)
    console.print(f"  Order ID: {result.order_id}")
    console.print(f"  Fill price: ${result.price:,.2f}")
    console.print(f"  Fee: ${result.fee:.4f}")
    
    # Check position
    position = exchange.get_position("BTC/USDC")
    console.print(f"  Position: {position} BTC")
    
    # Simulate stop loss
    stop_price = result.price * 0.9
    stop_result = exchange.stop_loss_order("BTC/USDC", 0.01, stop_price)
    console.print(f"\nStop loss placed at ${stop_price:,.2f}")
    
    # Check balances
    console.print(f"\nCurrent USDC: [yellow]${exchange.get_balance('USDC').total:,.2f}[/yellow]")
    console.print(f"Current BTC: [yellow]{exchange.get_balance('BTC').total:.6f}[/yellow]")
    
    # Simulate sell
    console.print("\nSimulating BTC sell...")
    sell_result = exchange.market_sell("BTC/USDC", 0.01)
    console.print(f"  Sell price: ${sell_result.price:,.2f}")
    
    # Final P&L
    pnl = exchange.get_pnl()
    console.print(f"\n[bold]Final P&L:[/bold]")
    console.print(f"  Initial: ${pnl['initial_balance']:,.2f}")
    console.print(f"  Current: ${pnl['current_equity']:,.2f}")
    
    pnl_color = "green" if pnl['pnl_amount'] >= 0 else "red"
    console.print(f"  P&L: [{pnl_color}]${pnl['pnl_amount']:+,.2f} ({pnl['pnl_percent']:+.2%})[/{pnl_color}]")
    
    return True


def test_database():
    """Test database connectivity."""
    console.print("\n[bold blue]═══ Testing Database ═══[/bold blue]\n")
    
    try:
        from src.infrastructure.database import DatabaseManager
        
        # Try to connect with a test URL (SQLite for testing)
        test_db_url = "sqlite:///data/test_fusionbot.db"
        
        console.print(f"Connecting to: [cyan]{test_db_url}[/cyan]")
        
        db = DatabaseManager(test_db_url)
        db.init_db()
        
        if db.health_check():
            console.print("[green]✅ Database connection successful[/green]")
            
            # Test a simple query
            with db.session() as session:
                from src.infrastructure.database.repositories import SystemStateRepository
                repo = SystemStateRepository(session)
                repo.set("test_key", "test_value")
                value = repo.get("test_key")
                console.print(f"  Write/Read test: [green]✅ Passed[/green]")
            
            db.close()
            return True
        else:
            console.print("[red]❌ Database health check failed[/red]")
            return False
            
    except Exception as e:
        console.print(f"[red]❌ Database error: {e}[/red]")
        console.print("[yellow]Note: For PostgreSQL, ensure the database server is running[/yellow]")
        return False


def main():
    """Run all infrastructure tests."""
    console.print(Panel.fit(
        "[bold white]FusionBot Infrastructure Tests[/bold white]\n"
        "Validating RSS feeds, market data, and database connectivity",
        title="🤖 FusionBot",
        border_style="blue",
    ))
    
    results = {}
    
    # Test RSS
    try:
        results["RSS Feeds"] = test_rss_feeds()
    except Exception as e:
        console.print(f"[red]RSS test failed: {e}[/red]")
        results["RSS Feeds"] = False
    
    # Test Market Data
    try:
        results["Market Data"] = test_market_data()
    except Exception as e:
        console.print(f"[red]Market data test failed: {e}[/red]")
        results["Market Data"] = False
    
    # Test Paper Trading
    try:
        results["Paper Trading"] = test_paper_trading()
    except Exception as e:
        console.print(f"[red]Paper trading test failed: {e}[/red]")
        results["Paper Trading"] = False
    
    # Test Database
    try:
        results["Database"] = test_database()
    except Exception as e:
        console.print(f"[red]Database test failed: {e}[/red]")
        results["Database"] = False
    
    # Summary
    console.print("\n" + "═" * 50)
    console.print("[bold]Test Summary:[/bold]\n")
    
    all_passed = True
    for test_name, passed in results.items():
        status = "[green]✅ PASS[/green]" if passed else "[red]❌ FAIL[/red]"
        console.print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    console.print("\n" + "═" * 50)
    
    if all_passed:
        console.print("\n[bold green]🎉 All tests passed! FusionBot is ready.[/bold green]\n")
    else:
        console.print("\n[bold yellow]⚠️  Some tests failed. Check the errors above.[/bold yellow]\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    # Create data directory if needed
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    sys.exit(main())

