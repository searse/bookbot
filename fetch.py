import sys
import requests
import os
import re
import threading
import time

API = "https://gutendex.com/books"

def slugify(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def has_plain_text(book) -> bool:
    """Check if a book has plain text format available."""
    fmts = book["formats"]
    # Look for any MIME type that starts with 'text/plain'
    return any(mime_type.startswith("text/plain") for mime_type in fmts.keys())

def search_books(query: str):
    # Create a simple loading animation
    spinner_chars = "|/-\\"
    spinner_running = [True]  # Use list for mutable reference
    
    def show_spinner():
        idx = 0
        while spinner_running[0]:
            char = spinner_chars[idx % len(spinner_chars)]
            print(f"\rSearching Project Gutenberg... {char}", end="", flush=True)
            time.sleep(0.1)
            idx += 1
    
    # Start spinner in background thread
    spinner_thread = threading.Thread(target=show_spinner)
    spinner_thread.daemon = True
    spinner_thread.start()
    
    try:
        # Use mime_type parameter to filter for plain text books at the API level
        params = {"search": query, "mime_type": "text/plain"}
        r = requests.get(API, params=params, timeout=20)
        r.raise_for_status()
        results = r.json()["results"]
        # All results should have plain text format since we filtered at API level
        return results
    except requests.exceptions.RequestException as e:
        # Stop spinner first, then show error
        spinner_running[0] = False
        spinner_thread.join(timeout=0.2)
        print(f"\r{' ' * 40}", end="")  # Clear the spinner line
        print(f"\rError searching for books: {e}")
        return []
    finally:
        # Stop spinner and clear the line
        spinner_running[0] = False
        if spinner_thread.is_alive():
            spinner_thread.join(timeout=0.2)
        print(f"\r{' ' * 40}", end="")  # Clear the spinner line
        print("\r", end="", flush=True)

def pick_text_url(book):
    fmts = book["formats"]
    # Look for any MIME type that starts with 'text/plain'
    # According to Gutendx API docs, could be 'text/plain', 'text/plain; charset=utf-8', etc.
    for mime_type, url in fmts.items():
        if mime_type.startswith("text/plain"):
            return url
    return None

def download_book(book, dest_dir="books"):
    os.makedirs(dest_dir, exist_ok=True)
    url = pick_text_url(book)
    if not url:
        raise ValueError("No plain text format available for this book.")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    name = f'{slugify(book["title"])}-{book["id"]}.txt'
    path = os.path.join(dest_dir, name)
    with open(path, "wb") as f:
        f.write(r.content)
    return path

def interactive_fetch():
    q = input("Search Project Gutenberg: ").strip()
    results = search_books(q)[:10]
    if not results:
        print("No plain text books found for your search.")
        print("This could be due to:")
        print("- No books matching your search term")
        print("- No plain text versions available for matching books")
        print("- Network connectivity issues")
        sys.exit(1)
    print(f"Found {len(results)} books with plain text format:")
    for i, b in enumerate(results, 1):
        auth = ", ".join(a["name"] for a in b["authors"]) or "Unknown"
        print(f"{i}. {b['title']} — {auth} (ID {b['id']})")
    try:
        choice = int(input("Choose a number: "))
        if choice < 1 or choice > len(results):
            print("Invalid choice."); sys.exit(1)
    except ValueError:
        print("Please enter a valid number."); sys.exit(1)
    book = results[choice-1]
    path = download_book(book)
    print(f"Saved to {path}")
    return path