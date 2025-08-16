# Contentful Blog Scraper - Project Overview

## Project Goal

This project is a specialized web scraper designed to extract blog post content from Contentful-powered websites, specifically targeting contributor pages. The primary goal is to convert HTML-based blog content into clean, structured markdown files with proper frontmatter metadata, while preserving all media assets (images) locally.

## Use Case

The scraper was originally developed for Snyk's contributor blog pages (e.g., `https://snyk.io/contributors/liran-tal/`) but is designed to be adaptable for other Contentful-based blog systems. It's particularly useful for:

- Content migration projects
- Creating local archives of blog content
- Converting HTML-based blogs to static site generators
- Preserving blog content with all associated media assets

## Technical Stack

### Core Technologies
- **Python 3.x** - Primary programming language
- **Requests** (2.31.0) - HTTP library for web scraping
- **BeautifulSoup4** (4.12.3) - HTML parsing and manipulation
- **python-frontmatter** (1.1.0) - YAML frontmatter handling for markdown files

### Architecture
- **Object-oriented design** with `BlogScraper` class as the main orchestrator
- **Session-based HTTP requests** for efficient scraping
- **Resume capability** with progress tracking via JSON files
- **Rate limiting** with configurable delays to be respectful to servers

## Key Features

### Content Extraction
- **Blog post discovery** via pagination through contributor pages *(Enhanced with flexible Next button detection)*
- **Metadata extraction** including title, description, publication date, and canonical URLs
- **Content conversion** from HTML to clean markdown format
- **Code block preservation** with language detection and proper formatting
- **Image handling** with local download and path updates *(Enhanced with dual path format support)*

### Robustness
- **Error handling** with comprehensive logging
- **Retry mechanisms** for failed requests
- **Progress persistence** allowing interrupted scrapes to resume
- **Duplicate detection** to avoid re-processing existing content

### Output Structure
- **Organized file hierarchy** with assets in dedicated directories
- **Standardized frontmatter** compatible with static site generators
- **Local image storage** with proper naming conventions
- **Clean markdown** with preserved formatting and links

## How to Run

### Prerequisites
- Python 3.x
- pip package manager
- Virtual environment (recommended)

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd scrape-contentful-blogs-by-contributors

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage
```bash
# Run the scraper with default settings
python3 scrape_blogs.py

# The scraper will:
# 1. Create output directory structure
# 2. Start scraping from the configured base URL
# 3. Download all blog posts and images
# 4. Save progress for resume capability
```

### Output Structure
```
output/
├── blog-post-1.md
├── blog-post-2.md
├── assets/
│   └── images/
│       └── blog/
│           ├── post-1-image1.jpg
│           └── post-2-image1.png
└── scrape_progress.json
```

## Configuration

### Main Configurable Parameters
The scraper can be customized by modifying the `BlogScraper` class initialization:

```python
scraper = BlogScraper(
    base_url="https://example.com/contributors/author/",
    output_dir="custom_output",
    page_delay=5,        # Delay between page requests (seconds)
    post_delay=3,        # Delay between blog post requests (seconds)
    max_retries=5        # Maximum retry attempts for failed requests
)
```

### Target URL Configuration
To scrape different blogs, modify the `base_url` in the `main()` function:

```python
def main():
    base_url = "https://your-blog.com/contributors/author-name/"
    scraper = BlogScraper(base_url)
    scraper.scrape()
```

## Limitations and Considerations

### Technical Limitations
- **HTML structure dependency** - Selectors are hardcoded for specific Contentful layouts
- **Single contributor focus** - Designed for individual author pages, not multi-author blogs
- **Contentful-specific** - May require adaptation for other CMS platforms

### Ethical Considerations
- **Rate limiting** - Built-in delays to avoid overwhelming servers
- **Respectful scraping** - User-agent headers and reasonable request patterns
- **Local storage** - Downloads content for local use, not redistribution

### Legal Considerations
- **Content ownership** - Ensure you have rights to scrape and store content
- **Terms of service** - Review target website's terms before scraping
- **Copyright compliance** - Respect intellectual property rights

## Future Development

### Potential Enhancements
- **Multi-site support** - Scrape multiple contributor pages simultaneously
- **Content validation** - Verify scraped content integrity
- **Export formats** - Support for additional output formats (JSON, XML)
- **API integration** - Direct Contentful API integration as alternative to scraping
- **Content transformation** - Advanced markdown processing and formatting options
