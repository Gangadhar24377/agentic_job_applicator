# tool_functions.py
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

def analyze_resume(tool_input):
    """Analyze a resume and extract key information
    
    Args:
        tool_input: Can be a string (resume_path) or a dict with file_path
    """
    try:
        from resume_parser import ResumeParser
        parser = ResumeParser()
        
        # Handle different input types
        if isinstance(tool_input, str):
            resume_path = tool_input
        elif isinstance(tool_input, dict) and "file_path" in tool_input:
            resume_path = tool_input["file_path"]
        elif isinstance(tool_input, dict) and "resume_path" in tool_input:
            resume_path = tool_input["resume_path"]
        else:
            return {"error": f"Invalid input format: {tool_input}"}
        
        # IMPORTANT: Call _run directly to avoid recursion issues
        return parser._run(file_path=resume_path)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return {"error": f"{str(e)}\n{error_details}"}

def search_jobs(tool_input):
    """Search for job postings based on criteria
    
    Args:
        tool_input: Dict with search parameters or string with search query
    """
    try:
        # Try to import the Serper search tool first
        try:
            from real_serper_job_search import SerperJobSearchTool
            
            # Check if Serper API key is available
            serper_api_key = os.environ.get("SERPER_API_KEY")
            if serper_api_key:
                searcher = SerperJobSearchTool(serper_api_key=serper_api_key)
                print("Using Serper job search")
            else:
                # Fall back to basic job search if no API key
                from job_search import JobSearchTool
                searcher = JobSearchTool()
                print("Serper API key not found, falling back to basic job search")
        except ImportError:
            # Fall back to basic job search if Serper tool not available
            from job_search import JobSearchTool
            searcher = JobSearchTool()
            print("Serper job search not available, using basic job search")
        
        # Handle different input types
        if isinstance(tool_input, str):
            # If it's just a string, treat it as the search query
            return searcher._run(query=tool_input)
        elif isinstance(tool_input, dict):
            # For serper search, we want to pass all parameters directly
            # For basic search, convert 'search_query' to 'query'
            if hasattr(searcher, 'name') and searcher.name == 'SerperJobSearchTool':
                return searcher._run(**tool_input)
            else:
                # IMPORTANT: Convert any 'search_query' parameter to 'query'
                if 'search_query' in tool_input:
                    tool_input['query'] = tool_input.pop('search_query')
                
                # Call with the fixed parameters
                return searcher._run(**tool_input)
        else:
            return {"error": f"Invalid input format: {tool_input}"}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return {"error": f"{str(e)}\n{error_details}"}

def submit_application(tool_input):
    """Submit a job application
    
    Args:
        tool_input: Dict with application parameters
    """
    try:
        from application_submitter import ApplicationSubmitter
        submitter = ApplicationSubmitter()
        
        # Input validation
        if not isinstance(tool_input, dict):
            return {"error": "Input must be a dictionary"}
            
        # Required parameters
        job_posting = tool_input.get("job_posting")
        if not job_posting:
            return {"error": "job_posting is required"}
            
        applicant_data = tool_input.get("applicant_data", {"name": "Applicant"})
        resume_path = tool_input.get("resume_path")
        if not resume_path:
            return {"error": "resume_path is required"}
            
        dry_run = tool_input.get("dry_run", True)
        
        # Run the submitter
        return submitter._run(
            job_posting=job_posting,
            applicant_data=applicant_data,
            resume_path=resume_path,
            dry_run=dry_run
        )
    except Exception as e:
        return {"error": str(e)}