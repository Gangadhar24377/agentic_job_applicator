# llm_factory.py
from typing import Dict, Any, Optional
import os

class LLMConfig:
    """Configuration for various LLM providers and models"""
    def __init__(self, 
                 provider: str,
                 model_name: str,
                 api_key: Optional[str] = None,
                 model_path: Optional[str] = None,
                 parameters: Dict[str, Any] = None):
        self.provider = provider
        self.model_name = model_name
        self.api_key = api_key
        self.model_path = model_path
        self.parameters = parameters or {}

class LLMFactory:
    """Factory for creating LLM instances based on provider"""
    
    @staticmethod
    def create_llm(config: LLMConfig):
        """Create an LLM instance based on the provided configuration"""
        if config.provider.lower() == "openai":
            try:
                # Try newer import path first
                from langchain_openai import ChatOpenAI
                
                api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OpenAI API key is required")
                    
                return ChatOpenAI(
                    model=config.model_name,
                    openai_api_key=api_key,
                    temperature=config.parameters.get("temperature", 0.7),
                    max_tokens=config.parameters.get("max_tokens", None)
                )
            except ImportError:
                # Fall back to older import path
                from langchain.chat_models import ChatOpenAI
                
                api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OpenAI API key is required")
                    
                return ChatOpenAI(
                    model_name=config.model_name,
                    openai_api_key=api_key,
                    temperature=config.parameters.get("temperature", 0.7),
                    max_tokens=config.parameters.get("max_tokens", None)
                )
            
        elif config.provider.lower() == "huggingface":
            api_key = config.api_key or os.environ.get("HUGGINGFACE_API_KEY")
            
            if config.model_path:  # Local model
                try:
                    # Try newer import path first
                    from langchain_community.llms import HuggingFacePipeline
                except ImportError:
                    # Fall back to older import path
                    from langchain.llms import HuggingFacePipeline
                
                try:
                    import torch
                    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
                    
                    tokenizer = AutoTokenizer.from_pretrained(config.model_path)
                    model = AutoModelForCausalLM.from_pretrained(
                        config.model_path,
                        device_map="auto",
                        torch_dtype=torch.float16
                    )
                    
                    pipe = pipeline(
                        "text-generation",
                        model=model,
                        tokenizer=tokenizer,
                        max_new_tokens=config.parameters.get("max_tokens", 512),
                        temperature=config.parameters.get("temperature", 0.7)
                    )
                    
                    return HuggingFacePipeline(pipeline=pipe)
                except Exception as e:
                    raise ValueError(f"Error initializing HuggingFace pipeline: {str(e)}")
            else:  # API-based model
                if not api_key:
                    raise ValueError("HuggingFace API key is required for hosted models")
                
                try:
                    # Try newer import path first
                    from langchain_huggingface import HuggingFaceEndpoint
                except ImportError:
                    # Fall back to older import path
                    try:
                        from langchain.llms import HuggingFaceEndpoint
                    except ImportError:
                        raise ImportError("HuggingFace integration not available. Please install with: pip install langchain-huggingface")
                
                return HuggingFaceEndpoint(
                    endpoint_url=f"https://api-inference.huggingface.co/models/{config.model_name}",
                    huggingfacehub_api_token=api_key,
                    task="text-generation",
                    max_new_tokens=config.parameters.get("max_tokens", 512)
                )
                
        elif config.provider.lower() == "ollama":
            try:
                # Try newer import path first
                from langchain_community.llms import Ollama
            except ImportError:
                # Fall back to older import path
                try:
                    from langchain.llms import Ollama
                except ImportError:
                    raise ImportError("Ollama integration not available. Please ensure Ollama is installed and running.")
            
            # Default to localhost if not specified
            endpoint = config.parameters.get("endpoint", "http://localhost:11434")
            
            return Ollama(
                model=config.model_name,
                base_url=endpoint,
                temperature=config.parameters.get("temperature", 0.7)
            )
            
        elif config.provider.lower() == "anthropic":
            try:
                # Try newer import path first
                from langchain_anthropic import ChatAnthropic
            except ImportError:
                # Fall back to older import path
                try:
                    from langchain.chat_models import ChatAnthropic
                except ImportError:
                    raise ImportError("Anthropic integration not available. Please install with: pip install langchain-anthropic")
            
            api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("Anthropic API key is required")
                
            return ChatAnthropic(
                model=config.model_name,
                anthropic_api_key=api_key,
                temperature=config.parameters.get("temperature", 0.7),
                max_tokens=config.parameters.get("max_tokens", 1000)
            )
            
        elif config.provider.lower() == "custom":
            endpoint_url = config.parameters.get("endpoint_url")
            if not endpoint_url:
                raise ValueError("Custom endpoint URL is required")
                
            # This would need to be customized for specific endpoints
            # Here's a minimal implementation that assumes a basic API interface
            
            class CustomLLM:
                def __init__(self, endpoint, api_key=None, **kwargs):
                    import requests
                    self.endpoint = endpoint
                    self.api_key = api_key
                    self.kwargs = kwargs
                    self.session = requests.Session()
                
                def invoke(self, prompt):
                    import requests
                    
                    headers = {}
                    if self.api_key:
                        headers["Authorization"] = f"Bearer {self.api_key}"
                    
                    payload = {
                        "prompt": prompt,
                        "temperature": self.kwargs.get("temperature", 0.7),
                        "max_tokens": self.kwargs.get("max_tokens", 1000)
                    }
                    
                    response = self.session.post(
                        self.endpoint,
                        headers=headers,
                        json=payload
                    )
                    
                    response.raise_for_status()
                    return response.json().get("text", "")
            
            return CustomLLM(
                endpoint=endpoint_url,
                api_key=config.api_key,
                temperature=config.parameters.get("temperature", 0.7),
                max_tokens=config.parameters.get("max_tokens", 1000)
            )
            
        else:
            raise ValueError(f"Unsupported LLM provider: {config.provider}")

class AgentFactory:
    """Factory for creating agents with different LLM backends"""
    
    @staticmethod
    def create_agent(
        role: str,
        goal: str,
        backstory: str,
        tools: list,
        llm_config: LLMConfig,
        verbose: bool = False
    ):
        """Create an agent with the specified LLM configuration"""
        # Import here to avoid circular imports
        try:
            from crewai import Agent
            
            llm = LLMFactory.create_llm(llm_config)
            
            return Agent(
                role=role,
                goal=goal,
                backstory=backstory,
                tools=tools,
                llm=llm,
                verbose=verbose
            )
        except ImportError:
            raise ImportError("CrewAI not installed. Please install with: pip install crewai")