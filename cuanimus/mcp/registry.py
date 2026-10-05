"""
CUANIMUS Model Context Protocol (MCP) Tool, Resource, and Prompt Registry.
Provides registration, permission introspection, schema generation,
and dispatch for MCP endpoints.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Optional, List
from cuanimus.agent.identity import AgentIdentity, AgentPermission


@dataclass
class McpToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    permission_required: Optional[AgentPermission]
    handler: Callable[[Dict[str, Any], Dict[str, Any]], Any]

    def to_mcp_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class McpResourceDefinition:
    uri: str
    name: str
    description: str
    mime_type: str
    handler: Callable[[Dict[str, Any]], str]

    def to_mcp_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


@dataclass
class McpPromptDefinition:
    name: str
    description: str
    arguments: List[Dict[str, Any]]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]

    def to_mcp_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


class McpRegistry:
    """Central registry for MCP capabilities."""
    _tools: Dict[str, McpToolDefinition] = {}
    _resources: Dict[str, McpResourceDefinition] = {}
    _prompts: Dict[str, McpPromptDefinition] = {}

    @classmethod
    def register_tool(
        cls,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        permission_required: Optional[AgentPermission],
        handler: Callable[[Dict[str, Any], Dict[str, Any]], Any],
    ) -> None:
        cls._tools[name] = McpToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            permission_required=permission_required,
            handler=handler,
        )

    @classmethod
    def register_resource(
        cls,
        uri: str,
        name: str,
        description: str,
        mime_type: str,
        handler: Callable[[Dict[str, Any]], str],
    ) -> None:
        cls._resources[uri] = McpResourceDefinition(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
            handler=handler,
        )

    @classmethod
    def register_prompt(
        cls,
        name: str,
        description: str,
        arguments: List[Dict[str, Any]],
        handler: Callable[[Dict[str, Any]], Dict[str, Any]],
    ) -> None:
        cls._prompts[name] = McpPromptDefinition(
            name=name,
            description=description,
            arguments=arguments,
            handler=handler,
        )

    @classmethod
    def get_tool(cls, name: str) -> Optional[McpToolDefinition]:
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> List[Dict[str, Any]]:
        return [tool.to_mcp_dict() for tool in cls._tools.values()]

    @classmethod
    def get_resource(cls, uri: str) -> Optional[McpResourceDefinition]:
        return cls._resources.get(uri)

    @classmethod
    def list_resources(cls) -> List[Dict[str, Any]]:
        return [res.to_mcp_dict() for res in cls._resources.values()]

    @classmethod
    def get_prompt(cls, name: str) -> Optional[McpPromptDefinition]:
        return cls._prompts.get(name)

    @classmethod
    def list_prompts(cls) -> List[Dict[str, Any]]:
        return [prompt.to_mcp_dict() for prompt in cls._prompts.values()]

    @classmethod
    def clear(cls) -> None:
        cls._tools.clear()
        cls._resources.clear()
        cls._prompts.clear()
