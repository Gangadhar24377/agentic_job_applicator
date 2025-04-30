# app_web_jobs.py - Updated to use new WebJobSearchTool
import streamlit as st
import os
import json
import time
from datetime import datetime
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
import sys
import traceback

# Load environment variables
load_dotenv()

# Display the Python path to help debug import issues
print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")

# Add current directory to Python path for reliable imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Disable Streamlit watcher to avoid PyTorch conflict
os.environ['STREAMLIT_SERVER_WATCH_FILES'] = 'false'


# Try to import the web job search tool - prioritize this
try:
    from web_job_search import WebJobSearchTool
    WEB_SEARCH_AVAILABLE = True
    print("Web job search tool available")
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    print("WebJobSearchTool not available. Make sure web_job_search.py is in the current directory.")


# Add this near the imports section where other availability flags are defined
try:
    from real_serper_job_search import RealJobSearchTool
    REAL_SEARCH_AVAILABLE = True
    print("Real job search tool available")
except ImportError:
    REAL_SEARCH_AVAILABLE = False
    print("RealJobSearchTool not available. Will fall back to other search methods.")

# Import custom tools directly - fallback if main module has issues
try:
    from main import AutoJobApplicator
    MAIN_AVAILABLE = True
except ImportError:
    MAIN_AVAILABLE = False
    try:
        from resume_parser import ResumeParser
        
        # Try to import other job search tools as fallbacks
        try:
            from real_serper_job_search import RealJobSearchTool
            REAL_SEARCH_AVAILABLE = True
        except ImportError:
            REAL_SEARCH_AVAILABLE = False
            
            try:
                from real_serper_job_search import SerperJobSearchTool
                SERPER_AVAILABLE = True
            except ImportError:
                SERPER_AVAILABLE = False
                
                try:
                    from job_search import JobSearchTool
                    BASIC_SEARCH_AVAILABLE = True
                except ImportError:
                    BASIC_SEARCH_AVAILABLE = False
        
        from application_submitter import ApplicationSubmitter
    except ImportError:
        st.error("Required modules not available. Please check your installation.")
        st.stop()

# Try to import CrewAI to check if it's actually installed
try:
    import crewai
    print(f"CrewAI is installed. Version: {crewai.__version__}")
    CREWAI_AVAILABLE = True
except ImportError:
    print("CrewAI import failed. Will run in limited functionality mode.")
    CREWAI_AVAILABLE = False

# Set page configuration
st.set_page_config(
    page_title="Auto Job Applicator",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables
if "resume_analyzed" not in st.session_state:
    st.session_state.resume_analyzed = False
if "resume_data" not in st.session_state:
    st.session_state.resume_data = None
if "preferences_collected" not in st.session_state:
    st.session_state.preferences_collected = False
if "job_preferences" not in st.session_state:
    st.session_state.job_preferences = {}
if "jobs_found" not in st.session_state:
    st.session_state.jobs_found = []
if "approved_jobs" not in st.session_state:
    st.session_state.approved_jobs = []
if "application_results" not in st.session_state:
    st.session_state.application_results = []
if "job_applicator" not in st.session_state:
    st.session_state.job_applicator = None

# Sidebar for configuration
st.sidebar.title("⚙️ Configuration")

# LLM Provider selection
llm_provider = st.sidebar.selectbox(
    "LLM Provider",
    ["OpenAI", "Anthropic", "Hugging Face", "Ollama", "Custom"],
    index=0
)

# Model selection based on provider
if llm_provider == "OpenAI":
    model_options = ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
elif llm_provider == "Anthropic":
    model_options = ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
elif llm_provider == "Hugging Face":
    model_options = ["mistralai/Mixtral-8x7B-Instruct-v0.1", "meta-llama/Llama-2-70b-chat-hf"]
elif llm_provider == "Ollama":
    model_options = ["llama3", "mixtral", "mistral"]
else:  # Custom
    model_options = ["custom-model"]

llm_model = st.sidebar.selectbox("Model", model_options)

# API Key input with proper handling
api_key = st.sidebar.text_input("API Key (optional if set in environment)", type="password")
if api_key:
    os.environ[f"{llm_provider.upper()}_API_KEY"] = api_key

# Serper API Key input
serper_api_key = st.sidebar.text_input("Serper API Key (for job search)", type="password")
if serper_api_key:
    os.environ["SERPER_API_KEY"] = serper_api_key

# Advanced options
with st.sidebar.expander("Advanced Options"):
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.5, step=0.1)
    max_jobs = st.number_input("Maximum Jobs to Find", min_value=5, max_value=50, value=10)
    
    # Additional search options
    search_depth = st.slider("Search Depth", min_value=1, max_value=5, value=3, 
                          help="Higher values search more broadly but take longer")
    
    if llm_provider == "Custom":
        custom_endpoint = st.text_input("Custom Endpoint URL")

