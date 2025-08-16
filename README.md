# Snyk Blog Scraper

A Python script to scrape blog posts from Snyk's contributor pages and save them as markdown files with proper frontmatter.

## Prerequisites

- Python 3.x
- pip (Python package installer)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. Create and activate a virtual environment:
```bash
# Create a new virtual environment
python3 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```

3. Install dependencies:
```bash
python3 -m pip install -r requirements.txt
```

## Usage

Run the scraper:
```bash
python3 scrape_blogs.py
```

The script will:
- Create an `output` directory for the markdown files
- Create an `output/assets/images/blog` directory for content images
- Create an `output/assets/images/blog_featured` directory for featured images
- Scrape all blog posts from the contributor's page
- Save each blog post as a markdown file with proper frontmatter
- Download and save all images locally, updating the references in the markdown
- **Image Paths**: Content images use `/images/blog/` format, featured images use `~/assets/images/blog/` format (maintaining compatibility)

## Output Format

Each blog post will be saved as a markdown file with frontmatter in the following format:

```markdown
---
title: "title"
description: >-
   description
pubDate: '2023-12-28'
categories: ['']
keywords: ['']
slug: slug-for-blog-post
draft: false
tags: ['']
image: ~/assets/images/blog_featured/image.jpg
---

Blog post content...

Images in the content will use `/images/blog/filename.jpg` format, while the frontmatter image field uses `~/assets/images/blog/filename.jpg` (maintaining compatibility with existing systems).
```

## Deactivating the Virtual Environment

When you're done, you can deactivate the virtual environment:
```bash
deactivate
``` 