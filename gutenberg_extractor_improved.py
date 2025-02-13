import requests
from bs4 import BeautifulSoup, NavigableString
import re
import os

def convert_element_to_markdown(element, indent=0):
    """
    Recursively convert a BeautifulSoup element into Markdown.
    """
    md = ""
    prefix = " " * indent
    
    if isinstance(element, NavigableString):
        text = element.strip()
        return text if text else ""
    
    if element.name in ["h1", "h2", "h3", "h4"]:
        level = "#" * int(element.name[1])
        md += f"{level} {element.get_text(strip=True)}\n\n"
    elif element.name == "p":
        line = "".join(convert_element_to_markdown(child) for child in element.children)
        if line:
            md += line + "\n\n"
    elif element.name == "hr":
        md += "\n---\n\n"
    elif element.name in ["ul", "ol"]:
        is_ordered = (element.name == "ol")
        for i, li in enumerate(element.find_all("li", recursive=False), start=1):
            if is_ordered:
                md += f"{prefix}{i}. " + convert_element_to_markdown(li, indent=indent+4).lstrip() + "\n"
            else:
                md += f"{prefix}- " + convert_element_to_markdown(li, indent=indent+4).lstrip() + "\n"
        md += "\n"
    elif element.name == "a":
        href = element.get("href", "#")
        link_text = "".join(convert_element_to_markdown(child) for child in element.children).strip()
        md += f"[{link_text}]({href})"
    elif element.name == "br":
        md += "  \n"
    else:
        for child in element.children:
            md += convert_element_to_markdown(child, indent=indent)
    
    return md

def html_to_markdown(html):
    """
    Convert an HTML document to Markdown.
    """
    soup = BeautifulSoup(html, "html.parser")
    for unwanted in soup(["script", "style"]):
        unwanted.decompose()
    content = soup.body if soup.body else soup
    md = "".join(convert_element_to_markdown(child) for child in content.children)
    return md

def get_page_title(html, url):
    """Extracts a meaningful title for the output file."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string if soup.title else ""
    title = re.sub(r'[^a-zA-Z0-9_]', '_', title) if title else re.sub(r'[^a-zA-Z0-9_]', '_', url.split("//")[-1].split("/")[0])
    return title[:50]  # Truncate long titles

def process_urls(urls):
    """Downloads and processes each URL into a markdown file."""
    if not os.path.exists("output"):  # Ensure output directory exists
        os.makedirs("output")
    
    for url in urls:
        print(f"Downloading content from {url} ...")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            html = response.text
            title = get_page_title(html, url)
            markdown_text = html_to_markdown(html)
            output_filename = f"output/{title}.md"
            
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(markdown_text)
            
            print(f"Markdown file created: {output_filename}")
        except requests.RequestException as e:
            print(f"Failed to download {url}: {e}")

def main():
    urls = [
        "https://www.gutenberg.org/cache/epub/1342/pg1342-images.html",
        "https://www.gutenberg.org/cache/epub/67098/pg67098-images.html",
        "https://www.gutenberg.org/cache/epub/2701/pg2701-images.html",
        "https://www.gutenberg.org/cache/epub/1661/pg1661-images.html",
        "https://www.gutenberg.org/cache/epub/36/pg36-images.html",
        "https://www.gutenberg.org/cache/epub/35/pg35-images.html",
        "https://www.gutenberg.org/cache/epub/5200/pg5200-images.html",
        "https://www.gutenberg.org/cache/epub/64317/pg64317-images.html"

    ]  # Replace with a list of URLs to process
    process_urls(urls)

if __name__ == "__main__":
    main()
