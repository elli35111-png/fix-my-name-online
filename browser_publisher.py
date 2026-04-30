"""
Browser Automation Publisher for FMNOL Multi-Platform Publishing

Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.

This module provides browser automation for publishing content to platforms
that require browser-based interaction (no API access): Medium, Quora,
Substack, WordPress.com, Reddit, Tumblr, Pinterest, Threads, and Facebook.
"""

import json
import os
import re
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib

from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext, TimeoutError as PlaywrightTimeout

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration & Constants
# ============================================================================

DATA_DIR = Path("/Users/ellicakar/fix_my_name_online/data")
AUTH_DIR = DATA_DIR / "auth"
CREDENTIALS_FILE = DATA_DIR / "credentials.json"

RATE_LIMITS = {
    "medium": {"posts_per_day": 5, "min_hours_between": 4},
    "quora": {"posts_per_day": 10, "min_hours_between": 2},
    "substack": {"posts_per_day": 3, "min_hours_between": 8},
    "wordpress": {"posts_per_day": 10, "min_hours_between": 2},
    "reddit": {"posts_per_day": 5, "min_hours_between": 4},
    "tumblr": {"posts_per_day": 20, "min_hours_between": 1},
    "pinterest": {"posts_per_day": 30, "min_hours_between": 1},
    "threads": {"posts_per_day": 3, "min_hours_between": 6},
    "facebook": {"posts_per_day": 10, "min_hours_between": 2},
}

PLATFORM_URLS = {
    "medium": "https://medium.com",
    "quora": "https://www.quora.com",
    "substack": "https://substack.com",
    "wordpress": "https://wordpress.com",
    "reddit": "https://www.reddit.com",
    "tumblr": "https://www.tumblr.com",
    "pinterest": "https://www.pinterest.com",
    "threads": "https://threads.net",
    "facebook": "https://www.facebook.com",
}


class ContentType(Enum):
    """Supported content types for publishing."""
    MEDIUM_ARTICLE = "medium_article"
    GUEST_BLOG = "guest_blog"
    QUORA_ANSWER = "quora_answer"
    FAQ_ANSWER = "faq_answer"
    NEWSLETTER = "newsletter"
    INDUSTRY_INSIGHT = "industry_insight"
    PRESS_RELEASE = "press_release"
    SEO_ABOUT = "seo_about"
    REDDIT_POST = "reddit_post"
    REDDIT_COMMENT = "reddit_comment"
    BLOG_POST = "blog_post"
    SOCIAL_BIO = "social_bio"
    BRAND_STATEMENT = "brand_statement"
    LINKEDIN_POST = "linkedin_post"
    TWITTER_THREAD = "twitter_thread"


@dataclass
class PublishResult:
    """Structured result from a publish operation."""
    success: bool
    url: str = ""
    error: str = ""
    platform: str = ""
    content_type: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PlatformStatus:
    """Status of a publishing platform."""
    platform: str
    logged_in: bool
    last_post_time: Optional[str] = None
    posts_today: int = 0
    needs_reauth: bool = False
    error: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Utility Functions
# ============================================================================

def ensure_directories():
    """Ensure all required directories exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_DIR.mkdir(parents=True, exist_ok=True)


def load_credentials(customer_id: str) -> dict:
    """Load credentials for a customer from JSON file."""
    ensure_directories()
    cred_file = DATA_DIR / f"credentials_{customer_id}.json"
    
    if cred_file.exists():
        with open(cred_file, 'r') as f:
            return json.load(f)
    
    # Try loading from main credentials file
    if CREDENTIALS_FILE.exists():
        with open(CREDENTIALS_FILE, 'r') as f:
            all_creds = json.load(f)
            return all_creds.get(customer_id, {})
    
    return {}


def save_credentials(customer_id: str, credentials: dict):
    """Save credentials for a customer."""
    ensure_directories()
    cred_file = DATA_DIR / f"credentials_{customer_id}.json"
    
    with open(cred_file, 'w') as f:
        json.dump(credentials, f, indent=2)


def get_auth_state_path(customer_id: str, platform: str) -> Path:
    """Get the path for storing auth state for a platform/customer."""
    ensure_directories()
    return AUTH_DIR / f"{platform}_auth_{customer_id}.json"


def load_auth_state(customer_id: str, platform: str) -> Optional[dict]:
    """Load saved auth state for a platform."""
    auth_path = get_auth_state_path(customer_id, platform)
    
    if auth_path.exists():
        try:
            with open(auth_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load auth state for {platform}: {e}")
    
    return None


def save_auth_state(customer_id: str, platform: str, context: BrowserContext):
    """Save browser auth state to file."""
    auth_path = get_auth_state_path(customer_id, platform)
    
    try:
        state = context.storage_state()
        with open(auth_path, 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"Saved auth state for {platform}")
    except Exception as e:
        logger.error(f"Failed to save auth state for {platform}: {e}")


def convert_markdown_to_html(markdown_text: str) -> str:
    """Convert markdown to HTML for platforms that require it."""
    html = markdown_text
    
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    
    # Bold and italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    
    # Links
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)
    
    # Code blocks
    html = re.sub(r'```(.+?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
    html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
    
    # Paragraphs
    html = re.sub(r'\n\n', '</p><p>', html)
    html = '<p>' + html + '</p>'
    
    # Lists
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'^(\d+)\. (.+)$', r'<li>\2</li>', html, flags=re.MULTILINE)
    
    return html


def extract_slug_from_url(url: str) -> str:
    """Extract slug from various platform URLs."""
    patterns = [
        r'/([^/]+?)$',
        r'@([^/]+)',
        r'p/([a-zA-Z0-9]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return ""


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """Retry a function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)


# ============================================================================
# Content Adaptation Functions
# ============================================================================

