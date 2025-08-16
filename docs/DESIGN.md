# Contentful Blog Scraper - Technical Design

## Architecture Overview

The scraper follows a modular, object-oriented design with clear separation of concerns. The main `BlogScraper` class orchestrates the entire scraping process, while supporting classes handle specific responsibilities like progress tracking and statistics.

## Core Classes and Responsibilities

### BlogScraper Class
The main orchestrator class that handles the entire scraping workflow.

#### Key Methods:
- `__init__()` - Initializes scraper with configuration and creates output directories
- `scrape()` - Main entry point that orchestrates the entire scraping process
- `scrape_page()` - Processes individual pages and extracts blog post links
- `parse_blog_post()` - Converts HTML blog posts to structured markdown
- `save_as_markdown()` - Writes processed content to markdown files with frontmatter

#### Configuration Parameters:
```python
def __init__(self, base_url, output_dir="output", page_delay=3, post_delay=2, max_retries=3):
    self.base_url = base_url          # Target contributor page URL
    self.output_dir = output_dir      # Local output directory
    self.page_delay = page_delay      # Delay between page requests (seconds)
    self.post_delay = post_delay      # Delay between blog post requests (seconds)
    self.max_retries = max_retries    # Maximum retry attempts for failed requests
```

### ScrapingStats Class
Tracks scraping performance metrics and provides summary reporting.

## Data Flow Architecture

```
1. Base URL → 2. Page Discovery → 3. Blog Link Extraction → 4. Content Processing → 5. Markdown Generation → 6. File Output
   ↓              ↓                    ↓                      ↓                    ↓                    ↓
HTTP Session   Pagination          BeautifulSoup          HTML Parsing        Frontmatter         Local Storage
   ↓              ↓                    ↓                      ↓                    ↓                    ↓
Rate Limiting  Next Page URL      Link Collection        Content Cleaning     Metadata            Asset Download
```

## Content Processing Pipeline

### 1. HTML Fetching and Parsing
```python
def fetch_page(self, url):
    response = self.session.get(url, headers=self.headers)
    response.raise_for_status()
    return response.text
```

**Key Features:**
- Session-based requests for connection reuse
- Custom User-Agent headers to avoid blocking
- Error handling with `raise_for_status()`

### 2. Blog Link Discovery
```python
def extract_blog_links(self, html):
    soup = BeautifulSoup(html, 'html.parser')
    blog_elements = soup.find_all('a', href=lambda x: x and '/blog/' in x)
    # ... link processing
```

**Current Implementation:**
- Hardcoded selector: `href=lambda x: x and '/blog/' in x`
- Assumes blog URLs contain `/blog/` path segment
- **Limitation**: Not adaptable to different URL structures

### 3. Content Extraction and Transformation
The `parse_blog_post()` method implements a sophisticated HTML-to-markdown conversion pipeline:

#### Metadata Extraction:
```python
# Title extraction
title = soup.find('h1').get_text().strip() if soup.find('h1') else ''

# Date extraction (Contentful-specific)
date_element = soup.select_one('article p.txt-body-bold')
if date_element:
    date_text = date_element.get_text().strip()
    parsed_date = datetime.strptime(date_text, '%B %d, %Y')
    pub_date = parsed_date.strftime('%Y-%m-%d')
```

#### Content Processing Pipeline:
1. **Code Block Processing** - Preserves syntax highlighting and formatting
2. **Inline Code Conversion** - Converts `<code>` tags to markdown backticks
3. **Link Processing** - Converts relative URLs to absolute URLs
4. **Image Handling** - Downloads images locally and updates references
5. **HTML Cleanup** - Removes script/style tags and converts HTML to markdown

#### Code Block Preservation:
```python
# Process code blocks first (pre + code elements)
for pre in content_element.find_all('pre'):
    code_block = pre.find('code')
    if code_block:
        # Extract language from class
        lang = ''
        if code_block.get('class()'):
            for cls in code_block.get('class()):
                if cls.startswith('language-'):
                    lang = cls.replace('language-', '')
                    break
        
        # Complex text extraction preserving newlines
        code_lines = []
        current_line = []
        for span in code_block.find_all('span', recursive=True):
            text = span.get_text()
            if text.endswith('\n'):
                current_line.append(text.rstrip('\n'))
                code_lines.append(''.join(current_line))
                current_line = []
            else:
                current_line.append(text)
```

### 4. Image Asset Management
```python
def download_image(self, image_url, post_slug, for_content=False):
    response = self.session.get(image_url, headers=self.headers)
    response.raise_for_status()
    
    # Generate unique filename
    image_filename = image_url.split('/')[-1]
    image_path = os.path.join(self.output_dir, "assets/images/blog", f"{post_slug}-{image_filename}")
    
    # Save locally and return different path format based on usage
    with open(image_path, 'wb') as f:
        f.write(response.content)
    
    # Return different path format based on usage
    if for_content:
        return f"/images/blog/{post_slug}-{image_filename}"
    else:
        return f"~/assets/images/blog/{post_slug}-{image_filename}"
```