# Application Settings
with st.sidebar.expander("Application Settings"):
    dry_run = st.checkbox("Dry Run (simulate applications without submitting)", value=True)
    delay_between_apps = st.slider("Delay Between Applications (seconds)", min_value=1, max_value=60, value=5)

# Main interface
st.title("🤖 Agentic Job Application System")

# Check if Serper API key is available
if not os.environ.get("SERPER_API_KEY") and not serper_api_key:
    st.warning("No Serper API key found. Please enter a Serper API key in the sidebar to enable web job search functionality.")

# Use simple direct approach if main module isn't available
direct_mode = not MAIN_AVAILABLE

# Initialize the system - use either AutoJobApplicator or direct tools
def initialize_system():
    """Initialize the LLM system - fixed to prevent recursion"""
    if not MAIN_AVAILABLE:
        st.error("AutoJobApplicator not available. Using direct tools instead.")
        return False
        
    # Set up LLM configuration
    llm_config = {
        "provider": llm_provider.lower(),
        "model_name": llm_model,
        "api_key": api_key or os.environ.get(f"{llm_provider.upper()}_API_KEY"),
        "parameters": {
            "temperature": temperature
        }
    }
    
    # Add custom endpoint if applicable
    if llm_provider == "Custom" and 'custom_endpoint' in locals():
        llm_config["parameters"]["endpoint_url"] = custom_endpoint
    
    # Initialize or update the job applicator
    try:
        st.session_state.job_applicator = AutoJobApplicator(llm_config=llm_config)
        return True
    except Exception as e:
        st.error(f"Error initializing the system: {str(e)}")
        return False

# Step 1: Upload Resume
st.header("Step 1: Upload Your Resume")

resume_file = st.file_uploader("Upload your resume (PDF or DOCX)", type=["pdf", "docx"])

if resume_file is not None:
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # Save the uploaded file
    resume_path = os.path.join("uploads", resume_file.name)
    
    with open(resume_path, "wb") as f:
        f.write(resume_file.getbuffer())
    
    st.success(f"Resume uploaded: {resume_file.name}")
    
    # Analyze resume button
    if st.button("Analyze Resume"):
        with st.spinner("Analyzing your resume... This may take a minute."):
            try:
                if direct_mode:
                    # Create a new parser instance
                    parser = ResumeParser()
                    
                    # Call process_resume directly to avoid any recursion
                    result = parser.process_resume(resume_path)
                    
                    # Store the results
                    st.session_state.resume_data = result
                    st.session_state.resume_analyzed = True
                    st.success("Resume analysis complete!")
                else:
                    # Initialize the system if not already initialized
                    if st.session_state.job_applicator is None:
                        # Call initialize_system function without recursion
                        init_result = initialize_system()
                        if not init_result:
                            # Fall back to direct mode if initialization fails
                            parser = ResumeParser()
                            result = parser.process_resume(resume_path)
                            st.session_state.resume_data = result
                            st.session_state.resume_analyzed = True
                            st.success("Resume analysis complete (using fallback mode)!")
                            st.stop()
                    
                    # Use job applicator
                    result = st.session_state.job_applicator.analyze_resume_only(resume_path)
                    
                    # Handle different result formats
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"Error analyzing resume: {result['error']}")
                    else:
                        st.session_state.resume_data = result
                        st.session_state.resume_analyzed = True
                        st.success("Resume analysis complete!")
            except Exception as e:
                st.error(f"Error analyzing resume: {str(e)}")
                st.code(traceback.format_exc())

