# main.py
import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv

os.environ["CREWAI_DISABLE_EMBEDDINGS"] = "true"
import sys
print(sys.executable)  # This tells you which Python installation is running

# Load environment variables from .env file
load_dotenv()

try:
    from sqlite_fix import *
except ImportError:
    pass

# Import wrapper for CrewAI to handle import errors gracefully
try:
    from crewai import Crew, Agent, Task, Process, Tool
    CREWAI_AVAILABLE = True
except ImportError:
    print("CrewAI not installed. Install with: pip install crewai")
    CREWAI_AVAILABLE = False
    # Define placeholder classes
    class Agent:
        def __init__(self, **kwargs): pass
    class Task:
        def __init__(self, **kwargs): pass
    class Crew:
        def __init__(self, **kwargs): pass
    class Process:
        sequential = "sequential"
    class Tool:
        def __init__(self, **kwargs): pass

# Import custom tools with error handling
try:
    from resume_parser import ResumeParser
except ImportError:
    print("ResumeParser not available. Make sure resume_parser.py is in the current directory.")
    # Create dummy class for fallback
    class ResumeParser:
        def __init__(self, **kwargs): pass
        def run(self, **kwargs): return {}
        def _run(self, **kwargs): return {}
        def process_resume(self, file_path): return {}

# Try to import Serper job search tool first
try:
    from real_serper_job_search import SerperJobSearchTool
    SERPER_AVAILABLE = True
    print("Serper job search tool available")
except ImportError:
    SERPER_AVAILABLE = False
    print("SerperJobSearchTool not available. Will fall back to basic JobSearchTool.")

try:
    from job_search import JobSearchTool
except ImportError:
    print("JobSearchTool not available. Make sure job_search.py is in the current directory.")
    class JobSearchTool:
        def __init__(self, **kwargs): pass
        def run(self, **kwargs): return []

try:
    from application_submitter import ApplicationSubmitter
except ImportError:
    print("ApplicationSubmitter not available. Make sure application_submitter.py is in the current directory.")
    class ApplicationSubmitter:
        def __init__(self, **kwargs): pass
        def run(self, **kwargs): return {}

# Import tool functions
try:
    from tool_functions import analyze_resume, search_jobs, submit_application
except ImportError:
    # Define fallback functions if import fails
    def analyze_resume(resume_path):
        return {"error": "Tool function not available"}
    
    def search_jobs(search_query, location="", job_type="fulltime", limit=10):
        return {"error": "Tool function not available"}
    
    def submit_application(job_posting, applicant_data, resume_path, dry_run=True):
        return {"error": "Tool function not available"}

# Import LLM factory with error handling
try:
    from llm_factory import LLMConfig, LLMFactory
except ImportError:
    print("LLM Factory not available. Make sure llm_factory.py is in the current directory.")
    class LLMConfig:
        def __init__(self, **kwargs): pass
    class LLMFactory:
        @staticmethod
        def create_llm(config): return None