**Features:**
- **Clean, short filenames**: Uses post slug + random 8-char alphanumeric suffix (e.g., `post-slug-8bs9j3ns.jpg`)
- **Filesystem-safe naming**: Only alphanumeric characters, no URL encoding or special characters
- **Smart extension detection**: Determines file type from HTTP content-type headers
- Organized directory structure
- **Dual path format support**: 
  - Content images use `/images/blog/` format (cleaner for web deployment)
  - Frontmatter images use `~/assets/images/blog/` format (preserving existing behavior)
- Automatic path selection based on usage context

### 5. Markdown Generation with Frontmatter
```python
def save_as_markdown(self, post_data, content, filename):
    post = frontmatter.Post(content, **post_data)
    output_path = os.path.join(self.output_dir, f"{filename}.md")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(post))
```

**Frontmatter Structure:**
```yaml
---
title: "Blog Post Title"
description: "Post description extracted from meta tags or content"
pubDate: '2024-01-15'
categories: []
keywords: []
slug: "generated-from-url"
draft: false
tags: []
image: "~/assets/images/blog/post-slug-image.jpg"
canonical_url: "https://original-blog-url.com/post"
---

**Note:** The `image` field in frontmatter uses `~/assets/images/blog/` format, while images in the content body use `/images/blog/` format for cleaner web deployment.
```

## Pagination and Progress Management

### Pagination Strategy:
```python
def get_next_page_url(self, html):
    soup = BeautifulSoup(html, 'html.parser')
    pagination = soup.find('div', {'data-component': 'Pagination Links Bar'})
    
    # Find "Next" button by looking for various possible titles
    next_button = pagination.find('a', title='Next') or pagination.find('a', title='Next Page')
    if next_button:
        next_url = next_button.get('href')
        return urljoin(self.base_url, next_url)
    return None
```

**Current Implementation:**
- Hardcoded selector: `{'data-component': 'Pagination Links Bar'}`
- **Flexible Next button detection**: Supports both `title='Next'` and `title='Next Page'`
- **Improved adaptability**: Better handling of different pagination implementations
- **Limitation**: Still requires specific data-component attribute

### Progress Persistence:
```python
def save_progress(self, current_page_url, processed_urls):
    with open('scrape_progress.json', 'w') as f:
        json.dump({
            'current_page': current_page_url,
            'processed_urls': list(processed_urls),
            'timestamp': datetime.now().isoformat()
        }, f)
```

**Resume Capability:**
- Saves current page URL and processed URLs
- Converts sets to lists for JSON serialization
- Allows interrupted scrapes to resume from last position

## Error Handling and Resilience

### Request-Level Error Handling:
```python
def fetch_page(self, url):
    try:
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching {url}: {e}")
        return None
```

### Content Processing Error Handling:
```python
try:
    post_data, content = self.parse_blog_post(blog_url, blog_html)
    filename = post_data['slug']
    self.save_as_markdown(post_data, content, filename)
    processed_urls.add(blog_url)
    self.save_progress(url, processed_urls)
except Exception as e:
    logger.error(f"Error processing blog post {blog_url}: {e}")
    continue
```

### Rate Limiting:
```python
# Delay between page requests
time.sleep(self.page_delay)

# Delay between blog post requests
time.sleep(self.post_delay)
```

## Logging and Monitoring

### Logging Configuration:
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

### Key Log Messages:
- Page scraping progress
- Blog post processing status
- Error conditions and failures
- Completion summaries

## Configuration and Customization Points

### Hardcoded Selectors (Require Adaptation):
1. **Blog Link Detection**: `href=lambda x: x and '/blog/' in x` *(Enhanced with filtering)*
2. **Date Extraction**: `'article p.txt-body-bold'`
3. **Content Container**: `'txt-rich-long'` class
4. **Pagination**: `{'data-component': 'Pagination Links Bar'}` *(Enhanced with flexible Next button detection)*

### Easily Configurable:
1. **Delays**: `page_delay`, `post_delay`
2. **Output Directory**: `output_dir`
3. **Base URL**: `base_url`
4. **Retry Count**: `max_retries`

## Performance Characteristics

### Memory Usage:
- **Low memory footprint** - Processes one post at a time
- **Streaming downloads** - Images downloaded directly to disk
- **Efficient HTML parsing** - BeautifulSoup handles large HTML documents

### Network Efficiency:
- **Session reuse** - Maintains HTTP connections
- **Rate limiting** - Prevents server overload
- **Resume capability** - Avoids re-downloading existing content

### Scalability Considerations:
- **Single-threaded** - Not suitable for high-volume scraping
- **Sequential processing** - May be slow for large numbers of posts
- **Local storage** - Output directory size grows with content

## Security and Ethical Considerations

### Request Headers:
```python
self.headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
```

### Rate Limiting:
- Configurable delays between requests
- Respectful scraping patterns
- Avoids overwhelming target servers

## Testing and Validation

### Current State:
- **No automated tests** implemented
- **Manual validation** through output inspection
- **Error logging** for debugging

### Recommended Testing Strategy:
1. **Unit tests** for content parsing methods
2. **Integration tests** for end-to-end scraping
3. **Mock responses** for testing without network calls
4. **Output validation** for markdown and frontmatter correctness

## Deployment and Distribution

### Dependencies:
- Minimal external dependencies
- Python 3.x compatibility
- Virtual environment recommended

### Distribution:
- Single Python file (`scrape_blogs.py`)
- Requirements file for dependency management
- README with usage instructions
- No build process required
