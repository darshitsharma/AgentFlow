import { useState } from 'react';
import { Agent } from '../api';

const AVAILABLE_TOOLS = ['web_search', 'calculator', 'code_executor', 'file_reader', 'weather', 'summarizer'];
const AVAILABLE_CHANNELS = ['web', 'telegram'];
const AVAILABLE_MODELS = ['llama3.1:8b', 'mistral:7b', 'gemma2:9b', 'phi3:mini'];

interface Props {
    agent: Agent | null;
    onSave: (data: Partial<Agent>) => void;
    onCancel: () => void;
}

export default function AgentForm({ agent, onSave, onCancel }: Props) {
    const [form, setForm] = useState({
        name: agent?.name || '',
        role: agent?.role || '',
        system_prompt: agent?.system_prompt || '',
        model: agent?.model || 'llama3.1:8b',
        tools: agent?.tools || [],
        channels: agent?.channels || [],
        schedule: agent?.schedule || '',
        memory_enabled: agent?.memory_enabled ?? true,
        max_tokens: agent?.max_tokens || 4096,
        temperature: agent?.temperature || 0.7,
        guardrails: agent?.guardrails || {},
        skills: agent?.skills || [],
        interaction_rules: agent?.interaction_rules || {},
    });

    const toggleItem = (field: 'tools' | 'channels', item: string) => {
        setForm((prev) => ({
            ...prev,
            [field]: prev[field].includes(item)
                ? prev[field].filter((i) => i !== item)
                : [...prev[field], item],
        }));
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSave({
            ...form,
            schedule: form.schedule || null,
        } as Partial<Agent>);
    };

    return (
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 mb-6">
            <h3 className="text-lg font-semibold mb-4">{agent ? 'Edit Agent' : 'Create Agent'}</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Name *</label>
                        <input
                            type="text"
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Role *</label>
                        <input
                            type="text"
                            value={form.role}
                            onChange={(e) => setForm({ ...form, role: e.target.value })}
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                            required
                        />
                    </div>
                </div>

                <div>
                    <label className="block text-sm text-gray-400 mb-1">System Prompt</label>
                    <textarea
                        value={form.system_prompt}
                        onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
                        rows={4}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500 resize-none"
                    />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Model</label>
                        <select
                            value={form.model}
                            onChange={(e) => setForm({ ...form, model: e.target.value })}
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                        >
                            {AVAILABLE_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Max Tokens</label>
                        <input
                            type="number"
                            value={form.max_tokens}
                            onChange={(e) => setForm({ ...form, max_tokens: parseInt(e.target.value) })}
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Temperature</label>
                        <input
                            type="number"
                            step="0.1"
                            min="0"
                            max="2"
                            value={form.temperature}
                            onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                </div>

                <div>
                    <label className="block text-sm text-gray-400 mb-1">Tools</label>
                    <div className="flex flex-wrap gap-2">
                        {AVAILABLE_TOOLS.map((tool) => (
                            <button
                                key={tool}
                                type="button"
                                onClick={() => toggleItem('tools', tool)}
                                className={`px-3 py-1 rounded text-xs transition-colors ${form.tools.includes(tool)
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                    }`}
                            >
                                {tool}
                            </button>
                        ))}
                    </div>
                </div>

                <div>
                    <label className="block text-sm text-gray-400 mb-1">Channels</label>
                    <div className="flex flex-wrap gap-2">
                        {AVAILABLE_CHANNELS.map((ch) => (
                            <button
                                key={ch}
                                type="button"
                                onClick={() => toggleItem('channels', ch)}
                                className={`px-3 py-1 rounded text-xs transition-colors ${form.channels.includes(ch)
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                                    }`}
                            >
                                {ch}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Schedule (cron expression)</label>
                        <input
                            type="text"
                            value={form.schedule}
                            onChange={(e) => setForm({ ...form, schedule: e.target.value })}
                            placeholder="e.g. 0 9 * * * (daily at 9am)"
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                        />
                    </div>
                    <div className="flex items-center gap-3 pt-6">
                        <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={form.memory_enabled}
                                onChange={(e) => setForm({ ...form, memory_enabled: e.target.checked })}
                                className="rounded"
                            />
                            Enable Memory
                        </label>
                    </div>
                </div>

                <div className="flex items-center gap-3 pt-2">
                    <button
                        type="submit"
                        className="px-5 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors"
                    >
                        {agent ? 'Update Agent' : 'Create Agent'}
                    </button>
                    <button
                        type="button"
                        onClick={onCancel}
                        className="px-5 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
                    >
                        Cancel
                    </button>
                </div>
            </form>
        </div>
    );
}
