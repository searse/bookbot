import argparse

from stats import (
    get_num_words,
    chars_dict_to_sorted_list,
    get_chars_dict,
)

from fetch import interactive_fetch


def main():
    parser = argparse.ArgumentParser(description="Analyze text files from local path or Project Gutenberg")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to the book file to analyze")
    group.add_argument("--search", action="store_true", help="Search and download a book from Project Gutenberg")
    args = parser.parse_args()

    if args.search:
        book_path = interactive_fetch()
    else:
        book_path = args.file
    text = get_book_text(book_path)
    num_words = get_num_words(text)
    chars_dict = get_chars_dict(text)
    chars_sorted_list = chars_dict_to_sorted_list(chars_dict)
    print_report(book_path, num_words, chars_sorted_list)


def get_book_text(path):
    with open(path) as f:
        return f.read()


def print_report(book_path, num_words, chars_sorted_list):
    print("============ BOOKBOT ============")
    print(f"Analyzing book found at {book_path}...")
    print("----------- Word Count ----------")
    print(f"Found {num_words} total words")
    print("--------- Character Count -------")
    for item in chars_sorted_list:
        if not item["char"].isalpha():
            continue
        print(f"{item['char']}: {item['num']}")

    print("============= END ===============")


main()
