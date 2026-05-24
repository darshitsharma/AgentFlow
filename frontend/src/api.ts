const API_BASE = '/api';

export interface Agent {
    id: string;
    name: string;
    role: string;
    system_prompt: string;
    model: string;
    tools: string[];
    channels: string[];
    schedule: string | null;
    memory_enabled: boolean;
    max_tokens: number;
    temperature: number;
    guardrails: Record<string, any>;
    skills: string[];
    interaction_rules: Record<string, any>;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface Workflow {
    id: string;
    name: string;
    description: string;
    graph: Record<string, any>;
    channels: string[];
    is_template: boolean;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface Message {
    id: string;
    agent_id: string;
    role: string;
    content: string;
    channel: string;
    meta_info: Record<string, any>;
    tokens_used: number;
    cost: number;
    created_at: string;
}

export interface AgentLog {
    id: string;
    agent_id: string;
    workflow_execution_id: string | null;
    level: string;
    event: string;
    details: Record<string, any>;
    created_at: string;
}

export interface WorkflowExecution {
    id: string;
    workflow_id: string;
    status: string;
    input_data: Record<string, any>;
    output_data: Record<string, any>;
    started_at: string | null;
    completed_at: string | null;
    created_at: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || 'Request failed');
    }
    if (res.status === 204) return undefined as T;
    return res.json();
}

// Agents
export const agentsApi = {
    list: () => request<Agent[]>('/agents/'),
    get: (id: string) => request<Agent>(`/agents/${id}`),
    create: (data: Partial<Agent>) => request<Agent>('/agents/', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Partial<Agent>) => request<Agent>(`/agents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/agents/${id}`, { method: 'DELETE' }),
};

// Workflows
export const workflowsApi = {
    list: () => request<Workflow[]>('/workflows/'),
    templates: () => request<Workflow[]>('/workflows/templates'),
    get: (id: string) => request<Workflow>(`/workflows/${id}`),
    create: (data: Partial<Workflow>) => request<Workflow>('/workflows/', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Partial<Workflow>) => request<Workflow>(`/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/workflows/${id}`, { method: 'DELETE' }),
};

// Messages
export const messagesApi = {
    byAgent: (agentId: string, limit = 50) => request<Message[]>(`/messages/agent/${agentId}?limit=${limit}`),
    byChannel: (channel: string, limit = 50) => request<Message[]>(`/messages/channel/${channel}?limit=${limit}`),
};

// Chat
export const chatApi = {
    send: (agentId: string, message: string, channel = 'web') =>
        request<Message>(`/chat/${agentId}`, { method: 'POST', body: JSON.stringify({ content: message, channel }) }),
};

// Memory
export const memoryApi = {
    getLongTerm: (agentId: string) => request<{ agent_id: string; facts: any[] }>(`/memory/${agentId}/long-term`),
    addFact: (agentId: string, fact: string, source = 'manual') =>
        request<any>(`/memory/${agentId}/long-term`, { method: 'POST', body: JSON.stringify({ fact, source }) }),
    deleteFact: (agentId: string, factId: string) =>
        request<any>(`/memory/${agentId}/long-term/${factId}`, { method: 'DELETE' }),
    recall: (agentId: string, query: string) =>
        request<any>(`/memory/${agentId}/recall`, { method: 'POST', body: JSON.stringify({ query }) }),
    clear: (agentId: string, memoryType = 'all') =>
        request<any>(`/memory/${agentId}/clear?memory_type=${memoryType}`, { method: 'DELETE' }),
};

// Logs
export const logsApi = {
    byAgent: (agentId: string, limit = 100) => request<AgentLog[]>(`/logs/agent/${agentId}?limit=${limit}`),
    byExecution: (executionId: string) => request<AgentLog[]>(`/logs/execution/${executionId}`),
    recent: (limit = 50) => request<AgentLog[]>(`/logs/recent?limit=${limit}`),
    stats: () => request<any>(`/logs/stats`),
};

// Workflow Execution
export const executionApi = {
    start: (workflowId: string, inputData: Record<string, any> = {}) =>
        request<WorkflowExecution>(`/workflows/${workflowId}/execute`, { method: 'POST', body: JSON.stringify({ input_data: inputData }) }),
};