def adapt_for_medium(content: dict) -> dict:
    """Adapt content for Medium platform."""
    adapted = content.copy()
    adapted['html_content'] = convert_markdown_to_html(content.get('content', ''))
    adapted['excerpt'] = content.get('content', '')[:200] + '...' if len(content.get('content', '')) > 200 else content.get('content', '')
    return adapted


def adapt_for_quora(content: dict) -> dict:
    """Adapt content for Quora (Q&A format)."""
    adapted = content.copy()
    # Extract or generate question from title
    title = content.get('title', '')
    if '?' not in title:
        title = f"What is {title}?"
    adapted['question'] = title
    adapted['answer'] = content.get('content', '')
    return adapted


def adapt_for_substack(content: dict) -> dict:
    """Adapt content for Substack newsletter."""
    adapted = content.copy()
    adapted['email_subject'] = content.get('title', '')
    adapted['preview_text'] = content.get('content', '')[:150] + '...'
    return adapted


def adapt_for_wordpress(content: dict) -> dict:
    """Adapt content for WordPress."""
    adapted = content.copy()
    adapted['html_content'] = convert_markdown_to_html(content.get('content', ''))
    return adapted


def adapt_for_reddit(content: dict) -> dict:
    """Adapt content for Reddit (community style)."""
    adapted = content.copy()
    # Reddit prefers shorter, conversational content
    adapted['reddit_title'] = content.get('title', '')
    adapted['reddit_body'] = content.get('content', '')
    return adapted


def adapt_for_tumblr(content: dict) -> dict:
    """Adapt content for Tumblr."""
    adapted = content.copy()
    adapted['html_content'] = convert_markdown_to_html(content.get('content', ''))
    return adapted


def adapt_for_pinterest(content: dict) -> dict:
    """Adapt content for Pinterest."""
    adapted = content.copy()
    adapted['pin_description'] = f"{content.get('title', '')} - {content.get('content', '')[:500]}"
    return adapted


def adapt_content(content: dict, platform: str) -> dict:
    """Adapt content format for specific platform."""
    adaptors = {
        "medium": adapt_for_medium,
        "quora": adapt_for_quora,
        "substack": adapt_for_substack,
        "wordpress": adapt_for_wordpress,
        "reddit": adapt_for_reddit,
        "tumblr": adapt_for_tumblr,
        "pinterest": adapt_for_pinterest,
    }
    
    adaptor = adaptors.get(platform)
    if adaptor:
        return adaptor(content)
    
    return content


# ============================================================================
# Base Browser Publisher Class
# ============================================================================

class BaseBrowserPublisher(ABC):
    """
    Abstract base class for browser-based publishing.
    
    All platform publishers inherit from this class and implement
    platform-specific login and publish methods.
    """
    
    def __init__(
        self,
        customer_id: str,
        credentials: dict,
        headless: bool = True,
        user_agent: Optional[str] = None
    ):
        """
        Initialize the browser publisher.
        
        Args:
            customer_id: Unique identifier for the customer
            credentials: Dict containing platform credentials
            headless: Whether to run browser in headless mode
            user_agent: Custom user agent string
        """
        self.customer_id = customer_id
        self.credentials = credentials
        self.headless = headless
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.platform_name = self.__class__.__name__.replace("Publisher", "").lower()
        
        # Rate limiting tracking
        self.last_post_time: Optional[datetime] = None
        self.posts_today: int = 0
        self.last_reset_date: Optional[str] = None
    
    @property
    def platform_url(self) -> str:
        """Get the base URL for this platform."""
        return PLATFORM_URLS.get(self.platform_name, "")
    
    @property
    def rate_limit(self) -> dict:
        """Get rate limit settings for this platform."""
        return RATE_LIMITS.get(self.platform_name, {"posts_per_day": 10, "min_hours_between": 2})
    
    def _get_auth_state_path(self) -> Path:
        """Get the path for storing auth state."""
        return get_auth_state_path(self.customer_id, self.platform_name)
    
    def _load_saved_auth_state(self) -> Optional[dict]:
        """Load saved authentication state."""
        return load_auth_state(self.customer_id, self.platform_name)
    
    def _save_auth_state(self):
        """Save current browser authentication state."""
        if self.context:
            save_auth_state(self.customer_id, self.platform_name, self.context)
    
    def _init_browser(self):
        """Initialize Playwright browser."""
        if self.browser is None:
            playwright = sync_playwright().start()
            self._playwright = playwright
            self.browser = playwright.chromium.launch(headless=self.headless)
    
    def _create_context(self) -> BrowserContext:
        """Create a new browser context."""
        self._init_browser()
        
        context_options = {
            "user_agent": self.user_agent,
            "viewport": {"width": 1280, "height": 720},
            "locale": "en-US",
        }
        
        # Try to load saved auth state
        saved_state = self._load_saved_auth_state()
        if saved_state:
            context_options["storage_state"] = saved_state
        
        self.context = self.browser.new_context(**context_options)
        self.page = self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(30000)
        
        return self.context
    
    def _close_browser(self):
        """Close browser and cleanup."""
        if self.context:
            try:
                self.context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")
            self.context = None
            self.page = None
        
        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self.browser = None
        
        if hasattr(self, '_playwright'):
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
    
    def _check_rate_limit(self) -> tuple[bool, str]:
        """Check if we're within rate limits."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Reset daily counter if new day
        if self.last_reset_date != today:
            self.posts_today = 0
            self.last_reset_date = today
        
        # Check posts per day limit
        if self.posts_today >= self.rate_limit["posts_per_day"]:
            return False, f"Daily post limit ({self.rate_limit['posts_per_day']}) reached"
        
        # Check minimum hours between posts
        if self.last_post_time:
            hours_since_last = (datetime.now() - self.last_post_time).total_seconds() / 3600
            if hours_since_last < self.rate_limit["min_hours_between"]:
                remaining = self.rate_limit["min_hours_between"] - hours_since_last
                return False, f"Must wait {remaining:.1f} more hours between posts"
        
        return True, ""
    
    def _update_rate_limit(self):
        """Update rate limiting counters after a successful post."""
        self.posts_today += 1
        self.last_post_time = datetime.now()
    
    def _wait_for_selector(self, selector: str, timeout: int = 30000, state: str = "visible"):
        """Wait for an element to appear."""
        if self.page:
            self.page.wait_for_selector(selector, timeout=timeout, state=state)
    
    def _click_safe(self, selector: str, retries: int = 3):
        """Click an element with retry logic."""
        for attempt in range(retries):
            try:
                if self.page:
                    self.page.click(selector)
                    return True
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(1)
        return False
    
    def _fill_safe(self, selector: str, value: str, clear_first: bool = True):
        """Fill an input field safely."""
        if self.page:
            if clear_first:
                self.page.fill(selector, "")
            self.page.fill(selector, value)
    
    def _handle_captcha(self) -> bool:
        """Detect and handle captcha. Returns True if captcha was detected."""
        if self.page:
            # Common captcha indicators
            captcha_indicators = [
                "captcha",
                "verify you are human",
                "i'm not a robot",
                "prove you're not a robot",
                "recaptcha",
            ]
            
            page_content = self.page.content().lower()
            for indicator in captcha_indicators:
                if indicator in page_content:
                    logger.warning(f"CAPTCHA detected on {self.platform_name}!")
                    return True
        
        return False
    
    # ========================================================================
    # Public API Methods
    # ========================================================================
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._close_browser()
        return False
    
    @abstractmethod
    def login(self) -> bool:
        """
        Log in to the platform.
        
        Returns:
            True if login successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def is_logged_in(self) -> bool:
        """
        Check if currently logged in.
        
        Returns:
            True if logged in, False otherwise.
        """
        pass
    
    @abstractmethod
    def publish(self, content: dict) -> PublishResult:
        """
        Publish content to the platform.
        
        Args:
            content: Dict containing title, content, tags, etc.
            
        Returns:
            PublishResult with success status, URL, and any error message.
        """
        pass
    
    def get_published_url(self) -> str:
        """
        Get the URL of the last published content.
        
        Returns:
            URL string of published content.
        """
        if self.page:
            return self.page.url
        return ""
    
    def cleanup(self):
        """Cleanup browser resources."""
        self._close_browser()


