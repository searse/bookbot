"""
BookBot Gutenberg API client and interactive book fetcher.

This module provides functionality to search and download books from Project Gutenberg
using the Gutendex API.
"""

import sys
import os
import re
import threading
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import requests

# Constants
GUTENDEX_API_URL = "https://gutendex.com/books"
DEFAULT_TIMEOUT = 20
DOWNLOAD_TIMEOUT = 60
MAX_SEARCH_RESULTS = 10
DEFAULT_BOOKS_DIR = "books"
SPINNER_CHARS = "|/-\\"
SPINNER_DELAY = 0.1


@dataclass
class BookSearchResult:
    """Represents a book from the Gutenberg search results."""
    id: int
    title: str
    authors: List[Dict[str, Any]]
    formats: Dict[str, str]
    
    @property
    def authors_display(self) -> str:
        """Get a formatted string of authors for display."""
        return ", ".join(author["name"] for author in self.authors) or "Unknown"
    
    @property
    def text_url(self) -> Optional[str]:
        """Get the plain text URL for this book."""
        for mime_type, url in self.formats.items():
            if mime_type.startswith("text/plain"):
                return url
        return None


class SpinnerContext:
    """Context manager for showing a loading spinner."""
    
    def __init__(self, message: str = "Loading"):
        self.message = message
        self.spinner_running = [True]
        self.spinner_thread: Optional[threading.Thread] = None
    
    def __enter__(self):
        self.spinner_thread = threading.Thread(target=self._show_spinner)
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.spinner_running[0] = False
        if self.spinner_thread and self.spinner_thread.is_alive():
            self.spinner_thread.join(timeout=0.2)
        self._clear_spinner_line()
    
    def _show_spinner(self):
        """Show the spinning animation."""
        idx = 0
        while self.spinner_running[0]:
            char = SPINNER_CHARS[idx % len(SPINNER_CHARS)]
            print(f"\r{self.message}... {char}", end="", flush=True)
            time.sleep(SPINNER_DELAY)
            idx += 1
    
    def _clear_spinner_line(self):
        """Clear the spinner line."""
        print(f"\r{' ' * 40}", end="")
        print("\r", end="", flush=True)


class GutenbergAPIError(Exception):
    """Base exception for Gutenberg API related errors."""
    pass