# Display resume analysis if available
if st.session_state.resume_analyzed and st.session_state.resume_data:
    with st.expander("Resume Analysis Results", expanded=True):
        # Pretty print the resume data in a more user-friendly format
        resume_data = st.session_state.resume_data
        
        # Convert to more readable format if it's a string
        if isinstance(resume_data, str):
            try:
                # Try to parse as JSON if it's a JSON string
                if resume_data.startswith("{") and resume_data.endswith("}"):
                    resume_data = json.loads(resume_data)
            except:
                pass
        
        if isinstance(resume_data, dict):
            # Extract structured_info if present
            if "structured_info" in resume_data:
                resume_data = resume_data["structured_info"]
                
            # Extract and display key information
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Skills Identified")
                if "skills" in resume_data:
                    skills = resume_data["skills"]
                    if isinstance(skills, list):
                        for skill in skills:
                            st.write(f"• {skill}")
                    else:
                        st.write(skills)
                
                st.subheader("Education")
                if "education" in resume_data:
                    education = resume_data["education"]
                    if isinstance(education, list):
                        for edu in education:
                            st.write(f"• {edu}")
                    else:
                        st.write(education)
            
            with col2:
                st.subheader("Experience Summary")
                if "work_experience" in resume_data:
                    experience = resume_data["work_experience"]
                    if isinstance(experience, list):
                        for exp in experience[:3]:  # Show only first 3 for brevity
                            st.write(f"• {exp}")
                        if len(experience) > 3:
                            st.write(f"... and {len(experience) - 3} more")
                    else:
                        st.write(experience)
                
                st.subheader("Recommended Job Types")
                if "recommended_jobs" in resume_data:
                    jobs = resume_data["recommended_jobs"]
                    if isinstance(jobs, list):
                        for job in jobs:
                            st.write(f"• {job}")
                    else:
                        st.write(jobs)
        else:
            # If it's a string or other format, display as is
            st.write(resume_data)

# Step 2: Job Preferences
if st.session_state.resume_analyzed:
    st.header("Step 2: Set Your Job Preferences")
    
    # Get recommended jobs if available to use as defaults
    default_job_types = []
    if st.session_state.resume_data and isinstance(st.session_state.resume_data, dict):
        data = st.session_state.resume_data
        if "structured_info" in data:
            data = data["structured_info"]
        
        if "recommended_jobs" in data and isinstance(data["recommended_jobs"], list):
            # Take first recommended job for default
            default_job_types = [data["recommended_jobs"][0]] if data["recommended_jobs"] else []
    
    col1, col2 = st.columns(2)
    
    with col1:
        company_types = st.multiselect(
            "Company Types",
            ["Startups", "Small Business", "Mid-size", "Enterprise", "Fortune 500", "Non-profit"],
            default=["Startups", "Mid-size"]
        )
        
        industry_preferences = st.multiselect(
            "Industry Preferences",
            ["Technology", "Finance", "Healthcare", "Education", "Manufacturing", "Retail", 
             "Media", "Government", "Non-profit", "Energy", "Transportation", "Other"],
            default=["Technology"]
        )
        
        location_preferences = st.text_input("Location Preferences (cities, states, or 'Remote')")
        
        remote_preference = st.selectbox(
            "Remote Work Preference",
            ["Remote Only", "Hybrid", "On-site", "No Preference"],
            index=3
        )
    
    with col2:
        experience_level = st.selectbox(
            "Experience Level",
            ["Entry Level", "Mid Level", "Senior", "Executive"],
            index=1
        )
        
        job_types = st.multiselect(
            "Job Types",
            ["Full-time", "Part-time", "Contract", "Freelance", "Internship"],
            default=["Full-time"]
        )
        
        salary_range = st.select_slider(
            "Desired Salary Range (USD)",
            options=["40k-60k", "60k-80k", "80k-100k", "100k-120k", "120k-150k", "150k+"],
            value="80k-100k"
        )
        
        num_applications = st.slider(
            "Number of Applications to Submit",
            min_value=1,
            max_value=max_jobs,
            value=min(5, max_jobs)
        )
    
    additional_preferences = st.text_area("Additional Preferences or Requirements")
    
    if st.button("Save Preferences"):
        st.session_state.job_preferences = {
            "company_types": company_types,
            "industry_preferences": industry_preferences,
            "location_preferences": location_preferences,
            "remote_preference": remote_preference,
            "experience_level": experience_level,
            "job_types": job_types,
            "salary_range": salary_range,
            "num_applications": num_applications,
            "additional_preferences": additional_preferences
        }
        
        st.session_state.preferences_collected = True
        st.success("Preferences saved successfully!")

