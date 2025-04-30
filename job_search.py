# job_search.py
from typing import Dict, List, Any, Optional, ClassVar
import requests
from bs4 import BeautifulSoup
import json
import time
import random
import re
from pydantic import Field

# Try to import BaseTool with proper error handling for different LangChain versions
try:
    from langchain.tools import BaseTool
except ImportError:
    # For newer LangChain versions
    try:
        from langchain.tools import BaseTool
    except ImportError:
        # Define fallback if import fails
        class BaseTool:
            name: str = "base_tool"
            description: str = "Base tool description"
            
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
            
            def _run(self, *args, **kwargs):
                raise NotImplementedError("Tool does not implement _run")
            
            def run(self, *args, **kwargs):
                return self._run(*args, **kwargs)

# Try to import Selenium with proper error handling
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class JobSearchTool(BaseTool):
    """Tool for searching and collecting job postings from various platforms"""
    
    # Properly annotated class attributes for Pydantic v2 compatibility
    name: ClassVar[str] = "JobSearchTool"
    description: ClassVar[str] = "Searches for job postings across multiple platforms based on criteria"
    
    # Add these field declarations
    llm: Optional[Any] = None
    use_selenium: bool = True
    driver: Optional[Any] = None
    available_platforms: List[str] = Field(default_factory=lambda: ["linkedin", "indeed", "glassdoor", "monster", "ziprecruiter"])
    
    def __init__(self, llm=None, use_selenium=True):
        """Initialize the job search tool"""
        super().__init__()
        self.llm = llm
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.driver = None
        self.available_platforms = ["linkedin", "indeed", "glassdoor", "monster", "ziprecruiter"]
    
    def _run(self, query="", location="", platforms=None, company_size="", job_type="fulltime", 
         experience_level="", posted_within="", limit=10, **kwargs) -> List[Dict[str, Any]]:
        """
        Search for jobs based on criteria
        
        Args:
            query (str): The job title or keywords to search for (primary search term)
            location (str): Location to search in
            platforms (List[str]): Job platforms to search
            company_size (str): Filter by company size
            job_type (str): Type of job (fulltime, parttime, contract, remote)
            experience_level (str): Experience level (entry, mid, senior)
            posted_within (str): Time range filter (day, week, month)
            limit (int): Maximum number of results to return
            
        Returns:
            List of job posting dictionaries with details
        """
        # Also handle 'search_query' for backward compatibility
        search_query = kwargs.get('search_query', query)
        
        # Validate platforms
        if platforms is None:
            platforms = self.available_platforms
        else:
            platforms = [p.lower() for p in platforms]
            platforms = [p for p in platforms if p in self.available_platforms]
            
        if not platforms:
            platforms = ["linkedin", "indeed"]  # Default to these if none valid
        
        # Initialize Selenium if needed and not already initialized
        if self.use_selenium and self.driver is None:
            self._init_selenium()
        
        all_results = []
        
        # Search each platform
        for platform in platforms:
            try:
                platform_results = self._search_platform(
                    platform, 
                    search_query, 
                    location, 
                    company_size,
                    job_type,
                    experience_level,
                    posted_within,
                    limit
                )
                
                # Add platform information to results
                for job in platform_results:
                    job["platform"] = platform
                
                all_results.extend(platform_results)
                
                # Small delay between platform requests to avoid rate limiting
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error searching {platform}: {str(e)}")
                continue
        
        # Score and rank results if LLM is available
        if self.llm is not None:
            all_results = self._score_results(all_results, search_query)
        
        return all_results
    
    def _init_selenium(self):
        """Initialize Selenium WebDriver with headless Chrome"""
        if not SELENIUM_AVAILABLE:
            print("Selenium is not available. Install with: pip install selenium")
            self.use_selenium = False
            return
            
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Add random user agent to avoid detection
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
            ]
            chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
            
            # Try using webdriver-manager if available
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from selenium.webdriver.chrome.service import Service
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except ImportError:
                # Fall back to direct ChromeDriver initialization
                self.driver = webdriver.Chrome(options=chrome_options)
                
        except Exception as e:
            print(f"Failed to initialize Chrome WebDriver: {str(e)}")
            print("Falling back to requests-based searches")
            self.use_selenium = False
    
    def _search_platform(self, 
                         platform: str, 
                         search_query: str, 
                         location: str,
                         company_size: str,
                         job_type: str,
                         experience_level: str,
                         posted_within: str,
                         limit: int) -> List[Dict[str, Any]]:
        """Search a specific platform for job postings"""
        if platform == "linkedin":
            return self._search_linkedin(search_query, location, company_size, job_type, experience_level, posted_within, limit)
        elif platform == "indeed":
            return self._search_indeed(search_query, location, job_type, experience_level, posted_within, limit)
        elif platform == "glassdoor":
            # Placeholder for Glassdoor search implementation
            return []
        elif platform == "monster":
            # Placeholder for Monster search implementation
            return []
        elif platform == "ziprecruiter":
            # Placeholder for ZipRecruiter search implementation
            return []
        else:
            return []
    
    def _search_linkedin(self, 
                        search_query: str, 
                        location: str,
                        company_size: str,
                        job_type: str,
                        experience_level: str,
                        posted_within: str,
                        limit: int) -> List[Dict[str, Any]]:
        """Search LinkedIn for job postings"""
        # Example implementation - in a real system, this would be more robust
        if not self.use_selenium or not SELENIUM_AVAILABLE:
            return self._search_linkedin_requests(search_query, location, limit)
        
        # Using mock data for demonstration
        # In a real implementation, this would use Selenium to scrape LinkedIn
        mock_results = []
        for i in range(min(limit, 5)):
            mock_results.append({
                "title": f"{search_query.title()} Specialist",
                "company": f"Company {i+1}",
                "location": location or "Remote",
                "url": f"https://linkedin.com/jobs/view/job{i+1}",
                "posted_date": "2023-04-01",
                "description_snippet": f"Looking for a skilled {search_query} professional...",
                "relevance_score": random.randint(7, 10)
            })
        
        return mock_results
    
    def _search_linkedin_requests(self, search_query: str, location: str, limit: int) -> List[Dict[str, Any]]:
        """Fallback method using requests instead of Selenium"""
        # Mock implementation
        mock_results = []
        for i in range(min(limit, 3)):
            mock_results.append({
                "title": f"{search_query.title()} Associate",
                "company": f"Company {i+1}",
                "location": location or "Various Locations",
                "url": f"https://linkedin.com/jobs/view/job{i+1}",
                "posted_date": "2023-04-01",
                "relevance_score": random.randint(6, 9)
            })
        
        return mock_results
    
    def _search_indeed(self, 
                      search_query: str, 
                      location: str,
                      job_type: str,
                      experience_level: str,
                      posted_within: str,
                      limit: int) -> List[Dict[str, Any]]:
        """Search Indeed for job postings"""
        # Mock implementation
        mock_results = []
        for i in range(min(limit, 4)):
            mock_results.append({
                "title": f"Senior {search_query.title()}",
                "company": f"Indeed Company {i+1}",
                "location": location or "Nationwide",
                "url": f"https://indeed.com/jobs/view/job{i+1}",
                "posted_date": "2023-04-05",
                "salary": f"${70000 + i*10000} - ${90000 + i*10000}",
                "description_snippet": f"We're looking for an experienced {search_query} professional...",
                "relevance_score": random.randint(7, 10)
            })
        
        return mock_results
    
    def _score_results(self, results: List[Dict[str, Any]], search_query: str) -> List[Dict[str, Any]]:
        """Score and rank job results using LLM if available"""
        if not results or self.llm is None:
            # Add default scoring if LLM not available
            for job in results:
                if "relevance_score" not in job:
                    # Simple keyword matching score
                    title = job.get("title", "").lower()
                    desc = job.get("description_snippet", "").lower()
                    query = search_query.lower()
                    
                    # Basic scoring: 
                    # 10 points if query is in title
                    # 5 points if query is in description
                    # +1-3 points randomly
                    score = 5
                    if query in title:
                        score += 5
                    if query in desc:
                        score += 3
                    
                    # Add some randomness to differentiate similar listings
                    score += random.randint(0, 2)
                    
                    # Cap at 10
                    job["relevance_score"] = min(score, 10)
            
            # Sort by relevance score
            results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            return results
            
        try:
            # In a real implementation, this would use the LLM to score results
            # For now, we'll just use default scoring
            results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            return results
        except Exception as e:
            print(f"Error scoring results: {str(e)}")
            return results
    
    def close(self):
        """Clean up resources"""
        if self.driver is not None:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None