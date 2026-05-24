import { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Brain, Trash2, Loader2 } from 'lucide-react';
import { Agent, Message, agentsApi, chatApi, messagesApi, memoryApi } from '../api';

export default function ChatPage() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const [showMemory, setShowMemory] = useState(false);
    const [facts, setFacts] = useState<any[]>([]);
    const [newFact, setNewFact] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        agentsApi.list().then(setAgents);
    }, []);

    useEffect(() => {
        if (selectedAgent) {
            messagesApi.byAgent(selectedAgent.id).then(setMessages);
            if (showMemory) loadFacts();
        }
    }, [selectedAgent]);

    const loadFacts = async () => {
        if (!selectedAgent) return;
        const res = await memoryApi.getLongTerm(selectedAgent.id);
        setFacts(res.facts || []);
    };

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || !selectedAgent || sending) return;
        const text = input;
        setInput('');
        setSending(true);

        // Optimistic user message
        const tempMsg: Message = {
            id: 'temp-' + Date.now(),
            agent_id: selectedAgent.id,
            role: 'user',
            content: text,
            channel: 'web',
            meta_info: {},
            tokens_used: 0,
            cost: 0,
            created_at: new Date().toISOString(),
        };
        setMessages(prev => [...prev, tempMsg]);

        try {
            const response = await chatApi.send(selectedAgent.id, text);
            // Replace temp msg + add response
            setMessages(prev => [
                ...prev.filter(m => m.id !== tempMsg.id),
                { ...tempMsg, id: 'user-' + Date.now() },
                response,
            ]);
        } catch (e: any) {
            setMessages(prev => [
                ...prev,
                {
                    id: 'error-' + Date.now(),
                    agent_id: selectedAgent.id,
                    role: 'assistant',
                    content: `Error: ${e.message}`,
                    channel: 'web',
                    meta_info: {},
                    tokens_used: 0,
                    cost: 0,
                    created_at: new Date().toISOString(),
                },
            ]);
        } finally {
            setSending(false);
        }
    };

    const handleAddFact = async () => {
        if (!newFact.trim() || !selectedAgent) return;
        await memoryApi.addFact(selectedAgent.id, newFact);
        setNewFact('');
        loadFacts();
    };

    const handleDeleteFact = async (factId: string) => {
        if (!selectedAgent) return;
        await memoryApi.deleteFact(selectedAgent.id, factId);
        loadFacts();
    };

    const handleClearMemory = async (type: string) => {
        if (!selectedAgent || !confirm(`Clear ${type} memory?`)) return;
        await memoryApi.clear(selectedAgent.id, type);
        if (type !== 'short') loadFacts();
    };

    return (
        <div className="flex h-full">
            {/* Agent Selector Sidebar */}
            <div className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
                <div className="p-3 border-b border-gray-700">
                    <h3 className="text-sm font-semibold text-gray-300">Select Agent</h3>
                </div>
                <div className="flex-1 overflow-auto p-2 space-y-1">
                    {agents.map(agent => (
                        <button
                            key={agent.id}
                            onClick={() => { setSelectedAgent(agent); setShowMemory(false); }}
                            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${selectedAgent?.id === agent.id
                                ? 'bg-blue-600 text-white'
                                : 'text-gray-300 hover:bg-gray-700'
                                }`}
                        >
                            <div className="font-medium">{agent.name}</div>
                            <div className="text-xs opacity-70">{agent.role}</div>
                        </button>
                    ))}
                    {agents.length === 0 && (
                        <p className="text-xs text-gray-500 p-3">No agents created yet</p>
                    )}
                </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col">
                {selectedAgent ? (
                    <>
                        {/* Header */}
                        <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                            <div>
                                <h2 className="font-semibold">{selectedAgent.name}</h2>
                                <p className="text-xs text-gray-400">{selectedAgent.model} · {selectedAgent.role}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => { setShowMemory(!showMemory); if (!showMemory) loadFacts(); }}
                                    className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs transition-colors ${showMemory ? 'bg-purple-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                        }`}
                                >
                                    <Brain size={14} /> Memory
                                </button>
                            </div>
                        </div>

                        {showMemory ? (
                            /* Memory Panel */
                            <div className="flex-1 overflow-auto p-4 space-y-4">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-lg font-semibold">Long-Term Memory</h3>
                                    <div className="flex gap-2">
                                        <button onClick={() => handleClearMemory('short')} className="px-2 py-1 bg-yellow-900/50 hover:bg-yellow-800 rounded text-xs text-yellow-300">Clear Short-Term</button>
                                        <button onClick={() => handleClearMemory('long')} className="px-2 py-1 bg-red-900/50 hover:bg-red-800 rounded text-xs text-red-300">Clear Long-Term</button>
                                    </div>
                                </div>

                                {/* Add fact */}
                                <div className="flex gap-2">
                                    <input
                                        value={newFact}
                                        onChange={e => setNewFact(e.target.value)}
                                        onKeyDown={e => e.key === 'Enter' && handleAddFact()}
                                        placeholder="Add a fact to long-term memory..."
                                        className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-purple-500"
                                    />
                                    <button onClick={handleAddFact} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm">Add</button>
                                </div>

                                {/* Facts list */}
                                <div className="space-y-2">
                                    {facts.map((fact, i) => (
                                        <div key={fact.id || i} className="flex items-start justify-between bg-gray-800 rounded-lg p-3 border border-gray-700">
                                            <div>
                                                <p className="text-sm">{fact.fact}</p>
                                                <p className="text-xs text-gray-500 mt-1">Source: {fact.source} · {fact.timestamp ? new Date(fact.timestamp).toLocaleString() : ''}</p>
                                            </div>
                                            <button onClick={() => handleDeleteFact(fact.id)} className="text-red-400 hover:text-red-300 ml-2">
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    ))}
                                    {facts.length === 0 && (
                                        <p className="text-sm text-gray-500 text-center py-8">No long-term memories yet. Add facts manually or ask the agent to remember things.</p>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <>
                                {/* Messages */}
                                <div className="flex-1 overflow-auto p-4 space-y-4">
                                    {messages.map(msg => (
                                        <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                            {msg.role !== 'user' && (
                                                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                                                    <Bot size={16} />
                                                </div>
                                            )}
                                            <div className={`max-w-[70%] rounded-xl px-4 py-2.5 ${msg.role === 'user'
                                                ? 'bg-blue-600 text-white'
                                                : 'bg-gray-800 border border-gray-700'
                                                }`}>
                                                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-[10px] opacity-50">
                                                        {new Date(msg.created_at).toLocaleTimeString()}
                                                    </span>
                                                    {msg.tokens_used > 0 && (
                                                        <span className="text-[10px] opacity-50">{msg.tokens_used} tokens</span>
                                                    )}
                                                </div>
                                            </div>
                                            {msg.role === 'user' && (
                                                <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center flex-shrink-0">
                                                    <User size={16} />
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                    {sending && (
                                        <div className="flex gap-3 justify-start">
                                            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                                                <Bot size={16} />
                                            </div>
                                            <div className="bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5">
                                                <Loader2 size={16} className="animate-spin text-gray-400" />
                                            </div>
                                        </div>
                                    )}
                                    <div ref={messagesEndRef} />
                                </div>

                                {/* Input */}
                                <div className="p-4 border-t border-gray-700">
                                    <div className="flex gap-2">
                                        <input
                                            value={input}
                                            onChange={e => setInput(e.target.value)}
                                            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                                            placeholder="Type a message..."
                                            disabled={sending}
                                            className="flex-1 px-4 py-2.5 bg-gray-800 border border-gray-700 rounded-xl text-sm focus:outline-none focus:border-blue-500 disabled:opacity-50"
                                        />
                                        <button
                                            onClick={handleSend}
                                            disabled={sending || !input.trim()}
                                            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-xl transition-colors"
                                        >
                                            <Send size={16} />
                                        </button>
                                    </div>
                                </div>
                            </>
                        )}
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-500">
                        <div className="text-center">
                            <Bot size={48} className="mx-auto mb-4 opacity-30" />
                            <p>Select an agent to start chatting</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