# Step 3: Find Jobs
if st.session_state.preferences_collected:
    st.header("Step 3: Find Matching Jobs")
    
    # Prepare search terms based on resume and preferences
    search_terms = []
    
    # PRIORITY 1: First try to get recommended jobs from resume analysis
    if st.session_state.resume_data and isinstance(st.session_state.resume_data, dict):
        data = st.session_state.resume_data
        if "structured_info" in data:
            data = data["structured_info"]
        
        if "recommended_jobs" in data and isinstance(data["recommended_jobs"], list) and data["recommended_jobs"]:
            # Use ALL recommended jobs from the resume analysis
            search_terms.extend(data["recommended_jobs"])
            st.write("Using job recommendations from your resume analysis")
    
    # PRIORITY 2: If no recommended jobs found, use the job types from preferences
    if not search_terms and st.session_state.job_preferences:
        job_types = st.session_state.job_preferences.get("job_types", [])
        if job_types:
            st.write("No recommended jobs found in resume analysis. Using job types from your preferences.")
            search_terms.extend(job_types)  # Use the actual job types directly
    
    # PRIORITY 3: Final fallback to very generic terms only if nothing else is available
    if not search_terms:
        field = None
        # Try to extract field from resume data
        if st.session_state.resume_data and isinstance(st.session_state.resume_data, dict):
            data = st.session_state.resume_data
            if "structured_info" in data:
                data = data["structured_info"]
            if "field" in data and data["field"]:
                field = data["field"]
        
        # Use field + generic role as fallback
        if field:
            search_terms = [f"{field} Professional", f"{field} Specialist"]
        else:
            search_terms = ["Professional", "Specialist"]  # Very generic fallback
        st.write("No specific job recommendations found. Using generic search terms.")
    
    # Remove duplicates
    search_terms = list(set(search_terms))
    
    # Display search terms 
    st.write(f"Will search for: {', '.join(search_terms)}")
    
    # Check for Serper API key
    if not os.environ.get("SERPER_API_KEY") and not serper_api_key:
        st.error("Serper API key is required for job search. Please enter it in the sidebar.")
    else:
        # Display which search method will be used
        if WEB_SEARCH_AVAILABLE:
            st.info("Using comprehensive web job search with Serper API")
        elif REAL_SEARCH_AVAILABLE:
            st.info("Using real job search with Serper API")
        elif SERPER_AVAILABLE:
            st.info("Using basic Serper API for job search")
        else:
            st.warning("Using limited job search functionality - results may not be actual job listings")
    
    if st.button("Find Matching Jobs"):
        with st.spinner("Searching for matching jobs across the web... This may take a few minutes."):
            try:
                # Determine which job search tool to use, prioritizing the most advanced one available
                if WEB_SEARCH_AVAILABLE and (os.environ.get("SERPER_API_KEY") or serper_api_key):
                    # Use the new web job search tool
                    st.info("Using comprehensive web job search to find real job listings...")
                    
                    # Get API key from environment or input
                    api_key = os.environ.get("SERPER_API_KEY") or serper_api_key
                    
                    # Create the web job search tool
                    searcher = WebJobSearchTool(serper_api_key=api_key)
                    
                    # Build search query from first search term
                    # When searching with WebJobSearchTool
                search_query = search_terms[0] if search_terms else ""  # Empty default so we can detect and handle it

                if not search_query:
                    # If somehow we still have no search query, check if there's a field
                    field = None
                    if st.session_state.resume_data and isinstance(st.session_state.resume_data, dict):
                        data = st.session_state.resume_data.get("structured_info", st.session_state.resume_data)
                        field = data.get("field", "")
                    
                    # Use field or most generic term
                    search_query = field + " Professional" if field else "Professional"
                    location = st.session_state.job_preferences.get("location_preferences", "")
                    remote = "remote" in st.session_state.job_preferences.get("remote_preference", "").lower()
                    
                    # Run the search
                    result = searcher.run(
                    query=search_terms[0] if search_terms else "",  # Just pass the first search term
                    location=location,
                    remote=remote,
                    resume_data=st.session_state.resume_data,  # Pass FULL resume data
                    preferences=st.session_state.job_preferences,
                    limit=max_jobs,
                    all_recommended_jobs=True  # Add this flag to search all recommended jobs
                )
                
                # Fall back to other search tools if needed
                elif REAL_SEARCH_AVAILABLE and (os.environ.get("SERPER_API_KEY") or serper_api_key):
                    # Use RealJobSearchTool as fallback
                    api_key = os.environ.get("SERPER_API_KEY") or serper_api_key
                    searcher = RealJobSearchTool(serper_api_key=api_key)
                    
                    search_query = search_terms[0] if search_terms else "Software Engineer"
                    location = st.session_state.job_preferences.get("location_preferences", "")
                    remote = "remote" in st.session_state.job_preferences.get("remote_preference", "").lower()
                    
                    st.info("Using real job search with Serper API...")
                    result = searcher.run(
                        query=search_query,
                        location=location,
                        remote=remote,
                        resume_data=st.session_state.resume_data,
                        preferences=st.session_state.job_preferences,
                        limit=max_jobs
                    )
                    
                elif direct_mode:
                    if SERPER_AVAILABLE and (os.environ.get("SERPER_API_KEY") or serper_api_key):
                        # Use SerperJobSearchTool
                        api_key = os.environ.get("SERPER_API_KEY") or serper_api_key
                        searcher = SerperJobSearchTool(serper_api_key=api_key)
                        
                        st.info("Using Serper for job search based on your resume and preferences")
                        # Pass resume and preferences directly
                        result = searcher._run(
                            resume_data=st.session_state.resume_data,
                            preferences=st.session_state.job_preferences,
                            limit=max_jobs
                        )
                    elif BASIC_SEARCH_AVAILABLE:
                        # Fall back to basic search as last resort
                        searcher = JobSearchTool()
                        # Use first search term for simplicity
                        search_query = search_terms[0] if search_terms else "Software Engineer"
                        location = st.session_state.job_preferences.get("location_preferences", "")
                        
                        # Display what we're searching for
                        st.info(f"Using basic search for: {search_query} jobs in {location or 'any location'}")
                        
                        # Use query parameter
                        result = searcher._run(
                            query=search_query,
                            location=location,
                            limit=max_jobs
                        )
                    else:
                        st.error("No job search tools available. Please check your installation.")
                        st.stop()
                else:
                    # Initialize the system if not already initialized
                    if st.session_state.job_applicator is None:
                        # Call initialize_system function without recursion
                        init_result = initialize_system()
                        if not init_result:
                            st.stop()
                    
                    # Use job applicator
                    result = st.session_state.job_applicator.search_jobs_only(
                        resume_analysis=st.session_state.resume_data,
                        preferences=st.session_state.job_preferences,
                        max_jobs=max_jobs
                    )
                
                # Handle different result formats
                if isinstance(result, dict) and "error" in result:
                    st.error(f"Error finding jobs: {result['error']}")
                else:
                    # Parse the result
                    if isinstance(result, str):
                        try:
                            # Try to parse as JSON if it's a JSON string
                            if result.startswith("[") and result.endswith("]"):
                                result = json.loads(result)
                            elif result.startswith("{") and result.endswith("}"):
                                result_dict = json.loads(result)
                                if "jobs" in result_dict:
                                    result = result_dict["jobs"]
                        except:
                            # If parsing fails, treat as raw result
                            st.session_state.jobs_found = [{"title": "Parsing Error", "description": result}]
                    
                    # Store the results
                    if isinstance(result, list):
                        st.session_state.jobs_found = result
                    else:
                        st.session_state.jobs_found = [{"title": "Unknown Result", "description": str(result)}]
                    
                    st.success(f"Found {len(st.session_state.jobs_found)} matching jobs!")
            except Exception as e:
                st.error(f"Error finding jobs: {str(e)}")
                st.code(traceback.format_exc())