# ============================================================================
# Medium Publisher
# ============================================================================

class MediumPublisher(BaseBrowserPublisher):
    """Publisher for Medium.com articles."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "medium"
    
    def login(self) -> bool:
        """Log in to Medium."""
        try:
            self._create_context()
            
            # Check if already logged in
            if self.is_logged_in():
                logger.info("Already logged in to Medium")
                return True
            
            # Navigate to login page
            self.page.goto(f"{self.platform_url}/login")
            time.sleep(2)
            
            # Fill login form
            email = self.credentials.get("email", "")
            password = self.credentials.get("password", "")
            
            if not email or not password:
                logger.error("Missing Medium credentials")
                return False
            
            # Find and fill email field
            self.page.fill('input[name="email"]', email)
            time.sleep(1)
            
            # Click continue or next
            self._click_safe('button[type="submit"]')
            time.sleep(2)
            
            # Fill password
            self.page.fill('input[name="password"]', password)
            time.sleep(1)
            
            # Submit
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            # Check for captcha
            if self._handle_captcha():
                return False
            
            # Verify login
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Medium")
                return True
            
            logger.error("Failed to log in to Medium")
            return False
            
        except Exception as e:
            logger.error(f"Medium login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Medium."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/me", wait_until="domcontentloaded")
            time.sleep(2)
            
            # Check for profile avatar or sign in button
            page_content = self.page.content()
            
            # Look for signed-in indicators
            signed_in_indicators = [
                "data-testid=\"headerNav\"",
                "class=\"avatar",
                "Sign out",
            ]
            
            for indicator in signed_in_indicators:
                if indicator in page_content:
                    return True
            
            # Check URL - should not redirect to login
            if "/login" in self.page.url:
                return False
            
            return "profile" in self.page.url or "/me" in self.page.url
            
        except Exception as e:
            logger.warning(f"Error checking Medium login status: {e}")
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish an article to Medium."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "medium_article")
        )
        
        try:
            # Check rate limit
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            # Ensure logged in
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Medium"
                    return result
            
            # Navigate to new story page
            self.page.goto(f"{self.platform_url}/new-story")
            time.sleep(3)
            
            # Adapt content for Medium
            adapted = adapt_for_medium(content)
            
            # Fill title
            title = content.get("title", "")
            title_selector = '[data-testid="titleField"]'
            if not self.page.query_selector(title_selector):
                title_selector = 'div[data-offset-key]'
            
            self._fill_safe(title_selector, title)
            time.sleep(1)
            
            # Fill content (main body)
            # Medium uses a contenteditable div
            content_selector = '[data-testid="postField"]'
            if not self.page.query_selector(content_selector):
                content_selector = 'article'
            
            html_content = adapted.get("html_content", convert_markdown_to_html(content.get("content", "")))
            self._fill_safe(content_selector, html_content)
            time.sleep(1)
            
            # Add tags if provided
            tags = content.get("tags", [])
            if tags:
                tag_selector = '[data-testid="tagInputField"]'
                if self.page.query_selector(tag_selector):
                    for tag in tags[:5]:  # Medium allows up to 5 tags
                        self._fill_safe(tag_selector, tag)
                        self._click_safe(tag_selector)
                        time.sleep(0.5)
            
            # Click publish button
            publish_button_selectors = [
                '[data-testid="publishButton"]',
                'button:has-text("Publish")',
                'div:has-text("Publish")',
            ]
            
            for selector in publish_button_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            # Handle publish confirmation
            confirm_selectors = [
                'button:has-text("Publish Now")',
                'button:has-text("Publish")',
                '[data-testid="confirm"]',
            ]
            
            for selector in confirm_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            # Extract published URL
            published_url = self.get_published_url()
            
            if published_url and "/new-story" not in published_url:
                result.success = True
                result.url = published_url
                self._update_rate_limit()
                logger.info(f"Published to Medium: {published_url}")
            else:
                result.error = "Failed to get published URL"
            
        except Exception as e:
            logger.error(f"Medium publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


# ============================================================================
# Quora Publisher
# ============================================================================

class QuoraPublisher(BaseBrowserPublisher):
    """Publisher for Quora answers."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "quora"
    
    def login(self) -> bool:
        """Log in to Quora."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to Quora")
                return True
            
            # Navigate to login
            self.page.goto(f"{self.platform_url}/")
            time.sleep(2)
            
            # Click login button if present
            login_selectors = [
                'a:has-text("Log in")',
                'button:has-text("Log in")',
                '[data-testid="Login"]',
            ]
            
            for selector in login_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(2)
            
            email = self.credentials.get("email", "")
            password = self.credentials.get("password", "")
            
            if not email or not password:
                logger.error("Missing Quora credentials")
                return False
            
            # Fill email
            self.page.fill('input[type="email"], input[name="email"]', email)
            time.sleep(1)
            
            # Fill password
            self.page.fill('input[type="password"], input[name="password"]', password)
            time.sleep(1)
            
            # Submit
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            if self._handle_captcha():
                return False
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Quora")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Quora login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Quora."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            
            page_content = self.page.content()
            
            # Look for logged-in indicators
            logged_in_indicators = [
                "data-testid=\"userMenu\"",
                "profile photo",
                "Answer",
                "Spaces",
            ]
            
            for indicator in logged_in_indicators:
                if indicator in page_content:
                    return True
            
            return "/login" not in self.page.url
            
        except Exception as e:
            logger.warning(f"Error checking Quora login status: {e}")
            return False
    
    def _search_for_question(self, keyword: str) -> Optional[str]:
        """Search for a relevant question on Quora."""
        try:
            # Use search
            search_url = f"{self.platform_url}/search?q={keyword.replace(' ', '+')}"
            self.page.goto(search_url)
            time.sleep(3)
            
            # Find first question link
            question_selectors = [
                'a[href*="/"]',
                '.qu-word--passive',
                '[data-testid="search-result"] a',
            ]
            
            for selector in question_selectors:
                elements = self.page.query_selector_all(selector)
                for elem in elements[:10]:
                    href = elem.get_attribute("href")
                    if href and "/" in href and "search" not in href:
                        return f"{self.platform_url}{href}" if href.startswith("/") else href
            
            return None
            
        except Exception as e:
            logger.warning(f"Error searching for question: {e}")
            return None
    
    def publish(self, content: dict) -> PublishResult:
        """Publish an answer to Quora."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "quora_answer")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Quora"
                    return result
            
            # Get question to answer
            keyword = content.get("keyword", content.get("title", ""))
            question_url = self._search_for_question(keyword)
            
            if not question_url:
                # Try to post a new question + answer
                question_url = f"{self.platform_url}/"
            
            self.page.goto(question_url)
            time.sleep(3)
            
            # Adapt content for Quora
            adapted = adapt_for_quora(content)
            
            # Look for answer box
            answer_box_selectors = [
                '[data-testid="answer-input-box"]',
                'div[contenteditable="true"]',
                'textarea[name="answer"]',
                '.answer_input',
            ]
            
            answer_filled = False
            for selector in answer_box_selectors:
                if self.page.query_selector(selector):
                    self._fill_safe(selector, adapted.get("answer", content.get("content", "")))
                    answer_filled = True
                    break
            
            if not answer_filled:
                # Try clicking "Add Answer" button
                add_answer_selectors = [
                    'button:has-text("Add Answer")',
                    'span:has-text("Add Answer")',
                ]
                
                for selector in add_answer_selectors:
                    if self.page.query_selector(selector):
                        self._click_safe(selector)
                        time.sleep(2)
                        
                        for ans_selector in answer_box_selectors:
                            if self.page.query_selector(ans_selector):
                                self._fill_safe(ans_selector, adapted.get("answer", content.get("content", "")))
                                answer_filled = True
                                break
                        break
            
            time.sleep(1)
            
            # Submit answer
            submit_selectors = [
                'button:has-text("Submit")',
                'button:has-text("Post Answer")',
                '[data-testid="submit"]',
            ]
            
            for selector in submit_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            # Get URL
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"Quora publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