class AutoJobApplicator:
    """Main orchestrator for the automated job application system"""
    
    def __init__(self, llm_config: Dict[str, Any] = None):
        """Initialize the job application system"""
        # Set up LLM configuration
        self.llm_config = llm_config or {
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": os.environ.get("OPENAI_API_KEY"),
            "parameters": {
                "temperature": 0.5
            }
        }
        
        # Create LLM instance
        self.llm_config_obj = LLMConfig(
            provider=self.llm_config["provider"],
            model_name=self.llm_config["model_name"],
            api_key=self.llm_config["api_key"],
            parameters=self.llm_config["parameters"]
        )
        
        # Create LLM instance with better error handling
        try:
            self.llm = LLMFactory.create_llm(self.llm_config_obj)
        except ValueError as e:
            if "API key" in str(e):
                print("No API key found. Running in limited functionality mode.")
                self.llm = None
            else:
                raise e
        except Exception as e:
            print(f"Error creating LLM: {str(e)}")
            self.llm = None
        
        # Initialize tools for direct use
        self.resume_parser = ResumeParser(llm=self.llm)
        self.job_search_tool = JobSearchTool(llm=self.llm)
        self.application_submitter = ApplicationSubmitter(llm=self.llm)
        
        # Initialize agents if CrewAI is available
        if CREWAI_AVAILABLE:
            self._create_agents()
            
            # Initialize tasks
            self._create_tasks()
            
            # Initialize crew
            self._create_crew()
        else:
            print("CrewAI not available. Some functionality will be limited.")
        
        # State management
        self.resume_data = None
        self.job_preferences = None
        self.found_jobs = []
        self.approved_jobs = []
        self.application_results = []
    
    def _create_agents(self):
        """Create the agent crew members using function-based tools"""
        # Create tools using functions
        resume_tool = Tool(
            name="ResumeAnalyzer",
            description="Analyzes a resume and extracts key information",
            func=analyze_resume
        )

        job_search_tool = Tool(
            name="JobSearcher",
            description="Searches for job postings based on criteria",
            func=search_jobs
        )

        application_tool = Tool(
            name="ApplicationSubmitter",
            description="Submits a job application",
            func=submit_application
        )

        # Resume Analysis Agent
        self.resume_analyst = Agent(
            role="Resume Analyst",
            goal="Extract comprehensive career information from resumes and identify ideal job types",
            backstory="""You are an expert at analyzing resumes and extracting key information. 
            You have a deep understanding of different industries and roles, allowing you to identify 
            the most relevant job opportunities for candidates based on their experience.""",
            tools=[resume_tool],
            llm=self.llm,
            verbose=True
        )
        
        # Job Search Agent
        self.job_finder = Agent(
            role="Job Search Specialist",
            goal="Find the most suitable job openings based on candidate qualifications and preferences",
            backstory="""You are a master job hunter who knows how to navigate various job platforms. 
            You understand what makes a good job match and can filter through listings to find 
            the best opportunities that match a candidate's skills and preferences.""",
            tools=[job_search_tool],
            llm=self.llm,
            verbose=True
        )
        
        # Application Specialist Agent
        self.application_specialist = Agent(
            role="Application Specialist",
            goal="Submit optimized job applications that maximize the chance of getting interviews",
            backstory="""You are an expert at crafting compelling job applications. 
            You know how to present a candidate's qualifications in the best light and 
            navigate application systems efficiently to submit high-quality applications.""",
            tools=[application_tool],
            llm=self.llm,
            verbose=True
        )
        
        # Coordination Agent
        self.coordinator = Agent(
            role="Application Coordinator",
            goal="Oversee the entire job application process and ensure all steps are completed effectively",
            backstory="""You are a master orchestrator who manages complex workflows. 
            You collect user preferences, coordinate between specialists, and ensure 
            the job application process runs smoothly from start to finish.""",
            tools=[],
            llm=self.llm,
            verbose=True
        )
    
    def _create_tasks(self):
        """Create the tasks for the crew"""
        # Task 1: Analyze Resume
        self.analyze_resume_task = Task(
            description="""
            Analyze the candidate's resume thoroughly to extract:
            1. Contact information and personal details
            2. Skills (technical and soft)
            3. Work experience and accomplishments
            4. Education and certifications
            5. Career narrative and strengths
            
            Then, identify the most suitable job types and roles based on the resume.
            Provide a detailed summary of findings.
            """,
            agent=self.resume_analyst,
            expected_output="A comprehensive analysis of the resume and recommended job types",
            context=None
        )
        
        # Task 2: Collect User Preferences
        self.collect_preferences_task = Task(
            description="""
            Engage with the user to collect their job search preferences:
            1. Preferred company types (startups, mid-size, enterprise)
            2. Industry preferences
            3. Location preferences (including remote options)
            4. Salary expectations
            5. Other important factors (culture, benefits, etc.)
            6. How many job applications to submit
            
            Based on the resume analysis and these preferences, create a detailed job search strategy.
            """,
            agent=self.coordinator,
            expected_output="A complete job search strategy based on user preferences and resume analysis",
            context=None
        )
        
        # Task 3: Search for Jobs
        self.search_jobs_task = Task(
            description="""
            Using the job search strategy and resume analysis:
            1. Search for relevant job openings across multiple platforms
            2. Filter results based on user preferences
            3. Rank opportunities by relevance and potential fit
            4. Provide a detailed report of the top matches
            
            Identify at least {max_jobs} potential opportunities that match the criteria.
            """,
            agent=self.job_finder,
            expected_output="A ranked list of job opportunities with details and rationale for each match",
            context=None
        )
        
        # Task 4: Present Jobs for Approval
        self.present_jobs_task = Task(
            description="""
            Present the identified job opportunities to the user for approval:
            1. Summarize each opportunity clearly
            2. Explain why it's a good match based on resume and preferences
            3. Collect user feedback on which opportunities to pursue
            
            Obtain explicit approval for each job application before proceeding.
            """,
            agent=self.coordinator,
            expected_output="A list of user-approved job opportunities to apply for",
            context=None
        )
        
        # Task 5: Submit Applications
        self.submit_applications_task = Task(
            description="""
            For each approved job opportunity:
            1. Generate a customized cover letter highlighting relevant experience
            2. Prepare application materials tailored to the specific role
            3. Submit the application through the appropriate channel
            4. Track submission status and details
            
            Provide a detailed report of all submission attempts and outcomes.
            """,
            agent=self.application_specialist,
            expected_output="A complete report of application submissions with status for each",
            context=None
        )
        
        # Task 6: Final Report
        self.final_report_task = Task(
            description="""
            Prepare a comprehensive final report for the user:
            1. Summary of all applications submitted
            2. Status of each application
            3. Recommendations for follow-up actions
            4. Suggested improvements for future applications
            
            Present this information in a clear, actionable format.
            """,
            agent=self.coordinator,
            expected_output="A final report detailing all application activities and next steps",
            context=None
        )
    
    def _create_crew(self):
        """Create the CrewAI crew with all agents and tasks"""
        self.crew = Crew(
            agents=[
                self.resume_analyst,
                self.job_finder,
                self.application_specialist,
                self.coordinator
            ],
            tasks=[
                self.analyze_resume_task,
                self.collect_preferences_task,
                self.search_jobs_task,
                self.present_jobs_task,
                self.submit_applications_task,
                self.final_report_task
            ],
            verbose=True,
            process=Process.sequential  # Tasks will be executed in order
        )
    
    def run(self, resume_path: str, max_jobs: int = 10, dry_run: bool = True):
        """Run the full job application process"""
        if not CREWAI_AVAILABLE:
            return {"error": "CrewAI not available. Cannot run full process."}
            
        # Update context for tasks with dynamic parameters
        self.analyze_resume_task.context = {"resume_path": resume_path}
        self.search_jobs_task.context = {"max_jobs": max_jobs}
        self.submit_applications_task.context = {"dry_run": dry_run}
        
        # Execute the crew workflow
        try:
            result = self.crew.kickoff()
            return result
        except Exception as e:
            print(f"Error running crew workflow: {str(e)}")
            return {"error": str(e)}
    
    def analyze_resume_only(self, resume_path: str):
        """Run only the resume analysis step"""
        try:
            # Use direct function call with correct parameter format
            return analyze_resume({"file_path": resume_path})
        except Exception as e:
            print(f"Error analyzing resume: {str(e)}")
            return {"error": str(e)}
    
    def search_jobs_only(self, resume_analysis: Dict[str, Any], preferences: Dict[str, Any], max_jobs: int = 10):
        """Run only the job search step"""
        try:
            if CREWAI_AVAILABLE:
                self.search_jobs_task.context = {
                    "resume_analysis": resume_analysis,
                    "preferences": preferences,
                    "max_jobs": max_jobs
                }
                result = self.job_finder.execute_task(self.search_jobs_task)
            else:
                # Direct tool usage if CrewAI not available
                search_query = ""
                
                # Try to get search terms from preferences or resume analysis
                if "job_types" in preferences and preferences["job_types"]:
                    search_query = preferences["job_types"][0] 
                elif isinstance(resume_analysis, dict):
                    data = resume_analysis
                    if "structured_info" in data:
                        data = data["structured_info"]
                    
                    if "recommended_jobs" in data and data["recommended_jobs"]:
                        search_query = data["recommended_jobs"][0]
                
                # Default if nothing found
                if not search_query:
                    search_query = "Software Engineer"
                    
                location = preferences.get("location_preferences", "")
                
                # IMPORTANT: Use query instead of search_query parameter
                result = self.job_search_tool._run(
                    query=search_query,
                    location=location,
                    limit=max_jobs
                )
                
            return result
        except Exception as e:
            print(f"Error searching jobs: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return {"error": str(e)}
    
    def submit_applications_only(self, approved_jobs: List[Dict[str, Any]], applicant_data: Dict[str, Any], resume_path: str, dry_run: bool = True):
        """Run only the application submission step"""
        try:
            results = []
            for job in approved_jobs:
                result = submit_application(
                    job_posting=job,
                    applicant_data=applicant_data,
                    resume_path=resume_path,
                    dry_run=dry_run
                )
                results.append(result)
                
            return results
        except Exception as e:
            print(f"Error submitting applications: {str(e)}")
            return {"error": str(e)}

def main():
    """Command line interface for the job application system"""
    parser = argparse.ArgumentParser(description="Automated Job Application System")
    
    # Add arguments
    parser.add_argument("--resume", required=True, help="Path to resume file")
    parser.add_argument("--llm-provider", default="openai", help="LLM provider (openai, huggingface, ollama, anthropic, etc.)")
    parser.add_argument("--llm-model", default="gpt-4o", help="Model name for the chosen provider")
    parser.add_argument("--max-jobs", type=int, default=10, help="Maximum number of jobs to find")
    parser.add_argument("--dry-run", action="store_true", help="Simulate application submissions without actually submitting")
    parser.add_argument("--api-key", help="API key for the LLM provider (if not set in environment variables)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if resume file exists
    if not os.path.exists(args.resume):
        print(f"Error: Resume file '{args.resume}' not found")
        return
    
    # Set up LLM configuration
    llm_config = {
        "provider": args.llm_provider,
        "model_name": args.llm_model,
        "api_key": args.api_key or os.environ.get(f"{args.llm_provider.upper()}_API_KEY"),
        "parameters": {
            "temperature": 0.5
        }
    }
    
    # Initialize the job applicator
    job_applicator = AutoJobApplicator(llm_config=llm_config)
    
    # Run the process
    result = job_applicator.run(
        resume_path=args.resume,
        max_jobs=args.max_jobs,
        dry_run=args.dry_run
    )
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"application_results_{timestamp}.json", "w") as f:
        json.dump(result, f, indent=4)
    
    print(f"Application process completed. Results saved to application_results_{timestamp}.json")

if __name__ == "__main__":
    main()