# Display found jobs if available
if st.session_state.jobs_found:
    with st.expander("Matching Jobs", expanded=True):
        # Convert to DataFrame for easier display
        jobs_data = []
        for i, job in enumerate(st.session_state.jobs_found):
            # Default values for missing fields
            job_title = job.get("title", "Unknown")
            job_company = job.get("company", "Unknown Company")
            job_location = job.get("location", "Unknown Location")
            job_platform = job.get("platform", "Unknown")
            job_score = job.get("relevance_score", 0)
            job_explanation = job.get("score_explanation", "")
            job_url = job.get("url", "")
            job_snippet = job.get("description_snippet", "No description available")
            job_salary = job.get("salary", "Not specified")
            job_date = job.get("posted_date", "Unknown")
            
            job_item = {
                "ID": i,
                "Title": job_title,
                "Company": job_company,
                "Location": job_location,
                "Platform": job_platform,
                "Match Score": job_score,
                "Score Explanation": job_explanation,
                "URL": job_url,
                "Salary": job_salary,
                "Posted": job_date,
                "Description": job_snippet[:150] + "..." if len(job_snippet) > 150 else job_snippet,
                "Apply": False  # Default selection state
            }
            jobs_data.append(job_item)
        
        jobs_df = pd.DataFrame(jobs_data)
        
        # Add checkboxes for selection
        st.write("Select jobs to apply for:")
        
        edited_df = st.data_editor(
            jobs_df,
            column_config={
                "ID": st.column_config.NumberColumn("ID", disabled=True),
                "Title": st.column_config.TextColumn("Job Title"),
                "Company": st.column_config.TextColumn("Company"),
                "Location": st.column_config.TextColumn("Location"),
                "Platform": st.column_config.TextColumn("Platform"),
                "Match Score": st.column_config.ProgressColumn(
                    "Match Score", 
                    min_value=0,
                    max_value=10,
                    format="%d"
                ),
                "Score Explanation": st.column_config.TextColumn("Match Details"),
                "Salary": st.column_config.TextColumn("Salary"),
                "Posted": st.column_config.TextColumn("Posted Date"),
                "Description": st.column_config.TextColumn("Description"),
                "URL": st.column_config.LinkColumn("Job Link"),
                "Apply": st.column_config.CheckboxColumn("Apply", default=False)
            },
            use_container_width=True,
            hide_index=True,
            num_rows="fixed"
        )
        
        # Button to save selections
        if st.button("Save Selected Jobs"):
            selected_job_ids = edited_df[edited_df["Apply"]]["ID"].tolist()
            st.session_state.approved_jobs = [st.session_state.jobs_found[i] for i in selected_job_ids]
            st.success(f"Selected {len(st.session_state.approved_jobs)} jobs for application!")

