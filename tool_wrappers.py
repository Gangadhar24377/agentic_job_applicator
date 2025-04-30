# tool_wrappers.py
from typing import Any, Dict, List, Union, Optional
from langchain.tools import Tool

class ToolWrapper:
    @staticmethod
    def wrap_tool(tool_instance):
        """Wrap a custom tool to make it compatible with CrewAI and LangChain"""
        # Check if the tool already has the necessary properties and methods
        if hasattr(tool_instance, "name") and hasattr(tool_instance, "description") and hasattr(tool_instance, "run"):
            # Create a LangChain Tool instance
            return Tool(
                name=tool_instance.name,
                description=tool_instance.description,
                func=tool_instance.run
            )
        else:
            raise ValueError(f"Tool {type(tool_instance)} does not have required attributes (name, description, run)")