# ============================================================================
# Substack Publisher
# ============================================================================

class SubstackPublisher(BaseBrowserPublisher):
    """Publisher for Substack newsletters."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "substack"
    
    def login(self) -> bool:
        """Log in to Substack."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to Substack")
                return True
            
            self.page.goto(f"{self.platform_url}/login")
            time.sleep(2)
            
            email = self.credentials.get("email", "")
            password = self.credentials.get("password", "")
            
            if not email or not password:
                logger.error("Missing Substack credentials")
                return False
            
            # Fill login form
            self.page.fill('input[type="email"]', email)
            time.sleep(1)
            
            # Click continue or next
            continue_btn = self.page.query_selector('button[type="submit"]')
            if continue_btn:
                continue_btn.click()
            
            time.sleep(2)
            
            # Fill password
            self.page.fill('input[type="password"]', password)
            time.sleep(1)
            
            # Submit
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            if self._handle_captcha():
                return False
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Substack")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Substack login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Substack."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/dashboard", wait_until="domcontentloaded")
            time.sleep(2)
            
            # Look for dashboard elements
            page_content = self.page.content()
            
            logged_in_indicators = [
                "dashboard",
                "New post",
                "Subscribers",
                "Settings",
            ]
            
            for indicator in logged_in_indicators:
                if indicator in page_content:
                    return True
            
            return "/login" not in self.page.url
            
        except Exception as e:
            logger.warning(f"Error checking Substack login status: {e}")
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish a newsletter to Substack."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "newsletter")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Substack"
                    return result
            
            # Navigate to new post
            self.page.goto(f"{self.platform_url}/dashboard/new/post")
            time.sleep(3)
            
            # Adapt content
            adapted = adapt_for_substack(content)
            
            # Fill title
            title_selector = 'input[name="title"], input[placeholder*="Title"]'
            self._fill_safe(title_selector, content.get("title", ""))
            time.sleep(1)
            
            # Fill content
            content_selector = '[data-testid="post-editor"]'
            if not self.page.query_selector(content_selector):
                content_selector = 'div[contenteditable="true"]'
            
            self._fill_safe(content_selector, content.get("content", ""))
            time.sleep(1)
            
            # Add tags if available
            tags = content.get("tags", [])
            if tags:
                tag_selector = 'input[placeholder*="tag" i], input[name="tags"]'
                if self.page.query_selector(tag_selector):
                    for tag in tags[:5]:
                        self._fill_safe(tag_selector, tag)
                        self._click_safe(tag_selector)
                        time.sleep(0.5)
            
            # Click publish button
            publish_selectors = [
                'button:has-text("Publish")',
                'button:has-text("Publish now")',
                '[data-testid="publish"]',
            ]
            
            for selector in publish_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            # Confirm publish if needed
            confirm_selectors = [
                'button:has-text("Confirm")',
                'button:has-text("Yes, publish")',
            ]
            
            for selector in confirm_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"Substack publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


