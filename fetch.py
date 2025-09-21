import sys
import requests
import os
import re
import threading
import time

API = "https://gutendex.com/books"

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
        return {"success": True, "results": results}
    except requests.exceptions.Timeout:
        # Stop spinner first, then show error
        spinner_running[0] = False
        spinner_thread.join(timeout=0.2)
        print(f"\r{' ' * 40}", end="")  # Clear the spinner line
        print("\rError: Project Gutenberg API did not respond in time (timeout after 20 seconds)")
        return {"success": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        # Stop spinner first, then show error
        spinner_running[0] = False
        spinner_thread.join(timeout=0.2)
        print(f"\r{' ' * 40}", end="")  # Clear the spinner line
        print("\rError: Could not connect to Project Gutenberg API")
        return {"success": False, "error": "connection"}
    except requests.exceptions.RequestException as e:
        # Stop spinner first, then show error
        spinner_running[0] = False
        spinner_thread.join(timeout=0.2)
        print(f"\r{' ' * 40}", end="")  # Clear the spinner line
        print(f"\rError: Failed to search Project Gutenberg: {str(e)}")
        return {"success": False, "error": "other"}
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
    # According to GutenDex API docs, could be 'text/plain', 'text/plain; charset=utf-8', etc.
    for mime_type, url in fmts.items():
        if mime_type.startswith("text/plain"):
            return url
    return None

def slugify(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

def download_book(book, dest_dir="books"):
    os.makedirs(dest_dir, exist_ok=True)
    url = pick_text_url(book)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    name = f'{slugify(book["title"])}-{book["id"]}.txt'
    path = os.path.join(dest_dir, name)
    with open(path, "wb") as f:
        f.write(r.content)
    return path

def interactive_fetch():
    while True:
        q = input("Search Project Gutenberg (or type 'quit' to exit): ").strip()
        if q.lower() == 'quit':
            print("Closing BookBot...")
            sys.exit(0)
            
        response = search_books(q)
        if not response["success"]:
            print("Press Enter to try another search, or type 'quit' to exit")
            if input().lower() == 'quit':
                print("Closing BookBot...")
                sys.exit(0)
            continue
            
        results = response["results"][:10]
        if not results:
            print("No books found matching your search term.")
            print("Please try a different search term.")
            continue
            
        print(f"Found {len(results)} books with plain text format:")
        for i, b in enumerate(results, 1):
            auth = ", ".join(a["name"] for a in b["authors"]) or "Unknown"
            print(f"{i}. {b['title']} — {auth} (ID {b['id']})")
            
        while True:
            try:
                choice = input("Choose a number (or press Enter to search again, 'quit' to exit): ").strip()
                if not choice:  # Empty input, user wants to search again
                    break
                if choice.lower() == 'quit':
                    print("Closing BookBot...")
                    sys.exit(0)
                    
                choice_num = int(choice)
                if choice_num < 1 or choice_num > len(results):
                    print("Invalid choice. Please try again.")
                    continue
                    
                book = results[choice_num-1]
                path = download_book(book)
                print(f"Saved to {path}")
                return path
                
            except ValueError:
                print("Please enter a valid number.")
                continue