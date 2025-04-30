# real_serper_job_search.py
from typing import Dict, List, Any, Optional, ClassVar
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
        
        Args:
            query (str): The job title or keywords to search for (primary search term)
            location (str): Location to search in
            job_type (str): Type of job (fulltime, parttime, contract, remote)
            experience_level (str): Experience level (entry, mid, senior)
            remote (bool): Whether to search for remote jobs
            limit (int): Maximum number of results to return
            resume_data (dict): Parsed resume data for matching
            preferences (dict): User preferences for job matching
            
        Returns:
            List of job posting dictionaries with details
        """
        # For compatibility with other code
        return self._run(query, location, job_type, experience_level, remote, limit, resume_data, preferences, **kwargs)
    
    def _run(self, query="", location="", job_type="fulltime", 
         experience_level="", remote=False, limit=10, 
         resume_data=None, preferences=None, **kwargs) -> List[Dict[str, Any]]:
        """
        Main search function - same parameters as run()
        """
        # Build search queries based on input criteria
        search_queries = self._build_search_queries(query, location, job_type, experience_level, remote, resume_data, preferences)
        
        all_results = []
        
        # Execute searches for each query
        for search_query in search_queries[:3]:  # Limit to top 3 search queries to avoid API overuse
            try:
                print(f"Searching for: {search_query}")
                # Perform Serper search
                serper_results = self._search_serper(search_query, limit // 2)  # Divide limit among queries
                
                # Process and filter results
                processed_results = self._process_serper_results(serper_results)
                
                # Add to overall results
                all_results.extend(processed_results)
                
                # Small delay between requests
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                print(f"Error searching with query '{search_query}': {str(e)}")
        
        # If we don't have enough results, try one more time with a more specific query
        if len(all_results) < limit and len(search_queries) > 0:
            try:
                # Add "job posting" to make the search more specific
                specific_query = f"{search_queries[0]} exact"
                serper_results = self._search_serper(specific_query, limit - len(all_results))
                
                # Process and filter results
                processed_results = self._process_serper_results(serper_results)
                
                # Add to overall results
                all_results.extend(processed_results)
                
            except Exception as e:
                print(f"Error searching with specific query: {str(e)}")
        
        # Remove duplicates based on URL
        unique_results = self._remove_duplicates(all_results)
        
        # Filter out non-job listings
        filtered_results = [job for job in unique_results if self._is_valid_job_posting(job)]
        
        # Score and rank results
        scored_results = self._score_results(filtered_results, resume_data, preferences)
        
        # Sort by score and limit results
        scored_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # If we still have no valid results, return a message
        if not scored_results:
            dummy_result = {
                "title": "No job listings found",
                "company": "Please try different search terms or check your Serper API key",
                "location": "Unknown",
                "description_snippet": "The search did not return any valid job listings. Try modifying your search criteria or check if the Serper API key is working correctly.",
                "url": "",
                "platform": "none",
                "relevance_score": 0,
                "score_explanation": "No valid job listings found"
            }
            return [dummy_result]
            
        return scored_results[:limit]
    
    def _build_search_queries(self, query, location, job_type, experience_level, remote, resume_data, preferences):
        """Build a list of search queries based on inputs and resume/preference data"""
        search_queries = []
        
        # Determine the job title to search for
        job_title = query
        
        # If no direct query, try to get job title from preferences or resume
        if not job_title and preferences:
            job_types = preferences.get("job_types", [])
            if job_types and len(job_types) > 0:
                job_title = job_types[0]
        
        # If still no job title, try to get it from resume_data
        if not job_title and resume_data:
            data = resume_data
            if isinstance(data, dict) and "structured_info" in data:
                data = data["structured_info"]
            
            if isinstance(data, dict) and "recommended_jobs" in data and data["recommended_jobs"]:
                job_title = data["recommended_jobs"][0]
        
        # Default job title if nothing found
        if not job_title:
            job_title = "Software Engineer"
        
        # Get location from preferences if not provided
        if not location and preferences:
            location = preferences.get("location_preferences", "")
        
        # Handle remote preference
        is_remote = remote
        if not is_remote and preferences:
            remote_pref = preferences.get("remote_preference", "")
            if isinstance(remote_pref, str) and "remote" in remote_pref.lower():
                is_remote = True
        
        # Build queries for different job sites
        # Be very specific to ensure we get actual job listings
        
        # LinkedIn jobs (specifically targeting job view pages)
        linkedin_query = f"{job_title} jobs"
        if location:
            linkedin_query += f" in {location}"
        if is_remote:
            linkedin_query += " remote"
        linkedin_query += " site:linkedin.com/jobs/view"
        search_queries.append(linkedin_query)
        
        # Indeed jobs
        indeed_query = f"{job_title} jobs"
        if location:
            indeed_query += f" in {location}"
        if is_remote:
            indeed_query += " remote"
        indeed_query += " site:indeed.com/viewjob"
        search_queries.append(indeed_query)
        
        # Add skills-based query if resume data is available
        if resume_data and isinstance(resume_data, dict):
            data = resume_data
            if "structured_info" in data:
                data = data["structured_info"]
            
            if "skills" in data and isinstance(data["skills"], list) and len(data["skills"]) > 0:
                # Use top 3 skills for a more targeted search
                top_skills = data["skills"][:3]
                skills_str = " ".join(top_skills)
                
                skills_query = f"{job_title} {skills_str} jobs"
                if location:
                    skills_query += f" in {location}"
                if is_remote:
                    skills_query += " remote"
                skills_query += " site:linkedin.com/jobs/view"
                search_queries.append(skills_query)
        
        return search_queries
    
    def _search_serper(self, search_query, limit=10):
        """Perform a search using Serper API"""
        url = "https://google.serper.dev/search"
        
        payload = json.dumps({
            "q": search_query,
            "num": min(limit * 2, 20)  # Request more results but cap at 20
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
        
        # Check if organic results exist
        if 'organic' not in serper_results:
            print("No organic results found in Serper response")
            return processed_results
        
        # Extract job listings from organic results
        for result in serper_results['organic']:
            # Extract job details
            job = self._extract_job_details(result)
            processed_results.append(job)
        
        return processed_results
    
    def _extract_job_details(self, result):
        """Extract job details from a Serper result"""
        # Get basic information from the result
        url = result.get('link', '')
        title = result.get('title', '')
        snippet = result.get('snippet', '')
        
        # Clean up title by removing site name
        title = re.sub(r' - LinkedIn$', '', title)
        title = re.sub(r' \| Indeed\.com$', '', title)
        title = re.sub(r' \| Glassdoor$', '', title)
        title = re.sub(r' \| ZipRecruiter$', '', title)
        
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
        elif "monster.com" in url:
            platform = "monster"
        
        # Extract job ID
        job_id = None
        if platform == "linkedin":
            id_match = re.search(r'linkedin\.com/jobs/view/(\d+)', url)
            if id_match:
                job_id = id_match.group(1)
        elif platform == "indeed":
            id_match = re.search(r'jk=([^&]+)', url)
            if id_match:
                job_id = id_match.group(1)
        
        # Extract company name
        company = "Unknown Company"
        
        # Try to extract company from title
        if "at " in title:
            # Pattern: "Job Title at Company Name"
            company_match = re.search(r'at ([^-]+)(?:-|$)', title)
            if company_match:
                company = company_match.group(1).strip()
        
        # If company still unknown, try from snippet
        if company == "Unknown Company" and "at " in snippet:
            company_match = re.search(r'at ([^.•]+)', snippet)
            if company_match:
                company = company_match.group(1).strip()
        
        # Extract location
        location = "Unknown Location"
        if "in " in title:
            # Try to find location after "in "
            location_match = re.search(r'in ([^-]+)(?:-|$)', title)
            if location_match:
                location = location_match.group(1).strip()
        
        # If location still unknown, try from snippet
        if location == "Unknown Location" and "in " in snippet:
            location_match = re.search(r'in ([^.•]+)', snippet)
            if location_match:
                location = location_match.group(1).strip()
        
        # Check if remote
        is_remote = (
            'remote' in title.lower() or 
            'remote' in snippet.lower() or 
            'work from home' in snippet.lower() or
            'wfh' in snippet.lower()
        )
        
        if is_remote:
            if location == "Unknown Location":
                location = "Remote"
            elif "remote" not in location.lower():
                location += " (Remote)"
        
        # Extract posting date
        posted_date = None
        date_patterns = [
            r'Posted (\d+ days? ago)',
            r'Posted (yesterday|today)',
            r'(\d+ days? ago)',
            r'(yesterday|today)'
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, snippet, re.IGNORECASE)
            if date_match:
                posted_date = date_match.group(1)
                break
        
        # Extract salary information
        salary = None
        salary_patterns = [
            r'\$([0-9,.]+k?)\s*-\s*\$([0-9,.]+k?)',
            r'\$([0-9,.]+k?)/yr',
            r'\$([0-9,.]+k?) a year',
            r'([0-9,.]+k?)-([0-9,.]+k?) a year'
        ]
        
        for pattern in salary_patterns:
            salary_match = re.search(pattern, snippet, re.IGNORECASE)
            if salary_match:
                if salary_match.group(1) and (len(salary_match.groups()) == 1 or not salary_match.group(2)):
                    salary = f"${salary_match.group(1)}"
                else:
                    salary = f"${salary_match.group(1)} - ${salary_match.group(2)}"
                break
        
        # Create job object
        job = {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "description_snippet": snippet,
            "platform": platform,
            "job_id": job_id,
            "salary": salary,
            "posted_date": posted_date,
            "is_remote": is_remote,
            "source": "serper",
            "found_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return job
    
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
        # Check if the URL is a real job posting URL (not a generic jobs page)
        url = job.get('url', '')
        
        # Pattern for actual job posting URLs
        real_job_patterns = [
            r'linkedin\.com/jobs/view/',
            r'indeed\.com/viewjob\?',
            r'indeed\.com/job/',
            r'glassdoor\.com/job/',
            r'ziprecruiter\.com/.*detail'
        ]
        
        # Check if URL matches any real job pattern
        is_real_job_url = any(re.search(pattern, url) for pattern in real_job_patterns)
        
        # Check if the job has both a title and company
        has_basic_info = (
            job.get('title', '') and 
            job.get('title', '') != "Unknown" and
            job.get('company', '') and 
            job.get('company', '') != "Unknown Company"
        )
        
        # Determine if valid based on URL check
        return is_real_job_url and has_basic_info
    
    def _score_results(self, results, resume_data, preferences):
        """Score job results based on resume data and preferences"""
        if not results:
            return []
            
        # Extract skills and experience from resume_data if available
        candidate_skills = []
        candidate_field = None
        
        if resume_data and isinstance(resume_data, dict):
            data = resume_data
            if "structured_info" in data:
                data = data["structured_info"]
                
            if "skills" in data and isinstance(data["skills"], list):
                candidate_skills = data["skills"]
                
            if "field" in data:
                candidate_field = data["field"]
        
        # Extract user preferences if available
        preferred_job_types = []
        preferred_industries = []
        preferred_remote = False
        preferred_location = None
        
        if preferences and isinstance(preferences, dict):
            if "job_types" in preferences and isinstance(preferences["job_types"], list):
                preferred_job_types = preferences["job_types"]
                
            if "industry_preferences" in preferences and isinstance(preferences["industry_preferences"], list):
                preferred_industries = preferences["industry_preferences"]
                
            if "remote_preference" in preferences:
                remote_pref = preferences["remote_preference"]
                if isinstance(remote_pref, str) and "remote" in remote_pref.lower():
                    preferred_remote = True
                    
            if "location_preferences" in preferences:
                preferred_location = preferences["location_preferences"]
        
        # Score each result
        for job in results:
            score = 5.0  # Base score
            job_text = f"{job.get('title', '')} {job.get('description_snippet', '')}"
            
            # Skills match
            matching_skills = []
            if candidate_skills:
                for skill in candidate_skills:
                    if skill.lower() in job_text.lower():
                        matching_skills.append(skill)
                
                if matching_skills:
                    skill_bonus = min(3.0, len(matching_skills) * 0.5)  # Up to 3 points for skills
                    score += skill_bonus
            
            # Field match
            if candidate_field and candidate_field.lower() in job_text.lower():
                score += 1.0
            
            # Job type match
            matching_job_types = []
            if preferred_job_types:
                for job_type in preferred_job_types:
                    if job_type.lower() in job_text.lower():
                        matching_job_types.append(job_type)
                
                if matching_job_types:
                    score += min(1.0, len(matching_job_types) * 0.5)
            
            # Industry match
            matching_industries = []
            if preferred_industries:
                for industry in preferred_industries:
                    if industry.lower() in job_text.lower():
                        matching_industries.append(industry)
                
                if matching_industries:
                    score += min(1.0, len(matching_industries) * 0.5)
            
            # Remote match
            if preferred_remote and job.get('is_remote', False):
                score += 1.0
            
            # Location match
            if preferred_location and job.get('location', ''):
                if preferred_location.lower() in job.get('location', '').lower():
                    score += 1.0
            
            # Store score and matching information
            job["relevance_score"] = min(10.0, score)  # Cap at 10
            job["matching_skills"] = matching_skills
            job["matching_job_types"] = matching_job_types
            job["matching_industries"] = matching_industries
            
            # Generate explanation
            job["score_explanation"] = self._generate_score_explanation(job)
        
        return results
    
    def _generate_score_explanation(self, job):
        """Generate an explanation for the job match score"""
        explanations = []
        
        # Skills match explanation
        matching_skills = job.get("matching_skills", [])
        if matching_skills:
            if len(matching_skills) == 1:
                explanations.append(f"Matches skill: {matching_skills[0]}")
            else:
                skill_text = ", ".join(matching_skills[:3])
                if len(matching_skills) > 3:
                    skill_text += f" and {len(matching_skills) - 3} more"
                explanations.append(f"Matches skills: {skill_text}")
        
        # Job type match
        matching_job_types = job.get("matching_job_types", [])
        if matching_job_types:
            explanations.append(f"Matches job types: {', '.join(matching_job_types)}")
        
        # Industry match
        matching_industries = job.get("matching_industries", [])
        if matching_industries:
            explanations.append(f"Matches industries: {', '.join(matching_industries)}")
        
        # Location match
        preferred_location = job.get("location_match")
        if preferred_location:
            explanations.append(f"Location match: {preferred_location}")
        
        # Remote match
        if job.get("is_remote") and job.get("remote_match"):
            explanations.append("Matches remote preference")
        
        if not explanations:
            return "Basic match based on job search criteria"
        
        return "; ".join(explanations)