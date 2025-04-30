# resume_parser.py - Pydantic-compliant version
from typing import Dict, List, Any, Optional, ClassVar, Union
import PyPDF2
import docx
import json
import os
import re
from pydantic import Field

# Import BaseTool with error handling
try:
    from langchain.tools import BaseTool
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.schema import Document
except ImportError:
    try:
        from langchain.tools import BaseTool
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.schema.document import Document
    except ImportError:
        # Define simple base class if imports fail
        class BaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
            
            def _run(self, *args, **kwargs):
                raise NotImplementedError("Tool does not implement _run")
            
            def run(self, *args, **kwargs):
                return self._run(*args, **kwargs)
        
        class RecursiveCharacterTextSplitter:
            def __init__(self, chunk_size=1000, chunk_overlap=200):
                self.chunk_size = chunk_size
                self.chunk_overlap = chunk_overlap
                
            def create_documents(self, texts):
                if not texts:
                    return []
                    
                # Simple implementation for fallback
                docs = []
                for text in texts:
                    # Split text into chunks
                    chunks = []
                    for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                        end = min(i + self.chunk_size, len(text))
                        chunks.append(Document(page_content=text[i:end]))
                    docs.extend(chunks)
                return docs
        
        class Document:
            def __init__(self, page_content):
                self.page_content = page_content

# Define MockEmbeddings
class MockEmbeddings:
    def __init__(self, *args, **kwargs):
        pass
            
    def embed_query(self, text):
        # Return a simple embedding vector (random values)
        import random
        return [random.random() for _ in range(384)]

# Try to import actual embeddings
try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    try:
        from langchain.embeddings.openai import OpenAIEmbeddings
    except ImportError:
        OpenAIEmbeddings = MockEmbeddings

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    try:
        from langchain.embeddings import HuggingFaceEmbeddings
    except ImportError:
        HuggingFaceEmbeddings = MockEmbeddings

