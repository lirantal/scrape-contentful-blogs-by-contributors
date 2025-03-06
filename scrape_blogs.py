import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import re
import json
from urllib.parse import urljoin
import frontmatter
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BlogScraper:
    def __init__(self, base_url, output_dir="output"):
        self.base_url = base_url
        self.output_dir = output_dir
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "assets/images/blog"), exist_ok=True)

    def fetch_page(self, url):
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def extract_blog_links(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        blog_links = []
        
        # Find all blog post links
        # Note: You'll need to adjust these selectors based on the actual HTML structure
        blog_elements = soup.find_all('a', href=lambda x: x and '/blog/' in x)
        
        for blog in blog_elements:
            link = urljoin(self.base_url, blog.get('href'))
            blog_links.append(link)
            
        return list(set(blog_links))  # Remove duplicates

    def download_image(self, image_url, post_slug):
        try:
            response = self.session.get(image_url, headers=self.headers)
            response.raise_for_status()
            
            # Extract image filename from URL
            image_filename = image_url.split('/')[-1]
            image_path = os.path.join(self.output_dir, "assets/images/blog", f"{post_slug}-{image_filename}")
            
            with open(image_path, 'wb') as f:
                f.write(response.content)
                
            return f"~/assets/images/blog/{post_slug}-{image_filename}"
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return image_url

    def parse_blog_post(self, url, html):
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract metadata (adjust selectors as needed)
        title = soup.find('h1').get_text().strip() if soup.find('h1') else ''
        
        # Find publication date in the article component with txt-body-bold class
        pub_date = datetime.now().strftime('%Y-%m-%d')  # Default to current date
        date_element = soup.select_one('article p.txt-body-bold')
        if date_element:
            try:
                date_text = date_element.get_text().strip()
                parsed_date = datetime.strptime(date_text, '%B %d, %Y')
                pub_date = parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                logger.warning(f"Could not parse date from {date_text}")

        # Generate slug from URL
        slug = url.rstrip('/').split('/')[-1]

        # Extract main content - specifically targeting the txt-rich-long class
        content_element = soup.find('div', class_='txt-rich-long')
        content = ''
        
        if content_element:
            # Remove any toggle-play-wrapper elements before processing
            for toggle_wrapper in content_element.find_all('div', class_='toggle-play-wrapper'):
                toggle_wrapper.decompose()

            # Process code blocks first (pre + code elements)
            for pre in content_element.find_all('pre'):
                code_block = pre.find('code')
                if code_block:
                    # Get the language from the class if available
                    lang = ''
                    if code_block.get('class'):
                        for cls in code_block.get('class'):
                            if cls.startswith('language-'):
                                lang = cls.replace('language-', '')
                                break
                    
                    # Extract code content while preserving actual newlines and removing span artifacts
                    code_lines = []
                    current_line = []
                    
                    for span in code_block.find_all('span', recursive=True):
                        # Get the text content
                        text = span.get_text()
                        # If the span ends with a newline, add to current line and start new line
                        if text.endswith('\n'):
                            current_line.append(text.rstrip('\n'))
                            code_lines.append(''.join(current_line))
                            current_line = []
                        else:
                            current_line.append(text)
                    
                    # Add any remaining content in current_line
                    if current_line:
                        code_lines.append(''.join(current_line))
                    
                    # Join lines with proper newlines
                    code_content = '\n'.join(code_lines)
                    
                    # If no spans were found, fallback to regular text
                    if not code_content.strip():
                        code_content = code_block.get_text('\n').strip()
                    
                    markdown_block = soup.new_string(f"\n```{lang}\n{code_content}\n```\n\n")
                    pre.replace_with(markdown_block)

            # Process inline code elements
            for code in content_element.find_all('code'):
                # Skip if this code element is inside a pre (should have been handled above)
                if not code.find_parent('pre'):
                    code_text = code.get_text()
                    code.replace_with(f'`{code_text}`')

            # Process links before other transformations
            for link in content_element.find_all('a'):
                href = link.get('href', '')
                if href:
                    # Make sure the href is absolute
                    href = urljoin(url, href)
                    text = link.get_text()
                    link.replace_with(f'[{text}]({href})')

            # Process images in content
            for img in content_element.find_all('img'):
                img_url = img.get('src', '')
                if img_url:
                    img_url = urljoin(url, img_url)
                    local_img_path = self.download_image(img_url, slug)
                    # Update image reference in markdown format
                    img.replace_with(f"![{img.get('alt', 'image')}]({local_img_path})\n")

            # Clean up the content
            # Remove any script tags
            for script in content_element.find_all('script'):
                script.decompose()
            
            # Remove any style tags
            for style in content_element.find_all('style'):
                style.decompose()

            # Convert HTML content to markdown-friendly format while preserving our markdown elements
            # First, get the modified HTML with our markdown elements
            content = str(content_element)
            
            # Convert common HTML elements to markdown
            content = re.sub(r'<h1.*?>(.*?)</h1>', r'\n# \1\n\n', content)
            content = re.sub(r'<h2.*?>(.*?)</h2>', r'\n## \1\n\n', content)
            content = re.sub(r'<h3.*?>(.*?)</h3>', r'\n### \1\n\n', content)
            content = re.sub(r'<p.*?>(.*?)</p>', r'\1\n\n', content)
            content = re.sub(r'<li.*?>(.*?)</li>', r'* \1\n', content)
            
            # Remove any remaining HTML tags but preserve our markdown
            content = re.sub(r'<(?!`|/`|!\[|\[)[^>]+>', '', content)
            
            # Clean up extra whitespace while preserving intentional line breaks
            content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
            content = content.strip()

        # Try to extract description from meta tags or first paragraph
        description = ''
        meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
        if meta_desc:
            description = meta_desc.get('content', '')
        elif content:
            # Take first paragraph as description if no meta description
            first_para = content.split('\n\n')[0]
            description = first_para[:160] + '...' if len(first_para) > 160 else first_para

        # Try to find main image
        main_image = ''
        og_image = soup.find('meta', {'property': 'og:image'})
        if og_image:
            image_url = og_image.get('content', '')
            if image_url:
                main_image = self.download_image(image_url, slug)

        # Create frontmatter data
        post_data = {
            'title': title,
            'description': description,
            'pubDate': pub_date,
            'categories': [],
            'keywords': [],
            'slug': slug,
            'draft': False,
            'tags': [],
            'image': main_image,
            'canonical_url': url  # Add canonical URL to frontmatter
        }

        return post_data, content

    def save_as_markdown(self, post_data, content, filename):
        post = frontmatter.Post(content, **post_data)
        
        output_path = os.path.join(self.output_dir, f"{filename}.md")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post))
        
        logger.info(f"  -> Saved blog post: {output_path}")

    def get_next_page_url(self, html):
        """Extract the next page URL from the pagination element"""
        soup = BeautifulSoup(html, 'html.parser')
        pagination = soup.find('div', {'data-component': 'Pagination Links Bar'})
        
        if not pagination:
            return None
            
        # Find the "Next" button by looking for the chevron-right icon
        next_button = pagination.find('a', title='Next')
        if next_button:
            next_url = next_button.get('href')
            if next_url:
                return urljoin(self.base_url, next_url)
        
        return None

    def scrape_page(self, url):
        """Scrape a single page of blog posts"""
        html = self.fetch_page(url)
        if not html:
            return None
        
        # Extract blog links from this page
        blog_links = self.extract_blog_links(html)
        logger.info(f"Found {len(blog_links)} blog posts on page {url}")
        
        # Process each blog post
        for blog_url in blog_links:
            logger.info(f"Processing blog post: {blog_url}")
            
            # Add delay to be respectful to the server
            time.sleep(2)
            
            blog_html = self.fetch_page(blog_url)
            if not blog_html:
                continue
            
            post_data, content = self.parse_blog_post(blog_url, blog_html)
            filename = post_data['slug']
            self.save_as_markdown(post_data, content, filename)
        
        return html

    def scrape(self):
        """Scrape all pages of blog posts"""
        logger.info(f"Starting scrape of {self.base_url}")
        
        current_url = self.base_url
        page_number = 1
        
        while current_url:
            logger.info(f"Scraping page {page_number}: {current_url}")
            
            # Scrape the current page
            html = self.scrape_page(current_url)
            if not html:
                break
            
            # Get the next page URL
            next_url = self.get_next_page_url(html)
            
            # If there's no next page, we're done
            if not next_url:
                logger.info("No more pages to scrape")
                break
            
            # Add a delay before fetching the next page
            time.sleep(3)
            
            # Update for next iteration
            current_url = next_url
            page_number += 1
        
        logger.info("Finished scraping all pages")

def main():
    base_url = "https://snyk.io/contributors/liran-tal/"
    scraper = BlogScraper(base_url)
    scraper.scrape()

if __name__ == "__main__":
    main() 