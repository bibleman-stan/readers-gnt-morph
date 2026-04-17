#!/usr/bin/env python3
"""
Inject generated chapter JSON into the HTML template to produce a standalone file.
"""
import json, sys, os

def main():
    data_file = sys.argv[1] if len(sys.argv) > 1 else 'build/acts/9.json'
    template = sys.argv[2] if len(sys.argv) > 2 else 'templates/reader.html'
    output = sys.argv[3] if len(sys.argv) > 3 else 'docs/acts/9.html'

    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with open(template, 'r', encoding='utf-8') as f:
        html = f.read()

    # Inject data and chapter info
    book = data.get('book', 'Acts')
    chapter = data.get('chapter', '?')
    ch_json = json.dumps(data['data'], ensure_ascii=False)
    lex_json = json.dumps(data['lex'], ensure_ascii=False)

    html = html.replace('CHAPTER_DATA_PLACEHOLDER', ch_json)
    html = html.replace('LEX_DATA_PLACEHOLDER', lex_json)
    html = html.replace('BOOK_NAME_PLACEHOLDER', book)
    html = html.replace('CHAPTER_NUM_PLACEHOLDER', str(chapter))

    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Built {output}: {len(data['data'])} entries, {len(data['lex'])} lexicon entries")

if __name__ == '__main__':
    main()