class GutenbergAPI:
    """Client for interacting with the Gutendex API."""
    
    def __init__(self, base_url: str = GUTENDEX_API_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
    
    def search_books(self, query: str) -> List[BookSearchResult]:
        """Search for books with the given query."""
        try:
            params = {"search": query, "mime_type": "text/plain"}
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            results_data = response.json()["results"]
            return [
                BookSearchResult(
                    id=book["id"],
                    title=book["title"],
                    authors=book["authors"],
                    formats=book["formats"]
                )
                for book in results_data
            ]
            
        except requests.exceptions.Timeout:
            raise GutenbergAPIError(
                f"Project Gutenberg API did not respond in time (timeout after {self.timeout} seconds)"
            )
        except requests.exceptions.ConnectionError:
            raise GutenbergAPIError("Could not connect to Project Gutenberg API")
        except requests.exceptions.RequestException as e:
            raise GutenbergAPIError(f"Failed to search Project Gutenberg: {str(e)}")
    
    def download_book_content(self, url: str) -> bytes:
        """Download the content of a book from the given URL."""
        try:
            response = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            raise GutenbergAPIError(f"Failed to download book: {str(e)}")


class BookDownloader:
    """Handles downloading and saving books."""
    
    def __init__(self, destination_dir: str = DEFAULT_BOOKS_DIR):
        self.destination_dir = destination_dir
        self.api = GutenbergAPI()
    
    def _slugify(self, text: str) -> str:
        """Convert text to a URL-friendly slug."""
        return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    
    def _generate_filename(self, book: BookSearchResult) -> str:
        """Generate a filename for the book."""
        slug = self._slugify(book.title)
        return f'{slug}-{book.id}.txt'
    
    def download_book(self, book: BookSearchResult) -> str:
        """Download a book and save it to the destination directory."""
        if not book.text_url:
            raise GutenbergAPIError(f"No text format available for book: {book.title}")
        
        # Ensure destination directory exists
        os.makedirs(self.destination_dir, exist_ok=True)
        
        # Download content
        content = self.api.download_book_content(book.text_url)
        
        # Save to file
        filename = self._generate_filename(book)
        filepath = os.path.join(self.destination_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(content)
        
        return filepath


class InteractiveBookFetcher:
    """Handles the interactive book search and selection process."""
    
    def __init__(self):
        self.api = GutenbergAPI()
        self.downloader = BookDownloader()
    
    def run(self) -> str:
        """Run the interactive book fetching process."""
        while True:
            query = self._get_search_query()
            if query is None:  # User wants to quit
                return None
            
            books = self._search_books_with_spinner(query)
            if books is None:  # Error occurred, try again
                continue
            
            if not books:
                print("No books found matching your search term.")
                print("Please try a different search term.")
                continue
            
            selected_book = self._select_book(books)
            if selected_book is None:  # User wants to search again or quit
                continue
            
            return self._download_selected_book(selected_book)
    
    def _get_search_query(self) -> Optional[str]:
        """Get search query from user."""
        query = input("Search Project Gutenberg (or type 'quit' to exit): ").strip()
        if query.lower() == 'quit':
            print("Closing BookBot...")
            sys.exit(0)
        return query
    
    def _search_books_with_spinner(self, query: str) -> Optional[List[BookSearchResult]]:
        """Search for books with a loading spinner."""
        with SpinnerContext("Searching Project Gutenberg"):
            try:
                return self.api.search_books(query)
            except GutenbergAPIError as e:
                print(f"\rError: {e}")
                print("Press Enter to try another search, or type 'quit' to exit")
                if input().lower() == 'quit':
                    print("Closing BookBot...")
                    sys.exit(0)
                return None
    
    def _display_search_results(self, books: List[BookSearchResult]) -> None:
        """Display the search results to the user."""
        print(f"Found {len(books)} books with plain text format:")
        for i, book in enumerate(books, 1):
            print(f"{i}. {book.title} — {book.authors_display} (ID {book.id})")
    
    def _select_book(self, books: List[BookSearchResult]) -> Optional[BookSearchResult]:
        """Let user select a book from the search results."""
        # Limit results for display
        display_books = books[:MAX_SEARCH_RESULTS]
        self._display_search_results(display_books)
        
        while True:
            choice = input(
                "Choose a number (or press Enter to search again, 'quit' to exit): "
            ).strip()
            
            if not choice:  # Empty input, search again
                return None
            
            if choice.lower() == 'quit':
                print("Closing BookBot...")
                sys.exit(0)
            
            try:
                choice_num = int(choice)
                if 1 <= choice_num <= len(display_books):
                    return display_books[choice_num - 1]
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
    
    def _download_selected_book(self, book: BookSearchResult) -> str:
        """Download the selected book."""
        try:
            filepath = self.downloader.download_book(book)
            print(f"Saved to {filepath}")
            return filepath
        except GutenbergAPIError as e:
            print(f"Error downloading book: {e}")
            return None


def interactive_fetch() -> str:
    """
    Main entry point for interactive book fetching.
    
    Returns:
        str: Path to the downloaded book file
    """
    fetcher = InteractiveBookFetcher()
    return fetcher.run()


# Backward compatibility functions
def search_books(query: str) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    
    Returns results in the old format expected by existing code.
    """
    try:
        api = GutenbergAPI()
        with SpinnerContext("Searching Project Gutenberg"):
            books = api.search_books(query)
        
        # Convert to old format
        results = [
            {
                "id": book.id,
                "title": book.title,
                "authors": book.authors,
                "formats": book.formats
            }
            for book in books
        ]
        
        return {"success": True, "results": results}
        
    except GutenbergAPIError as e:
        print(f"\rError: {e}")
        return {"success": False, "error": "api_error"}


def download_book(book_dict: Dict[str, Any], dest_dir: str = DEFAULT_BOOKS_DIR) -> str:
    """
    Legacy function for backward compatibility.
    
    Args:
        book_dict: Book data in the old dictionary format
        dest_dir: Destination directory for the download
    
    Returns:
        str: Path to the downloaded file
    """
    # Convert old format to new format
    book = BookSearchResult(
        id=book_dict["id"],
        title=book_dict["title"],
        authors=book_dict["authors"],
        formats=book_dict["formats"]
    )
    
    downloader = BookDownloader(dest_dir)
    return downloader.download_book(book)


# Keep these functions for any external usage
def pick_text_url(book_dict: Dict[str, Any]) -> Optional[str]:
    """Legacy function - get text URL from book dictionary."""
    book = BookSearchResult(
        id=book_dict["id"],
        title=book_dict["title"],
        authors=book_dict["authors"],
        formats=book_dict["formats"]
    )
    return book.text_url


def slugify(text: str) -> str:
    """Legacy function - convert text to slug."""
    downloader = BookDownloader()
    return downloader._slugify(text)
