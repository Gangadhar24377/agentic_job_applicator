# real_job_search.py - Simplified version for direct use in job_applicator
from typing import Dict, List, Any, Optional
import requests
import json
import os
import time
import random
import re
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class RealJobSearchTool:
    """Tool for searching and collecting REAL job postings using Serper API"""
    
    def __init__(self, serper_api_key=None):
        """Initialize the Serper job search tool"""
        # Use provided API key or load from environment
        if serper_api_key:
            self.serper_api_key = serper_api_key
        else:
            self.serper_api_key = os.environ.get("SERPER_API_KEY", "")
            
        if not self.serper_api_key:
            raise ValueError("Serper API key is required. Set it in .env file as SERPER_API_KEY or pass it to the constructor.")
    
    def run(self, query="", location="", job_type="fulltime", 
         experience_level="", remote=False, limit=10, 
         resume_data=None, preferences=None, **kwargs) -> List[Dict[str, Any]]:
        """
        Search for jobs based on criteria using Serper API
        """
        # For compatibility with other code
        return self._run(query, location, job_type, experience_level, remote, limit, resume_data, preferences, **kwargs)
    
    def _run(self, query="", location="", job_type="fulltime", 
         experience_level="", remote=False, limit=10, 
         resume_data=None, preferences=None, **kwargs) -> List[Dict[str, Any]]:
        """
        Main search function - same parameters as run()
        """
        # Build search queries
        search_queries = self._build_search_queries(query, location, job_type, remote, resume_data, preferences)
        
        all_results = []
        # Execute searches for each query
        for search_query in search_queries[:2]:  # Limit to top 2 search queries
            try:
                print(f"Searching for: {search_query}")
                # Perform Serper search
                serper_results = self._search_serper(search_query, limit // 2)
                processed_results = self._process_serper_results(serper_results)
                all_results.extend(processed_results)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                print(f"Error searching with query '{search_query}': {str(e)}")

        # Remove duplicates and filter out non-job listings
        unique_results = self._remove_duplicates(all_results)
        filtered_results = [job for job in unique_results if self._is_valid_job_posting(job)]
        
        # Score and rank results
        scored_results = self._score_results(filtered_results, resume_data, preferences)
        scored_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # Return dummy result if no jobs found
        if not scored_results:
            return [{"title": "No job listings found", "company": "Try different search terms", 
                    "location": "Unknown", "url": "", "platform": "none", "relevance_score": 0}]
            
        return scored_results[:limit]
    
    def _build_search_queries(self, query, location, job_type, remote, resume_data, preferences):
        """Build a list of search queries based on inputs and resume/preference data"""
        # Get job title from query, preferences or resume
        job_title = query
        if not job_title and preferences:
            job_types = preferences.get("job_types", [])
            if job_types and len(job_types) > 0:
                job_title = job_types[0]
        if not job_title and resume_data:
            data = resume_data
            if isinstance(data, dict) and "structured_info" in data:
                data = data["structured_info"]
            if isinstance(data, dict) and "recommended_jobs" in data and data["recommended_jobs"]:
                job_title = data["recommended_jobs"][0]
        if not job_title:
            job_title = "Software Engineer"
        
        # Build search queries
        search_queries = []
        
        # LinkedIn jobs query
        linkedin_query = f"{job_title} jobs"
        if location:
            linkedin_query += f" in {location}"
        if remote:
            linkedin_query += " remote"
        linkedin_query += " site:linkedin.com/jobs/view"
        search_queries.append(linkedin_query)
        
        # Indeed jobs query
        indeed_query = f"{job_title} jobs"
        if location:
            indeed_query += f" in {location}"
        if remote:
            indeed_query += " remote"
        indeed_query += " site:indeed.com/viewjob"
        search_queries.append(indeed_query)
        
        return search_queries
    
    def _search_serper(self, search_query, limit=10):
        """Perform a search using Serper API"""
        url = "https://google.serper.dev/search"
        payload = json.dumps({
            "q": search_query,
            "num": min(limit * 2, 20)
        })
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code != 200:
            raise Exception(f"Serper API error: {response.status_code} - {response.text}")
        return response.json()
    
    def _process_serper_results(self, serper_results):
        """Process Serper API results into job posting objects"""
        processed_results = []
        if 'organic' not in serper_results:
            return processed_results
        
        for result in serper_results['organic']:
            job = self._extract_job_details(result)
            processed_results.append(job)
        
        return processed_results
    
    def _extract_job_details(self, result):
        """Extract job details from a Serper result"""
        url = result.get('link', '')
        title = result.get('title', '')
        snippet = result.get('snippet', '')
        
        # Clean up title
        title = re.sub(r' - LinkedIn$', '', title)
        title = re.sub(r' \| Indeed\.com$', '', title)
        
        # Determine platform
        platform = "unknown"
        if "linkedin.com" in url:
            platform = "linkedin"
        elif "indeed.com" in url:
            platform = "indeed"
        elif "glassdoor.com" in url:
            platform = "glassdoor"
        elif "ziprecruiter.com" in url:
            platform = "ziprecruiter"
        
        # Extract job ID
        job_id = None
        if platform == "linkedin":
            id_match = re.search(r'linkedin\.com/jobs/view/(\d+)', url)
            if id_match:
                job_id = id_match.group(1)
        
        # Extract company name
        company = "Unknown Company"
        if "at " in title:
            company_match = re.search(r'at ([^-]+)(?:-|$)', title)
            if company_match:
                company = company_match.group(1).strip()
        
        # Extract location
        location = "Unknown Location"
        if "in " in title:
            location_match = re.search(r'in ([^-]+)(?:-|$)', title)
            if location_match:
                location = location_match.group(1).strip()
        
        # Extract posting date and salary
        posted_date = None
        date_match = re.search(r'Posted (\d+ days? ago|yesterday|today)', snippet, re.IGNORECASE)
        if date_match:
            posted_date = date_match.group(1)
        
        salary = None
        salary_match = re.search(r'\$([0-9,.]+k?)\s*-\s*\$([0-9,.]+k?)', snippet)
        if salary_match:
            salary = f"${salary_match.group(1)} - ${salary_match.group(2)}"
        
        return {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "description_snippet": snippet,
            "platform": platform,
            "job_id": job_id,
            "salary": salary,
            "posted_date": posted_date,
            "is_remote": "remote" in title.lower() or "remote" in snippet.lower(),
            "source": "serper",
            "found_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def _remove_duplicates(self, results):
        """Remove duplicate job listings based on URL"""
        unique_urls = {}
        unique_results = []
        for job in results:
            url = job.get('url', '')
            if url and url not in unique_urls:
                unique_urls[url] = True
                unique_results.append(job)
        return unique_results
    
    def _is_valid_job_posting(self, job):
        """Check if a job posting has valid details and is likely a real job"""
        url = job.get('url', '')
        real_job_patterns = [
            r'linkedin\.com/jobs/view/',
            r'indeed\.com/viewjob\?',
            r'indeed\.com/job/',
            r'glassdoor\.com/job/',
            r'ziprecruiter\.com/.*detail'
        ]
        is_real_job_url = any(re.search(pattern, url) for pattern in real_job_patterns)
        has_basic_info = (job.get('title', '') and job.get('company', '') != "Unknown Company")
        return is_real_job_url and has_basic_info
    
    def _score_results(self, results, resume_data, preferences):
        """Score job results based on resume data and preferences"""
        if not results:
            return []
            
        # Extract skills and preferences
        candidate_skills = []
        if resume_data and isinstance(resume_data, dict):
            data = resume_data
            if "structured_info" in data:
                data = data["structured_info"]
            if "skills" in data and isinstance(data["skills"], list):
                candidate_skills = data["skills"]
        
        # Score each result
        for job in results:
            score = 5.0  # Base score
            job_text = f"{job.get('title', '')} {job.get('description_snippet', '')}"
            
            # Skills match
            matching_skills = []
            for skill in candidate_skills:
                if skill.lower() in job_text.lower():
                    matching_skills.append(skill)
            
            if matching_skills:
                skill_bonus = min(3.0, len(matching_skills) * 0.5)  # Up to 3 points
                score += skill_bonus
            
            # Store score and explanation
            job["relevance_score"] = min(10.0, score)  # Cap at 10
            job["matching_skills"] = matching_skills
            
            # Generate explanation
            if matching_skills:
                skill_text = ", ".join(matching_skills[:3])
                if len(matching_skills) > 3:
                    skill_text += f" and {len(matching_skills) - 3} more"
                job["score_explanation"] = f"Matches skills: {skill_text}"
            else:
                job["score_explanation"] = "Basic match based on job search criteria"
        
        return results