# ============================================================================
# WordPress.com Publisher
# ============================================================================

class WordPressComPublisher(BaseBrowserPublisher):
    """Publisher for WordPress.com sites."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "wordpress"
        self.site = credentials.get("site", "")
    
    def login(self) -> bool:
        """Log in to WordPress.com."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to WordPress")
                return True
            
            self.page.goto(f"{self.platform_url}/log-in")
            time.sleep(2)
            
            email = self.credentials.get("email", "")
            password = self.credentials.get("password", "")
            
            if not email or not password:
                logger.error("Missing WordPress credentials")
                return False
            
            # Fill login form
            self.page.fill('input[type="text"], input[name="usernameOrEmail"]', email)
            time.sleep(1)
            
            self._click_safe('button[type="submit"]')
            time.sleep(2)
            
            # Fill password
            self.page.fill('input[type="password"]', password)
            time.sleep(1)
            
            # Submit
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            if self._handle_captcha():
                return False
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to WordPress")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"WordPress login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to WordPress."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            
            page_content = self.page.content()
            
            logged_in_indicators = [
                "wp-admin",
                "gutenberg",
                "My Site",
                "reader",
            ]
            
            for indicator in logged_in_indicators:
                if indicator in page_content:
                    return True
            
            return "/log-in" not in self.page.url
            
        except Exception as e:
            logger.warning(f"Error checking WordPress login status: {e}")
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish a post to WordPress."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "guest_blog")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to WordPress"
                    return result
            
            # Navigate to new post
            base_url = f"https://{self.site}.wordpress.com" if self.site else self.platform_url
            self.page.goto(f"{base_url}/wp-admin/post-new.php")
            time.sleep(3)
            
            # Fill title
            title_selector = '#title'
            self._fill_safe(title_selector, content.get("title", ""))
            time.sleep(1)
            
            # Fill content (Gutenberg editor)
            content_selector = '.block-editor-default-block-appender'
            if not self.page.query_selector(content_selector):
                content_selector = 'textarea[name="content"]'
            
            adapted = adapt_for_wordpress(content)
            html_content = adapted.get("html_content", convert_markdown_to_html(content.get("content", "")))
            self._fill_safe(content_selector, html_content)
            time.sleep(1)
            
            # Click publish
            publish_selectors = [
                'button:has-text("Publish")',
                '#publish',
                '.editor-post-publish-button',
            ]
            
            for selector in publish_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"WordPress publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


# ============================================================================
# Reddit Publisher
# ============================================================================

class RedditPublisher(BaseBrowserPublisher):
    """Publisher for Reddit posts."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "reddit"
        self.subreddit = credentials.get("subreddit", "")
    
    def login(self) -> bool:
        """Log in to Reddit."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to Reddit")
                return True
            
            self.page.goto(f"{self.platform_url}/login")
            time.sleep(2)
            
            username = self.credentials.get("username", "")
            password = self.credentials.get("password", "")
            
            if not username or not password:
                logger.error("Missing Reddit credentials")
                return False
            
            # Fill username
            self.page.fill('input[name="username"]', username)
            time.sleep(1)
            
            # Fill password
            self.page.fill('input[name="password"]', password)
            time.sleep(1)
            
            # Submit
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            if self._handle_captcha():
                logger.warning("Reddit may require captcha")
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Reddit")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Reddit login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Reddit."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            
            page_content = self.page.content()
            
            logged_in_indicators = [
                'data-testid="user-menu"',
                "Logout",
                "Profile",
                "/user/",
            ]
            
            for indicator in logged_in_indicators:
                if indicator in page_content:
                    return True
            
            return "/login" not in self.page.url
            
        except Exception as e:
            logger.warning(f"Error checking Reddit login status: {e}")
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish a post to Reddit."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "reddit_post")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Reddit"
                    return result
            
            # Navigate to subreddit or home
            subreddit = content.get("subreddit", self.subreddit)
            if subreddit:
                self.page.goto(f"{self.platform_url}/r/{subreddit}")
            else:
                self.page.goto(f"{self.platform_url}/")
            
            time.sleep(3)
            
            # Click create post button
            create_post_selectors = [
                'a:has-text("Create Post")',
                'button:has-text("Create Post")',
                '[data-testid="create-post"]',
            ]
            
            for selector in create_post_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(2)
            
            # Adapt content
            adapted = adapt_for_reddit(content)
            
            # Fill title
            title_selector = 'input[name="title"], input[placeholder*="title" i]'
            self._fill_safe(title_selector, adapted.get("reddit_title", content.get("title", "")))
            time.sleep(1)
            
            # Fill body (text post)
            body_selectors = [
                'div[contenteditable="true"]',
                'textarea[name="text"]',
                'textarea[placeholder*="body" i]',
            ]
            
            for selector in body_selectors:
                if self.page.query_selector(selector):
                    self._fill_safe(selector, adapted.get("reddit_body", content.get("content", "")))
                    break
            
            time.sleep(1)
            
            # Submit
            submit_selectors = [
                'button:has-text("Post")',
                'button:has-text("Submit")',
                '[data-testid="submit-form"]',
            ]
            
            for selector in submit_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"Reddit publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


