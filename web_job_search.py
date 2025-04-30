# web_job_search.py - Comprehensive web job search
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

class WebJobSearchTool:
    """Tool for searching and collecting job postings from across the web using Serper API"""
    
    def __init__(self, serper_api_key=None):
        """Initialize the web job search tool"""
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
            query (str): The job title or keywords to search for
            location (str): Location to search in
            job_type (str): Type of job
            experience_level (str): Experience level
            remote (bool): Whether to search for remote jobs
            limit (int): Maximum number of results to return
            resume_data (dict): Parsed resume data for matching
            preferences (dict): User preferences for job matching
        """
        # For compatibility with other code
        return self._run(query, location, job_type, experience_level, remote, limit, resume_data, preferences, **kwargs)
    
    def _run(self, query="", location="", job_type="fulltime", 
     experience_level="", remote=False, limit=10, 
     resume_data=None, preferences=None, **kwargs):
    
        # BUILD MORE DIVERSE SEARCH QUERIES - this is key
        search_queries = self._build_search_queries(query, location, job_type, remote, resume_data, preferences)
        
        all_results = []
        
        # SEARCH ACROSS ALL RECOMMENDED JOB TYPES FROM RESUME
        if resume_data and isinstance(resume_data, dict):
            data = resume_data
            if "structured_info" in data:
                data = data["structured_info"]
            
            if "recommended_jobs" in data and isinstance(data["recommended_jobs"], list):
                # Add specific search for EACH recommended job type
                for job_type in data["recommended_jobs"][:3]:  # Limit to top 3 to avoid API overuse
                    job_query = f"{job_type} jobs in {location}" if location else f"{job_type} jobs"
                    try:
                        print(f"Searching for recommended job type: {job_query}")
                        serper_results = self._search_serper(job_query, limit // 2)
                        processed_results = self._process_serper_results(serper_results)
                        all_results.extend(processed_results)
                        time.sleep(random.uniform(1.0, 2.0))
                    except Exception as e:
                        print(f"Error searching for {job_query}: {str(e)}")
        
        # THEN PROCEED WITH REGULAR SEARCH QUERIES
        for search_query in search_queries[:3]:
            try:
                print(f"Searching for: {search_query}")
                serper_results = self._search_serper(search_query, limit // 2)
                processed_results = self._process_serper_results(serper_results)
                all_results.extend(processed_results)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception as e:
                print(f"Error searching with query '{search_query}': {str(e)}")
        
        # INCREASE SERPER API RESULT COUNT
        # In the _search_serper method:
        payload = json.dumps({
            "q": search_query,
            "num": 20  # Request more results
        })
        
        # Remove duplicates
        unique_results = self._remove_duplicates(all_results)
        
        # Filter for valid job postings
        filtered_results = [job for job in unique_results if self._is_valid_job_posting(job)]
        
        # If we have very few results, try to relax the filters
        if len(filtered_results) < 3:
            # Use less strict filtering
            relaxed_results = [job for job in unique_results if self._appears_to_be_job(job)]
            # Add any new results that passed the relaxed filter but not the strict one
            for job in relaxed_results:
                if job not in filtered_results:
                    filtered_results.append(job)
        
        # Score and rank results
        scored_results = self._score_results(filtered_results, resume_data, preferences)
        
        # Sort by score
        scored_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        # If we still have no results, create a dummy result to inform the user
        if not scored_results:
            dummy_result = {
                "title": "No job listings found",
                "company": "Please try different search terms or check your Serper API key",
                "location": "Unknown",
                "description_snippet": "The search did not return any valid job listings. Try modifying your search criteria.",
                "url": "",
                "platform": "none",
                "relevance_score": 0,
                "score_explanation": "No valid job listings found"
            }
            return [dummy_result]
            
        # Return limited number of results
        return scored_results[:limit]
    
    def _build_search_queries(self, query, location, job_type, remote, resume_data, preferences):
        """Build a variety of search queries to find jobs from multiple sources"""
        # Get job title from query, preferences or resume
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
        
        # Get industry from preferences if available
        industry = ""
        if preferences and "industry_preferences" in preferences:
            industries = preferences.get("industry_preferences", [])
            if industries and len(industries) > 0:
                industry = industries[0]
        
        # Create array for search queries
        search_queries = []
        
        # 1. Generic job search query
        base_query = f"{job_title} jobs"
        if location:
            base_query += f" in {location}"
        if remote:
            base_query += " remote"
        search_queries.append(base_query)
        
        # 2. Job board specific queries - use multiple job boards
        job_boards = [
            "linkedin.com/jobs", 
            "indeed.com", 
            "glassdoor.com", 
            "ziprecruiter.com", 
            "monster.com",
            "careers.google.com",
            "jobs.apple.com",
            "amazon.jobs",
            "jobs.microsoft.com"
        ]
        
        # Add queries for major job boards
        for board in job_boards[:3]:  # Use top 3 boards
            board_query = f"{job_title} jobs"
            if location:
                board_query += f" in {location}"
            if remote:
                board_query += " remote"
            board_query += f" site:{board}"
            search_queries.append(board_query)
        
        # 3. Add industry-specific query if available
        if industry:
            industry_query = f"{job_title} jobs in {industry} industry"
            if location:
                industry_query += f" {location}"
            search_queries.append(industry_query)
        
        # 4. Use skills if available from resume
        if resume_data and isinstance(resume_data, dict):
            data = resume_data
            if "structured_info" in data:
                data = data["structured_info"]
            
            if "skills" in data and isinstance(data["skills"], list) and len(data["skills"]) > 0:
                # Get top skills
                top_skills = data["skills"][:3]
                skills_str = " ".join(top_skills)
                
                skills_query = f"{job_title} jobs requiring {skills_str}"
                if location:
                    skills_query += f" in {location}"
                search_queries.append(skills_query)
        
        # 5. Add "now hiring" query for more current results
        hiring_query = f"now hiring {job_title}"
        if location:
            hiring_query += f" in {location}"
        search_queries.append(hiring_query)
        
        # Remove duplicates
        unique_queries = []
        for query in search_queries:
            if query not in unique_queries:
                unique_queries.append(query)
        
        return unique_queries
    
    def _search_serper(self, search_query, limit=10):
        """Perform a search using Serper API"""
        url = "https://google.serper.dev/search"
        
        payload = json.dumps({
            "q": search_query,
            "num": min(limit * 2, 20)  # Request more results than needed but cap at 20
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
            return processed_results
        
        # Extract job listings from results
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
        title = re.sub(r' \| Monster\.com$', '', title)
        
        # Determine platform/source
        platform = "unknown"
        for domain, platform_name in [
            ("linkedin.com", "linkedin"),
            ("indeed.com", "indeed"),
            ("glassdoor.com", "glassdoor"),
            ("ziprecruiter.com", "ziprecruiter"),
            ("monster.com", "monster"),
            ("careers.google.com", "google"),
            ("jobs.apple.com", "apple"),
            ("amazon.jobs", "amazon"),
            ("jobs.microsoft.com", "microsoft"),
            ("lever.co", "lever"),
            ("greenhouse.io", "greenhouse"),
            ("workday.com", "workday")
        ]:
            if domain in url:
                platform = platform_name
                break
        
        # Extract job ID where possible
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
        company_patterns = [
            r'([^|]+?) is hiring', 
            r'([^|]+?) careers',
            r'([^|]+?) jobs',
            r'(.+?) \|',
            r'at ([^|]+?)( -|$)',
            r'with ([^|]+?)( -|$)',
            r'for ([^|]+?)( -|$)'
        ]
        
        for pattern in company_patterns:
            company_match = re.search(pattern, title, re.IGNORECASE)
            if company_match:
                company_candidate = company_match.group(1).strip()
                # Make sure it's a reasonable length for a company name
                if 2 <= len(company_candidate) <= 50:
                    company = company_candidate
                    break
        
        # Clean up company name
        company = re.sub(r'Jobs$|Careers$|Hiring$|Job$|Career$', '', company).strip()
        
        # If company still unknown, try to extract from snippet
        if company == "Unknown Company":
            for pattern in company_patterns:
                company_match = re.search(pattern, snippet, re.IGNORECASE)
                if company_match:
                    company_candidate = company_match.group(1).strip()
                    if 2 <= len(company_candidate) <= 50:
                        company = company_candidate
                        break
        
        # Extract location
        location = "Unknown Location"
        location_patterns = [
            r'in ([^|]+?)( -|$)',
            r'at ([^|]+?)( -|$)',
            r'location: ([^|]+?)[,\.]',
            r'located in ([^|]+?)[,\.]'
        ]
        
        for pattern in location_patterns:
            location_match = re.search(pattern, title, re.IGNORECASE)
            if location_match:
                location_candidate = location_match.group(1).strip()
                if 2 <= len(location_candidate) <= 50:
                    location = location_candidate
                    break
        
        # If location still unknown, try snippet
        if location == "Unknown Location":
            for pattern in location_patterns:
                location_match = re.search(pattern, snippet, re.IGNORECASE)
                if location_match:
                    location_candidate = location_match.group(1).strip()
                    if 2 <= len(location_candidate) <= 50:
                        location = location_candidate
                        break
        
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
            r'ziprecruiter\.com/.*detail',
            r'lever\.co',
            r'greenhouse\.io',
            r'workable\.com',
            r'careers.*\.com/job',
            r'jobs.*\.com/job',
            r'apply.workable.com',
            r'boards.greenhouse.io'
        ]
        
        # Check if URL matches any real job pattern
        is_real_job_url = any(re.search(pattern, url) for pattern in real_job_patterns)
        
        # Check if the job has minimum required information
        has_minimum_info = (
            job.get('title', '') and 
            job.get('company', '') != "Unknown Company" and
            len(job.get('description_snippet', '')) > 20  # Ensure some description
        )
        
        # If URL matches known job posting patterns, it's likely a real job
        if is_real_job_url and has_minimum_info:
            return True
            
        return False
    
    def _appears_to_be_job(self, job):
        """Less strict check to determine if a result is likely a job posting"""
        # Check if title and snippet contain job-related keywords
        title = job.get('title', '').lower()
        snippet = job.get('description_snippet', '').lower()
        combined = title + " " + snippet
        
        # Keywords that suggest a job posting
        job_keywords = [
            'hiring', 'job', 'career', 'position', 'opportunity', 'apply',
            'employment', 'full-time', 'part-time', 'salary', 'remote work',
            'work from home', 'responsibilities', 'qualifications', 'required',
            'experience needed', 'skills', 'we are looking', 'join our team'
        ]
        
        # Check for at least 2 job keywords
        keyword_count = sum(1 for keyword in job_keywords if keyword in combined)
        if keyword_count >= 2:
            return True
            
        # Check if the URL contains job-related paths
        url = job.get('url', '').lower()
        job_url_patterns = [
            '/job', '/career', '/opening', '/position', '/apply',
            '/employment', '/opportunity', '/listing', '/vacancy'
        ]
        
        if any(pattern in url for pattern in job_url_patterns):
            return True
            
        return False
    
    def _score_results(self, results, resume_data, preferences):
        """Score job results based on relevance to resume and preferences"""
        if not results:
            return []
            
        # Extract skills and experience from resume_data if available
        candidate_skills = []
        candidate_field = None
        preferred_job_types = []
        preferred_industries = []
        preferred_remote = False
        preferred_location = None
        
        # Extract skills from resume
        if resume_data and isinstance(resume_data, dict):
            data = resume_data
            if "structured_info" in data:
                data = data["structured_info"]
                
            if "skills" in data and isinstance(data["skills"], list):
                candidate_skills = [skill.lower() for skill in data["skills"]]
                
            if "field" in data:
                candidate_field = data["field"].lower()
        
        # Extract preferences
        if preferences and isinstance(preferences, dict):
            if "job_types" in preferences and isinstance(preferences["job_types"], list):
                preferred_job_types = [jt.lower() for jt in preferences["job_types"]]
                
            if "industry_preferences" in preferences and isinstance(preferences["industry_preferences"], list):
                preferred_industries = [ind.lower() for ind in preferences["industry_preferences"]]
                
            if "remote_preference" in preferences:
                remote_pref = preferences["remote_preference"]
                if isinstance(remote_pref, str) and "remote" in remote_pref.lower():
                    preferred_remote = True
                    
            if "location_preferences" in preferences:
                preferred_location = preferences["location_preferences"].lower() if preferences["location_preferences"] else None
        
        # Score each result
        for job in results:
            score = 5.0  # Base score
            
            # Convert text fields to lowercase for matching
            job_title = job.get('title', '').lower()
            job_company = job.get('company', '').lower()
            job_snippet = job.get('description_snippet', '').lower() 
            job_location = job.get('location', '').lower()
            
            # Combined text for matching
            job_text = f"{job_title} {job_company} {job_snippet}"
            
            # Store matching details for explanation
            matching_details = {}
            
            # 1. Match skills
            matching_skills = []
            for skill in candidate_skills:
                if skill in job_text:
                    matching_skills.append(skill)
            
            if matching_skills:
                # More matching skills = higher score
                skill_bonus = min(3.0, len(matching_skills) * 0.5)  # Up to 3 points for skills
                score += skill_bonus
                matching_details["skills"] = matching_skills
            
            # 2. Match field/industry
            if candidate_field and candidate_field in job_text:
                score += 1.0
                matching_details["field"] = candidate_field
            
            # 3. Match job type
            matching_job_types = []
            for job_type in preferred_job_types:
                if job_type in job_text:
                    matching_job_types.append(job_type)
            
            if matching_job_types:
                job_type_bonus = min(1.0, len(matching_job_types) * 0.5)
                score += job_type_bonus
                matching_details["job_types"] = matching_job_types
            
            # 4. Match industry
            matching_industries = []
            for industry in preferred_industries:
                if industry in job_text:
                    matching_industries.append(industry)
            
            if matching_industries:
                industry_bonus = min(1.0, len(matching_industries) * 0.5)
                score += industry_bonus
                matching_details["industries"] = matching_industries
            
            # 5. Match remote preference
            if preferred_remote and job.get('is_remote', False):
                score += 1.0
                matching_details["remote"] = True
            
            # 6. Match location
            if preferred_location and preferred_location in job_location:
                score += 1.0
                matching_details["location"] = preferred_location
            
            # Store the final score (capped at 10)
            job["relevance_score"] = min(10.0, score)
            job["matching_details"] = matching_details
            
            # Generate human-readable explanation
            job["score_explanation"] = self._generate_score_explanation(job)
        
        return results
    
    def _generate_score_explanation(self, job):
        """Generate a human-readable explanation of the matching score"""
        matching_details = job.get("matching_details", {})
        explanations = []
        
        # Add skill matches
        if "skills" in matching_details:
            skills = matching_details["skills"]
            if len(skills) == 1:
                explanations.append(f"Matches skill: {skills[0]}")
            else:
                skill_text = ", ".join(skills[:3])
                if len(skills) > 3:
                    skill_text += f" and {len(skills) - 3} more"
                explanations.append(f"Matches skills: {skill_text}")
        
        # Add field match
        if "field" in matching_details:
            explanations.append(f"Matches field: {matching_details['field']}")
        
        # Add job type matches
        if "job_types" in matching_details:
            job_types = matching_details["job_types"]
            explanations.append(f"Matches job types: {', '.join(job_types)}")
        
        # Add industry matches
        if "industries" in matching_details:
            industries = matching_details["industries"]
            explanations.append(f"Matches industries: {', '.join(industries)}")
        
        # Add location match
        if "location" in matching_details:
            explanations.append(f"Location match: {matching_details['location']}")
        
        # Add remote match
        if matching_details.get("remote", False):
            explanations.append("Matches remote preference")
        
        # Default explanation if no specific matches
        if not explanations:
            explanations.append("Basic match based on job search criteria")
        
        # Join all explanations
        return "; ".join(explanations)