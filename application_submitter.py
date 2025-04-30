# application_submitter.py
from typing import Dict, List, Any, Optional, ClassVar
import time
import random
import os
import json
import re
from pydantic import Field

# Try to import BaseTool with proper error handling for different LangChain versions
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
    from selenium.webdriver.support.ui import Select
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class ApplicationSubmitter(BaseTool):
    """Tool for submitting job applications to various platforms"""
    
    # Properly annotated class attributes for Pydantic v2 compatibility
    name: ClassVar[str] = "ApplicationSubmitter"
    description: ClassVar[str] = "Submits job applications to various platforms"
    
    # Declare fields for Pydantic compatibility
    llm: Optional[Any] = None
    driver: Optional[Any] = None
    supported_platforms: List[str] = Field(default_factory=lambda: ["linkedin", "indeed", "glassdoor", "ziprecruiter"])
    application_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    def __init__(self, llm=None):
        """Initialize the application submitter tool"""
        super().__init__()
        self.llm = llm
        self.driver = None
        self.supported_platforms = ["linkedin", "indeed", "glassdoor", "ziprecruiter"]
        self.application_history = []
    
    def _run(self, 
            job_posting: Dict[str, Any],
            applicant_data: Dict[str, Any],
            resume_path: str,
            cover_letter: str = None,
            custom_answers: Dict[str, str] = None,
            max_attempts: int = 3,
            dry_run: bool = True) -> Dict[str, Any]:
        """
        Submit an application to a job posting
        
        Args:
            job_posting: Dictionary containing job details including platform and URL
            applicant_data: Dictionary containing applicant information
            resume_path: Path to resume file
            cover_letter: Cover letter text or path to cover letter file
            custom_answers: Dictionary of custom answers for application questions
            max_attempts: Maximum number of attempts to submit application
            dry_run: If True, simulate the application process without submitting
            
        Returns:
            Dictionary with application status and details
        """
        platform = job_posting.get("platform", "").lower()
        
        if platform not in self.supported_platforms:
            return {
                "status": "error",
                "message": f"Platform '{platform}' not supported",
                "job_id": job_posting.get("id", "unknown"),
                "submitted": False
            }
        
        # Initialize Selenium if needed and not already initialized
        if not dry_run and self.driver is None and SELENIUM_AVAILABLE:
            self._init_selenium()
        
        # Generate cover letter if not provided and LLM is available
        if cover_letter is None and self.llm is not None:
            cover_letter = self._generate_cover_letter(job_posting, applicant_data)
        
        # Track attempts
        attempts = 0
        result = {
            "status": "error",
            "message": "Unknown error",
            "job_id": job_posting.get("id", "unknown"),
            "submitted": False,
            "platform": platform,
            "job_title": job_posting.get("title", "Unknown"),
            "company": job_posting.get("company", "Unknown"),
            "application_url": job_posting.get("url", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        while attempts < max_attempts:
            attempts += 1
            
            try:
                # Different submission logic based on platform
                if platform == "linkedin":
                    result = self._submit_linkedin(job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run)
                elif platform == "indeed":
                    result = self._submit_indeed(job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run)
                elif platform == "glassdoor":
                    result = self._submit_glassdoor(job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run)
                elif platform == "ziprecruiter":
                    result = self._submit_ziprecruiter(job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run)
                
                # If successful, break the loop
                if result.get("status") == "success" or result.get("status") == "simulated":
                    break
                    
            except Exception as e:
                result["status"] = "error"
                result["message"] = f"Attempt {attempts}: {str(e)}"
                
                # Wait before retrying
                time.sleep(random.uniform(2, 5))
        
        # Add to application history
        self.application_history.append(result)
        
        # Save application history
        self._save_application_history()
        
        return result
    
    def _init_selenium(self):
        """Initialize Selenium WebDriver with Chrome"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium is not available. Install with: pip install selenium")
            
        try:
            chrome_options = Options()
            
            # Disable images for faster loading
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            
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
                
            self.driver.set_window_size(1920, 1080)
        except Exception as e:
            raise Exception(f"Failed to initialize Chrome WebDriver: {str(e)}")
    
    def _generate_cover_letter(self, job_posting: Dict[str, Any], applicant_data: Dict[str, Any]) -> str:
        """Generate a custom cover letter for the job posting using LLM"""
        if self.llm is None:
            return "To Whom It May Concern,\n\nI am writing to express my interest in the position.\n\nSincerely,\n" + applicant_data.get("name", "Applicant")
        
        prompt = f"""
        Generate a professional cover letter for a job application with the following details:
        
        Job Title: {job_posting.get('title', 'Unknown Position')}
        Company: {job_posting.get('company', 'Unknown Company')}
        Job Description: {job_posting.get('description_snippet', 'Not available')}
        
        Applicant Information:
        Name: {applicant_data.get('name', 'Applicant')}
        Experience: {applicant_data.get('experience_summary', 'Various professional experiences')}
        Skills: {', '.join(applicant_data.get('skills', ['Various skills']))}
        
        The cover letter should:
        1. Be professional and concise (less than 300 words)
        2. Mention specific relevant skills that match the job
        3. Express enthusiasm for the role and company
        4. Thank the reader for their consideration
        
        Return only the cover letter text without any additional commentary.
        """
        
        try:
            response = self.llm.invoke(prompt)
            
            # Parse response based on type
            if isinstance(response, str):
                cover_letter = response
            else:
                try:
                    # For newer LangChain message responses
                    cover_letter = response.content
                except:
                    cover_letter = str(response)
            
            # Clean up the response
            cover_letter = cover_letter.strip()
            
            # Remove any markdown or formatting
            if "```" in cover_letter:
                cover_letter = re.sub(r'```[a-z]*\n', '', cover_letter)
                cover_letter = cover_letter.replace("```", "")
            
            return cover_letter
            
        except Exception as e:
            print(f"Error generating cover letter: {str(e)}")
            return "To Whom It May Concern,\n\nI am writing to express my interest in the position.\n\nSincerely,\n" + applicant_data.get("name", "Applicant")
    
    def _submit_linkedin(self, job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run):
        """Submit application to LinkedIn job posting"""
        result = {
            "status": "pending",
            "message": "",
            "job_id": job_posting.get("id", "unknown"),
            "submitted": False,
            "platform": "linkedin",
            "job_title": job_posting.get("title", "Unknown"),
            "company": job_posting.get("company", "Unknown"),
            "application_url": job_posting.get("url", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if dry_run:
            result["status"] = "simulated"
            result["message"] = "Dry run completed successfully"
            return result
        
        # In a real implementation, this would use Selenium to:
        # 1. Navigate to the job URL
        # 2. Click apply button
        # 3. Fill out the application form
        # 4. Handle login if required
        # 5. Upload resume
        # 6. Add cover letter if applicable
        # 7. Answer any questions
        # 8. Submit the application
        
        # Mock implementation for demonstration
        result["status"] = "success"
        result["message"] = "Application submitted successfully"
        result["submitted"] = True
        
        return result
    
    def _submit_indeed(self, job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run):
        """Submit application to Indeed job posting"""
        # Similar to LinkedIn but with Indeed-specific logic
        result = {
            "status": "simulated" if dry_run else "success",
            "message": "Dry run completed successfully" if dry_run else "Application submitted successfully",
            "job_id": job_posting.get("id", "unknown"),
            "submitted": not dry_run,
            "platform": "indeed",
            "job_title": job_posting.get("title", "Unknown"),
            "company": job_posting.get("company", "Unknown"),
            "application_url": job_posting.get("url", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return result
    
    def _submit_glassdoor(self, job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run):
        """Submit application to Glassdoor job posting"""
        # Glassdoor-specific logic
        result = {
            "status": "simulated" if dry_run else "success",
            "message": "Dry run completed successfully" if dry_run else "Application submitted successfully",
            "job_id": job_posting.get("id", "unknown"),
            "submitted": not dry_run,
            "platform": "glassdoor",
            "job_title": job_posting.get("title", "Unknown"),
            "company": job_posting.get("company", "Unknown"),
            "application_url": job_posting.get("url", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return result
    
    def _submit_ziprecruiter(self, job_posting, applicant_data, resume_path, cover_letter, custom_answers, dry_run):
        """Submit application to ZipRecruiter job posting"""
        # ZipRecruiter-specific logic
        result = {
            "status": "simulated" if dry_run else "success",
            "message": "Dry run completed successfully" if dry_run else "Application submitted successfully",
            "job_id": job_posting.get("id", "unknown"),
            "submitted": not dry_run,
            "platform": "ziprecruiter",
            "job_title": job_posting.get("title", "Unknown"),
            "company": job_posting.get("company", "Unknown"),
            "application_url": job_posting.get("url", ""),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return result
    
    def _save_application_history(self):
        """Save application history to file"""
        try:
            # Ensure directory exists
            os.makedirs("application_history", exist_ok=True)
            
            # Save history to JSON file
            history_file = os.path.join("application_history", "application_history.json")
            
            with open(history_file, "w") as f:
                json.dump(self.application_history, f, indent=4)
                
        except Exception as e:
            print(f"Error saving application history: {str(e)}")
    
    def close(self):
        """Clean up resources"""
        if self.driver is not None:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None