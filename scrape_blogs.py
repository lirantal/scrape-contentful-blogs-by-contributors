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

class SnykBlogScraper:
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
        
        # Find publication date - look for the date in the blog card first
        pub_date = datetime.now().strftime('%Y-%m-%d')  # Default to current date
        
        # Try different date selectors
        date_selectors = [
            'time[datetime]',  # Look for semantic time tag with datetime attribute
            '.blog-card time',  # Look for time within blog card
            'article time',    # Look for time within article
            '[class*="date"]', # Look for any element with 'date' in its class
        ]
        
        for selector in date_selectors:
            date_element = soup.select_one(selector)
            if date_element:
                # Try to get the datetime attribute first
                date_str = date_element.get('datetime', '')
                if not date_str:
                    date_str = date_element.get_text().strip()
                
                try:
                    # Try different date formats
                    for date_format in ['%Y-%m-%d', '%B %d, %Y', '%Y-%m-%dT%H:%M:%S.%fZ']:
                        try:
                            parsed_date = datetime.strptime(date_str, date_format)
                            pub_date = parsed_date.strftime('%Y-%m-%d')
                            break
                        except ValueError:
                            continue
                    if pub_date:  # If we successfully parsed a date, break the outer loop
                        break
                except ValueError:
                    logger.warning(f"Could not parse date from {date_str}")
                    continue

        # Generate slug from URL
        slug = url.rstrip('/').split('/')[-1]

        # Extract main content - specifically targeting the txt-rich-long class
        content_element = soup.find('div', class_='txt-rich-long')
        content = ''
        
        if content_element:
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
        
        logger.info(f"Saved blog post: {output_path}")

    def scrape(self):
        logger.info(f"Starting scrape of {self.base_url}")
        
        # Fetch the main page
        html = self.fetch_page(self.base_url)
        if not html:
            return
        
        # Extract blog links
        blog_links = self.extract_blog_links(html)
        logger.info(f"Found {len(blog_links)} blog posts to scrape")
        
        # Process each blog post
        for url in blog_links:
            logger.info(f"Processing blog post: {url}")
            
            # Add delay to be respectful to the server
            time.sleep(2)
            
            html = self.fetch_page(url)
            if not html:
                continue
            
            post_data, content = self.parse_blog_post(url, html)
            filename = post_data['slug']
            self.save_as_markdown(post_data, content, filename)

def main():
    base_url = "https://snyk.io/contributors/liran-tal/"
    scraper = SnykBlogScraper(base_url)
    scraper.scrape()

if __name__ == "__main__":
    main() 