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
import random
import string

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BlogScraper:
    def __init__(self, base_url, output_dir="output", page_delay=3, post_delay=2, max_retries=3):
        self.base_url = base_url
        self.output_dir = output_dir
        self.page_delay = page_delay
        self.post_delay = post_delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "assets/images/blog"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "assets/images/blog_featured"), exist_ok=True)

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
        # Filter out the main blog page URL and only get actual blog post URLs
        blog_elements = soup.find_all('a', href=lambda x: x and '/blog/' in x and x != '/blog/' and not x.endswith('/blog/'))
        
        for blog in blog_elements:
            link = urljoin(self.base_url, blog.get('href'))
            # Additional filter to ensure we don't process the main blog page
            if link != 'https://snyk.io/blog/' and link != 'https://snyk.io/blog':
                blog_links.append(link)
            
        return list(set(blog_links))  # Remove duplicates

    def download_image(self, image_url, post_slug, for_content=False, is_featured=False):
        try:
            response = self.session.get(image_url, headers=self.headers)
            response.raise_for_status()
            
            # Generate clean, short filename: post_slug + random 8-char alphanumeric suffix
            
            # Generate random 8-character alphanumeric suffix
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            
            # Determine file extension from content type or URL
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = '.jpg'
            elif 'png' in content_type:
                extension = '.png'
            elif 'gif' in content_type:
                extension = '.gif'
            elif 'webp' in content_type:
                extension = '.webp'
            else:
                # Fallback: try to extract extension from URL
                url_parts = image_url.split('?')[0].split('#')[0]  # Remove query params and fragments
                extension = os.path.splitext(url_parts)[1]
                if not extension or len(extension) > 5:  # Sanity check
                    extension = '.jpg'  # Default fallback
            
            # Create clean filename
            clean_filename = f"{post_slug}-{suffix}{extension}"
            
            # Choose directory based on image type
            if is_featured:
                image_dir = "assets/images/blog_featured"
                image_path = os.path.join(self.output_dir, image_dir, clean_filename)
            else:
                image_dir = "assets/images/blog"
                image_path = os.path.join(self.output_dir, image_dir, clean_filename)
            
            with open(image_path, 'wb') as f:
                f.write(response.content)
            
            # Return different path format based on usage
            if for_content:
                return f"/images/blog/{clean_filename}"
            else:
                return f"~/assets/images/blog_featured/{clean_filename}" if is_featured else f"~/assets/images/blog/{clean_filename}"
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
                    local_img_path = self.download_image(img_url, slug, for_content=True)
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
                main_image = self.download_image(image_url, slug, for_content=False, is_featured=True)

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
            logger.warning("No pagination element found")
            return None
            
        # Find the "Next" button by looking for various possible titles
        next_button = pagination.find('a', title='Next') or pagination.find('a', title='Next Page')
        if next_button:
            next_url = next_button.get('href')
            if next_url:
                full_next_url = urljoin(self.base_url, next_url)
                logger.info(f"Found next page URL: {full_next_url}")
                return full_next_url
            else:
                logger.warning("Next button found but no href attribute")
        else:
            logger.warning("No 'Next' button found in pagination")
        
        return None

    def save_progress(self, current_page_url, processed_urls):
        """Save scraping progress including all processed blog URLs"""
        with open('scrape_progress.json', 'w') as f:
            json.dump({
                'current_page': current_page_url,
                'processed_urls': list(processed_urls),  # Convert set to list for JSON
                'timestamp': datetime.now().isoformat()
            }, f)

    def load_progress(self):
        """Load previous scraping progress"""
        try:
            with open('scrape_progress.json', 'r') as f:
                data = json.load(f)
                # Convert list back to set for efficient lookups
                data['processed_urls'] = set(data['processed_urls'])
                return data
        except FileNotFoundError:
            return {
                'current_page': None,
                'processed_urls': set(),
                'timestamp': None
            }

    def scrape_page(self, url, processed_urls):
        """Scrape a single page of blog posts"""
        html = self.fetch_page(url)
        if not html:
            return None
        
        # Extract blog links from this page
        blog_links = self.extract_blog_links(html)
        logger.info(f"Found {len(blog_links)} blog posts on page {url}")
        
        # Debug: Log the first few blog links found
        if blog_links:
            logger.info(f"Sample blog links found: {blog_links[:3]}")
        else:
            logger.warning("No blog links found on this page")
        
        # Process each blog post
        for blog_url in blog_links:
            # Skip if we've already processed this URL
            if blog_url in processed_urls:
                logger.info(f"Skipping already processed blog post: {blog_url}")
                continue
                
            logger.info(f"Processing blog post: {blog_url}")
            
            # Add delay to be respectful to the server
            time.sleep(self.post_delay)
            
            blog_html = self.fetch_page(blog_url)
            if not blog_html:
                continue
            
            try:
                post_data, content = self.parse_blog_post(blog_url, blog_html)
                filename = post_data['slug']
                self.save_as_markdown(post_data, content, filename)
                
                # Mark this URL as processed
                processed_urls.add(blog_url)
                
                # Save progress after each successful blog post
                self.save_progress(url, processed_urls)
                
            except Exception as e:
                logger.error(f"Error processing blog post {blog_url}: {e}")
                continue
        
        return html

    def scrape(self):
        """Scrape all pages of blog posts with resume capability"""
        logger.info(f"Starting scrape of {self.base_url}")
        
        # Load previous progress
        progress = self.load_progress()
        processed_urls = progress['processed_urls']
        current_url = progress['current_page'] or self.base_url
        
        if progress['timestamp']:
            logger.info(f"Resuming scrape from page {current_url}")
            logger.info(f"Already processed {len(processed_urls)} blog posts")
        
        page_number = 1
        
        while current_url:
            logger.info(f"Scraping page {page_number}: {current_url}")
            
            # Scrape the current page
            html = self.scrape_page(current_url, processed_urls)
            if not html:
                break
            
            # Get the next page URL
            next_url = self.get_next_page_url(html)
            
            # If there's no next page, we're done
            if not next_url:
                logger.info("No more pages to scrape")
                break
            
            logger.info(f"Moving to next page: {next_url}")
            
            # Add a delay before fetching the next page
            time.sleep(self.page_delay)
            
            # Update for next iteration
            current_url = next_url
            page_number += 1
            
            # Save progress after each page
            self.save_progress(current_url, processed_urls)
        
        logger.info(f"Finished scraping all pages. Total posts processed: {len(processed_urls)}")

class ScrapingStats:
    def __init__(self):
        self.total_posts = 0
        self.failed_posts = 0
        self.total_images = 0
        self.failed_images = 0
        self.start_time = datetime.now()

    def print_summary(self):
        duration = datetime.now() - self.start_time
        logger.info(f"""
Scraping Summary:
----------------
Total Posts: {self.total_posts}
Failed Posts: {self.failed_posts}
Total Images: {self.total_images}
Failed Images: {self.failed_images}
Duration: {duration}
        """)

def main():
    base_url = "https://snyk.io/contributors/liran-tal/"
    scraper = BlogScraper(base_url)
    scraper.scrape()

if __name__ == "__main__":
    main() 