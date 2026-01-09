#!/usr/bin/env python3
"""
Check Binance Testnet Transaction History
==========================================

Quick script to investigate order history and trades.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

import ccxt
from rich.console import Console
from rich.table import Table
from rich import box

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_settings

console = Console()


def format_timestamp(ts: Optional[int]) -> str:
    """Format timestamp to readable date."""
    if not ts:
        return "N/A"
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def check_order_history(exchange: ccxt.binance, symbol: str = None, limit: int = 50):
    """Check order history."""
    console.print(f"\n[bold cyan]📋 Order History (last {limit})[/bold cyan]")
    
    try:
        # Binance requires symbol for fetch_orders
        if not symbol:
            # Check common symbols
            symbols_to_check = ["BTC/USDC", "ETH/USDC", "SOL/USDC"]
            all_orders = []
            for sym in symbols_to_check:
                try:
                    orders = exchange.fetch_orders(sym, limit=limit)
                    all_orders.extend(orders)
                except Exception:
                    continue
            orders = sorted(all_orders, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit]
        else:
            orders = exchange.fetch_orders(symbol, limit=limit)
        
        if not orders:
            console.print("[yellow]No orders found[/yellow]")
            return
        
        table = Table(box=box.ROUNDED)
        table.add_column("Order ID", style="cyan")
        table.add_column("Symbol", style="magenta")
        table.add_column("Side", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Status", style="blue")
        table.add_column("Price", style="white")
        table.add_column("Filled", style="white")
        table.add_column("Time", style="dim")
        
        for order in orders:
            status = order.get("status", "unknown")
            status_style = {
                "closed": "green",
                "filled": "green",
                "open": "yellow",
                "canceled": "red",
                "cancelled": "red",
            }.get(status, "white")
            
            table.add_row(
                str(order.get("id", "N/A")),
                order.get("symbol", "N/A"),
                order.get("side", "N/A").upper(),
                order.get("type", "N/A"),
                f"[{status_style}]{status}[/{status_style}]",
                f"{order.get('price', 0):,.2f}" if order.get("price") else "Market",
                f"{order.get('filled', 0):.6f}",
                format_timestamp(order.get("timestamp")),
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error fetching orders: {e}[/red]")


def check_trade_history(exchange: ccxt.binance, symbol: str = None, limit: int = 50):
    """Check trade history (filled orders)."""
    console.print(f"\n[bold cyan]💰 Trade History (last {limit})[/bold cyan]")
    
    try:
        # Binance requires symbol for fetch_my_trades
        if not symbol:
            # Check common symbols
            symbols_to_check = ["BTC/USDC", "ETH/USDC", "SOL/USDC"]
            all_trades = []
            for sym in symbols_to_check:
                try:
                    trades = exchange.fetch_my_trades(sym, limit=limit)
                    if trades:
                        all_trades.extend(trades)
                except Exception:
                    continue
            trades = sorted(all_trades, key=lambda x: x.get("timestamp", 0), reverse=True)[:limit] if all_trades else []
        else:
            trades = exchange.fetch_my_trades(symbol, limit=limit) or []
        
        if not trades:
            console.print("[yellow]No trades found[/yellow]")
            return
        
        table = Table(box=box.ROUNDED)
        table.add_column("Trade ID", style="cyan")
        table.add_column("Order ID", style="dim")
        table.add_column("Symbol", style="magenta")
        table.add_column("Side", style="green")
        table.add_column("Price", style="white")
        table.add_column("Amount", style="white")
        table.add_column("Cost", style="white")
        table.add_column("Fee", style="dim")
        table.add_column("Time", style="dim")
        
        for trade in trades:
            fee_info = trade.get("fee", {}) or {}
            table.add_row(
                str(trade.get("id", "N/A")),
                str(trade.get("order", "N/A")),
                trade.get("symbol", "N/A"),
                trade.get("side", "N/A").upper(),
                f"{trade.get('price', 0):,.2f}",
                f"{trade.get('amount', 0):.6f}",
                f"{trade.get('cost', 0):,.2f}",
                f"{fee_info.get('cost', 0):.6f} {fee_info.get('currency', '')}",
                format_timestamp(trade.get("timestamp")),
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error fetching trades: {e}[/red]")


def check_specific_order(exchange: ccxt.binance, order_id: str, symbol: str):
    """Check specific order details."""
    console.print(f"\n[bold cyan]🔍 Order Details: {order_id}[/bold cyan]")
    
    try:
        order = exchange.fetch_order(order_id, symbol)
        
        console.print(f"\n[bold]Order ID:[/bold] {order.get('id')}")
        console.print(f"[bold]Symbol:[/bold] {order.get('symbol')}")
        console.print(f"[bold]Side:[/bold] {order.get('side')}")
        console.print(f"[bold]Type:[/bold] {order.get('type')}")
        console.print(f"[bold]Status:[/bold] {order.get('status')}")
        console.print(f"[bold]Price:[/bold] {order.get('price', 'Market')}")
        console.print(f"[bold]Amount:[/bold] {order.get('amount')}")
        console.print(f"[bold]Filled:[/bold] {order.get('filled')}")
        console.print(f"[bold]Remaining:[/bold] {order.get('remaining')}")
        console.print(f"[bold]Average Fill Price:[/bold] {order.get('average')}")
        console.print(f"[bold]Time:[/bold] {format_timestamp(order.get('timestamp'))}")
        console.print(f"[bold]Last Update:[/bold] {format_timestamp(order.get('lastUpdateTimestamp'))}")
        
        if order.get("info"):
            console.print(f"\n[bold]Raw Info:[/bold]")
            console.print(order["info"])
        
    except Exception as e:
        console.print(f"[red]Error fetching order: {e}[/red]")


def check_open_orders(exchange: ccxt.binance, symbol: str = None):
    """Check open orders."""
    console.print(f"\n[bold cyan]📊 Open Orders[/bold cyan]")
    
    try:
        # Suppress warning for fetch_open_orders without symbol
        if not hasattr(exchange, "_suppressed_warning"):
            exchange.options["warnOnFetchOpenOrdersWithoutSymbol"] = False
            exchange._suppressed_warning = True
        
        if symbol:
            orders = exchange.fetch_open_orders(symbol)
        else:
            # Check common symbols
            symbols_to_check = ["BTC/USDC", "ETH/USDC", "SOL/USDC"]
            all_orders = []
            for sym in symbols_to_check:
                try:
                    orders = exchange.fetch_open_orders(sym)
                    if orders:
                        all_orders.extend(orders)
                except Exception:
                    continue
            orders = all_orders
        
        if not orders:
            console.print("[green]No open orders[/green]")
            return
        
        table = Table(box=box.ROUNDED)
        table.add_column("Order ID", style="cyan")
        table.add_column("Symbol", style="magenta")
        table.add_column("Side", style="green")
        table.add_column("Type", style="yellow")
        table.add_column("Price", style="white")
        table.add_column("Amount", style="white")
        table.add_column("Filled", style="white")
        table.add_column("Time", style="dim")
        
        for order in orders:
            table.add_row(
                str(order.get("id", "N/A")),
                order.get("symbol", "N/A"),
                order.get("side", "N/A").upper(),
                order.get("type", "N/A"),
                f"{order.get('price', 0):,.2f}" if order.get("price") else "Market",
                f"{order.get('amount', 0):.6f}",
                f"{order.get('filled', 0):.6f}",
                format_timestamp(order.get("timestamp")),
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error fetching open orders: {e}[/red]")


def _safe_get_balance_value(value):
    """Safely extract numeric balance value from various formats."""
    if value is None:
        return 0
    
    if isinstance(value, dict):
        return float(value.get("total", 0) or 0)
    
    if isinstance(value, (int, float)):
        return float(value)
    
    # Skip strings (likely timestamps or metadata)
    if isinstance(value, str):
        # Try to parse as float, but skip if it looks like a timestamp
        if "T" in value or "-" in value[:4]:  # ISO timestamp format
            return 0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0
    
    return 0


def check_balances(exchange: ccxt.binance):
    """Check current account balances."""
    console.print(f"\n[bold cyan]💰 Account Balances[/bold cyan]")
    
    try:
        balance = exchange.fetch_balance()
        settings = get_settings()
        
        # Get watchlist base currencies (e.g., "BTC/USDC" -> "BTC")
        watchlist_symbols = settings.watchlist_symbols
        watchlist_currencies = set()
        for symbol in watchlist_symbols:
            base = symbol.split("/")[0]
            watchlist_currencies.add(base)
        
        # Only show USDC and watchlist currencies
        currencies_to_show = ["USDC"] + sorted(watchlist_currencies)
        
        table = Table(box=box.ROUNDED)
        table.add_column("Currency", style="cyan")
        table.add_column("Free", style="green")
        table.add_column("Used", style="yellow")
        table.add_column("Total", style="white")
        
        for currency in currencies_to_show:
            if currency in balance:
                curr_bal = balance[currency]
                
                # Handle both dict structure and direct value
                if isinstance(curr_bal, dict):
                    free = float(curr_bal.get("free", 0) or 0)
                    used = float(curr_bal.get("used", 0) or 0)
                    total = float(curr_bal.get("total", 0) or 0)
                else:
                    # If it's a direct value, treat as total
                    total = _safe_get_balance_value(curr_bal)
                    free = total
                    used = 0
                
                # Always show USDC and watchlist currencies, even if 0
                table.add_row(
                    currency,
                    f"{free:.8f}".rstrip("0").rstrip("."),
                    f"{used:.8f}".rstrip("0").rstrip("."),
                    f"{total:.8f}".rstrip("0").rstrip("."),
                )
        
        console.print(table)
        
        # Also show position check for watchlist symbols
        console.print(f"\n[bold cyan]📊 Position Check (get_position)[/bold cyan]")
        position_table = Table(box=box.ROUNDED)
        position_table.add_column("Symbol", style="magenta")
        position_table.add_column("Position Size", style="white")
        position_table.add_column("Balance Check", style="dim")
        
        for symbol in watchlist_symbols:
            try:
                base = symbol.split("/")[0]
                base_balance = balance.get(base)
                total_balance = _safe_get_balance_value(base_balance)
                
                # Simulate get_position() logic
                position_size = total_balance if total_balance > 0 else None
                
                position_table.add_row(
                    symbol,
                    f"{position_size:.8f}".rstrip("0").rstrip(".") if position_size else "[red]None[/red]",
                    f"Balance: {total_balance:.8f}".rstrip("0").rstrip(".") if total_balance > 0 else "[red]0[/red]",
                )
            except Exception as e:
                position_table.add_row(symbol, "[red]Error[/red]", str(e)[:50])
        
        console.print(position_table)
        
    except Exception as e:
        console.print(f"[red]Error fetching balances: {e}[/red]")


def main():
    """Main function."""
    settings = get_settings()
    
    if not settings.binance_api_key or not settings.binance_api_secret:
        console.print("[red]Binance API keys not configured![/red]")
        console.print("Set BINANCE_API_KEY and BINANCE_API_SECRET in your .env file")
        return
    
    # Initialize exchange
    exchange_config = {
        "apiKey": settings.binance_api_key,
        "secret": settings.binance_api_secret,
        "sandbox": settings.binance_testnet,
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    }
    
    exchange = ccxt.binance(exchange_config)
    
    try:
        exchange.load_markets()
        console.print(f"[green]✓ Connected to Binance {'Testnet' if settings.binance_testnet else 'Mainnet'}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")
        return
    
    # Check specific order if provided
    import sys
    if len(sys.argv) > 1:
        order_id = sys.argv[1]
        symbol = sys.argv[2] if len(sys.argv) > 2 else "BTC/USDC"
        check_specific_order(exchange, order_id, symbol)
        return
    
    # Show all history
    check_balances(exchange)
    check_open_orders(exchange)
    check_order_history(exchange, limit=20)
    check_trade_history(exchange, limit=20)
    
    console.print("\n[bold]💡 Tips:[/bold]")
    console.print("  - Check specific order: python scripts/check_binance_history.py <order_id> <symbol>")
    console.print("  - Example: python scripts/check_binance_history.py 102023 BTC/USDC")


if __name__ == "__main__":
    main()