# ============================================================================
# Additional Platform Publishers
# ============================================================================

class TumblrPublisher(BaseBrowserPublisher):
    """Publisher for Tumblr posts."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "tumblr"
    
    def login(self) -> bool:
        """Log in to Tumblr."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to Tumblr")
                return True
            
            self.page.goto(f"{self.platform_url}/login")
            time.sleep(2)
            
            email = self.credentials.get("email", "")
            password = self.credentials.get("password", "")
            
            if not email or not password:
                logger.error("Missing Tumblr credentials")
                return False
            
            self.page.fill('input[name="email"]', email)
            time.sleep(1)
            self.page.fill('input[name="password"]', password)
            time.sleep(1)
            
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Tumblr")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Tumblr login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Tumblr."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            
            return "/login" not in self.page.url
            
        except Exception:
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish a post to Tumblr."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "blog_post")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Tumblr"
                    return result
            
            self.page.goto(f"{self.platform_url}/new/text")
            time.sleep(3)
            
            adapted = adapt_for_tumblr(content)
            
            # Fill title
            title_selector = 'input[name="title"], input[id="post_title"]'
            self._fill_safe(title_selector, content.get("title", ""))
            time.sleep(1)
            
            # Fill content
            content_selector = 'textarea[name="body"], div[contenteditable="true"]'
            html_content = adapted.get("html_content", content.get("content", ""))
            self._fill_safe(content_selector, html_content)
            time.sleep(1)
            
            # Add tags
            tags = content.get("tags", [])
            if tags:
                tag_selector = 'input[name="tags"]'
                self._fill_safe(tag_selector, ",".join(tags))
                time.sleep(1)
            
            # Post
            post_selectors = [
                'button:has-text("Post")',
                'button:has-text("Publish")',
            ]
            
            for selector in post_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"Tumblr publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


class PinterestPublisher(BaseBrowserPublisher):
    """Publisher for Pinterest pins."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "pinterest"
    
    def login(self) -> bool:
        """Log in to Pinterest."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to Pinterest")
                return True
            
            self.page.goto(f"{self.platform_url}/login")
            time.sleep(2)
            
            email = self.credentials.get("email", "")
            password = self.credentials.get("password", "")
            
            if not email or not password:
                logger.error("Missing Pinterest credentials")
                return False
            
            self.page.fill('input[type="email"], input[name="email"]', email)
            time.sleep(1)
            self.page.fill('input[type="password"], input[name="password"]', password)
            time.sleep(1)
            
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Pinterest")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Pinterest login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Pinterest."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            
            return "/login" not in self.page.url
            
        except Exception:
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish a pin to Pinterest."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "social_bio")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Pinterest"
                    return result
            
            self.page.goto(f"{self.platform_url}/pinbuilder")
            time.sleep(3)
            
            adapted = adapt_for_pinterest(content)
            
            # Fill description
            desc_selector = 'textarea[name="description"], textarea[id="pin-draft-description"]'
            self._fill_safe(desc_selector, adapted.get("pin_description", content.get("content", "")))
            time.sleep(1)
            
            # Add link if provided
            if content.get("url"):
                link_selector = 'input[name="link"], input[id="pin-draft-link"]'
                self._fill_safe(link_selector, content.get("url"))
                time.sleep(1)
            
            # Post
            post_selectors = [
                'button:has-text("Save")',
                'button:has-text("Publish")',
            ]
            
            for selector in post_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"Pinterest publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


class ThreadsPublisher(BaseBrowserPublisher):
    """Publisher for Threads.net posts."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "threads"
    
    def login(self) -> bool:
        """Log in to Threads via Instagram."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to Threads")
                return True
            
            self.page.goto(f"{self.platform_url}/")
            time.sleep(2)
            
            # Look for login button
            login_selectors = [
                'a:has-text("Log in")',
                'button:has-text("Log in with Instagram")',
            ]
            
            for selector in login_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(2)
            
            username = self.credentials.get("username", "")
            password = self.credentials.get("password", "")
            
            if not username or not password:
                logger.error("Missing Threads/Instagram credentials")
                return False
            
            self.page.fill('input[name="username"]', username)
            time.sleep(1)
            self.page.fill('input[name="password"]', password)
            time.sleep(1)
            
            self._click_safe('button[type="submit"]')
            time.sleep(3)
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Threads")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Threads login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Threads."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            
            return "/login" not in self.page.url
            
        except Exception:
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish a post to Threads."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "social_bio")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Threads"
                    return result
            
            self.page.goto(f"{self.platform_url}/")
            time.sleep(3)
            
            # Look for create/new post button
            create_selectors = [
                'button:has-text("New post")',
                '[aria-label="New post"]',
                'a:has-text("Create")',
            ]
            
            for selector in create_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(2)
            
            # Fill content
            content_selector = 'div[contenteditable="true"][data-lexical-editor="true"]'
            if not self.page.query_selector(content_selector):
                content_selector = 'textarea'
            
            self._fill_safe(content_selector, content.get("content", content.get("title", "")))
            time.sleep(1)
            
            # Post
            post_selectors = [
                'button:has-text("Post")',
                'button:has-text("Publish")',
            ]
            
            for selector in post_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"Threads publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


