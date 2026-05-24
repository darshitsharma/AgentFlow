import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Brain, Search, X, Trash } from 'lucide-react';
import { Agent, agentsApi, memoryApi } from '../api';
import AgentForm from '../components/AgentForm';

export default function AgentsPage() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [showForm, setShowForm] = useState(false);
    const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
    const [loading, setLoading] = useState(true);
    const [memoryAgent, setMemoryAgent] = useState<Agent | null>(null);
    const [facts, setFacts] = useState<any[]>([]);
    const [recallQuery, setRecallQuery] = useState('');
    const [recallResults, setRecallResults] = useState<{ short_term: any[]; long_term: any[] } | null>(null);
    const [recalling, setRecalling] = useState(false);
    const [newFact, setNewFact] = useState('');

    const loadAgents = async () => {
        try {
            const data = await agentsApi.list();
            setAgents(data);
        } catch (e) {
            console.error('Failed to load agents:', e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { loadAgents(); }, []);

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this agent?')) return;
        await agentsApi.delete(id);
        loadAgents();
    };

    const handleSave = async (data: Partial<Agent>) => {
        if (editingAgent) {
            await agentsApi.update(editingAgent.id, data);
        } else {
            await agentsApi.create(data);
        }
        setShowForm(false);
        setEditingAgent(null);
        loadAgents();
    };

    const openMemory = async (agent: Agent) => {
        setMemoryAgent(agent);
        setRecallResults(null);
        setRecallQuery('');
        setNewFact('');
        try {
            const res = await memoryApi.getLongTerm(agent.id);
            setFacts(res.facts || []);
        } catch { setFacts([]); }
    };

    const handleRecall = async () => {
        if (!memoryAgent || !recallQuery.trim()) return;
        setRecalling(true);
        try {
            const res = await memoryApi.recall(memoryAgent.id, recallQuery);
            setRecallResults({ short_term: res.short_term || [], long_term: res.long_term || [] });
        } catch { setRecallResults({ short_term: [], long_term: [] }); }
        finally { setRecalling(false); }
    };

    const handleAddFact = async () => {
        if (!memoryAgent || !newFact.trim()) return;
        await memoryApi.addFact(memoryAgent.id, newFact);
        setNewFact('');
        const res = await memoryApi.getLongTerm(memoryAgent.id);
        setFacts(res.facts || []);
    };

    const handleDeleteFact = async (factId: string) => {
        if (!memoryAgent) return;
        await memoryApi.deleteFact(memoryAgent.id, factId);
        const res = await memoryApi.getLongTerm(memoryAgent.id);
        setFacts(res.facts || []);
    };

    const handleClearMemory = async (type: string) => {
        if (!memoryAgent || !confirm(`Clear ${type} memory for ${memoryAgent.name}?`)) return;
        await memoryApi.clear(memoryAgent.id, type);
        if (type === 'all' || type === 'long_term') setFacts([]);
        if (recallResults) setRecallResults(null);
    };

    if (loading) return <div className="p-8 text-gray-400">Loading agents...</div>;

    return (
        <div className="p-8">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">Agents</h2>
                <button
                    onClick={() => { setEditingAgent(null); setShowForm(true); }}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
                >
                    <Plus size={16} /> Create Agent
                </button>
            </div>

            {showForm && (
                <AgentForm
                    agent={editingAgent}
                    onSave={handleSave}
                    onCancel={() => { setShowForm(false); setEditingAgent(null); }}
                />
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agents.map((agent) => (
                    <div key={agent.id} className="bg-gray-800 rounded-xl p-5 border border-gray-700 hover:border-gray-600 transition-colors">
                        <div className="flex items-start justify-between mb-3">
                            <div>
                                <h3 className="font-semibold text-lg">{agent.name}</h3>
                                <p className="text-sm text-gray-400">{agent.role}</p>
                            </div>
                            <span className={`px-2 py-0.5 rounded text-xs ${agent.is_active ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
                                {agent.is_active ? 'Active' : 'Inactive'}
                            </span>
                        </div>
                        <div className="text-xs text-gray-500 space-y-1 mb-4">
                            <p>Model: <span className="text-gray-300">{agent.model}</span></p>
                            <p>Tools: <span className="text-gray-300">{agent.tools.length > 0 ? agent.tools.join(', ') : 'None'}</span></p>
                            <p>Channels: <span className="text-gray-300">{agent.channels.length > 0 ? agent.channels.join(', ') : 'None'}</span></p>
                            <p>Memory: <span className="text-gray-300">{agent.memory_enabled ? 'Enabled' : 'Disabled'}</span></p>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => { setEditingAgent(agent); setShowForm(true); }}
                                className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs transition-colors"
                            >
                                <Edit2 size={12} /> Edit
                            </button>
                            {agent.memory_enabled && (
                                <button
                                    onClick={() => openMemory(agent)}
                                    className="flex items-center gap-1 px-3 py-1.5 bg-purple-900/50 hover:bg-purple-800 rounded text-xs transition-colors text-purple-300"
                                >
                                    <Brain size={12} /> Memory
                                </button>
                            )}
                            <button
                                onClick={() => handleDelete(agent.id)}
                                className="flex items-center gap-1 px-3 py-1.5 bg-red-900/50 hover:bg-red-800 rounded text-xs transition-colors text-red-300"
                            >
                                <Trash2 size={12} /> Delete
                            </button>
                        </div>
                    </div>
                ))}
            </div>

            {agents.length === 0 && !showForm && (
                <div className="text-center py-16 text-gray-500">
                    <p className="text-lg mb-2">No agents yet</p>
                    <p className="text-sm">Create your first AI agent to get started</p>
                </div>
            )}

            {/* Memory Panel Overlay */}
            {memoryAgent && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
                    <div className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-[700px] max-h-[80vh] flex flex-col">
                        {/* Header */}
                        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-700">
                            <div className="flex items-center gap-2">
                                <Brain size={18} className="text-purple-400" />
                                <h3 className="text-lg font-semibold">{memoryAgent.name} — Memory</h3>
                            </div>
                            <button onClick={() => setMemoryAgent(null)} className="text-gray-400 hover:text-white"><X size={18} /></button>
                        </div>

                        <div className="flex-1 overflow-auto p-5 space-y-5">
                            {/* Semantic Recall */}
                            <div>
                                <h4 className="text-sm font-semibold text-gray-300 mb-2">Semantic Recall</h4>
                                <div className="flex gap-2">
                                    <input
                                        value={recallQuery}
                                        onChange={(e) => setRecallQuery(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleRecall()}
                                        placeholder="Search agent's memory..."
                                        className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm focus:outline-none focus:border-purple-500"
                                    />
                                    <button onClick={handleRecall} disabled={recalling} className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 rounded text-xs">
                                        <Search size={12} /> {recalling ? 'Searching...' : 'Recall'}
                                    </button>
                                </div>
                                {recallResults && (
                                    <div className="mt-3 space-y-3">
                                        {recallResults.short_term.length > 0 && (
                                            <div>
                                                <p className="text-xs font-medium text-blue-400 mb-1">Short-Term Memory ({recallResults.short_term.length})</p>
                                                <div className="space-y-1">
                                                    {recallResults.short_term.map((m: any, i: number) => (
                                                        <div key={i} className="bg-gray-900 rounded p-2 text-xs">
                                                            <div className="flex items-center gap-2 mb-1">
                                                                <span className={`px-1.5 py-0.5 rounded text-[10px] ${m.role === 'user' ? 'bg-blue-900 text-blue-300' : 'bg-green-900 text-green-300'}`}>{m.role}</span>
                                                                {m.distance != null && <span className="text-gray-500">similarity: {(1 - m.distance).toFixed(3)}</span>}
                                                            </div>
                                                            <p className="text-gray-300">{m.content}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                        {recallResults.long_term.length > 0 && (
                                            <div>
                                                <p className="text-xs font-medium text-purple-400 mb-1">Long-Term Memory ({recallResults.long_term.length})</p>
                                                <div className="space-y-1">
                                                    {recallResults.long_term.map((m: any, i: number) => (
                                                        <div key={i} className="bg-gray-900 rounded p-2 text-xs">
                                                            <div className="flex items-center gap-2 mb-1">
                                                                <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-900 text-purple-300">fact</span>
                                                                {m.distance != null && <span className="text-gray-500">similarity: {(1 - m.distance).toFixed(3)}</span>}
                                                            </div>
                                                            <p className="text-gray-300">{m.content}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                        {recallResults.short_term.length === 0 && recallResults.long_term.length === 0 && (
                                            <p className="text-xs text-gray-500">No memories found for this query.</p>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Long-Term Facts */}
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <h4 className="text-sm font-semibold text-gray-300">Long-Term Facts ({facts.length})</h4>
                                    <div className="flex gap-1">
                                        <button onClick={() => handleClearMemory('short_term')} className="px-2 py-1 text-[10px] bg-gray-700 hover:bg-gray-600 rounded text-gray-400">Clear Short-Term</button>
                                        <button onClick={() => handleClearMemory('long_term')} className="px-2 py-1 text-[10px] bg-gray-700 hover:bg-gray-600 rounded text-gray-400">Clear Long-Term</button>
                                        <button onClick={() => handleClearMemory('all')} className="px-2 py-1 text-[10px] bg-red-900/50 hover:bg-red-800 rounded text-red-400">Clear All</button>
                                    </div>
                                </div>
                                {/* Add fact */}
                                <div className="flex gap-2 mb-3">
                                    <input
                                        value={newFact}
                                        onChange={(e) => setNewFact(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleAddFact()}
                                        placeholder="Add a fact to long-term memory..."
                                        className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm focus:outline-none focus:border-purple-500"
                                    />
                                    <button onClick={handleAddFact} className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 rounded text-xs">Add</button>
                                </div>
                                {/* Facts list */}
                                <div className="space-y-1 max-h-48 overflow-auto">
                                    {facts.map((fact: any) => (
                                        <div key={fact.id} className="flex items-start justify-between bg-gray-900 rounded p-2 text-xs group">
                                            <div className="flex-1">
                                                <p className="text-gray-300">{fact.content || fact.document}</p>
                                                <p className="text-gray-600 text-[10px] mt-0.5">
                                                    {fact.source && `Source: ${fact.source}`}
                                                    {fact.timestamp && ` · ${new Date(fact.timestamp).toLocaleString()}`}
                                                </p>
                                            </div>
                                            <button onClick={() => handleDeleteFact(fact.id)} className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-300 ml-2 mt-0.5">
                                                <Trash size={12} />
                                            </button>
                                        </div>
                                    ))}
                                    {facts.length === 0 && (
                                        <p className="text-xs text-gray-500 text-center py-4">No long-term facts stored yet.</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
