#!/usr/bin/env python3
"""
Get Telegram Chat ID
====================

Simple script to get your Telegram Chat ID.
You need your bot token first (from @BotFather).

Usage:
    python scripts/get_telegram_chat_id.py YOUR_BOT_TOKEN
"""

import sys
import requests
from rich.console import Console
from rich.panel import Panel

console = Console()


def get_chat_id(bot_token: str):
    """Get chat ID from Telegram bot updates."""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    try:
        console.print("[cyan]Fetching updates from Telegram...[/cyan]")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("ok"):
            error = data.get("description", "Unknown error")
            console.print(f"[red]❌ Error: {error}[/red]")
            return None
        
        updates = data.get("result", [])
        
        if not updates:
            console.print("\n[yellow]⚠️  No messages found![/yellow]")
            console.print("[yellow]Please do the following:[/yellow]")
            console.print("1. Open Telegram")
            console.print("2. Search for your bot (the username you created)")
            console.print("3. Start a chat with your bot")
            console.print("4. Send ANY message (e.g., 'Hello' or '/start')")
            console.print("5. Run this script again\n")
            return None
        
        # Get all unique chat IDs from updates
        chat_ids = set()
        for update in updates:
            if "message" in update:
                chat = update["message"].get("chat", {})
                chat_id = chat.get("id")
                chat_type = chat.get("type", "unknown")
                if chat_id:
                    chat_ids.add((chat_id, chat_type))
        
        if not chat_ids:
            console.print("[red]❌ No chat IDs found in updates[/red]")
            return None
        
        console.print("\n[green]✅ Found Chat IDs:[/green]\n")
        
        for chat_id, chat_type in chat_ids:
            console.print(f"  [bold]Chat ID:[/bold] {chat_id} (Type: {chat_type})")
        
        # Return the first (most recent) chat ID
        most_recent = updates[-1]["message"]["chat"]["id"]
        console.print(f"\n[bold green]Using most recent Chat ID: {most_recent}[/bold green]")
        
        return most_recent
        
    except requests.exceptions.RequestException as e:
        console.print(f"[red]❌ Network error: {e}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        return None


def main():
    """Main function."""
    console.print(Panel.fit(
        "[bold green]Telegram Chat ID Finder[/bold green]\n"
        "This script helps you find your Telegram Chat ID.\n"
        "You need your bot token from @BotFather first.",
        title="Setup Helper"
    ))
    
    # Get bot token from command line or prompt
    if len(sys.argv) > 1:
        bot_token = sys.argv[1]
    else:
        console.print("\n[yellow]Enter your bot token from @BotFather:[/yellow]")
        console.print("[dim](It looks like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz)[/dim]")
        bot_token = input("Bot Token: ").strip()
    
    if not bot_token:
        console.print("[red]❌ Bot token is required![/red]")
        console.print("\n[yellow]How to get your bot token:[/yellow]")
        console.print("1. Open Telegram and search for @BotFather")
        console.print("2. Send /newbot")
        console.print("3. Follow the prompts to create a bot")
        console.print("4. BotFather will give you a token")
        sys.exit(1)
    
    # Validate token format (basic check)
    if ":" not in bot_token or len(bot_token) < 20:
        console.print("[red]❌ Invalid bot token format![/red]")
        console.print("[yellow]Bot token should look like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz[/yellow]")
        sys.exit(1)
    
    console.print(f"\n[cyan]Using bot token: {bot_token[:10]}...{bot_token[-5:]}[/cyan]\n")
    
    # Get chat ID
    chat_id = get_chat_id(bot_token)
    
    if chat_id:
        console.print("\n" + "=" * 60)
        console.print("[bold green]✅ Success![/bold green]")
        console.print("=" * 60)
        console.print(f"\n[bold]Your Chat ID is:[/bold] [green]{chat_id}[/green]\n")
        console.print("[yellow]Add this to your .env file:[/yellow]")
        console.print(f"[code]TELEGRAM_CHAT_ID={chat_id}[/code]\n")
    else:
        console.print("\n[yellow]💡 Tips:[/yellow]")
        console.print("• Make sure you've sent a message to your bot")
        console.print("• Check that your bot token is correct")
        console.print("• Try sending another message and run the script again\n")


if __name__ == "__main__":
    main()