class FacebookPublisher(BaseBrowserPublisher):
    """Publisher for Facebook posts."""
    
    def __init__(self, customer_id: str, credentials: dict, headless: bool = True):
        super().__init__(customer_id, credentials, headless)
        self.platform_name = "facebook"
        self.page_id = credentials.get("page_id", "")
    
    def login(self) -> bool:
        """Log in to Facebook."""
        try:
            self._create_context()
            
            if self.is_logged_in():
                logger.info("Already logged in to Facebook")
                return True
            
            self.page.goto(f"{self.platform_url}/login")
            time.sleep(2)
            
            email = self.credentials.get("email", "")
            password = self.credentials.get("password", "")
            
            if not email or not password:
                logger.error("Missing Facebook credentials")
                return False
            
            self.page.fill('input[name="email"]', email)
            time.sleep(1)
            self.page.fill('input[name="pass"]', password)
            time.sleep(1)
            
            self._click_safe('button[name="login"], button[type="submit"]')
            time.sleep(3)
            
            if self._handle_captcha():
                logger.warning("Facebook captcha may be required")
            
            if self.is_logged_in():
                self._save_auth_state()
                logger.info("Successfully logged in to Facebook")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Facebook login error: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Check if logged in to Facebook."""
        try:
            if not self.page:
                return False
            
            self.page.goto(f"{self.platform_url}/", wait_until="domcontentloaded")
            time.sleep(2)
            
            return "/login" not in self.page.url and "login" not in self.page.url
            
        except Exception:
            return False
    
    def publish(self, content: dict) -> PublishResult:
        """Publish a post to Facebook."""
        result = PublishResult(
            platform=self.platform_name,
            content_type=content.get("content_type", "brand_statement")
        )
        
        try:
            can_proceed, limit_msg = self._check_rate_limit()
            if not can_proceed:
                result.error = limit_msg
                return result
            
            if not self.is_logged_in():
                if not self.login():
                    result.error = "Failed to login to Facebook"
                    return result
            
            # Navigate to page or profile
            if self.page_id:
                self.page.goto(f"{self.platform_url}/{self.page_id}")
            else:
                self.page.goto(f"{self.platform_url}/")
            
            time.sleep(3)
            
            # Look for create post box
            create_selectors = [
                'div[data-testid="cometcomposer"]',
                'span:has-text("Write something")',
                'div[aria-label="Create post"]',
            ]
            
            for selector in create_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(2)
            
            # Fill content
            content_selector = 'div[contenteditable="true"][data-lexical-editor="true"]'
            if not self.page.query_selector(content_selector):
                content_selector = 'textarea[name="xhpc_message"]'
            
            post_content = f"{content.get('title', '')}\n\n{content.get('content', '')}"
            self._fill_safe(content_selector, post_content)
            time.sleep(1)
            
            # Post
            post_selectors = [
                'button:has-text("Post")',
                'div:has-text("Post")',
                '[data-testid="react-composer-post-button"]',
            ]
            
            for selector in post_selectors:
                if self.page.query_selector(selector):
                    self._click_safe(selector)
                    break
            
            time.sleep(3)
            
            result.success = True
            result.url = self.get_published_url()
            self._update_rate_limit()
            
        except Exception as e:
            logger.error(f"Facebook publish error: {e}")
            result.error = str(e)
        
        finally:
            self._close_browser()
        
        return result


# ============================================================================
# Publisher Factory
# ============================================================================

def get_publisher(
    platform: str,
    customer_id: str,
    credentials: dict,
    headless: bool = True
) -> Optional[BaseBrowserPublisher]:
    """Get a publisher instance for the specified platform."""
    publishers = {
        "medium": MediumPublisher,
        "quora": QuoraPublisher,
        "substack": SubstackPublisher,
        "wordpress": WordPressComPublisher,
        "reddit": RedditPublisher,
        "tumblr": TumblrPublisher,
        "pinterest": PinterestPublisher,
        "threads": ThreadsPublisher,
        "facebook": FacebookPublisher,
    }
    
    publisher_class = publishers.get(platform.lower())
    if publisher_class:
        return publisher_class(customer_id, credentials, headless)
    
    return None


# ============================================================================
# Publishing Pipeline
# ============================================================================

class PublishingPipeline:
    """
    Orchestrates publishing content across all configured platforms.
    
    This class manages the publishing workflow, including credential loading,
    platform status checking, bulk publishing with staggering, and error handling.
    """
    
    def __init__(
        self,
        customer_id: str,
        credentials: Optional[dict] = None,
        headless: bool = True
    ):
        """
        Initialize the publishing pipeline.
        
        Args:
            customer_id: Unique identifier for the customer
            credentials: Optional credentials dict (will load from file if not provided)
            headless: Whether to run browsers in headless mode
        """
        self.customer_id = customer_id
        self.headless = headless
        
        # Load credentials
        if credentials:
            self.credentials = credentials
        else:
            self.credentials = load_credentials(customer_id)
        
        # Initialize publishers
        self.publishers: Dict[str, BaseBrowserPublisher] = {}
        
        # Status tracking
        self.last_publish_times: Dict[str, datetime] = {}
        
        logger.info(f"Initialized PublishingPipeline for customer: {customer_id}")
    
    def _get_publisher(self, platform: str) -> Optional[BaseBrowserPublisher]:
        """Get or create a publisher for the specified platform."""
        if platform not in self.publishers:
            platform_creds = self.credentials.get(platform, {})
            if not platform_creds:
                logger.warning(f"No credentials found for platform: {platform}")
                return None
            
            publisher = get_publisher(platform, self.customer_id, platform_creds, self.headless)
            if publisher:
                self.publishers[platform] = publisher
        
        return self.publishers.get(platform)
    
    def publish_article(self, content: dict, platforms: List[str]) -> dict:
        """
        Publish a single content piece to multiple platforms.
        
        Args:
            content: Dict containing title, content, content_type, tags, url
            platforms: List of platform names to publish to
            
        Returns:
            Dict with total, successful, failed counts and detailed results
        """
        results = {
            "total": len(platforms),
            "successful": [],
            "failed": [],
            "results": [],
        }
        
        for platform in platforms:
            publisher = self._get_publisher(platform)
            
            if not publisher:
                results["failed"].append(platform)
                results["results"].append({
                    "platform": platform,
                    "success": False,
                    "error": "Publisher not available or missing credentials",
                })
                continue
            
            try:
                # Adapt content for platform
                adapted_content = adapt_content(content, platform)
                
                # Publish
                with publisher:
                    publish_result = publisher.publish(adapted_content)
                
                # Record result
                results["results"].append({
                    "platform": platform,
                    "success": publish_result.success,
                    "url": publish_result.url,
                    "error": publish_result.error,
                })
                
                if publish_result.success:
                    results["successful"].append(platform)
                    self.last_publish_times[platform] = datetime.now()
                else:
                    results["failed"].append(platform)
                
            except Exception as e:
                logger.error(f"Error publishing to {platform}: {e}")
                results["failed"].append(platform)
                results["results"].append({
                    "platform": platform,
                    "success": False,
                    "error": str(e),
                })
        
        return results
    
    def bulk_publish(
        self,
        contents: List[dict],
        platforms: List[str],
        stagger_hours: int = 2
    ) -> dict:
        """
        Publish multiple content pieces with staggered timing.
        
        Args:
            contents: List of content dicts to publish
            platforms: List of platforms to publish to
            stagger_hours: Minimum hours between posts to same platform
            
        Returns:
            Dict with overall results and individual content results
        """
        overall_results = {
            "total_contents": len(contents),
            "total_platforms": len(platforms),
            "successful": 0,
            "failed": 0,
            "content_results": [],
        }
        
        for i, content in enumerate(contents):
            logger.info(f"Publishing content {i + 1}/{len(contents)}")
            
            # Check if we need to wait for rate limits
            for platform in platforms:
                if platform in self.last_publish_times:
                    last_time = self.last_publish_times[platform]
                    rate_limit = RATE_LIMITS.get(platform, {}).get("min_hours_between", 2)
                    hours_since = (datetime.now() - last_time).total_seconds() / 3600
                    
                    if hours_since < rate_limit:
                        wait_time = rate_limit - hours_since
                        logger.info(f"Waiting {wait_time:.1f} hours before next {platform} post")
                        # In production, this would sleep. For demo, we just continue.
            
            # Publish to all platforms
            content_results = self.publish_article(content, platforms)
            
            overall_results["successful"] += len(content_results["successful"])
            overall_results["failed"] += len(content_results["failed"])
            overall_results["content_results"].append(content_results)
        
        return overall_results
    
    def check_platform_status(self) -> dict:
        """
        Check the status of all configured platforms.
        
        Returns:
            Dict mapping platform names to PlatformStatus objects
        """
        status = {}
        
        for platform in self.credentials.keys():
            platform_status = PlatformStatus(platform=platform, logged_in=False)
            
            publisher = self._get_publisher(platform)
            if not publisher:
                platform_status.error = "Publisher not available"
                status[platform] = platform_status
                continue
            
            try:
                with publisher:
                    if publisher.is_logged_in():
                        platform_status.logged_in = True
                    else:
                        # Try to login
                        if publisher.login():
                            platform_status.logged_in = True
                            platform_status.needs_reauth = False
                        else:
                            platform_status.needs_reauth = True
                            platform_status.error = "Login failed"
            except Exception as e:
                platform_status.error = str(e)
                platform_status.needs_reauth = True
            
            status[platform] = platform_status
        
        return status
    
    def cleanup(self):
        """Clean up all publisher resources."""
        for publisher in self.publishers.values():
            publisher.cleanup()
        self.publishers.clear()


# ============================================================================
# Hermes Integration
# ============================================================================

def create_hermes_publish_task(
    customer_id: str,
    content_batch: List[dict],
    platforms: List[str],
    mode: str = "bulk"
) -> dict:
    """
    Create a Hermes task for async publishing.
    
    Args:
        customer_id: Customer identifier
        content_batch: List of content dicts to publish
        platforms: List of platform names
        mode: 'single', 'bulk', 'daily', or 'weekly'
        
    Returns:
        Task configuration dict for Hermes
    """
    task_config = {
        "task_type": "browser_publishing",
        "customer_id": customer_id,
        "platforms": platforms,
        "mode": mode,
        "content_count": len(content_batch),
        "created_at": datetime.now().isoformat(),
    }
    
    if mode == "daily":
        task_config["schedule"] = "daily"
        task_config["batch_size"] = 50
        task_config["daily_targets"] = {
            "articles": 50,
            "social_posts": 50,
        }
    elif mode == "weekly":
        task_config["schedule"] = "weekly"
        task_config["batch_size"] = len(content_batch)
    
    return task_config


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python browser_publisher.py <customer_id>")
        print("Example: python browser_publisher.py fmnol_customer_001")
        sys.exit(1)
    
    customer_id = sys.argv[1]
    
    # Create pipeline
    pipeline = PublishingPipeline(customer_id, headless=True)
    
    # Check status
    print("Checking platform status...")
    status = pipeline.check_platform_status()
    
    for platform, platform_status in status.items():
        if isinstance(platform_status, PlatformStatus):
            status_str = "✓" if platform_status.logged_in else "✗"
            print(f"  {status_str} {platform}: logged_in={platform_status.logged_in}")
            if platform_status.error:
                print(f"    Error: {platform_status.error}")
    
    print("\nTo publish content, use the PublishingPipeline class in your code.")
    
    pipeline.cleanup()