# Create a simple class that doesn't use Pydantic at all
class SimpleResumeParser:
    """Simple tool for extracting structured information from resumes without Pydantic"""
    
    def __init__(self, llm=None, embeddings=None):
        """Initialize the resume parser with optional LLM and embeddings"""
        self.name = "ResumeParser"
        self.description = "Extracts structured information from resume documents (PDF, DOCX)"
        self.llm = llm
        
        # Initialize embeddings
        if embeddings is None:
            # Try to use OpenAI embeddings, fall back to HuggingFace if no API key
            try:
                self.embeddings = OpenAIEmbeddings()
            except:
                try:
                    self.embeddings = HuggingFaceEmbeddings(
                        model_name="sentence-transformers/all-mpnet-base-v2"
                    )
                except:
                    # If both fail, use mock embeddings
                    self.embeddings = MockEmbeddings()
        else:
            self.embeddings = embeddings
            
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
    
    def run(self, tool_input):
        """Public method used by LangChain/CrewAI"""
        print(f"ResumeParser.run called with {type(tool_input)}")
        
        # Handle different input types
        if isinstance(tool_input, str):
            file_path = tool_input
        elif isinstance(tool_input, dict) and "file_path" in tool_input:
            file_path = tool_input["file_path"]
        else:
            raise ValueError(f"Invalid input format: {tool_input}")
        
        # Call the internal method directly to avoid recursion
        return self.process_resume(file_path)
    
    def _run(self, file_path):
        """Internal method required by LangChain"""
        print(f"ResumeParser._run called with {file_path}")
        
        # Call our process method to avoid any recursion issues
        return self.process_resume(file_path)
    
    def process_resume(self, file_path):
        """Main method to process a resume file - avoids any recursion issues"""
        print(f"Processing resume: {file_path}")
        
        try:
            # Extract text from document
            text = self.extract_text(file_path)
            
            # Split into sections
            sections = self.split_into_sections(text)
            
            # Extract structured information
            structured_info = self.extract_structured_info(sections, text)
            
            # Generate embeddings for semantic search
            embedded_sections = self.generate_embeddings(sections)
            
            return {
                "structured_info": structured_info,
                "embedded_sections": embedded_sections,
                "raw_text": text
            }
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Error processing resume: {str(e)}\n{error_details}")
            return {"error": f"Error processing resume: {str(e)}"}
    
    def extract_text(self, file_path):
        """Extract text from PDF or DOCX file"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == ".pdf":
            return self.extract_from_pdf(file_path)
        elif file_extension == ".docx":
            return self.extract_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def extract_from_pdf(self, file_path):
        """Extract text from PDF file"""
        text = ""
        
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
                
        return text
    
    def extract_from_docx(self, file_path):
        """Extract text from DOCX file"""
        doc = docx.Document(file_path)
        text = ""
        
        for para in doc.paragraphs:
            text += para.text + "\n"
            
        return text
    
    def split_into_sections(self, text):
        """Split resume text into manageable sections"""
        documents = self.text_splitter.create_documents([text])
        return documents
    
    def extract_structured_info(self, sections, full_text):
        """Extract structured information from resume sections"""
        if self.llm is None:
            # Return basic structured info without LLM
            return self.basic_extraction(sections, full_text)
        
        combined_text = "\n".join([doc.page_content for doc in sections])
        
        # General prompt engineering without specifying resume type
        prompt = f"""
        Extract structured information from the following resume text.
        Analyze the content carefully to determine the candidate's field and expertise.
        
        Return the information in JSON format with the following keys:
        - contact_information: Extract name, email, phone, LinkedIn/GitHub, and location
        - skills: List of skills mentioned in the resume, categorized by type (technical, soft, domain-specific)
        - work_experience: List of jobs with company, title, dates, and responsibilities
        - education: List of educational experiences with institution, degree, dates
        - projects: List of projects with name, description, technologies used
        - certifications: List of professional certifications if any
        - publications: Any publications or papers mentioned
        - field: The candidate's primary professional field based on resume content
        - recommended_jobs: Recommend at least 5 job roles that would be a good fit based on the candidate's skills and experience
        
        Resume text:
        {combined_text}
        
        Return only the JSON without any additional text.
        """
        
        # Get response from LLM
        try:
            response = self.llm.invoke(prompt)
            
            # For string responses (most LLMs)
            if isinstance(response, str):
                response_text = response
            # For LangChain message responses
            else:
                try:
                    response_text = response.content
                except:
                    response_text = str(response)
                
            # Parse JSON from response
            try:
                # Extract JSON if it's embedded in the response
                if "```json" in response_text:
                    json_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    json_text = response_text.split("```")[1].strip()
                else:
                    json_text = response_text.strip()
                    
                structured_info = json.loads(json_text)
                return structured_info
            except json.JSONDecodeError:
                # Fallback to basic extraction if JSON parsing fails
                return self.basic_extraction(sections, full_text)
                
        except Exception as e:
            print(f"Error using LLM for extraction: {str(e)}")
            return self.basic_extraction(sections, full_text)
    
    def basic_extraction(self, sections, full_text):
        """Basic rule-based extraction when LLM is not available"""
        combined_text = "\n".join([doc.page_content for doc in sections])
        
        # Find sections using regex
        sections_dict = self.identify_resume_sections(full_text)
        
        # Find potential email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_matches = re.findall(email_pattern, combined_text)
        email = email_matches[0] if email_matches else None
        
        # Find potential phone
        phone_pattern = r'\+?[0-9]{1,4}[-.\s]?[0-9]{3,4}[-.\s]?[0-9]{3,4}'
        phone_matches = re.findall(phone_pattern, combined_text)
        phone = phone_matches[0] if phone_matches else None
        
        # Find potential name - look for name at the beginning of the resume
        name = None
        first_lines = combined_text.split('\n')[:5]  # Check first 5 lines
        for line in first_lines:
            line = line.strip()
            # Look for a line with 2-3 words that doesn't contain email or phone
            if line and len(line.split()) <= 3 and '@' not in line and not re.search(phone_pattern, line):
                name = line
                break
        
        # Extract skills
        skills = []
        
        # Look for skill lists - items after bullets or in comma-separated lists
        skill_patterns = [
            r'•\s*([^•\n]+)', # Bullet points
            r'▪\s*([^▪\n]+)', # Different bullet type
            r'[\-\*]\s*([^\-\*\n]+)', # Dashes or asterisks as bullets
            r'Skills:([^#]*?)\n\n', # Skills section
            r'Technologies:([^#]*?)\n\n', # Technologies section
            r'Technical Skills:([^#]*?)\n\n' # Technical Skills section
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Split by commas or semicolons for lists
                parts = re.split(r'[,;]', match)
                for part in parts:
                    skill = part.strip()
                    # Add if reasonable length and not already in the list
                    if skill and 2 <= len(skill) <= 50 and skill not in skills:
                        skills.append(skill)
        
        # Try to extract directly from skills section if it exists
        if "skills" in sections_dict:
            skills_text = sections_dict["skills"]
            # Split by common separators
            more_skills = re.split(r'[,•:\n]', skills_text)
            more_skills = [s.strip() for s in more_skills if s.strip()]
            skills.extend([s for s in more_skills if s not in skills])
        
        # Extract education
        education = []
        if "education" in sections_dict:
            edu_text = sections_dict["education"]
            # Look for degree patterns
            degree_patterns = [
                r'(B\.?Tech|Bachelor of Technology|BTech|M\.?Tech|Master of Technology|MTech|B\.?E|Bachelor of Engineering|M\.?E|Master of Engineering|Ph\.?D|Doctor of Philosophy|B\.?Sc|Bachelor of Science|M\.?Sc|Master of Science)',
                r'(High School|Secondary|Higher Secondary)',
                r'(College|University|Institute|School)'
            ]
            
            for pattern in degree_patterns:
                matches = re.finditer(pattern, edu_text, re.IGNORECASE)
                for match in matches:
                    # Get the line containing this degree
                    start = max(0, match.start() - 100)
                    end = min(len(edu_text), match.end() + 100)
                    context = edu_text[start:end]
                    lines = context.split('\n')
                    for line in lines:
                        if match.group() in line:
                            if line.strip() and line.strip() not in education:
                                education.append(line.strip())
                            break
        
        # Extract work experience
        work_experience = []
        if "experience" in sections_dict:
            exp_text = sections_dict["experience"]
            
            # Common job title words
            job_titles = [
                "Engineer", "Developer", "Researcher", "Scientist", "Analyst", "Specialist",
                "Manager", "Director", "Lead", "Head", "Chief", "Officer", "Consultant",
                "Intern", "Associate", "Assistant", "Administrator", "Coordinator", "Designer",
                "Architect", "Supervisor", "President", "VP", "Technician", "Advisor"
            ]
            
            lines = exp_text.split('\n')
            current_job = ""
            
            for line in lines:
                # Potential indicators of a new job entry
                is_new_job = (
                    any(title in line for title in job_titles) or 
                    re.search(r'\b\d{4}\b', line) or  # Year
                    re.search(r'(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', line)  # Month abbreviation
                )
                
                if is_new_job and len(line.strip()) > 0:
                    if current_job:
                        work_experience.append(current_job.strip())
                    current_job = line
                elif current_job and line.strip():
                    current_job += " " + line
            
            if current_job:
                work_experience.append(current_job.strip())
        
        # Extract projects
        projects = []
        if "projects" in sections_dict:
            project_text = sections_dict["projects"]
            lines = project_text.split('\n')
            current_project = ""
            
            for line in lines:
                # Potential indicators of a new project entry
                is_new_project = (
                    line.strip() and (
                        line.strip()[0].isupper() or  # Starts with uppercase
                        re.search(r'\b\d{4}\b', line) or  # Contains a year
                        line.strip().endswith(':')  # Ends with colon
                    )
                )
                
                if is_new_project:
                    if current_project:
                        projects.append(current_project.strip())
                    current_project = line
                elif current_project and line.strip():
                    current_project += " " + line
            
            if current_project:
                projects.append(current_project.strip())
        
        # Determine field and recommended jobs
        field = self.determine_field(combined_text, skills)
        recommended_jobs = self.recommend_jobs(field, skills, combined_text)
        
        return {
            "contact_information": {
                "name": name,
                "email": email,
                "phone": phone
            },
            "skills": skills,
            "work_experience": work_experience,
            "education": education,
            "projects": projects,
            "field": field,
            "recommended_jobs": recommended_jobs[:5]  # Limit to top 5
        }
    
    def determine_field(self, text, skills):
        """Analyze text to determine professional field"""
        # Use a simple keyword-based approach to identify general field
        field_keywords = {
            "Software Development": ["developer", "programming", "software", "code", "app", "application", "web"],
            "Data Science": ["data", "analytics", "statistics", "machine learning", "analysis"],
            "AI/ML": ["artificial intelligence", "machine learning", "deep learning", "neural", "NLP", "computer vision"],
            "IT/System Admin": ["network", "system", "administrator", "IT ", "infrastructure", "support"],
            "Design": ["design", "UX", "UI", "user experience", "creative", "graphic"],
            "Marketing": ["marketing", "social media", "SEO", "content", "campaign", "brand"],
            "Finance": ["finance", "accounting", "financial", "investment", "budget", "tax"],
            "Sales": ["sales", "business development", "account manager", "customer", "client"],
            "Healthcare": ["health", "medical", "clinical", "patient", "doctor", "nurse"],
            "Engineering": ["engineering", "mechanical", "electrical", "civil", "hardware"],
            "Education": ["teaching", "education", "instructor", "professor", "curriculum"]
        }
        
        # Count keyword occurrences for each field
        field_scores = {field: 0 for field in field_keywords}
        text_lower = text.lower()
        
        for field, keywords in field_keywords.items():
            for keyword in keywords:
                count = text_lower.count(keyword.lower())
                field_scores[field] += count
        
        # Determine primary field
        if not any(field_scores.values()):
            return "General Professional"
        else:
            return max(field_scores, key=field_scores.get)
    
    def recommend_jobs(self, field, skills, text):
        """Generate job recommendations based on field and skills"""
        # Job mapping for common fields
        job_mappings = {
            "Software Development": [
                "Software Engineer", "Full Stack Developer", "Frontend Developer", 
                "Backend Developer", "Mobile Developer", "DevOps Engineer"
            ],
            "Data Science": [
                "Data Scientist", "Data Analyst", "Business Intelligence Analyst",
                "Data Engineer", "Statistician", "Database Administrator"
            ],
            "AI/ML": [
                "Machine Learning Engineer", "AI Researcher", "NLP Engineer",
                "Computer Vision Engineer", "ML Ops Engineer", "AI Product Manager"
            ],
            "IT/System Admin": [
                "Systems Administrator", "Network Engineer", "IT Support Specialist",
                "Cloud Engineer", "Security Analyst", "Infrastructure Manager"
            ],
            "Design": [
                "UX Designer", "UI Designer", "Product Designer", "Graphic Designer",
                "Creative Director", "Interaction Designer"
            ],
            "Marketing": [
                "Marketing Manager", "Digital Marketing Specialist", "SEO Specialist",
                "Content Strategist", "Social Media Manager", "Marketing Analyst"
            ],
            "Finance": [
                "Financial Analyst", "Accountant", "Financial Controller",
                "Investment Analyst", "Finance Manager", "Budget Analyst"
            ],
            "Sales": [
                "Sales Representative", "Account Executive", "Business Development Manager",
                "Sales Manager", "Customer Success Manager", "Account Manager"
            ],
            "Healthcare": [
                "Clinical Specialist", "Healthcare Analyst", "Medical Technician",
                "Healthcare Administrator", "Clinical Research Associate"
            ],
            "Engineering": [
                "Mechanical Engineer", "Electrical Engineer", "Civil Engineer",
                "Project Engineer", "Quality Engineer", "Process Engineer"
            ],
            "Education": [
                "Teacher", "Instructor", "Education Coordinator", "Curriculum Developer",
                "Academic Advisor", "E-Learning Specialist"
            ],
            "General Professional": [
                "Project Manager", "Business Analyst", "Consultant",
                "Operations Manager", "Program Coordinator", "Administrative Specialist"
            ]
        }
        
        # Get recommendations based on primary field
        recommended_jobs = []
        if field in job_mappings:
            recommended_jobs.extend(job_mappings[field][:3])
        
        # Add a few general recommendations if needed
        if len(recommended_jobs) < 5:
            general_jobs = job_mappings["General Professional"]
            for job in general_jobs:
                if job not in recommended_jobs:
                    recommended_jobs.append(job)
                    if len(recommended_jobs) >= 5:
                        break
        
        return recommended_jobs
    
    def identify_resume_sections(self, text):
        """Identify different sections in the resume"""
        # Common section headers in resumes
        section_patterns = {
            "contact": r"(?i)contact|personal info|profile",
            "summary": r"(?i)summary|objective|profile",
            "experience": r"(?i)experience|employment|work history|work experience",
            "education": r"(?i)education|academic|qualifications",
            "skills": r"(?i)skills|technical skills|technologies|competencies",
            "projects": r"(?i)projects|personal projects|professional projects",
            "certifications": r"(?i)certifications|certificates|credentials",
            "publications": r"(?i)publications|papers|articles",
        }
        
        # Find all section headers and their positions
        sections = {}
        section_positions = []
        
        # Add beginning of text as a position
        section_positions.append((0, "start"))
        
        # Find all section headers
        for section, pattern in section_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                # Get the line containing this match
                line_start = text.rfind('\n', 0, match.start()) + 1
                line_end = text.find('\n', match.end())
                if line_end == -1:
                    line_end = len(text)
                
                line = text[line_start:line_end].strip()
                
                # Check if this line is likely a header (all caps, bold, etc.)
                if (line.isupper() or line[0] == '#' or 
                    all(c.isupper() or not c.isalpha() for c in line) or
                    match.start() - line_start < 5):  # Match near beginning of line
                    section_positions.append((match.start(), section))
        
        # Add end of text as a position
        section_positions.append((len(text), "end"))
        
        # Sort positions
        section_positions.sort()
        
        # Extract sections
        for i in range(len(section_positions) - 1):
            pos, section = section_positions[i]
            next_pos, _ = section_positions[i + 1]
            
            if section != "start" and section != "end":
                sections[section] = text[pos:next_pos].strip()
        
        return sections
    
    def generate_embeddings(self, sections):
        """Generate embeddings for resume sections for semantic search"""
        embedded_sections = []
        
        for i, doc in enumerate(sections):
            try:
                embedding = self.embeddings.embed_query(doc.page_content)
                
                embedded_sections.append({
                    "section_id": i,
                    "content": doc.page_content,
                    "embedding": embedding
                })
            except Exception as e:
                # Skip embedding generation if it fails
                embedded_sections.append({
                    "section_id": i,
                    "content": doc.page_content,
                    "embedding": None
                })
        
        return embedded_sections

# Export SimpleResumeParser as ResumeParser to maintain compatibility
ResumeParser = SimpleResumeParser