# Step 4: Submit Applications
if st.session_state.approved_jobs:
    st.header("Step 4: Submit Applications")
    
    st.write(f"Ready to apply to {len(st.session_state.approved_jobs)} selected jobs!")
    
    if dry_run:
        st.info("Running in simulation mode - no actual applications will be submitted")
    
    if st.button("Start Application Process"):
        with st.spinner("Submitting applications... This may take several minutes."):
            try:
                resume_path = os.path.join("uploads", resume_file.name)
                
                # Extract basic contact info if available
                applicant_name = "Applicant"
                if st.session_state.resume_data and isinstance(st.session_state.resume_data, dict):
                    data = st.session_state.resume_data
                    if "structured_info" in data:
                        data = data["structured_info"]
                        
                    if "contact_information" in data and isinstance(data["contact_information"], dict):
                        applicant_name = data["contact_information"].get("name", "Applicant")
                
                # Build applicant data
                applicant_data = {
                    "name": applicant_name,
                    "skills": [],  # Will be populated from resume data if available
                    "experience_summary": "Experienced professional"
                }
                
                # Add skills if available
                if st.session_state.resume_data and isinstance(st.session_state.resume_data, dict):
                    data = st.session_state.resume_data
                    if "structured_info" in data:
                        data = data["structured_info"]
                    
                    if "skills" in data and isinstance(data["skills"], list):
                        applicant_data["skills"] = data["skills"]
                
                if direct_mode:
                    # Use direct tool
                    submitter = ApplicationSubmitter()
                    results = []
                    
                    for job in st.session_state.approved_jobs:
                        result = submitter._run(
                            job_posting=job,
                            applicant_data=applicant_data,
                            resume_path=resume_path,
                            dry_run=dry_run
                        )
                        results.append(result)
                        # Add delay between submissions
                        time.sleep(delay_between_apps)
                    
                    result = results
                else:
                    # Initialize the system if not already initialized
                    if st.session_state.job_applicator is None:
                        # Call initialize_system function without recursion
                        init_result = initialize_system()
                        if not init_result:
                            st.stop()
                    
                    result = st.session_state.job_applicator.submit_applications_only(
                        approved_jobs=st.session_state.approved_jobs,
                        applicant_data=applicant_data,
                        resume_path=resume_path,
                        dry_run=dry_run
                    )
                
                # Handle different result formats
                if isinstance(result, dict) and "error" in result:
                    st.error(f"Error submitting applications: {result['error']}")
                else:
                    # Parse and store results
                    if isinstance(result, str):
                        try:
                            # Try to parse as JSON if it's a JSON string
                            if result.startswith("[") and result.endswith("]"):
                                result = json.loads(result)
                            elif result.startswith("{") and result.endswith("}"):
                                result_dict = json.loads(result)
                                if "applications" in result_dict:
                                    result = result_dict["applications"]
                        except:
                            # If parsing fails, use raw result
                            st.session_state.application_results = [{
                                "status": "error", 
                                "message": "Could not parse results",
                                "status": "error", 
                                "message": "Could not parse results", 
                                "details": result
                            }]
                    
                    # Store application results
                    if isinstance(result, list):
                        st.session_state.application_results = result
                    else:
                        st.session_state.application_results = [{
                            "status": "unknown", 
                            "message": str(result)
                        }]
                    
                    st.success("Application process completed!")
            except Exception as e:
                st.error(f"Error submitting applications: {str(e)}")
                st.code(traceback.format_exc())

