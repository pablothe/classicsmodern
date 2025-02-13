#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup, NavigableString, Tag

def convert_element_to_markdown(element, indent=0):
    """
    Recursively convert a BeautifulSoup element into Markdown.
    This simple conversion handles headings, paragraphs, horizontal rules,
    lists, and links.
    """
    md = ""
    prefix = " " * indent

    # If the element is a string, return it
    if isinstance(element, NavigableString):
        text = element.strip()
        return text if text else ""

    # If it's a tag, check its name and convert accordingly.
    if element.name == "h1":
        md += f"# {element.get_text(strip=True)}\n\n"
    elif element.name == "h2":
        md += f"## {element.get_text(strip=True)}\n\n"
    elif element.name == "h3":
        md += f"### {element.get_text(strip=True)}\n\n"
    elif element.name == "h4":
        md += f"#### {element.get_text(strip=True)}\n\n"
    elif element.name == "p":
        # Process children to also convert inline elements
        line = "".join(convert_element_to_markdown(child) for child in element.children)
        if line:
            md += line + "\n\n"
    elif element.name == "hr":
        md += "\n---\n\n"
    elif element.name in ["ul", "ol"]:
        # For lists, process each direct <li> child.
        is_ordered = (element.name == "ol")
        for i, li in enumerate(element.find_all("li", recursive=False), start=1):
            if is_ordered:
                md += f"{prefix}{i}. " + convert_element_to_markdown(li, indent=indent+4).lstrip() + "\n"
            else:
                md += f"{prefix}- " + convert_element_to_markdown(li, indent=indent+4).lstrip() + "\n"
        md += "\n"
    elif element.name == "li":
        # Process list items recursively.
        for child in element.children:
            md += convert_element_to_markdown(child, indent=indent)
    elif element.name == "a":
        # Create a markdown link.
        href = element.get("href", "#")
        link_text = "".join(convert_element_to_markdown(child) for child in element.children).strip()
        md += f"[{link_text}]({href})"
    elif element.name == "br":
        md += "  \n"
    else:
        # For any other tags, process their children.
        for child in element.children:
            md += convert_element_to_markdown(child, indent=indent)
    return md

def html_to_markdown(html):
    """
    Convert an HTML document to Markdown by parsing it and then processing
    the elements one by one.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove any script or style tags.
    for unwanted in soup(["script", "style"]):
        unwanted.decompose()

    # Here we assume the main content is inside the <body>.
    content = soup.body if soup.body else soup

    # Walk through the content and convert each child.
    md = ""
    for child in content.children:
        md += convert_element_to_markdown(child)

    return md

def main():
    # URL for the HTML version of Don Quijote from Project Gutenberg.
    url = "https://www.gutenberg.org/cache/epub/1342/pg1342-images.html"
    print(f"Downloading content from {url} ...")
    response = requests.get(url)
    if response.status_code != 200:
        print("Error downloading the page.")
        return

    # Set the correct encoding.
    # Option 1: Use the apparent encoding detected by requests.
    response.encoding = response.apparent_encoding
    # Option 2: Force the encoding if you know it (e.g., "utf-8")
    # response.encoding = "utf-8"

    html = response.text
    print("Converting HTML to Markdown ...")
    markdown_text = html_to_markdown(html)

    output_filename = "Pride_and_Prejudice.md"
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    print(f"Markdown file created: {output_filename}")

if __name__ == "__main__":
    main()
