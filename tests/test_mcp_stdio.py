"""Exercise the actual stdio adapter from a neutral directory."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip('mcp')
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_shared_stdio_server_is_unbound_and_keeps_projects_separate(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'src'
    repos = [tmp_path / name for name in ('project-a', 'project-b')]
    for repo in repos:
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    neutral = tmp_path / 'server-cwd'
    neutral.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.startswith('DONEGATE_MCP_')}
    env['PYTHONPATH'] = str(source)

    async def scenario():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'donegate_mcp.mcp.server'], cwd=neutral, env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                initialization = await session.initialize()
                assert initialization.serverInfo.name == 'donegate_mcp'
                assert initialization.serverInfo.version == '0.4.1'
                tool_list = await session.list_tools()
                tools = {tool.name: tool for tool in tool_list.tools}
                assert {'project_context', 'task_get', 'task_activate'} <= tools.keys()
                assert 'compact' in tools['task_create'].inputSchema['properties']

                async def call(name, **args):
                    result = await session.call_tool(name, args)
                    return result.structuredContent or json.loads(result.content[0].text)

                missing = await call('project_dashboard')
                assert missing['ok'] is False
                assert 'target required' in missing['errors'][0]
                assert not (neutral / '.donegate-mcp').exists()
                for repo in repos:
                    assert (await call('project_init', project_name=repo.name, repo_root=str(repo)))['ok']
                    created = await call('task_create', title=repo.name, spec_ref='spec.md', repo_root=str(repo), compact=True)
                    assert created['task']['task_id'] == 'TASK-0001'
                    assert (await call('task_activate', task_id='TASK-0001', repo_root=str(repo), compact=True))['ok']
                for repo in reversed(repos):
                    context = (await call('project_context', repo_root=str(repo)))['context']
                    assert context['project_name'] == repo.name
                    assert context['active_task']['title'] == repo.name
                mismatch = await call('task_create', title='wrong-project', spec_ref='spec.md', repo_root=str(repos[0]), data_root=str(repos[1] / '.donegate-mcp'))
                assert mismatch['ok'] is False
                assert 'ownership mismatch' in mismatch['errors'][0]
                for repo in repos:
                    assert len(list((repo / '.donegate-mcp' / 'tasks').glob('TASK-*.json'))) == 1
    asyncio.run(scenario())