# Display application results if available
if st.session_state.application_results:
    with st.expander("Application Results", expanded=True):
        for i, result in enumerate(st.session_state.application_results):
            status = result.get("status", "unknown")
            message = result.get("message", "No details available")
            job_title = result.get("job_title", f"Job {i+1}")
            company = result.get("company", "Unknown")
            
            if status == "success":
                st.success(f"✅ {job_title} at {company}: {message}")
            elif status == "simulated":
                st.info(f"🔄 {job_title} at {company}: {message}")
            elif status == "error":
                st.error(f"❌ {job_title} at {company}: {message}")
            else:
                st.warning(f"⚠️ {job_title} at {company}: {message}")
            
            st.write("---")
        
        # Summary statistics
        success_count = sum(1 for r in st.session_state.application_results if r.get("status") in ["success", "simulated"])
        error_count = sum(1 for r in st.session_state.application_results if r.get("status") == "error")
        
        # Create a simple pie chart if plotly is available
        try:
            summary_data = pd.DataFrame({
                "Status": ["Successful", "Failed"],
                "Count": [success_count, error_count]
            })
            
            fig = px.pie(
                summary_data, 
                values="Count", 
                names="Status",
                title="Application Results Summary",
                color="Status",
                color_discrete_map={"Successful": "#2ECC71", "Failed": "#E74C3C"}
            )
            
            st.plotly_chart(fig, use_container_width=True)
        except:
            # Fallback if plotly visualization fails
            st.write(f"Successful: {success_count}, Failed: {error_count}")

# Footer
st.write("---")
st.caption("© 2025 Auto Job Applicator")